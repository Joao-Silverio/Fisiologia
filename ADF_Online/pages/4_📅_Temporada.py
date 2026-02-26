import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import config
from streamlit_autorefresh import st_autorefresh
from data_loader import obter_hora_modificacao, load_global_data

# =====================================================================
# 1. CONFIGURAÇÃO E ESTILO
# =====================================================================
st.set_page_config(page_title="Temporada - Visão Geral", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("📅 Raio-X da Temporada")
st.markdown("Análise macro do desgaste e volume da equipa ao longo do calendário de jogos.")

# =====================================================================
# 2. CARREGAMENTO E PREPARAÇÃO DE DADOS (MACRO)
# =====================================================================
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

df_raw = st.session_state['df_global'].copy()

# Garantir que a data é tratada como tempo para ordenar corretamente o gráfico cronológico
df_raw['Data'] = pd.to_datetime(df_raw['Data'], errors='coerce')
df_raw = df_raw.sort_values('Data')

# Passo A: Somar tudo o que CADA ATLETA fez num JOGO
# (Como o arquivo original é dividido em intervalos, temos que somar para ter o total do jogo)
cols_agrupar = ['Total Distance', 'HIA', 'V5 Dist', 'Player Load', 'Acc3 Eff', 'Dec3 Eff']
cols_existentes = [c for c in cols_agrupar if c in df_raw.columns]

df_atleta_jogo = df_raw.groupby(['Data', 'Data_Display', 'Competição', 'Name'])[cols_existentes].sum().reset_index()

# Criar a métrica de força mecânica
if 'Acc3 Eff' in df_atleta_jogo.columns and 'Dec3 Eff' in df_atleta_jogo.columns:
    df_atleta_jogo['AccDec_Total'] = df_atleta_jogo['Acc3 Eff'] + df_atleta_jogo['Dec3 Eff']
    cols_existentes.append('AccDec_Total')

# Passo B: Tirar a MÉDIA DA EQUIPA por JOGO
# (Média é melhor que a soma total, pois a soma flutua dependendo de quantos reservas entraram)
df_equipa_jogo = df_atleta_jogo.groupby(['Data', 'Data_Display', 'Competição'])[cols_existentes].mean().reset_index()
df_equipa_jogo = df_equipa_jogo.sort_values('Data')

# --- Implementação Opção 3: Recordes de Intensidade (Worst-Case Scenario) ---
# Calculamos a maior média de HIA em blocos de 5 minutos para cada atleta na temporada
df_wcs = df_raw.groupby(['Name', 'Data', 'Data_Display'])['HIA'].rolling(window=5, min_periods=5).mean().reset_index()
df_recordes = df_wcs.groupby('Name')['HIA'].max().reset_index()
df_recordes.rename(columns={'HIA': 'Recorde_5min_HIA'}, inplace=True)

# Guardamos no session_state para usar no Live Tracker depois
st.session_state['df_recordes'] = df_recordes

# =====================================================================
# 3. FILTROS GLOBAIS (Progressive Disclosure)
# =====================================================================
with st.expander("⚙️ Configurar Visão da Temporada", expanded=True):
    c1, c2, c3 = st.columns([2, 2, 1])
    
    with c1:
        competicoes_disp = df_equipa_jogo['Competição'].dropna().unique().tolist()
        competicao_sel = st.multiselect("🏆 Filtrar Competições:", options=competicoes_disp, default=competicoes_disp)
        
    with c2:
        # Dicionário amigável para a interface
        opcoes_metricas = {
            'Total Distance': 'Volume Total (Distância)',
            'HIA': 'Alta Intensidade (HIA)',
            'V5 Dist': 'Explosão (Sprints V5)',
            'Player Load': 'Desgaste Interno (Player Load)',
            'AccDec_Total': 'Força Mecânica (Acc/Dec)'
        }
        # Só mostra as métricas que realmente existem no df
        metricas_validas = {k: v for k, v in opcoes_metricas.items() if k in cols_existentes}
        
        metrica_visao = st.selectbox("📊 Métrica Principal para Gráficos:", options=list(metricas_validas.keys()), format_func=lambda x: metricas_validas[x])
    
    with c3:
        visao_tipo = st.radio("Foco da Análise:", ["Média da Equipa", "Atleta Específico"])

# Aplicar filtros
if competicao_sel:
    df_equipa_jogo = df_equipa_jogo[df_equipa_jogo['Competição'].isin(competicao_sel)]
    df_atleta_jogo = df_atleta_jogo[df_atleta_jogo['Competição'].isin(competicao_sel)]

# Se escolheu olhar para um atleta específico
if visao_tipo == "Atleta Específico":
    lista_atletas = sorted(df_atleta_jogo['Name'].unique())
    atleta_alvo = st.selectbox("👤 Selecione o Atleta:", lista_atletas)
    df_plot = df_atleta_jogo[df_atleta_jogo['Name'] == atleta_alvo].sort_values('Data')
    titulo_contexto = f"Desempenho de {atleta_alvo}"
else:
    df_plot = df_equipa_jogo.copy()
    titulo_contexto = "Média do Plantel"

if df_plot.empty:
    st.info("Não há dados para os filtros selecionados.")
    st.stop()

# =====================================================================
# 4. PAINEL DE KPIs (Resumo da Temporada)
# =====================================================================
st.markdown("### 🏆 Resumo Global (Filtros Aplicados)")

k1, k2, k3, k4 = st.columns(4)

total_jogos = df_plot['Data'].nunique()
media_dist = df_plot['Total Distance'].mean() if 'Total Distance' in df_plot.columns else 0
media_hia = df_plot['HIA'].mean() if 'HIA' in df_plot.columns else 0
media_load = df_plot['Player Load'].mean() if 'Player Load' in df_plot.columns else 0

k1.metric("Jogos Analisados", f"{total_jogos}", help="Quantidade de partidas dentro dos filtros selecionados.")
k2.metric("Média de Volume / Jogo", f"{media_dist:.0f} m", help=f"Distância média percorrida por {visao_tipo.lower()} por partida.")
k3.metric("Média de HIA / Jogo", f"{media_hia:.0f} ações", help=f"Quantidade média de ações de alta intensidade por partida.")
k4.metric("Desgaste Médio (Load)", f"{media_load:.0f}", help="Carga mecânica (Player Load) média por partida.")

st.divider()

# =====================================================================
# 5. VISUALIZAÇÕES (ABAS)
# =====================================================================
tab1, tab2, tab3 = st.tabs(["📈 Evolução Cronológica", "⚖️ Comparação de Competições", "🔥 Top Jogos Extremos"])

nome_metrica_legivel = metricas_validas.get(metrica_visao, metrica_visao)

with tab1:
    st.markdown(f"**Linha do Tempo: {nome_metrica_legivel} ({titulo_contexto})**")
    
    # Gráfico de linha com marcadores para mostrar a subida/descida de carga no calendário
    fig_timeline = px.line(
        df_plot, 
        x='Data_Display', 
        y=metrica_visao, 
        markers=True,
        color='Competição',
        title=f"Evolução ao longo da Temporada",
        labels={'Data_Display': 'Partida', metrica_visao: nome_metrica_legivel},
        template='plotly_white'
    )
    
    # Adicionar uma linha de tendência (Média Móvel de 3 jogos) para ver a fase do time
    df_plot['Media_Movel'] = df_plot[metrica_visao].rolling(window=3, min_periods=1).mean()
    fig_timeline.add_trace(go.Scatter(
        x=df_plot['Data_Display'], 
        y=df_plot['Media_Movel'],
        mode='lines', 
        name='Tendência (3 Jogos)',
        line=dict(color='gray', width=2, dash='dot')
    ))

    fig_timeline.update_layout(height=400, hovermode="x unified", xaxis_tickangle=-45)
    st.plotly_chart(fig_timeline, use_container_width=True)

with tab2:
    st.markdown(f"**Exigência Física por Competição: {nome_metrica_legivel}**")
    
    # Boxplot é perfeito aqui: mostra a média, mas também a variação (jogos fáceis vs jogos duros) na mesma competição
    fig_box = px.box(
        df_plot, 
        x='Competição', 
        y=metrica_visao, 
        color='Competição',
        points="all", # Mostra os pontinhos de cada jogo ao lado da caixa
        title=f"Distribuição de Carga por Torneio",
        labels={'Competição': 'Torneio', metrica_visao: nome_metrica_legivel},
        template='plotly_white'
    )
    fig_box.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_box, use_container_width=True)

