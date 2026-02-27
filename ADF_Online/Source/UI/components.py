# ADF_Online/ui_components.py
import streamlit as st
from PIL import Image
import visual

def renderizar_cabecalho(titulo, subtitulo):
    """Gera um cabeçalho padrão, com a logo do clube e linha de separação moderna."""
    c1, c2 = st.columns([1, 10])
    with c1:
        try:
            st.image(Image.open(visual.CLUBE["logo_path"]), use_container_width=True)
        except:
            st.error("Logo")
    with c2:
        st.markdown(f"""
            <h1 style='color: {visual.CORES["texto_escuro"]}; margin-bottom: 0px;'>{titulo}</h1>
            <p style='color: {visual.CORES["texto_claro"]}; margin-top: 0px; font-size: 16px;'>{subtitulo} | {visual.CLUBE["nome"]}</p>
        """, unsafe_allow_html=True)
    st.markdown("<hr style='border: 1px solid #E2E8F0; margin-top: 10px; margin-bottom: 20px;'/>", unsafe_allow_html=True)

def renderizar_card_kpi(titulo, valor, cor_borda=visual.CORES["primaria"], icone="📊"):
    """Gera um cartão com sombra, estilo painel SaaS moderno."""
    html = f"""
    <div style="
        background-color: {visual.CORES['fundo_card']};
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border-left: 6px solid {cor_borda};
        margin-bottom: 15px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;">
        <span style="color: {visual.CORES['texto_claro']}; font-size: 14px; font-weight: 600; text-transform: uppercase;">{icone} {titulo}</span>
        <span style="color: {visual.CORES['texto_escuro']}; font-size: 32px; font-weight: 800; margin-top: 8px;">{valor}</span>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)