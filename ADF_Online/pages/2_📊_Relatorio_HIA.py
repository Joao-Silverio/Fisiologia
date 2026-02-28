import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import warnings

# 1. Importações da Arquitetura
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
from streamlit_autorefresh import st_autorefresh
import Source.UI.visual as visual
import Source.UI.components as ui

# 2. Configuração Visual
st.set_page_config(page_title=f"Relatório HIA | {visual.CLUBE['sigla']}", layout="wide", initial_sidebar_state="collapsed")
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# CHAMA O NOVO MENU SUPERIOR (E o fundo padrão)
ui.renderizar_menu_superior(pagina_atual="Relatório") # <-- Nome tem que ser igual ao que você botou lá no nav_items

# 3. Cabeçalho Padronizado
ui.renderizar_cabecalho("Timeline HIA", "Espectro de Intensidade e Ações V4+")

st_autorefresh(interval=2000, limit=None, key="refresh_desta_pagina")
hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
df_novo, df_recordes_novo = load_global_data(hora_atual)

if not df_novo.empty:
    st.session_state['df_global'] = df_novo
    st.session_state['df_recordes'] = df_recordes_novo

if 'df_global' not in st.session_state or st.session_state['df_global'].empty:
    st.warning("⚠️ Carregue os dados na página principal ou verifique o arquivo Excel.")
    st.stop()

# =====================================================================
# RECUPERANDO DADOS GLOBAIS
# =====================================================================
df_completo = st.session_state['df_global'].copy()
cols_componentes_hia = [c for c in config.COLS_COMPONENTES_HIA if c in df_completo.columns]

# =====================================================================
# 3. FILTROS: HIERARQUIA DE FUNIL (COMPETIÇÃO -> JOGO -> ATLETA)
# =====================================================================
st.markdown("### 🔍 Configuração do Perfil")
with st.container():
    
    # --- LINHA 1: COMPETIÇÃO E JOGO ---
    col1, col2 = st.columns([1.5, 2.5])
    
    lista_competicoes = sorted(df_completo['Competição'].dropna().unique().tolist()) if 'Competição' in df_completo.columns else []
    with col1:
        competicoes_selecionadas = st.multiselect("🏆 Competições:", options=lista_competicoes, default=[])
        
    df_base = df_completo[df_completo['Competição'].isin(competicoes_selecionadas)] if competicoes_selecionadas else df_completo.copy()
    lista_jogos_display = df_base.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
    
    with col2: 
        jogo_selecionado_display = st.selectbox("📅 Selecione o Jogo:", lista_jogos_display)
        
    if not jogo_selecionado_display: 
        st.warning("Nenhum dado encontrado.")
        st.stop()
        
    jogo_selecionado = df_base[df_base['Data_Display'] == jogo_selecionado_display]['Data'].iloc[0]
    df_jogo_filtrado = df_base[df_base['Data'] == jogo_selecionado].copy()

    # --- LINHA 2: ESCOLHA DO ATLETA (PILLS) ---
    st.markdown("<br>", unsafe_allow_html=True)
    lista_atletas = sorted(df_jogo_filtrado['Name'].dropna().unique())
    
    atleta_selecionado = st.pills("🏃 Selecione o Atleta para Foco Individual:", lista_atletas, default=lista_atletas[0] if lista_atletas else None)

    if not atleta_selecionado:
        st.warning("Por favor, selecione um atleta para continuar.")
        st.stop()

# Datasets finais para os gráficos
df_atleta_jogo = df_jogo_filtrado[df_jogo_filtrado['Name'] == atleta_selecionado].copy()
df_equipa_jogo = df_jogo_filtrado.copy()

# =====================================================================
# 4. MOTOR DO GRÁFICO EMPILHADO (STACKED BAR CHART) COM ABAS
# =====================================================================
st.markdown("<br>", unsafe_allow_html=True)
aba_t1, aba_t2 = st.tabs(["⏱️ 1º Tempo", "⏱️ 2º Tempo"])
mapa_abas = {1: aba_t1, 2: aba_t2}

