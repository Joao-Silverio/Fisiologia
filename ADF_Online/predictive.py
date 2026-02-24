"""
=============================================================================
MODELO PREDITIVO AO VIVO — DESEMPENHO DE ATLETAS DE FUTEBOL
Versão 3.0 — Calibrado com colunas reais do ADF Online 2024
=============================================================================
Grupos de features utilizados:
  • Distância e velocidade (V0–V8 Dist/Dur, High Speed Dist)
  • Alta intensidade / HIA (V4–V6 To8 Eff, Acc3, Dec3)
  • Aceleração / Desaceleração (Acc1–3, Dec1–3 Eff/Dist)
  • Carga interna (Player Load, Body Load, Equiv Distance Index)
  • Potência metabólica (Metabolic Power, M4–M8 Dist)
  • Frequência cardíaca (HR%, Max HR%, Heart Work Unit)
  • Work Rate (Work Rate Count, Dist, Dur)

Objetivo: dado o minuto X de um jogo ao vivo, prever a
          Distância Total e o Player Load ao final da partida.
=============================================================================
"""

import os
import warnings
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

import xgboost as xgb
import shap

warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
DIRETORIO_ATUAL      = os.path.dirname(os.path.abspath(__file__))
CAMINHO_EXCEL        = os.path.join(DIRETORIO_ATUAL, 'ADF OnLine 2024.xlsb')
N_SPLITS_CV          = 5
JANELA_INTRA         = 5    # períodos de 5 min para janela deslizante
MINUTO_CORTE_AO_VIVO = 45
RANDOM_STATE         = 42

# Agora o modelo vai treinar um motor de ML para CADA UMA destas variáveis
TARGETS = ['Dist_Total', 'Load_Total', 'V4_Dist', 'V5_Dist', 'V4_Eff', 'V5_Eff', 'HIA_Total']

print("=" * 65)
print("  MODELO PREDITIVO AO VIVO — v3.0")
print("=" * 65)


# ─────────────────────────────────────────────────────────────────────────────
# 1. CARREGAMENTO
# ─────────────────────────────────────────────────────────────────────────────
print("\n[1/7] Carregando dados...")

df = pd.read_excel(CAMINHO_EXCEL, engine='calamine')
df.columns = df.columns.str.strip()
df['Data'] = pd.to_datetime(df['Data'], errors='coerce')
df = df.dropna(subset=['Data', 'Name', 'Interval'])
df = df.sort_values(['Name', 'Data', 'Interval']).reset_index(drop=True)

print(f"   ✔  {len(df):,} registros | "
      f"{df['Name'].nunique()} atletas | "
      f"{df['Data'].nunique()} dias | "
      f"{df['Competição'].nunique() if 'Competição' in df.columns else '?'} competições")


# ─────────────────────────────────────────────────────────────────────────────
# 2. COLUNAS DERIVADAS ESSENCIAIS
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/7] Construindo variáveis derivadas...")

# --- HIA (High Intensity Actions) ---
hia_cols = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff']
for c in hia_cols:
    if c not in df.columns: df[c] = 0
df['HIA'] = df[hia_cols].sum(axis=1)

# --- High Speed Distance (V4 + V5 + V6) ---
for c in ['V4 Dist', 'V5 Dist', 'V6 Dist']:
    if c not in df.columns: df[c] = 0
df['HS_Dist'] = df['V4 Dist'] + df['V5 Dist'] + df['V6 Dist']

# --- Sprint Distance (V6 + V7 + V8) ---
for c in ['V7 Dist', 'V8 Dist']:
    if c not in df.columns: df[c] = 0
df['Sprint_Dist'] = df['V6 Dist'] + df['V7 Dist'] + df['V8 Dist']

# --- Razão aceleração/desaceleração de alta intensidade ---
for c in ['Acc3 Eff', 'Dec3 Eff', 'Acc3 Dist', 'Dec3 Dist']:
    if c not in df.columns: df[c] = 0
df['AccDec3_Ratio'] = df['Acc3 Eff'] / (df['Dec3 Eff'] + 1)

# --- Intensidade cardíaca (se disponível) ---
hr_col = 'Avg Heart Rate As Percentage Of Max'
if hr_col not in df.columns:
    hr_col = 'Heart Rate As Percentage Of Max'
if hr_col not in df.columns:
    df['HR_Pct'] = 0
    hr_col = 'HR_Pct'
