import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import warnings

# Importações da Arquitetura
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.UI.visual as visual
import Source.UI.components as ui

# =====================================================================
# INICIALIZAÇÃO DA PÁGINA
# =====================================================================
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal (Home) primeiro.")
    st.stop()
    
df_cache_estatico = st.session_state['df_global'].copy()

# Garantindo a ordem ASCENDENTE por Data (Cronológica) para os filtros
if 'Data' in df_cache_estatico.columns:
    df_cache_estatico['Data'] = pd.to_datetime(df_cache_estatico['Data'], errors='coerce')
    df_cache_estatico = df_cache_estatico.sort_values(by='Data', ascending=False)

# =====================================================================
# LAYOUT PRINCIPAL: 30% ESQUERDA (FILTROS) | 70% DIREITA (PAINEL)
# =====================================================================
col_esq, col_dir = st.columns([0.28, 0.72], gap="medium")

with col_esq:
    st.markdown("### 🔍 Configuração")
    
    # 1. Campeonato e Jogo
    c_camp, c_jogo = st.columns(2)
    
    lista_campeonatos = sorted(df_cache_estatico['Competição'].dropna().unique().tolist()) if 'Competição' in df_cache_estatico.columns else []
    with c_camp:
        campeonatos_selecionados = st.multiselect("🏆 Competições:", options=lista_campeonatos, default=[])
        
    df_base_estatico = df_cache_estatico[df_cache_estatico['Competição'].isin(campeonatos_selecionados)] if campeonatos_selecionados else df_cache_estatico.copy()
    lista_jogos_display = df_base_estatico.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
    
    with c_jogo: 
        jogo_selecionado_display = st.selectbox("📅 Jogo:", lista_jogos_display)
        
    if not jogo_selecionado_display: 
        st.warning("Nenhum dado encontrado.")
        st.stop()
        
    jogo_selecionado = df_base_estatico[df_base_estatico['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]

    # 2. Período
    st.markdown("<br>", unsafe_allow_html=True)
    periodo_texto = st.radio("⏱️ Período:", ["1º Tempo", "2º Tempo"], horizontal=True)
    periodo_sel = 1 if periodo_texto == "1º Tempo" else 2

    # 3. Tamanho do Bloco
    st.markdown("<br>", unsafe_allow_html=True)
    opcao_bloco = st.pills("Tamanho do Bloco de Análise:", ["3 minutos", "5 minutos", "15 minutos"], default="5 minutos")
    mapa_colunas_bloco = {"15 minutos": "Parte (15 min)", "5 minutos": "Parte (5 min)", "3 minutos": "Parte (3 min)"}
    coluna_faixa_sel = mapa_colunas_bloco[opcao_bloco]


# =====================================================================
# ÁREA DIREITA: FRAGMENTO DE ATUALIZAÇÃO (GRÁFICOS E ALERTAS)
# =====================================================================
with col_dir:
    st.markdown("### 🚨 Monitoramento Contínuo (V4)")

    @st.fragment(run_every="5s")
    def painel_fadiga_ao_vivo(campeonatos, jogo_alvo, periodo, coluna_faixa):
        """Atualiza a página de fadiga dinamicamente em tempo real."""
        
        hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
        df_fresco, df_rec_fresco = load_global_data(hora_atual)
        
        if df_fresco.empty:
            df_fresco = st.session_state['df_global']
        else:
            st.session_state['df_global'] = df_fresco
            st.session_state['df_recordes'] = df_rec_fresco

        df_base = df_fresco[df_fresco['Competição'].isin(campeonatos)] if campeonatos else df_fresco
        df_jogo = df_base[df_base['Data'] == jogo_alvo].copy()
        df_periodo = df_jogo[df_jogo['Período'] == periodo].copy()

        if df_periodo.empty:
            st.info(f"Nenhum dado encontrado para o {periodo}º Tempo deste jogo.")
            return

        if coluna_faixa not in df_periodo.columns:
            st.warning(f"A coluna de agrupamento '{coluna_faixa}' não está disponível nos dados atuais.")
            return

        # ==========================================
        # 1. LÓGICA DE ALERTAS (V4 DIST)
        # ==========================================
        col_v4 = 'V4 Dist'
        df_periodo = df_periodo.dropna(subset=[coluna_faixa])

        # Alerta: Jogadores com mais de 8 minutos sem ação em V4
        df_ausente = df_periodo[df_periodo[col_v4] <= 0].copy()
        contagem_critica = df_ausente.groupby('Name').size()
        atletas_em_alerta = contagem_critica[contagem_critica > 8].index.tolist()

        if atletas_em_alerta:
            st.error(f"⚠️ **ALERTA DE QUEDA DE INTENSIDADE:** Atletas com longo tempo (>8 min) sem estímulo em V4: **{', '.join(atletas_em_alerta)}**")

        # ==========================================
        # 2. ABAS (VISÃO GERAL x MAPA DE OCIOSIDADE)
        # ==========================================
        aba_visao_geral, aba_mapa = st.tabs(["📊 Visão Geral (V4)", "🕵️‍♂️ Mapa de Ociosidade"])

        # ABA 1: Visão Geral (2 Gráficos Lado a Lado)
        with aba_visao_geral:
            c_graf1, c_graf2 = st.columns(2)

            with c_graf1:
                df_contagem = df_ausente.groupby(['Name', coluna_faixa]).size().reset_index(name='Minutos_Ausentes')
                fig_rank = px.bar(
                    df_contagem, y="Name", x="Minutos_Ausentes", color=coluna_faixa,
                    orientation='h', template='plotly_dark',
                    color_discrete_sequence=px.colors.qualitative.Safe,
                    title="Minutos Acumulados em 'Apagão' (V4)"
                )
                fig_rank.update_layout(
                    barmode='stack', yaxis={'categoryorder':'total ascending'}, height=400,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig_rank, width='stretch', key=f"bar_{periodo}")

            with c_graf2:
                df_heatmap = df_periodo.groupby(['Interval', 'Name'])[col_v4].sum().reset_index()
                fig_heat = px.density_heatmap(
                    df_heatmap, x="Interval", y="Name", z=col_v4,
                    color_continuous_scale="Viridis", template='plotly_dark',
                    labels={'Interval': 'Minuto', col_v4: 'Distância'},
                    title="Densidade de Alta Velocidade (V4)"
                )
                fig_heat.update_layout(
                    height=400,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig_heat, use_container_width=True, key=f"heat_{periodo}")

        # ABA 2: Mapa de Ociosidade
        with aba_mapa:
            st.markdown("##### 🕵️‍♂️ Mapa de Ociosidade sobre a História do Jogo")
            st.caption("As barras coloridas aparecem **apenas** quando o atleta parou de correr. Os espaços vazios representam ação. O fundo indica o status do placar.")

            min_max = int(df_periodo['Interval'].max())
            status_jogo = df_periodo[['Interval', 'Placar']].drop_duplicates().sort_values('Interval')

            df_apenas_ausencia = df_periodo[df_periodo[col_v4] <= 0].copy()

            fig_final = go.Figure()

            # Blocos de 1 minuto para cada registro de ausência
            for placar_val in df_apenas_ausencia['Placar'].unique():
                df_group = df_apenas_ausencia[df_apenas_ausencia['Placar'] == placar_val]
                
                fig_final.add_trace(go.Bar(
                    y=df_group['Name'],
                    x=[1] * len(df_group), # Largura exata de 1 minuto
                    base=df_group['Interval'] - 0.5, # Posição
                    orientation='h',
                    name=str(placar_val),
                    marker_color=config.MAPA_CORES_PLACAR.get(placar_val, '#888888'), 
                    hovertemplate="Atleta: %{y}<br>Minuto: %{base}<extra></extra>"
                ))

            # Pintando o fundo com a história do jogo
            for i in range(len(status_jogo)):
                min_inicio = status_jogo.iloc[i]['Interval']
                min_fim = status_jogo.iloc[i+1]['Interval'] if i+1 < len(status_jogo) else min_max
                
                cor_contexto = config.MAPA_CORES_PLACAR.get(status_jogo.iloc[i]['Placar'], "#334155")
                
                fig_final.add_vrect(
                    x0=min_inicio - 0.5, x1=min_fim + 0.5,
                    fillcolor=cor_contexto, opacity=0.15, 
                    layer="below", line_width=0,
                )

            # Ajustes de Layout do Mapa de Ociosidade
            fig_final.update_layout(
                template='plotly_dark',
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                height=600,
                barmode='overlay', # Barras não empilham
                xaxis=dict(
                    title="Minuto de Jogo",
                    tickmode='linear', dtick=5,
                    range=[0, min_max + 1],
                    gridcolor='#334155'
                ),
                yaxis=dict(title="Atletas", categoryorder='total descending'),
                bargap=0.4,
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                margin=dict(l=20, r=20, t=20, b=50)
            )

            st.plotly_chart(fig_final, use_container_width=True, key=f"mapa_ociosidade_{periodo}")

    # Inicializa o fragmento passando os filtros selecionados
    painel_fadiga_ao_vivo(
        campeonatos_selecionados, 
        jogo_selecionado, 
        periodo_sel,
        coluna_faixa_sel
    )