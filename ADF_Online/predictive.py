"""
=============================================================================
MODELO PREDITIVO AO VIVO — DESEMPENHO DE ATLETAS DE FUTEBOL (V4.0 - POR TEMPO)
=============================================================================
Agora o sistema treina modelos ML separadamente para o 1º e 2º Tempo, 
respeitando a fisiologia da queda de rendimento real do atleta.
=============================================================================
"""

import os
import warnings
import numpy as np
import pandas as pd
import plotly.express as px

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error
import xgboost as xgb
import shap
import pickle

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
DIRETORIO_ATUAL      = os.path.dirname(os.path.abspath(__file__))
CAMINHO_EXCEL        = os.path.join(DIRETORIO_ATUAL, 'ADF OnLine 2024.xlsb')
DIRETORIO_MODELOS    = os.path.join(DIRETORIO_ATUAL, 'Models')
N_SPLITS_CV          = 5
JANELA_INTRA         = 5
RANDOM_STATE         = 42

TARGETS = ['Dist_Total', 'Load_Total', 'V4_Dist', 'V5_Dist', 'V4_Eff', 'V5_Eff', 'HIA_Total']

print("=" * 65)
print("  MODELO PREDITIVO AO VIVO — v4.0 (SEPARADO POR TEMPO)")
print("=" * 65)

# ─────────────────────────────────────────────────────────────────────────────
# 1 & 2. CARREGAMENTO E COLUNAS DERIVADAS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/5] Carregando dados e variáveis derivadas...")

df = pd.read_excel(CAMINHO_EXCEL, engine='calamine')
df.columns = df.columns.str.strip()
df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
df = df.dropna(subset=['Data', 'Name', 'Interval', 'Período']) # Agora exige Período
df = df.sort_values(['Name', 'Data', 'Período', 'Interval']).reset_index(drop=True)

# HIA
hia_cols = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff']
for c in hia_cols:
    if c not in df.columns: df[c] = 0
df['HIA'] = df[hia_cols].sum(axis=1)

# HR Pct
hr_col = 'Avg Heart Rate As Percentage Of Max' if 'Avg Heart Rate As Percentage Of Max' in df.columns else 'Heart Rate As Percentage Of Max'
df['HR_Pct'] = df[hr_col].fillna(0) if hr_col in df.columns else 0

# Diff Gols
def extrair_diff_gols(placar):
    s = str(placar).strip().lower()
    if any(x in s for x in ['vencendo', 'vitoria', 'vitória', 'ganhando', 'v']): return 1
    if any(x in s for x in ['perdendo', 'derrota', 'd']): return -1
    return 0

df['Diff_Gols'] = df['Placar'].apply(extrair_diff_gols) if 'Placar' in df.columns else 0
df['Resultado'] = df['Diff_Gols'].apply(lambda x: 'V' if x > 0 else ('D' if x < 0 else 'E'))

df['Min_Num'] = pd.to_numeric(df['Interval (min)' if 'Interval (min)' in df.columns else 'Interval'], errors='coerce').fillna(0)

# ─────────────────────────────────────────────────────────────────────────────
# 3. HISTÓRICO E RECUPERAÇÃO (AGRUPADO POR TEMPO)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/5] Construindo histórico agrupado por 1º e 2º Tempo...")

agg_dict = {
    'Total Distance':   'sum', 'Player Load':      'sum', 'HIA':              'sum',
    'V4 Dist':          'sum', 'V5 Dist':          'sum', 'V4 To8 Eff':       'sum',
    'V5 To8 Eff':       'sum', 'HR_Pct':           'mean','Min_Num':          'max',
    'Diff_Gols':        'last','Resultado':        'last',
}
for col in ['Equiv Distance Index', 'Metabolic Power']:
    if col in df.columns: agg_dict[col] = 'mean'
if 'Work Rate Dist' in df.columns: agg_dict['Work Rate Dist'] = 'sum'

# AGRUPA POR NOME, DATA E PERÍODO (1º e 2º Tempo)
df_jogo = df.groupby(['Name', 'Data', 'Período']).agg(agg_dict).reset_index()
df_jogo = df_jogo.rename(columns={
    'Total Distance': 'Dist_Total', 'Player Load': 'Load_Total', 'HIA': 'HIA_Total',
    'V4 Dist': 'V4_Dist', 'V5 Dist': 'V5_Dist', 'V4 To8 Eff': 'V4_Eff',
    'V5 To8 Eff': 'V5_Eff', 'HR_Pct': 'HR_Medio', 'Min_Num': 'Minutos',
})
df_jogo = df_jogo.sort_values(['Name', 'Data', 'Período'])

