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
    # 5 colunas em uma única linha. O Jogo (c2) recebe um pouco mais de espaço porque o nome é maior.
    c1, c2, c3, c4, c5 = st.columns([1.3, 1.6, 1.1, 1.2, 1.2])
    
    with c1:
        competicao_sel = st.multiselect("🏆 Competição:", options=df_base['Competição'].unique().tolist() if 'Competição' in df_base.columns else [])
        df_f1 = df_base[df_base['Competição'].isin(competicao_sel)] if competicao_sel else df_base.copy()

    with c2:
        jogo_sel = st.selectbox("📅 Selecione o Jogo:", df_f1['Data_Display'].unique())
        df_jogo_full = df_f1[df_f1['Data_Display'] == jogo_sel]
        
    with c3:
        # Alterado de st.radio para st.selectbox para economizar espaço horizontal
        periodo_sel = st.radio("⏱️ Período:", ["1º Tempo", "2º Tempo"], horizontal = True)

    # Lista de atletas disponíveis no jogo
    atletas_jogo = sorted(df_jogo_full['Name'].unique())

    with c4:
        atleta_1 = st.selectbox("🔴 Atleta 1 (Referência):", atletas_jogo, index=0)
        
    with c5:
        index_a2 = 1 if len(atletas_jogo) > 1 else 0
        atleta_2 = st.selectbox("🔵 Atleta 2 (Desafiante):", atletas_jogo, index=index_a2)

st.markdown("---")

if atleta_1 == atleta_2:
    st.warning("⚠️ Selecione dois atletas diferentes para a comparação.")
    st.stop()

# Aplicação do Filtro de Período
if periodo_sel == "1º Tempo":
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
# Precisamos somar as métricas de volume para o jogo inteiro
# Adicionado 'V5 Dist' para pegar a distância em Sprint
cols_volume = ['Total Distance', 'V4 Dist', 'V5 Dist', 'Player Load']
# Adicionando HIA e suas quebras (com segurança caso faltem colunas)
cols_hia = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Acc4 Eff', 'Dec4 Eff']
cols_existentes = [c for c in cols_volume + cols_hia if c in df_jogo.columns]

# Cria a coluna HIA Total se as colunas existirem
df_jogo['HIA_Total'] = df_jogo[[c for c in cols_hia if c in df_jogo.columns]].sum(axis=1)
if 'HIA_Total' not in cols_existentes:
    cols_existentes.append('HIA_Total')

# Agrupa tudo por Atleta somando o jogo todo
df_agrupado = df_jogo.groupby('Name')[cols_existentes].sum().reset_index()

# NOVA MÉTRICA: Soma de Acelerações e Desacelerações (Acc3 + Dec3)
df_agrupado['AccDec_Total'] = df_agrupado.get('Acc3 Eff', 0) + df_agrupado.get('Dec3 Eff', 0)

# Calcula os Minutos Jogados (Max Interval) por atleta
minutos_jogados = df_jogo.groupby('Name')['Interval'].nunique().reset_index()
df_agrupado = pd.merge(df_agrupado, minutos_jogados, on='Name')
df_agrupado.rename(columns={'Interval': 'Minutos Jogados'}, inplace=True)

# Extrai os dados dos dois lutadores
df_a1 = df_agrupado[df_agrupado['Name'] == atleta_1].iloc[0] if not df_agrupado[df_agrupado['Name'] == atleta_1].empty else None
df_a2 = df_agrupado[df_agrupado['Name'] == atleta_2].iloc[0] if not df_agrupado[df_agrupado['Name'] == atleta_2].empty else None

if df_a1 is None or df_a2 is None:
    st.error("Dados insuficientes para um dos atletas neste jogo.")
    st.stop()

# ==========================================
# 4. PAINEL DE KPIs: O DUELO (6 CARDS LADO A LADO)
# ==========================================
st.subheader("📊 Resumo do Confronto (Jogo Completo)")

