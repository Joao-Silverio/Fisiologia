import pandas as pd
import numpy as np
import os
import shutil
import Source.Dados.config as config
import streamlit as st

def extrair_diff_gols(placar):
    s = str(placar).strip().lower()
    if any(x in s for x in ['vencendo', 'vitoria', 'vitória', 'ganhando', 'v']): return 1
    if any(x in s for x in ['perdendo', 'derrota', 'd']): return -1
    return 0

def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

# ---------------------------------------------------------
# CAMADA 1: LEITURA BRUTA (Extremamente rápida)
# ---------------------------------------------------------
@st.cache_data(show_spinner="📥 Lendo Excel bruto...", max_entries=2)
def _read_raw_excel(hora_mod):
    """Lê o arquivo bruto. Só roda de novo se a hora_mod mudar."""
    shutil.copy2(config.ARQUIVO_ORIGINAL, config.ARQUIVO_TEMP)
    df = pd.read_excel(
        config.ARQUIVO_TEMP, 
        engine='calamine', decimal=',',
        usecols=lambda c: c.strip() in config.COLUNAS_NECESSARIAS
    )
    df.columns = df.columns.str.strip()
    return df

# ---------------------------------------------------------
# CAMADA 2: PROCESSAMENTO PESADO (Haversine, HIA, Recordes)
# ---------------------------------------------------------
@st.cache_data(show_spinner="⚙️ Processando métricas de GPS...", max_entries=2)
def _process_data(df):
    """Aplica toda a matemática. Fica em cache com base no DataFrame bruto de entrada."""
    df_proc = df.copy() # Garante que não mutamos o cache anterior

    for col in ['Latitude', 'Longitude']: 
        if col in df_proc.columns: 
            sujeira_limpa = df_proc[col].astype(str).str.replace(' ', '', regex=False).str.replace(',', '.', regex=False)
            sujeira_limpa = sujeira_limpa.replace(['nan', 'NaN', 'None', ''], np.nan)
            df_proc[col] = pd.to_numeric(sujeira_limpa, errors='coerce') 

    if 'Latitude' in df_proc.columns and 'Longitude' in df_proc.columns:
        lat1, lon1 = np.radians(config.LATITUDE_CASA), np.radians(config.LONGITUDE_CASA)
        lat2, lon2 = np.radians(df_proc['Latitude']), np.radians(df_proc['Longitude'])
        
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
        c = 2 * np.arcsin(np.sqrt(a))
        df_proc['Distancia_Viagem_km'] = 6371.0 * c
        
        df_proc.loc[df_proc['Distancia_Viagem_km'] <= config.RAIO_CASA_KM, 'Status_Local'] = 1
        df_proc.loc[df_proc['Distancia_Viagem_km'] > config.RAIO_CASA_KM, 'Status_Local'] = 0
        df_proc['Jogou_em_Casa'] = df_proc.groupby('Data')['Status_Local'].transform('min').fillna(1)
    else:
        df_proc['Jogou_em_Casa'] = 1

    df_proc[config.COLS_METRICAS_PREENCHER_ZERO] = df_proc[config.COLS_METRICAS_PREENCHER_ZERO].fillna(0)
    df_proc['HIA'] = (
        df_proc.get('V4 To8 Eff', 0) + df_proc.get('V5 To8 Eff', 0) + 
        df_proc.get('V6 To8 Eff', 0) + df_proc.get('Acc3 Eff', 0) + df_proc.get('Dec3 Eff', 0)
    )

    if 'Placar' in df_proc.columns:
        df_proc['Diff_Gols'] = df_proc['Placar'].apply(extrair_diff_gols)
    else:
        df_proc['Diff_Gols'] = 0
        
    df_proc['Data_Display'] = pd.to_datetime(df_proc['Data'], errors='coerce').dt.strftime('%d/%m/%Y') + ' ' + df_proc['Adversário'].astype(str)
    
    nome_coluna_tempo = 'Interval (min)' if 'Interval (min)' in df_proc.columns else 'Interval'
    df_proc['Min_Num'] = pd.to_numeric(df_proc[nome_coluna_tempo], errors='coerce').fillna(0)

    # Cálculo de recordes
    df_sorted = df_proc.sort_values(by=['Name', 'Data', 'Período', 'Min_Num']).copy()
    mapa_recordes = {
        'Total Distance': 'Dist_Total', 'Player Load': 'Load_Total',
        'V4 Dist': 'V4_Dist', 'V5 Dist': 'V5_Dist',
        'V4 To8 Eff': 'V4_Eff', 'V5 To8 Eff': 'V5_Eff', 'HIA': 'HIA_Total'
    }
    cols_calc = [c for c in mapa_recordes.keys() if c in df_sorted.columns]
    df_rolling = df_sorted.groupby(['Name', 'Data', 'Período'])[cols_calc].rolling(window=5, min_periods=1).sum().reset_index(drop=True)
    df_rolling['Name'] = df_sorted['Name'].values
    
    df_recordes = df_rolling.groupby('Name')[cols_calc].max().reset_index()
    df_recordes = df_recordes.rename(columns={col: f"Recorde_5min_{mapa_recordes[col]}" for col in cols_calc})

    return df_proc, df_recordes

