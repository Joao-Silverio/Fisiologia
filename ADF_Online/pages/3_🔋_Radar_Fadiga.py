import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. CONFIGURAÇÃO E ESTILO
st.set_page_config(page_title="Radar de Fadiga", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("🔋 Radar de Ausência de Estímulo (>19km/h)")

if 'df_global' not in st.session_state:
    st.warning("Carregue os dados na página principal (Home) primeiro.")
    st.stop()
    
df_base_total = st.session_state['df_global'].copy()

# Garantindo a ordem ascendente por Data
df_base_total['Data'] = pd.to_datetime(df_base_total['Data'])
df_base_total = df_base_total.sort_values(by='Data', ascending=False)

# Criando o display da data após a ordenação
df_base_total['Data_Display'] = df_base_total['Data'].dt.strftime('%d/%m/%Y') + ' ' + df_base_total['Adversário'].astype(str)

# ==========================================
# 2. FILTROS HORIZONTAIS
# ==========================================
st.markdown("### 🔍 Filtros de Análise")
with st.container():
    c1, c2, c3, c4 = st.columns([1.5, 2, 1, 1.5])
    
    with c1:
        competicao_sel = st.multiselect("🏆 Competição:", options=df_base_total['Competição'].unique().tolist() if 'Competição' in df_base_total.columns else [])
        df_base = df_base_total[df_base_total['Competição'].isin(competicao_sel)] if competicao_sel else df_base_total.copy()

    with c2:
        # A lista de jogos aqui já seguirá a ordem ascendente definida no df_base
        opcoes_jogos = df_base['Data_Display'].unique().tolist()
        jogo_sel = st.selectbox("📅 Selecione o Jogo:", opcoes_jogos)
        df_jogo = df_base[df_base['Data_Display'] == jogo_sel]

    with c3:
        periodo_sel = st.radio("⏱️ Período:", ["1º Tempo", "2º Tempo"], horizontal=True)
        num_periodo = 1 if periodo_sel == "1º Tempo" else 2
        df_periodo = df_jogo[df_jogo['Período'] == num_periodo]

    with c4:
        opcao_bloco = st.pills("Tamanho do Bloco:", ["3 minutos", "5 minutos", "15 minutos"], default="5 minutos")
        mapa_colunas_bloco = {"15 minutos": "Parte (15 min)", "5 minutos": "Parte (5 min)", "3 minutos": "Parte (3 min)"}
        coluna_faixa = mapa_colunas_bloco[opcao_bloco]

st.markdown("---")

# ==========================================
# 3. LÓGICA DE ALERTAS (FOCO EM V4 DIST)
# ==========================================
col_v4 = 'V4 Dist'
df_periodo = df_periodo.dropna(subset=[coluna_faixa])

# Alerta: Jogadores com mais de 8 minutos sem qualquer ação em V4 no tempo selecionado
df_ausente = df_periodo[df_periodo[col_v4] <= 0]
contagem_critica = df_ausente.groupby('Name').size()
# Threshold de 8 minutos para um alerta mais sensível em V4
atletas_em_alerta = contagem_critica[contagem_critica > 8].index.tolist()

if atletas_em_alerta:
    st.error(f"⚠️ **ALERTA DE INTENSIDADE (V4):** Atletas com longo tempo sem estímulo de Alta Velocidade: {', '.join(atletas_em_alerta)}")

# ==========================================
# ANALISE TATICA
# ==========================================

# Criar coluna de status do placar (exemplo baseado na sua lógica de ML)
def verificar_status(row):
    if 'Ganhando 1' in row and row['Ganhando 1'] == 1: return "Ganhando"
    if 'Perdendo 1' in row and row['Perdendo 1'] == 1: return "Perdendo"
    return "Empatando"

df_ausente['Status_Placar'] = df_ausente.apply(verificar_status, axis=1)

# Novo Gráfico de Ranking com Contexto Tático
fig_rank = px.bar(df_ausente.groupby(['Name', 'Status_Placar']).size().reset_index(name='Minutos'), 
                 y="Name", x="Minutos", color="Status_Placar",
                 title="Minutos de 'Apagão' por Status do Placar",
                 color_discrete_map={"Ganhando": "#2E7D32", "Perdendo": "#C62828", "Empatando": "#F9A825"},
                 template='plotly_white', orientation='h')

fig_rank.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_rank, use_container_width=True)

# ==========================================
# 4. GRÁFICOS
# ==========================================
col_esq, col_dir = st.columns([1, 1])

with col_esq:
    st.subheader("Minutos Acumulados em 'Apagão' (V4)")
    df_contagem = df_ausente.groupby(['Name', coluna_faixa]).size().reset_index(name='Minutos_Ausentes')
    
    fig_rank = px.bar(df_contagem, y="Name", x="Minutos_Ausentes", color=coluna_faixa,
                     orientation='h', template='plotly_white',
                     color_discrete_sequence=px.colors.qualitative.Safe)
    
    fig_rank.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'}, height=500)
    st.plotly_chart(fig_rank, use_container_width=True)

with col_dir:
    st.subheader("Densidade de Alta Velocidade (V4)")
    df_heatmap = df_periodo.groupby(['Interval', 'Name'])[col_v4].sum().reset_index()
    
    fig_heat = px.density_heatmap(df_heatmap, x="Interval", y="Name", z=col_v4,
                                 color_continuous_scale="Viridis", template='plotly_white',
                                 labels={'Interval': 'Minuto do Jogo', col_v4: 'Metros em V4'})
    
    fig_heat.update_layout(height=500)
    st.plotly_chart(fig_heat, use_container_width=True)
