import streamlit as st
import config
from PIL import Image
from streamlit_autorefresh import st_autorefresh

# 1. Importar as funções do novo "Coração" do sistema
from data_loader import obter_hora_modificacao, load_global_data

# Configuração da página e logo
logo = Image.open(config.CAMINHO_LOGO)
st.set_page_config(page_title="Sports Performance Hub", layout="wide", page_icon=logo)

st.markdown("""
    <style>
        .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

col_logo, col_titulo = st.columns([1, 15]) 
with col_logo:
    st.image(logo, width=100) 
with col_titulo:
    st.title("Sports Performance Hub")

st.markdown("Bem-vindo ao painel central de análise fisiológica e tática.")

# 2. A "Magia" do Tempo Real (A página pisca a cada 2 segundos para ver se há atualizações)
st_autorefresh(interval=2000, limit=None, key="home_tracker_refresh")

# 3. Lê a impressão digital do ficheiro
hora_atualizacao = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

# 4. O teu código original, mas agora muito mais rápido e limpo!
try:
    df, df_recordes = load_global_data(hora_atualizacao)
    
    if df is not None and df_recordes is not None and not df.empty:
        # Guarda na memória para o resto do sistema poder usar instantaneamente
        st.session_state['df_global'] = df
        st.session_state['df_recordes'] = df_recordes
        
        st.success("✅ Base de dados global e Recordes Fisiológicos carregados com sucesso em Tempo Real!")
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Atletas Registrados", df['Name'].nunique() if 'Name' in df.columns else 0)
        col2.metric("Total de Jogos Analisados", df['Data'].nunique() if 'Data' in df.columns else 0)
        col3.metric("Linhas de GPS Lidas", len(df))
        st.info("👈 Selecione um dos módulos no menu lateral para começar a análise.")
    else:
        st.warning("⚠️ O ficheiro Excel está vazio ou não pôde ser lido.")
        
except Exception as e:
    st.error(f"Erro ao processar os dados: {e}")