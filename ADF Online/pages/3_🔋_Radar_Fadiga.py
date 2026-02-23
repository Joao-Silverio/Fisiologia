import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Radar de Fadiga", layout="wide")
st.title("🔋 Radar de Ausência de Estímulo (>19km/h)")
st.markdown("Visualização de blocos de tempo onde o atleta não atingiu alta velocidade.")

if 'df_global' not in st.session_state:
    st.warning("Carregue os dados na página principal (Home) primeiro.")
    st.stop()
    
df = st.session_state['df_global'].copy()

# ==========================================
# FILTROS LATERAIS
# ==========================================
st.sidebar.header("Filtros")

# Filtro de Período
tempo_sel = st.sidebar.radio("Período", ["1º Tempo", "2º Tempo"])
meio_tempo = 1 if tempo_sel == "1º Tempo" else 2
if 'Período' in df.columns:
    df = df[df['Período'] == meio_tempo]

# NOVO FILTRO: Escolher a granularidade (tamanho do bloco)
# Usa exatamente os nomes das colunas que vi na sua base de dados
opcao_bloco = st.sidebar.selectbox(
    "Tamanho do Bloco de Tempo", 
    ["5 minutos", "15 minutos", "3 minutos"]
)

# Mapeia a escolha do usuário para o nome real da coluna no seu Excel
mapa_colunas_bloco = {
    "15 minutos": "Parte (15 min)",
    "5 minutos": "Parte (5 min)",
    "3 minutos": "Parte (3 min)"
}
coluna_faixa = mapa_colunas_bloco[opcao_bloco]

# ==========================================
# LÓGICA DE AUSÊNCIA
# ==========================================

# Limpa linhas que não tenham a faixa de tempo preenchida
df = df.dropna(subset=[coluna_faixa])

# Define a coluna de alta velocidade
col_alta_vel = 'V4 Dist' # Pode trocar para 'Dist. Z3' se preferir

# 1. Filtra apenas os minutos onde o atleta correu ZERO metros em alta velocidade
df_ausente = df[df[col_alta_vel] <= 0]

# 2. Agrupa pelo Nome e pela coluna que já veio pronta do seu Excel e conta as linhas (minutos)
df_contagem = df_ausente.groupby(['Name', coluna_faixa]).size().reset_index(name='Minutos_Ausentes')

# ==========================================
# DESENHAR O GRÁFICO NO PLOTLY
# ==========================================
fig = px.bar(df_contagem, 
             y="Name", 
             x="Minutos_Ausentes", 
             color=coluna_faixa, 
             orientation='h',
             title=f"Minutos Acumulados sem Atingir >19km/h ({tempo_sel}) - Blocos de {opcao_bloco}",
             template='plotly_dark',
             color_discrete_sequence=px.colors.qualitative.Prism) 

# Ajustes de visual para organizar quem teve MENOS piques no topo
fig.update_layout(
    barmode='stack', 
    yaxis={'categoryorder':'total ascending'}, # Ordena as barras da maior para a menor
    height=600,
    xaxis_title="Total de Minutos Ausentes",
    yaxis_title="Atleta",
    legend_title_text="Faixa de Tempo"
)

st.plotly_chart(fig, use_container_width=True)