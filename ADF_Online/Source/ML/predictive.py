"""
=============================================================================
MODELO PREDITIVO AO VIVO — SNAPSHOTS + TODAS AS SUBSTITUIÇÕES (EQ45)
=============================================================================
Aproveita 100% dos dados. Se o jogador saiu aos 15 min, os snapshots do
minuto 1 ao 15 são usados no treino, mas apontando para o Alvo Equivalente (Eq45).
=============================================================================
"""

import os
import warnings
import numpy as np
import pandas as pd
import pickle
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb
import ADF_Online.Source.Dados.config as config
from ADF_Online.Source.Dados.data_loader import load_global_data

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
DIRETORIO_ATUAL      = os.path.dirname(os.path.abspath(__file__))
CAMINHO_EXCEL        = os.path.join(DIRETORIO_ATUAL, 'ADF OnLine 2024.xlsb')
DIRETORIO_MODELOS    = os.path.join(DIRETORIO_ATUAL, 'Models')
RANDOM_STATE         = 42

print("=" * 65)
print("  MODELO PREDITIVO - APROVEITAMENTO TOTAL (INCLUI SUBSTITUIÇÕES)")
print("=" * 65)

MAPA_METRICAS = {
    'Dist_Total': 'Total Distance',
    'Load_Total': 'Player Load',
    'V4_Dist':    'V4 Dist',
    'V5_Dist':    'V5 Dist',
    'V4_Eff':     'V4 To8 Eff',
    'V5_Eff':     'V5 To8 Eff',
    'HIA_Total':  'HIA' 
}

# ─────────────────────────────────────────────────────────────────────────────
# 1. CARREGAR DADOS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/4] Carregando dados prontos para o Treino...")
df, _ = load_global_data(0)

if df is None:
    print("❌ Falha ao carregar dados. Abortando.")
    exit()

# O df já vem com: HIA, Jogou_em_Casa, Diff_Gols e Fillna(0).

# ─────────────────────────────────────────────────────────────────────────────
# 2. HISTÓRICO COM TARGET EQUIVALENTE (EQ45/EQ50)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Calculando o histórico e os Alvos de Previsão (Targets)...")
df_jogos = df.groupby(['Name', 'Data', 'Período']).agg({
    'Total Distance': 'sum', 'Player Load': 'sum', 'V4 Dist': 'sum',
    'V5 Dist': 'sum', 'V4 To8 Eff': 'sum', 'V5 To8 Eff': 'sum', 'HIA': 'sum',
    'Diff_Gols': 'last',
    'Min_Num': 'max', # Descobrimos exatamente em que minuto ele saiu
    'Jogou_em_Casa' : 'first'  #Jogo em casa ou Fora
}).reset_index()
df_jogos.rename(columns={'Min_Num': 'Minutos_Jogados'}, inplace=True)

datas_unicas = df_jogos[['Name', 'Data']].drop_duplicates().sort_values(['Name', 'Data'])
datas_unicas['Dias_Descanso'] = datas_unicas.groupby('Name')['Data'].diff().dt.days.fillna(7).clip(1, 30)
df_jogos = df_jogos.merge(datas_unicas, on=['Name', 'Data'], how='left')

# Evitar divisões absurdas se alguém jogou só 2 minutos
df_jogos['Min_Divisor'] = df_jogos['Minutos_Jogados'].clip(lower=10)
# T1 = 45 min, T2 = 50 min
df_jogos['Min_Periodo'] = np.where(df_jogos['Período'] == 1, 45, 50)

cols_target = []
for metric_target, metric_base in MAPA_METRICAS.items():
    # O PULO DO GATO: O alvo de treino é a projeção dele para o fim do tempo
    nome_target = f'TARGET_{metric_target}'
    df_jogos[nome_target] = (df_jogos[metric_base] / df_jogos['Min_Divisor']) * df_jogos['Min_Periodo']
    cols_target.append(nome_target)
    
    # As médias aprendem com o ritmo projetado
    df_jogos[f'Media_Geral_{metric_target}'] = df_jogos.groupby(['Name', 'Período'])[nome_target].transform(lambda x: x.expanding().mean().shift(1))
    df_jogos[f'Media_3J_{metric_target}'] = df_jogos.groupby(['Name', 'Período'])[nome_target].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    df_jogos[f'Trend_{metric_target}'] = df_jogos[f'Media_3J_{metric_target}'] / (df_jogos[f'Media_Geral_{metric_target}'] + 1)

df_jogos['Carga_3Jogos_PL'] = df_jogos.groupby(['Name', 'Período'])['Player Load'].transform(lambda x: x.rolling(3, min_periods=1).sum().shift(1))
df_jogos['N_Jogos'] = df_jogos.groupby(['Name', 'Período']).cumcount()
df_jogos = df_jogos.fillna(0)