c1, c2, c3 = st.columns([1, 0.2, 1])
c1.markdown(f"<h4 style='text-align: right; color: #EF5350; margin-bottom: 0;'>🔴 {atleta_1}</h4><p style='text-align: right; margin-top: 0;'>{df_a1['Minutos Jogados']:.0f} min</p>", unsafe_allow_html=True)
c2.markdown(f"<h3 style='text-align: center; color: var(--text-color); opacity: 0.7;'>VS</h3>", unsafe_allow_html=True)
c3.markdown(f"<h4 style='text-align: left; color: #42A5F5; margin-bottom: 0;'>🔵 {atleta_2}</h4><p style='text-align: left; margin-top: 0;'>{df_a2['Minutos Jogados']:.0f} min</p>", unsafe_allow_html=True)

# Agora com 6 colunas para acomodar a métrica de Sprint (V5)
col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5, col_kpi6 = st.columns(6)

def kpi_card(col, label, val1, val2, unidade=""):
    # Cores vivas para brilharem no Dark Mode
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
# Novo Card: Sprint V5
kpi_card(col_kpi4, "Distância em Sprints", df_a1.get('V5 Dist', 0), df_a2.get('V5 Dist', 0), "m")
kpi_card(col_kpi5, "Acc + Dec", df_a1.get('AccDec_Total', 0), df_a2.get('AccDec_Total', 0), "")
kpi_card(col_kpi6, "Player Load", df_a1.get('Player Load', 0), df_a2.get('Player Load', 0), "")

# ==========================================
# 5. RADAR E GRÁFICOS DE LINHA (EM ABAS)
# ==========================================
st.markdown("<br>", unsafe_allow_html=True) # Espaço visual
col_radar, col_timeline = st.columns([1, 1.4])

with col_radar:
    st.subheader("🕸️ Perfil Fisiológico")
    
    # Radar Chart - Adicionando V5 Dist e garantindo fallback caso a coluna se chame diferente
    metricas_radar = ['Total Distance', 'V4 Dist', 'V5 Dist', 'HIA_Total', 'AccDec_Total', 'Player Load']
    # Mantém apenas as que realmente existem no df
    metricas_radar = [m for m in metricas_radar if m in df_agrupado.columns]
    
    # Dicionário para deixar os nomes bonitos no gráfico
    nomes_bonitos = {
        'Total Distance': 'Distância',
        'V4 Dist': 'Distância V4',
        'V5 Dist': 'Distância V5',
        'HIA_Total': 'HIA Total',
        'AccDec_Total': 'Acc/Dec',
        'Player Load': 'Player Load'
    }
    
    maximos_time = df_agrupado[metricas_radar].max()
    
    # Prevenção contra divisão por zero se o máximo do time for 0
    maximos_time = maximos_time.replace(0, 1) 

    val1_norm = (df_a1[metricas_radar] / maximos_time * 100).fillna(0).tolist()
    val2_norm = (df_a2[metricas_radar] / maximos_time * 100).fillna(0).tolist()
    
    # 1. EXTRAIR OS VALORES REAIS ORIGINAIS (BÓNUS PARA MOSTRAR NO BALÃO)
    val1_orig = df_a1[metricas_radar].fillna(0).tolist()
    val2_orig = df_a2[metricas_radar].fillna(0).tolist()
    
    # Fechar o círculo do radar para a linha conectar o fim ao início
    val1_norm += [val1_norm[0]]
    val2_norm += [val2_norm[0]]
    val1_orig += [val1_orig[0]]  # Fechar também os valores reais
    val2_orig += [val2_orig[0]]  
    
    # Aplicar os nomes curtos e bonitos no eixo do radar
    categorias_labels = [nomes_bonitos.get(m, m) for m in metricas_radar]
    categorias_labels += [categorias_labels[0]]
    
    fig_radar = go.Figure()
    
    # Atleta 1
    fig_radar.add_trace(go.Scatterpolar(
        r=val1_norm, 
        theta=categorias_labels, 
        fill='toself', 
        name=atleta_1, 
        line_color='#EF5350', 
        fillcolor='rgba(239, 83, 80, 0.4)',
        mode='lines+markers',           # <-- Adiciona os pequenos pontos na ponta
        hoveron='points',               # <-- O Segredo: O rato passa a ignorar as sobreposições de preenchimento!
        customdata=val1_orig,           # <-- Passamos o valor absoluto
        hovertemplate='<b>%{theta}</b><br>Valor Real: %{customdata:.0f}<br>Escala (%): %{r:.1f}%<extra></extra>'
    ))
    
    # Atleta 2
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
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], ticksuffix="%")),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        height=450, margin=dict(t=30, b=40, l=40, r=40)
    )
    st.plotly_chart(fig_radar, use_container_width=True)