# Dias de descanso (calculado por dia, não por período)
datas_unicas = df_jogo[['Name', 'Data']].drop_duplicates().sort_values(['Name', 'Data'])
datas_unicas['Dias_Descanso'] = datas_unicas.groupby('Name')['Data'].diff().dt.days.fillna(7).clip(1, 30)
df_jogo = df_jogo.merge(datas_unicas, on=['Name', 'Data'], how='left')

# Expanding means POR PERÍODO (Média histórica do T1 não se mistura com T2)
medias = {'Dist_Total': 'Media_Dist_Geral', 'Load_Total': 'Media_Load_Geral', 'HIA_Total': 'Media_HIA_Geral', 'HR_Medio': 'Media_HR_Geral'}
for orig, dest in medias.items():
    df_jogo[dest] = df_jogo.groupby(['Name', 'Período'])[orig].transform(lambda x: x.expanding().mean().shift(1))

for orig, dest in [('Dist_Total', 'Media_Dist_Contexto'), ('HIA_Total', 'Media_HIA_Contexto'), ('Load_Total', 'Media_Load_Contexto')]:
    df_jogo[dest] = df_jogo.groupby(['Name', 'Período', 'Resultado'])[orig].transform(lambda x: x.expanding().mean().shift(1))

df_jogo['Carga_3Jogos'] = df_jogo.groupby(['Name', 'Período'])['Load_Total'].transform(lambda x: x.rolling(3, min_periods=1).sum().shift(1))
df_jogo['Carga_7Jogos'] = df_jogo.groupby(['Name', 'Período'])['Load_Total'].transform(lambda x: x.rolling(7, min_periods=1).sum().shift(1))

df_jogo['Media_Dist_3Jogos'] = df_jogo.groupby(['Name', 'Período'])['Dist_Total'].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
df_jogo['Trend_Dist'] = df_jogo['Media_Dist_3Jogos'] / (df_jogo['Media_Dist_Geral'] + 1)
df_jogo['N_Jogos'] = df_jogo.groupby(['Name', 'Período']).cumcount()

colunas_num = df_jogo.select_dtypes(include='number').columns.tolist()
df_jogo[colunas_num] = df_jogo[colunas_num].fillna(df_jogo.groupby('Name')[colunas_num].transform('median'))
df_jogo[colunas_num] = df_jogo[colunas_num].fillna(0)
df_jogo = df_jogo[df_jogo['Minutos'] > 5].copy()

# ─────────────────────────────────────────────────────────────────────────────
# 4. TREINAMENTO (DOIS MODELOS POR MÉTRICA)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/5] Treinando modelos por Tempo (T1 e T2)...")
os.makedirs(DIRETORIO_MODELOS, exist_ok=True)

FEATURES = ['Minutos', 'Dias_Descanso', 'Diff_Gols', 'N_Jogos', 'Media_Dist_Geral', 'Media_Load_Geral', 'Media_HIA_Geral', 'Media_HR_Geral', 'Media_Dist_Contexto', 'Media_HIA_Contexto', 'Media_Load_Contexto', 'Carga_3Jogos', 'Carga_7Jogos', 'Trend_Dist']
for col in ['Equiv Distance Index', 'Metabolic Power', 'Work Rate Dist']:
    if col in df_jogo.columns: FEATURES.append(col)

FEATURES_VALIDAS = [f for f in FEATURES if f in df_jogo.columns]

for periodo in [1, 2]:
    print(f"\n  ⏱️  TREINANDO MODELOS PARA O {periodo}º TEMPO:")
    df_p = df_jogo[df_jogo['Período'] == periodo].copy()
    
    for target in TARGETS:
        if target not in df_p.columns: continue

        df_m = df_p[FEATURES_VALIDAS + [target, 'Name', 'Data']].replace([np.inf, -np.inf], np.nan).dropna()
        if len(df_m) < 10: continue

        X = df_m[FEATURES_VALIDAS].values
        y = df_m[target].values

        modelo_xgb = xgb.XGBRegressor(n_estimators=400, max_depth=5, learning_rate=0.04, random_state=RANDOM_STATE, verbosity=0)
        modelo_xgb.fit(X, y)
        
        # O pulo do gato: Grava o nome com "_T1" ou "_T2" no final
        caminho_modelo = os.path.join(DIRETORIO_MODELOS, f'modelo_{target}_T{periodo}.pkl')
        
        with open(caminho_modelo, 'wb') as f:
            pickle.dump({
                'modelo':   modelo_xgb,
                'features': FEATURES_VALIDAS,
                'mae':      mean_absolute_error(y, modelo_xgb.predict(X))
            }, f)
        
        print(f"     ✔ {target} (MAE: {mean_absolute_error(y, modelo_xgb.predict(X)):.1f}) -> Salvo como _T{periodo}.pkl")

print("\n[5/5] Treinamento concluído com sucesso! Pode abrir o Live Tracker.")