cols_historico = ['Name', 'Data', 'Período', 'Dias_Descanso', 'Carga_3Jogos_PL', 'N_Jogos', 'Minutos_Jogados'] + \
                 [col for col in df_jogos.columns if 'Media_Geral_' in col or 'Trend_' in col] + cols_target

df_historico_limpo = df_jogos[cols_historico]

# ─────────────────────────────────────────────────────────────────────────────
# 3. SNAPSHOTS MINUTO A MINUTO
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Gerando os Snapshots (Até ao minuto em que ele for substituído)...")
grp = df.groupby(['Name', 'Data', 'Período'])
for metric_target, metric_base in MAPA_METRICAS.items():
    df[f'{metric_target}_Acumulado_Agora'] = grp[metric_base].cumsum()

# Ao fazermos merge, as linhas onde ele não estava em campo simplesmente não existirão!
df_snapshots = df.merge(df_historico_limpo, on=['Name', 'Data', 'Período'], how='left')
df_snapshots = df_snapshots.dropna(subset=['Min_Num'])

# ─────────────────────────────────────────────────────────────────────────────
# 4. TREINAR OS MODELOS E EXIBIR RAIO-X (DEBUG)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Iniciando Treino com 100% de Aproveitamento de Dados...")
os.makedirs(DIRETORIO_MODELOS, exist_ok=True)

for metric_target in MAPA_METRICAS.keys():
    print(f"\n" + "="*55)
    print(f"🚀 TREINANDO E AVALIANDO: {metric_target.upper()}")
    print("="*55)
    
    FEATURES_DA_METRICA = [
        'Min_Num', 
        'Dias_Descanso', 
        'N_Jogos', 
        'Carga_3Jogos_PL',
        'Diff_Gols', 'Jogou_em_Casa',
        f'{metric_target}_Acumulado_Agora',   
        f'Media_Geral_{metric_target}',       
        f'Trend_{metric_target}'              
    ]
    
    alvo = f'TARGET_{metric_target}'
    
    for periodo in [1, 2]:
        print(f"\n  ⏱️  {periodo}º TEMPO:")
        
        # O filtro agora aceita TODOS os snapshots gerados, sem eliminar ninguém por substituição!
        df_treino = df_snapshots[(df_snapshots['Período'] == periodo) & (df_snapshots['Min_Num'] > 0)].copy()
        df_treino = df_treino[FEATURES_DA_METRICA + [alvo]].dropna()
        
        if len(df_treino) < 50:
            print(f"     ⚠️ Poucos dados ({len(df_treino)} linhas). Pulando...")
            continue
            
        X = df_treino[FEATURES_DA_METRICA]
        y = df_treino[alvo]
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=RANDOM_STATE)
        
        modelo = xgb.XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=RANDOM_STATE, verbosity=0)
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        print(f"     📊 Métricas de Teste:")
        print(f"        - MAE (Erro Absoluto):  {mae:.1f}")
        print(f"        - R² (Acurácia Global): {max(0, r2)*100:.1f} %")
        
        importancias = modelo.feature_importances_
        indices_top = np.argsort(importancias)[::-1][:3]
        print(f"     🧠 O que mais pesa (Top 3):")
        for idx in indices_top:
            print(f"        - {FEATURES_DA_METRICA[idx]}: {importancias[idx]*100:.1f}%")

        print(f"     👀 Exemplos (Teste Cego - Alvo EQ45):")
        amostra_idx = np.random.choice(len(y_test), 5, replace=False) if len(y_test) > 5 else range(len(y_test))
        for i in amostra_idx:
            real = y_test.iloc[i]
            previsto = y_pred[i]
            diff = previsto - real
            minuto_amostra = X_test.iloc[i]['Min_Num']
            print(f"        > Snapshot aos {minuto_amostra:.0f}' | Alvo Final Real(Eq): {real:.0f} | IA Disse: {previsto:.0f} | Erro: {diff:+.0f}")
            
        modelo_final = xgb.XGBRegressor(n_estimators=300, max_depth=5, learning_rate=0.05, random_state=RANDOM_STATE, verbosity=0)
        modelo_final.fit(X, y)
        mae_final = mean_absolute_error(y, modelo_final.predict(X))
        
        nome_arquivo = f'modelo_{metric_target}_T{periodo}.pkl'
        caminho_salvar = os.path.join(DIRETORIO_MODELOS, nome_arquivo)
        
        with open(caminho_salvar, 'wb') as f:
            pickle.dump({
                'modelo': modelo_final,
                'features': FEATURES_DA_METRICA,
                'mae': mae_final
            }, f)
            
        print(f"     💾 IA treinada (Usando 100% dos Snapshots) e salva em '{nome_arquivo}'!")

print("\n" + "=" * 65)
print("✅ SUCESSO! Cérebro de IA atualizado (Todas as substituições aproveitadas).")
print("=" * 65)