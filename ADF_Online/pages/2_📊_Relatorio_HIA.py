import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import os
import shutil
import warnings

# =====================================================================
# 1. CONFIGURAÇÃO DA PÁGINA WEB E AJUSTE DE MARGEM
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

st.title("⚡ Timeline HIA: Densidade e Recuperação")

# =====================================================================
# 2. CARREGAMENTO DE DADOS (Padronizado com o Live Tracker)
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
    arquivo_temp = 'ADF_TEMP_HIA.xlsb'
    try:
        shutil.copy2(arquivo_original, arquivo_temp)
        # Adicionamos Acc4 e Dec4 na lista de leitura caso existam
        colunas_necessarias = [
            'Data', 'Interval', 'Name', 'Período', 'Adversário',
            'V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 
            'Acc3 Eff', 'Dec3 Eff', 'Acc4 Eff', 'Dec4 Eff', 'Campeonato'
        ]
        # Carrega apenas as colunas que realmente existem no arquivo para evitar erro
        import calamine
        sheet_cols = pd.read_excel(arquivo_temp, engine='calamine', nrows=0).columns
        cols_to_use = [c for c in colunas_necessarias if c in sheet_cols]
        
        df = pd.read_excel(arquivo_temp, engine='calamine', usecols=cols_to_use) 
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Erro na leitura: {e}")
        return None

df_completo = carregar_dados(hora_atualizacao)

if df_completo is None or df_completo.empty:
    st.stop()

# Criar a métrica HIA somando ações de alta intensidade (Tratando caso alguma coluna falte)
df_completo['HIA'] = (
    df_completo.get('V4 To8 Eff', pd.Series(0, index=df_completo.index)).fillna(0) + 
    df_completo.get('V5 To8 Eff', pd.Series(0, index=df_completo.index)).fillna(0) + 
    df_completo.get('V6 To8 Eff', pd.Series(0, index=df_completo.index)).fillna(0) + 
    df_completo.get('Acc3 Eff', pd.Series(0, index=df_completo.index)).fillna(0) + 
    df_completo.get('Dec3 Eff', pd.Series(0, index=df_completo.index)).fillna(0) +
    df_completo.get('Acc4 Eff', pd.Series(0, index=df_completo.index)).fillna(0) + 
    df_completo.get('Dec4 Eff', pd.Series(0, index=df_completo.index)).fillna(0)
)

df_completo['Data_Display'] = pd.to_datetime(df_completo['Data']).dt.strftime('%d/%m/%Y') + ' ' + df_completo['Adversário'].astype(str)

# =====================================================================
# 3. FILTROS NA TELA PRINCIPAL (IDÊNTICOS AO LIVE TRACKER)
# =====================================================================
st.markdown("### 🔍 Filtros de Análise")

with st.container():
    
    lista_campeonatos = sorted(df_completo['Campeonato'].dropna().unique().tolist()) if 'Campeonato' in df_completo.columns else []
    
    campeonatos_selecionados = st.multiselect(
        "🏆 Campeonatos (Deixe vazio para incluir TODOS):", 
        options=lista_campeonatos,
        default=[] 
    )
    
    if not campeonatos_selecionados or 'Campeonato' not in df_completo.columns: 
        df_base = df_completo.copy()
    else:
        df_base = df_completo[df_completo['Campeonato'].isin(campeonatos_selecionados)].copy()

    col1, col2, col3 = st.columns([1.5, 2, 1.5])
    
    with col1:
        modo_filtro = st.radio("Prioridade:", ("Focar no Atleta", "Focar no Jogo"), horizontal=True)
            
    with col3:
        ordem_graficos = st.radio("Ordem na Tela:", ("1º Tempo no Topo", "2º Tempo no Topo"), horizontal=True)

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

if jogo_selecionado_display:
    jogo_selecionado = df_base[df_base['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]
else:
    st.warning("Nenhum dado encontrado.")
    st.stop()

df_atleta = df_base[(df_base['Name'] == atleta_selecionado) & (df_base['Data'] == jogo_selecionado)].copy()

# =====================================================================
# 4. MOTOR DO GRÁFICO (LINHA DO TEMPO HIA MINUTO A MINUTO)
# =====================================================================
periodos_para_analise = [1, 2] if ordem_graficos == "1º Tempo no Topo" else [2, 1]

for periodo in periodos_para_analise:
    
    st.markdown(f"### ⏱️ {periodo}º Tempo")

    df_periodo = df_atleta[df_atleta['Período'] == periodo].copy()

    if not df_periodo.empty:
        # Agrupa os dados para garantir que temos a soma exata por minuto (Interval)
        df_minutos = df_periodo.groupby('Interval')['HIA'].sum().reset_index()
        
        minuto_maximo = int(df_minutos['Interval'].max())
        
        # Garante que todos os minutos existam no eixo (mesmo os zerados)
        todos_minutos = pd.DataFrame({'Interval': range(1, minuto_maximo + 1)})
        df_timeline = pd.merge(todos_minutos, df_minutos, on='Interval', how='left').fillna(0)
        
        # =====================================================================
        # LÓGICA DE DETECÇÃO DE RECUPERAÇÃO (O tempo "Sem Ação")
        # =====================================================================
        # Conta a maior sequência de minutos consecutivos onde HIA == 0
        df_timeline['Zero_Block'] = (df_timeline['HIA'] > 0).cumsum()
        sequencias_zeros = df_timeline[df_timeline['HIA'] == 0].groupby('Zero_Block').size()
        maior_gap_descanso = sequencias_zeros.max() if not sequencias_zeros.empty else 0
        
        total_hia = df_timeline['HIA'].sum()
        densidade = total_hia / minuto_maximo if minuto_maximo > 0 else 0

        # KPIs do Período
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("HIA Total", f"{total_hia:.0f} ações")
        k2.metric("Minutos Jogados", f"{minuto_maximo} min")
        k3.metric("Densidade (HIA/min)", f"{densidade:.2f}")
        k4.metric("Maior Gap sem HIA", f"{maior_gap_descanso} min seguidos", delta="Recuperação", delta_color="normal")

        # Gráfico Plotly
        fig = go.Figure()
        
        # Desenha as barras de ação
        fig.add_trace(go.Bar(
            x=df_timeline['Interval'],
            y=df_timeline['HIA'],
            marker_color='#FF3D00', # Laranja neon vibrante para alta intensidade
            name='HIA por Minuto',
            hovertemplate='Minuto %{x}: %{y:.0f} ações<extra></extra>'
        ))

        fig.update_xaxes(tickmode='linear', dtick=5, range=[0, minuto_maximo + 1], title="Minuto de Jogo")
        fig.update_yaxes(title="Qtd. Ações HIA")
        
        fig.update_layout(
            template='plotly_white', 
            height=300, # Gráfico mais achatado para parecer uma "linha do tempo"
            margin=dict(l=20, r=20, t=30, b=20),
            hovermode='x unified',
            bargap=0.1 # Deixa as barras gordinhas e coladas umas nas outras
        )

        st.plotly_chart(fig, use_container_width=True, key=f"hia_chart_{periodo}")
        
    else:
        st.info(f"Nenhum dado de HIA encontrado para o {periodo}º Tempo.")