with tab3:
    col_max, col_min = st.columns(2)
    
    # Top 5 Jogos mais intensos
    df_top = df_plot.nlargest(5, metrica_visao)
    # 5 Jogos menos intensos
    df_bottom = df_plot.nsmallest(5, metrica_visao)
    
    with col_max:
        st.markdown(f"🔴 **Top 5 Jogos de MAIOR Exigência**")
        fig_top = px.bar(
            df_top, 
            y='Data_Display', 
            x=metrica_visao, 
            orientation='h',
            color=metrica_visao,
            color_continuous_scale='Reds',
            labels={'Data_Display': 'Partida', metrica_visao: ''},
            template='plotly_white'
        )
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'}, height=350, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_top, use_container_width=True)

    with col_min:
        st.markdown(f"🟢 **Top 5 Jogos de MENOR Exigência**")
        fig_bottom = px.bar(
            df_bottom, 
            y='Data_Display', 
            x=metrica_visao, 
            orientation='h',
            color=metrica_visao,
            color_continuous_scale='Greens_r',
            labels={'Data_Display': 'Partida', metrica_visao: ''},
            template='plotly_white'
        )
        fig_bottom.update_layout(yaxis={'categoryorder':'total descending'}, height=350, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig_bottom, use_container_width=True)

# --- Implementação Opção 4: Placar vs. Intensidade ---
with tab1: # Pode criar uma nova tab4 se preferir
    st.markdown("### 🏟️ Comportamento Tático-Físico (Placar vs. HIA)")
    
    # Agrupamos a intensidade média por status do placar
    df_placar_int = df_raw.groupby('Placar')['HIA'].mean().reset_index()
    
    fig_placar = px.bar(
        df_placar_int,
        x='Placar',
        y='HIA',
        color='Placar',
        title="Intensidade Média da Equipe por Condição do Jogo",
        labels={'HIA': 'Média de Ações Intensas (HIA)'},
        color_discrete_map=config.MAPA_CORES_PLACAR, # Usando o mapa de cores do config.py
        template='plotly_white'
    )
    st.plotly_chart(fig_placar, use_container_width=True)
    st.info("💡 Este gráfico revela se a equipe mantém a intensidade alta mesmo quando está em vantagem ou se há um relaxamento físico.")
