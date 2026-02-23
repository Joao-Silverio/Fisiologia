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

# Garantindo a ordem ASCENDENTE por Data (Cronológica)
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
# 3. LÓGICA DE ALERTAS E TRATAMENTO (V4 DIST)
# ==========================================
col_v4 = 'V4 Dist'
df_periodo = df_periodo.dropna(subset=[coluna_faixa])

# Alerta: Jogadores com mais de 8 minutos sem qualquer ação em V4
df_ausente = df_periodo[df_periodo[col_v4] <= 0].copy()
contagem_critica = df_ausente.groupby('Name').size()
atletas_em_alerta = contagem_critica[contagem_critica > 8].index.tolist()

if atletas_em_alerta:
    st.error(f"⚠️ **ALERTA DE INTENSIDADE (V4):** Atletas com longo tempo sem estímulo de Alta Velocidade: {', '.join(atletas_em_alerta)}")

# ==========================================
# 4. GRÁFICOS LADO A LADO
# ==========================================
col_esq, col_dir = st.columns([1, 1])

with col_esq:
    st.subheader("Minutos Acumulados em 'Apagão' (V4)")
    df_contagem = df_ausente.groupby(['Name', coluna_faixa]).size().reset_index(name='Minutos_Ausentes')
    fig_rank = px.bar(df_contagem, y="Name", x="Minutos_Ausentes", color=coluna_faixa,
                     orientation='h', template='plotly_white',
                     color_discrete_sequence=px.colors.qualitative.Safe)
    fig_rank.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'}, height=450)
    st.plotly_chart(fig_rank, use_container_width=True)

with col_dir:
    st.subheader("Densidade de Alta Velocidade (V4)")
    df_heatmap = df_periodo.groupby(['Interval', 'Name'])[col_v4].sum().reset_index()
    fig_heat = px.density_heatmap(df_heatmap, x="Interval", y="Name", z=col_v4,
                                 color_continuous_scale="Viridis", template='plotly_white',
                                 labels={'Interval': 'Minuto do Jogo', col_v4: 'Metros em V4'})
    fig_heat.update_layout(height=450)
    st.plotly_chart(fig_heat, use_container_width=True)

# ==========================================
# 5. ANÁLISE TÁTICA CONSOLIDADA (HISTÓRIA DO JOGO)
# ==========================================
st.markdown("---")
st.header("📖 Contexto Tático e Cronologia dos Apagões")

# Mapeamento de cores expandido para cobrir todas as variações do seu Placar
mapa_cores_placar = {
    "Ganhando 1": "#2E7D32", "Ganhando 2": "#1B5E20", 
    "Perdendo 1": "#C62828", "Perdendo 2": "#B71C1C", 
    "Empatando": "#F9A825"
}

# Layout em colunas: Volume à esquerda e Timeline à direita
col_vol, col_time = st.columns([1, 1.2])

with col_vol:
    st.subheader("Em que situação o atleta 'apaga' mais?")
    df_tatica = df_ausente.groupby(['Name', 'Placar']).size().reset_index(name='Minutos')
    
    fig_vol = px.bar(df_tatica, y="Name", x="Minutos", color="Placar",
                    color_discrete_map=mapa_cores_placar,
                    template='plotly_white', orientation='h')
    
    fig_vol.update_layout(barmode='stack', yaxis={'categoryorder':'total ascending'}, 
                         height=500, showlegend=False) # Legend oculta para não repetir
    st.plotly_chart(fig_vol, use_container_width=True)

with col_time:
    st.subheader("Timeline: Performance vs. Placar")
    atleta_foco = st.selectbox("Selecione um Atleta para análise detalhada:", df_periodo['Name'].unique())
    
    # Preparação da Timeline do Placar
    min_max = int(df_periodo['Interval'].max())
    timeline_game = pd.DataFrame({'Interval': range(1, min_max + 1)})
    
    # Pegamos o placar minuto a minuto do jogo
    status_jogo = df_periodo[['Interval', 'Placar']].drop_duplicates().sort_values('Interval')
    timeline_game = pd.merge(timeline_game, status_jogo, on='Interval', how='left').ffill()

    # Gráfico de Área para o fundo colorido (A História do Jogo)
    fig_historia = px.area(timeline_game, x="Interval", y=[1]*len(timeline_game), color="Placar",
                           color_discrete_map=mapa_cores_placar,
                           template='plotly_white')

    # Adicionamos os "X" pretos (Apagões) do atleta selecionado
    df_atleta_ausente = df_periodo[(df_periodo['Name'] == atleta_foco) & (df_periodo[col_v4] <= 0)]
    
    fig_historia.add_trace(go.Scatter(
        x=df_atleta_ausente['Interval'], 
        y=[0.5]*len(df_atleta_ausente),
        mode='markers',
        name='Apagão (V4 <= 0)',
        marker=dict(color='black', symbol='x', size=10, line=dict(width=1)),
        hovertemplate='Apagão no Minuto %{x}<extra></extra>'
    ))

    fig_historia.update_layout(
        height=400, 
        yaxis={'visible': False},
        xaxis_title="Minutos de Jogo",
        legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_historia, use_container_width=True)

# Alerta de Insight Fisiológico
st.info(f"💡 **Dica de Análise:** Se os 'X' pretos do **{atleta_foco}** surgem concentrados no final de um bloco de cor (ex: final do período perdendo), isso indica fadiga física acumulada. Se surgem logo após uma mudança de placar, pode ser um abalo anímico/tático.")
