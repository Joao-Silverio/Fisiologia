from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import plotly.express as px
from streamlit_autorefresh import st_autorefresh

import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.UI.components as ui
import Source.UI.visual as visual

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title=f"Sports Hub | {visual.CLUBE['sigla']}",
    layout="wide",
    initial_sidebar_state="collapsed",
)

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
# MENU SUPERIOR E CABEÇALHO PADRÃO
# --------------------------------------------------
ui.renderizar_menu_superior(pagina_atual="Home")

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
        # KPI CARDS (Usando o padrão do projeto)
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
            ui.renderizar_card_kpi(
                "Recordes",
                str(df_recordes["Name"].nunique()) if "Name" in df_recordes.columns else str(len(df_recordes)),
                icone="🏆",
                cor_borda=visual.CORES["alerta_fadiga"]
            )

        st.divider()

        # --------------------------------------------------
        # RANKING + GRÁFICO
        # --------------------------------------------------
        col_left, col_right = st.columns([1.4, 1])

        # -----------------------------
        # RANKING
        # -----------------------------
        with col_left:
            st.markdown("#### Ranking de Carga (HIA)")

            if {"Name", "HIA"}.issubset(df.columns):
                ranking_hia = (
                    df.groupby("Name", as_index=False)["HIA"]
                    .sum()
                    .sort_values("HIA", ascending=False)
                    .head(8)
                )
                ranking_hia["HIA"] = ranking_hia["HIA"].round(1)

                st.dataframe(
                    ranking_hia.rename(columns={"Name": "Atleta", "HIA": "HIA Acumulado"}),
                    width='stretch',
                    hide_index=True
                )
            else:
                st.info("Sem colunas suficientes para ranking.")

        # -----------------------------
        # GRÁFICO
        # -----------------------------
        with col_right:
            st.markdown("#### Sessões por Dia")

            if "Data" in df.columns:
                series = pd.to_datetime(df["Data"], errors="coerce").dropna().dt.date

                if not series.empty:
                    freq = pd.Series(series).value_counts().sort_index().tail(10)
                    
                    # Gráfico Plotly com design integrado
                    fig = px.bar(
                        x=freq.index,
                        y=freq.values,
                    )
                    # Aplica as cores padrão definidas no seu visual.py
                    fig.update_traces(marker_color=visual.CORES["secundaria"])
                    # 1. Aplica o template base primeiro
                    fig.update_layout(**visual.PLOTLY_TEMPLATE['layout'])
                    
                    # 2. Sobrescreve apenas os atributos específicos deste gráfico
                    fig.update_layout(
                        height=320,
                        margin=dict(l=0, r=0, t=20, b=0),
                        xaxis_title="",
                        yaxis_title=""
                    )
                    st.plotly_chart(fig, width='stretch')
                else:
                    st.info("Sem datas válidas.")
            else:
                st.info("Sem coluna Data.")
    else:
        st.warning("Ficheiro Excel vazio.")

except Exception as e:
    st.error(f"Erro: {e}")
