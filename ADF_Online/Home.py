from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.UI.components as ui
import Source.UI.visual as visual

st.set_page_config(
    page_title=f"Sports Hub | {visual.CLUBE['sigla']}",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 1. CHAMA O NOVO MENU SUPERIOR (E o fundo padrão)
ui.renderizar_menu_superior(pagina_atual="Home")

# CSS exclusivo do painel de resumos (Hero Banner da Home)
st.markdown(
    f"""
    <style>
        .home-hero {{
            background: linear-gradient(120deg, {visual.CORES['fundo_card']} 0%, #0F172A 100%);
            border: 1px solid #334155;
            border-radius: 16px;
            padding: 18px 22px;
            margin: 6px 0 14px 0;
        }}
        .home-title {{
            color: {visual.CORES['texto_escuro']};
            font-size: 1.8rem;
            font-weight: 800;
            margin: 0;
        }}
        .home-subtitle {{
            color: {visual.CORES['texto_claro']};
            margin: 6px 0 0 0;
            font-size: 0.98rem;
        }}
        .home-chip-wrap {{
            display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px;
        }}
        .home-chip {{
            background: #1E293B;
            border: 1px solid #334155;
            color: {visual.CORES['texto_escuro']};
            padding: 6px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

def _safe_dates(series):
    dt = pd.to_datetime(series, errors="coerce")
    return dt.dropna()

ui.renderizar_cabecalho(
    "Sports Performance Hub",
    "Painel central de análise fisiológica e tática",
)

st_autorefresh(interval=2500, limit=None, key="home_tracker_refresh")
hora_atualizacao = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

try:
    df, df_recordes = load_global_data(hora_atualizacao)

    if df is not None and not df.empty:
        st.session_state["df_global"] = df
        st.session_state["df_recordes"] = df_recordes

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

        st.markdown(
            f"""
            <section class="home-hero">
                <p class="home-title">Centro de Comando - {visual.CLUBE['sigla']}</p>
                <p class="home-subtitle">Visão operacional de prontidão, carga e monitoramento em tempo real.</p>
                <div class="home-chip-wrap">
                    <span class="home-chip">Atualização: {dt_mod.strftime('%d/%m/%Y %H:%M:%S') if dt_mod else 'indisponível'}</span>
                    <span class="home-chip">Último jogo: {last_game.strftime('%d/%m/%Y') if last_game is not None else 'indisponível'}</span>
                    <span class="home-chip">Atletas ativos (7d): {atletas_ativos_7d}</span>
                    <span class="home-chip">Média HIA: {media_hia:.1f}</span>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            ui.renderizar_card_kpi("Total de Atletas", str(df["Name"].nunique()) if "Name" in df.columns else "0", icone="👥")
        with c2:
            ui.renderizar_card_kpi("Jogos Analisados", str(df["Data"].nunique()) if "Data" in df.columns else "0", icone="📆")
        with c3:
            ui.renderizar_card_kpi("Linhas de GPS", str(len(df)), cor_borda=visual.CORES["ok_prontidao"], icone="📡")
        with c4:
            ui.renderizar_card_kpi("Recordes Mapeados", str(df_recordes["Name"].nunique()) if "Name" in df_recordes.columns else str(len(df_recordes)), cor_borda=visual.CORES["secundaria"], icone="🏆")

        col_left, col_right = st.columns([1.4, 1])
        with col_left:
            st.markdown("#### Ranking de Carga (HIA)")
            if {"Name", "HIA"}.issubset(df.columns):
                ranking_hia = (df.groupby("Name", as_index=False)["HIA"].sum().sort_values("HIA", ascending=False).head(8))
                ranking_hia["HIA"] = ranking_hia["HIA"].round(1)
                st.dataframe(ranking_hia.rename(columns={"Name": "Atleta", "HIA": "HIA Acumulado"}), width='stretch', hide_index=True)
            else:
                st.info("Sem colunas suficientes para gerar ranking HIA.")

        with col_right:
            st.markdown("#### Sessões por Dia")
            if "Data" in df.columns:
                series = pd.to_datetime(df["Data"], errors="coerce").dropna().dt.date
                if not series.empty:
                    freq = pd.Series(series).value_counts().sort_index().tail(10)
                    st.bar_chart(freq)
                else:
                    st.info("Sem datas válidas para montar o gráfico.")
            else:
                st.info("Sem coluna Data para montar o gráfico.")
    else:
        st.warning("Ficheiro Excel vazio.")
except Exception as e:
    st.error(f"Erro: {e}")