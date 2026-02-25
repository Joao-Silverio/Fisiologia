import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import os
import warnings
from streamlit_autorefresh import st_autorefresh
from ml_engine import executar_ml_ao_vivo
import config  
from PIL import Image

# 1. Carrega a imagem com segurança
logo = Image.open(config.CAMINHO_LOGO)

# 2. Usa a variável 'logo'
st.set_page_config(page_title="Live Tracker Físico", layout="wide", page_icon=logo)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

contador = st_autorefresh(interval=60000, limit=1000, key="live_tracker_refresh")

col_logo, col_titulo = st.columns([1, 15])

with col_logo:
    st.image(logo, width=100) 

with col_titulo:
    st.title('Live Tracker: Projeção de Carga Física')

st.caption(f"Última atualização automática: Ciclo {contador}")

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# =====================================================================
# RECUPERANDO DADOS GLOBAIS
# =====================================================================
if 'df_global' not in st.session_state:
    st.warning("⚠️ Carregue os dados na página principal (Home) primeiro.")
    st.stop()

df_completo = st.session_state['df_global'].copy()
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

coluna_jogo = 'Data'
coluna_minuto = 'Interval'

# =====================================================================
# 3. FILTROS NA TELA PRINCIPAL
# =====================================================================
st.markdown("### 🔍 Filtros de Análise")

