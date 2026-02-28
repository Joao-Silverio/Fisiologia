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

# =====================================================================
# ÁREA DIREITA: FRAGMENTO DE ATUALIZAÇÃO (SLIDERS + ABAS + GRÁFICO + KPIS)
# =====================================================================
with col_dir:
    st.markdown("### 🚀 Projeção e Machine Learning")

    # CSS para colar as abas aos sliders e diminuir margens vazias
    st.markdown("""
        <style>
            div[data-testid="stSlider"] { margin-bottom: 0px !important; }
            div[data-testid="stTabs"] { margin-top: -30px !important; }
            .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        </style>
    """, unsafe_allow_html=True)

    @st.fragment(run_every="5s")
    def painel_tracker_ao_vivo(campeonatos, jogo_alvo, atleta, periodo):
        hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
        df_fresco, df_rec_fresco = load_global_data(hora_atual)
        
        if df_fresco.empty:
            df_fresco = st.session_state['df_global']
        else:
            st.session_state['df_global'] = df_fresco
            st.session_state['df_recordes'] = df_rec_fresco

        df_base = df_fresco[df_fresco['Competição'].isin(campeonatos)] if campeonatos else df_fresco
        df_atleta = df_base[df_base['Name'] == atleta].copy()
        
        coluna_jogo = 'Data'
        coluna_minuto = 'Interval'

        df_periodo = df_atleta[df_atleta['Período'] == periodo].copy()
        df_periodo = df_periodo.sort_values(by=[coluna_jogo, coluna_minuto])
        
        # Recalcular Acumulados
        for col_calc, col_acum in [
            ('Total Distance', 'Dist Acumulada'), ('V4 Dist', 'V4 Dist Acumulada'),
            ('V5 Dist', 'V5 Dist Acumulada'), ('V4 To8 Eff', 'V4 Eff Acumulada'),
            ('V5 To8 Eff', 'V5 Eff Acumulada'), ('HIA', 'HIA Acumulada'), 
            ('Player Load', 'Player Load Acumulada')
        ]:
            if col_calc in df_periodo.columns:
                df_periodo[col_acum] = df_periodo.groupby(coluna_jogo)[col_calc].cumsum()

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
        key_corte = f"slider_corte_{periodo}_{atleta}"
        key_proj = f"slider_proj_{periodo}_{atleta}"
        teto_maximo = max(minuto_final_partida, 45 if periodo == 1 else 50)
        
        if key_corte not in st.session_state: st.session_state[key_corte] = minuto_atual_max
        if key_proj not in st.session_state: st.session_state[key_proj] = teto_maximo

        with col_s1:
            minuto_corte = st.slider(f"⏱️ Início da Previsão (Corte):", min_value=1, max_value=minuto_atual_max, value=st.session_state[key_corte], step=1, key=key_corte)
        with col_s2:
            val_proj_atual = max(st.session_state[key_proj], minuto_corte)
            minuto_projecao_ate = st.slider(f"🚀 Fim da Previsão (Projetar até):", min_value=1, max_value=teto_maximo, value=val_proj_atual, step=1, key=key_proj) 

        df_historico_base = df[df[coluna_jogo] != jogo_alvo].copy()
        df_atual_base = df[df[coluna_jogo] == jogo_alvo].sort_values(coluna_minuto)
        
        # --- ABAS DAS MÉTRICAS ---
        opcoes_metricas = list(config.METRICAS_CONFIG.keys())
        abas = st.tabs(opcoes_metricas)
        
        for i, metrica in enumerate(opcoes_metricas):
            with abas[i]:
                cfg = config.METRICAS_CONFIG[metrica]
                coluna_distancia = cfg["coluna_distancia"]
                coluna_acumulada = cfg["coluna_acumulada"]
                unidade = cfg["unidade"]
                titulo_grafico = f"{cfg['titulo_grafico']} - {atleta} ({periodo}º T)"

                df_historico = df_historico_base.dropna(subset=[coluna_acumulada]).copy()
                df_atual = df_atual_base.dropna(subset=[coluna_acumulada]).copy()
                df_atual_corte = df_atual[df_atual[coluna_minuto] <= minuto_corte].copy()

                carga_atual = df_atual_corte[coluna_acumulada].iloc[-1] if not df_atual_corte.empty else 0
                minuto_atual = df_atual_corte[coluna_minuto].iloc[-1] if not df_atual_corte.empty else 0
                pl_atual = df_atual_corte['Player Load Acumulada'].iloc[-1] if 'Player Load Acumulada' in df_atual_corte.columns and not df_atual_corte.empty else 0

                ml = executar_ml_ao_vivo(
                    df_historico, df_atual_corte, df_base,
                    coluna_distancia, coluna_acumulada, coluna_minuto, coluna_jogo,
                    jogo_alvo, periodo, minuto_projecao_ate, metrica,
                    atleta, DIRETORIO_ATUAL
                )

                # =====================================================================
                # 7 KPIs NA MESMA LINHA (RENDERIZADOS ABAIXO DO GRÁFICO)
                # =====================================================================
                def fmt_dist(x):
                    if metrica in ["Total Distance", "V4 Dist", "V5 Dist"]: return f"{x:.2f}{unidade}" if not np.isnan(x) else "N/A"
                    else: return f"{x:.0f}{unidade}" if not np.isnan(x) else "N/A"
                        
                def fmt_pct(x): return f"{x:+.1f}%" if not np.isnan(x) else "N/A"

                cor_delta = "normal" if metrica in ["V4 Dist", "HIA", "Total Distance"] else "inverse"
                
                cor_grupo_volume = visual.CORES["primaria"]      
                cor_grupo_media  = visual.CORES["secundaria"]    
                cor_grupo_load   = visual.CORES["aviso_carga"]   
                cor_grupo_pico   = visual.CORES["alerta_fadiga"] 
                
                def fmt_pct_colorido(x, tipo_cor="normal"):
                    if np.isnan(x): return "N/A"
                    is_neg = x < 0
                    seta = "▼" if is_neg else "▲"
                    if tipo_cor == "normal": cor = visual.CORES["alerta_fadiga"] if is_neg else visual.CORES["ok_prontidao"]
                    else: cor = visual.CORES["ok_prontidao"] if is_neg else visual.CORES["alerta_fadiga"]
                    return f"<span style='color: {cor};'>{abs(x):.1f}%</span>"
                
                # --- Cálculo do Pico(5m) ---
                val_recorde = 0
                if 'df_recordes' in st.session_state:
                    rec = st.session_state['df_recordes']
                    sufixo_recorde = config.METRICAS_CONFIG[metrica].get('arquivo_modelo', '').replace('modelo_', '').replace('.pkl', '')
                    if not sufixo_recorde: 
                        sufixo_recorde = metrica.replace(' ', '_')
                    nome_coluna_recorde = f"Recorde_5min_{sufixo_recorde}"
                    
                    if nome_coluna_recorde in rec.columns:
                        recorde_atleta = rec[rec['Name'] == atleta][nome_coluna_recorde].values
                        val_recorde = recorde_atleta[0] if len(recorde_atleta) > 0 else 0
                
                esforço_atual_5m = df_atual_corte[coluna_distancia].tail(5).sum() if not df_atual_corte.empty else 0
                percentual_do_limite = (esforço_atual_5m / val_recorde * 100) if val_recorde > 0 else 0

                # Renderiza a única linha com gap reduzido
                st.markdown("<div style='margin-top: 5px;'></div>", unsafe_allow_html=True)
                k0, k1, k2, k3, k4, k5, k6 = st.columns(7, gap="small")
                with k0: renderizar_kpi_mini("Corte", fmt_dist(carga_atual), cor_borda=cor_grupo_volume, icone="⏳")
                with k1: renderizar_kpi_mini("Histórico", fmt_pct_colorido(ml['delta_alvo_pct'], cor_delta), cor_borda=cor_grupo_media, icone="🕰️")
                with k2: renderizar_kpi_mini("Equipe", fmt_pct(ml['delta_time_pct']), delta=f"{fmt_pct(ml['delta_atleta_vs_time'])}", delta_color=cor_delta, cor_borda=cor_grupo_media, icone="👥")
                with k3: renderizar_kpi_mini(f"Proj. Final", fmt_dist(ml['carga_projetada']), cor_borda=cor_grupo_volume, icone="🚀")
                with k4: renderizar_kpi_mini("Ritmo", fmt_pct_colorido(ml['delta_projetado_pct'], cor_delta), cor_borda=cor_grupo_volume, icone="📈")
                with k5: renderizar_kpi_mini("Load Atual", f"{pl_atual:.0f}", delta=fmt_pct(ml['delta_pl_pct']), delta_color="inverse", cor_borda=cor_grupo_load, icone="🔋")
                with k6: renderizar_kpi_mini("Pico (5m)", f"{percentual_do_limite:.0f}%", delta=f"{val_recorde:.0f}{unidade}", delta_color="off", cor_borda=cor_grupo_pico, icone="🔥")

                
                # =====================================================================
                # GRÁFICO PLOTLY (AGORA ACIMA DOS KPIS)
                # =====================================================================
                if metrica in ["Total Distance", "V4 Dist", "V5 Dist"]: hover_formato = "%{y:.2f}" + unidade
                else: hover_formato = "%{y:.0f}" + unidade

                fig = go.Figure()
                
                if not df_historico.empty:
                    jogos_historicos = df_historico[coluna_jogo].unique()
                    colors = px.colors.qualitative.Set1
                    for idx, jogo in enumerate(jogos_historicos):
                        df_j = df_historico[df_historico[coluna_jogo] == jogo].sort_values(coluna_minuto)
                        jogo_disp = df_base[df_base['Data'] == jogo]['Data_Display'].iloc[0] if jogo in df_base['Data'].values else str(jogo)
                        fig.add_trace(go.Scatter(
                            x=df_j[coluna_minuto], y=df_j[coluna_acumulada], mode='lines',
                            name=jogo_disp, opacity=0.35, line=dict(color=colors[idx % len(colors)], width=2), 
                            hovertemplate=f'<b>{jogo_disp}</b><br>Valor: {hover_formato}<extra></extra>'
                        ))

                jogo_disp_atual = df_base[df_base['Data'] == jogo_alvo]['Data_Display'].iloc[0] if jogo_alvo in df_base['Data'].values else str(jogo_alvo)
                fig.add_trace(go.Scatter(
                    x=df_atual[coluna_minuto], y=df_atual[coluna_acumulada], mode='lines',
                    name=f'{jogo_disp_atual} (Real)', line=dict(color='#00E676', width=4), 
                    hovertemplate=f'<b>{jogo_disp_atual}</b><br>Valor: {hover_formato}<extra></extra>'
                ))

                if len(ml['minutos_futuros']) > 0 and len(ml['pred_superior']) > 0: 
                    fig.add_trace(go.Scatter(x=ml['minutos_futuros'], y=ml['pred_superior'], mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
                    fig.add_trace(go.Scatter(
                        x=ml['minutos_futuros'], y=ml['pred_inferior'], mode='lines', line=dict(width=0),
                        fill='tonexty', fillcolor='rgba(255, 140, 0, 0.15)', name='Margem de Variação', hoverinfo='skip'
                    ))
                    fig.add_trace(go.Scatter(
                        x=ml['minutos_futuros'], y=ml['acumulado_pred'], mode='lines', name='Projeção da IA',
                        line=dict(color='#FF8C00', width=3, dash='dash'), hovertemplate=f'Projeção: {hover_formato}<extra></extra>'
                    ))
                    fig.add_vline(x=minuto_atual, line_dash="dash", line_color="#E53935")

                x_min = 0
                x_max = minuto_projecao_ate + 2  

                fig.update_xaxes(tickmode='linear', dtick=1, range=[x_min, x_max], tickfont=dict(size=10), tickangle=0)

                # Altura do gráfico e margem inferior reduzidas para integrar melhor com os KPIs abaixo
                fig.update_layout(
                    template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                    title=titulo_grafico,
                    xaxis_title=f'Minutos', yaxis_title=metrica,
                    legend=dict(bgcolor='rgba(0,0,0,0)', orientation="h", yanchor="top", y=-0.2, xanchor="center", x=0.5),
                    height=480, hovermode='x unified', margin=dict(l=20, r=20, t=50, b=80) 
                )

                st.plotly_chart(fig, use_container_width=True, key=f"graf_{periodo}_{i}_{atleta}")

    # Inicializa o fragmento passando os parâmetros da coluna Esquerda (Filtros)
    painel_tracker_ao_vivo(
        campeonatos_selecionados, 
        jogo_selecionado, 
        atleta_selecionado,
        periodo_sel
    )