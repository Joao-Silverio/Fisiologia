import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# ==========================================
# 1. CONFIGURAÇÃO E ESTILO
# ==========================================
st.set_page_config(page_title="Raio-X: Duelo de Atletas", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("⚔️ Raio-X: Duelo de Atletas (Head-to-Head)")
st.markdown("Comparação direta de performance física e mecânica no mesmo jogo.")

if 'df_global' not in st.session_state:
    st.warning("Carregue os dados na página principal (Home) primeiro.")
    st.stop()
    
df_base = st.session_state['df_global'].copy()
df_base['Data_Display'] = pd.to_datetime(df_base['Data']).dt.strftime('%d/%m/%Y') + ' ' + df_base['Adversário'].astype(str)

# ==========================================
# 2. FILTROS DE COMPARAÇÃO
# ==========================================
st.markdown("### 🔍 Configuração do Duelo")

with st.container():
    c1, c2, c3, c4 = st.columns([1.5, 2, 1.5, 1.5])
    
    with c1:
        competicao_sel = st.multiselect("🏆 Competição:", options=df_base['Competição'].unique().tolist() if 'Competição' in df_base.columns else [])
        df_f1 = df_base[df_base['Competição'].isin(competicao_sel)] if competicao_sel else df_base.copy()

    with c2:
        jogo_sel = st.selectbox("📅 Selecione o Jogo:", df_f1['Data_Display'].unique())
        df_jogo = df_f1[df_f1['Data_Display'] == jogo_sel]

    # Lista de atletas disponíveis no jogo
    atletas_jogo = sorted(df_jogo['Name'].unique())

    with c3:
        atleta_1 = st.selectbox("🔴 Atleta 1 (Referência):", atletas_jogo, index=0)
        
    with c4:
        # Garante que o atleta 2 seja diferente por padrão, se possível
        index_a2 = 1 if len(atletas_jogo) > 1 else 0
        atleta_2 = st.selectbox("🔵 Atleta 2 (Desafiante):", atletas_jogo, index=index_a2)

st.markdown("---")

if atleta_1 == atleta_2:
    st.warning("⚠️ Selecione dois atletas diferentes para a comparação.")
    st.stop()

# ==========================================
# 3. PREPARAÇÃO DOS DADOS (AGRUPAMENTO DO JOGO)
# ==========================================
# Precisamos somar as métricas de volume para o jogo inteiro
cols_volume = ['Total Distance', 'V4 Dist', 'Player Load']
# Adicionando HIA e suas quebras (com segurança caso faltem colunas)
cols_hia = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Acc4 Eff', 'Dec4 Eff']
cols_existentes = [c for c in cols_volume + cols_hia if c in df_jogo.columns]

# Cria a coluna HIA Total se as colunas existirem
df_jogo['HIA_Total'] = df_jogo[[c for c in cols_hia if c in df_jogo.columns]].sum(axis=1)
if 'HIA_Total' not in cols_existentes:
    cols_existentes.append('HIA_Total')

# Agrupa tudo por Atleta somando o jogo todo
df_agrupado = df_jogo.groupby('Name')[cols_existentes].sum().reset_index()

# Calcula os Minutos Jogados (Max Interval) por atleta
minutos_jogados = df_jogo.groupby('Name')['Interval'].max().reset_index()
df_agrupado = pd.merge(df_agrupado, minutos_jogados, on='Name')
df_agrupado.rename(columns={'Interval': 'Minutos Jogados'}, inplace=True)

# Extrai os dados dos dois lutadores
df_a1 = df_agrupado[df_agrupado['Name'] == atleta_1].iloc[0] if not df_agrupado[df_agrupado['Name'] == atleta_1].empty else None
df_a2 = df_agrupado[df_agrupado['Name'] == atleta_2].iloc[0] if not df_agrupado[df_agrupado['Name'] == atleta_2].empty else None

if df_a1 is None or df_a2 is None:
    st.error("Dados insuficientes para um dos atletas neste jogo.")
    st.stop()

# ==========================================
# 4. PAINEL DE KPIs: O DUELO (CARDS LADO A LADO)
# ==========================================
st.subheader("📊 Resumo do Confronto (Jogo Completo)")

c1, c2, c3 = st.columns([1, 0.2, 1])
c1.markdown(f"<h4 style='text-align: right; color: #EF5350; margin-bottom: 0;'>🔴 {atleta_1}</h4><p style='text-align: right; margin-top: 0;'>{df_a1['Minutos Jogados']:.0f} min</p>", unsafe_allow_html=True)
c2.markdown(f"<h3 style='text-align: center; color: #bdbdbd;'>VS</h3>", unsafe_allow_html=True)
c3.markdown(f"<h4 style='text-align: left; color: #42A5F5; margin-bottom: 0;'>🔵 {atleta_2}</h4><p style='text-align: left; margin-top: 0;'>{df_a2['Minutos Jogados']:.0f} min</p>", unsafe_allow_html=True)

# Cria 4 colunas para os KPIs ficarem perfeitamente alinhados na horizontal
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

def kpi_card(col, label, val1, val2, unidade=""):
    cor1 = "#2E7D32" if val1 > val2 else "#C62828" if val1 < val2 else "gray" # Verde ganha, Vermelho perde
    cor2 = "#2E7D32" if val2 > val1 else "#C62828" if val2 < val1 else "gray"
    
    with col:
        st.markdown(f"""
        <div style='background-color: #f8f9fa; padding: 15px; border-radius: 10px; text-align: center; border: 1px solid #e0e0e0; box-shadow: 2px 2px 5px rgba(0,0,0,0.05);'>
            <p style='color: #757575; margin-bottom: 8px; font-size: 14px; font-weight: bold;'>{label}</p>
            <h4 style='margin-top: 0; font-size: 18px;'>
                <span style='color: {cor1};'>{val1:.1f}{unidade}</span> 
                <span style='color: #bdbdbd; font-size: 14px; margin: 0 5px;'>x</span> 
                <span style='color: {cor2};'>{val2:.1f}{unidade}</span>
            </h4>
        </div>
        """, unsafe_allow_html=True)

kpi_card(col_kpi1, "Distância Total", df_a1.get('Total Distance', 0), df_a2.get('Total Distance', 0), "m")
kpi_card(col_kpi2, "Alta Intensidade (HIA)", df_a1.get('HIA_Total', 0), df_a2.get('HIA_Total', 0), "")
kpi_card(col_kpi3, "Alta Velocidade (V4)", df_a1.get('V4 Dist', 0), df_a2.get('V4 Dist', 0), "m")
kpi_card(col_kpi4, "Player Load", df_a1.get('Player Load', 0), df_a2.get('Player Load', 0), "")

# ==========================================
# 5. RADAR E GRÁFICOS DE LINHA (EM ABAS)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True) # Espaço visual
col_radar, col_timeline = st.columns([1, 1.4])

with col_radar:
    st.subheader("🕸️ Perfil Fisiológico")
    
    # Radar Chart
    metricas_radar = ['Total Distance', 'V4 Dist', 'HIA_Total', 'Player Load']
    metricas_radar = [m for m in metricas_radar if m in df_agrupado.columns]
    
    maximos_time = df_agrupado[metricas_radar].max()
    val1_norm = (df_a1[metricas_radar] / maximos_time * 100).fillna(0).tolist()
    val2_norm = (df_a2[metricas_radar] / maximos_time * 100).fillna(0).tolist()
    
    val1_norm += [val1_norm[0]]
    val2_norm += [val2_norm[0]]
    categorias = metricas_radar + [metricas_radar[0]]
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(r=val1_norm, theta=categorias, fill='toself', name=atleta_1, line_color='#EF5350', fillcolor='rgba(239, 83, 80, 0.4)'))
    fig_radar.add_trace(go.Scatterpolar(r=val2_norm, theta=categorias, fill='toself', name=atleta_2, line_color='#42A5F5', fillcolor='rgba(66, 165, 245, 0.4)'))

    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")),
        showlegend=True, template='plotly_white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        height=450, margin=dict(t=30, b=40, l=40, r=40)
    )
    st.plotly_chart(fig_radar, use_container_width=True)

