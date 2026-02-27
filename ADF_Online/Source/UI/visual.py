# ADF_Online/visual.py
import os

# 1. IDENTIDADE DO CLUBE (Fácil de alterar para novos clientes)
CLUBE = {
    "nome": "Barra FC",
    "sigla": "BFC",
    "logo_path": os.path.join(os.path.dirname(__file__), 'BarraFC.png')
}

# 2. PALETA DE CORES (Baseada no escudo do clube)
CORES = {
    "primaria": "#2E7D32",      # Verde Barra FC
    "secundaria": "#81C784",    # Verde claro
    "fundo_card": "#FFFFFF",
    "texto_escuro": "#1E293B",
    "texto_claro": "#64748B",
    "alerta_fadiga": "#EF4444", # Vermelho
    "aviso_carga": "#F59E0B",   # Laranja
    "ok_prontidao": "#10B981"   # Verde
}

# 3. DICIONÁRIO PADRÃO DO PLOTLY
# Isso garante que todos os gráficos do sistema nasçam com o visual do clube
PLOTLY_TEMPLATE = {
    "layout": {
        "font": {"family": "Inter, sans-serif", "color": CORES["texto_escuro"]},
        "plot_bgcolor": "rgba(0,0,0,0)",
        "paper_bgcolor": "rgba(0,0,0,0)",
        "colorway": [CORES["primaria"], CORES["aviso_carga"], CORES["alerta_fadiga"]],
        "margin": dict(l=20, r=20, t=40, b=20)
    }
}