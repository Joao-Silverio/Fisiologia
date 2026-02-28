import streamlit as st
import pandas as pd
import warnings
import plotly.express as px

# Importações seguindo o padrão da arquitetura
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
from streamlit_autorefresh import st_autorefresh
import Source.UI.visual as visual
import Source.UI.components as ui

# Configuração de Página
st.set_page_config(page_title=f"Raio-X Individual | {visual.CLUBE['sigla']}", layout="wide")
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# Cabeçalho Padronizado
ui.renderizar_cabecalho("Relatório Individual", "Análise de performance e comparação histórica")

# Refresh e Carregamento de Dados
st_autorefresh(interval=2000, limit=None, key="refresh_individual_atleta")
hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
df_novo, _ = load_global_data(hora_atual)

if not df_novo.empty:
    st.session_state['df_global'] = df_novo

if 'df_global' not in st.session_state:
    st.warning("⚠️ Carregue os dados na Home primeiro.")
    st.stop()

df_completo = st.session_state['df_global'].copy()

# =====================================================================
# FILTROS: HIERARQUIA DE FUNIL (JOGO -> ATLETA)
# =====================================================================
st.markdown("### 🔍 Seleção de Análise")

with st.container():
    col_j, col_a = st.columns([2, 2])
    
    # 1. Seleção do Jogo Primeiro (Destaque)
    lista_jogos = df_completo.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
    with col_j:
        jogo_destaque_display = st.selectbox("🎯 Selecione o Jogo em Destaque:", lista_jogos)
    
    jogo_destaque_data = df_completo[df_completo['Data_Display'] == jogo_destaque_display]['Data'].iloc[0]
    df_jogo_base = df_completo[df_completo['Data'] == jogo_destaque_data]

    # 2. Seleção do Atleta (Apenas quem jogou nesse jogo)
    lista_atletas = sorted(df_jogo_base['Name'].dropna().unique())
    with col_a:
        atleta_selecionado = st.selectbox("🏃 Selecione o Atleta:", lista_atletas)

# Separação de Dados: Jogo Destaque vs Histórico do Atleta
df_atleta_total = df_completo[df_completo['Name'] == atleta_selecionado].copy()
df_jogo_atleta = df_atleta_total[df_atleta_total['Data'] == jogo_destaque_data]
df_historico_atleta = df_atleta_total[df_atleta_total['Data'] != jogo_destaque_data]

# =====================================================================
# ESTRUTURA DA PÁGINA INDIVIDUAL (SEM GRÁFICOS)
# =====================================================================
st.markdown(f"#### 👤 Painel Individual: {atleta_selecionado} | Jogo {jogo_destaque_display}")

total_jogos = df_atleta_total['Data'].nunique()
total_minutos = int(df_jogo_atleta['Duration'].sum()) if 'Duration' in df_jogo_atleta.columns else 0
media_minutos = (
    df_atleta_total.groupby('Data')['Duration'].sum().mean()
    if 'Duration' in df_atleta_total.columns and not df_atleta_total.empty
    else 0
)

col_kpi_1, col_kpi_2, col_kpi_3 = st.columns(3)

with col_kpi_1:
    ui.renderizar_card_kpi("Jogos no Histórico", f"{total_jogos}", cor_borda=visual.CORES["primaria"])
with col_kpi_2:
    ui.renderizar_card_kpi("Minutagem no Jogo", f"{total_minutos} min", cor_borda=visual.CORES["secundaria"])
with col_kpi_3:
    ui.renderizar_card_kpi("Média de Minutos", f"{media_minutos:.0f} min", cor_borda=visual.CORES["aviso_carga"])

st.markdown("### 🧭 Estrutura de Análise Jogo a Jogo")

aba_timeline, aba_comparativo, aba_minutagem, aba_clusters, aba_insights = st.tabs([
    "📈 Linha do tempo",
    "⚔️ Comparativo entre jogos",
    "⏱️ Minutagens",
    "🏃 Clusters Velocidade/Aceleração",
    "💡 Insights e próximos passos"
])

with aba_timeline:
    st.markdown("#### Evolução de performance por partida")
    
    # Agrupa os dados por jogo para o atleta
    cols_analise = ['Total Distance', 'Player Load', 'HIA']
    df_evolucao = df_atleta_total.groupby(['Data', 'Data_Display'])[cols_analise].sum().reset_index().sort_values('Data')
    
    col_a, col_b = st.columns([2, 1])
    with col_a:
        metrica_grafico = st.selectbox("Selecione a Métrica:", cols_analise, key="metrica_timeline")
        
        # Gráfico Plotly
        fig = px.line(
            df_evolucao, 
            x='Data_Display', 
            y=metrica_grafico, 
            markers=True,
            title=f"Evolução: {metrica_grafico}"
        )
        # Aplica o tema visual padronizado do projeto
        fig.update_layout(visual.PLOTLY_TEMPLATE['layout'])
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.markdown("**Resumo Histórico**")
        df_resumo = df_evolucao[['Data_Display', metrica_grafico]].tail(5).sort_values('Data_Display', ascending=False)
        st.dataframe(df_resumo, use_container_width=True, hide_index=True)

