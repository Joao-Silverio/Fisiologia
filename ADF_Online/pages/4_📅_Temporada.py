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
# FUNÇÃO LOCAL: MINI CARDS COM EFEITO VIDRO CENTRALIZADO E AJUSTADO
# =====================================================================
def renderizar_kpi_mini(titulo, valor, cor_borda=None, icone="📊", delta=None, delta_color="normal"):
    """Gera um KPI com efeito de vidro, texto centralizado e altura correta para não cortar."""
    if cor_borda is None: cor_borda = visual.CORES.get("primaria", "#3B82F6")
    
    if delta is not None and str(delta).strip() not in ["", "None", "0", "0.0"]:
        d_str = str(delta).strip()
        is_neg = d_str.startswith("-") or "▼" in d_str
        d_clean = d_str.replace("+", "").replace("-", "").replace("▼", "").replace("▲", "").strip()
        
        if delta_color == "normal":
            c_d = visual.CORES["alerta_fadiga"] if is_neg else visual.CORES["ok_prontidao"]
            seta = "▼" if is_neg else "▲"
        elif delta_color == "inverse":
            c_d = visual.CORES["ok_prontidao"] if is_neg else visual.CORES["alerta_fadiga"]
            seta = "▼" if is_neg else "▲"
        else:
            c_d = visual.CORES["texto_claro"]
            seta = "•"
            
        html_delta = f"<div style='margin-top: 6px; font-size: 13px; font-weight: 700; color: {c_d};'>{seta} {d_clean}</div>"
    else:
        # Espaço invisível para evitar quebra de layout
        html_delta = f"<div style='margin-top: 6px; font-size: 13px; opacity: 0;'>&nbsp;</div>"

    # Gradiente transparente para o efeito Glassmorphism
    fundo_vidro = f"linear-gradient(135deg, {cor_borda}22 0%, rgba(15, 23, 42, 0.8) 100%)"
    
    style_div = f"""
        background: {fundo_vidro};
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 18px 15px;
        border-left: 6px solid {cor_borda};
        border-top: 1px solid rgba(255, 255, 255, 0.1);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center; /* Centraliza Horizontalmente */
        text-align: center;  /* Centraliza o Texto */
        min-height: 125px;   /* Altura aumentada para nunca cortar o conteúdo */
        height: 100%;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        box-sizing: border-box;
    """
    
    style_tit = f"color: {visual.CORES['texto_claro']}; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; letter-spacing: 0.5px;"
    style_val = f"color: {visual.CORES['texto_escuro']}; font-size: 22px; font-weight: 800; line-height: 1.1;"

    html = f"""
    <div style='{style_div}'>
        <div style='{style_tit}'>{icone} {titulo}</div>
        <div style='{style_val}'>{valor}</div>
        {html_delta}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


# =====================================================================
# INICIALIZAÇÃO DA PÁGINA
# =====================================================================

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal (Home) primeiro.")
    st.stop()

df_cache_estatico = st.session_state['df_global'].copy()

# =====================================================================
# LAYOUT PRINCIPAL: 30% ESQUERDA (FILTROS) | 70% DIREITA (PAINEL)
# =====================================================================
col_esq, col_dir = st.columns([0.28, 0.72], gap="medium")

with col_esq:
    st.markdown("### 🔍 Configuração")
    
    # 1. Campeonato e Jogo Lado a Lado
    c_camp, c_jogo = st.columns(2)
    
    lista_campeonatos = sorted(df_cache_estatico['Competição'].dropna().unique().tolist())
    with c_camp:
        campeonatos_selecionados = st.multiselect("🏆 Campeonatos:", options=lista_campeonatos, default=[])
        
    df_base_estatico = df_cache_estatico[df_cache_estatico['Competição'].isin(campeonatos_selecionados)] if campeonatos_selecionados else df_cache_estatico.copy()
    lista_jogos_display = df_base_estatico.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
    
    with c_jogo: 
        jogo_selecionado_display = st.selectbox("📅 Jogo:", lista_jogos_display)
        
    if not jogo_selecionado_display: 
        st.warning("Nenhum dado encontrado.")
        st.stop()
        
    jogo_selecionado = df_base_estatico[df_base_estatico['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]
    df_jogo_filtrado = df_base_estatico[df_base_estatico['Data'] == jogo_selecionado].copy()

    # 2. Métrica Principal
    st.markdown("<br>", unsafe_allow_html=True)
    opcoes_metricas = {
        'Total Distance': 'Volume Total (Distância)',
        'HIA': 'Alta Intensidade (HIA)',
        'V5 Dist': 'Explosão (Sprints V5)',
        'Player Load': 'Desgaste Interno (Player Load)',
        'AccDec_Total': 'Força Mecânica (Acc/Dec)'
    }
    metricas_validas = {k: v for k, v in opcoes_metricas.items() if k in df_cache_estatico.columns or k in ['Acc3 Eff', 'Dec3 Eff']}
    metrica_visao = st.selectbox("📊 Métrica Principal:", options=list(metricas_validas.keys()), format_func=lambda x: metricas_validas[x])

    # 3. Foco da Análise
    visao_tipo = st.radio("🎯 Foco da Análise:", ["Média da Equipa", "Atleta Específico"])

    if visao_tipo == "Atleta Específico":
        lista_atletas = sorted(df_cache_estatico['Name'].dropna().unique())
        atleta_alvo = st.selectbox("👤 Selecione o Atleta:", lista_atletas)
    else:
        atleta_alvo = None

    # 4. Local do Jogo
    filtro_local = st.radio("🏟️ Local do Jogo:", ["Ambos", "Casa", "Fora"], horizontal=True)


# =====================================================================
# ÁREA DIREITA: FRAGMENTO DE ATUALIZAÇÃO (GRÁFICOS E KPIS)
# =====================================================================
with col_dir:
    st.markdown("### 📈 Painel da Temporada")

    # CSS ajustado para não colar as abas em cima dos KPIs (margin-top: 10px)
    st.markdown("""
        <style>
            div[data-testid="stTabs"] { margin-top: 10px !important; }
            .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        </style>
    """, unsafe_allow_html=True)

    @st.fragment(run_every="5s")
    def painel_temporada_ao_vivo(competicoes, metrica, visao, atleta, local):
        hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
        df_fresco, df_rec_fresco = load_global_data(hora_atual)
        
        if df_fresco.empty:
            df_fresco = st.session_state['df_global']
        else:
            st.session_state['df_global'] = df_fresco
            st.session_state['df_recordes'] = df_rec_fresco

        df_raw = df_fresco.copy()
        df_raw['Data'] = pd.to_datetime(df_raw['Data'], errors='coerce')
        df_raw = df_raw.sort_values('Data')

        # Agrupamento
        cols_agrupar = ['Total Distance', 'HIA', 'V5 Dist', 'Player Load', 'Acc3 Eff', 'Dec3 Eff']
        cols_existentes = [c for c in cols_agrupar if c in df_raw.columns]

        df_atleta_jogo = df_raw.groupby(['Data', 'Data_Display', 'Competição', 'Name', 'Jogou_em_Casa'])[cols_existentes].sum().reset_index()

        if 'Acc3 Eff' in df_atleta_jogo.columns and 'Dec3 Eff' in df_atleta_jogo.columns:
            df_atleta_jogo['AccDec_Total'] = df_atleta_jogo['Acc3 Eff'] + df_atleta_jogo['Dec3 Eff']
            if 'AccDec_Total' not in cols_existentes: cols_existentes.append('AccDec_Total')

        # Média da Equipe
        df_equipa_jogo = df_atleta_jogo.groupby(['Data', 'Data_Display', 'Competição', 'Jogou_em_Casa'])[cols_existentes].mean().reset_index()
        df_equipa_jogo = df_equipa_jogo.sort_values('Data')

        # Aplicando Filtros
        if competicoes:
            df_equipa_jogo = df_equipa_jogo[df_equipa_jogo['Competição'].isin(competicoes)]
            df_atleta_jogo = df_atleta_jogo[df_atleta_jogo['Competição'].isin(competicoes)]

        if local == "Casa":
            df_equipa_jogo = df_equipa_jogo[df_equipa_jogo['Jogou_em_Casa'] == 1]
            df_atleta_jogo = df_atleta_jogo[df_atleta_jogo['Jogou_em_Casa'] == 1]
        elif local == "Fora":
            df_equipa_jogo = df_equipa_jogo[df_equipa_jogo['Jogou_em_Casa'] == 0]
            df_atleta_jogo = df_atleta_jogo[df_atleta_jogo['Jogou_em_Casa'] == 0]

        if visao == "Atleta Específico" and atleta:
            df_plot = df_atleta_jogo[df_atleta_jogo['Name'] == atleta].sort_values('Data')
            titulo_contexto = f"Desempenho de {atleta}"
        else:
            df_plot = df_equipa_jogo.copy()
            titulo_contexto = "Média do Plantel"

        if df_plot.empty or metrica not in df_plot.columns:
            st.info("Não há dados suficientes para os filtros selecionados.")
            return

        # ==========================================
        # 1. KPIs CENTRAIS COM VIDRO
        # ==========================================
        total_jogos = df_plot['Data'].nunique()
        media_dist = df_plot['Total Distance'].mean() if 'Total Distance' in df_plot.columns else 0
        media_hia = df_plot['HIA'].mean() if 'HIA' in df_plot.columns else 0
        media_load = df_plot['Player Load'].mean() if 'Player Load' in df_plot.columns else 0

        k1, k2, k3, k4 = st.columns(4, gap="small")
        with k1: renderizar_kpi_mini("Jogos", f"{total_jogos}", icone="📅")
        with k2: renderizar_kpi_mini("Volume / Jogo", f"{media_dist:.0f} m", icone="🏃")
        with k3: renderizar_kpi_mini("HIA / Jogo", f"{media_hia:.0f}", cor_borda=visual.CORES["alerta_fadiga"], icone="🔥")
        with k4: renderizar_kpi_mini("Load / Jogo", f"{media_load:.0f}", cor_borda=visual.CORES["aviso_carga"], icone="🏋️‍♂️")
        
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

        # ==========================================
        # 2. TODAS AS ANÁLISES EM 5 ABAS
        # ==========================================
        tab1, tab2, tab3, tab4, tab5, tabScatter, tabLinhaBanda = st.tabs([
            "📈 Cronológica", 
            "⚽ Tática x Placar",
            "⚖️ Competições", 
            "🔥 Extremos",
            "🏟️ Casa vs Fora",
            "Scatter",
            "Linha com Banda"
        ])

        nome_metrica_legivel = metricas_validas.get(metrica, metrica)

        # --- ABA 1: CRONOLÓGICA ---
        with tab1:
            fig_line = px.line(
                df_plot, x='Data_Display', y=metrica, markers=True,
                title=f"Tendência de {nome_metrica_legivel} ({titulo_contexto})",
                template='plotly_dark'
            )
            fig_line.update_layout(
                xaxis_title="Data / Adversário", yaxis_title=nome_metrica_legivel,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=40, b=40)
            )
            fig_line.update_traces(line=dict(width=3, color=visual.CORES["secundaria"]), marker=dict(size=8))
            st.plotly_chart(fig_line, use_container_width=True, key="graf_line_temp")

        # --- ABA 2: TÁTICA X PLACAR ---
        with tab2:
            st.markdown("##### Comportamento Tático-Físico (Placar vs. HIA)")
            df_placar_int = df_raw.groupby('Placar')['HIA'].mean().reset_index()
            
            fig_placar = px.bar(
                df_placar_int, x='Placar', y='HIA', color='Placar',
                title="Intensidade Média da Equipe por Condição do Jogo",
                labels={'HIA': 'Média de Ações Intensas (HIA)'},
                color_discrete_map=config.MAPA_CORES_PLACAR, 
                template='plotly_dark'
            )
            fig_placar.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=20, r=20, t=40, b=40)
            )
            st.plotly_chart(fig_placar, width='stretch', key="graf_placar_hia")

        # --- ABA 3: COMPETIÇÕES ---
        with tab3:
            if 'Competição' in df_plot.columns:
                c_graf1, c_graf2 = st.columns(2)
                
                with c_graf1:
                    fig_box = px.box(
                        df_plot, x='Competição', y=metrica, color='Competição', points="all",
                        title=f"Variação de {nome_metrica_legivel}", template='plotly_dark'
                    )
                    fig_box.update_layout(showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                    st.plotly_chart(fig_box, width='stretch', key="graf_box")

                with c_graf2:
                    df_comp_sorted = df_plot.sort_values('Data')
                    fig_line_comp = px.line(
                        df_comp_sorted, x='Data_Display', y=metrica, color='Competição', markers=True,
                        title=f"Evolução por Competição", template='plotly_dark'
                    )
                    fig_line_comp.update_layout(
                        xaxis_title="Data", yaxis_title="", plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5)
                    )
                    st.plotly_chart(fig_line_comp, width='stretch', key="graf_line_comp")

                st.markdown("##### 📋 Resumo Estatístico")
                df_stats = df_plot.groupby('Competição')[metrica].agg(
                    Jogos='count', Média='mean', Máximo='max', Mínimo='min', Desvio_Padrão='std'
                ).reset_index().round(1)
                df_stats.rename(columns={'Média': f'Média ({nome_metrica_legivel})'}, inplace=True)
                st.dataframe(df_stats, use_container_width=True)

        # --- ABA 4: TOP JOGOS EXTREMOS ---
        with tab4:
            df_top = df_plot.sort_values(by=metrica, ascending=False).head(5)
            fig_top = px.bar(
                df_top, x='Data_Display', y=metrica, text_auto='.0f', color=metrica,
                color_continuous_scale='Reds', title=f"Top 5 Jogos de Maior Exigência ({titulo_contexto})",
                template='plotly_dark'
            )
            fig_top.update_layout(
                xaxis_title="Adversário", yaxis_title=nome_metrica_legivel,
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig_top, use_container_width=True, key="graf_top5")

        # --- ABA 5: CASA VS FORA ---
        with tab5:
            df_comp_local = df_atleta_jogo if visao == "Atleta Específico" else df_equipa_jogo
            if visao == "Atleta Específico" and atleta:
                df_comp_local = df_comp_local[df_comp_local['Name'] == atleta]

            if not df_comp_local.empty and 'Jogou_em_Casa' in df_comp_local.columns:
                df_casa_fora = df_comp_local.groupby('Jogou_em_Casa')[metrica].mean().reset_index()
                df_casa_fora['Local'] = df_casa_fora['Jogou_em_Casa'].map({1: '🏟️ Casa', 0: '🚌 Fora'})

                fig_comp_local = px.bar(
                    df_casa_fora, x='Local', y=metrica, color='Local', text_auto='.0f',
                    title=f"Média de {nome_metrica_legivel} por Localização",
                    color_discrete_map={'🏟️ Casa': '#2E7D32', '🚌 Fora': '#546E7A'},
                    template='plotly_dark'
                )
                
                fig_comp_local.update_layout(
                    showlegend=False, height=450,
                    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_comp_local, use_container_width=True, key="graf_casa_fora")
            else:
                st.warning("Não há dados suficientes sobre o Local do Jogo.")

        with tabScatter:
            df_scatter = df_comp_local[df_comp_local['Data'] == jogo_selecionado].copy()
            df_scatter_agg = df_scatter.groupby('Name').agg(
                Distancia=('Total Distance', 'sum'),
                Player_Load=('Player Load', 'sum'),
                HIA=('HIA', 'sum'),
                Minutos=('Min_Num', 'max')
            ).reset_index()
            df_scatter_agg['Carga_por_min'] = df_scatter_agg['Player_Load'] / df_scatter_agg['Minutos'].clip(lower=1)

            fig_scatter = px.scatter(
                df_scatter_agg, x='Minutos', y='Player_Load',
                size='HIA', color='Carga_por_min',
                text='Name', hover_data=['Distancia', 'HIA'],
                color_continuous_scale='RdYlGn',
                labels={'Player_Load': 'Player Load Total', 'Minutos': 'Minutos Jogados',
                        'Carga_por_min': 'Carga/min'},
                size_max=40
            )
            fig_scatter.update_traces(textposition='top center', textfont_size=10)
            fig_scatter.update_layout(
                height=420, template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(t=10, b=10)
            )
            st.plotly_chart(fig_scatter, width='stretch')

    # Inicializa o fragmento passando os filtros da esquerda
    painel_temporada_ao_vivo(
        campeonatos_selecionados,
        metrica_visao,
        visao_tipo,
        atleta_alvo,
        filtro_local
    )
