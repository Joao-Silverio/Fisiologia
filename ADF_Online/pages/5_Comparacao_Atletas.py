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
# 4. PAINEL DE KPIs: O DUELO
# ==========================================
st.subheader("📊 Resumo do Confronto (Jogo Completo)")

def kpi_duelo(label, val1, val2, unidade=""):
    # Função para destacar quem ganhou a métrica
    cor1 = "green" if val1 > val2 else "red" if val1 < val2 else "gray"
    cor2 = "green" if val2 > val1 else "red" if val2 < val1 else "gray"
    
    col_a, col_b, col_c = st.columns([1, 2, 1])
    with col_b:
        st.markdown(f"<p style='text-align: center; color: gray; margin-bottom: 0;'>{label}</p>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align: center; margin-top: 0;'><span style='color: {cor1};'>{val1:.1f}{unidade}</span> <span style='color: white;'>x</span> <span style='color: {cor2};'>{val2:.1f}{unidade}</span></h3>", unsafe_allow_html=True)

# Minutos não competem, só informam
c1, c2, c3 = st.columns(3)
c1.markdown(f"<h4 style='text-align: center; color: #EF5350;'>🔴 {atleta_1}</h4><p style='text-align: center;'>{df_a1['Minutos Jogados']:.0f} min jogados</p>", unsafe_allow_html=True)
c2.markdown(f"<h4 style='text-align: center; color: gray;'>VS</h4>", unsafe_allow_html=True)
c3.markdown(f"<h4 style='text-align: center; color: #42A5F5;'>🔵 {atleta_2}</h4><p style='text-align: center;'>{df_a2['Minutos Jogados']:.0f} min jogados</p>", unsafe_allow_html=True)

st.markdown("---")

kpi_duelo("Distância Total", df_a1.get('Total Distance', 0), df_a2.get('Total Distance', 0), "m")
kpi_duelo("Ações de Alta Intensidade (HIA)", df_a1.get('HIA_Total', 0), df_a2.get('HIA_Total', 0), "")
kpi_duelo("Distância em Alta Velocidade (V4)", df_a1.get('V4 Dist', 0), df_a2.get('V4 Dist', 0), "m")
kpi_duelo("Desgaste Sistêmico (Player Load)", df_a1.get('Player Load', 0), df_a2.get('Player Load', 0), "")

# ==========================================
# 5. GRÁFICO DE RADAR (IMPRESSÃO DIGITAL ATLÉTICA)
# ==========================================
st.markdown("---")
col_radar, col_timeline = st.columns([1, 1.2])

with col_radar:
    st.subheader("🕸️ Perfil Fisiológico (Radar)")
    
    # Selecionamos métricas chaves para a "Impressão Digital"
    metricas_radar = ['Total Distance', 'V4 Dist', 'HIA_Total', 'Player Load']
    metricas_radar = [m for m in metricas_radar if m in df_agrupado.columns]
    
    # NORMALIZAÇÃO: Descobre o máximo que ALGUÉM fez no time neste jogo para criar a escala 100%
    maximos_time = df_agrupado[metricas_radar].max()
    
    # Calcula a % que cada um fez do máximo do time
    val1_norm = (df_a1[metricas_radar] / maximos_time * 100).fillna(0).tolist()
    val2_norm = (df_a2[metricas_radar] / maximos_time * 100).fillna(0).tolist()
    
    # Fechar o círculo do radar repetindo o primeiro valor no final
    val1_norm += [val1_norm[0]]
    val2_norm += [val2_norm[0]]
    categorias = metricas_radar + [metricas_radar[0]]
    
    fig_radar = go.Figure()

    fig_radar.add_trace(go.Scatterpolar(
        r=val1_norm, theta=categorias, fill='toself', name=atleta_1,
        line_color='#EF5350', fillcolor='rgba(239, 83, 80, 0.4)'
    ))
    
    fig_radar.add_trace(go.Scatterpolar(
        r=val2_norm, theta=categorias, fill='toself', name=atleta_2,
        line_color='#42A5F5', fillcolor='rgba(66, 165, 245, 0.4)'
    ))

    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")
        ),
        showlegend=True,
        template='plotly_white',
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        height=450, margin=dict(t=40, b=40, l=40, r=40)
    )
    
    st.plotly_chart(fig_radar, use_container_width=True)
    st.info("💡 **Como ler o Radar:** A borda externa (100%) representa o atleta da equipe que mais pontuou naquela métrica neste jogo. Quanto mais cheia a teia, mais dominante o atleta foi no contexto do elenco.")

# ==========================================
# 6. TIMELINE COMPARATIVA (ACUMULADO)
# ==========================================
with col_timeline:
    st.subheader("📈 Corrida de Ritmo: V4 Acumulada")
    
    # Filtramos minuto a minuto apenas para os dois
    df_min_a1 = df_jogo[df_jogo['Name'] == atleta_1].sort_values('Interval')
    df_min_a2 = df_jogo[df_jogo['Name'] == atleta_2].sort_values('Interval')
    
    # Calculamos a soma acumulada
    df_min_a1['V4_Acumulada'] = df_min_a1.get('V4 Dist', pd.Series(0)).cumsum()
    df_min_a2['V4_Acumulada'] = df_min_a2.get('V4 Dist', pd.Series(0)).cumsum()
    
    fig_line = go.Figure()
    
    fig_line.add_trace(go.Scatter(
        x=df_min_a1['Interval'], y=df_min_a1['V4_Acumulada'],
        mode='lines', name=atleta_1, line=dict(color='#EF5350', width=3)
    ))
    
    fig_line.add_trace(go.Scatter(
        x=df_min_a2['Interval'], y=df_min_a2['V4_Acumulada'],
        mode='lines', name=atleta_2, line=dict(color='#42A5F5', width=3)
    ))
    
    fig_line.update_layout(
        template='plotly_white',
        height=450,
        xaxis_title="Minuto de Jogo",
        yaxis_title="V4 Distância Acumulada (m)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
