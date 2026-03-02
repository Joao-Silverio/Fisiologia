"""
=============================================================================
MODELO PREDITIVO AO VIVO — SNAPSHOTS + TODAS AS SUBSTITUIÇÕES (EQ45)
=============================================================================
Aproveita 100% dos dados. Se o jogador saiu aos 15 min, os snapshots do
minuto 1 ao 15 são usados no treino, mas apontando para o Alvo Equivalente (Eq45).
=============================================================================
"""

import os
import sys

# ---------------------------------------------------------------------
# HACK DE DIRETÓRIO: Garante que o Python encontre a pasta 'Source'
# ---------------------------------------------------------------------
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
RAIZ_PROJETO = os.path.abspath(os.path.join(DIRETORIO_ATUAL, '..', '..'))
if RAIZ_PROJETO not in sys.path:
    sys.path.append(RAIZ_PROJETO)
# ---------------------------------------------------------------------

import warnings
import numpy as np
import pandas as pd
import pickle
from sklearn.model_selection import train_test_split, GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

import Source.Dados.config as config
from Source.Dados.data_loader import load_global_data

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
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

# O df já vem com: HIA, Jogou_em_Casa, Diff_Gols (min a min) e Fillna(0).

# ─────────────────────────────────────────────────────────────────────────────
# 2. HISTÓRICO COM TARGET EQUIVALENTE E HERANÇA DO 1º TEMPO
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Calculando o histórico e os Alvos de Previsão (Targets)...")
df_jogos = df.groupby(['Name', 'Data', 'Período']).agg({
    'Total Distance': 'sum', 'Player Load': 'sum', 'V4 Dist': 'sum',
    'V5 Dist': 'sum', 'V4 To8 Eff': 'sum', 'V5 To8 Eff': 'sum', 'HIA': 'sum',
    'Min_Num': 'max', 
    'Jogou_em_Casa' : 'first' 
    # Diff_Gols removido daqui (fica apenas no snapshot minuto a minuto)
}).reset_index()
df_jogos.rename(columns={'Min_Num': 'Minutos_Jogados'}, inplace=True)

datas_unicas = df_jogos[['Name', 'Data']].drop_duplicates().sort_values(['Name', 'Data'])
datas_unicas['Dias_Descanso'] = datas_unicas.groupby('Name')['Data'].diff().dt.days.fillna(7).clip(1, 30)
df_jogos = df_jogos.merge(datas_unicas, on=['Name', 'Data'], how='left')

df_jogos['Min_Divisor'] = df_jogos['Minutos_Jogados'].clip(lower=10)
df_jogos['Min_Periodo'] = np.where(df_jogos['Período'] == 1, 45, 50)

cols_target = []
for metric_target, metric_base in MAPA_METRICAS.items():
    nome_target = f'TARGET_{metric_target}'
    df_jogos[nome_target] = (df_jogos[metric_base] / df_jogos['Min_Divisor']) * df_jogos['Min_Periodo']
    cols_target.append(nome_target)
    
    df_jogos[f'Media_Geral_{metric_target}'] = df_jogos.groupby(['Name', 'Período'])[nome_target].transform(lambda x: x.expanding().mean().shift(1))
    df_jogos[f'Media_3J_{metric_target}'] = df_jogos.groupby(['Name', 'Período'])[nome_target].transform(lambda x: x.rolling(3, min_periods=1).mean().shift(1))
    df_jogos[f'Trend_{metric_target}'] = df_jogos[f'Media_3J_{metric_target}'] / (df_jogos[f'Media_Geral_{metric_target}'] + 1)

df_jogos['Carga_3Jogos_PL'] = df_jogos.groupby(['Name', 'Período'])['Player Load'].transform(lambda x: x.rolling(3, min_periods=1).sum().shift(1))
df_jogos['N_Jogos'] = df_jogos.groupby(['Name', 'Período']).cumcount()
df_jogos = df_jogos.fillna(0)

# 🚀 PASSO 1 DA MELHORIA: Capturar o esforço final do 1º Tempo para usar no 2º
df_t1 = df_jogos[df_jogos['Período'] == 1].copy()
renames_t1 = {metric_base: f'Total_T1_{metric_target}' for metric_target, metric_base in MAPA_METRICAS.items()}
df_t1 = df_t1[['Name', 'Data'] + list(renames_t1.keys())].rename(columns=renames_t1)

cols_historico = ['Name', 'Data', 'Período', 'Dias_Descanso', 'Carga_3Jogos_PL', 'N_Jogos', 'Minutos_Jogados'] + \
                 [col for col in df_jogos.columns if 'Media_Geral_' in col or 'Trend_' in col] + cols_target

df_historico_limpo = df_jogos[cols_historico]

# ─────────────────────────────────────────────────────────────────────────────
# 3. SNAPSHOTS MINUTO A MINUTO (COM PASSO 3: RITMO/PACING)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Gerando os Snapshots (Até ao minuto em que ele for substituído)...")
grp = df.groupby(['Name', 'Data', 'Período'])
for metric_target, metric_base in MAPA_METRICAS.items():
    df[f'{metric_target}_Acumulado_Agora'] = grp[metric_base].cumsum()
    # 🚀 PASSO 3 DA MELHORIA: Taxa de intensidade por minuto (Pacing)
    # Clip(lower=1) evita erro de divisão por zero no minuto 0
    df[f'Ritmo_{metric_target}'] = df[f'{metric_target}_Acumulado_Agora'] / df['Min_Num'].clip(lower=1)

