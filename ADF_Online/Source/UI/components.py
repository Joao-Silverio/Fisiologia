import streamlit as st
from PIL import Image
import Source.UI.visual as visual

def renderizar_cabecalho(titulo, subtitulo):
    """Gera um cabeçalho padrão, com a logo do clube e linha de separação moderna."""
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
    """Gera um cartão SaaS colorido com suporte a Delta."""
    
    # 1. TRUQUE DA ALTURA: Se tem Delta, desenha. Se não tem, desenha invisível (opacity: 0)
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
        else: # "off"
            cor_d = visual.CORES["texto_claro"]
            seta = "•"

        html_delta = f"<div style='margin-top: 4px; font-size: 14px; font-weight: 700; color: {cor_d};'>{seta} {delta_texto}</div>"
    else:
        # Delta fantasma para segurar o espaço perfeitamente alinhado!
        html_delta = f"<div style='margin-top: 4px; font-size: 14px; font-weight: 700; opacity: 0; user-select: none;'>• -</div>"

    # 2. TRUQUE DA COR: Gradiente e Brilho (Glow)
    # Adicionamos "1A" no fim do HEX da cor para dar ~10% de transparência e pintar o fundo suavemente
    fundo_gradiente = f"linear-gradient(135deg, {cor_borda}1A 0%, {visual.CORES['fundo_card']} 100%)"
    # Adicionamos "33" no fim do HEX para criar uma sombra suave da mesma cor do cartão (20% opacidade)
    sombra_glow = f"0 4px 15px -3px {cor_borda}33"

    style_div = f"background: {fundo_gradiente}; border-radius: 12px; padding: 20px; box-shadow: {sombra_glow}; border-left: 6px solid {cor_borda}; margin-bottom: 15px; display: flex; flex-direction: column; justify-content: space-between; height: 100%; min-height: 130px;"
    style_titulo = f"color: {visual.CORES['texto_claro']}; font-size: 13px; font-weight: 600; text-transform: uppercase;"
    style_valor = f"color: {visual.CORES['texto_escuro']}; font-size: 32px; font-weight: 800; margin-top: 8px;"

    # HTML FINAL
    html = f"<div style='{style_div}'><span style='{style_titulo}'>{icone} {titulo}</span><span style='{style_valor}'>{valor}</span>{html_delta}</div>"
    
    st.markdown(html, unsafe_allow_html=True)