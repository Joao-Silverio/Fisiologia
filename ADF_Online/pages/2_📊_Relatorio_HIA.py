import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Relatório HIA", layout="wide")
st.title("📊 Análise de Alta Intensidade e Sprint (HIA)")

# Puxa os dados que foram carregados na Home.py
if 'df_global' not in st.session_state:
    st.warning("Por favor, acesse a página inicial (Home) primeiro para carregar os dados.")
    st.stop()

df = st.session_state['df_global'].copy()

# --- ATENÇÃO: Substitua pelos nomes EXATOS das suas colunas no Excel ---
col_v4 = 'V4 To8 Eff'  # Exemplo baseado na sua foto
col_v5 = 'V5 To8 Eff'
col_v6 = 'V6 To8 Eff'
col_acc3 = 'Acc3 Eff'
col_acc4 = 'Acc4 Eff'
col_dec3 = 'Dec3 Eff'
col_dec4 = 'Dec4 Eff'
# ----------------------------------------------------------------------

st.sidebar.header("Filtros")
jogo_sel = st.sidebar.selectbox("Selecione o Jogo", df['Data'].unique() if 'Data' in df.columns else ["Todos"])
if jogo_sel != "Todos":
    df = df[df['Data'] == jogo_sel]

# 1. Criando a coluna HIA usando a sua lógica do Power BI
# Somamos as colunas preenchendo vazios com zero para não dar erro matemático
hia_cols = [col_v4, col_v5, col_v6, col_acc3, col_acc4, col_dec3, col_dec4]
existing_cols = [col for col in hia_cols if col in df.columns]
if existing_cols:
    df['HIA'] = df[existing_cols].fillna(0).sum(axis=1)
else:
    st.warning("Colunas de HIA não encontradas no arquivo Excel. Usando Dist. Z3 como proxy.")
    df['HIA'] = df['Dist. Z3'].fillna(0) if 'Dist. Z3' in df.columns else 0

# 2. Cálculos Globais da Partida
total_hia = df['HIA'].sum()
# Para calcular densidade (HIA/min), precisamos dos minutos totais do jogo
minutos_jogados = df['Interval'].max() if 'Interval' in df.columns else 50
hia_por_minuto = total_hia / minutos_jogados if minutos_jogados > 0 else 0

# 3. KPIs no topo (Igual à sua tela "HIA | HIA/min")
c1, c2, c3 = st.columns(3)
c1.metric("HIA Total", f"{total_hia:.0f} ações")
c2.metric("Densidade (HIA/min)", f"{hia_por_minuto:.2f}")

# 4. Gráfico: HIA por Atleta (Top 10 mais intensos)
df_agrupado = df.groupby('Name')['HIA'].sum().reset_index()
df_agrupado = df_agrupado.sort_values(by='HIA', ascending=True).tail(10) # Pegar os 10 maiores

fig = px.bar(df_agrupado, x='HIA', y='Name', orientation='h',
             title='Ações de Alta Intensidade por Atleta',
             color_discrete_sequence=['#1f77b4'], template='plotly_dark')
st.plotly_chart(fig, use_container_width=True)