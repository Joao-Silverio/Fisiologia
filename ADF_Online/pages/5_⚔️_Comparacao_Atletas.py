import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from Source.Dados.positions import get_position, get_benchmark, classify_performance, position_badge_html, POSITION_CONFIG

# 1. Novas Importações
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
from streamlit_autorefresh import st_autorefresh
import Source.UI.visual as visual
import Source.UI.components as ui

# 3. Cabeçalho Padronizado
ui.renderizar_cabecalho("Comparação de Atletas", "Comparativo direto de performance e métricas de GPS")

# 1. Pede à página para "piscar os olhos" a cada 2 segundos (2000 ms)
st_autorefresh(interval=2000, limit=None, key="refresh_desta_pagina")

# 2. Verifica a "impressão digital" (hora exata) do ficheiro Excel
hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

# 3. Pede os dados. Se a "hora_atual" não mudou, o Streamlit não faz NADA (0% de CPU).
df_novo, df_recordes_novo = load_global_data(hora_atual)

# 4. Atualiza a memória global para os gráficos desenharem com os dados frescos
if not df_novo.empty:
    st.session_state['df_global'] = df_novo
    st.session_state['df_recordes'] = df_recordes_novo

if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal ou verifique o arquivo Excel.")
    st.stop()
    
df_base = st.session_state['df_global'].copy()

# 1. Converte a coluna para o formato de data (caso ainda não esteja)
df_base['Data'] = pd.to_datetime(df_base['Data'], errors='coerce')

# 2. Ordena os dados do MAIS NOVO para o MAIS ANTIGO (ascending=False)
df_base = df_base.sort_values(by='Data', ascending=False)

# 3. Cria o nome de exibição do jogo já com os dados ordenados
df_base['Data_Display'] = df_base['Data'].dt.strftime('%d/%m/%Y') + ' ' + df_base['Adversário'].astype(str)

# ==========================================
# 2. FILTROS DE COMPARAÇÃO (TUDO EM UMA LINHA)
# ==========================================
st.markdown("### 🔍 Configuração do Duelo")

with st.container():
    c1, c2, c3, c4, c5 = st.columns([1.3, 1.5, 1.2, 1.2, 1.2])
    
    with c1:
        competicao_sel = st.multiselect("🏆 Competição:", options=df_base['Competição'].unique().tolist() if 'Competição' in df_base.columns else [])
        df_f1 = df_base[df_base['Competição'].isin(competicao_sel)] if competicao_sel else df_base.copy()

    with c2:
        jogo_sel = st.selectbox("📅 Selecione o Jogo:", df_f1['Data_Display'].unique())
        df_jogo_full = df_f1[df_f1['Data_Display'] == jogo_sel]
        
    with c3:
        periodo_sel = st.radio("⏱️ Período:", ["Ambos", "1º Tempo", "2º Tempo"], horizontal = True)

    # Lista de atletas disponíveis no jogo
    atletas_jogo = sorted(df_jogo_full['Name'].unique())

    with c4:
        atleta_1 = st.selectbox("🔴 Atleta 1 (Referência):", atletas_jogo, index=0)
        
    with c5:
        index_a2 = 1 if len(atletas_jogo) > 1 else 0
        atleta_2 = st.selectbox("🔵 Atleta 2 (Desafiante):", atletas_jogo, index=index_a2)

pos_a1 = get_position(atleta_1)
pos_a2 = get_position(atleta_2)

if atleta_1 == atleta_2:
    st.warning("⚠️ Selecione dois atletas diferentes para a comparação.")
    st.stop()

# Aplicação do Filtro de Período
elif periodo_sel == "1º Tempo":
    df_jogo = df_jogo_full[df_jogo_full['Período'] == 1].copy()
elif periodo_sel == "2º Tempo":
    df_jogo = df_jogo_full[df_jogo_full['Período'] == 2].copy()
else:
    df_jogo = df_jogo_full.copy()

if df_jogo.empty:
    st.warning(f"⚠️ Não há dados disponíveis para {periodo_sel} neste jogo.")
    st.stop()

# ==========================================
# 3. PREPARAÇÃO DOS DADOS (AGRUPAMENTO DO JOGO)
# ==========================================
cols_volume = ['Total Distance', 'V4 Dist', 'V5 Dist', 'Player Load']
cols_hia = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Acc4 Eff', 'Dec4 Eff']
cols_existentes = [c for c in cols_volume + cols_hia if c in df_jogo.columns]

