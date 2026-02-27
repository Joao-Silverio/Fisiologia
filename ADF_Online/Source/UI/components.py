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
            st.image(Image.open(visual.CLUBE["logo_path"]), use_container_width=True)
        except:
            st.error("Logo")
    with c2:
        html_cabecalho = f"<h1 style='color: {visual.CORES['texto_escuro']}; margin-bottom: 0px;'>{titulo}</h1><p style='color: {visual.CORES['texto_claro']}; margin-top: 0px; font-size: 16px;'>{subtitulo} | {visual.CLUBE['nome']}</p>"
        st.markdown(html_cabecalho, unsafe_allow_html=True)
    st.markdown("<hr style='border: 1px solid #334155; margin-top: 10px; margin-bottom: 20px;'/>", unsafe_allow_html=True)

def renderizar_card_kpi(titulo, valor, cor_borda=visual.CORES["primaria"], icone="📊", delta=None, delta_color="normal"):
    """Gera um cartão com altura fixa e alinhamento vertical garantido."""
    
    # 1. LÓGICA DO DELTA (Sempre ocupa espaço, mesmo se for None)
    if delta is not None:
        delta_str = str(delta).strip()
        is_negative = delta_str.startswith("-")
        delta_texto = delta_str.replace("+", "").replace("-", "").strip()
        
        if delta_color == "normal":
            cor_d = visual.CORES["alerta_fadiga"] if is_negative else visual.CORES["ok_prontidao"]
            seta = "▼" if is_negative else "▲"
        elif delta_color == "inverse":
            cor_d = visual.CORES["ok_prontidao"] if is_negative else visual.CORES["alerta_fadiga"]
            seta = "▼" if is_negative else "▲"
        else:
            cor_d = visual.CORES["texto_claro"]
            seta = "•"
        html_delta = f"<div style='margin-top: 4px; font-size: 14px; font-weight: 700; color: {cor_d};'>{seta} {delta_texto}</div>"
    else:
        # Se não houver delta, criamos um bloco invisível com a mesma altura para não desregular o card
        html_delta = f"<div style='margin-top: 4px; font-size: 14px; font-weight: 700; opacity: 0; user-select: none;'>&nbsp;</div>"

    # 2. ESTILIZAÇÃO (Fixamos a altura mínima para todos serem iguais)
    fundo_gradiente = f"linear-gradient(135deg, {cor_borda}1A 0%, {visual.CORES['fundo_card']} 100%)"
    sombra_glow = f"0 4px 15px -3px {cor_borda}33"

    # height: 100% e min-height garantem que fiquem alinhados na mesma linha de colunas
    style_div = f"background: {fundo_gradiente}; border-radius: 12px; padding: 18px; box-shadow: {sombra_glow}; border-left: 6px solid {cor_borda}; display: flex; flex-direction: column; justify-content: center; min-height: 140px; height: 100%;"
    style_titulo = f"color: {visual.CORES['texto_claro']}; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;"
    style_valor = f"color: {visual.CORES['texto_escuro']}; font-size: 28px; font-weight: 800; line-height: 1.2;"

    # HTML FINAL (Estrutura rígida)
    html = f"""
    <div style='{style_div}'>
        <div style='{style_titulo}'>{icone} {titulo}</div>
        <div style='{style_valor}'>{valor}</div>
        {html_delta}
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)