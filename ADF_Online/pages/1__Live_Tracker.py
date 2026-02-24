import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import os
import warnings
from streamlit_autorefresh import st_autorefresh
from ml_engine import executar_ml_ao_vivo

st.set_page_config(page_title="Live Tracker Físico", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

contador = st_autorefresh(interval=60000, limit=1000, key="live_tracker_refresh")

st.title('⚽ Live Tracker: Projeção de Carga Física')
st.caption(f"Última atualização automática: Ciclo {contador}")

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# =====================================================================
# RECUPERANDO DADOS GLOBAIS (Sem redundância de carregamento!)
# =====================================================================
if 'df_global' not in st.session_state:
    st.warning("⚠️ Carregue os dados na página principal (Home) primeiro.")
    st.stop()

# Pega os dados já limpos e calculados pela Home
df_completo = st.session_state['df_global'].copy()
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

coluna_jogo = 'Data'
coluna_minuto = 'Interval'

# DAQUI PARA BAIXO, PODE MANTER O SEU CÓDIGO A PARTIR DE:
# st.markdown("### 🔍 Filtros de Análise")

# =====================================================================
# 3. FILTROS NA TELA PRINCIPAL (COM FILTRO GLOBAL MULTIPLO)
# =====================================================================
st.markdown("### 🔍 Filtros de Análise")

with st.container():
    
    # --- O NOVO FILTRO GLOBAL MÚLTIPLO ---
    lista_campeonatos = sorted(df_completo['Competição'].dropna().unique().tolist())
    
    campeonatos_selecionados = st.multiselect(
        "🏆 Campeonatos (Deixe vazio para incluir TODOS):", 
        options=lista_campeonatos,
        default=[] # Começa vazio (mostrando a base inteira)
    )
    
    # A Lógica do "Vazio = Todos"
    if not campeonatos_selecionados: 
        df_base = df_completo.copy()
    else:
        df_base = df_completo[df_completo['Competição'].isin(campeonatos_selecionados)].copy()

    # Linha 1: 4 Colunas para deixar todos os controles lado a lado
    col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.5, 1.5])
    
    with col1:
        modo_filtro = st.radio("Prioridade:", ("Focar no Atleta", "Focar no Jogo"), horizontal=True)
        
    with col3:
        metrica_selecionada = st.pills("Métrica:", ["Total Distance", "V4 Dist", "V5 Dist", "HIA", "V4 Eff", "V5 Eff"], default="V4 Dist")
        if not metrica_selecionada:
            metrica_selecionada = "V4 Dist"
            
    with col4:
        ordem_graficos = st.radio("Ordem na Tela:", ("1º Tempo no Topo", "2º Tempo no Topo"), horizontal=True)

    # A lógica usando df_base (Garante que só apareçam jogadores e jogos DESTE(S) campeonato(s))
    if modo_filtro == "Focar no Atleta":
        lista_atletas = df_base['Name'].dropna().unique()
        atletas_ordenados = sorted(lista_atletas)
        
        atleta_selecionado = st.pills("Selecione o Atleta:", atletas_ordenados, default=atletas_ordenados[0] if len(atletas_ordenados)>0 else None)
        if not atleta_selecionado and len(atletas_ordenados) > 0:
            atleta_selecionado = atletas_ordenados[0]
        
        df_filtrado = df_base[df_base['Name'] == atleta_selecionado]
        jogos_unicos = df_filtrado.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)
        lista_jogos_display = jogos_unicos['Data_Display'].tolist()
        
        with col2:
            jogo_selecionado_display = st.selectbox("Selecione o Jogo:", lista_jogos_display)
        
    else:
        jogos_unicos = df_base.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)
        lista_jogos_display = jogos_unicos['Data_Display'].tolist()
        
        with col2:
            jogo_selecionado_display = st.selectbox("Selecione o Jogo:", lista_jogos_display)
        
        df_filtrado = df_base[df_base['Data_Display'] == jogo_selecionado_display]
        lista_atletas = df_filtrado['Name'].dropna().unique()
        atletas_ordenados = sorted(lista_atletas)
        
        atleta_selecionado = st.pills("Selecione o Atleta:", atletas_ordenados, default=atletas_ordenados[0] if len(atletas_ordenados)>0 else None)
        if not atleta_selecionado and len(atletas_ordenados) > 0:
            atleta_selecionado = atletas_ordenados[0]

    # Recupera a data original escondida (Com trava de segurança)
    if jogo_selecionado_display:
        jogo_selecionado = df_base[df_base['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]
    else:
        st.warning("Nenhum dado encontrado para o(s) campeonato(s) selecionado(s).")
        st.stop()
    
    # Define as colunas conforme a métrica selecionada
    if metrica_selecionada == "Total Distance":
        coluna_distancia = 'Total Distance'
        coluna_acumulada = 'Dist Acumulada'
        titulo_grafico = f'Projeção de Distância Total - {atleta_selecionado}'
    elif metrica_selecionada == "V4 Dist":
        coluna_distancia = 'V4 Dist'
        coluna_acumulada = 'V4 Dist Acumulada'
        titulo_grafico = f'Projeção de V4 Dist - {atleta_selecionado}'
    elif metrica_selecionada == "V5 Dist":
        coluna_distancia = 'V5 Dist'
        coluna_acumulada = 'V5 Dist Acumulada'
        titulo_grafico = f'Projeção de Sprints (V5 Dist) - {atleta_selecionado}'
    elif metrica_selecionada == "V4 Eff":
        coluna_distancia = 'V4 To8 Eff'
        coluna_acumulada = 'V4 Eff Acumulada'
        titulo_grafico = f'Projeção de Ações V4+ - {atleta_selecionado}'
    elif metrica_selecionada == "V5 Eff":
        coluna_distancia = 'V5 To8 Eff'
        coluna_acumulada = 'V5 Eff Acumulada'
        titulo_grafico = f'Projeção de Ações V5+ (Sprints) - {atleta_selecionado}'
    else:
        coluna_distancia = 'HIA'
        coluna_acumulada = 'HIA Acumulada'
        titulo_grafico = f'Projeção de HIA - {atleta_selecionado}'
    
    # Filtra o dataframe base para o atleta escolhido usando o DF protegido!
    df_atleta = df_base[df_base['Name'] == atleta_selecionado].copy()

# =====================================================================
# 4. MOTOR DE GERAÇÃO DOS GRÁFICOS E ML (1º e 2º TEMPO)
# =====================================================================
# Define a ordem dos gráficos dinamicamente com base no filtro
periodos_para_analise = [1, 2] if ordem_graficos == "1º Tempo no Topo" else [2, 1]

for periodo in periodos_para_analise:
    
    st.markdown(f"### ⏱️ Análise Fisiológica - {periodo}º Tempo")

    # Filtra o dataframe SÓ para o tempo que está sendo desenhado agora
    df_periodo = df_atleta[df_atleta['Período'] == periodo].copy()

   # Calcular o Acumulado (Garante que cada tempo comece do zero)
    df_periodo = df_periodo.sort_values(by=[coluna_jogo, coluna_minuto])
    df_periodo['Dist Acumulada'] = df_periodo.groupby(coluna_jogo)['Total Distance'].cumsum()
    df_periodo['V4 Dist Acumulada'] = df_periodo.groupby(coluna_jogo)['V4 Dist'].cumsum()
    
    # ---> NOVAS MÉTRICAS ACUMULADAS <---
    if 'V5 Dist' in df_periodo.columns:
        df_periodo['V5 Dist Acumulada'] = df_periodo.groupby(coluna_jogo)['V5 Dist'].cumsum()
    if 'V4 To8 Eff' in df_periodo.columns:
        df_periodo['V4 Eff Acumulada'] = df_periodo.groupby(coluna_jogo)['V4 To8 Eff'].cumsum()
    if 'V5 To8 Eff' in df_periodo.columns:
        df_periodo['V5 Eff Acumulada'] = df_periodo.groupby(coluna_jogo)['V5 To8 Eff'].cumsum()
        
    if 'HIA' in df_periodo.columns:
        df_periodo['HIA Acumulada'] = df_periodo.groupby(coluna_jogo)['HIA'].cumsum()
        
    if 'Player Load' in df_periodo.columns:
        df_periodo['Player Load Acumulada'] = df_periodo.groupby(coluna_jogo)['Player Load'].cumsum()

    df = df_periodo.dropna(subset=[coluna_minuto, coluna_acumulada]).copy()

    if not df.empty:
        max_minutos_por_jogo = df.groupby(coluna_jogo)[coluna_minuto].max()
        jogo_atual_nome = jogo_selecionado
        
        # Se o jogador não atuou neste tempo no jogo selecionado, avisa e pula pro próximo
        if jogo_atual_nome not in max_minutos_por_jogo.index:
            st.warning(f"O atleta selecionado não atuou no {periodo}º Tempo deste jogo.")
            continue
            
        minuto_atual_max = int(max_minutos_por_jogo[jogo_atual_nome])
        minuto_final_partida = int(max_minutos_por_jogo.max())
        
        # Slider independente por gráfico
        minuto_projecao_ate = st.slider(
            f"Projetar o {periodo}º Tempo até o minuto:",
            min_value=minuto_atual_max,
            max_value=max(minuto_final_partida, minuto_atual_max + 1),
            value=minuto_final_partida,
            step=1,
            key=f"slider_projecao_{periodo}" 
        ) 

        # Separar os dados
        df_historico = df[df[coluna_jogo] != jogo_atual_nome].copy()
        df_atual = df[df[coluna_jogo] == jogo_atual_nome].sort_values(coluna_minuto)

        # =====================================================================
        # TRAVAS DE SEGURANÇA (Evita o NameError se não houver histórico)
        # =====================================================================
        minutos_futuros = []
        pred_superior = []
        pred_inferior = []
        acumulado_pred = []
        
        carga_atual = df_atual[coluna_acumulada].iloc[-1] if not df_atual.empty else 0
        minuto_atual = df_atual[coluna_minuto].iloc[-1] if not df_atual.empty else 0
        pl_atual_acumulado = df_atual['Player Load Acumulada'].iloc[-1] if 'Player Load Acumulada' in df_atual.columns and not df_atual.empty else 1
        
        # Valores iniciais neutros para os KPIs caso a IA não ligue
        carga_projetada = carga_atual
        minuto_final_proj = minuto_atual
        delta_alvo_pct = 0.0
        delta_pl_pct = 0.0
        delta_projetado_pct = 0.0
        delta_time_pct = 0.0
        delta_atleta_vs_time = 0.0

        if not df_historico.empty and not df_atual.empty:
            
            # Inteligência Artificial Ativada
            col_placar = 'Placar'
            media_min_geral = df_historico.groupby(coluna_minuto)[coluna_distancia].mean()
            
            if col_placar in df_atual.columns and col_placar in df_historico.columns:
                placar_atual = df_atual[col_placar].iloc[-1]
                df_hist_cenario = df_historico[df_historico[col_placar] == placar_atual]
                
                if not df_hist_cenario.empty:
                    media_min_cenario = df_hist_cenario.groupby(coluna_minuto)[coluna_distancia].mean()
                    peso_placar = 0.7 if len(df_hist_cenario[coluna_jogo].unique()) >= 3 else 0.4
                else:
                    media_min_cenario = media_min_geral
                    peso_placar = 0.0
                    placar_atual = "Sem dados prévios"
            else:
                media_min_cenario = media_min_geral
                peso_placar = 0.0
                placar_atual = "Coluna não encontrada"
                
            ml = executar_ml_ao_vivo(
            df_historico, df_atual, df_base,
            coluna_distancia, coluna_acumulada, coluna_minuto, coluna_jogo,
            jogo_atual_nome, periodo, minuto_projecao_ate, metrica_selecionada,
            atleta_selecionado, DIRETORIO_ATUAL
        )

            # Desempacotar os resultados (substitui as variáveis que existiam antes)
            minutos_futuros       = ml['minutos_futuros']
            acumulado_pred        = ml['acumulado_pred']
            pred_superior         = ml['pred_superior']
            pred_inferior         = ml['pred_inferior']
            carga_projetada       = ml['carga_projetada']
            minuto_final_proj     = ml['minuto_final_proj']
            delta_alvo_pct        = ml['delta_alvo_pct']
            delta_pl_pct          = ml['delta_pl_pct']
            delta_projetado_pct   = ml['delta_projetado_pct']
            delta_time_pct        = ml['delta_time_pct']
            delta_atleta_vs_time  = ml['delta_atleta_vs_time']

            st.info(f"🧠 **{ml['modelo_usado']}** | Placar: '{ml['placar_atual']}' | Descanso: {ml['dias_descanso']}d | MetPow: {ml['met_power_atual']:.1f}" if ml['met_power_atual'] else f"🧠 **{ml['modelo_usado']}**")


        else:
            st.warning("Pouco histórico neste campeonato para ativar a IA. Mostrando os dados em tempo real puros.")

        # =====================================================================
        # RENDERIZAÇÃO NA TELA (Roda com ou sem Inteligência Artificial)
        # =====================================================================
        unidade = "" if metrica_selecionada in ["HIA", "V4 Eff", "V5 Eff"] else " m"
        def fmt_dist(x): return f"{x:.0f}{unidade}" if not np.isnan(x) else "N/A"
        def fmt_pct(x): return f"{x:+.1f}%" if not np.isnan(x) else "N/A"

        k0, k1, k2, k3, k4, k5 = st.columns(6)
        cor_delta = "normal" if metrica_selecionada in ["V4 Dist", "HIA", "Total Distance"] else "inverse"
        
        k0.metric("Volume Atual", fmt_dist(carga_atual))
        k1.metric("Desempenho vs Histórico", fmt_pct(delta_alvo_pct), delta=fmt_pct(delta_alvo_pct), delta_color=cor_delta)
        k2.metric("Ritmo vs Média Equipe", fmt_pct(delta_time_pct), delta=f"{fmt_pct(delta_atleta_vs_time)} (Atleta vs Jogo)", delta_color=cor_delta)
        k3.metric(f"Projeção Final (min {minuto_final_proj})", fmt_dist(carga_projetada))
        k4.metric(f"Ritmo Previsto", fmt_pct(delta_projetado_pct), delta=fmt_pct(delta_projetado_pct), delta_color=cor_delta)
        k5.metric(f"Player Load", f"{pl_atual_acumulado:.0f}", delta=fmt_pct(delta_pl_pct), delta_color="inverse")
       
        # Recuperar recorde do atleta
        if 'df_recordes' in st.session_state:
            rec = st.session_state['df_recordes']
            recorde_atleta = rec[rec['Name'] == atleta_selecionado]['Recorde_5min_HIA'].values
            val_recorde = recorde_atleta[0] if len(recorde_atleta) > 0 else 0
            
            # Calcular esforço atual (últimos 5 min)
            esforço_atual_5m = df_atual[coluna_distancia].tail(5).mean()
            percentual_do_limite = (esforço_atual_5m / val_recorde * 100) if val_recorde > 0 else 0
        
            # Adicionar novo Card de KPI
            k6, k7 = st.columns(2) # Ajuste a disposição conforme seu layout
            k6.metric(
                label="Proximidade do Limite (5 min)",
                value=f"{percentual_do_limite:.1f}%",
                delta=f"Recorde: {val_recorde:.1f}",
                help="Compara a intensidade dos últimos 5 minutos com o bloco mais intenso que este atleta já fez na temporada."
            )

        # =====================================================================
        # GRÁFICO PLOTLY MODO CLARO
        # =====================================================================
        fig = go.Figure()
        
        if not df_historico.empty:
            jogos_historicos = df_historico[coluna_jogo].unique()
            colors = px.colors.qualitative.Plotly
            for idx, jogo in enumerate(jogos_historicos):
                df_j = df_historico[df_historico[coluna_jogo] == jogo].sort_values(coluna_minuto)
                jogo_display = df_completo[df_completo['Data'] == jogo]['Data_Display'].iloc[0] if jogo in df_completo['Data'].values else str(jogo)
                fig.add_trace(go.Scatter(
                    x=df_j[coluna_minuto], y=df_j[coluna_acumulada], mode='lines',
                    name=jogo_display, opacity=0.3, # Deixei o histórico mais suave no fundo branco
                    line=dict(color=colors[idx % len(colors)], dash='dot', width=1.5),
                    hovertemplate='Valor: %{y:.1f}<extra></extra>'
                ))

        jogo_display = df_completo[df_completo['Data'] == jogo_atual_nome]['Data_Display'].iloc[0] if jogo_atual_nome in df_completo['Data'].values else str(jogo_atual_nome)
        fig.add_trace(go.Scatter(
            x=df_atual[coluna_minuto], y=df_atual[coluna_acumulada], mode='lines',
            name=f'{jogo_display} (Atual)', line=dict(color='#00E676', width=4), 
            hovertemplate='Atual: %{y:.1f}m<extra></extra>'
        ))

        # Nova trava de segurança para desenhar a área de projeção:
        if len(minutos_futuros) > 0 and len(pred_superior) > 0: 
            fig.add_trace(go.Scatter(x=minutos_futuros, y=pred_superior, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=pred_inferior, mode='lines', line=dict(width=0),
                fill='tonexty', fillcolor='rgba(255, 140, 0, 0.15)', name='Margem de Variação', hoverinfo='skip' # Laranja translúcido
            ))
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=acumulado_pred, mode='lines', name='Projeção com ML',
                line=dict(color='#FF8C00', width=3, dash='dash'), hovertemplate='Projeção: %{y:.1f}m<extra></extra>' # Laranja Escuro/Forte
            ))
            fig.add_vline(x=minuto_atual, line_dash="dash", line_color="gray")
            fig.add_annotation(x=minuto_atual, y=1, text="Agora", showarrow=False, yref="paper", xanchor="left", yanchor="top")

        x_min = 0
        x_max = minuto_projecao_ate + 2  

        fig.update_xaxes(tickmode='linear', dtick=1, range=[x_min, x_max], tickfont=dict(size=10), tickangle=0)

        fig.update_layout(
            title=titulo_grafico + f" - {periodo}º Tempo",
            xaxis_title=f'Minutos de Jogo ({periodo}º Tempo)',
            yaxis_title=metrica_selecionada,
            template='plotly_white', # Fundo limpo e branco
            legend=dict(bgcolor='rgba(0,0,0,0)', orientation="h", yanchor="top", y=-0.35, xanchor="center", x=0.5),
            height=650, hovermode='x unified', margin=dict(l=20, r=20, t=50, b=200)
        )

        st.plotly_chart(fig, use_container_width=True, key=f"grafico_{periodo}")
            
    else:
        st.info(f"Nenhum dado encontrado para o {periodo}º Tempo deste atleta.")