for periodo in [1, 2]:
    with mapa_abas[periodo]:
        st.markdown(f"### ⏱️ Espectro de Intensidade: {atleta_selecionado} ({periodo}º Tempo)")
        df_periodo = df_atleta_jogo[df_atleta_jogo['Período'] == periodo].copy()

        if not df_periodo.empty and cols_componentes_hia:
            # Agrupa os componentes do atleta
            df_minutos_components = df_periodo.groupby('Interval')[cols_componentes_hia].sum().reset_index()
            minuto_maximo = int(df_minutos_components['Interval'].max())
            todos_minutos = pd.DataFrame({'Interval': range(1, minuto_maximo + 1)})
            df_timeline_full = pd.merge(todos_minutos, df_minutos_components, on='Interval', how='left').fillna(0)
            df_timeline_full['Total_HIA_Min'] = df_timeline_full[cols_componentes_hia].sum(axis=1)
            
            # Cálculos da Média da Equipa
            df_equipa_periodo = df_equipa_jogo[df_equipa_jogo['Período'] == periodo].copy()
            
            if not df_equipa_periodo.empty:
                df_equipa_periodo['Total_HIA'] = df_equipa_periodo[cols_componentes_hia].sum(axis=1)
                hia_por_jogador = df_equipa_periodo.groupby('Name')['Total_HIA'].sum()
                hia_por_jogador = hia_por_jogador[hia_por_jogador > 0]
                media_hia_equipe = hia_por_jogador.mean() if not hia_por_jogador.empty else 0
                
                hia_jogador_minuto = df_equipa_periodo.groupby(['Interval', 'Name'])['Total_HIA'].sum().reset_index()
                media_grupo_minuto = hia_jogador_minuto.groupby('Interval')['Total_HIA'].mean().reset_index()
            else:
                media_hia_equipe = 0
                media_grupo_minuto = pd.DataFrame(columns=['Interval', 'Total_HIA'])

            # Lógica KPIs do Atleta
            df_timeline_full['Zero_Block'] = (df_timeline_full['Total_HIA_Min'] > 0).cumsum()
            sequencias_zeros = df_timeline_full[df_timeline_full['Total_HIA_Min'] == 0].groupby('Zero_Block').size()
            maior_gap_descanso = sequencias_zeros.max() if not sequencias_zeros.empty else 0
            
            total_hia_periodo = df_timeline_full['Total_HIA_Min'].sum()
            densidade = total_hia_periodo / minuto_maximo if minuto_maximo > 0 else 0
            delta_vs_equipe = ((total_hia_periodo / media_hia_equipe) - 1) * 100 if media_hia_equipe > 0 else 0.0

            # Renderização dos Cartões Customizados
            k1, k2, k3, k4, k5 = st.columns(5)
            
            with k1: ui.renderizar_card_kpi("Minutos Jogados", f"{minuto_maximo}m", icone="⏱️")
            with k2: ui.renderizar_card_kpi("HIA Total", f"{total_hia_periodo:.2f}", cor_borda=visual.CORES["alerta_fadiga"], icone="⚡")
            with k3: ui.renderizar_card_kpi("Média da Equipe", f"{media_hia_equipe:.2f}", delta=f"{delta_vs_equipe:+.2f}% vs Equipe", delta_color="normal", icone="👥")
            with k4: ui.renderizar_card_kpi("Densidade", f"{densidade:.2f}", icone="📊")
            with k5: ui.renderizar_card_kpi("Tempo s/ Estímulo", f"{maior_gap_descanso}m", delta="Recuperação", delta_color="off", cor_borda=visual.CORES["ok_prontidao"], icone="🔋")
                
            # Gráfico Empilhado
            df_melted = df_timeline_full.melt(id_vars=['Interval'], value_vars=cols_componentes_hia, var_name='Tipo de Esforço', value_name='Qtd Ações')
            df_melted = df_melted[df_melted['Qtd Ações'] > 0]

            CORES_DARK_HIA = {
                'V4 To8 Eff': '#FDE68A', 'V5 To8 Eff': '#F59E0B', 'V6 To8 Eff': '#EF4444', 
                'Acc3 Eff': '#60A5FA', 'Dec3 Eff': '#10B981', 'Acc4 Eff': '#3B82F6', 'Dec4 Eff': '#059669',
            }

            fig = px.bar(df_melted, x='Interval', y='Qtd Ações', color='Tipo de Esforço', color_discrete_map=CORES_DARK_HIA, title=None)

            if not media_grupo_minuto.empty:
                fig.add_trace(go.Scatter(
                    x=media_grupo_minuto['Interval'], y=media_grupo_minuto['Total_HIA'], mode='lines',
                    name='Média da Equipe', line=dict(color='#F8FAFC', width=2, dash='dot'), hovertemplate='Média Equipe: %{y:.2f} ações<extra></extra>' 
                ))

            fig.update_layout(
                template='plotly_dark', plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=350, margin=dict(l=20, r=20, t=10, b=20),
                hovermode='x unified', bargap=0.15, 
                xaxis=dict(tickmode='linear', dtick=5, range=[0, minuto_maximo + 1], title="Minuto de Jogo", gridcolor='#334155'),
                yaxis=dict(title="Qtd. Ações HIA", gridcolor='#334155'),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title=None)
            )
            fig.update_traces(hovertemplate='%{y:.2f} ações', selector=dict(type='bar'))

            st.plotly_chart(fig, width='stretch', key=f"hia_stacked_{periodo}")
            
        else:
            st.info(f"Nenhum dado de alta intensidade encontrado para o {periodo}º Tempo deste atleta.")