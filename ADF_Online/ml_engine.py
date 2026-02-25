"""
=====================================================================
MOTOR ML - VERSÃO FINAL (ESCALA CORRIGIDA + CURVA DE FADIGA)
=====================================================================
"""

import os
import pickle
import numpy as np
import pandas as pd
import config 

def carregar_modelo_treinado(diretorio, metrica_selecionada, periodo):
    if metrica_selecionada not in config.METRICAS_CONFIG: return None
    nome_base = config.METRICAS_CONFIG[metrica_selecionada]["arquivo_modelo"]
    nome_arquivo = nome_base.replace('.pkl', f'_T{periodo}.pkl')
    caminho = os.path.join(config.DIRETORIO_MODELOS, nome_arquivo)
    try:
        with open(caminho, 'rb') as f: return pickle.load(f)
    except FileNotFoundError: return None

def calcular_dias_descanso(df_atleta, jogo_atual):
    datas = sorted(df_atleta['Data'].unique())
    datas_anteriores = [d for d in datas if d < jogo_atual]
    if not datas_anteriores: return 7 
    ultimo_jogo = max(datas_anteriores)
    return min((jogo_atual - ultimo_jogo).days, 30)

def fator_fadiga_por_minuto(minuto, minuto_max_periodo=45):
    # Cria a curvatura natural da fadiga no gráfico (evita a linha reta)
    progresso = minuto / max(minuto_max_periodo, 1)
    decaimento = 1.0 - (0.25 * (progresso ** 2))
    return max(0.50, decaimento)

def projetar_com_modelo_treinado(modelo_dict, row_atleta, minutos_futuros,
                                 dist_acumulada_atual, minuto_atual, periodo):
    features = modelo_dict['features']
    modelo = modelo_dict['modelo']
    sample = {f: row_atleta.get(f, 0) for f in features}
    
    minuto_final_periodo = 45 if periodo == 1 else 50
    sample['Minutos'] = minuto_final_periodo
    sample_df = pd.DataFrame([sample])[features]

    # Agora a IA recebe os dados na escala certa e prevê um valor alto e coerente!
    dist_final_prevista = float(modelo.predict(sample_df)[0])

    dist_restante = dist_final_prevista - dist_acumulada_atual
    
    # Trava de segurança: se ele estiver batendo recordes, projeta para cima
    if dist_restante <= 0:
        ritmo = dist_acumulada_atual / max(minuto_atual, 1)
        dist_restante = ritmo * len(minutos_futuros) * 0.8
        dist_final_prevista = dist_acumulada_atual + dist_restante

    acumulado_pred = []
    acum = dist_acumulada_atual
    
    # Distribui os metros que faltam copiando o formato da fadiga natural (curva)
    fatores = [fator_fadiga_por_minuto(m, minuto_final_periodo) for m in minutos_futuros]
    soma_fatores = sum(fatores) if sum(fatores) > 0 else 1

    for fator in fatores:
        dist_minuto = dist_restante * (fator / soma_fatores)
        acum += dist_minuto
        acumulado_pred.append(acum)

    return acumulado_pred, dist_final_prevista

def projetar_fallback_shap(df_historico, coluna_distancia, coluna_acumulada,
                            coluna_minuto, minutos_futuros, carga_atual,
                            minuto_atual, fator_hoje, placar_atual,
                            media_min_geral, media_min_cenario, peso_placar):
    acumulado_pred = []
    valor_acum = carga_atual

    for m in minutos_futuros:
        dist_g = media_min_geral.loc[m]   if m in media_min_geral.index   else 0
        dist_c = media_min_cenario.loc[m] if m in media_min_cenario.index else dist_g

        dist_mesclada = (dist_c * peso_placar) + (dist_g * (1 - peso_placar))
        dist_mesclada = max(0, dist_mesclada)

        dist_projetada = dist_mesclada * fator_hoje
        valor_acum += dist_projetada
        acumulado_pred.append(valor_acum)

    return acumulado_pred

