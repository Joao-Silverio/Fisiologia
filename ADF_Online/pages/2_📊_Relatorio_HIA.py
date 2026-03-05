import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import os
import warnings

from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.Dados.config as config
import Source.UI.visual as visual
import Source.UI.components as ui

# =====================================================================
# FUNÇÃO LOCAL: MINI CARDS PARA UMA ÚNICA LINHA PERFEITA
# =====================================================================
def renderizar_kpi_mini(titulo, valor, cor_borda=None, icone="📊", delta=None, delta_color="normal"):
    """Gera um KPI compacto para caber perfeitamente na mesma linha."""
    if cor_borda is None: cor_borda = visual.CORES.get("primaria", "#3B82F6")
    
    if delta is not None and str(delta).strip() != "" and str(delta).strip() != "None":
        d_str = str(delta).strip()
        is_neg = d_str.startswith("-") or "▼" in d_str
        d_clean = d_str.replace("+", "").replace("-", "").replace("▼", "").replace("▲", "").strip()
        
        if delta_color == "normal":
            c_d = visual.CORES["alerta_fadiga"] if is_neg else visual.CORES["ok_prontidao"]
            seta = "▼" if is_neg else "▲"
        elif delta_color == "inverse":
            c_d = visual.CORES["ok_prontidao"] if is_neg else visual.CORES["alerta_fadiga"]
            seta = "▼" if is_neg else "▲"
        elif delta_color == "off":
            c_d = visual.CORES["texto_claro"]
            seta = "•"
        else:
            c_d = visual.CORES["texto_claro"]
            seta = ""
        html_delta = f"<div style='margin-top: 4px; font-size: 11px; font-weight: 700; color: {c_d};'>{seta} {d_clean}</div>"
    else:
        html_delta = f"<div style='margin-top: 4px; font-size: 11px; font-weight: 700; opacity: 0;'>&nbsp;</div>"

    fundo = f"linear-gradient(135deg, {cor_borda}1A 0%, rgba(15, 23, 42, 0.7) 100%)"
    
    style_div = f"background: {fundo}; border-radius: 8px; padding: 12px 8px; border-left: 4px solid {cor_borda}; border-top: 1px solid #334155; border-right: 1px solid #334155; border-bottom: 1px solid #334155; display: flex; flex-direction: column; justify-content: center; min-height: 85px; height: 100%; box-shadow: 0 4px 10px rgba(0,0,0,0.3);"
    style_tit = f"color: {visual.CORES['texto_claro']}; font-size: 10px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
    style_val = f"color: {visual.CORES['texto_escuro']}; font-size: 17px; font-weight: 800; line-height: 1.1; white-space: nowrap;"

    html = f"""
    <div style='{style_div}' title='{titulo}'>
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

df_cache_estatico = st.session_state['df_global']
cols_componentes_hia_disp = [c for c in config.COLS_COMPONENTES_HIA if c in df_cache_estatico.columns]

# =====================================================================
# LAYOUT PRINCIPAL: 30% ESQUERDA (FILTROS) | 70% DIREITA (PAINEL)
# =====================================================================
col_esq, col_dir = st.columns([0.28, 0.72], gap="medium")

with col_esq:
    st.markdown("### 🔍 Configuração do Perfil")
    
    # 1. Campeonato e Jogo Lado a Lado
    c_camp, c_jogo = st.columns(2)
    
    lista_campeonatos = sorted(df_cache_estatico['Competição'].dropna().unique().tolist()) if 'Competição' in df_cache_estatico.columns else []
    with c_camp:
        campeonatos_selecionados = st.multiselect("🏆 Competições:", options=lista_campeonatos, default=[])
        
    df_base_estatico = df_cache_estatico[df_cache_estatico['Competição'].isin(campeonatos_selecionados)] if campeonatos_selecionados else df_cache_estatico.copy()
    lista_jogos_display = df_base_estatico.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
    
    with c_jogo: 
        jogo_selecionado_display = st.selectbox("📅 Selecione o Jogo:", lista_jogos_display)
        
    if not jogo_selecionado_display: 
        st.warning("Nenhum dado encontrado.")
        st.stop()
        
    jogo_selecionado = df_base_estatico[df_base_estatico['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]
    df_jogo_filtrado = df_base_estatico[df_base_estatico['Data'] == jogo_selecionado].copy()

    # 2. Período
    st.markdown("<br>", unsafe_allow_html=True)
    periodo_texto = st.radio("⏱️ Período de Análise:", ["1º Tempo", "2º Tempo"], horizontal=True)
    periodo_sel = 1 if periodo_texto == "1º Tempo" else 2

    # 3. Seleção de Atletas (Pills)
    st.markdown("<br>", unsafe_allow_html=True)
    lista_atletas = sorted(df_jogo_filtrado['Name'].dropna().unique())
    atleta_selecionado = st.pills("🏃 Selecione o Atleta para Foco Individual:", lista_atletas, default=lista_atletas[0] if lista_atletas else None)

    if not atleta_selecionado:
        st.warning("Por favor, selecione um atleta para continuar.")
        st.stop()

# =====================================================================
# ÁREA DIREITA: FRAGMENTO DE ATUALIZAÇÃO (GRÁFICO EMPILHADO + KPIS)
# =====================================================================
with col_dir:
    @st.fragment(run_every="5s")
    def painel_hia_ao_vivo(campeonatos, jogo_alvo, atleta, periodo):
        """Atualiza o gráfico de HIA dinamicamente em tempo real."""
        hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
        df_fresco, df_rec_fresco = load_global_data(hora_atual)
        
        if df_fresco.empty:
            df_fresco = st.session_state['df_global']
        else:
            st.session_state['df_global'] = df_fresco
            st.session_state['df_recordes'] = df_rec_fresco

        df_base = df_fresco[df_fresco['Competição'].isin(campeonatos)] if campeonatos else df_fresco
        df_equipa_jogo = df_base[df_base['Data'] == jogo_alvo].copy()
        df_atleta_jogo = df_equipa_jogo[df_equipa_jogo['Name'] == atleta].copy()
        
        cols_componentes_hia = [c for c in config.COLS_COMPONENTES_HIA if c in df_equipa_jogo.columns]
        
        df_periodo = df_atleta_jogo[df_atleta_jogo['Período'] == periodo].copy()

        if df_periodo.empty or not cols_componentes_hia:
            st.info(f"Nenhum dado de alta intensidade encontrado para o {periodo}º Tempo deste atleta.")
            return

        # =====================================================================
        # LÓGICA DE PROCESSAMENTO E AGREGAÇÃO DO HIA
        # =====================================================================
        df_minutos_components = df_periodo.groupby('Interval')[cols_componentes_hia].sum().reset_index()
        minuto_maximo = int(df_minutos_components['Interval'].max())
        todos_minutos = pd.DataFrame({'Interval': range(1, minuto_maximo + 1)})
        df_timeline_full = pd.merge(todos_minutos, df_minutos_components, on='Interval', how='left').fillna(0)
        df_timeline_full['Total_HIA_Min'] = df_timeline_full[cols_componentes_hia].sum(axis=1)
        
        # Cálculos da Média da Equipa
        df_equipa_periodo = df_equipa_jogo[df_equipa_jogo['Período'] == periodo].copy()
        
        if not df_equipa_periodo.empty:
            df_equipa_periodo['Total_HIA'] = df_equipa_periodo[cols_componentes_hia].sum(axis=1)
            hia_por_jogador = df_equipa_periodo.groupby('Name')['Total_HIA'].sum()
            hia_por_jogador = hia_por_jogador[hia_por_jogador > 0]
            media_hia_equipe = hia_por_jogador.mean() if not hia_por_jogador.empty else 0
            
            hia_jogador_minuto = df_equipa_periodo.groupby(['Interval', 'Name'])['Total_HIA'].sum().reset_index()
            media_grupo_minuto = hia_jogador_minuto.groupby('Interval')['Total_HIA'].mean().reset_index()
        else:
            media_hia_equipe = 0
            media_grupo_minuto = pd.DataFrame(columns=['Interval', 'Total_HIA'])

        # Cálculos Avançados do Atleta (Gaps e Densidade)
        df_timeline_full['Zero_Block'] = (df_timeline_full['Total_HIA_Min'] > 0).cumsum()
        sequencias_zeros = df_timeline_full[df_timeline_full['Total_HIA_Min'] == 0].groupby('Zero_Block').size()
        maior_gap_descanso = sequencias_zeros.max() if not sequencias_zeros.empty else 0
        
        total_hia_periodo = df_timeline_full['Total_HIA_Min'].sum()
        densidade = total_hia_periodo / minuto_maximo if minuto_maximo > 0 else 0
        delta_vs_equipe = ((total_hia_periodo / media_hia_equipe) - 1) * 100 if media_hia_equipe > 0 else 0.0

        # =====================================================================
        # GRÁFICO PLOTLY EMPILHADO
        # =====================================================================

        # =====================================================================
        # 5 MINIS KPIs EM UMA ÚNICA LINHA ABAIXO DO GRÁFICO
        # =====================================================================
        st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
        k1, k2, k3, k4, k5 = st.columns(5, gap="small")
        
        with k1: renderizar_kpi_mini("Minutos", f"{minuto_maximo}m", icone="⏱️")
        with k2: renderizar_kpi_mini("HIA Total", f"{total_hia_periodo:.0f}", cor_borda=visual.CORES["alerta_fadiga"], icone="⚡")
        with k3: renderizar_kpi_mini("Equipe", f"{media_hia_equipe:.1f}", delta=f"{delta_vs_equipe:+.1f}% vs Equipe", delta_color="normal", icone="👥")
        with k4: renderizar_kpi_mini("Densidade", f"{densidade:.2f}", icone="📊")
        with k5: renderizar_kpi_mini("S/ Estímulo", f"{maior_gap_descanso}m", delta="Recuperação", delta_color="off", cor_borda=visual.CORES["ok_prontidao"], icone="🔋")

        st.markdown(f"### ⏱️ Espectro de Intensidade: {atleta_selecionado} ({periodo_sel}º Tempo)")

        df_melted = df_timeline_full.melt(id_vars=['Interval'], value_vars=cols_componentes_hia, var_name='Tipo de Esforço', value_name='Qtd Ações')
        df_melted = df_melted[df_melted['Qtd Ações'] > 0]

        CORES_DARK_HIA = {
            'V4 To8 Eff': '#FDE68A', 'V5 To8 Eff': '#F59E0B', 'V6 To8 Eff': '#EF4444', 
            'Acc3 Eff': '#60A5FA', 'Dec3 Eff': '#10B981', 'Acc4 Eff': '#3B82F6', 'Dec4 Eff': '#059669',
        }

        fig = px.bar(df_melted, x='Interval', y='Qtd Ações', color='Tipo de Esforço', color_discrete_map=CORES_DARK_HIA, title=None)

        if not media_grupo_minuto.empty:
            fig.add_trace(go.Scatter(
                x=media_grupo_minuto['Interval'], y=media_grupo_minuto['Total_HIA'], mode='lines',
                name='Média da Equipe', line=dict(color='#F8FAFC', width=2, dash='dot'), hovertemplate='Média Equipe: %{y:.2f} ações<extra></extra>' 
            ))

        fig.update_layout(
            template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', 
            height=450, margin=dict(l=20, r=20, t=10, b=20),
            hovermode='x unified', bargap=0.15, 
            xaxis=dict(tickmode='linear', dtick=5, range=[0, minuto_maximo + 1], title="Minutos de Jogo", gridcolor='#334155'),
            yaxis=dict(title="Qtd. Ações HIA", gridcolor='#334155'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
        )
        fig.update_traces(hovertemplate='%{y:.2f} ações', selector=dict(type='bar'))

        fig.update_traces(hovertemplate='%{y:.2f} ações', selector=dict(type='bar'))

        # =====================================================================
        # 🆕 CRIANDO AS ABAS E DISTRIBUINDO OS GRÁFICOS
        # =====================================================================
        abas_hia = st.tabs(["📊 HIA Empilhado", "🔵 Dispersão de Carga", "📈 Evolução (Banda)"])

        # ---------------------------------------------------------------------
        # ABA 1: HIA Empilhado (O que você já tinha)
        # ---------------------------------------------------------------------
        with abas_hia[0]:
            st.plotly_chart(fig, width='stretch', key=f"hia_stacked_{periodo}_{atleta}_{jogo_alvo}")

        # ---------------------------------------------------------------------
        # ABA 2: Scatter (Dispersão: Carga vs Minutagem)
        # ---------------------------------------------------------------------
        with abas_hia[1]:
            st.markdown("#### 🔵 Dispersão: Carga vs Minutagem por Atleta")
            
            # Trocado df_completo por df_base e filtrado pelo jogo alvo do fragmento
            df_scatter = df_base[df_base['Data'] == jogo_alvo].copy()
            
            if not df_scatter.empty and 'Player Load' in df_scatter.columns:
                # Trocado Min_Num por Interval
                df_scatter_agg = df_scatter.groupby('Name').agg(
                    Distancia=('Total Distance', 'sum') if 'Total Distance' in df_scatter.columns else ('Interval', 'count'),
                    Player_Load=('Player Load', 'sum'),
                    HIA=('HIA', 'sum') if 'HIA' in df_scatter.columns else ('Interval', 'count'),
                    Minutos=('Interval', 'max')
                ).reset_index()
                
                df_scatter_agg['Carga_por_min'] = df_scatter_agg['Player_Load'] / df_scatter_agg['Minutos'].clip(lower=1)

                fig_scatter = px.scatter(
                    df_scatter_agg, x='Minutos', y='Player_Load',
                    size='HIA', color='Carga_por_min',
                    text='Name', hover_data=['Distancia', 'HIA'],
                    color_continuous_scale='RdYlGn',
                    labels={'Player_Load': 'Player Load Total', 'Minutos': 'Minutos Jogados', 'Carga_por_min': 'Carga/min'},
                    size_max=40
                )
                fig_scatter.update_traces(textposition='top center', textfont_size=10)
                fig_scatter.update_layout(
                    height=420, template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=10, b=10)
                )
                st.plotly_chart(fig_scatter, width='stretch', key=f"scatter_carga_{periodo}_{jogo_alvo}")
            else:
                st.info("Dados de carga insuficientes para este jogo.")

        # ---------------------------------------------------------------------
        # ABA 3: Linha com Banda de Confiança
        # ---------------------------------------------------------------------
        with abas_hia[2]:
            st.markdown("#### 📈 Evolução com Banda de Variação (±1 DP)")

            # Colunas para não empilhar os seletores
            c_atl, c_met = st.columns(2)
            with c_atl:
                atleta_linha = st.selectbox("Atleta:", sorted(df_base['Name'].dropna().unique()), key=f"sel_linha_{periodo}")
            with c_met:
                metrica_linha = st.radio("Métrica:", ['Total Distance', 'Player Load', 'HIA'], horizontal=True, key=f"rad_linha_{periodo}")

            if metrica_linha in df_base.columns:
                # Trocado df_completo por df_base
                df_linha = df_base[df_base['Name'] == atleta_linha].groupby(['Data','Data_Display'])[metrica_linha].sum().reset_index().sort_values('Data')

                if len(df_linha) >= 3:
                    media_l  = df_linha[metrica_linha].mean()
                    dp_l     = df_linha[metrica_linha].std()
                    
                    fig_banda = go.Figure()
                    
                    # Banda ±1 DP
                    fig_banda.add_trace(go.Scatter(
                        x=df_linha['Data_Display'], y=[media_l + dp_l] * len(df_linha),
                        mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'
                    ))
                    fig_banda.add_trace(go.Scatter(
                        x=df_linha['Data_Display'], y=[media_l - dp_l] * len(df_linha),
                        mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(96,165,250,0.1)',
                        name='±1 Desvio Padrão', hoverinfo='skip'
                    ))
                    
                    # Linha principal
                    cores_pts = ['#EF4444' if abs(v - media_l) > dp_l else '#22C55E' for v in df_linha[metrica_linha]]
                    fig_banda.add_trace(go.Scatter(
                        x=df_linha['Data_Display'], y=df_linha[metrica_linha],
                        mode='lines+markers', name=atleta_linha,
                        line=dict(color='#60A5FA', width=2),
                        marker=dict(size=9, color=cores_pts),
                        hovertemplate="<b>%{x}</b><br>Valor: %{y:.1f}<extra></extra>"
                    ))
                    
                    # Linha da média
                    fig_banda.add_hline(y=media_l, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                                        annotation_text=f"Média: {media_l:.1f}", annotation_position="top left")
                    
                    fig_banda.update_layout(
                        height=380, template='plotly_dark',
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                        xaxis_tickangle=-30, margin=dict(t=10, b=60),
                        legend=dict(orientation="h", y=-0.35, x=0.5, xanchor="center")
                    )
                    st.plotly_chart(fig_banda, width='stretch', key=f"banda_{periodo}_{atleta_linha}_{metrica_linha}")
                else:
                    st.info("Mínimo de 3 jogos para exibir a banda de variação.")
            else:
                st.warning("Métrica selecionada não encontrada nos dados.")

    # =====================================================================
    # Inicia o bloco fragmentado
    # =====================================================================
    painel_hia_ao_vivo(
        campeonatos_selecionados, 
        jogo_selecionado, 
        atleta_selecionado,
        periodo_sel
    )