else:
    df['HR_Pct'] = df[hr_col].fillna(0)

# --- Diff de gols ---
def extrair_diff_gols(placar):
    """Suporta '2-1', 'Vencendo', 'Perdendo', 'Empatando', 'V', 'D', 'E'."""
    s = str(placar).strip().lower()
    # Texto em português
    if any(x in s for x in ['vencendo', 'vitoria', 'vitória', 'ganhando']): return 1
    if any(x in s for x in ['perdendo', 'derrota']):                         return -1
    if any(x in s for x in ['empat']):                                        return 0
    if s == 'v': return 1
    if s == 'd': return -1
    if s == 'e': return 0
    # Formato numérico '2-1'
    try:
        partes = s.replace(' ', '').split('-')
        return int(partes[0]) - int(partes[1])
    except Exception:
        return 0

if 'Placar' in df.columns:
    df['Diff_Gols'] = df['Placar'].apply(extrair_diff_gols)
    df['Resultado'] = df['Diff_Gols'].apply(
        lambda x: 'V' if x > 0 else ('D' if x < 0 else 'E')
    )
else:
    df['Diff_Gols'] = 0
    df['Resultado'] = 'E'

# --- Interval em minutos numérico ---
if 'Interval (min)' in df.columns:
    df['Min_Num'] = pd.to_numeric(df['Interval (min)'], errors='coerce').fillna(0)
else:
    df['Min_Num'] = pd.to_numeric(df['Interval'], errors='coerce').fillna(0)

# --- Fase do jogo (0=início, 1=meio, 2=fim) ---
df['Fase_Jogo'] = pd.cut(df['Min_Num'], bins=[0, 30, 60, 200],
                          labels=[0, 1, 2], right=True).astype(float).fillna(0)

print("   ✔  HIA, HS_Dist, Sprint_Dist, AccDec3, HR_Pct, Diff_Gols criados")


# ─────────────────────────────────────────────────────────────────────────────
# 3. FEATURES INTRA-JOGO (FADIGA EM TEMPO REAL)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/7] Calculando features de fadiga intra-jogo...")

grp = df.groupby(['Name', 'Data'])

# Janela deslizante (intensidade recente)
for col, alias in [
    ('Total Distance',  'Dist_Janela'),
    ('HIA',             'HIA_Janela'),
    ('Player Load',     'Load_Janela'),
    ('HS_Dist',         'HS_Janela'),
    ('HR_Pct',          'HR_Janela'),
    ('Metabolic Power', 'MetPow_Janela'),
]:
    if col in df.columns:
        df[alias] = grp[col].transform(
            lambda x: x.rolling(JANELA_INTRA, min_periods=1).mean()
        )
    else:
        df[alias] = 0

# Acumulados no jogo
for col, alias in [
    ('Total Distance', 'Dist_Acum'),
    ('HIA',            'HIA_Acum'),
    ('Player Load',    'Load_Acum'),
    ('Sprint_Dist',    'Sprint_Acum'),
    ('Acc3 Eff',       'Acc3_Acum'),
    ('Dec3 Eff',       'Dec3_Acum'),
]:
    if col in df.columns:
        df[alias] = grp[col].cumsum()
    else:
        df[alias] = 0

# Decaimento: rendimento atual vs pico do jogo
df['Pico_Dist'] = grp['Total Distance'].transform('max')
df['Decaimento'] = (df['Total Distance'] / df['Pico_Dist'].replace(0, np.nan)).fillna(1).clip(0, 2)

# Intensidade normalizada pelo tempo
df['Dist_por_Min']  = df['Dist_Acum']  / df['Min_Num'].replace(0, np.nan)
df['Load_por_Min']  = df['Load_Acum']  / df['Min_Num'].replace(0, np.nan)
df['HIA_por_Min']   = df['HIA_Acum']   / df['Min_Num'].replace(0, np.nan)

df[['Dist_por_Min', 'Load_por_Min', 'HIA_por_Min']] = \
    df[['Dist_por_Min', 'Load_por_Min', 'HIA_por_Min']].fillna(0)

print("   ✔  Janelas, acumulados, decaimento e intensidade por minuto calculados")


# ─────────────────────────────────────────────────────────────────────────────
# 4. FEATURES INTER-JOGO (HISTÓRICO E RECUPERAÇÃO)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/7] Calculando histórico entre jogos...")