def executar_ml_ao_vivo(
    df_historico, df_atual, df_base,
    coluna_distancia, coluna_acumulada, coluna_minuto, coluna_jogo,
    jogo_atual_nome, periodo, minuto_projecao_ate, metrica_selecionada,
    atleta_selecionado, DIRETORIO_ATUAL
):
    resultado = {
        'minutos_futuros': [], 'acumulado_pred': [], 'pred_superior': [], 'pred_inferior': [],
        'carga_projetada': 0, 'minuto_final_proj': 0, 'delta_alvo_pct': 0.0, 'delta_pl_pct': 0.0,
        'delta_projetado_pct': 0.0, 'delta_time_pct': 0.0, 'delta_atleta_vs_time': 0.0, 
        'modelo_usado': 'Sem histórico', 'mae_modelo': None
    }

    if df_historico.empty or df_atual.empty: return resultado

    carga_atual       = df_atual[coluna_acumulada].iloc[-1]
    minuto_atual      = int(df_atual[coluna_minuto].iloc[-1])
    pl_atual_acumulado = df_atual['Player Load Acumulada'].iloc[-1] if 'Player Load Acumulada' in df_atual.columns else 1

    minutos_futuros = list(range(minuto_atual + 1, minuto_projecao_ate + 1))
    if not minutos_futuros:
        resultado['carga_projetada'] = carga_atual
        resultado['minuto_final_proj'] = minuto_atual
        return resultado

    placar_atual  = df_atual['Placar'].iloc[-1] if 'Placar' in df_atual.columns else 'N/A'
    resultado_ctx = df_atual['Resultado'].iloc[-1] if 'Resultado' in df_atual.columns else 'E'

    media_min_geral   = df_historico.groupby(coluna_minuto)[coluna_distancia].mean()
    df_hist_cenario   = df_historico[df_historico.get('Placar', pd.Series()) == placar_atual] if 'Placar' in df_historico.columns else pd.DataFrame()
    n_jogos_cenario   = df_hist_cenario[coluna_jogo].nunique() if not df_hist_cenario.empty else 0
    peso_placar       = 0.6 if n_jogos_cenario >= 3 else (0.3 if n_jogos_cenario > 0 else 0.0)
    media_min_cenario = df_hist_cenario.groupby(coluna_minuto)[coluna_distancia].mean() if not df_hist_cenario.empty else media_min_geral

    curva_media_acum = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
    media_acum_agora = curva_media_acum.loc[minuto_atual] if minuto_atual in curva_media_acum.index else carga_atual
    fator_alvo = (carga_atual / media_acum_agora) if media_acum_agora > 0 else 1.0

    curva_media_pl   = df_historico.groupby(coluna_minuto)['Player Load Acumulada'].mean() if 'Player Load Acumulada' in df_historico.columns else curva_media_acum
    media_pl_agora   = curva_media_pl.loc[minuto_atual] if minuto_atual in curva_media_pl.index else pl_atual_acumulado
    fator_pl = (pl_atual_acumulado / media_pl_agora) if media_pl_agora > 0 else 1.0
    fator_hoje = (fator_alvo * 0.78) + (fator_pl * 0.22)

    dias_desc = calcular_dias_descanso(df_historico, pd.to_datetime(jogo_atual_nome)) if hasattr(jogo_atual_nome, 'year') or isinstance(jogo_atual_nome, str) else 7

    # =========================================================================
    # CORREÇÃO CRÍTICA: RECONSTRUINDO AS FEATURES NA ESCALA CORRETA (POR JOGO)
    # =========================================================================
    hia_cols = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff']
    df_historico['HIA'] = df_historico[[c for c in hia_cols if c in df_historico.columns]].sum(axis=1) if any(c in df_historico.columns for c in hia_cols) else 0
    
    hs_cols = ['V4 Dist', 'V5 Dist', 'V6 Dist']
    df_historico['HS_Dist'] = df_historico[[c for c in hs_cols if c in df_historico.columns]].sum(axis=1) if any(c in df_historico.columns for c in hs_cols) else 0
    
    sprint_cols = ['V6 Dist', 'V7 Dist', 'V8 Dist']
    df_historico['Sprint_Dist'] = df_historico[[c for c in sprint_cols if c in df_historico.columns]].sum(axis=1) if any(c in df_historico.columns for c in sprint_cols) else 0

    def soma_jogo(col):
        if col not in df_historico.columns: return 0
        return df_historico.groupby(coluna_jogo)[col].sum().mean()

    def soma_jogo_ctx(col, ctx):
        if col not in df_historico.columns or 'Resultado' not in df_historico.columns: return 0
        df_c = df_historico[df_historico['Resultado'] == ctx]
        if df_c.empty: return soma_jogo(col)
        return df_c.groupby(coluna_jogo)[col].sum().mean()

    media_geral = soma_jogo(coluna_distancia)
    media_3j = df_historico.groupby(coluna_jogo)[coluna_distancia].sum().tail(3).mean()
    trend_dist = media_3j / (media_geral + 1) if media_geral > 0 else 1.0

    modelo_dict = carregar_modelo_treinado(DIRETORIO_ATUAL, metrica_selecionada, periodo)
    acumulado_pred = []

    if modelo_dict is not None:
        row_atleta = {
            'Minutos':              45 if periodo == 1 else 50,
            'Dias_Descanso':        dias_desc,
            'Diff_Gols':            1 if resultado_ctx == 'V' else (-1 if resultado_ctx == 'D' else 0),
            'N_Jogos':              df_historico[coluna_jogo].nunique(),
            'Media_Dist_Geral':     media_geral,
            'Media_Load_Geral':     soma_jogo('Player Load'),
            'Media_HIA_Geral':      soma_jogo('HIA'),
            'Media_HS_Geral':       soma_jogo('HS_Dist'),
            'Media_Sprint_Geral':   soma_jogo('Sprint_Dist'),
            'Media_HR_Geral':       df_historico['HR_Pct'].mean() if 'HR_Pct' in df_historico.columns else 0,
            'Media_Dist_Contexto':  soma_jogo_ctx(coluna_distancia, resultado_ctx),
            'Media_HIA_Contexto':   soma_jogo_ctx('HIA', resultado_ctx),
            'Media_Load_Contexto':  soma_jogo_ctx('Player Load', resultado_ctx),
            'Carga_3Jogos':         df_historico.groupby(coluna_jogo)['Player Load'].sum().tail(3).sum() if 'Player Load' in df_historico.columns else 0,
            'Carga_7Jogos':         df_historico.groupby(coluna_jogo)['Player Load'].sum().tail(7).sum() if 'Player Load' in df_historico.columns else 0,
            'Trend_Dist':           trend_dist,
            'Metabolic Power':      df_historico['Metabolic Power'].mean() if 'Metabolic Power' in df_historico.columns else 0,
            'Equiv Distance Index': df_historico['Equiv Distance Index'].mean() if 'Equiv Distance Index' in df_historico.columns else 0,
            'Work Rate Dist':       soma_jogo('Work Rate Dist')
        }

        try:
            acumulado_pred, dist_final_prev = projetar_com_modelo_treinado(
                modelo_dict, row_atleta, minutos_futuros, carga_atual, minuto_atual, periodo
            )
            resultado['modelo_usado'] = f"XGBoost (MAE histórico: {modelo_dict['mae']:.0f}m)"
            resultado['mae_modelo']   = modelo_dict['mae']
        except Exception as e:
            acumulado_pred = []
            print(f"Modelo treinado falhou: {e}")

    if not acumulado_pred:
        acumulado_pred = projetar_fallback_shap(
            df_historico, coluna_distancia, coluna_acumulada, coluna_minuto, minutos_futuros, carga_atual,
            minuto_atual, fator_hoje, placar_atual, media_min_geral, media_min_cenario, peso_placar
        )
        resultado['modelo_usado'] = "Fallback SHAP (Pesos Históricos Ajustados)"

    pred_superior = []
    pred_inferior = []
    for i, val in enumerate(acumulado_pred):
        margem = 0.04 + (i / max(len(acumulado_pred), 1)) * 0.08 
        pred_superior.append(val * (1 + margem))
        pred_inferior.append(val * (1 - margem))

    carga_projetada  = acumulado_pred[-1] if acumulado_pred else carga_atual
    minuto_final_proj = minutos_futuros[-1] if minutos_futuros else minuto_atual

    media_hist_final = curva_media_acum.loc[minuto_final_proj] if minuto_final_proj in curva_media_acum.index else media_acum_agora
    fator_proj       = (carga_projetada / media_hist_final) if media_hist_final > 0 else 1.0

    df_time_hoje = df_base[(df_base['Data'] == jogo_atual_nome) & (df_base['Período'] == periodo) & (df_base['Interval'] <= minuto_atual)]
    df_time_hist = df_base[(df_base['Data'] != jogo_atual_nome) & (df_base['Período'] == periodo) & (df_base['Interval'] <= minuto_atual)]
    carga_hoje_time = df_time_hoje.groupby('Name')[coluna_distancia].sum().mean() if not df_time_hoje.empty else 0
    carga_hist_time = df_time_hist.groupby(['Data', 'Name'])[coluna_distancia].sum().mean() if not df_time_hist.empty else carga_hoje_time
    
    delta_time_pct  = ((carga_hoje_time / carga_hist_time) - 1) * 100 if carga_hist_time > 0 else 0.0
    delta_alvo_pct  = (fator_alvo - 1) * 100
    delta_pl_pct    = (fator_pl - 1) * 100

    resultado.update({
        'minutos_futuros':     minutos_futuros, 'acumulado_pred':      acumulado_pred,
        'pred_superior':       pred_superior,   'pred_inferior':       pred_inferior,
        'carga_projetada':     carga_projetada, 'minuto_final_proj':   minuto_final_proj,
        'delta_alvo_pct':      delta_alvo_pct,  'delta_pl_pct':        delta_pl_pct,
        'delta_projetado_pct': (fator_proj - 1) * 100, 'delta_time_pct': delta_time_pct,
        'delta_atleta_vs_time': delta_alvo_pct - delta_time_pct, 'placar_atual': placar_atual,
        'peso_placar':         peso_placar,     'fator_hoje':          fator_hoje,
        'dias_descanso':       dias_desc
    })
    return resultado