with aba_comparativo:
    st.markdown("#### Diferenças do jogo selecionado para a média")
    
    # Calcula as métricas do JOGO ATUAL
    metricas_alvo = ["Total Distance", "Player Load", "HIA", "V5 To8 Eff"]
    jogo_atual_stats = df_jogo_atleta[metricas_alvo].sum()
    
    # Calcula a MÉDIA HISTÓRICA por jogo
    df_agrupado_hist = df_historico_atleta.groupby('Data')[metricas_alvo].sum()
    media_historica = df_agrupado_hist.mean().fillna(0)
    
    # Monta o DataFrame de Comparação
    df_comp = pd.DataFrame({
        "Métrica": metricas_alvo,
        "Jogo Atual": jogo_atual_stats.values.round(1),
        "Média (Outros Jogos)": media_historica.values.round(1)
    })
    
    df_comp['Diferença %'] = ((df_comp['Jogo Atual'] - df_comp['Média (Outros Jogos)']) / df_comp['Média (Outros Jogos)'] * 100).fillna(0)
    
    # Formatação visual
    def formatar_cor(val):
        cor = visual.CORES["ok_prontidao"] if val >= 0 else visual.CORES["alerta_fadiga"]
        return f'<span style="color:{cor}; font-weight:bold;">{val:+.1f}%</span>'
    
    df_comp_display = df_comp.copy()
    df_comp_display['Diferença %'] = df_comp_display['Diferença %'].apply(formatar_cor)
    
    st.write(df_comp_display.to_html(escape=False, index=False), unsafe_allow_html=True)

with aba_minutagem:
    st.markdown("#### Minutagem e distribuição por período no jogo atual")
    
    if 'Min_Num' in df_jogo_atleta.columns and 'Período' in df_jogo_atleta.columns:
        df_tempos = df_jogo_atleta.groupby('Período')['Min_Num'].sum().reset_index()
        total_min_jogo = df_tempos['Min_Num'].sum()
        
        df_tempos['% do Total'] = (df_tempos['Min_Num'] / total_min_jogo * 100).round(1).astype(str) + "%"
        
        col1, col2 = st.columns(2)
        with col1:
            st.dataframe(df_tempos.rename(columns={'Min_Num': 'Minutos Jogados'}), use_container_width=True, hide_index=True)
        with col2:
            st.info(f"**Minutagem Total neste jogo:** {total_min_jogo:.1f} minutos.")
    else:
        st.warning("Dados de Período ou Minutos (Min_Num) não disponíveis para esta análise.")

with aba_clusters:
    st.markdown("#### Ações por zonas de intensidade (Jogo Atual)")
    
    cluster_cols = st.columns(3)
    
    # Somando as variáveis do jogo selecionado
    soma_jogo = df_jogo_atleta.sum(numeric_only=True)
    
    with cluster_cols[0]:
        st.markdown("**🏃 Moderada (V4)**")
        st.metric("Esforços V4", f"{int(soma_jogo.get('V4 To8 Eff', 0))}")
        st.metric("Distância V4", f"{soma_jogo.get('V4 Dist', 0):.1f} m")

    with cluster_cols[1]:
        st.markdown("**⚡ Alta/Sprints (V5+)**")
        st.metric("Esforços V5+", f"{int(soma_jogo.get('V5 To8 Eff', 0) + soma_jogo.get('V6 To8 Eff', 0))}")
        st.metric("Distância V5", f"{soma_jogo.get('V5 Dist', 0):.1f} m")

    with cluster_cols[2]:
        st.markdown("**🛑 Mecânica (Acel/Dec)**")
        st.metric("Acelerações (>3m/s²)", f"{int(soma_jogo.get('Acc3 Eff', 0))}")
        st.metric("Desacelerações (<-3m/s²)", f"{int(soma_jogo.get('Dec3 Eff', 0))}")

with aba_insights:
    st.markdown("#### 💡 Insights Automatizados do Jogo")
    
    hia_diff = df_comp[df_comp['Métrica'] == 'HIA']['Diferença %'].values[0]
    dist_diff = df_comp[df_comp['Métrica'] == 'Total Distance']['Diferença %'].values[0]
    
    if hia_diff > 10:
        st.success(f"📈 **Alta Intensidade Elevada:** O atleta teve um número de ações de alta intensidade (HIA) {hia_diff:.1f}% acima da sua média. Monitorar fadiga muscular nos próximos dias.")
    elif hia_diff < -10:
        st.warning(f"📉 **Queda de Intensidade:** O atleta realizou {abs(hia_diff):.1f}% menos ações intensas do que seu padrão normal.")
    else:
        st.info("⚖️ **Intensidade Padrão:** O HIA do atleta manteve-se na sua média histórica.")
        
    st.markdown(f"- O Volume Total (Distância) variou **{dist_diff:+.1f}%** em relação à média.")
