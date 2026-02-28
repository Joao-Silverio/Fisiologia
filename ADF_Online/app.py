# ADF_Online/app.py
import streamlit as st
import Source.UI.visual as visual
import Source.UI.components as ui

# O set_page_config AGORA FICA AQUI NO MAESTRO, UMA ÚNICA VEZ PARA TODO O PROJETO!
st.set_page_config(
    page_title="Sports Hub | BFC",
    layout="wide",
    initial_sidebar_state="collapsed", # Opcional: pode mudar para "expanded" se quiser usar a sidebar nativa
)

# Definição Oficial das Páginas
paginas = {
    "Dashboard Central": [
        st.Page("Home.py", title="Home", icon=":material/home:"), # Aponta para o seu Home.py atual!
    ],
    "Telemetria Ao Vivo": [
        st.Page("pages/1_🔴_Live_Tracker.py", title="Live Tracker", icon=":material/sensors:"),
        st.Page("pages/3_🔋_Radar_Fadiga.py", title="Radar Fadiga", icon=":material/battery_charging_full:"),
    ],
    "Análises Pós-Jogo": [
        st.Page("pages/2_📊_Relatorio_HIA.py", title="Relatório HIA", icon=":material/analytics:"),
        st.Page("pages/4_📅_Temporada.py", title="Visão Temporada", icon=":material/calendar_month:"),
        st.Page("pages/5_⚔️_Comparacao_Atletas.py", title="Comparação", icon=":material/compare_arrows:"),
        st.Page("pages/6_👤_Individual_Atleta.py", title="Visão Individual", icon=":material/person:"),
    ]
}

# Inicializa o roteamento nativo
pg = st.navigation(paginas, position="hidden") #esconde o menu nativo

#MENU GOLBAL
ui.renderizar_menu_superior(pagina_atual=pg.title) 
# A página "Home" é a que aparece ao abrir o app

# Roda a página selecionada
pg.run()