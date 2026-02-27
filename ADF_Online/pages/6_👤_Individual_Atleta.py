import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
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
# KPIs DE PERFORMANCE (DESTAQUE VS MÉDIA DA TEMPORADA)
# =====================================================================
st.markdown(f"#### 📊 Performance: {atleta_selecionado} em {jogo_destaque_display}")

metrics_map = [
    {"label": "Distância Total", "key": "Total Distance", "unit": "m", "color": visual.CORES["primaria"]},
    {"label": "Ações V4+", "key": "V4 To8 Eff", "unit": "", "color": visual.CORES["secundaria"]},
    {"label": "Ações HIA", "key": "HIA", "unit": "", "color": visual.CORES["alerta_fadiga"]},
    {"label": "Carga (PL)", "key": "Player Load", "unit": "", "color": visual.CORES["aviso_carga"]}
]

cols_kpi = st.columns(len(metrics_map))

for i, met in enumerate(metrics_map):
    val_jogo = df_jogo_atleta[met['key']].sum()
    # Média por jogo no histórico
    val_hist = df_historico_atleta.groupby('Data')[met['key']].sum().mean() if not df_historico_atleta.empty else val_jogo
    
    delta_pct = ((val_jogo / val_hist) - 1) * 100 if val_hist > 0 else 0
    
    with cols_kpi[i]:
        ui.renderizar_card_kpi(
            met['label'], 
            f"{val_jogo:.1f}{met['unit']}" if "Dist" in met['key'] else f"{val_jogo:.0f}", 
            cor_borda=met['color'],
            delta=f"{delta_pct:+.1f}% vs Média",
            delta_color="normal" if met['key'] != "Player Load" else "inverse"
        )

# =====================================================================
# GRÁFICO DE EVOLUÇÃO (DESTAQUE COLORIDO)
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

# =====================================================================
# RADAR DE INTENSIDADE (PERFIL DE AÇÕES)
# =====================================================================
st.markdown("### ⏱️ Perfil de Intensidade por Período")

c1, c2 = st.columns(2)
componentes = [c for c in config.COLS_COMPONENTES_HIA if c in df_completo.columns]

for idx, periodo in enumerate([1, 2]):
    with [c1, c2][idx]:
        st.write(f"**{periodo}º Tempo**")
        df_p_jogo = df_jogo_atleta[df_jogo_atleta['Período'] == periodo]
        df_p_hist = df_historico_atleta[df_historico_atleta['Período'] == periodo]
        
        if not df_p_jogo.empty and componentes:
            val_jogo = df_p_jogo[componentes].sum().values
            val_hist = df_p_hist.groupby('Data')[componentes].sum().mean().values if not df_p_hist.empty else val_jogo
            
            fig_rad = go.Figure()
            fig_rad.add_trace(go.Scatterpolar(r=val_hist, theta=componentes, fill='toself', name='Média Temporada', line=dict(color=visual.CORES['texto_claro'])))
            fig_rad.add_trace(go.Scatterpolar(r=val_jogo, theta=componentes, fill='toself', name='Jogo Atual', line=dict(color=visual.CORES['alerta_fadiga'])))
            
            fig_rad.update_layout(
                template='plotly_dark',
                polar=dict(radialaxis=dict(visible=True, showticklabels=False, gridcolor='#334155'),
                           angularaxis=dict(gridcolor='#334155')),
                paper_bgcolor='rgba(0,0,0,0)',
                height=350,
                margin=dict(t=30, b=30, l=50, r=50)
            )
            st.plotly_chart(fig_rad, key=f"radar_ind_{periodo}")
        else:
            st.info(f"Sem dados para o {periodo}º tempo.")