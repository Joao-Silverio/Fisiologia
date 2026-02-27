# Source/UI/visual.py
import os

# Caminho raiz dinâmico (Volta de UI -> Source -> ADF_Online)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 1. IDENTIDADE
CLUBE = {
    "nome": "Barra FC",
    "sigla": "BFC",
    "logo_path": os.path.join(BASE_DIR, 'Assets', 'BarraFC.png')
}

# 2. PALETA DE CORES (DARK MODE MODERNO)
CORES = {
    "primaria": "#FDFD96",      # Azul vibrante (Botões e destaques principais)
    "secundaria": "#60A5FA",    # Azul claro
    "fundo_card": "#1E293B",    # Fundo dos cartões (Cinza/Azul muito escuro)
    "texto_escuro": "#F8FAFC",  # Branco/Gelo (No dark mode, o "texto_escuro" principal vira claro para dar contraste)
    "texto_claro": "#94A3B8",   # Cinza chumbo (Subtítulos)
    "alerta_fadiga": "#EF4444", # Vermelho
    "aviso_carga": "#D97706",   # Laranja
    "ok_prontidao": "#10B981"   # Verde
}

# 3. DICIONÁRIO PADRÃO DO PLOTLY (Para os gráficos ficarem com fundo escuro)
PLOTLY_TEMPLATE = {
    "layout": {
        "font": {"family": "Inter, sans-serif", "color": CORES["texto_escuro"]},
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "colorway": [CORES["primaria"], CORES["aviso_carga"], CORES["alerta_fadiga"]],
        "margin": dict(l=20, r=20, t=40, b=20)
    }
}