agg_dict = {
    'Total Distance':   'sum',
    'Player Load':      'sum',
    'HIA':              'sum',
    'V4 Dist':          'sum', # Adicionado
    'V5 Dist':          'sum', # Adicionado
    'V4 To8 Eff':       'sum', # Adicionado
    'V5 To8 Eff':       'sum', # Adicionado
    'HS_Dist':          'sum',
    'Sprint_Dist':      'sum',
    'Acc3 Eff':         'sum',
    'Dec3 Eff':         'sum',
    'HR_Pct':           'mean',
    'Min_Num':          'max',
    'Diff_Gols':        'last',
    'Resultado':        'last',
}
if 'Equiv Distance Index' in df.columns:
    agg_dict['Equiv Distance Index'] = 'mean'
if 'Metabolic Power' in df.columns:
    agg_dict['Metabolic Power'] = 'mean'
if 'Work Rate Dist' in df.columns:
    agg_dict['Work Rate Dist'] = 'sum'
if 'Competição' in df.columns:
    agg_dict['Competição'] = 'last'

df_jogo = df.groupby(['Name', 'Data']).agg(agg_dict).reset_index()
df_jogo = df_jogo.rename(columns={
    'Total Distance': 'Dist_Total',
    'Player Load':    'Load_Total',
    'HIA':            'HIA_Total',
    'V4 Dist':        'V4_Dist', # Adicionado
    'V5 Dist':        'V5_Dist', # Adicionado
    'V4 To8 Eff':     'V4_Eff',  # Adicionado
    'V5 To8 Eff':     'V5_Eff',  # Adicionado
    'HS_Dist':        'HS_Total',
    'Sprint_Dist':    'Sprint_Total',
    'Acc3 Eff':       'Acc3_Total',
    'Dec3 Eff':       'Dec3_Total',
    'HR_Pct':         'HR_Medio',
    'Min_Num':        'Minutos',
})
df_jogo = df_jogo.sort_values(['Name', 'Data'])

# Dias de descanso
df_jogo['Dias_Descanso'] = (
    df_jogo.groupby('Name')['Data'].diff().dt.days.fillna(7).clip(1, 30)
)

# Expanding means (sem data leakage)
medias = {
    'Dist_Total':   'Media_Dist_Geral',
    'Load_Total':   'Media_Load_Geral',
    'HIA_Total':    'Media_HIA_Geral',
    'HS_Total':     'Media_HS_Geral',
    'Sprint_Total': 'Media_Sprint_Geral',
    'HR_Medio':     'Media_HR_Geral',
}
for orig, dest in medias.items():
    df_jogo[dest] = df_jogo.groupby('Name')[orig].transform(
        lambda x: x.expanding().mean().shift(1)
    )

# Médias por contexto de resultado
for orig, dest in [
    ('Dist_Total', 'Media_Dist_Contexto'),
    ('HIA_Total',  'Media_HIA_Contexto'),
    ('Load_Total', 'Media_Load_Contexto'),
]:
    df_jogo[dest] = df_jogo.groupby(['Name', 'Resultado'])[orig].transform(
        lambda x: x.expanding().mean().shift(1)
    )

# Carga acumulada nos últimos 3 e 7 jogos
df_jogo['Carga_3Jogos'] = df_jogo.groupby('Name')['Load_Total'].transform(
    lambda x: x.rolling(3, min_periods=1).sum().shift(1)
)
df_jogo['Carga_7Jogos'] = df_jogo.groupby('Name')['Load_Total'].transform(
    lambda x: x.rolling(7, min_periods=1).sum().shift(1)
)

# Tendência recente: média dos últimos 3 jogos vs geral
df_jogo['Media_Dist_3Jogos'] = df_jogo.groupby('Name')['Dist_Total'].transform(
    lambda x: x.rolling(3, min_periods=1).mean().shift(1)
)
df_jogo['Trend_Dist'] = df_jogo['Media_Dist_3Jogos'] / (df_jogo['Media_Dist_Geral'] + 1)

# Número do jogo na temporada (volume de experiência)
df_jogo['N_Jogos'] = df_jogo.groupby('Name').cumcount()

# Preenchimento de NaN — apenas colunas numéricas com mediana
colunas_num = df_jogo.select_dtypes(include='number').columns.tolist()
colunas_obj = df_jogo.select_dtypes(exclude='number').columns.tolist()