# Fusão 1: Historico
df_snapshots = df.merge(df_historico_limpo, on=['Name', 'Data', 'Período'], how='left')

# Fusão 2: Herança do 1º Tempo
df_snapshots = df_snapshots.merge(df_t1, on=['Name', 'Data'], how='left')
for metric_target in MAPA_METRICAS.keys():
    df_snapshots[f'Total_T1_{metric_target}'] = df_snapshots[f'Total_T1_{metric_target}'].fillna(0)

df_snapshots = df_snapshots.dropna(subset=['Min_Num'])

# ─────────────────────────────────────────────────────────────────────────────
# 4. TREINAR OS MODELOS E EXIBIR RAIO-X
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Iniciando Treino...")
os.makedirs(DIRETORIO_MODELOS, exist_ok=True)

for metric_target in MAPA_METRICAS.keys():
    print(f"\n" + "="*55)
    print(f"🚀 TREINANDO E AVALIANDO: {metric_target.upper()}")
    print("="*55)
    
    # As features base agora incluem a funcionalidade do Passo 3
    FEATURES_BASE = [
        'Min_Num', 
        'Dias_Descanso', 
        'N_Jogos', 
        'Carga_3Jogos_PL',
        'Diff_Gols', 'Jogou_em_Casa',
        f'{metric_target}_Acumulado_Agora',   
        f'Ritmo_{metric_target}',            # <-- Nova Inteligência de Pacing 
        f'Media_Geral_{metric_target}',       
        f'Trend_{metric_target}'              
    ]
    
    alvo = f'TARGET_{metric_target}'
    
    for periodo in [1, 2]:
        print(f"\n  ⏱️  {periodo}º TEMPO:")
        
        # Copiamos as features para não alterar a base do outro período
        features_atuais = FEATURES_BASE.copy()
        
        # 🚀 PASSO 1 DA MELHORIA: Inserir a herança de fadiga no 2º Tempo
        if periodo == 2:
            features_atuais.append(f'Total_T1_{metric_target}')
        
        df_treino = df_snapshots[(df_snapshots['Período'] == periodo) & (df_snapshots['Min_Num'] > 0)].copy()
        colunas_necessarias = features_atuais + [alvo, 'Data', 'Name']
        df_treino = df_treino[colunas_necessarias].dropna()
        
        if len(df_treino) < 50:
            print(f"     ⚠️ Poucos dados ({len(df_treino)} linhas). Pulando...")
            continue
            
        X = df_treino[features_atuais]
        y = df_treino[alvo]
        grupos = df_treino['Data'].astype(str) + "_" + df_treino['Name']
        
        gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
        train_idx, test_idx = next(gss.split(X, y, groups=grupos))
        
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        # 🚀 PASSO 5 DA MELHORIA: Tuning Dinâmico do Cérebro
        # Sprints e HIA têm muito ruído (estocásticos). Menos árvores evitam o "overfitting"
        is_explosivo = 'V5' in metric_target or 'HIA' in metric_target
        if is_explosivo:
            n_est, max_d, lr = 100, 3, 0.03
        else:
            # Distância e Carga são mais lineares. Árvores mais profundas captam a curva fisiológica.
            n_est, max_d, lr = 300, 5, 0.05
            
        modelo = xgb.XGBRegressor(n_estimators=n_est, max_depth=max_d, learning_rate=lr, random_state=RANDOM_STATE, verbosity=0)
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
            print(f"        - {features_atuais[idx]}: {importancias[idx]*100:.1f}%")

        print(f"     👀 Exemplos (Teste Cego - Alvo EQ45/50):")
        amostra_idx = np.random.choice(len(y_test), 5, replace=False) if len(y_test) > 5 else range(len(y_test))
        for i in amostra_idx:
            real = y_test.iloc[i]
            previsto = y_pred[i]
            diff = previsto - real
            minuto_amostra = X_test.iloc[i]['Min_Num']
            print(f"        > Snapshot aos {minuto_amostra:.0f}' | Real: {real:.0f} | IA Previu: {previsto:.0f} | Erro: {diff:+.0f}")
            
        # Treinamento final aproveitando todos os dados daquela métrica/período
        modelo_final = xgb.XGBRegressor(n_estimators=n_est, max_depth=max_d, learning_rate=lr, random_state=RANDOM_STATE, verbosity=0)
        modelo_final.fit(X, y)
        mae_final = mean_absolute_error(y, modelo_final.predict(X))
        
        nome_arquivo = f'modelo_{metric_target}_T{periodo}.pkl'
        caminho_salvar = os.path.join(DIRETORIO_MODELOS, nome_arquivo)
        
        with open(caminho_salvar, 'wb') as f:
            pickle.dump({
                'modelo': modelo_final,
                'features': features_atuais,
                'mae': mae_final
            }, f)
            
        print(f"     💾 IA salva: '{nome_arquivo}'")

print("\n" + "=" * 65)
print("✅ SUCESSO! Modelos atualizados com Herança T1, Ritmo e Tuning Dinâmico.")
print("=" * 65)