# =============================================================================
# positions.py — Configuração de Posições dos Atletas
# ADF Online | Coloque em: ADF_Online/positions.py
# =============================================================================

PLAYER_POSITIONS: dict = {
    # ⬇ Substitua pelos nomes EXATOS como aparecem no seu Excel (coluna "Name")
    "Ewerton Ferreira":       "GOL",
    "Jean Pierre":     "ZAG",
    "Guilherme Teixeira":  "ZAG",
    "Da Rocha":   "LAT",
    "Kayque Ryann":     "LAT",
    "Marcelo Ferreira":     "LAT",
    "Elvinho":    "MEI",
    "Natan Costa":     "MEI",
    "Joao Miguel":     "MEI",
    "Giovani Albuquerque":     "ATA",
    "Gabriel Lyra":      "ATA",
}

# Benchmarks baseados em: Mohr (2003), Bangsbo (2006), Stølen (2005)
# Nomes das métricas = colunas reais do seu projeto
POSITION_CONFIG: dict = {
    "GOL": {
        "label": "Goleiro",  "emoji": "🧤", "color": "#FFC300",
        "benchmarks": {
            "Total Distance": {"min": 4500,  "max": 6500,  "elite": 5500},
            "HIA_Total":      {"min": 10,    "max": 40,    "elite": 25},
            "V4 Dist":        {"min": 50,    "max": 300,   "elite": 150},
            "V5 Dist":        {"min": 10,    "max": 100,   "elite": 40},
            "Player Load":    {"min": 400,   "max": 700,   "elite": 550},
            "AccDec_Total":   {"min": 15,    "max": 50,    "elite": 30},
        },
    },
    "ZAG": {
        "label": "Zagueiro", "emoji": "🛡️", "color": "#1A73E8",
        "benchmarks": {
            "Total Distance": {"min": 8000,  "max": 11000, "elite": 9500},
            "HIA_Total":      {"min": 40,    "max": 100,   "elite": 65},
            "V4 Dist":        {"min": 300,   "max": 800,   "elite": 500},
            "V5 Dist":        {"min": 50,    "max": 200,   "elite": 110},
            "Player Load":    {"min": 650,   "max": 950,   "elite": 800},
            "AccDec_Total":   {"min": 30,    "max": 80,    "elite": 55},
        },
    },
    "LAT": {
        "label": "Lateral",  "emoji": "⚡", "color": "#34A853",
        "benchmarks": {
            "Total Distance": {"min": 9500,  "max": 13000, "elite": 11200},
            "HIA_Total":      {"min": 60,    "max": 140,   "elite": 95},
            "V4 Dist":        {"min": 500,   "max": 1200,  "elite": 800},
            "V5 Dist":        {"min": 100,   "max": 400,   "elite": 220},
            "Player Load":    {"min": 750,   "max": 1100,  "elite": 920},
            "AccDec_Total":   {"min": 50,    "max": 120,   "elite": 80},
        },
    },
    "MEI": {
        "label": "Meia",     "emoji": "🎯", "color": "#9B59B6",
        "benchmarks": {
            "Total Distance": {"min": 10000, "max": 13500, "elite": 11800},
            "HIA_Total":      {"min": 80,    "max": 180,   "elite": 120},
            "V4 Dist":        {"min": 600,   "max": 1400,  "elite": 950},
            "V5 Dist":        {"min": 120,   "max": 450,   "elite": 260},
            "Player Load":    {"min": 800,   "max": 1200,  "elite": 1000},
            "AccDec_Total":   {"min": 60,    "max": 150,   "elite": 100},
        },
    },
    "ATA": {
        "label": "Atacante", "emoji": "⚽", "color": "#E74C3C",
        "benchmarks": {
            "Total Distance": {"min": 8500,  "max": 12000, "elite": 10200},
            "HIA_Total":      {"min": 70,    "max": 160,   "elite": 110},
            "V4 Dist":        {"min": 500,   "max": 1300,  "elite": 850},
            "V5 Dist":        {"min": 150,   "max": 550,   "elite": 320},
            "Player Load":    {"min": 700,   "max": 1050,  "elite": 880},
            "AccDec_Total":   {"min": 45,    "max": 120,   "elite": 80},
        },
    },
}

POSITION_ORDER = ["GOL", "ZAG", "LAT", "MEI", "ATA"]


def get_position(player_name: str) -> str | None:
    if not player_name:
        return None
    if player_name in PLAYER_POSITIONS:
        return PLAYER_POSITIONS[player_name]
    low = str(player_name).strip().lower()
    for name, pos in PLAYER_POSITIONS.items():
        if name.lower() == low:
            return pos
    for name, pos in PLAYER_POSITIONS.items():
        if low in name.lower() or name.lower() in low:
            return pos
    return None

def get_benchmark(position: str, metric: str) -> dict | None:
    if not position or position not in POSITION_CONFIG:
        return None
    return POSITION_CONFIG[position]["benchmarks"].get(metric)

def classify_performance(value: float, position: str, metric: str) -> str:
    bench = get_benchmark(position, metric)
    if not bench:
        return "sem_benchmark"
    if value < bench["min"]:   return "abaixo"
    if value >= bench["elite"]: return "elite"
    if value <= bench["max"]:  return "normal"
    return "acima"

def position_badge_html(position: str) -> str:
    if not position or position not in POSITION_CONFIG:
        return "<span style='color:#888;font-size:0.8rem'>❓ Não mapeado</span>"
    c = POSITION_CONFIG[position]
    return (
        f"<span style='background:{c['color']}22;border:1.5px solid {c['color']};"
        f"color:{c['color']};padding:2px 10px;border-radius:20px;"
        f"font-weight:700;font-size:0.8rem'>{c['emoji']} {c['label']}</span>"
    )