with col_timeline:
    st.subheader("📈 Corrida de Ritmo (Timeline)")
    
    # --- Preparação de Dados para as Linhas Acumuladas ---
    df_min_a1 = df_jogo[df_jogo['Name'] == atleta_1].sort_values('Interval').copy()
    df_min_a2 = df_jogo[df_jogo['Name'] == atleta_2].sort_values('Interval').copy()
    
    # NOVA: Distância Total Acumulada
    df_min_a1['Total_Dist_Acum'] = df_min_a1.get('Total Distance', pd.Series(0)).cumsum()
    df_min_a2['Total_Dist_Acum'] = df_min_a2.get('Total Distance', pd.Series(0)).cumsum()
    
    # V4 Acumulada
    df_min_a1['V4_Acum'] = df_min_a1.get('V4 Dist', pd.Series(0)).cumsum()
    df_min_a2['V4_Acum'] = df_min_a2.get('V4 Dist', pd.Series(0)).cumsum()
    
    # Sprints Acumulados (V5)
    col_sprint = 'V5 Dist' if 'V5 Dist' in df_jogo.columns else 'V5 To8 Eff'
    df_min_a1['V5_Acum'] = df_min_a1.get(col_sprint, pd.Series(0)).cumsum()
    df_min_a2['V5_Acum'] = df_min_a2.get(col_sprint, pd.Series(0)).cumsum()
    
    # Força (Acc3 + Dec3) Acumulada
    df_min_a1['AccDec'] = df_min_a1.get('Acc3 Eff', pd.Series(0)) + df_min_a1.get('Dec3 Eff', pd.Series(0))
    df_min_a2['AccDec'] = df_min_a2.get('Acc3 Eff', pd.Series(0)) + df_min_a2.get('Dec3 Eff', pd.Series(0))
    df_min_a1['AccDec_Acum'] = df_min_a1['AccDec'].cumsum()
    df_min_a2['AccDec_Acum'] = df_min_a2['AccDec'].cumsum()

    # --- Criação das Abas (Tabs) - Adicionado "📏 Distância Total" ---
    tab0, tab1, tab2, tab3 = st.tabs(["📏 Distância Total", "⚡ V4 Acumulada", "🚀 Sprints (V5)", "🛑 Força (Acc3 + Dec3)"])
    
    def desenhar_grafico_linha(df1, df2, coluna_y, titulo_y):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df1['Interval'], y=df1[coluna_y], mode='lines', name=atleta_1, line=dict(color='#EF5350', width=3)))
        fig.add_trace(go.Scatter(x=df2['Interval'], y=df2[coluna_y], mode='lines', name=atleta_2, line=dict(color='#42A5F5', width=3)))
        fig.update_layout(
            height=380,
            xaxis_title="Minuto de Jogo", yaxis_title=titulo_y,
            hovermode="x unified", margin=dict(t=10, b=10, l=10, r=10),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        return fig

    # Renderização de cada aba (COM A KEY ADICIONADA PARA EVITAR ERROS)
    with tab0:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'Total_Dist_Acum', 'Distância Total Acumulada (m)'), use_container_width=True, key="grafico_tab0")
        
    with tab1:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'V4_Acum', 'Volume de V4 (m)'), use_container_width=True, key="grafico_tab1")
        
    with tab2:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'V5_Acum', 'Volume de Sprint'), use_container_width=True, key="grafico_tab2")
        
    with tab3:
        st.plotly_chart(desenhar_grafico_linha(df_min_a1, df_min_a2, 'AccDec_Acum', 'Ações de Acc/Dec'), use_container_width=True, key="grafico_tab3")
