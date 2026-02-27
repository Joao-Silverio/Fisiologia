import streamlit as st
from streamlit_autorefresh import st_autorefresh

# 1. Importações da sua nova Arquitetura
import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.UI.visual as visual
import Source.UI.components as ui

# 2. Configuração de Página usando o Visual central
st.set_page_config(page_title=f"Sports Hub | {visual.CLUBE['sigla']}", layout="wide")

# 3. SUBSTITUI os títulos antigos por UMA única linha do seu componente!
ui.renderizar_cabecalho("Sports Performance Hub", "Painel central de análise fisiológica e tática")

# 4. A Lógica dos dados (mantém exatamente igual)
st_autorefresh(interval=2000, limit=None, key="home_tracker_refresh")
hora_atualizacao = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)

try:
    df, df_recordes = load_global_data(hora_atualizacao)
    
    if df is not None and not df.empty:
        st.session_state['df_global'] = df
        st.session_state['df_recordes'] = df_recordes
        
        st.success("✅ Base de dados carregada!")
        
        # 5. SUBSTITUI os `st.metric` antigos pelos seus novos cartões Dark Mode!
        c1, c2, c3 = st.columns(3)
        with c1:
            ui.renderizar_card_kpi("Total de Atletas", str(df['Name'].nunique()), icone="👥")
        with c2:
            ui.renderizar_card_kpi("Jogos Analisados", str(df['Data'].nunique()), icone="📅")
        with c3:
            ui.renderizar_card_kpi("Linhas de GPS", str(len(df)), cor_borda=visual.CORES["ok_prontidao"], icone="📡")
            
    else:
        st.warning("⚠️ Ficheiro Excel vazio.")
except Exception as e:
    st.error(f"Erro: {e}")