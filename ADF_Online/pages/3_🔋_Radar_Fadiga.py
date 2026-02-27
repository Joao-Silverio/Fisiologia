import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# 1. Novas Importações
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
from streamlit_autorefresh import st_autorefresh
import Source.UI.visual as visual
import Source.UI.components as ui

# 2. Configuração Visual
st.set_page_config(page_title=f"Radar de Fadiga | {visual.CLUBE['sigla']}", layout="wide")

# 3. Cabeçalho Padronizado
ui.renderizar_cabecalho("Radar de Fadiga", "Mapeamento de ausência de estímulo (>19km/h)")

# 1. Pede à página para "piscar os olhos" a cada 2 segundos (2000 ms)
# Usa uma "key" diferente para cada página (ex: "refresh_comparacao", "refresh_hia")
st_autorefresh(interval=2000, limit=None, key="refresh_desta_pagina")

# 2. Verifica a "impressão digital" (hora exata) do ficheiro Excel
hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

# 3. Pede os dados. Se a "hora_atual" não mudou, o Streamlit não faz NADA (0% de CPU).
# Se a "hora_atual" mudou, o Streamlit carrega os dados novos!
df_novo, df_recordes_novo = load_global_data(hora_atual)

# 4. Atualiza a memória global para os gráficos desenharem com os dados frescos
if not df_novo.empty:
    st.session_state['df_global'] = df_novo
    st.session_state['df_recordes'] = df_recordes_novo

# E depois continuas a ler o session_state como sempre fizeste:
if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal ou verifique o arquivo Excel.")
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
# 5. MAPA DE OCIOSIDADE SOBRE A HISTÓRIA DO JOGO (DEFINITIVO)
# ==========================================
st.markdown("---")
st.header("🕵️‍♂️ Mapa de Ociosidade sobre a História do Jogo")
st.markdown("As barras coloridas aparecem **apenas** quando o atleta parou de correr. Os espaços vazios representam os momentos de ação.")

# O DICIONÁRIO DE CORES FOI REMOVIDO DAQUI

# 2. Preparação da Timeline do Jogo (Fundo)
min_max = int(df_periodo['Interval'].max())
status_jogo = df_periodo[['Interval', 'Placar']].drop_duplicates().sort_values('Interval')

# 3. FILTRAGEM: Apenas minutos ONDE O ATLETA NÃO CORREU
df_apenas_ausencia = df_periodo[df_periodo[col_v4] <= 0].copy()

# 4. CONSTRUÇÃO DO GRÁFICO (O SEGREDO DOS BLOCOS)
fig_final = go.Figure()

# Desenhamos blocos exatos de 1 minuto para cada registro de ausência
for placar_val in df_apenas_ausencia['Placar'].unique():
    df_group = df_apenas_ausencia[df_apenas_ausencia['Placar'] == placar_val]
    
    fig_final.add_trace(go.Bar(
        y=df_group['Name'],
        x=[1] * len(df_group), # A largura da barra é sempre de exatamente 1 minuto
        base=df_group['Interval'] - 0.5, # A barra é posicionada no minuto exato em que ocorreu
        orientation='h',
        name=placar_val,
        # <--- USANDO O CONFIG AQUI:
        marker_color=config.MAPA_CORES_PLACAR.get(placar_val, '#888888'), 
        hovertemplate="Atleta: %{y}<br>Minuto: %{base}<extra></extra>"
    ))

# 5. PINTANDO O FUNDO (A HISTÓRIA DO JOGO)
for i in range(len(status_jogo)):
    min_inicio = status_jogo.iloc[i]['Interval']
    min_fim = status_jogo.iloc[i+1]['Interval'] if i+1 < len(status_jogo) else min_max
    
    # <--- USANDO O CONFIG AQUI:
    cor_contexto = config.MAPA_CORES_PLACAR.get(status_jogo.iloc[i]['Placar'], "#EEEEEE")
    
    fig_final.add_vrect(
        x0=min_inicio - 0.5, x1=min_fim + 0.5,
        fillcolor=cor_contexto, opacity=0.15, 
        layer="below", line_width=0,
    )

# 6. Ajustes de Layout
fig_final.update_layout(
    template='plotly_white',
    height=700,
    barmode='overlay', # Garante que as barras não tentem se empilhar
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