import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import shutil
import os
import warnings
from streamlit_autorefresh import st_autorefresh

# =====================================================================
# 1. CONFIGURAÇÃO DA PÁGINA WEB E AJUSTE DE MARGEM
# =====================================================================
st.set_page_config(page_title="Live Tracker Físico", layout="wide")

# CSS para remover o espaço gigante do topo
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

contador = st_autorefresh(interval=60000, limit=1000, key="live_tracker_refresh")

st.title('⚽ Live Tracker: Projeção de Carga Física')
st.caption(f"Última atualização automática: Ciclo {contador}")

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# =====================================================================
# 2. CARREGAMENTO DE DADOS (Caminhos Dinâmicos e Engine Rápida)
# =====================================================================
def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_RAIZ = os.path.dirname(DIRETORIO_ATUAL)
arquivo_original = os.path.join(DIRETORIO_RAIZ, 'ADF OnLine 2024.xlsb')

hora_atualizacao = obter_hora_modificacao(arquivo_original)

@st.cache_resource(show_spinner=False)
def carregar_dados(hora_mod):
    arquivo_temp = 'ADF_TEMP_LIVE.xlsb'
    try:
        shutil.copy2(arquivo_original, arquivo_temp)
        colunas_necessarias = [
            'Data', 'Interval', 'Name', 'Período', 'Placar', 'Adversário',
            'Total Distance', 'V4 Dist', 'V4 To8 Eff', 'V5 To8 Eff', 
            'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Player Load', 'Competição'
        ]
        df = pd.read_excel(arquivo_temp, engine='calamine', usecols=colunas_necessarias) 
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro na leitura: {e}")
        return None

df_completo = carregar_dados(hora_atualizacao)

if df_completo is None:
    st.stop()

# Criar a métrica HIA somando ações de alta intensidade
df_completo['HIA'] = (
    df_completo['V4 To8 Eff'].fillna(0) + 
    df_completo['V5 To8 Eff'].fillna(0) + 
    df_completo['V6 To8 Eff'].fillna(0) + 
    df_completo['Acc3 Eff'].fillna(0) + 
    df_completo['Dec3 Eff'].fillna(0)
)

# Formatar datas para exibição bonita
df_completo['Data_Display'] = pd.to_datetime(df_completo['Data']).dt.strftime('%d/%m/%Y') + ' ' + df_completo['Adversário'].astype(str)

