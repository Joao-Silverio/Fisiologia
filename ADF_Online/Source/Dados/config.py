import os

# ==========================================
# 1. CAMINHOS E DIRETÓRIOS
# ==========================================
# Pega o diretório atual do config.py (que agora é ADF_Online/src/data)
DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))

BASE_DIR = os.path.dirname(os.path.dirname(DIR_ATUAL))

ARQUIVO_ORIGINAL = os.path.join(BASE_DIR, 'Data_Files', 'ADF OnLine 2024.xlsb')
ARQUIVO_TEMP = os.path.join(BASE_DIR, 'Data_Files', 'ADF_TEMP_HOME.xlsb')

# Adicionando o caminho oficial da pasta de modelos
DIRETORIO_MODELOS = os.path.join(BASE_DIR, 'Models')

# Adiciona Logo:
CAMINHO_LOGO = os.path.join(BASE_DIR, 'Assets', 'BarraFC.png')

# =================================================================
# CONFIGURAÇÕES DE GEOLOCALIZAÇÃO (FATOR CASA)
# =================================================================
# Arena Barra FC - Canhanduba (Itajaí, SC)
LATITUDE_CASA = -26.948597   # Coordenada exata do centro do campo
LONGITUDE_CASA = -48.674744

# Distância máxima (em km) para o jogo ser considerado "Em Casa"
RAIO_CASA_KM = 2.0

# ==========================================
# 2. COLUNAS DA BASE DE DADOS
# ==========================================
COLUNAS_NECESSARIAS = [
    'Name', 'Data', 'Interval', 'Name', 'Período', 'Placar', 'Resultado', 'Adversário',
    'Total Distance', 'V4 Dist', 'V5 Dist', 'V4 To8 Eff', 'V5 To8 Eff', 
    'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Player Load',
    'Parte (15 min)', 'Parte (5 min)', 'Parte (3 min)', 'Competição', 'Metabolic Power', 'Latitude', 'Longitude'
]

COLS_NAO_METRICAS = ['Data', 'Name', 'Adversário', 'Competição', 'Placar', 'Resultado', 'Parte (15 min)', 'Parte (5 min)', 'Parte (3 min)']
COLS_METRICAS_PREENCHER_ZERO = [c for c in COLUNAS_NECESSARIAS if c not in COLS_NAO_METRICAS]

# ESTA É A VARIÁVEL QUE ESTAVA FALTANDO PARA O RELATÓRIO HIA FUNCIONAR:
COLS_COMPONENTES_HIA = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Acc4 Eff', 'Dec4 Eff']

# ==========================================
# 3. DICIONÁRIO DO LIVE TRACKER / ML
# ==========================================
METRICAS_CONFIG = {
    "Total Distance": {"coluna_distancia": "Total Distance", "coluna_acumulada": "Dist Acumulada", "titulo_grafico": "Projeção de Distância Total", "arquivo_modelo": "modelo_Dist_Total.pkl", "unidade": " m"},
    "V4 Dist": {"coluna_distancia": "V4 Dist", "coluna_acumulada": "V4 Dist Acumulada", "titulo_grafico": "Projeção de V4 Dist", "arquivo_modelo": "modelo_V4_Dist.pkl", "unidade": " m"},
    "V5 Dist": {"coluna_distancia": "V5 Dist", "coluna_acumulada": "V5 Dist Acumulada", "titulo_grafico": "Projeção de Sprints (V5 Dist)", "arquivo_modelo": "modelo_V5_Dist.pkl", "unidade": " m"},
    "V4 Eff": {"coluna_distancia": "V4 To8 Eff", "coluna_acumulada": "V4 Eff Acumulada", "titulo_grafico": "Projeção de Ações V4+", "arquivo_modelo": "modelo_V4_Eff.pkl", "unidade": ""},
    "V5 Eff": {"coluna_distancia": "V5 To8 Eff", "coluna_acumulada": "V5 Eff Acumulada", "titulo_grafico": "Projeção de Ações V5+ (Sprints)", "arquivo_modelo": "modelo_V5_Eff.pkl", "unidade": ""},
    "HIA": {"coluna_distancia": "HIA", "coluna_acumulada": "HIA Acumulada", "titulo_grafico": "Projeção de HIA", "arquivo_modelo": "modelo_HIA_Total.pkl", "unidade": ""}
}

# ==========================================
# 4. PALETAS DE CORES (PADRONIZAÇÃO VISUAL)
# ==========================================
MAPA_CORES_PLACAR = {
    "Ganhando 1": "#2E7D32", "Ganhando 2": "#1B5E20", 
    "Perdendo 1": "#C62828", "Perdendo 2": "#B71C1C", 
    "Empatando": "#F9A825"
}

MAPA_CORES_HIA = {
    'V4 To8 Eff': '#FFAB91', 'V5 To8 Eff': '#FF7043', 'V6 To8 Eff': '#D84315', 
    'Acc3 Eff': '#90CAF9',
    'Dec3 Eff': '#A5D6A7',
}
