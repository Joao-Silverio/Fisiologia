import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. CONFIGURAÇÃO E ESTILO (PADRÃO LIVE TRACKER)
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
df_base_total['Data_Display'] = pd.to_datetime(df_base_total['Data']).dt.strftime('%d/%m/%Y') + ' ' + df_base_total['Adversário'].astype(str)

# ==========================================
# 2. FILTROS HORIZONTAIS (ESTÉTICA PADRONIZADA)
# ==========================================
st.markdown("### 🔍 Filtros de Análise")
with st.container():
    c1, c2, c3, c4 = st.columns([1.5, 2, 1, 1.5])
    
    with c1:
        competicao_sel = st.multiselect("🏆 Competição:", options=sorted(df_base_total['Competição'].unique().tolist()) if 'Competição' in df_base_total.columns else [])
        df_base = df_base_total[df_base_total['Competição'].isin(competicao_sel)] if competicao_sel else df_base_total.copy()

    with c2:
        jogo_sel = st.selectbox("📅 Selecione o Jogo:", df_base['Data_Display'].unique())
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
# 3. LÓGICA DE ALERTAS E KPIs
# ==========================================
col_alta_vel = 'V4 Dist'
df_periodo = df_periodo.dropna(subset=[coluna_faixa])

# Jogadores com mais de 10 min sem atingir V4 no período
df_ausente = df_periodo[df_periodo[col_alta_vel] <= 0]
contagem_critica = df_ausente.groupby('Name').size()
atletas_em_alerta = contagem_critica[contagem_critica > 10].index.tolist()

if atletas_em_alerta:
    st.error(f"⚠️ **ALERTA DE FADIGA:** Atletas com >10 min sem estímulo de alta velocidade: {', '.join(atletas_em_alerta)}")

# ==========================================
# 4. GRÁFICOS
# ==========================================
col_esq, col_dir = st.columns([1, 1])

with col_esq:
    st.subheader("Ranking de Ausência Acumulada")
    df_contagem = df_ausente.groupby(['Name', coluna_faixa]).size().reset_index(name='Minutos_Ausentes')
    
    fig_rank = px.bar(df_contagem, y="Name", x="Minutos_Ausentes", color=coluna_faixa,
                     orientation='h', template='plotly_white',
                     color_discrete_sequence=px.colors.qualitative.Safe)
    
    fig_rank.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'}, height=500, margin=dict(t=30, b=20))
    st.plotly_chart(fig_rank, use_container_width=True)

with col_dir:
    st.subheader("Timeline de Intensidade do Elenco")
    # Gráfico de calor para ver ONDE estão os buracos no tempo
    df_heatmap = df_periodo.groupby(['Interval', 'Name'])[col_alta_vel].sum().reset_index()
    
    fig_heat = px.density_heatmap(df_heatmap, x="Interval", y="Name", z=col_alta_vel,
                                 color_continuous_scale="Viridis", template='plotly_white',
                                 labels={'Interval': 'Minuto do Jogo', 'V4 Dist': 'Metros em V4'})
    
    fig_heat.update_layout(height=500, margin=dict(t=30, b=20))
    st.plotly_chart(fig_heat, use_container_width=True)
