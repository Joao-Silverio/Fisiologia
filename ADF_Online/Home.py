import streamlit as st
import pandas as pd
import os
import shutil
import warnings
import config # <-- Importamos as configurações

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# Trocando o 'page_icon' para a sua imagem (muda o ícone da aba do navegador)
st.set_page_config(page_title="Sports Performance Hub", layout="wide", page_icon="BarraFC.png")

# Criando duas colunas: uma bem fininha para a logo e uma larga para o título
col_logo, col_titulo = st.columns([1, 15]) 

with col_logo:
    # O width=60 controla o tamanho da imagem. Você pode aumentar ou diminuir!
    st.image("BarraFC.png", width=100) 

with col_titulo:
    # O título agora fica sem o emoji, limpo e ao lado da imagem
    st.title("Sports Performance Hub")

st.markdown("Bem-vindo ao painel central de análise fisiológica e tática.")

def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

hora_atualizacao = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

@st.cache_resource(show_spinner="Carregando base de dados da temporada na velocidade da luz...")
def load_global_data(hora_mod):
    try:
        shutil.copy2(config.ARQUIVO_ORIGINAL, config.ARQUIVO_TEMP)
        
        # Usando as colunas do config.py
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

        return df
        
    except PermissionError:
        st.toast("⏳ A base de dados principal está a ser atualizada...")
        return None
    except Exception as e:
        st.error(f"Erro na leitura do ficheiro: {e}")
        return None

try:
    df = load_global_data(hora_atualizacao)
    if df is not None:
        st.session_state['df_global'] = df
        st.success("✅ Base de dados global carregada com sucesso!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Atletas Registrados", df['Name'].nunique() if 'Name' in df.columns else 0)
        col2.metric("Total de Jogos Analisados", df['Data'].nunique() if 'Data' in df.columns else 0)
        col3.metric("Linhas de GPS Lidas", len(df))
        st.info("👈 Selecione um dos módulos no menu lateral para começar a análise.")
except Exception as e:
    st.error(f"Erro ao processar os dados: {e}")