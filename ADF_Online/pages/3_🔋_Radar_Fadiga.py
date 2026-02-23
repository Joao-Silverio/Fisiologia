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
# 5. MAPA DE OCIOSIDADE SOBRE A HISTÓRIA DO JOGO (CORRIGIDO)
# ==========================================
st.markdown("---")
st.header("🕵️‍♂️ Mapa de Ociosidade sobre a História do Jogo")
st.markdown("As barras coloridas aparecem **apenas** quando o atleta parou de correr. Onde o atleta agiu, a barra some e mostra o fundo.")

# 1. Configuração de Cores
mapa_cores_placar = {
    "Ganhando 1": "#2E7D32", "Ganhando 2": "#1B5E20", 
    "Perdendo 1": "#C62828", "Perdendo 2": "#B71C1C", 
    "Empatando": "#F9A825"
}

# 2. Preparação da Timeline do Jogo (Fundo)
min_max = int(df_periodo['Interval'].max())
status_jogo = df_periodo[['Interval', 'Placar']].drop_duplicates().sort_values('Interval')

# 3. FILTRAGEM CRUCIAL: Criamos o DF contendo APENAS os minutos de inatividade
# Se o atleta correu > 0 em V4, o minuto é removido do gráfico
df_apenas_ausencia = df_periodo[df_periodo[col_v4] <= 0].copy()

# 4. Criação do Gráfico de Barras (Inatividade Real)
# Usamos 'Interval' como um valor discreto para criar blocos separados
fig_final = px.bar(
    df_apenas_ausencia, 
    x="Interval", 
    y="Name", 
    color="Placar",
    color_discrete_map=mapa_cores_placar,
    orientation='h',
    template='plotly_white',
    title=f"Cronologia de Inatividade - {periodo_sel}"
)

# 5. PINTANDO O FUNDO (A HISTÓRIA DO JOGO)
for i in range(len(status_jogo)):
    min_inicio = status_jogo.iloc[i]['Interval']
    min_fim = status_jogo.iloc[i+1]['Interval'] if i+1 < len(status_jogo) else min_max
    cor_contexto = mapa_cores_placar.get(status_jogo.iloc[i]['Placar'], "#EEEEEE")
    
    fig_final.add_vrect(
        x0=min_inicio - 0.5, x1=min_fim + 0.5,
        fillcolor=cor_contexto, opacity=0.15, 
        layer="below", line_width=0,
    )

# 6. AJUSTE DE "SUMIÇO": Forçamos o eixo X a tratar cada minuto como um bloco individual
fig_final.update_traces(marker_line_width=0, width=0.8) # Largura menor que 1 cria o espaço vazio

fig_final.update_layout(
    height=700,
    xaxis=dict(
        title="Linha do Tempo Real (Minutos)",
        tickmode='linear', dtick=5,
        range=[0, min_max + 1]
    ),
    yaxis=dict(title="Atletas", categoryorder='total descending'),
    bargap=0.4,
    legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5)
)

st.plotly_chart(fig_final, use_container_width=True)
