from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh

import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.UI.components as ui
import Source.UI.visual as visual

# --------------------------------------------------
# GLOBAL CSS (Apenas para o Hero Banner, adaptado às cores do clube)
# --------------------------------------------------
st.markdown(f"""
<style>
/* HERO */
.hero {{
    background: linear-gradient(135deg, {visual.CORES['fundo_card']}, #020617);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 28px;
    margin-bottom: 20px;
    backdrop-filter: blur(6px);
    box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    animation: fadeUp .6s ease;
    border-left: 4px solid {visual.CORES['primaria']};
}}
.hero-title {{
    font-size: 2.2rem;
    font-weight: 800;
    color: {visual.CORES['texto_escuro']};
}}
.hero-sub {{
    opacity: 0.8;
    font-size: 1rem;
    color: {visual.CORES['texto_claro']};
}}
.hero-chips {{
    margin-top: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}}
.hero-chip {{
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    padding: 6px 12px;
    border-radius: 999px;
    font-size: 0.75rem;
    color: {visual.CORES['texto_escuro']};
    font-weight: 600;
}}
/* ANIMATION */
@keyframes fadeUp {{
    0% {{opacity:0; transform:translateY(10px)}}
    100% {{opacity:1; transform:translateY(0)}}
}}
</style>
""", unsafe_allow_html=True)

# --------------------------------------------------
# CABEÇALHO PADRÃO
# --------------------------------------------------
ui.renderizar_cabecalho(
    "Sports Performance Hub",
    "Painel central de análise fisiológica e tática",
)

# --------------------------------------------------
# AUTO REFRESH
# --------------------------------------------------
st_autorefresh(interval=5000, limit=None, key="home_refresh")

# --------------------------------------------------
# UTILS
# --------------------------------------------------
def _safe_dates(series):
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dropna()

# --------------------------------------------------
# DATA LOAD
# --------------------------------------------------
hora_atualizacao = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

