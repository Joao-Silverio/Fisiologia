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
# FILTROS: HIERARQUIA DE FUNIL (JOGO -> ATLETA -> PERÍODO)
# =====================================================================
st.markdown("### 🔍 Seleção de Análise")

with st.container():
    col_j, col_a, col_p = st.columns([2, 2, 1])
    
    # 1. Seleção do Jogo
    lista_jogos = df_completo.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
    with col_j:
        jogo_destaque_display = st.selectbox("🎯 Jogo em Destaque:", lista_jogos)
    
    jogo_destaque_data = df_completo[df_completo['Data_Display'] == jogo_destaque_display]['Data'].iloc[0]
    df_jogo_base = df_completo[df_completo['Data'] == jogo_destaque_data]

    # 2. Seleção do Atleta
    lista_atletas = sorted(df_jogo_base['Name'].dropna().unique())
    with col_a:
        atleta_selecionado = st.selectbox("🏃 Atleta:", lista_atletas)
        
    # 3. Seleção do Período
    with col_p:
        opcoes_periodo = ["Jogo Completo", "1º Tempo", "2º Tempo"]
        periodo_selecionado = st.selectbox("⏱️ Período:", opcoes_periodo)

# =====================================================================
# PROCESSAMENTO DOS DADOS COM BASE NOS FILTROS
# =====================================================================
# Isola todos os dados do atleta selecionado
df_atleta_total = df_completo[df_completo['Name'] == atleta_selecionado].copy()

# Aplica o filtro de período de forma robusta procurando '1' ou '2' na coluna Período
if periodo_selecionado == "1º Tempo":
    df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('1', na=False)]
elif periodo_selecionado == "2º Tempo":
    df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('2', na=False)]

# Separação: Jogo Destaque vs Histórico Restante (já com o período filtrado)
df_jogo_atleta = df_atleta_total[df_atleta_total['Data'] == jogo_destaque_data]
df_historico_atleta = df_atleta_total[df_atleta_total['Data'] != jogo_destaque_data]

# =====================================================================
# KPIs DINÂMICOS DA PÁGINA INDIVIDUAL
# =====================================================================
st.markdown(f"#### 👤 Painel Individual: {atleta_selecionado} | Jogo {jogo_destaque_display} ({periodo_selecionado})")

total_jogos = df_atleta_total['Data'].nunique()

# NOVA LÓGICA DE MINUTAGEM: Pega o valor máximo (último número) de cada período jogado
if 'Min_Num' in df_jogo_atleta.columns and not df_jogo_atleta.empty:
    # Agrupa por período e pega o máximo, depois soma (se for o jogo completo, soma T1+T2)
    total_minutos = df_jogo_atleta.groupby('Período')['Min_Num'].max().sum()
else:
    total_minutos = 0

if 'Min_Num' in df_atleta_total.columns and total_jogos > 0:
    # Para a média histórica: descobre os minutos de cada jogo (somando os máx de cada período) e tira a média
    minutos_por_jogo = df_atleta_total.groupby(['Data', 'Período'])['Min_Num'].max().groupby('Data').sum()
    media_minutos = minutos_por_jogo.mean()
else:
    media_minutos = 0

col_kpi_1, col_kpi_2, col_kpi_3 = st.columns(3)

with col_kpi_1:
    ui.renderizar_card_kpi("Jogos no Histórico", f"{total_jogos}", cor_borda=visual.CORES["primaria"])
with col_kpi_2:
    ui.renderizar_card_kpi(f"Minutagem ({periodo_selecionado})", f"{total_minutos:.0f} min", cor_borda=visual.CORES["secundaria"])
with col_kpi_3:
    ui.renderizar_card_kpi(f"Média de Minutos ({periodo_selecionado})", f"{media_minutos:.0f} min", cor_borda=visual.CORES["aviso_carga"])

# =====================================================================
# ABAS DE ANÁLISE JOGO A JOGO COM DADOS REAIS
# =====================================================================
st.markdown("### 🧭 Estrutura de Análise Jogo a Jogo")

aba_timeline, aba_comparativo, aba_minutagem, aba_clusters, aba_insights = st.tabs([
    "📈 Linha do tempo",
    "⚔️ Comparativo",
    "⏱️ Minutagens",
    "🏃 Clusters Intensidade",
    "💡 Insights"
])

# ----------------- ABA 1: TIMELINE -----------------
with aba_timeline:
    st.markdown("#### Evolução de performance por partida")
    
    cols_analise = ['Total Distance', 'Player Load', 'HIA']
    # Agrupa os dados por jogo para construir a linha do tempo do período selecionado
    df_evolucao = df_atleta_total.groupby(['Data', 'Data_Display'])[cols_analise].sum().reset_index().sort_values('Data')
    
    if not df_evolucao.empty:
        col_a, col_b = st.columns([2, 1])
        with col_a:
            metrica_grafico = st.selectbox("Selecione a Métrica:", cols_analise, key="metrica_timeline")
            
            fig = px.line(
                df_evolucao, 
                x='Data_Display', 
                y=metrica_grafico, 
                markers=True,
                title=f"Evolução: {metrica_grafico} ({periodo_selecionado})"
            )
            fig.update_layout(visual.PLOTLY_TEMPLATE['layout'])
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            st.markdown("**Resumo (Últimos 5 jogos)**")
            df_resumo = df_evolucao[['Data_Display', metrica_grafico]].tail(5).sort_values('Data_Display', ascending=False)
            df_resumo.rename(columns={'Data_Display': 'Jogo'}, inplace=True)
            st.dataframe(df_resumo, use_container_width=True, hide_index=True)
    else:
        st.info("Não há dados suficientes para gerar a linha do tempo neste recorte.")

