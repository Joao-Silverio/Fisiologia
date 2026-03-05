import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import os
import warnings

from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
from Source.ML.ml_engine import executar_ml_ao_vivo
import Source.Dados.config as config
import Source.UI.visual as visual
import Source.UI.components as ui

# Validação inicial
if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal (Home) primeiro.")
    st.stop()

modo_apres = ui.renderizar_toggle_apresentacao()

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

df_cache_estatico = st.session_state['df_global']

# =====================================================================
# FUNÇÃO LOCAL: MINI CARDS PARA UMA ÚNICA LINHA PERFEITA
# =====================================================================
def renderizar_kpi_mini(titulo, valor, cor_borda=None, icone="📊", delta=None, delta_color="normal"):
    """Gera um KPI compacto para caber 7 na mesma linha sem espremer a fonte."""
    if cor_borda is None: cor_borda = visual.CORES.get("primaria", "#3B82F6")
    
    # Tratamento do delta
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

    # Estilização Compacta
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

    st.markdown("""
        <style>
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }
        </style>
    """, unsafe_allow_html=True)

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

    # 2. Período
    st.markdown("<br>", unsafe_allow_html=True)
    periodo_texto = st.radio("⏱️ Período de Análise:", ["1º Tempo", "2º Tempo"], horizontal=True)
    periodo_sel = 1 if periodo_texto == "1º Tempo" else 2

    # 3. Seleção de Atletas (Pills)
    st.markdown("<br>", unsafe_allow_html=True)
    lista_atletas = sorted(df_jogo_filtrado['Name'].dropna().unique())
    atleta_selecionado = st.pills("🏃 Selecione o Atleta:", lista_atletas, default=lista_atletas[0] if lista_atletas else None)

    if not atleta_selecionado:
        st.warning("Por favor, selecione um atleta para continuar.")
        st.stop()

