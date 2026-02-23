import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px # Importante para o gráfico empilhado
import os
import shutil
import warnings

# =====================================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =====================================================================
st.set_page_config(page_title="Relatório HIA - Timeline", layout="wide")

st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
    </style>
    """, unsafe_allow_html=True)

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')
st.title("⚡ Timeline HIA: Espectro de Intensidade")

# =====================================================================
# 2. CARREGAMENTO DE DADOS BLINDADO
# =====================================================================
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_RAIZ = os.path.dirname(DIRETORIO_ATUAL)
arquivo_original = os.path.join(DIRETORIO_RAIZ, 'ADF OnLine 2024.xlsb')

@st.cache_resource(show_spinner=False)
def carregar_dados():
    arquivo_temp = 'ADF_TEMP_HIA_STACKED.xlsb'
    try:
        shutil.copy2(arquivo_original, arquivo_temp)
        df = pd.read_excel(arquivo_temp, engine='calamine') 
        df.columns = df.columns.str.strip()
        
        # Lista MESTRE de colunas que compõem o HIA (Agora com 'Competição')
        colunas_desejadas = [
            'Data', 'Interval', 'Name', 'Período', 'Adversário', 'Competição',
            'V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 
            'Acc3 Eff', 'Dec3 Eff', 'Acc4 Eff', 'Dec4 Eff'
        ]
        
        # Filtra apenas as que existem no Excel do usuário
        colunas_existentes = [c for c in colunas_desejadas if c in df.columns]
        df = df[colunas_existentes]
        
        # Preenche vazios com 0 nas métricas para não quebrar contas
        cols_metricas = [c for c in colunas_existentes if c not in ['Data', 'Interval', 'Name', 'Período', 'Adversário', 'Competição']]
        df[cols_metricas] = df[cols_metricas].fillna(0)
        
        return df, cols_metricas
        
    except Exception as e:
        st.error(f"Erro na leitura: {e}")
        return None, []

df_completo, cols_componentes_hia = carregar_dados()

if df_completo is None or df_completo.empty:
    st.stop()

df_completo['Data_Display'] = pd.to_datetime(df_completo['Data']).dt.strftime('%d/%m/%Y') + ' ' + df_completo['Adversário'].astype(str)

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
# Mapa de cores semântico para diferenciar os tipos de esforço
color_map = {
    'V4 To8 Eff': '#FFAB91', 'V5 To8 Eff': '#FF7043', 'V6 To8 Eff': '#D84315', # Vermelhos (Velocidade)
    'Acc3 Eff': '#90CAF9', 'Acc4 Eff': '#1976D2', # Azuis (Aceleração)
    'Dec3 Eff': '#A5D6A7', 'Dec4 Eff': '#388E3C'  # Verdes (Desaceleração)
}

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
        
        # 3. Calcula o TOTAL HIA por minuto (para os KPIs e lógica de gap)
        df_timeline_full['Total_HIA_Min'] = df_timeline_full[cols_componentes_hia].sum(axis=1)
        
        # --- LÓGICA DE KPIs ---
        df_timeline_full['Zero_Block'] = (df_timeline_full['Total_HIA_Min'] > 0).cumsum()
        sequencias_zeros = df_timeline_full[df_timeline_full['Total_HIA_Min'] == 0].groupby('Zero_Block').size()
        maior_gap_descanso = sequencias_zeros.max() if not sequencias_zeros.empty else 0
        
        total_hia_periodo = df_timeline_full['Total_HIA_Min'].sum()
        densidade = total_hia_periodo / minuto_maximo if minuto_maximo > 0 else 0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("HIA Total (Soma)", f"{total_hia_periodo:.0f} ações")
        k2.metric("Minutos Jogados", f"{minuto_maximo} min")
        k3.metric("Densidade (HIA/min)", f"{densidade:.2f}")
        k4.metric("Maior Gap sem HIA", f"{maior_gap_descanso} min seguidos", delta="Recuperação", delta_color="normal")

        # 4. Transformação para formato Longo (Melt)
        df_melted = df_timeline_full.melt(
            id_vars=['Interval'], 
            value_vars=cols_componentes_hia,
            var_name='Tipo de Esforço', 
            value_name='Qtd Ações'
        )
        df_melted = df_melted[df_melted['Qtd Ações'] > 0]

        # 5. Gera o Gráfico Empilhado
        fig = px.bar(
            df_melted,
            x='Interval',
            y='Qtd Ações',
            color='Tipo de Esforço',
            color_discrete_map=color_map, 
            title=None 
        )

        # =====================================================================
        # LÓGICA DA LINHA DE MÉDIA DA EQUIPA NO MESMO MINUTO
        # =====================================================================
        # Vai buscar todos os jogadores daquele jogo e daquele período
        df_equipa_periodo = df_base[(df_base['Data'] == jogo_selecionado) & (df_base['Período'] == periodo)].copy()
        
        if not df_equipa_periodo.empty:
            # Soma todas as colunas de HIA para ter o total por registo
            df_equipa_periodo['Total_HIA'] = df_equipa_periodo[cols_componentes_hia].sum(axis=1)
            
            # 1º Agrupa por Minuto e Jogador (para saber quanto cada jogador fez naquele minuto)
            hia_jogador_minuto = df_equipa_periodo.groupby(['Interval', 'Name'])['Total_HIA'].sum().reset_index()
            
            # 2º Calcula a média dessas somas por minuto
            media_grupo_minuto = hia_jogador_minuto.groupby('Interval')['Total_HIA'].mean().reset_index()
            
            # Adiciona a linha ao gráfico
            fig.add_trace(go.Scatter(
                x=media_grupo_minuto['Interval'],
                y=media_grupo_minuto['Total_HIA'],
                mode='lines',
                name='Média da Equipa',
                line=dict(color='#212121', width=2, dash='dot'), # Linha preta/escura pontilhada
                hovertemplate='Média Equipa: %{y:.1f} ações<extra></extra>'
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
            yaxis=dict(title="Qtd. Ações HIA (Empilhado)"),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None
            )
        )
        # Adiciona o total no topo da barra ao passar o rato
        fig.update_traces(hovertemplate='%{y:.0f} ações', selector=dict(type='bar'))

        st.plotly_chart(fig, use_container_width=True, key=f"hia_stacked_{periodo}")
        
    else:
        st.info(f"Nenhum dado de alta intensidade encontrado para o {periodo}º Tempo.")