# ----------------- ABA 2: COMPARATIVO -----------------
with aba_comparativo:
    st.markdown("#### Diferenças do jogo selecionado para a sua média histórica")
    
    metricas_alvo = ["Total Distance", "Player Load", "HIA", "V5 To8 Eff"]
    
    if not df_jogo_atleta.empty and not df_historico_atleta.empty:
        # Jogo Atual
        jogo_atual_stats = df_jogo_atleta[metricas_alvo].sum()
        
        # Média Histórica do atleta
        df_agrupado_hist = df_historico_atleta.groupby('Data')[metricas_alvo].sum()
        media_historica = df_agrupado_hist.mean().fillna(0)
        
        df_comp = pd.DataFrame({
            "Métrica": metricas_alvo,
            "Jogo Atual": jogo_atual_stats.values.round(1),
            "Média (Outros Jogos)": media_historica.values.round(1)
        })
        
        df_comp['Diferença %'] = ((df_comp['Jogo Atual'] - df_comp['Média (Outros Jogos)']) / df_comp['Média (Outros Jogos)'] * 100).fillna(0)
        
        def formatar_cor(val):
            cor = visual.CORES["ok_prontidao"] if val >= 0 else visual.CORES["alerta_fadiga"]
            return f'<span style="color:{cor}; font-weight:bold;">{val:+.1f}%</span>'
        
        df_comp_display = df_comp.copy()
        df_comp_display['Diferença %'] = df_comp_display['Diferença %'].apply(formatar_cor)
        
        st.write(df_comp_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.warning("Não há dados suficientes para gerar o comparativo. O atleta precisa ter participado de outros jogos.")

# ----------------- ABA 3: MINUTAGEM -----------------
with aba_minutagem:
    st.markdown("#### Resumo de Minutagem")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.info(f"**{periodo_selecionado}:** {total_minutos:.0f} minutos jogados na partida selecionada.")
    with col2:
        st.info(f"**Média Histórica ({periodo_selecionado}):** {media_minutos:.0f} minutos.")
        
    if periodo_selecionado == "Jogo Completo":
        st.write("Dica: Selecione '1º Tempo' ou '2º Tempo' no filtro superior para ver a quebra exata de minutos por etapa.")

# ----------------- ABA 4: CLUSTERS -----------------
with aba_clusters:
    st.markdown(f"#### Ações por zonas de intensidade (Jogo Atual - {periodo_selecionado})")
    
    cluster_cols = st.columns(3)
    soma_jogo = df_jogo_atleta.sum(numeric_only=True)
    
    with cluster_cols[0]:
        st.markdown("**🏃 Moderada (V4)**")
        st.metric("Esforços V4", f"{int(soma_jogo.get('V4 To8 Eff', 0))}")
        st.metric("Distância V4", f"{soma_jogo.get('V4 Dist', 0):.1f} m")

    with cluster_cols[1]:
        st.markdown("**⚡ Alta/Sprints (V5+)**")
        st.metric("Esforços V5+", f"{int(soma_jogo.get('V5 To8 Eff', 0) + soma_jogo.get('V6 To8 Eff', 0))}")
        st.metric("Distância V5+", f"{soma_jogo.get('V5 Dist', 0):.1f} m")

    with cluster_cols[2]:
        st.markdown("**🛑 Mecânica (Acel/Dec)**")
        st.metric("Acelerações (>3m/s²)", f"{int(soma_jogo.get('Acc3 Eff', 0))}")
        st.metric("Desacelerações (<-3m/s²)", f"{int(soma_jogo.get('Dec3 Eff', 0))}")

# ----------------- ABA 5: INSIGHTS -----------------
with aba_insights:
    st.markdown("#### 💡 Insights Automatizados")
    
    if not df_jogo_atleta.empty and not df_historico_atleta.empty:
        hia_diff = df_comp[df_comp['Métrica'] == 'HIA']['Diferença %'].values[0]
        dist_diff = df_comp[df_comp['Métrica'] == 'Total Distance']['Diferença %'].values[0]
        
        if hia_diff > 10:
            st.success(f"📈 **Alta Intensidade Elevada:** O atleta teve um volume de ações de alta intensidade (HIA) {hia_diff:.1f}% acima da sua média no {periodo_selecionado.lower()}. Monitorar fadiga muscular/recuperação.")
        elif hia_diff < -10:
            st.warning(f"📉 **Queda de Intensidade:** O atleta realizou {abs(hia_diff):.1f}% menos ações intensas do que o seu padrão normal neste recorte.")
        else:
            st.info(f"⚖️ **Intensidade Padrão:** O HIA do atleta manteve-se equilibrado com sua média histórica no {periodo_selecionado.lower()}.")
            
        st.markdown(f"- O Volume de **Distância Total** no {periodo_selecionado.lower()} variou **{dist_diff:+.1f}%** em relação à média do atleta.")
    else:
        st.write("Sem base histórica suficiente para gerar insights comparativos.")
