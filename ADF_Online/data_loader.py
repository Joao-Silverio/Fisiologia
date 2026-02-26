import streamlit as st
import pandas as pd
import os
import shutil
import config

def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

@st.cache_resource(show_spinner="🔄 Nova atualização detetada no Excel! A processar dados...")
def load_global_data(hora_mod):
    try:
        shutil.copy2(config.ARQUIVO_ORIGINAL, config.ARQUIVO_TEMP)
        
        df = pd.read_excel(
            config.ARQUIVO_TEMP, 
            engine='calamine',
            usecols=lambda c: c.strip() in config.COLUNAS_NECESSARIAS
        )
        df.columns = df.columns.str.strip()

        df[config.COLS_METRICAS_PREENCHER_ZERO] = df[config.COLS_METRICAS_PREENCHER_ZERO].fillna(0)

        df['HIA'] = (
            df.get('V4 To8 Eff', 0) + df.get('V5 To8 Eff', 0) + 
            df.get('V6 To8 Eff', 0) + df.get('Acc3 Eff', 0) + df.get('Dec3 Eff', 0)
        )

        df['Data_Display'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%d/%m/%Y') + ' ' + df['Adversário'].astype(str)

        # Fábrica de Recordes
        df_sorted = df.sort_values(by=['Name', 'Data', 'Período', 'Interval']).copy()
        
        mapa_recordes = {
            'Total Distance': 'Dist_Total', 'Player Load': 'Load_Total',
            'V4 Dist': 'V4_Dist', 'V5 Dist': 'V5_Dist',
            'V4 To8 Eff': 'V4_Eff', 'V5 To8 Eff': 'V5_Eff', 'HIA': 'HIA_Total'
        }
        
        cols_calc = [c for c in mapa_recordes.keys() if c in df_sorted.columns]
        
        df_rolling = df_sorted.groupby(['Name', 'Data', 'Período'])[cols_calc].rolling(window=5, min_periods=1).sum().reset_index(drop=True)
        df_rolling['Name'] = df_sorted['Name'].values
        
        df_recordes = df_rolling.groupby('Name')[cols_calc].max().reset_index()
        rename_dict = {col: f"Recorde_5min_{mapa_recordes[col]}" for col in cols_calc}
        df_recordes = df_recordes.rename(columns=rename_dict)

        return df, df_recordes
        
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(), pd.DataFrame()