df_jogo[colunas_num] = df_jogo[colunas_num].fillna(
    df_jogo.groupby('Name')[colunas_num].transform('median')
)
df_jogo[colunas_num] = df_jogo[colunas_num].fillna(0)
df_jogo[colunas_obj] = df_jogo[colunas_obj].fillna('Desconhecido')
df_jogo = df_jogo[df_jogo['Minutos'] > 5].copy()

print(f"   ✔  {len(df_jogo):,} registros de jogo | features inter-jogo prontas")


# ─────────────────────────────────────────────────────────────────────────────
# 5. MODELO — PREVISÃO DA DISTÂNCIA TOTAL E PLAYER LOAD
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/7] Treinando modelos e validação Walk-Forward...")

FEATURES = [
    # Contexto do jogo
    'Minutos',
    'Dias_Descanso',
    'Diff_Gols',
    'N_Jogos',
    # Histórico geral
    'Media_Dist_Geral',
    'Media_Load_Geral',
    'Media_HIA_Geral',
    'Media_HS_Geral',
    'Media_Sprint_Geral',
    'Media_HR_Geral',
    # Histórico por contexto (resultado)
    'Media_Dist_Contexto',
    'Media_HIA_Contexto',
    'Media_Load_Contexto',
    # Carga e fadiga acumulada
    'Carga_3Jogos',
    'Carga_7Jogos',
    'Trend_Dist',
]

# Adicionar colunas opcionais se existirem
for col in ['Equiv Distance Index', 'Metabolic Power', 'Work Rate Dist']:
    renamed = col.replace(' ', '_')
    if col in df_jogo.columns:
        FEATURES.append(col)

tscv = TimeSeriesSplit(n_splits=N_SPLITS_CV)

resultados    = {}
modelos_finais = {}

# ── Diagnóstico: quais features existem de fato no df_jogo ─────────────────
cols_numericas_jogo = df_jogo.select_dtypes(include='number').columns.tolist()
FEATURES_VALIDAS = [f for f in FEATURES if f in cols_numericas_jogo]
FEATURES_FALTANDO = [f for f in FEATURES if f not in cols_numericas_jogo]

print(f"\n   Features disponíveis : {len(FEATURES_VALIDAS)}/{len(FEATURES)}")
if FEATURES_FALTANDO:
    print(f"   Features ausentes    : {FEATURES_FALTANDO}")

if len(FEATURES_VALIDAS) == 0:
    print("\n   ❌ ERRO: Nenhuma feature válida encontrada!")
    print("   Colunas numéricas disponíveis em df_jogo:")
    for c in sorted(cols_numericas_jogo): print(f"      • {c}")
    raise ValueError("Nenhuma feature válida — verifique os nomes das colunas acima.")

for target in TARGETS:
    if target not in df_jogo.columns:
        print(f"   ⚠  '{target}' não encontrado em df_jogo, pulando...")
        print(f"      Colunas disponíveis: {[c for c in df_jogo.columns if 'dist' in c.lower() or 'load' in c.lower()]}")
        continue

    # Usar cópia local de FEATURES para não sobrescrever a lista global
    feats = FEATURES_VALIDAS.copy()

    df_m = df_jogo[feats + [target, 'Name', 'Data']].copy()
    df_m = df_m.replace([np.inf, -np.inf], np.nan).dropna()
    df_m = df_m.sort_values('Data').reset_index(drop=True)

    print(f"\n   {target}: {len(df_m)} amostras, {len(feats)} features")

    if len(df_m) < N_SPLITS_CV * 2:
        print(f"   ⚠  Amostras insuficientes ({len(df_m)}) para {N_SPLITS_CV} folds, pulando...")
        continue

    X = df_m[feats].values
    y = df_m[target].values

    erros_rf, erros_xgb = [], []

    modelo_rf  = RandomForestRegressor(n_estimators=300, max_depth=8,
                                       min_samples_leaf=5, n_jobs=-1,
                                       random_state=RANDOM_STATE)
    modelo_xgb = xgb.XGBRegressor(n_estimators=400, max_depth=5,
                                   learning_rate=0.04, subsample=0.8,
                                   colsample_bytree=0.8, min_child_weight=5,
                                   random_state=RANDOM_STATE, verbosity=0)

    for train_idx, test_idx in tscv.split(X):
        Xtr, Xte = X[train_idx], X[test_idx]
        ytr, yte = y[train_idx], y[test_idx]

        modelo_rf.fit(Xtr, ytr)
        erros_rf.append(mean_absolute_error(yte, modelo_rf.predict(Xte)))

        modelo_xgb.fit(Xtr, ytr, eval_set=[(Xte, yte)], verbose=False)
        erros_xgb.append(mean_absolute_error(yte, modelo_xgb.predict(Xte)))

    mae_rf  = float(np.mean(erros_rf))
    mae_xgb = float(np.mean(erros_xgb))

    modelo_rf.fit(X, y)
    modelo_xgb.fit(X, y)

    melhor = modelo_xgb if mae_xgb < mae_rf else modelo_rf
    nome_m = 'XGBoost' if mae_xgb < mae_rf else 'RandomForest'

    resultados[target] = {
        'MAE_RF': mae_rf, 'MAE_XGB': mae_xgb,
        'Melhor': nome_m,
        'df': df_m, 'X': X, 'y': y, 'FEATURES': feats
    }
    modelos_finais[target] = {
        'rf': modelo_rf, 'xgb': modelo_xgb, 'melhor': melhor, 'nome': nome_m
    }

    unid = 'm' if target == 'Dist_Total' else 'UA'
    print(f"     RandomForest → MAE: {mae_rf:.1f} {unid}")
    print(f"     XGBoost      → MAE: {mae_xgb:.1f} {unid}")
    print(f"     ✔  Melhor: {nome_m}")

