import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import warnings
import ADF_Online.Source.Dados.config as config # <--- IMPORTANDO O CONFIG
from streamlit_autorefresh import st_autorefresh
from ADF_Online.Source.Dados.data_loader import obter_hora_modificacao, load_global_data

st.set_page_config(page_title="Relatório HIA - Timeline", layout="wide")

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
st.title("⚡ Timeline HIA: Espectro de Intensidade")

# 1. Pede à página para "piscar os olhos" a cada 2 segundos (2000 ms)
# Usa uma "key" diferente para cada página (ex: "refresh_comparacao", "refresh_hia")
st_autorefresh(interval=2000, limit=None, key="refresh_desta_pagina")

# 2. Verifica a "impressão digital" (hora exata) do ficheiro Excel
hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

# 3. Pede os dados. Se a "hora_atual" não mudou, o Streamlit não faz NADA (0% de CPU).
# Se a "hora_atual" mudou, o Streamlit carrega os dados novos!
df_novo, df_recordes_novo = load_global_data(hora_atual)

# 4. Atualiza a memória global para os gráficos desenharem com os dados frescos
if not df_novo.empty:
    st.session_state['df_global'] = df_novo
    st.session_state['df_recordes'] = df_recordes_novo

# E depois continuas a ler o session_state como sempre fizeste:
if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal ou verifique o arquivo Excel.")
    st.stop()

# =====================================================================
# RECUPERANDO DADOS GLOBAIS
# =====================================================================

# Pega os dados já calculados e formatados
df_completo = st.session_state['df_global'].copy()

# Mapeia as colunas de componentes do HIA usando o config.py
cols_componentes_hia = [c for c in config.COLS_COMPONENTES_HIA if c in df_completo.columns]

# =====================================================================
# 3. FILTROS NA TELA PRINCIPAL (PADRÃO LIVE TRACKER)
# =====================================================================
st.markdown("### 🔍 Filtros de Análise")

with st.container():
    # Agora puxando da coluna 'Competição'
    lista_competicoes = sorted(df_completo['Competição'].dropna().unique().tolist()) if 'Competição' in df_completo.columns else []
    competicoes_selecionadas = st.multiselect("🏆 Competições (Deixe vazio para incluir TODAS):", options=lista_competicoes, default=[])
    
    if not competicoes_selecionadas or 'Competição' not in df_completo.columns: 
        df_base = df_completo.copy()
    else:
        df_base = df_completo[df_completo['Competição'].isin(competicoes_selecionadas)].copy()

    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    with col1: modo_filtro = st.radio("Prioridade:", ("Focar no Atleta", "Focar no Jogo"), horizontal=True)
    with col3: ordem_graficos = st.radio("Ordem na Tela:", ("1º Tempo no Topo", "2º Tempo no Topo"), horizontal=True)

    if modo_filtro == "Focar no Atleta":
        lista_atletas = sorted(df_base['Name'].dropna().unique())
        atleta_selecionado = st.pills("Selecione o Atleta:", lista_atletas, default=lista_atletas[0] if lista_atletas else None)
        if not atleta_selecionado and lista_atletas: atleta_selecionado = lista_atletas[0]
        
        df_filtrado = df_base[df_base['Name'] == atleta_selecionado]
        lista_jogos_display = df_filtrado.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
        with col2: jogo_selecionado_display = st.selectbox("Selecione o Jogo:", lista_jogos_display)
    else:
        lista_jogos_display = df_base.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
        with col2: jogo_selecionado_display = st.selectbox("Selecione o Jogo:", lista_jogos_display)
        
        df_filtrado = df_base[df_base['Data_Display'] == jogo_selecionado_display]
        lista_atletas = sorted(df_filtrado['Name'].dropna().unique())
        atleta_selecionado = st.pills("Selecione o Atleta:", lista_atletas, default=lista_atletas[0] if lista_atletas else None)
        if not atleta_selecionado and lista_atletas: atleta_selecionado = lista_atletas[0]