# ---------------------------------------------------------
# FUNÇÃO PRINCIPAL EXPORTADA
# ---------------------------------------------------------
def load_global_data(hora_mod):
    try:
        # A leitura bruta decide se precisa ir ao Excel ou se pega do cache
        df_raw = _read_raw_excel(hora_mod)
        # O processamento faz a matemática (também baseada em cache)
        return _process_data(df_raw)
    except Exception as e:
        mensagem = f"Erro ao carregar dados: {e}"
        if st.runtime.exists():
            st.error(mensagem)
        else:
            print(f"❌ {mensagem}")
        return pd.DataFrame(), pd.DataFrame()

# Colocamos o cache apenas nesta função interna
@st.cache_resource(show_spinner="🔄 Atualizando base de dados...")
def _load_data_logic(hora_mod):
    try:
        # 1. Copiar arquivo para evitar travamentos
        shutil.copy2(config.ARQUIVO_ORIGINAL, config.ARQUIVO_TEMP)
        
        # 2. Ler o Excel (Apenas UMA vez!)
        df = pd.read_excel(
            config.ARQUIVO_TEMP, 
            engine='calamine', decimal = ',', #Explica que o separador decimal é um vírgula
            usecols=lambda c: c.strip() in config.COLUNAS_NECESSARIAS
        )
        
        # 3. Limpar nomes de colunas (Remove espaços extras)
        df.columns = df.columns.str.strip()

        # SUPER BLINDAGEM DA VÍRGULA, ESPAÇOS E TEXTOS
        for col in ['Latitude', 'Longitude']: 
            if col in df.columns: 
                # Converte para texto, arranca espaços invisíveis e troca a vírgula por ponto
                sujeira_limpa = df[col].astype(str).str.replace(' ', '', regex=False).str.replace(',', '.', regex=False)
                # Garante que textos vazios não quebrem o conversor
                sujeira_limpa = sujeira_limpa.replace(['nan', 'NaN', 'None', ''], np.nan)
                
                # Força a conversão para número decimal rigoroso
                df[col] = pd.to_numeric(sujeira_limpa, errors='coerce') 

        # 4. Cálculo do Fator Casa (Arena Barra) com Inteligência de Equipe      
        if 'Latitude' in df.columns and 'Longitude' in df.columns:
            lat1, lon1 = np.radians(config.LATITUDE_CASA), np.radians(config.LONGITUDE_CASA)
            # Deixamos os vazios (NaN) intactos por enquanto para a matemática
            lat2 = np.radians(df['Latitude']) 
            lon2 = np.radians(df['Longitude'])
            
            dlat, dlon = lat2 - lat1, lon2 - lon1
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arcsin(np.sqrt(a))
            df['Distancia_Viagem_km'] = 6371.0 * c
            
            # Cria a marcação linha a linha: 1 = Casa, 0 = Fora, NaN = Sem GPS na linha
            df.loc[df['Distancia_Viagem_km'] <= config.RAIO_CASA_KM, 'Status_Local'] = 1
            df.loc[df['Distancia_Viagem_km'] > config.RAIO_CASA_KM, 'Status_Local'] = 0
            
            # Sabedoria de Equipe: 
            # Agrupa pelo dia do jogo (Data). Se algum atleta jogou Fora (0), todo o time ganha Fora (0).
            # Se não houver dados limpos de GPS para NINGUÉM naquele dia, assume Casa (1).
            df['Jogou_em_Casa'] = df.groupby('Data')['Status_Local'].transform('min').fillna(1)
            
        else:
            df['Jogou_em_Casa'] = 1

        # 5. Preencher Métricas Vazias e Calcular HIA
        df[config.COLS_METRICAS_PREENCHER_ZERO] = df[config.COLS_METRICAS_PREENCHER_ZERO].fillna(0)
        df['HIA'] = (
            df.get('V4 To8 Eff', 0) + df.get('V5 To8 Eff', 0) + 
            df.get('V6 To8 Eff', 0) + df.get('Acc3 Eff', 0) + df.get('Dec3 Eff', 0)
        )

        # ... (código anterior de Fator Casa e HIA) ...

        # 6. Placar e Datas
        if 'Placar' in df.columns:
            df['Diff_Gols'] = df['Placar'].apply(extrair_diff_gols)
        else:
            df['Diff_Gols'] = 0
            
        df['Data_Display'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%d/%m/%Y') + ' ' + df['Adversário'].astype(str)
        
        # --- ESTA É A CORREÇÃO CRÍTICA ---
        # Criamos a coluna Min_Num a partir do Interval para o predictive.py não dar erro
        nome_coluna_tempo = 'Interval (min)' if 'Interval (min)' in df.columns else 'Interval'
        df['Min_Num'] = pd.to_numeric(df[nome_coluna_tempo], errors='coerce').fillna(0)
        # ---------------------------------

        # 7. Fábrica de Recordes
        if 'Name' not in df.columns:
            raise KeyError("A coluna 'Name' não foi encontrada. Verifique o config.COLUNAS_NECESSARIAS.")

        # Usamos o Min_Num aqui também para manter a consistência
        df_sorted = df.sort_values(by=['Name', 'Data', 'Período', 'Min_Num']).copy()
        
        mapa_recordes = {
            'Total Distance': 'Dist_Total', 'Player Load': 'Load_Total',
            'V4 Dist': 'V4_Dist', 'V5 Dist': 'V5_Dist',
            'V4 To8 Eff': 'V4_Eff', 'V5 To8 Eff': 'V5_Eff', 'HIA': 'HIA_Total'
        }
        
        cols_calc = [c for c in mapa_recordes.keys() if c in df_sorted.columns]
        df_rolling = df_sorted.groupby(['Name', 'Data', 'Período'])[cols_calc].rolling(window=5, min_periods=1).sum().reset_index(drop=True)
        df_rolling['Name'] = df_sorted['Name'].values
        
        df_recordes = df_rolling.groupby('Name')[cols_calc].max().reset_index()
        df_recordes = df_recordes.rename(columns={col: f"Recorde_5min_{mapa_recordes[col]}" for col in cols_calc})

        return df, df_recordes
        
    except Exception as e:
        # Só usa st.error se estiver no Streamlit, senão usa print normal (para o terminal)
        mensagem = f"Erro ao carregar dados: {e}"
        if st.runtime.exists():
            st.error(mensagem)
        else:
            print(f"❌ {mensagem}")
        return pd.DataFrame(), pd.DataFrame()