with col_dir:
    st.markdown("### 🚀 Projeção e Machine Learning")

    # =====================================================================
    # VISÃO GERAL DO ELENCO (RADAR DE FADIGA)
    # =====================================================================
    with st.expander("👁️ Ver Radar do Elenco (Jogo Atual)", expanded=False):
        df_equipe_jogo = df_base_estatico[(df_base_estatico['Data'] == jogo_selecionado) & (df_base_estatico['Período'] == periodo_sel)].copy()
        
        if not df_equipe_jogo.empty:
            dados_radar = []
            for atl in df_equipe_jogo['Name'].unique():
                df_a = df_equipe_jogo[df_equipe_jogo['Name'] == atl].sort_values('Interval')
                if not df_a.empty:
                    load_total = df_a['Player Load'].sum() if 'Player Load' in df_a.columns else 0
                    intensidade_5m = (df_a['Total Distance'].tail(5).sum() / 5) if 'Total Distance' in df_a.columns else 0
                    
                    cor_ponto = visual.CORES['ok_prontidao']
                    if load_total > 400 and intensidade_5m < 70: 
                        cor_ponto = visual.CORES['alerta_fadiga']
                    elif load_total > 400 and intensidade_5m > 110:
                        cor_ponto = visual.CORES['aviso_carga']
                        
                    dados_radar.append({'Atleta': atl, 'Load': load_total, 'Intensidade': intensidade_5m, 'Cor': cor_ponto})
            
            df_radar = pd.DataFrame(dados_radar)
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatter(
                x=df_radar['Load'], y=df_radar['Intensidade'], mode='markers+text',
                text=df_radar['Atleta'], textposition="top center",
                marker=dict(size=14, color=df_radar['Cor'], line=dict(width=1, color='white')),
                hovertemplate="<b>%{text}</b><br>Load: %{x:.0f}<br>m/min (5m): %{y:.1f}<extra></extra>"
            ))
            fig_radar.update_layout(
                template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                title="Radar Coletivo: Volume x Ritmo Agudo",
                xaxis_title="Volume Total (Load Acumulado)", yaxis_title="Intensidade (m/min - Últimos 5m)",
                height=350, margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig_radar, width='stretch')
        else:
            st.info("Aguardando dados da equipe para o jogo selecionado...")

    # CSS Ajustado: Removemos o margin-top negativo das abas para não quebrar as abas aninhadas
    st.markdown("""
        <style>
            div[data-testid="stSlider"] { margin-bottom: 0px !important; }
            .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        </style>
    """, unsafe_allow_html=True)

    @st.fragment(run_every="5s")
    def painel_tracker_ao_vivo(campeonatos, jogo_alvo, atleta, periodo):
        hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
        df_fresco, df_rec_fresco = load_global_data(hora_atual)
        
        if df_fresco.empty: df_fresco = st.session_state['df_global']
        else:
            st.session_state['df_global'] = df_fresco
            st.session_state['df_recordes'] = df_rec_fresco

        df_base = df_fresco[df_fresco['Competição'].isin(campeonatos)] if campeonatos else df_fresco
        df_atleta = df_base[df_base['Name'] == atleta].copy()
        
        coluna_jogo, coluna_minuto = 'Data', 'Interval'
        df_periodo = df_atleta[df_atleta['Período'] == periodo].sort_values(by=[coluna_jogo, coluna_minuto])
        
        # Recalcular Acumulados
        for col_calc, col_acum in [('Total Distance', 'Dist Acumulada'), ('V4 Dist', 'V4 Dist Acumulada'), ('V5 Dist', 'V5 Dist Acumulada'), ('V4 To8 Eff', 'V4 Eff Acumulada'), ('V5 To8 Eff', 'V5 Eff Acumulada'), ('HIA', 'HIA Acumulada'), ('Player Load', 'Player Load Acumulada')]:
            if col_calc in df_periodo.columns: df_periodo[col_acum] = df_periodo.groupby(coluna_jogo)[col_calc].cumsum()

        df = df_periodo.dropna(subset=[coluna_minuto]).copy()
        if df.empty:
            st.info(f"Nenhum dado encontrado para o {periodo}º Tempo deste atleta.")
            return

        max_minutos_por_jogo = df.groupby(coluna_jogo)[coluna_minuto].max()
        if jogo_alvo not in max_minutos_por_jogo.index:
            st.warning(f"O atleta selecionado não atuou no {periodo}º Tempo deste jogo.")
            return
            
        minuto_atual_max = int(max_minutos_por_jogo[jogo_alvo])
        minuto_final_partida = int(max_minutos_por_jogo.max())
        
        # --- SLIDERS DA SIMULAÇÃO ---
        col_s1, col_s2 = st.columns(2)
        key_corte, key_proj = f"slider_corte_{periodo}_{atleta}", f"slider_proj_{periodo}_{atleta}"
        teto_maximo = max(minuto_final_partida, 45 if periodo == 1 else 50)
        
        if key_corte not in st.session_state: st.session_state[key_corte] = minuto_atual_max
        if key_proj not in st.session_state: st.session_state[key_proj] = teto_maximo

        with col_s1: minuto_corte = st.slider(f"⏱️ Início da Previsão (Corte):", min_value=1, max_value=minuto_atual_max, value=st.session_state[key_corte], step=1, key=key_corte)
        with col_s2: minuto_projecao_ate = st.slider(f"🚀 Fim da Previsão (Projetar até):", min_value=1, max_value=teto_maximo, value=max(st.session_state[key_proj], minuto_corte), step=1, key=key_proj) 

        df_historico_base = df[df[coluna_jogo] != jogo_alvo].copy()
        df_atual_base = df[df[coluna_jogo] == jogo_alvo].sort_values(coluna_minuto)
        
        # --- ABAS PRINCIPAIS (MÉTRICAS) ---
        opcoes_metricas = list(config.METRICAS_CONFIG.keys())
        abas = st.tabs(opcoes_metricas)
        
        for i, metrica in enumerate(opcoes_metricas):
            with abas[i]:
                cfg = config.METRICAS_CONFIG[metrica]
                coluna_distancia, coluna_acumulada, unidade = cfg["coluna_distancia"], cfg["coluna_acumulada"], cfg["unidade"]

                df_historico = df_historico_base.dropna(subset=[coluna_acumulada]).copy()
                df_atual = df_atual_base.dropna(subset=[coluna_acumulada]).copy()
                df_atual_corte = df_atual[df_atual[coluna_minuto] <= minuto_corte].copy()

                ml = executar_ml_ao_vivo(df_historico, df_atual_corte, df_base, coluna_distancia, coluna_acumulada, coluna_minuto, coluna_jogo, jogo_alvo, periodo, minuto_projecao_ate, metrica, atleta, DIRETORIO_ATUAL)

                # =====================================================================
                # RENDERIZANDO OS KPIs (AGORA NA POSIÇÃO CORRETA, ACIMA DOS GRÁFICOS)
                # =====================================================================
                carga_atual = df_atual_corte[coluna_acumulada].iloc[-1] if not df_atual_corte.empty else 0
                pl_atual = df_atual_corte['Player Load Acumulada'].iloc[-1] if 'Player Load Acumulada' in df_atual_corte.columns and not df_atual_corte.empty else 0

                val_recorde = 0
                if 'df_recordes' in st.session_state:
                    rec = st.session_state['df_recordes']
                    sufixo_recorde = config.METRICAS_CONFIG[metrica].get('arquivo_modelo', '').replace('modelo_', '').replace('.pkl', '') or metrica.replace(' ', '_')
                    if f"Recorde_5min_{sufixo_recorde}" in rec.columns:
                        recorde_atleta = rec[rec['Name'] == atleta][f"Recorde_5min_{sufixo_recorde}"].values
                        val_recorde = recorde_atleta[0] if len(recorde_atleta) > 0 else 0
                
                esforço_atual_5m = df_atual_corte[coluna_distancia].tail(5).sum() if not df_atual_corte.empty else 0
                percentual_do_limite = (esforço_atual_5m / val_recorde * 100) if val_recorde > 0 else 0

                def fmt_dist(x): return f"{x:.2f}{unidade}" if not np.isnan(x) and metrica in ["Total Distance", "V4 Dist", "V5 Dist"] else f"{x:.0f}{unidade}" if not np.isnan(x) else "N/A"
                def fmt_pct(x): return f"{x:+.1f}%" if not np.isnan(x) else "N/A"
                def fmt_pct_color(x, t_cor="normal"): 
                    if np.isnan(x): return "N/A"
                    is_neg = x < 0
                    cor = visual.CORES["alerta_fadiga"] if (is_neg and t_cor=="normal") or (not is_neg and t_cor=="inverse") else visual.CORES["ok_prontidao"]
                    return f"<span style='color: {cor};'>{abs(x):.1f}%</span>"

                cor_delta = "normal" if metrica in ["V4 Dist", "HIA", "Total Distance"] else "inverse"

                # 🆕 ALERTA DE FADIGA — Calcula delta de cada atleta no jogo atual
                alertas_fadiga = []
                for nome_atleta in df_base[df_base['Data'] == jogo_alvo]['Name'].unique():
                    df_hist_a = df_base[(df_base['Name'] == nome_atleta) & 
                                        (df_base['Data'] != jogo_alvo) & 
                                        (df_base['Período'] == periodo)]
                    df_hoje_a = df_base[(df_base['Name'] == nome_atleta) & 
                                        (df_base['Data'] == jogo_alvo) & 
                                        (df_base['Período'] == periodo) &
                                        (df_base[coluna_minuto] <= minuto_atual_max)]
                    
                    if df_hist_a.empty or df_hoje_a.empty:
                        continue
                    
                    carga_hoje_a = df_hoje_a['Total Distance'].sum()
                    media_hist_a = df_hist_a.groupby('Data')['Total Distance'].sum().mean()
                    delta_a = ((carga_hoje_a / media_hist_a) - 1) * 100 if media_hist_a > 0 else 0
                    
                    if delta_a > 20:
                        alertas_fadiga.append((nome_atleta, delta_a, "🔴 Sobrecarga"))
                    elif delta_a < -20:
                        alertas_fadiga.append((nome_atleta, delta_a, "🟡 Abaixo do padrão"))

                if alertas_fadiga:
                    with st.expander(f"⚠️ {len(alertas_fadiga)} atleta(s) fora do padrão — clique para ver", expanded=True):
                        cols_alerta = st.columns(len(alertas_fadiga))
                        for col_a, (nome_a, delta_a, tipo_a) in zip(cols_alerta, alertas_fadiga):
                            cor_a = visual.CORES["alerta_fadiga"] if delta_a > 0 else visual.CORES["aviso_carga"]
                            col_a.markdown(f"""
                                <div style='border:2px solid {cor_a}; border-radius:8px; padding:10px; text-align:center;
                                            background:{cor_a}22; animation: pulse 2s infinite;'>
                                    <b style='color:{cor_a}'>{tipo_a}</b><br>
                                    <span style='font-size:0.9rem'>{nome_a}</span><br>
                                    <b style='color:{cor_a}; font-size:1.2rem'>{delta_a:+.1f}%</b>
                                </div>
                            """, unsafe_allow_html=True)

                st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
                k0, k1, k2, k3, k4, k5, k6 = st.columns(7, gap="small")
                with k0: renderizar_kpi_mini("Corte", fmt_dist(carga_atual), cor_borda=visual.CORES["primaria"], icone="⏳")
                with k1: renderizar_kpi_mini("Histórico", fmt_pct_color(ml['delta_alvo_pct'], cor_delta), cor_borda=visual.CORES["secundaria"], icone="🕰️")
                with k2: renderizar_kpi_mini("Equipe", fmt_pct(ml['delta_time_pct']), delta=f"{fmt_pct(ml['delta_atleta_vs_time'])}", delta_color=cor_delta, cor_borda=visual.CORES["secundaria"], icone="👥")
                with k3: renderizar_kpi_mini("Proj. Final", fmt_dist(ml['carga_projetada']), cor_borda=visual.CORES["primaria"], icone="🚀")
                with k4: renderizar_kpi_mini("Ritmo", fmt_pct_color(ml['delta_projetado_pct'], cor_delta), cor_borda=visual.CORES["primaria"], icone="📈")
                with k5: renderizar_kpi_mini("Load Atual", f"{pl_atual:.0f}", delta=fmt_pct(ml['delta_pl_pct']), delta_color="inverse", cor_borda=visual.CORES["aviso_carga"], icone="🔋")
                with k6: renderizar_kpi_mini("Pico (5m)", f"{percentual_do_limite:.0f}%", delta=f"{val_recorde:.0f}{unidade}", delta_color="off", cor_borda=visual.CORES["alerta_fadiga"], icone="🔥")

                # ESPAÇAMENTO RESPIRÁVEL ENTRE KPIs E GRÁFICOS
                st.markdown("<div style='margin-top: 20px; margin-bottom: 5px;'></div>", unsafe_allow_html=True)

                # =====================================================================
                # CONSTRUÇÃO DOS GRÁFICOS
                # =====================================================================
                hover_formato = "%{y:.2f}" + unidade if metrica in ["Total Distance", "V4 Dist", "V5 Dist"] else "%{y:.0f}" + unidade

                # 1. Gráfico de Acumulado (Projeção)
                fig = go.Figure()
                if not df_historico.empty:
                    jogos_historicos = df_historico[coluna_jogo].unique()
                    colors = px.colors.qualitative.Set1
                    for idx, jogo in enumerate(jogos_historicos):
                        df_j = df_historico[df_historico[coluna_jogo] == jogo].sort_values(coluna_minuto)
                        jogo_disp = df_base[df_base['Data'] == jogo]['Data_Display'].iloc[0] if jogo in df_base['Data'].values else str(jogo)
                        fig.add_trace(go.Scatter(x=df_j[coluna_minuto], y=df_j[coluna_acumulada], mode='lines', name=jogo_disp, opacity=0.35, line=dict(color=colors[idx % len(colors)], width=2), hovertemplate=f'<b>{jogo_disp}</b><br>Valor: {hover_formato}<extra></extra>'))

                jogo_disp_atual = df_base[df_base['Data'] == jogo_alvo]['Data_Display'].iloc[0] if jogo_alvo in df_base['Data'].values else str(jogo_alvo)
                fig.add_trace(go.Scatter(x=df_atual[coluna_minuto], y=df_atual[coluna_acumulada], mode='lines', name=f'{jogo_disp_atual} (Real)', line=dict(color='#00E676', width=4), hovertemplate=f'<b>{jogo_disp_atual}</b><br>Valor: {hover_formato}<extra></extra>'))

                if len(ml['minutos_futuros']) > 0 and len(ml['pred_superior']) > 0: 
                    fig.add_trace(go.Scatter(x=ml['minutos_futuros'], y=ml['pred_superior'], mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                    fig.add_trace(go.Scatter(x=ml['minutos_futuros'], y=ml['pred_inferior'], mode='lines', line=dict(width=0), fill='tonexty', fillcolor='rgba(255, 140, 0, 0.15)', name='Margem Variação', hoverinfo='skip'))
                    fig.add_trace(go.Scatter(x=ml['minutos_futuros'], y=ml['acumulado_pred'], mode='lines', name='Projeção IA', line=dict(color='#FF8C00', width=3, dash='dash'), hovertemplate=f'Projeção: {hover_formato}<extra></extra>'))
                    minuto_atual = df_atual_corte[coluna_minuto].iloc[-1] if not df_atual_corte.empty else 0
                    fig.add_vline(x=minuto_atual, line_dash="dash", line_color="#E53935")

                fig.update_xaxes(tickmode='linear', dtick=1, range=[0, minuto_projecao_ate + 2], tickfont=dict(size=10))
                fig.update_layout(template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', title=f"{cfg['titulo_grafico']} - {atleta} ({periodo}º T)", xaxis_title='Minutos', yaxis_title=metrica, legend=dict(bgcolor='rgba(0,0,0,0)', orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5), height=400, hovermode='x unified', margin=dict(l=20, r=20, t=40, b=20))

                # 2. Gráfico de Média Móvel
                fig_movel = go.Figure()
                if not df_atual.empty and coluna_distancia in df_atual.columns:
                    df_temp = df_atual.copy()
                    df_temp['Movel_3m'] = df_temp[coluna_distancia].rolling(window=3, min_periods=1).mean()
                    fig_movel.add_trace(go.Scatter(x=df_temp[coluna_minuto], y=df_temp['Movel_3m'], mode='lines', name='Ritmo Médio (3m)', line=dict(color=visual.CORES['secundaria'], width=3, shape='spline'), fill='tozeroy', fillcolor='rgba(96, 165, 250, 0.1)', hovertemplate="Min: %{x}<br>Média (3m): %{y:.1f}<extra></extra>"))
                fig_movel.update_layout(template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', title=f"Média Móvel de Ritmo (3 min) - {atleta}", xaxis_title="Minutos", yaxis_title=f"{metrica} / min", height=400, margin=dict(l=20, r=20, t=40, b=20), hovermode='x unified')

                # 3. Gráfico de Densidade
                fig_dens = go.Figure()
                if not df_atual.empty and coluna_distancia in df_atual.columns:
                    cor_barra = visual.CORES['alerta_fadiga'] if metrica in ["V4 Dist", "V5 Dist", "HIA"] else visual.CORES['secundaria']
                    fig_dens.add_trace(go.Bar(x=df_atual[coluna_minuto], y=df_atual[coluna_distancia], marker_color=cor_barra, opacity=0.85, name='Esforço Agudo', hovertemplate="Min: %{x}<br>Valor: %{y:.1f}<extra></extra>"))
                fig_dens.update_layout(template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', title=f"Densidade de Esforços por Minuto - {atleta}", xaxis_title="Minutos", yaxis_title=f"Valor Bruto ({unidade})", bargap=0.2, height=400, margin=dict(l=20, r=20, t=40, b=20), hovermode='x unified')

                # =====================================================================
                # EXIBIÇÃO: ABAS DOS GRÁFICOS (EMBAIXO DOS KPIs)
                # =====================================================================
                abas_graficos = st.tabs(["📈 Acumulado (Projeção)", "🌊 Ritmo (Média Móvel)", "📊 Densidade (Esforços)"])
                with abas_graficos[0]: st.plotly_chart(fig, width='stretch', key=f"graf_acum_{periodo}_{i}_{atleta}")
                with abas_graficos[1]: st.plotly_chart(fig_movel, width='stretch', key=f"graf_movel_{periodo}_{i}_{atleta}")
                with abas_graficos[2]: st.plotly_chart(fig_dens, width='stretch', key=f"graf_dens_{periodo}_{i}_{atleta}")

    painel_tracker_ao_vivo(campeonatos_selecionados, jogo_selecionado, atleta_selecionado, periodo_sel)