if not jogo_selecionado_display: st.warning("Nenhum dado encontrado."); st.stop()
jogo_selecionado = df_base[df_base['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]

# Filtra o dataframe final para o atleta e jogo escolhidos
df_atleta_jogo = df_base[(df_base['Name'] == atleta_selecionado) & (df_base['Data'] == jogo_selecionado)].copy()

# =====================================================================
# 4. MOTOR DO GRÁFICO EMPILHADO (STACKED BAR CHART)
# =====================================================================

periodos_para_analise = [1, 2] if ordem_graficos == "1º Tempo no Topo" else [2, 1]

for periodo in periodos_para_analise:
    st.markdown(f"### ⏱️ {periodo}º Tempo")
    df_periodo = df_atleta_jogo[df_atleta_jogo['Período'] == periodo].copy()

    if not df_periodo.empty and cols_componentes_hia:
        # 1. Agrupa por minuto somando CADA COMPONENTE separadamente
        df_minutos_components = df_periodo.groupby('Interval')[cols_componentes_hia].sum().reset_index()
        
        # 2. Garante que todos os minutos existam no eixo X (preenchendo com 0)
        minuto_maximo = int(df_minutos_components['Interval'].max())
        todos_minutos = pd.DataFrame({'Interval': range(1, minuto_maximo + 1)})
        df_timeline_full = pd.merge(todos_minutos, df_minutos_components, on='Interval', how='left').fillna(0)
        
        # 3. Calcula o TOTAL HIA por minuto do ATLETA
        df_timeline_full['Total_HIA_Min'] = df_timeline_full[cols_componentes_hia].sum(axis=1)
        
        # =====================================================================
        # CÁLCULOS DA EQUIPE (Para o Botão KPI e para a Linha do Gráfico)
        # =====================================================================
        df_equipa_periodo = df_base[(df_base['Data'] == jogo_selecionado) & (df_base['Período'] == periodo)].copy()
        
        if not df_equipa_periodo.empty:
            df_equipa_periodo['Total_HIA'] = df_equipa_periodo[cols_componentes_hia].sum(axis=1)
            
            # Média TOTAL de HIA por jogador (Para o novo botão)
            hia_por_jogador = df_equipa_periodo.groupby('Name')['Total_HIA'].sum()
            hia_por_jogador = hia_por_jogador[hia_por_jogador > 0] # Ignora quem não entrou
            media_hia_equipe = hia_por_jogador.mean() if not hia_por_jogador.empty else 0
            
            # Média por MINUTO (Para a linha tracejada do gráfico)
            hia_jogador_minuto = df_equipa_periodo.groupby(['Interval', 'Name'])['Total_HIA'].sum().reset_index()
            media_grupo_minuto = hia_jogador_minuto.groupby('Interval')['Total_HIA'].mean().reset_index()
        else:
            media_hia_equipe = 0
            media_grupo_minuto = pd.DataFrame(columns=['Interval', 'Total_HIA'])

        # --- LÓGICA DE KPIs DO ATLETA ---
        df_timeline_full['Zero_Block'] = (df_timeline_full['Total_HIA_Min'] > 0).cumsum()
        sequencias_zeros = df_timeline_full[df_timeline_full['Total_HIA_Min'] == 0].groupby('Zero_Block').size()
        maior_gap_descanso = sequencias_zeros.max() if not sequencias_zeros.empty else 0
        
        total_hia_periodo = df_timeline_full['Total_HIA_Min'].sum()
        densidade = total_hia_periodo / minuto_maximo if minuto_maximo > 0 else 0
        
        # Calcula a porcentagem do Atleta vs a Média da Equipe
        delta_vs_equipe = ((total_hia_periodo / media_hia_equipe) - 1) * 100 if media_hia_equipe > 0 else 0.0

        # =====================================================================
        # RENDERIZAÇÃO DOS BOTÕES (REORDENADOS E FORMATADOS)
        # =====================================================================
        k1, k2, k3, k4, k5 = st.columns(5)
        
        # 1. Minutos Jogados (Inteiro)
        k1.metric("Minutos Jogados", f"{minuto_maximo} min")
        
        # 2. HIA Total (2 casas decimais)
        k2.metric("HIA Total", f"{total_hia_periodo:.2f} ações")
        
        # 3. Média da Equipe (2 casas decimais + Delta %)
        k3.metric(
            "Média da Equipe (HIA)", 
            f"{media_hia_equipe:.2f} ações", 
            delta=f"{delta_vs_equipe:+.2f}% vs Equipe", 
            delta_color="normal"
        )
        
        # 4. Densidade (2 casas decimais)
        k4.metric("Densidade (HIA/min)", f"{densidade:.2f}")
        
        # 5. Tempo sem ação/Gap (2 casas decimais)
        k5.metric("Tempo Máx. sem Estímulo", f"{maior_gap_descanso} min", delta="Recuperação", delta_color="normal", help="Maior sequência de minutos sem ações de alta intensidade, indicando o tempo máximo de recuperação durante o período.")

        # =====================================================================
        # GRÁFICO EMPILHADO (Ajustado para 2 casas decimais no hover)
        # =====================================================================
        df_melted = df_timeline_full.melt(
            id_vars=['Interval'], 
            value_vars=cols_componentes_hia,
            var_name='Tipo de Esforço', 
            value_name='Qtd Ações'
        )
        df_melted = df_melted[df_melted['Qtd Ações'] > 0]

        fig = px.bar(
            df_melted,
            x='Interval',
            y='Qtd Ações',
            color='Tipo de Esforço',
            color_discrete_map=config.MAPA_CORES_HIA, # <--- USANDO O CONFIG AQUI
            title=None 
        )

        # Adiciona a linha pontilhada da Equipe ao gráfico
        if not media_grupo_minuto.empty:
            fig.add_trace(go.Scatter(
                x=media_grupo_minuto['Interval'],
                y=media_grupo_minuto['Total_HIA'],
                mode='lines',
                name='Média da Equipe',
                line=dict(color='#212121', width=2, dash='dot'),
                hovertemplate='Média Equipe: %{y:.2f} ações<extra></extra>' # Formatação no gráfico
            ))

        fig.update_layout(
            template='plotly_white',
            height=350,
            margin=dict(l=20, r=20, t=10, b=20),
            hovermode='x unified',
            bargap=0.15, 
            xaxis=dict(
                tickmode='linear', dtick=5, range=[0, minuto_maximo + 1], title="Minuto de Jogo"
            ),
            yaxis=dict(title="Qtd. Ações HIA"),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None
            )
        )
        # Formatação de 2 casas decimais nas barras ao passar o mouse
        fig.update_traces(hovertemplate='%{y:.2f} ações', selector=dict(type='bar'))

        st.plotly_chart(fig, use_container_width=True, key=f"hia_stacked_{periodo}")
        
    else:
        st.info(f"Nenhum dado de alta intensidade encontrado para o {periodo}º Tempo.")