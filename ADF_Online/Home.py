import streamlit as st
import pandas as pd
import os
import shutil
import warnings
import config # <-- Garantindo o import do config
from PIL import Image

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

logo = Image.open(config.CAMINHO_LOGO)

st.set_page_config(page_title="Sports Performance Hub", layout="wide", page_icon=logo)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# Só importa o st_autorefresh se realmente for usar na Home (normalmente usa-se só no Live Tracker, mas mantive como pediu)
from streamlit_autorefresh import st_autorefresh
contador = st_autorefresh(interval=60000, limit=1000, key="home_tracker_refresh")

col_logo, col_titulo = st.columns([1, 15]) 

with col_logo:
    st.image(logo, width=100) 

with col_titulo:
    st.title("Sports Performance Hub")

st.markdown("Bem-vindo ao painel central de análise fisiológica e tática.")

def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

hora_atualizacao = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

@st.cache_resource(show_spinner="Carregando base de dados e processando recordes fisiológicos...")
def load_global_data(hora_mod):
    try:
        shutil.copy2(config.ARQUIVO_ORIGINAL, config.ARQUIVO_TEMP)
        
        df = pd.read_excel(
            config.ARQUIVO_TEMP, 
            engine='calamine',
            usecols=lambda c: c.strip() in config.COLUNAS_NECESSARIAS
        )
        df.columns = df.columns.str.strip()

        # 1. Preencher Nulos usando a lista do config.py
        df[config.COLS_METRICAS_PREENCHER_ZERO] = df[config.COLS_METRICAS_PREENCHER_ZERO].fillna(0)

        # 2. Criar Métrica HIA Global
        df['HIA'] = (
            df.get('V4 To8 Eff', 0) + df.get('V5 To8 Eff', 0) + 
            df.get('V6 To8 Eff', 0) + df.get('Acc3 Eff', 0) + df.get('Dec3 Eff', 0)
        )

        # 3. Formatar Datas de Exibição
        df['Data_Display'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%d/%m/%Y') + ' ' + df['Adversário'].astype(str)

        # =================================================================
        # 4. FÁBRICA DE RECORDES (Picos de 5 Minutos para o Live Tracker)
        # =================================================================
        df_sorted = df.sort_values(by=['Name', 'Data', 'Período', 'Interval']).copy()
        
        # Mapeamos as colunas do Catapult para os Nomes que o seu Live Tracker pede
        mapa_recordes = {
            'Total Distance': 'Dist_Total',
            'Player Load': 'Load_Total',
            'V4 Dist': 'V4_Dist',
            'V5 Dist': 'V5_Dist',
            'V4 To8 Eff': 'V4_Eff',
            'V5 To8 Eff': 'V5_Eff',
            'HIA': 'HIA_Total'
        }
        
        cols_calc = [c for c in mapa_recordes.keys() if c in df_sorted.columns]
        
        # Calcula a soma móvel de 5 em 5 minutos para cada atleta em cada jogo/período
        df_rolling = df_sorted.groupby(['Name', 'Data', 'Período'])[cols_calc].rolling(window=5, min_periods=1).sum().reset_index(drop=True)
        df_rolling['Name'] = df_sorted['Name'].values
        
        # Acha o valor MÁXIMO (Recorde da Temporada) de cada atleta para cada métrica
        df_recordes = df_rolling.groupby('Name')[cols_calc].max().reset_index()
        
        # Renomeia para o padrão "Recorde_5min_V4_Dist"
        rename_dict = {col: f"Recorde_5min_{mapa_recordes[col]}" for col in cols_calc}
        df_recordes = df_recordes.rename(columns=rename_dict)

        # Retornamos os dois dataframes!
        return df, df_recordes
        
    except PermissionError:
        st.toast("⏳ A base de dados principal está a ser atualizada...")
        return None, None
    except Exception as e:
        st.error(f"Erro na leitura do ficheiro: {e}")
        return None, None

try:
    df, df_recordes = load_global_data(hora_atualizacao)
    
    if df is not None and df_recordes is not None:
        # Guarda na memória para o resto do sistema poder usar
        st.session_state['df_global'] = df
        st.session_state['df_recordes'] = df_recordes
        
        st.success("✅ Base de dados global e Recordes Fisiológicos carregados com sucesso!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Atletas Registrados", df['Name'].nunique() if 'Name' in df.columns else 0)
        col2.metric("Total de Jogos Analisados", df['Data'].nunique() if 'Data' in df.columns else 0)
        col3.metric("Linhas de GPS Lidas", len(df))
        st.info("👈 Selecione um dos módulos no menu lateral para começar a análise.")
except Exception as e:
    st.error(f"Erro ao processar os dados: {e}")