with col_timeline:
    st.subheader("📈 Corrida de Ritmo (Timeline)")
    
    # --- Preparação de Dados para as Linhas Acumuladas ---
    df_min_a1 = df_jogo[df_jogo['Name'] == atleta_1].sort_values('Interval').copy()
    df_min_a2 = df_jogo[df_jogo['Name'] == atleta_2].sort_values('Interval').copy()
    
    # V4 Acumulada
    df_min_a1['V4_Acum'] = df_min_a1.get('V4 Dist', pd.Series(0)).cumsum()
    df_min_a2['V4_Acum'] = df_min_a2.get('V4 Dist', pd.Series(0)).cumsum()
    
    # Sprints Acumulados (V5) - Busca 'V5 Dist', se não achar, usa 'V5 To8 Eff'
    col_sprint = 'V5 Dist' if 'V5 Dist' in df_jogo.columns else 'V5 To8 Eff'
    df_min_a1['V5_Acum'] = df_min_a1.get(col_sprint, pd.Series(0)).cumsum()
    df_min_a2['V5_Acum'] = df_min_a2.get(col_sprint, pd.Series(0)).cumsum()
    
    # Força (Acc3 + Dec3) Acumulada
    df_min_a1['AccDec'] = df_min_a1.get('Acc3 Eff', pd.Series(0)) + df_min_a1.get('Dec3 Eff', pd.Series(0))
    df_min_a2['AccDec'] = df_min_a2.get('Acc3 Eff', pd.Series(0)) + df_min_a2.get('Dec3 Eff', pd.Series(0))
    df_min_a1['AccDec_Acum'] = df_min_a1['AccDec'].cumsum()
    df_min_a2['AccDec_Acum'] = df_min_a2['AccDec'].cumsum()

    # --- Criação das Abas (Tabs) ---
    tab1, tab2, tab3 = st.tabs(["⚡ V4 Acumulada", "🚀 Sprints (V5)", "🛑 Força (Acc3 + Dec3)"])
    
    def desenhar_grafico_linha(df1, df2, coluna_y, titulo_y):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df1['Interval'], y=df1[coluna_y], mode='lines', name=atleta_1, line=dict(color='#EF5350', width=3)))
        fig.add_trace(go.Scatter(x=df2['Interval'], y=df2[coluna_y], mode='lines', name=atleta_2, line=dict(color='#42A5F5', width=3)))
        fig.update_layout(
            template='plotly_white', height=380,
            xaxis_title="Minuto de Jogo", yaxis_title=titulo_y,
            hovermode="x unified", margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        return fig

    with tab1:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'V4_Acum', 'Volume de V4 (m)'), use_container_width=True)
        
    with tab2:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'V5_Acum', f'Volume de Sprint ({col_sprint})'), use_container_width=True)
        
    with tab3:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'AccDec_Acum', 'Ações de Acc/Dec'), use_container_width=True)
