"""
=============================================================================
MODELO PREDITIVO AO VIVO — SNAPSHOTS MINUTO A MINUTO (VERSÃO DEFINITIVA)
=============================================================================
Esta arquitetura treina a IA ensinando-a a entender a fadiga ao longo do tempo.
1 Linha de Treino = 1 Momento do Jogo (ex: Minuto 15, Minuto 20, Minuto 26...)
=============================================================================
"""

import os
import warnings
import numpy as np
import pandas as pd
import pickle
from sklearn.metrics import mean_absolute_error
import xgboost as xgb

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
DIRETORIO_ATUAL      = os.path.dirname(os.path.abspath(__file__))
CAMINHO_EXCEL        = os.path.join(DIRETORIO_ATUAL, 'ADF OnLine 2024.xlsb')
DIRETORIO_MODELOS    = os.path.join(DIRETORIO_ATUAL, 'Models')
RANDOM_STATE         = 42

print("=" * 65)
print("  MODELO PREDITIVO - ARQUITETURA DE SNAPSHOTS (MINUTO A MINUTO)")
print("=" * 65)

# MAPEAMENTO DAS MÉTRICAS (Alvo Final vs Coluna Bruta do Catapult)
MAPA_METRICAS = {
    'Dist_Total': 'Total Distance',
    'Load_Total': 'Player Load',
    'V4_Dist':    'V4 Dist',
    'V5_Dist':    'V5 Dist',
    'V4_Eff':     'V4 To8 Eff',
    'V5_Eff':     'V5 To8 Eff',
    'HIA_Total':  'HIA' # (Calculada abaixo)
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. CARREGAR DADOS E LIMPAR
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/4] Carregando dados base...")
df = pd.read_excel(CAMINHO_EXCEL, engine='calamine')
df.columns = df.columns.str.strip()
df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
df = df.dropna(subset=['Data', 'Name', 'Interval', 'Período'])

# Extrair o minuto numérico
if 'Interval (min)' in df.columns:
    df['Min_Num'] = pd.to_numeric(df['Interval (min)'], errors='coerce').fillna(0)
else:
    df['Min_Num'] = pd.to_numeric(df['Interval'], errors='coerce').fillna(0)

# Filtrar apenas 1º e 2º tempo, e ordenar cronologicamente
df = df[df['Período'].isin([1, 2])]
df = df.sort_values(['Name', 'Data', 'Período', 'Min_Num']).reset_index(drop=True)

# Preencher N/A com 0 para as métricas base
for col in MAPA_METRICAS.values():
    if col != 'HIA' and col not in df.columns: df[col] = 0

# Calcular HIA base
hia_cols = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff']
df['HIA'] = df[[c for c in hia_cols if c in df.columns]].sum(axis=1)

# Resultado e Gols
def extrair_diff_gols(placar):
    s = str(placar).strip().lower()
    if any(x in s for x in ['vencendo', 'vitoria', 'vitória', 'ganhando', 'v']): return 1
    if any(x in s for x in ['perdendo', 'derrota', 'd']): return -1
    return 0
df['Diff_Gols'] = df['Placar'].apply(extrair_diff_gols) if 'Placar' in df.columns else 0

# ─────────────────────────────────────────────────────────────────────────────
# 2. CONSTRUIR O "HISTÓRICO" (O QUE ELE FEZ NOS JOGOS ANTERIORES)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Calculando o histórico dos atletas (Sem olhar para o futuro)...")

# Primeiro, agrupamos o total de cada jogo
df_jogos = df.groupby(['Name', 'Data', 'Período']).agg({
    'Total Distance': 'sum', 'Player Load': 'sum', 'V4 Dist': 'sum',
    'V5 Dist': 'sum', 'V4 To8 Eff': 'sum', 'V5 To8 Eff': 'sum', 'HIA': 'sum',
    'Diff_Gols': 'last'
}).reset_index()

# Calculamos Dias de Descanso
datas_unicas = df_jogos[['Name', 'Data']].drop_duplicates().sort_values(['Name', 'Data'])
datas_unicas['Dias_Descanso'] = datas_unicas.groupby('Name')['Data'].diff().dt.days.fillna(7).clip(1, 30)
df_jogos = df_jogos.merge(datas_unicas, on=['Name', 'Data'], how='left')

# Calculamos as Médias Expandidas (Tudo .shift(1) para a IA não trapacear)
for metric_target, metric_base in MAPA_METRICAS.items():
    # Média Geral daquela métrica no Período
    df_jogos[f'Media_Geral_{metric_target}'] = df_jogos.groupby(['Name', 'Período'])[metric_base].transform(lambda x: x.expanding().mean().shift(1))
    # Média dos últimos 3 jogos daquela métrica
    df_jogos[f'Media_3J_{metric_target}'] = df_jogos.groupby(['Name', 'Período'])[metric_base].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    
    # Criamos a "Tendência" (Ritmo recente vs Ritmo da vida toda)
    df_jogos[f'Trend_{metric_target}'] = df_jogos[f'Media_3J_{metric_target}'] / (df_jogos[f'Media_Geral_{metric_target}'] + 1)