coluna_jogo = 'Data'
coluna_minuto = 'Interval'

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
        metrica_selecionada = st.pills("Métrica:", ["Total Distance", "V4 Dist", "HIA"], default="V4 Dist")
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
    
    # Define as colunas conforme a métrica
    if metrica_selecionada == "Total Distance":
        coluna_distancia = 'Total Distance'
        coluna_acumulada = 'Dist Acumulada'
        titulo_grafico = f'Projeção de Distância - {atleta_selecionado}'
    elif metrica_selecionada == "V4 Dist":
        coluna_distancia = 'V4 Dist'
        coluna_acumulada = 'V4 Dist Acumulada'
        titulo_grafico = f'Projeção de V4 Dist - {atleta_selecionado}'
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
                
            st.info(f"🧠 **ML Engine ({periodo}º Tempo):** Tática ('{placar_atual}'). Ajuste: 70% Ritmo vs 30% Player Load.")

            curva_media_acumulada_geral = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
            if 'Player Load Acumulada' in df_historico.columns:
                curva_media_pl_geral = df_historico.groupby(coluna_minuto)['Player Load Acumulada'].mean()
            else:
                curva_media_pl_geral = curva_media_acumulada_geral
            
            if minuto_atual in curva_media_acumulada_geral.index:
                media_acumulada_neste_minuto = curva_media_acumulada_geral.loc[minuto_atual]
                media_pl_neste_minuto = curva_media_pl_geral.loc[minuto_atual] if minuto_atual in curva_media_pl_geral.index else pl_atual_acumulado
            else:
                media_acumulada_neste_minuto = carga_atual 
                media_pl_neste_minuto = pl_atual_acumulado
                
            fator_alvo = (carga_atual / media_acumulada_neste_minuto) if media_acumulada_neste_minuto > 0 else 1.0
            fator_pl = (pl_atual_acumulado / media_pl_neste_minuto) if media_pl_neste_minuto > 0 else 1.0
            
            peso_player_load = 0.3 
            fator_hoje = (fator_alvo * (1 - peso_player_load)) + (fator_pl * peso_player_load)

            minutos_futuros = list(range(minuto_atual + 1, minuto_projecao_ate + 1))
            valor_projetado_atual = carga_atual 
            
            for m in minutos_futuros:
                dist_g = media_min_geral.loc[m] if m in media_min_geral.index else 0
                dist_c = media_min_cenario.loc[m] if m in media_min_cenario.index else dist_g
                
                dist_mesclada = (dist_c * peso_placar) + (dist_g * (1 - peso_placar))
                dist_mesclada = max(0, dist_mesclada)
                
                dist_projetada_minuto = dist_mesclada * fator_hoje
                valor_projetado_atual += dist_projetada_minuto
                acumulado_pred.append(valor_projetado_atual)
            
            margem_erro = 0.05
            pred_superior = [val * (1 + margem_erro) for val in acumulado_pred]
            pred_inferior = [val * (1 - margem_erro) for val in acumulado_pred]

            # --- PREPARAÇÃO DOS KPIs ---
            carga_projetada = acumulado_pred[-1] if len(acumulado_pred) > 0 else carga_atual
            minuto_final_proj = minutos_futuros[-1] if len(minutos_futuros) > 0 else minuto_atual

            delta_alvo_pct = (fator_alvo - 1) * 100 
            delta_pl_pct = (fator_pl - 1) * 100
            
            if minuto_final_proj in curva_media_acumulada_geral.index:
                media_historica_futura = curva_media_acumulada_geral.loc[minuto_final_proj]
            else:
                media_historica_futura = media_acumulada_neste_minuto

            fator_projetado = (carga_projetada / media_historica_futura) if media_historica_futura > 0 else 1.0
            delta_projetado_pct = (fator_projetado - 1) * 100
            
            # --- RITMO COLETIVO ---
            df_time_hoje = df_base[(df_base['Data'] == jogo_atual_nome) & (df_base['Período'] == periodo) & (df_base['Interval'] <= minuto_atual)]
            df_time_hist = df_base[(df_base['Data'] != jogo_atual_nome) & (df_base['Período'] == periodo) & (df_base['Interval'] <= minuto_atual)]

            carga_hoje_time = df_time_hoje.groupby('Name')[coluna_distancia].sum().mean() if not df_time_hoje.empty else 0
            carga_hist_time = df_time_hist.groupby(['Data', 'Name'])[coluna_distancia].sum().mean() if not df_time_hist.empty else carga_hoje_time
            
            delta_time_pct = ((carga_hoje_time / carga_hist_time) - 1) * 100 if carga_hist_time > 0 else 0.0
            delta_atleta_vs_time = delta_alvo_pct - delta_time_pct

        else:
            st.warning("Pouco histórico neste campeonato para ativar a IA. Mostrando os dados em tempo real puros.")

        # =====================================================================
        # RENDERIZAÇÃO NA TELA (Roda com ou sem Inteligência Artificial)
        # =====================================================================
        unidade = "" if metrica_selecionada == "HIA" else " m"
        def fmt_dist(x): return f"{x:.0f}{unidade}" if not np.isnan(x) else "N/A"
        def fmt_pct(x): return f"{x:+.1f}%" if not np.isnan(x) else "N/A"

        k0, k1, k2, k3, k4, k5 = st.columns(6)
        cor_delta = "normal" if metrica_selecionada in ["V4 Dist", "HIA", "Total Distance"] else "inverse"
        
        k0.metric("Carga Atual", fmt_dist(carga_atual))
        k1.metric("vs Própria Média", fmt_pct(delta_alvo_pct), delta=fmt_pct(delta_alvo_pct), delta_color=cor_delta)
        k2.metric("Ritmo Coletivo (Jogo)", fmt_pct(delta_time_pct), delta=f"{fmt_pct(delta_atleta_vs_time)} (Atleta vs Jogo)", delta_color=cor_delta)
        k3.metric(f"Carga Proj. (min {minuto_final_proj})", fmt_dist(carga_projetada))
        k4.metric(f"Ritmo Previsto", fmt_pct(delta_projetado_pct), delta=fmt_pct(delta_projetado_pct), delta_color=cor_delta)
        k5.metric(f"Desgaste Sistêmico (PL)", f"{pl_atual_acumulado:.0f}", delta=fmt_pct(delta_pl_pct), delta_color="inverse")

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