try:
    df, df_recordes = load_global_data(hora_atualizacao)

    if df is not None and not df.empty:
        st.session_state["df_global"] = df
        st.session_state["df_recordes"] = df_recordes

        # -----------------------------
        # CÁLCULO DE MÉTRICAS
        # -----------------------------
        dt_mod = datetime.fromtimestamp(hora_atualizacao) if hora_atualizacao else None
        dt_series = _safe_dates(df["Data"]) if "Data" in df.columns else pd.Series(dtype="datetime64[ns]")
        last_game = dt_series.max() if not dt_series.empty else None
        
        window_start = (datetime.now() - timedelta(days=7)).date()
        atletas_ativos_7d = (
            df.loc[pd.to_datetime(df["Data"], errors="coerce").dt.date >= window_start, "Name"].nunique()
            if "Name" in df.columns and "Data" in df.columns
            else 0
        )
        media_hia = float(df["HIA"].mean()) if "HIA" in df.columns else 0.0

        # --------------------------------------------------
        # HERO BANNER (Destaque Principal)
        # --------------------------------------------------
        st.markdown(f"""
        <div class="hero">
            <div class="hero-title">
                ⚡ Centro de Comando — {visual.CLUBE['sigla']}
            </div>
            <div class="hero-sub">
                Visão operacional de prontidão, carga fisiológica e monitoramento em tempo real
            </div>
            <div class="hero-chips">
                <div class="hero-chip">📡 Atualização: {dt_mod.strftime('%d/%m %H:%M') if dt_mod else '—'}</div>
                <div class="hero-chip">⚽ Último jogo: {last_game.strftime('%d/%m/%Y') if last_game else '—'}</div>
                <div class="hero-chip">👥 Atletas ativos (7d): {atletas_ativos_7d}</div>
                <div class="hero-chip">🔥 Média HIA: {media_hia:.1f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # --------------------------------------------------
        # KPI CARDS
        # --------------------------------------------------
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            ui.renderizar_card_kpi(
                "Total de Atletas",
                str(df["Name"].nunique()) if "Name" in df.columns else "0",
                icone="👥",
                cor_borda=visual.CORES["primaria"]
            )
        with c2:
            ui.renderizar_card_kpi(
                "Jogos Analisados",
                str(df["Data"].nunique()) if "Data" in df.columns else "0",
                icone="📅",
                cor_borda=visual.CORES["secundaria"]
            )
        with c3:
            ui.renderizar_card_kpi(
                "Linhas de GPS",
                str(len(df)),
                icone="📡",
                cor_borda=visual.CORES["ok_prontidao"]
            )
        with c4:
            total_minutos = df["Min_Num"].sum() if "Min_Num" in df.columns else 0
            ui.renderizar_card_kpi(
                "Tempo Monitorado",
                f"{total_minutos / 60:.0f}h",
                icone="⏱️",
                cor_borda=visual.CORES["aviso_carga"]
            )

        st.divider()

        # --------------------------------------------------
        # GRÁFICO: DISPERSÃO CARGA VS INTENSIDADE
        # --------------------------------------------------
        st.markdown("#### 🔵 Dispersão do Plantel — Carga vs Intensidade")

        colunas_necessarias = {'Name', 'Data_Display', 'Total Distance', 'HIA', 'Player Load', 'Min_Num'}
        
        if colunas_necessarias.issubset(df.columns):
            lista_jogos = df['Data_Display'].dropna().unique().tolist()
            
            if lista_jogos:
                # Usa uma coluna menor apenas para o selectbox não ficar esticado na tela toda
                col_sel, _ = st.columns([1, 3])
                with col_sel:
                    jogo_home = st.selectbox("Selecione o Jogo:", lista_jogos, key="sel_scatter_home")
                
                df_home_jogo = df[df['Data_Display'] == jogo_home]
                
                df_home_agg  = df_home_jogo.groupby('Name').agg(
                    Distancia=('Total Distance', 'sum'),
                    HIA=('HIA', 'sum'),
                    Player_Load=('Player Load', 'sum'),
                    Minutos=('Min_Num', 'max')
                ).reset_index()

                media_dist_h = df_home_agg['Distancia'].mean()
                media_hia_h  = df_home_agg['HIA'].mean()

                # Cores por quadrante
                def cor_quadrante(row):
                    if row['Distancia'] >= media_dist_h and row['HIA'] >= media_hia_h: return '#22C55E'  # ideal
                    if row['Distancia'] < media_dist_h  and row['HIA'] < media_hia_h:  return '#EF4444'  # alerta
                    return '#F59E0B'  # misto

                df_home_agg['cor'] = df_home_agg.apply(cor_quadrante, axis=1)

                fig_home_scatter = go.Figure()
                fig_home_scatter.add_trace(go.Scatter(
                    x=df_home_agg['Distancia'], y=df_home_agg['HIA'],
                    mode='markers+text', text=df_home_agg['Name'],
                    textposition='top center', textfont=dict(size=10),
                    marker=dict(size=df_home_agg['Player_Load'] / df_home_agg['Player_Load'].max() * 30 + 8,
                                color=df_home_agg['cor'], line=dict(width=1, color='white')),
                    hovertemplate="<b>%{text}</b><br>Distância: %{x:.0f}m<br>HIA: %{y:.0f}<extra></extra>"
                ))

                # Linhas de média (quadrantes)
                fig_home_scatter.add_vline(x=media_dist_h, line_dash="dash", line_color="rgba(255,255,255,0.2)")
                fig_home_scatter.add_hline(y=media_hia_h,  line_dash="dash", line_color="rgba(255,255,255,0.2)")

                # Labels dos quadrantes adaptadas e encurtadas para telas menores
                fig_home_scatter.add_annotation(text="✅ Alto Vol + Alta Int", x=df_home_agg['Distancia'].max(), y=df_home_agg['HIA'].max(), showarrow=False, font=dict(color='#22C55E', size=11), xanchor='right', yanchor='bottom')
                fig_home_scatter.add_annotation(text="⚠️ Baixo Vol + Baixa Int", x=df_home_agg['Distancia'].min(), y=df_home_agg['HIA'].min(), showarrow=False, font=dict(color='#EF4444', size=11), xanchor='left', yanchor='top')

                fig_home_scatter.update_layout(
                    height=450, template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    xaxis_title="Distância Total (m)", yaxis_title="HIA Total",
                    margin=dict(t=10, b=10, l=10, r=10)
                )
                st.plotly_chart(fig_home_scatter, width='stretch', key="plot_home_scatter")

                # Legenda Responsiva em HTML (Evita quebrar em telas pequenas)
                st.markdown("""
                    <div style='display:flex; flex-wrap:wrap; gap:20px; font-size:0.9rem; padding-top:10px; justify-content:center;'>
                        <span style='color:#22C55E;'>🟢 <b>Alto Volume + Alta Intensidade</b> (Ideal)</span>
                        <span style='color:#F59E0B;'>🟡 <b>Misto</b> (Analisar individualmente)</span>
                        <span style='color:#EF4444;'>🔴 <b>Baixo Volume + Baixa Intensidade</b> (Alerta)</span>
                        <span style='color:#94A3B8;'>⚫ <b>Tamanho da bolha:</b> Player Load</span>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.info("Nenhum jogo encontrado no histórico.")
        else:
            st.info("Colunas insuficientes para o gráfico de dispersão.")

    else:
        st.warning("Ficheiro Excel vazio.")

except Exception as e:
    st.error(f"Erro: {e}")