if not modelos_finais:
    print("\n   ❌ Nenhum modelo foi treinado! Verifique o diagnóstico acima.")
    print("   Colunas de df_jogo disponíveis:")
    for c in sorted(df_jogo.columns): print(f"      • {c}")
    raise RuntimeError("Nenhum modelo treinado — veja as colunas acima e ajuste TARGETS ou FEATURES.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. SHAP — EXPLICABILIDADE
# ─────────────────────────────────────────────────────────────────────────────
print("\n[6/7] Calculando SHAP...")

shap_dfs = {}
for target in TARGETS:
    if target not in modelos_finais:
        continue
    modelo = modelos_finais[target]['melhor']
    X_shap = resultados[target]['X']
    explainer   = shap.TreeExplainer(modelo)
    shap_vals   = explainer.shap_values(X_shap)
    shap_dfs[target] = pd.DataFrame({
        'Feature':   resultados[target]['FEATURES'],
        'SHAP_Abs':  np.abs(shap_vals).mean(axis=0),
        'SHAP_Mean': shap_vals.mean(axis=0),
    }).sort_values('SHAP_Abs', ascending=False)

print("   ✔  SHAP calculado para todos os targets")


# ─────────────────────────────────────────────────────────────────────────────
# 7. SIMULAÇÃO AO VIVO + VISUALIZAÇÕES
# ─────────────────────────────────────────────────────────────────────────────
print("\n[7/7] Gerando previsões ao vivo e gráficos...")

# Simulação: para cada atleta, variar o minuto e prever distância final
df_ultimo = df_jogo.sort_values('Data').groupby('Name').last().reset_index()
top_atletas = df_jogo.groupby('Name').size().nlargest(8).index.tolist()
df_sim_list = []

for _, row in df_ultimo[df_ultimo['Name'].isin(top_atletas)].iterrows():
    for minuto in range(MINUTO_CORTE_AO_VIVO, 95, 5):
        entry = {'Atleta': row['Name'], 'Minuto': minuto}
        for target in TARGETS:
            if target in modelos_finais:
                feats_t   = resultados[target]['FEATURES']
                sample    = {f: row.get(f, 0) for f in feats_t}
                sample['Minutos'] = minuto
                sample_df = pd.DataFrame([sample])[feats_t]
                entry[f'Prev_{target}'] = modelos_finais[target]['melhor'].predict(sample_df)[0]
        df_sim_list.append(entry)

df_sim = pd.DataFrame(df_sim_list)

# ── Gráfico 1: Feature Importance SHAP (ambos os targets) ──────────────────
'''targets_com_shap = [t for t in TARGETS if t in shap_dfs]
fig1 = None

if len(targets_com_shap) > 0:
    n_cols = max(1, len(targets_com_shap))
    fig1 = make_subplots(rows=1, cols=n_cols,
                         subplot_titles=[f'SHAP — {t}' for t in targets_com_shap])
    for i, target in enumerate(targets_com_shap, 1):
        top10 = shap_dfs[target].head(10).sort_values('SHAP_Abs')
        bar_colors = ['#2ECC71' if v >= 0 else '#E74C3C' for v in top10['SHAP_Mean']]
        fig1.add_trace(go.Bar(
            x=top10['SHAP_Abs'], y=top10['Feature'],
            orientation='h', marker_color=bar_colors, name=target,
            text=top10['SHAP_Abs'].round(1), textposition='outside'
        ), row=1, col=i)
    fig1.update_layout(
        title='Top 10 Features por Impacto SHAP<br><sup>Verde = efeito positivo | Vermelho = efeito negativo</sup>',
        template='plotly_white', height=500, showlegend=False
)
else:
    # Fallback: feature importance do RandomForest se SHAP falhar
    print("   ⚠  SHAP sem dados — usando feature importance do RandomForest como fallback")
    target_fb    = list(modelos_finais.keys())[0]
    importancias = modelos_finais[target_fb]['rf'].feature_importances_
    feat_cols    = resultados[target_fb]['FEATURES']
    df_imp = pd.DataFrame({'Feature': feat_cols, 'Importância (%)': importancias * 100}) \
               .sort_values('Importância (%)', ascending=True).tail(10)
    fig1 = px.bar(df_imp, x='Importância (%)', y='Feature', orientation='h',
                  title='Feature Importance — RandomForest (fallback)',
                  template='plotly_white', color='Importância (%)',
                  color_continuous_scale='Blues', text_auto='.1f')

# ── Gráfico 2: Previsão ao vivo — Distância Total ─────────────────────────
if 'Prev_Dist_Total' in df_sim.columns:
    fig2 = px.line(
        df_sim, x='Minuto', y='Prev_Dist_Total', color='Atleta',
        title=f'Previsão de Distância Total ao Vivo (a partir do minuto {MINUTO_CORTE_AO_VIVO})',
        labels={'Prev_Dist_Total': 'Distância Prevista (m)', 'Minuto': 'Minuto do Jogo'},
        template='plotly_white', markers=True
    )
    fig2.add_vline(x=MINUTO_CORTE_AO_VIVO, line_dash='dash', line_color='gray',
                   annotation_text='Agora ao vivo', annotation_position='top right')
    fig2.update_layout(height=500)

# ── Gráfico 3: Previsão ao vivo — Player Load ─────────────────────────────
if 'Prev_Load_Total' in df_sim.columns:
    fig3 = px.line(
        df_sim, x='Minuto', y='Prev_Load_Total', color='Atleta',
        title=f'Previsão de Player Load ao Vivo (a partir do minuto {MINUTO_CORTE_AO_VIVO})',
        labels={'Prev_Load_Total': 'Player Load Previsto (UA)', 'Minuto': 'Minuto do Jogo'},
        template='plotly_white', markers=True
    )
    fig3.add_vline(x=MINUTO_CORTE_AO_VIVO, line_dash='dash', line_color='gray',
                   annotation_text='Agora ao vivo', annotation_position='top right')
    fig3.update_layout(height=500)

# ── Gráfico 4: Comparação Dist Real vs Dist Prevista (último jogo de cada atleta) ──
df_m_dist = resultados.get('Dist_Total', {}).get('df')
if df_m_dist is not None:
    df_m_dist = df_m_dist.copy()
    feats_dist = resultados['Dist_Total']['FEATURES']
    df_m_dist['Pred'] = modelos_finais['Dist_Total']['melhor'].predict(
        df_m_dist[feats_dist].values
    )
    df_m_dist['Erro'] = (df_m_dist['Pred'] - df_m_dist['Dist_Total']).abs()

    fig4 = px.scatter(
        df_m_dist, x='Dist_Total', y='Pred',
        color='Erro',
        color_continuous_scale='RdYlGn_r',
        title='Real vs Previsto — Distância Total<br><sup>Ponto na diagonal = previsão perfeita</sup>',
        labels={'Dist_Total': 'Distância Real (m)', 'Pred': 'Distância Prevista (m)'},
        template='plotly_white', opacity=0.7,
        hover_data=['Name'] if 'Name' in df_m_dist.columns else None
    )
    max_val = max(df_m_dist['Dist_Total'].max(), df_m_dist['Pred'].max())
    fig4.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode='lines', line=dict(color='black', dash='dash', width=1),
        name='Perfeito', showlegend=False
    ))

# ── Gráfico 5: Ranking de atletas por Distância Média Prevista ────────────
df_min90 = df_sim[df_sim['Minuto'] == 90].copy()
if 'Prev_Dist_Total' in df_min90.columns:
    df_rank = df_min90.sort_values('Prev_Dist_Total', ascending=False)
    fig5 = px.bar(
        df_rank, x='Atleta', y='Prev_Dist_Total',
        title='Ranking de Atletas — Distância Total Prevista (90 min)',
        labels={'Prev_Dist_Total': 'Distância Prevista (m)'},
        template='plotly_white', color='Prev_Dist_Total',
        color_continuous_scale='Blues', text_auto='.0f'
    )
    fig5.update_xaxes(tickangle=30)

# ── Gráfico 6: Dias de descanso vs Distância (impacto da recuperação) ────
if 'Dias_Descanso' in df_jogo.columns and 'Dist_Total' in df_jogo.columns:
    fig6 = px.scatter(
        df_jogo[df_jogo['Name'].isin(top_atletas)],
        x='Dias_Descanso', y='Dist_Total',
        color='Name', trendline='ols',
        title='Impacto dos Dias de Descanso na Distância Total',
        labels={'Dias_Descanso': 'Dias de Descanso', 'Dist_Total': 'Distância Total (m)'},
        template='plotly_white', opacity=0.7
    )

# Exibir gráficos
if fig1 is not None:                                 fig1.show()
if 'Prev_Dist_Total' in df_sim.columns: fig2.show()
if 'Prev_Load_Total'    in df_sim.columns: fig3.show()
if df_m_dist is not None:                   fig4.show()
if 'Prev_Dist_Total' in df_sim.columns: fig5.show()
fig6.show()
'''


# ─────────────────────────────────────────────────────────────────────────────
# RESUMO FINAL
# ─────────────────────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("  RESUMO FINAL")
print("=" * 65)
for target in TARGETS:
    if target not in resultados: continue
    r   = resultados[target]
    unid = 'm' if target == 'Dist_Total' else 'UA'
    mae  = min(r['MAE_RF'], r['MAE_XGB'])
    print(f"\n  {target}:")
    print(f"    Melhor modelo : {r['Melhor']}")
    print(f"    MAE           : {mae:.1f} {unid}")
    if target in shap_dfs:
        print(f"    Top 3 features:")
        for _, row in shap_dfs[target].head(3).iterrows():
            print(f"      • {row['Feature']:<30}  SHAP: {row['SHAP_Abs']:.2f}")

# Exportar
#saida_prev = os.path.join(DIRETORIO_ATUAL, 'previsoes_ao_vivo.csv')
#saida_shap = os.path.join(DIRETORIO_ATUAL, 'shap_importance.csv')
#df_sim.to_csv(saida_prev, index=False)
#if 'Dist_Total' in shap_dfs:
#    shap_dfs['Dist_Total'].to_csv(saida_shap, index=False)

#print(f"\n  ✔  Previsões ao vivo  → {saida_prev}")
#print(f"  ✔  Importância SHAP   → {saida_shap}")
print("=" * 65)

# ─────────────────────────────────────────────────────────────────────────────
# SALVANDO OS MODELOS TREINADOS PARA O STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────
import pickle

# ─────────────────────────────────────────────────────────────────────────────
# SALVANDO OS MODELOS TREINADOS PARA O STREAMLIT
# ─────────────────────────────────────────────────────────────────────────────
import pickle

# Define o caminho da pasta models e cria ela se não existir
DIRETORIO_MODELOS = os.path.join(DIRETORIO_ATUAL, 'models')
os.makedirs(DIRETORIO_MODELOS, exist_ok=True)

print("\n[EXPORTAÇÃO] Salvando modelos para a aplicação Web na pasta 'models'...")
for target in TARGETS:
    if target in modelos_finais:
        # Agora salva apontando para DIRETORIO_MODELOS
        caminho_modelo = os.path.join(DIRETORIO_MODELOS, f'modelo_{target}.pkl')
        
        with open(caminho_modelo, 'wb') as f:
            pickle.dump({
                'modelo':   modelos_finais[target]['melhor'],
                'features': resultados[target]['FEATURES'],
                'mae':      resultados[target]['MAE_RF'] if modelos_finais[target]['nome'] == 'RandomForest' else resultados[target]['MAE_XGB']
            }, f)
        print(f"  ✔ Salvo: models/modelo_{target}.pkl")