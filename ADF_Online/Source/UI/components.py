import streamlit as st
from PIL import Image
import Source.UI.visual as visual

def renderizar_cabecalho(titulo, subtitulo):
    """Gera um cabeçalho padrão e injeta CSS para subir o conteúdo da página."""
    st.markdown("""
        <style>
            .block-container {
                padding-top: 1.5rem !important;
                padding-bottom: 1rem !important;
            }
        </style>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 10])
    with c1:
        try:
            st.image(Image.open(visual.CLUBE["logo_path"]), width='content')
        except:
            st.error("Logo")
    with c2:
        html_cabecalho = f"<h1 style='color: {visual.CORES['texto_escuro']}; margin-bottom: 0px;'>{titulo}</h1><p style='color: {visual.CORES['texto_claro']}; margin-top: 0px; font-size: 16px;'>{subtitulo} | {visual.CLUBE['nome']}</p>"
        st.markdown(html_cabecalho, unsafe_allow_html=True)
    st.markdown("<hr style='border: 1px solid #334155; margin-top: 10px; margin-bottom: 20px;'/>", unsafe_allow_html=True)

def renderizar_card_kpi(titulo, valor, cor_borda=None, icone="📊", delta=None, delta_color="normal"):
    """
    Gera um cartão KPI com altura fixa e suporte a variações (delta).
    Garante consistência visual mesmo quando o delta é omitido.
    """
    
    # Define a cor padrão caso nenhuma seja enviada
    if cor_borda is None:
        cor_borda = visual.CORES.get("primaria", "#3B82F6")

    # 1. Processamento do Delta (Garante que o espaço vertical sempre exista)
    if delta is not None and str(delta).strip() != "":
        d_str = str(delta).strip()
        is_neg = d_str.startswith("-")
        # Limpeza para exibição
        d_clean = d_str.replace("+", "").replace("-", "").strip()
        
        if delta_color == "normal":
            c_d = visual.CORES["alerta_fadiga"] if is_neg else visual.CORES["ok_prontidao"]
            seta = "▼" if is_neg else "▲"
        elif delta_color == "inverse":
            c_d = visual.CORES["ok_prontidao"] if is_neg else visual.CORES["alerta_fadiga"]
            seta = "▼" if is_neg else "▲"
        else:
            c_d = visual.CORES["texto_claro"]
            seta = "•"
        html_delta = f"<div style='margin-top: 4px; font-size: 14px; font-weight: 700; color: {c_d};'>{seta} {d_clean}</div>"
    else:
        # Espaço reservado invisível para manter todos os cartões com o mesmo tamanho
        html_delta = f"<div style='margin-top: 4px; font-size: 14px; font-weight: 700; opacity: 0; user-select: none;'>&nbsp;</div>"

    # 2. Estilização e Efeitos (Glow e Gradiente)
    fundo = f"linear-gradient(135deg, {cor_borda}1A 0%, {visual.CORES['fundo_card']} 100%)"
    sombra = f"0 4px 15px -3px {cor_borda}33"

    # min-height garante que os cartões fiquem alinhados na mesma linha
    style_div = f"background: {fundo}; border-radius: 12px; padding: 18px; box-shadow: {sombra}; border-left: 6px solid {cor_borda}; display: flex; flex-direction: column; justify-content: center; min-height: 145px; height: 100%;"
    style_tit = f"color: {visual.CORES['texto_claro']}; font-size: 11px; font-weight: 700; text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.5px;"
    style_val = f"color: {visual.CORES['texto_escuro']}; font-size: 26px; font-weight: 800; line-height: 1.1;"

    html = f"""
    <div style='{style_div}'>
        <div style='{style_tit}'>{icone} {titulo}</div>
        <div style='{style_val}'>{valor}</div>
        {html_delta}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)