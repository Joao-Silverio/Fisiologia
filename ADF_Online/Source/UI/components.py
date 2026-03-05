import streamlit as st
from PIL import Image
import Source.UI.visual as visual
from Source.Dados.data_loader import load_global_data, obter_hora_modificacao
import Source.Dados.config as config

def renderizar_cabecalho(titulo, subtitulo):
    """Gera um cabeçalho padrão e injeta CSS para subir o conteúdo da página."""
    #st.markdown("""
     #   <style>
      #      .block-container {
       #         padding-top: 1.5rem !important;
        #        padding-bottom: 1rem !important;
         #   }
        #</style>
    #""", unsafe_allow_html=True)

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

def renderizar_menu_superior(pagina_atual="Home"):
    st.markdown(
        f"""
        <style>
            /* 1. Cores de fundo */
            .stApp {{
                background:
                    radial-gradient(circle at top right, {visual.CORES.get('primaria', '#FDFD96')}20 0%, transparent 35%),
                    radial-gradient(circle at bottom left, {visual.CORES.get('secundaria', '#60A5FA')}22 0%, transparent 40%);
            }}
            
            /* 2. Ocultar o menu lateral nativo */
            [data-testid="stSidebarNav"], [data-testid="stSidebar"], [data-testid="collapsedControl"] {{ 
                display: none !important; 
            }}
            
            /* 3. Ajuste do topo da página para dar espaço ao menu */
            .block-container {{ 
                padding-top: 4rem !important; /* Mais espaço no topo para o menu não bater no header nativo */
            }}
            
            /* 4. Esconder ou afastar o header padrão do Streamlit (onde ficam os 3 pontinhos) */
            header[data-testid="stHeader"] {{
                background: transparent !important;
                height: 0px !important;
            }}

            /* 5. A mágica para capturar a primeira linha de colunas da página (Nosso Menu) */
            div[data-testid="stVerticalBlock"] > div:first-child(-n+3) [data-testid="stHorizontalBlock"]:first-of-type {{
                background: rgba(15, 23, 42, 0.90) !important;
                border: 1px solid #334155 !important; 
                border-radius: 12px !important;
                padding: 12px !important; 
                backdrop-filter: blur(12px) !important; 
                margin-bottom: 2rem !important;
                
                /* Mantém o menu preso no topo, mas abaixo da linha de perigo do header */
                position: sticky !important;
                top: 1rem !important;
                z-index: 999999 !important; 
                box-shadow: 0 10px 30px rgba(0,0,0,0.5) !important;
            }}

            /* 6. ESTILO DOS BOTÕES DO MENU */
            [data-testid="stHorizontalBlock"] button[data-testid="baseButton-primary"] {{
                background-color: #FFFFFF !important;
                border: 1px solid #FFFFFF !important;
                border-radius: 8px !important;
                min-height: 45px !important;
            }}
            [data-testid="stHorizontalBlock"] button[data-testid="baseButton-primary"] * {{
                color: #000000 !important;
                font-weight: 800 !important;
            }}

            [data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"] {{
                background-color: transparent !important;
                border: 1px solid #334155 !important;
                border-radius: 8px !important;
                min-height: 45px !important;
            }}
            [data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"] p {{
                color: {visual.CORES.get('texto_claro', '#94A3B8')} !important;
                font-weight: 600 !important;
            }}
            [data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"]:hover {{
                border-color: {visual.CORES.get('secundaria', '#60A5FA')} !important;
                background-color: rgba(96, 165, 250, 0.1) !important;
            }}
            [data-testid="stHorizontalBlock"] button[data-testid="baseButton-secondary"]:hover p {{
                color: #FFFFFF !important;
            }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    nav_items = [
        ("Home.py", "Home", ":material/home:"),
        ("pages/1_🔴_Live_Tracker.py", "Live", ":material/sensors:"),
        ("pages/2_📊_Relatorio_HIA.py", "Relatório", ":material/analytics:"),
        ("pages/3_🔋_Radar_Fadiga.py", "Fadiga", ":material/battery_charging_full:"),
        ("pages/4_📅_Temporada.py", "Temporada", ":material/calendar_month:"),
        ("pages/5_⚔️_Comparacao_Atletas.py", "Comparação", ":material/compare_arrows:"),
        ("pages/6_👤_Individual_Atleta.py", "Atleta", ":material/person:"),
    ]

    # Usamos container para garantir que a injeção do CSS pegue exatamente esse bloco
    with st.container():
        cols = st.columns(len(nav_items))
        
        for col, (caminho_pagina, label, icon) in zip(cols, nav_items):
            with col:
                is_active = label.lower() in pagina_atual.lower()
                
                # use_container_width é o padrão ouro moderno do Streamlit. 
                # Se falhar localmente, é urgência máxima atualizar seu Streamlit local.
                if st.button(
                    f"{icon} {label}",
                    key=f"nav_top_{pagina_atual}_{label}",
                    width='stretch', 
                    type="primary" if is_active else "secondary",
                ):
                    if not is_active:
                        st.switch_page(caminho_pagina)

# O "run_every" faz apenas este bloco de código rodar a cada 5 segundos
@st.fragment(run_every="5s")
def renderizar_painel_ao_vivo(df_original, pagina_atual):
    """
    Componente inteligente anti-flicker. 
    Ele busca ativamente dados novos sem recarregar os filtros laterais ou menus.
    """
    hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
    df_novo, df_recordes_novo = load_global_data(hora_atual)
    
    # Atualizamos as métricas de sessão de forma invisível
    if not df_novo.empty:
        st.session_state['df_global'] = df_novo
        st.session_state['df_recordes'] = df_recordes_novo
    
    # Agora pegamos os dados mais frescos
    df_ativo = st.session_state.get('df_global', df_original)
    
    # Exemplo: Renderizando os KPI's centrais da página
    st.markdown(f"*(Última atualização silenciosa: {pd.Timestamp.now().strftime('%H:%M:%S')})*")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total de Linhas Lidas", len(df_ativo))
    with c2:
        media_hia = df_ativo['HIA'].mean() if 'HIA' in df_ativo.columns else 0
        st.metric("HIA Médio da Equipe", f"{media_hia:.1f}")
    with c3:
        if 'Placar' in df_ativo.columns:
            st.metric("Placar Atualizado", str(df_ativo['Placar'].iloc[-1]))

def renderizar_toggle_apresentacao():
    """Toggle que oculta filtros e expande gráficos para apresentação."""
    if 'modo_apresentacao' not in st.session_state:
        st.session_state['modo_apresentacao'] = False

    col_toggle = st.columns([8, 1])[1]
    with col_toggle:
        if st.button(
            "🎬" if not st.session_state['modo_apresentacao'] else "✏️",
            help="Modo Apresentação" if not st.session_state['modo_apresentacao'] else "Modo Edição",
            key="btn_modo_apresentacao"
        ):
            st.session_state['modo_apresentacao'] = not st.session_state['modo_apresentacao']
            st.rerun()

    if st.session_state['modo_apresentacao']:
        st.markdown("""
            <style>
                /* Oculta filtros e controles */
                [data-testid="stSidebar"],
                div[data-testid="stVerticalBlock"] > div:nth-child(-n+3) [data-testid="stHorizontalBlock"]:first-of-type,
                div[data-testid="stSelectbox"],
                div[data-testid="stMultiSelect"],
                div[data-testid="stRadio"],
                div[data-testid="stSlider"],
                div[data-testid="stPills"] { display: none !important; }
                
                /* Expande gráficos */
                .block-container { 
                    max-width: 100% !important; 
                    padding: 1rem !important; 
                }
                
                /* Fonte maior nos valores */
                [data-testid="stMetricValue"] { font-size: 2rem !important; }
            </style>
        """, unsafe_allow_html=True)
        st.info("🎬 Modo Apresentação ativo — clique em ✏️ para voltar ao modo edição")
    
    return st.session_state['modo_apresentacao']