df_jogo['HIA_Total'] = df_jogo[[c for c in cols_hia if c in df_jogo.columns]].sum(axis=1)
if 'HIA_Total' not in cols_existentes:
    cols_existentes.append('HIA_Total')

df_agrupado = df_jogo.groupby('Name')[cols_existentes].sum().reset_index()

df_agrupado['AccDec_Total'] = df_agrupado.get('Acc3 Eff', 0) + df_agrupado.get('Dec3 Eff', 0)

minutos_jogados = (
    df_jogo.groupby('Name')
    .apply(lambda x: x.set_index(['Período', 'Interval']).index.nunique())
    .reset_index()
)
minutos_jogados.columns = ['Name', 'Minutos Jogados']
df_agrupado = pd.merge(df_agrupado, minutos_jogados, on='Name')

df_a1 = df_agrupado[df_agrupado['Name'] == atleta_1].iloc[0] if not df_agrupado[df_agrupado['Name'] == atleta_1].empty else None
df_a2 = df_agrupado[df_agrupado['Name'] == atleta_2].iloc[0] if not df_agrupado[df_agrupado['Name'] == atleta_2].empty else None

if df_a1 is None or df_a2 is None:
    st.error("Dados insuficientes para um dos atletas neste jogo.")
    st.stop()

# ==========================================
# 4. PAINEL DE KPIs: O DUELO
# ==========================================
st.subheader("📊 Resumo do Confronto (Jogo Completo)")

# PARA:
c1.markdown(f"""
    <div style='display:flex; flex-direction:column; align-items:center; gap:4px;'>
        <div style='display:flex; align-items:center; justify-content:center; gap:10px;'>
            {position_badge_html(pos_a1)}
            <h4 style='color:#EF5350; margin:0;'>🔴 {atleta_1}</h4>
        </div>
        <p style='margin:0; opacity:0.7; font-size:0.85rem;'>{df_a1['Minutos Jogados']:.0f} min</p>
    </div>
""", unsafe_allow_html=True)

c2.markdown("<h3 style='text-align:center; opacity:0.7;'>VS</h3>", unsafe_allow_html=True)

c3.markdown(f"""
    <div style='display:flex; flex-direction:column; align-items:center; gap:4px;'>
        <div style='display:flex; align-items:center; justify-content:center; gap:10px;'>
            <h4 style='color:#42A5F5; margin:0;'>🔵 {atleta_2}</h4>
            {position_badge_html(pos_a2)}
        </div>
        <p style='margin:0; opacity:0.7; font-size:0.85rem;'>{df_a2['Minutos Jogados']:.0f} min</p>
    </div>
""", unsafe_allow_html=True)

# Alerta quando posições diferentes — comparação com contexto
if pos_a1 and pos_a2 and pos_a1 != pos_a2:
    cfg1 = POSITION_CONFIG[pos_a1]
    cfg2 = POSITION_CONFIG[pos_a2]
    st.info(
        f"ℹ️ **Posições diferentes:** {cfg1['emoji']} {cfg1['label']} vs {cfg2['emoji']} {cfg2['label']}. "
        "Os valores absolutos não são diretamente comparáveis — use o radar 'Por Posição' para uma análise justa."
    )

col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5, col_kpi6 = st.columns(6)