with st.container():
    lista_campeonatos = sorted(df_completo['Competição'].dropna().unique().tolist())
    
    campeonatos_selecionados = st.multiselect(
        "🏆 Campeonatos (Deixe vazio para incluir TODOS):", 
        options=lista_campeonatos,
        default=[]
    )
    
    if not campeonatos_selecionados: 
        df_base = df_completo.copy()
    else:
        df_base = df_completo[df_completo['Competição'].isin(campeonatos_selecionados)].copy()

    col1, col2, col3, col4 = st.columns([1.5, 1.5, 1.5, 1.5])
    
    with col1:
        modo_filtro = st.radio("Prioridade:", ("Focar no Atleta", "Focar no Jogo"), horizontal=True)
        
    with col3:
        opcoes_metricas = list(config.METRICAS_CONFIG.keys())
        metrica_selecionada = st.pills("Métrica:", opcoes_metricas, default="V4 Dist")
        if not metrica_selecionada:
            metrica_selecionada = "V4 Dist"
            
    with col4:
        ordem_graficos = st.radio("Ordem na Tela:", ("1º Tempo no Topo", "2º Tempo no Topo"), horizontal=True)

    # ================= LÓGICA DE FILTRAGEM =================
    jogo_selecionado_display = None
    atleta_selecionado = None

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
            if lista_jogos_display:
                jogo_selecionado_display = st.selectbox("Selecione o Jogo:", lista_jogos_display)
        
    else:
        jogos_unicos = df_base.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)
        lista_jogos_display = jogos_unicos['Data_Display'].tolist()
        
        with col2:
            if lista_jogos_display:
                jogo_selecionado_display = st.selectbox("Selecione o Jogo:", lista_jogos_display)
        
        if jogo_selecionado_display:
            df_filtrado = df_base[df_base['Data_Display'] == jogo_selecionado_display]
            lista_atletas = df_filtrado['Name'].dropna().unique()
            atletas_ordenados = sorted(lista_atletas)
            
            atleta_selecionado = st.pills("Selecione o Atleta:", atletas_ordenados, default=atletas_ordenados[0] if len(atletas_ordenados)>0 else None)
            if not atleta_selecionado and len(atletas_ordenados) > 0:
                atleta_selecionado = atletas_ordenados[0]

    if jogo_selecionado_display:
        jogo_selecionado = df_base[df_base['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]
    else:
        st.warning("Nenhum dado encontrado para o(s) campeonato(s) selecionado(s).")
        st.stop()
    
    cfg = config.METRICAS_CONFIG[metrica_selecionada]
    coluna_distancia = cfg["coluna_distancia"]
    coluna_acumulada = cfg["coluna_acumulada"]
    titulo_grafico = f"{cfg['titulo_grafico']} - {atleta_selecionado}"
    unidade = cfg["unidade"]
    
    df_atleta = df_base[df_base['Name'] == atleta_selecionado].copy()

# =====================================================================
# 4. MOTOR DE GERAÇÃO DOS GRÁFICOS E ML (1º e 2º TEMPO)
# =====================================================================
periodos_para_analise = [1, 2] if ordem_graficos == "1º Tempo no Topo" else [2, 1]

for periodo in periodos_para_analise:
    
    st.markdown(f"### ⏱️ Análise Fisiológica - {periodo}º Tempo")

    df_periodo = df_atleta[df_atleta['Período'] == periodo].copy()
    df_periodo = df_periodo.sort_values(by=[coluna_jogo, coluna_minuto])
    
    # Calcular o Acumulado (Garante que cada tempo comece do zero)
    if 'Total Distance' in df_periodo.columns:
        df_periodo['Dist Acumulada'] = df_periodo.groupby(coluna_jogo)['Total Distance'].cumsum()
    if 'V4 Dist' in df_periodo.columns:
        df_periodo['V4 Dist Acumulada'] = df_periodo.groupby(coluna_jogo)['V4 Dist'].cumsum()
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
        
        if jogo_atual_nome not in max_minutos_por_jogo.index:
            st.warning(f"O atleta selecionado não atuou no {periodo}º Tempo deste jogo.")
            continue
            
        minuto_atual_max = int(max_minutos_por_jogo[jogo_atual_nome])
        minuto_final_partida = int(max_minutos_por_jogo.max())
        
        # --- A NOVA LÓGICA DE SIMULAÇÃO DO "AGORA" (MINUTO DE CORTE) ---
        
        # 1. Chaves únicas para os componentes baseadas no período
        key_slider = f"slider_corte_{periodo}"
        key_num = f"num_corte_{periodo}"

        # 2. Inicializa os valores na memória do sistema (session_state) se for a primeira vez
        if key_slider not in st.session_state:
            st.session_state[key_slider] = minuto_atual_max
        if key_num not in st.session_state:
            st.session_state[key_num] = minuto_atual_max

        # 3. Funções "Callbacks" para sincronizar a barra e a caixinha
        def atualizar_caixinha():
            st.session_state[key_num] = st.session_state[key_slider]
            
        def atualizar_barra():
            st.session_state[key_slider] = st.session_state[key_num]

        # 4. Cria duas colunas: uma larga (80%) para a barra, uma estreita (20%) para a caixinha
        col_barra, col_caixa = st.columns([4, 1])
        
        with col_barra:
            st.slider(
                f"⏱️ Simular o 'Agora' (Minuto de Corte):",
                min_value=1,
                max_value=minuto_atual_max,
                step=1,
                help="Volte no tempo para auditar o ritmo do atleta.",
                key=key_slider,
                on_change=atualizar_caixinha # Avisa a caixinha quando a barra mexer
            )
            
        with col_caixa:
            st.number_input(
                "Minuto Exato:",
                min_value=1,
                max_value=minuto_atual_max,
                step=1,
                key=key_num,
                on_change=atualizar_barra # Avisa a barra quando a caixinha mexer
            )
            
        # 5. O minuto de corte final que vai alimentar a IA
        minuto_corte = st.session_state[key_slider]
        
        # Define automaticamente o final da projeção nos bastidores (45 min ou 50 min)
        minuto_projecao_ate = max(minuto_final_partida, 45 if periodo == 1 else 50)
        
        # Cria um DataFrame simulado ("congelado" no tempo até o minuto de corte) para alimentar a IA
        df_atual_corte = df_atual[df_atual[coluna_minuto] <= minuto_corte].copy()

        minutos_futuros = []
        pred_superior = []
        pred_inferior = []
        acumulado_pred = []
        
        # As métricas numéricas extraem dados a partir do recorte "Simulado", não do fim do jogo
        carga_atual = df_atual_corte[coluna_acumulada].iloc[-1] if not df_atual_corte.empty else 0
        minuto_atual = df_atual_corte[coluna_minuto].iloc[-1] if not df_atual_corte.empty else 0
        pl_atual_acumulado = df_atual_corte['Player Load Acumulada'].iloc[-1] if 'Player Load Acumulada' in df_atual_corte.columns and not df_atual_corte.empty else 1
        
        carga_projetada = carga_atual
        minuto_final_proj = minuto_atual
        delta_alvo_pct = 0.0
        delta_pl_pct = 0.0
        delta_projetado_pct = 0.0
        delta_time_pct = 0.0
        delta_atleta_vs_time = 0.0

        if not df_historico.empty and not df_atual.empty:
            
            col_placar = 'Placar'
            media_min_geral = df_historico.groupby(coluna_minuto)[coluna_distancia].mean()
            
            if col_placar in df_atual_corte.columns and col_placar in df_historico.columns:
                placar_atual = df_atual_corte[col_placar].iloc[-1] if not df_atual_corte.empty else "N/A"
                df_hist_cenario = df_historico[df_historico[col_placar] == placar_atual]
                
                if not df_hist_cenario.empty:
                    media_min_cenario = df_hist_cenario.groupby(coluna_minuto)[coluna_distancia].mean()
                    peso_placar = 0.7 if len(df_hist_cenario[coluna_jogo].unique()) >= 3 else 0.4
                else:
                    media_min_cenario = media_min_geral
                    peso_placar = 0.0
            else:
                media_min_cenario = media_min_geral
                peso_placar = 0.0
                placar_atual = "Coluna não encontrada"
                
            # Aqui passamos o dataframe "congelado" (df_atual_corte) para a IA simular
            ml = executar_ml_ao_vivo(
                df_historico, df_atual_corte, df_base,
                coluna_distancia, coluna_acumulada, coluna_minuto, coluna_jogo,
                jogo_atual_nome, periodo, minuto_projecao_ate, metrica_selecionada,
                atleta_selecionado, DIRETORIO_ATUAL
            )

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

            met_pow = ml.get('met_power_atual')
            placar = ml.get('placar_atual', 'N/A')
            descanso = ml.get('dias_descanso', '-')
            modelo = ml.get('modelo_usado', 'Sem IA')
            
            if met_pow is not None:
                st.info(f"🧠 **{modelo}** | Placar no momento do corte: '{placar}' | Descanso: {descanso}d | MetPow: {met_pow:.1f}")
            else:
                st.info(f"🧠 **{modelo}**")

        else:
            st.warning("Pouco histórico neste campeonato para ativar a IA. Mostrando os dados em tempo real puros.")

        # =====================================================================
        # RENDERIZAÇÃO NA TELA
        # =====================================================================
        def fmt_dist(x): return f"{x:.0f}{unidade}" if not np.isnan(x) else "N/A"
        def fmt_pct(x): return f"{x:+.1f}%" if not np.isnan(x) else "N/A"

        k0, k1, k2, k3, k4, k5, k6 = st.columns(7)
        cor_delta = "normal" if metrica_selecionada in ["V4 Dist", "HIA", "Total Distance"] else "inverse"
        
        k0.metric("Volume no Corte", fmt_dist(carga_atual))
        k1.metric("Ritmo até o Corte vs Histórico", fmt_pct(delta_alvo_pct), delta=fmt_pct(delta_alvo_pct), delta_color=cor_delta)
        k2.metric("Ritmo até o Corte vs Equipe", fmt_pct(delta_time_pct), delta=f"{fmt_pct(delta_atleta_vs_time)} (Atleta vs Jogo)", delta_color=cor_delta)
        k3.metric(f"Projeção Final (min {minuto_final_proj})", fmt_dist(carga_projetada))
        k4.metric(f"Ritmo Projetado", fmt_pct(delta_projetado_pct), delta=fmt_pct(delta_projetado_pct), delta_color=cor_delta)
        k5.metric(f"Player Load no Corte", f"{pl_atual_acumulado:.0f}", delta=fmt_pct(delta_pl_pct), delta_color="inverse")
       
        if 'df_recordes' in st.session_state:
            rec = st.session_state['df_recordes']
            recorde_atleta = rec[rec['Name'] == atleta_selecionado]['Recorde_5min_HIA'].values
            val_recorde = recorde_atleta[0] if len(recorde_atleta) > 0 else 0
            
            # Esforço calculado a partir dos últimos 5 min do momento simulado
            esforço_atual_5m = df_atual_corte[coluna_distancia].tail(5).mean() if not df_atual_corte.empty else 0
            percentual_do_limite = (esforço_atual_5m / val_recorde * 100) if val_recorde > 0 else 0
        
            k6.metric(
                label="Proximidade Limite (5 min)",
                value=f"{percentual_do_limite:.1f}%",
                delta=f"Recorde: {val_recorde:.1f}",
                help="Compara a intensidade dos últimos 5 minutos no momento simulado com o recorde do atleta na temporada."
            )

        fig = go.Figure()
        
        # Linhas do passado (Histórico)
        if not df_historico.empty:
            jogos_historicos = df_historico[coluna_jogo].unique()
            colors = px.colors.qualitative.Pastel # Usando cores mais suaves para o fundo
            for idx, jogo in enumerate(jogos_historicos):
                df_j = df_historico[df_historico[coluna_jogo] == jogo].sort_values(coluna_minuto)
                jogo_display = df_completo[df_completo['Data'] == jogo]['Data_Display'].iloc[0] if jogo in df_completo['Data'].values else str(jogo)
                fig.add_trace(go.Scatter(
                    x=df_j[coluna_minuto], y=df_j[coluna_acumulada], mode='lines',
                    name=jogo_display, opacity=0.45, # Aumentamos a opacidade para ver melhor
                    line=dict(color=colors[idx % len(colors)], width=2.5), # Tiramos o pontilhado e deixamos mais espessa
                    hovertemplate=f'<b>{jogo_display}</b><br>Valor: %{{y:.1f}}m<extra></extra>' # Mostra o nome do jogo ao passar o mouse na linha
                ))

        # PLOTA A LINHA VERDE COMPLETA (O QUE ELE REALMENTE FEZ NO JOGO TODO)
        jogo_display = df_completo[df_completo['Data'] == jogo_atual_nome]['Data_Display'].iloc[0] if jogo_atual_nome in df_completo['Data'].values else str(jogo_atual_nome)
        fig.add_trace(go.Scatter(
            x=df_atual[coluna_minuto], y=df_atual[coluna_acumulada], mode='lines',
            name=f'{jogo_display} (Realizado)', line=dict(color='#00E676', width=4), 
            hovertemplate='Realizado: %{y:.1f}m<extra></extra>'
        ))

        # PLOTA A PROJEÇÃO QUE COMEÇA DO PONTO DE CORTE
        if len(minutos_futuros) > 0 and len(pred_superior) > 0: 
            fig.add_trace(go.Scatter(x=minutos_futuros, y=pred_superior, mode='lines', line=dict(width=0), showlegend=False, hoverinfo='skip'))
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=pred_inferior, mode='lines', line=dict(width=0),
                fill='tonexty', fillcolor='rgba(255, 140, 0, 0.15)', name='Margem de Variação', hoverinfo='skip'
            ))
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=acumulado_pred, mode='lines', name='Projeção a partir do Corte',
                line=dict(color='#FF8C00', width=3, dash='dash'), hovertemplate='Projeção: %{y:.1f}m<extra></extra>'
            ))
            
            # Linha vertical vermelha indicando onde a IA fez a projeção
            fig.add_vline(x=minuto_atual, line_dash="dash", line_color="#E53935")
            fig.add_annotation(x=minuto_atual, y=carga_atual, text=" Ponto de Corte", showarrow=False, yref="y", xanchor="left", yanchor="bottom", font=dict(color="#E53935"))

        x_min = 0
        x_max = minuto_projecao_ate + 2  

        fig.update_xaxes(tickmode='linear', dtick=1, range=[x_min, x_max], tickfont=dict(size=10), tickangle=0)

        fig.update_layout(
            title=titulo_grafico + f" - {periodo}º Tempo",
            xaxis_title=f'Minutos de Jogo ({periodo}º Tempo)',
            yaxis_title=metrica_selecionada,
            template='plotly_white',
            legend=dict(bgcolor='rgba(0,0,0,0)', orientation="h", yanchor="top", y=-0.35, xanchor="center", x=0.5),
            height=650, hovermode='x unified', margin=dict(l=20, r=20, t=50, b=200)
        )

        st.plotly_chart(fig, use_container_width=True, key=f"grafico_{periodo}")
            
    else:
        st.info(f"Nenhum dado encontrado para o {periodo}º Tempo deste atleta.")
