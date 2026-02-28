import streamlit as st
import pandas as pd
import warnings
import plotly.express as px
import plotly.graph_objects as go

# Importações seguindo o padrão da arquitetura
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
from streamlit_autorefresh import st_autorefresh
import Source.UI.visual as visual
import Source.UI.components as ui

# Configuração de Página
st.set_page_config(page_title=f"Raio-X Individual | {visual.CLUBE['sigla']}", layout="wide", initial_sidebar_state="collapsed")
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

#Chama MENU HORIZONTAL
ui.renderizar_menu_superior(pagina_atual="Atleta") # <-- Nome tem que ser igual ao que você botou lá no nav_items

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
# PROCESSAMENTO DOS DADOS COM BASE NOS FILTROS (CORREÇÃO DA SOMA)
# =====================================================================
# Isola todos os dados do atleta selecionado
df_atleta_total = df_completo[df_completo['Name'] == atleta_selecionado].copy()

# 🚨 CORREÇÃO CRÍTICA DAS MÉTRICAS (EVITAR DUPLICIDADE)
# Mantém APENAS as linhas que são explicitamente de 1º ou 2º tempo.
# Isso impede que o sistema some linhas de "Aquecimento" ou a linha resumo de "Match/Jogo" que o GPS gera.
df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('1|2', regex=True, na=False)]

# Aplica o filtro de período de forma robusta
if periodo_selecionado == "1º Tempo":
    df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('1', na=False)]
elif periodo_selecionado == "2º Tempo":
    df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('2', na=False)]

# Separação: Jogo Destaque vs Histórico Restante (já com o período filtrado e corrigido)
df_jogo_atleta = df_atleta_total[df_atleta_total['Data'] == jogo_destaque_data]
df_historico_atleta = df_atleta_total[df_atleta_total['Data'] != jogo_destaque_data]

# =====================================================================
# KPIs DINÂMICOS DA PÁGINA INDIVIDUAL
# =====================================================================
st.markdown(f"#### 👤 Painel Individual: {atleta_selecionado} | Jogo {jogo_destaque_display} ({periodo_selecionado})")

total_jogos = df_atleta_total['Data'].nunique()

# LÓGICA DE MINUTAGEM: Pega o valor máximo de cada período jogado
if 'Min_Num' in df_jogo_atleta.columns and not df_jogo_atleta.empty:
    total_minutos = df_jogo_atleta.groupby('Período')['Min_Num'].max().sum()
else:
    total_minutos = 0

if 'Min_Num' in df_atleta_total.columns and total_jogos > 0:
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
st.markdown("### 📈 Linha do Tempo da Temporada")

# Métrica selecionável via pills (padrão visuals)
metrica_evol = st.pills("Visualizar Evolução de:", ["Total Distance", "V4 To8 Eff", "HIA", "Player Load"], default="Total Distance")

df_ev = df_atleta_total.groupby(['Data', 'Data_Display'])[metrica_evol].sum().reset_index().sort_values('Data')
df_ev['Status'] = df_ev['Data'].apply(lambda x: 'Destaque' if x == jogo_destaque_data else 'Histórico')

fig_ev = px.bar(
    df_ev, x='Data_Display', y=metrica_evol, color='Status',
    color_discrete_map={'Destaque': visual.CORES['alerta_fadiga'], 'Histórico': visual.CORES['primaria']},
    text_auto='.0f'
)

# Adiciona linha de média
media_geral = df_ev[metrica_evol].mean()
fig_ev.add_hline(y=media_geral, line_dash="dash", line_color=visual.CORES['texto_claro'], 
                 annotation_text=f"Média: {media_geral:.1f}")

fig_ev.update_layout(
    template='plotly_dark',
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    height=400,
    xaxis_title=None,
    yaxis_title=metrica_evol,
    showlegend=False
)

# use_container_width removido conforme solicitado
st.plotly_chart(fig_ev)

# ----------------- ABA 2: COMPARATIVO -----------------
with aba_comparativo:
    st.markdown("#### Diferenças do jogo selecionado para a sua média histórica")
    
    metricas_alvo = ["Total Distance", "Player Load", "HIA", "V5 To8 Eff", "V4 Dist", "V5 Dist"]
    
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

# ----------------- ABA 3: CLUSTERS -----------------
with aba_clusters:
    st.markdown(f"#### Perfil de Intensidade: V4 Dist vs Distância Total ({periodo_selecionado})")
    
    # Agrupa todos os jogos do atleta para calcular a Intensidade (V4 Dist / Total Distance)
    df_intensidade = df_atleta_total.groupby(['Data', 'Data_Display'])[['Total Distance', 'V4 Dist']].sum().reset_index()
    
    # Evita divisão por zero substituindo 0 por 1 no Total Distance para o cálculo
    df_intensidade['Intensidade (%)'] = (df_intensidade['V4 Dist'] / df_intensidade['Total Distance'].replace(0, 1)) * 100

    if not df_jogo_atleta.empty and len(df_intensidade) > 0:
        jogo_atual_row = df_intensidade[df_intensidade['Data'] == jogo_destaque_data]
        
        if not jogo_atual_row.empty:
            intensidade_atual = jogo_atual_row['Intensidade (%)'].values[0]
            dist_total_atual = jogo_atual_row['Total Distance'].values[0]
            v4_atual = jogo_atual_row['V4 Dist'].values[0]
        else:
            intensidade_atual = dist_total_atual = v4_atual = 0

        p33 = df_intensidade['Intensidade (%)'].quantile(0.33)
        p66 = df_intensidade['Intensidade (%)'].quantile(0.66)

        if intensidade_atual >= p66:
            nome_cluster = "🔴 Alta Intensidade"
            desc_cluster = "O atleta correu em alta velocidade numa proporção muito maior que o seu normal."
        elif intensidade_atual >= p33:
            nome_cluster = "🟡 Intensidade Moderada"
            desc_cluster = "A relação entre a distância percorrida e o esforço intenso está no padrão habitual."
        else:
            nome_cluster = "🟢 Baixa Intensidade"
            desc_cluster = "Jogo cadenciado. O volume de V4 foi baixo em relação à distância total percorrida."

        c1, c2, c3 = st.columns([1, 1, 1.5])

        with c1:
            st.markdown("**Jogo Analisado**")
            st.metric("Índice de Intensidade", f"{intensidade_atual:.1f}%")
            st.caption(f"**V4 Dist:** {v4_atual:.1f} m")
            st.caption(f"**Dist Total:** {dist_total_atual:.1f} m")

        with c2:
            st.markdown("**Classificação do Jogo**")
            st.info(f"**{nome_cluster}**\n\n{desc_cluster}")
            st.write(f"Média Histórica do Atleta: **{df_intensidade['Intensidade (%)'].mean():.1f}%**")

        with c3:
            st.markdown("**🏆 Top 3 Jogos Mais Intensos (Histórico)**")
            top_3 = df_intensidade.sort_values(by='Intensidade (%)', ascending=False).head(3)
            
            top_3_display = top_3[['Data_Display', 'Intensidade (%)', 'V4 Dist']].rename(columns={'Data_Display': 'Jogo'})
            top_3_display['Intensidade (%)'] = top_3_display['Intensidade (%)'].round(1).astype(str) + '%'
            top_3_display['V4 Dist'] = top_3_display['V4 Dist'].round(1)
            
            st.dataframe(top_3_display, use_container_width=True, hide_index=True)
    else:
        st.info("Dados insuficientes para calcular clusters de intensidade.")

# ----------------- ABA 4: INSIGHTS -----------------
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
