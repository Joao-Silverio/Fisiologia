import streamlit as st
import pandas as pd
import warnings

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
    st.write(
        "Use este bloco para mostrar a evolução do atleta em cada jogo (distância, HIA, Player Load, ações em alta intensidade etc.)."
    )

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown("**Linha do tempo (estrutura sugerida)**")
        st.dataframe(
            pd.DataFrame(
                {
                    "Jogo": df_atleta_total.sort_values('Data', ascending=False)['Data_Display'].drop_duplicates().head(8),
                    "Status": "Pendente",
                    "Observação": "Adicionar variação vs jogo anterior"
                }
            ),
            use_container_width=True,
            hide_index=True
        )
    with col_b:
        st.info("Sugestão: destacar recordes pessoais, tendência de melhora e sinais de queda de rendimento.")

with aba_comparativo:
    st.markdown("#### Diferenças do jogo selecionado para outros jogos")
    st.write("Estrutura para comparação direta contra 1 jogo de referência ou médias de blocos (últimos 3/5 jogos).")

    opcoes_referencia = ["Último jogo", "Média últimos 3", "Média últimos 5", "Melhor jogo da temporada"]
    st.selectbox("Base de comparação", opcoes_referencia, index=1)

    st.dataframe(
        pd.DataFrame(
            {
                "Métrica": ["Total Distance", "Player Load", "HIA", "V4 To8 Eff"],
                "Jogo Atual": ["-", "-", "-", "-"],
                "Referência": ["-", "-", "-", "-"],
                "Diferença": ["-", "-", "-", "-"]
            }
        ),
        use_container_width=True,
        hide_index=True
    )

with aba_minutagem:
    st.markdown("#### Minutagem e distribuição por período")
    st.write("Espaço para mostrar minutos jogados, consistência de participação e carga relativa por tempo.")

    st.dataframe(
        pd.DataFrame(
            {
                "Recorte": ["Jogo Atual", "Média Temporada", "Últimos 5 Jogos", "Pico de Minutagem"],
                "Minutos": ["-", "-", "-", "-"],
                "% 1º Tempo": ["-", "-", "-", "-"],
                "% 2º Tempo": ["-", "-", "-", "-"]
            }
        ),
        use_container_width=True,
        hide_index=True
    )

with aba_clusters:
    st.markdown("#### Clusters de velocidade e aceleração")
    st.write("Área dedicada a segmentar ações por zonas de intensidade e perfil de aceleração/desaceleração.")

    cluster_cols = st.columns(3)
    cluster_labels = ["Cluster 1 - Baixa Intensidade", "Cluster 2 - Moderada", "Cluster 3 - Alta Intensidade"]

    for i, label in enumerate(cluster_labels):
        with cluster_cols[i]:
            st.markdown(f"**{label}**")
            st.caption("Definir ranges de velocidade/aceleração e listar volume de ações por jogo.")

    st.dataframe(
        pd.DataFrame(
            {
                "Cluster": ["Baixa", "Moderada", "Alta"],
                "Velocidade (km/h)": ["-", "-", "-"],
                "Aceleração (m/s²)": ["-", "-", "-"],
                "Ações no jogo": ["-", "-", "-"]
            }
        ),
        use_container_width=True,
        hide_index=True
    )

with aba_insights:
    st.markdown("#### Sugestões de leitura técnica")
    st.markdown(
        """
        - Comparar o jogo atual com a tendência dos últimos jogos para validar melhora real.
        - Cruzar minutagem com métricas de alta intensidade para avaliar eficiência por minuto.
        - Monitorar clusters de alta aceleração para ajustar carga e prevenção de risco.
        - Enviar ao atleta um resumo pós-jogo com 3 pontos: evolução, diferença para referência e foco do próximo jogo.
        """
    )