def kpi_card(col, label, val1, val2, unidade=""):
    cor1 = "#4CAF50" if val1 > val2 else "#EF5350" if val1 < val2 else "gray" 
    cor2 = "#4CAF50" if val2 > val1 else "#EF5350" if val2 < val1 else "gray"
    
    with col:
        st.markdown(f"""
        <div style='background-color: rgba(130, 130, 130, 0.15); 
                    padding: 15px 5px; 
                    border-radius: 10px; 
                    border: 1px solid rgba(130, 130, 130, 0.4); 
                    box-shadow: 0 4px 6px rgba(0,0,0,0.2);
                    display: flex; 
                    flex-direction: column; 
                    justify-content: center; 
                    align-items: center; 
                    height: 100%;'>
            <p style='color: var(--text-color); margin: 0 0 10px 0; font-size: 13px; font-weight: bold; opacity: 0.9;'>{label}</p>
            <div style='display: flex; justify-content: center; align-items: center; gap: 10px; width: 100%;'>
                <span style='color: {cor1}; font-size: 18px; font-weight: 800;'>{val1:.0f}{unidade}</span> 
                <span style='color: var(--text-color); opacity: 0.4; font-size: 14px;'>x</span> 
                <span style='color: {cor2}; font-size: 18px; font-weight: 800;'>{val2:.0f}{unidade}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

kpi_card(col_kpi1, "Distância", df_a1.get('Total Distance', 0), df_a2.get('Total Distance', 0), "m")
kpi_card(col_kpi2, "HIA (Total)", df_a1.get('HIA_Total', 0), df_a2.get('HIA_Total', 0), "")
kpi_card(col_kpi3, "Distância em V4", df_a1.get('V4 Dist', 0), df_a2.get('V4 Dist', 0), "m")
kpi_card(col_kpi4, "Distância em Sprints", df_a1.get('V5 Dist', 0), df_a2.get('V5 Dist', 0), "m")
kpi_card(col_kpi5, "Acc + Dec", df_a1.get('AccDec_Total', 0), df_a2.get('AccDec_Total', 0), "")
kpi_card(col_kpi6, "Player Load", df_a1.get('Player Load', 0), df_a2.get('Player Load', 0), "")

# ==========================================
# 5. RADAR E GRÁFICOS DE LINHA (EM ABAS)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True)
col_radar, col_timeline = st.columns([1, 1.4])

with col_radar:
    st.subheader("🕸️ Perfil Fisiológico")
    
    metricas_radar = ['Total Distance', 'V4 Dist', 'V5 Dist', 'HIA_Total', 'AccDec_Total', 'Player Load']
    metricas_radar = [m for m in metricas_radar if m in df_agrupado.columns]
    
    nomes_bonitos = {
        'Total Distance': 'Distância',
        'V4 Dist': 'Distância V4',
        'V5 Dist': 'Distância V5',
        'HIA_Total': 'HIA Total',
        'AccDec_Total': 'Acc/Dec',
        'Player Load': 'Player Load'
    }
    
    # 🆕 Toggle de modo de normalização
    modo_radar = st.radio(
        "Normalizar radar por:",
        ["🏟️ Máximo do time", "📍 Benchmark da posição"],
        horizontal=True,
        help="'Benchmark da posição' avalia cada atleta contra o esperado para sua função tática, não contra o colega.",
    )

    if modo_radar == "📍 Benchmark da posição":
        def _norm_pos(row_data, position, metrics):
            vals = []
            for m in metrics:
                v = float(row_data.get(m, 0) or 0)
                bench = get_benchmark(position, m)
                vals.append(min(v / bench["elite"] * 100, 150) if bench and bench["elite"] > 0 else 0)
            return vals

        val1_norm = _norm_pos(df_a1, pos_a1, metricas_radar)
        val2_norm = _norm_pos(df_a2, pos_a2, metricas_radar)
        radial_range = [0, 150]
        tick_suffix  = "% elite"
    else:
        maximos_time = df_agrupado[metricas_radar].max().replace(0, 1)
        val1_norm = (df_a1[metricas_radar].fillna(0).infer_objects(copy=False) / maximos_time * 100).fillna(0).infer_objects(copy=False).tolist()
        val2_norm = (df_a2[metricas_radar].fillna(0).infer_objects(copy=False) / maximos_time * 100).fillna(0).infer_objects(copy=False).tolist()
        radial_range = [0, 100]
        tick_suffix  = "%"
        
    val1_orig = df_a1[metricas_radar].fillna(0).infer_objects(copy=False).tolist()
    val2_orig = df_a2[metricas_radar].fillna(0).infer_objects(copy=False).tolist()
    
    val1_norm += [val1_norm[0]]
    val2_norm += [val2_norm[0]]
    val1_orig += [val1_orig[0]]  
    val2_orig += [val2_orig[0]]  
    
    categorias_labels = [nomes_bonitos.get(m, m) for m in metricas_radar]
    categorias_labels += [categorias_labels[0]]
    
    fig_radar = go.Figure()
    
    fig_radar.add_trace(go.Scatterpolar(
        r=val1_norm, 
        theta=categorias_labels, 
        fill='toself', 
        name=atleta_1, 
        line_color='#EF5350', 
        fillcolor='rgba(239, 83, 80, 0.4)',
        mode='lines+markers',           
        hoveron='points',               
        customdata=val1_orig,           
        hovertemplate='<b>%{theta}</b><br>Valor Real: %{customdata:.0f}<br>Escala (%): %{r:.1f}%<extra></extra>'
    ))
    
    fig_radar.add_trace(go.Scatterpolar(
        r=val2_norm, 
        theta=categorias_labels, 
        fill='toself', 
        name=atleta_2, 
        line_color='#42A5F5', 
        fillcolor='rgba(66, 165, 245, 0.4)',
        mode='lines+markers',           
        hoveron='points',               
        customdata=val2_orig,           
        hovertemplate='<b>%{theta}</b><br>Valor Real: %{customdata:.0f}<br>Escala (%): %{r:.1f}%<extra></extra>'
    ))

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=radial_range, ticksuffix=tick_suffix)),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        height=450, margin=dict(t=30, b=40, l=40, r=40)
    )
    st.plotly_chart(fig_radar, width='stretch')

with col_timeline:
    st.subheader("📈 Corrida de Ritmo (Timeline)")

    # Timeline sempre usa o jogo completo — independente do filtro de período
    def preparar_timeline(df_jogo_full, atleta):
        df = df_jogo_full[df_jogo_full['Name'] == atleta].copy()
        
        # Ordena por Período → Interval para garantir sequência correta
        df = df.sort_values(['Período', 'Interval']).reset_index(drop=True)
        
        # Cria minuto contínuo: 2º tempo começa de onde o 1º terminou
        df['Minuto'] = range(1, len(df) + 1)

        # Linha vertical de separação dos tempos
        fim_1t = df[df['Período'] == 1]['Minuto'].max() if 1 in df['Período'].values else None

        # Acumulados
        df['Total_Dist_Acum'] = df['Total Distance'].cumsum() if 'Total Distance' in df.columns else 0
        df['V4_Acum']         = df['V4 Dist'].cumsum()        if 'V4 Dist'        in df.columns else 0

        col_sprint = 'V5 Dist' if 'V5 Dist' in df.columns else 'V5 To8 Eff'
        df['V5_Acum'] = df[col_sprint].cumsum() if col_sprint in df.columns else 0

        acc = df['Acc3 Eff'] if 'Acc3 Eff' in df.columns else pd.Series(0, index=df.index)
        dec = df['Dec3 Eff'] if 'Dec3 Eff' in df.columns else pd.Series(0, index=df.index)
        df['AccDec_Acum'] = (acc + dec).cumsum()

        return df, fim_1t

    df_tl_a1, fim_1t = preparar_timeline(df_jogo, atleta_1)
    df_tl_a2, _      = preparar_timeline(df_jogo, atleta_2)

    if periodo_sel != "Ambos":
        fim_1t = None

    def desenhar_grafico_linha(df1, df2, coluna_y, titulo_y, fim_1t):
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df1['Minuto'], y=df1[coluna_y], mode='lines',
            name=atleta_1, line=dict(color='#EF5350', width=3)
        ))
        fig.add_trace(go.Scatter(
            x=df2['Minuto'], y=df2[coluna_y], mode='lines',
            name=atleta_2, line=dict(color='#42A5F5', width=3)
        ))
        # Linha vertical separando 1º e 2º tempo
        if fim_1t:
            fig.add_vline(
                x=fim_1t, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                annotation_text="Intervalo", annotation_position="top",
                annotation_font=dict(size=11, color="rgba(255,255,255,0.5)")
            )
        fig.update_layout(
            height=380,
            xaxis_title="Minuto de Jogo", yaxis_title=titulo_y,
            hovermode="x unified", margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        return fig

    tab0, tab1, tab2, tab3 = st.tabs(["📏 Distância Total", "⚡ V4 Acumulada", "🚀 Sprints (V5)", "🛑 Força (Acc3 + Dec3)"])

    with tab0:
        st.plotly_chart(desenhar_grafico_linha(df_tl_a1, df_tl_a2, 'Total_Dist_Acum', 'Distância Total Acumulada (m)', fim_1t), width='stretch', key="grafico_tab0")
    with tab1:
        st.plotly_chart(desenhar_grafico_linha(df_tl_a1, df_tl_a2, 'V4_Acum', 'Volume de V4 (m)', fim_1t), width='stretch', key="grafico_tab1")
    with tab2:
        st.plotly_chart(desenhar_grafico_linha(df_tl_a1, df_tl_a2, 'V5_Acum', 'Volume de Sprint', fim_1t), width='stretch', key="grafico_tab2")
    with tab3:
        st.plotly_chart(desenhar_grafico_linha(df_tl_a1, df_tl_a2, 'AccDec_Acum', 'Ações de Acc/Dec', fim_1t), width='stretch', key="grafico_tab3")