df_jogos['Carga_3Jogos_PL'] = df_jogos.groupby(['Name', 'Período'])['Player Load'].transform(lambda x: x.rolling(3, min_periods=1).sum().shift(1))
df_jogos['N_Jogos'] = df_jogos.groupby(['Name', 'Período']).cumcount()

# Preenche os N/As do primeiro jogo com 0
df_jogos = df_jogos.fillna(0)

# Isolamos apenas as colunas de contexto histórico para colar na base principal
cols_historico = ['Name', 'Data', 'Período', 'Dias_Descanso', 'Carga_3Jogos_PL', 'N_Jogos'] + \
                 [col for col in df_jogos.columns if 'Media_Geral_' in col or 'Trend_' in col]
df_historico_limpo = df_jogos[cols_historico]

# ─────────────────────────────────────────────────────────────────────────────
# 3. CRIAR OS SNAPSHOTS MINUTO A MINUTO (O PULO DO GATO)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Gerando os Snapshots (A IA assistindo ao jogo)...")

# Para cada linha do GPS (Interval), calculamos o quanto ele JÁ ACUMULOU até ali
grp = df.groupby(['Name', 'Data', 'Período'])
for metric_target, metric_base in MAPA_METRICAS.items():
    df[f'{metric_target}_Acumulado_Agora'] = grp[metric_base].cumsum()
    # E descobrimos qual foi o valor que ele atingiu no FIM daquele período (O nosso Alvo de Previsão)
    df[f'TARGET_{metric_target}'] = grp[metric_base].transform('sum')

# Fundimos o histórico do pré-jogo em cada snapshot do minuto
df_snapshots = df.merge(df_historico_limpo, on=['Name', 'Data', 'Período'], how='left')
df_snapshots = df_snapshots.dropna(subset=['Min_Num'])

# ─────────────────────────────────────────────────────────────────────────────
# 4. TREINAR OS MODELOS ESPECIALISTAS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Treinando os modelos XGBoost...")
os.makedirs(DIRETORIO_MODELOS, exist_ok=True)

# Vamos treinar 2 modelos (T1 e T2) para cada Métrica do nosso Mapa
for metric_target in MAPA_METRICAS.keys():
    print(f"\n🚀 Treinando IA para: {metric_target}")
    
    # As features MUDAM dependendo do que estamos a prever!
    # Se formos prever V4_Dist, a IA vai focar no V4_Dist_Acumulado e na Media_Geral de V4
    FEATURES_DA_METRICA = [
        'Min_Num', 
        'Dias_Descanso', 
        'N_Jogos', 
        'Carga_3Jogos_PL',
        'Diff_Gols',
        f'{metric_target}_Acumulado_Agora',   # O esforço HOJE nesta métrica
        f'Media_Geral_{metric_target}',       # O que ele costuma fazer
        f'Trend_{metric_target}'              # A forma recente dele
    ]
    
    alvo = f'TARGET_{metric_target}'
    
    for periodo in [1, 2]:
        df_treino = df_snapshots[(df_snapshots['Período'] == periodo) & (df_snapshots['Min_Num'] > 0)].copy()
        df_treino = df_treino[FEATURES_DA_METRICA + [alvo]].dropna()
        
        if len(df_treino) < 50:
            print(f"   ⚠️ Poucos dados para {metric_target} no T{periodo}. Pulando...")
            continue
            
        X = df_treino[FEATURES_DA_METRICA].values
        y = df_treino[alvo].values
        
        # XGBoost poderoso: ele vai aprender que "Se Min_Num = 26 e Acumulado = X, então o Final é Y"
        modelo = xgb.XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=RANDOM_STATE, verbosity=0)
        modelo.fit(X, y)
        
        mae = mean_absolute_error(y, modelo.predict(X))
        
        # Guardar o modelo
        nome_arquivo = f'modelo_{metric_target}_T{periodo}.pkl'
        caminho_salvar = os.path.join(DIRETORIO_MODELOS, nome_arquivo)
        
        with open(caminho_salvar, 'wb') as f:
            pickle.dump({
                'modelo': modelo,
                'features': FEATURES_DA_METRICA,
                'mae': mae
            }, f)
            
        print(f"   ✔ T{periodo} salvo! (Erro Médio de Treino: {mae:.1f})")

print("\n" + "=" * 65)
print("✅ SUCESSO! A Fábrica de IA gerou os novos cérebros focados minuto a minuto.")
print("=" * 65)