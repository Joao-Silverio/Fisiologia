import streamlit as st
import pandas as pd
import os
import shutil
import warnings

# Esconde os avisos do Excel
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

st.set_page_config(page_title="Sports Performance Hub", layout="wide", page_icon="⚽")

st.title("⚽ Sports Performance Hub")
st.markdown("Bem-vindo ao painel central de análise fisiológica e tática.")

# Função de inteligência para saber quando o Excel foi guardado
def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

# Descobre exatamente em qual pasta o código está rodando no servidor
DIRETORIO_ATUAL = os.path.dirname(os.path.abspath(__file__))

# Cola o nome do arquivo na frente da pasta
arquivo_original = os.path.join(DIRETORIO_ATUAL, 'ADF OnLine 2024.xlsb')
hora_atualizacao = obter_hora_modificacao(arquivo_original)

# 1. Função Global de Carregamento Turbo
@st.cache_resource(show_spinner="Carregando base de dados da temporada na velocidade da luz...")
def load_global_data(hora_mod):
    # Criamos um temporário com nome diferente do Live Tracker para não haver conflitos
    arquivo_temp = 'ADF_TEMP_HOME.xlsb' 
    
    try:
        shutil.copy2(arquivo_original, arquivo_temp)
        
        # Lista de todas as colunas que os seus Módulos (HIA, Radar, etc.) vão precisar.
        # Se no futuro criar um gráfico novo, lembre-se de adicionar a coluna aqui!
        colunas_necessarias = [
            'Data', 'Interval', 'Name', 'Período', 'Placar', 'Resultado', 'Adversário',
            'Total Distance', 'V4 Dist', 'V4 To8 Eff', 'V5 To8 Eff', 
            'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Player Load',
            'Parte (15 min)', 'Parte (5 min)', 'Parte (3 min)', 'Competição'
        ]
        
        # Lemos o Excel com o motor 'calamine'. 
        # O lambda garante que se uma coluna não existir no Excel, o código não quebra.
        df = pd.read_excel(
            arquivo_temp, 
            engine='calamine',
            usecols=lambda c: c.strip() in colunas_necessarias
        )
        
        df.columns = df.columns.str.strip()
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
        # Salva o dataframe na "Sessão" para as outras páginas usarem sem recarregar
        st.session_state['df_global'] = df
        
        st.success("✅ Base de dados global carregada com sucesso!")
        
        # Pequeno resumo na tela inicial
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Atletas Registrados", df['Name'].nunique() if 'Name' in df.columns else 0)
        col2.metric("Total de Jogos Analisados", df['Data'].nunique() if 'Data' in df.columns else 0)
        col3.metric("Linhas de GPS Lidas", len(df))
        
        st.info("👈 Selecione um dos módulos no menu lateral para começar a análise.")

except Exception as e:
    st.error(f"Erro ao processar os dados: {e}")
