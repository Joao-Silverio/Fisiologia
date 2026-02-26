"""
=====================================================================
MOTOR ML - ARQUITETURA SNAPSHOT (CORREÇÃO DA ESCALA DO SLIDER)
=====================================================================
"""
import os
import pickle
import numpy as np
import pandas as pd
import config

MAPA_METRICAS = {
    'Dist_Total': 'Total Distance',
    'Load_Total': 'Player Load',
    'V4_Dist':    'V4 Dist',
    'V5_Dist':    'V5 Dist',
    'V4_Eff':     'V4 To8 Eff',
    'V5_Eff':     'V5 To8 Eff',
    'HIA_Total':  'HIA'
}

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

def projetar_com_modelo_treinado(modelo_dict, row_atleta, minutos_futuros,
                                 dist_acumulada_atual, media_min_geral, periodo, minuto_atual):
    """
    1. Calcula a projeção TOTAL até ao fim do tempo regulamentar.
    2. Recorta e devolve apenas os minutos que o utilizador escolheu no slider.
    Isso impede que a linha fique espremida!
    """
    features = modelo_dict['features']
    modelo = modelo_dict['modelo']
    
    sample = {f: row_atleta.get(f, 0) for f in features}
    sample_df = pd.DataFrame([sample])[features]

    # PREVISÃO DA IA (Para o final do tempo regulamentar)
    dist_final_prevista = float(modelo.predict(sample_df)[0])
    dist_restante = max(0.0, dist_final_prevista - dist_acumulada_atual)

    # O SEGREDO: Calculamos a escala ATÉ AO FIM DO JOGO (45 ou 50 min)
    minuto_final_periodo = 45 if periodo == 1 else 50
    
    # Se o jogo teve acréscimos e o slider for além dos 45, esticamos o cálculo
    minuto_limite_calculo = max(minuto_final_periodo, minutos_futuros[-1] if minutos_futuros else minuto_final_periodo)
    todos_minutos_restantes = list(range(minuto_atual + 1, minuto_limite_calculo + 1))
    
    pesos_totais = []
    for m in todos_minutos_restantes:
        peso = media_min_geral.loc[m] if m in media_min_geral.index else 1.0
        pesos_totais.append(max(0.01, peso))

    soma_pesos_totais = sum(pesos_totais) if sum(pesos_totais) > 0 else 1

    # DISTRIBUI O VOLUME NO RITMO CERTO (SEM ESPREMER)
    acumulado_pred = []
    acum = dist_acumulada_atual
    
    for m, peso in zip(todos_minutos_restantes, pesos_totais):
        # A distância sobe aos poucos, respeitando o ritmo até aos 45 minutos
        dist_minuto = dist_restante * (peso / soma_pesos_totais)
        acum += dist_minuto
        
        # Só devolvemos para o gráfico os minutos que estão dentro da seleção do Slider!
        if m in minutos_futuros:
            acumulado_pred.append(acum)

    return acumulado_pred, dist_final_prevista

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

    minutos_futuros = list(range(minuto_atual + 1, minuto_projecao_ate + 1))
    if not minutos_futuros:
        resultado['carga_projetada'] = carga_atual
        resultado['minuto_final_proj'] = minuto_atual
        return resultado

    placar_atual  = df_atual['Placar'].iloc[-1] if 'Placar' in df_atual.columns else 'N/A'
    resultado_ctx = df_atual['Resultado'].iloc[-1] if 'Resultado' in df_atual.columns else 'E'

    dias_desc = calcular_dias_descanso(df_historico, pd.to_datetime(jogo_atual_nome)) if hasattr(jogo_atual_nome, 'year') or isinstance(jogo_atual_nome, str) else 7

    # 1. DEFINIR VALOR PADRÃO LOGO NO INÍCIO
    jogou_em_casa_val = 1 
    
    # 2. TENTAR CAPTURAR O VALOR REAL DO DATASET
    if 'Jogou_em_Casa' in df_atual.columns:
        jogou_em_casa_val = df_atual['Jogou_em_Casa'].iloc[-1]
    elif 'Jogou_em_Casa' in df_historico.columns:
        jogou_em_casa_val = df_historico['Jogou_em_Casa'].iloc[-1]
    
    def soma_jogo(col):
        return df_historico.groupby(coluna_jogo)[col].sum().mean() if col in df_historico.columns else 0

    metric_target = 'Dist_Total'
    for k, v in MAPA_METRICAS.items():
        if v == coluna_distancia:
            metric_target = k
            break
            
    hia_cols = ['V4 To8 Eff', 'V5 To8 Eff', 'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff']
    if 'HIA' not in df_historico.columns:
        df_historico['HIA'] = df_historico[[c for c in hia_cols if c in df_historico.columns]].sum(axis=1) if any(c in df_historico.columns for c in hia_cols) else 0

    media_geral_num = soma_jogo(coluna_distancia)
    media_3j = df_historico.groupby(coluna_jogo)[coluna_distancia].sum().tail(3).mean()
    trend_dist = media_3j / (media_geral_num + 1) if media_geral_num > 0 else 1.0
    carga_3jogos_pl = df_historico.groupby(coluna_jogo)['Player Load'].sum().tail(3).sum() if 'Player Load' in df_historico.columns else 0

    media_min_geral = df_historico.groupby(coluna_minuto)[coluna_distancia].mean()

    modelo_dict = carregar_modelo_treinado(DIRETORIO_ATUAL, metrica_selecionada, periodo)
    acumulado_pred = []

    if modelo_dict is not None:
        row_atleta = {
            'Min_Num': minuto_atual,
            'Dias_Descanso': dias_desc,
            'N_Jogos': df_historico[coluna_jogo].nunique(),
            'Carga_3Jogos_PL': carga_3jogos_pl,
            'Diff_Gols': 1 if resultado_ctx == 'V' else (-1 if resultado_ctx == 'D' else 0),
            'Jogou_em_Casa': jogou_em_casa_val,
            f'{metric_target}_Acumulado_Agora': carga_atual,
            f'Media_Geral_{metric_target}': media_geral_num,
            f'Trend_{metric_target}': trend_dist
        }

        try:
            # Enviamos o período e o minuto_atual para o cálculo de proporção não espremer os dados
            acumulado_pred, dist_final_prev = projetar_com_modelo_treinado(
                modelo_dict, row_atleta, minutos_futuros, carga_atual, media_min_geral, periodo, minuto_atual
            )
            resultado['modelo_usado'] = f"XGBoost Snapshot (MAE: {modelo_dict['mae']:.1f})"
            resultado['mae_modelo']   = modelo_dict['mae']
        except Exception as e:
            acumulado_pred = []
            print(f"Modelo treinado falhou: {e}")

    if not acumulado_pred:
        curva_media_acum = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
        media_acum_agora = curva_media_acum.loc[minuto_atual] if minuto_atual in curva_media_acum.index else carga_atual
        fator_alvo = (carga_atual / media_acum_agora) if media_acum_agora > 0 else 1.0

        valor_acum = carga_atual
        for m in minutos_futuros:
            dist_g = media_min_geral.loc[m] if m in media_min_geral.index else 0
            valor_acum += max(0, dist_g * fator_alvo)
            acumulado_pred.append(valor_acum)
        resultado['modelo_usado'] = "Fallback (Média Ajustada)"

    # ==========================================================
    # BUSCA MAE DE PREDICT.PY PARA CALCULAR A "SOMBRA" DE CONFIANÇA
    # ==========================================================
    pred_superior = []
    pred_inferior = []
    
    # Busca o erro real do modelo (ex: 137m). Se o modelo falhar (Fallback), usa 5%
    erro_maximo = modelo_dict['mae'] if modelo_dict is not None and 'mae' in modelo_dict else (carga_atual * 0.05)
    
    for i, val in enumerate(acumulado_pred):
        # A sombra começa fina perto do corte e vai alargando até ao MAE máximo no final
        progresso = (i + 1) / max(len(acumulado_pred), 1)
        erro_neste_ponto = erro_maximo * progresso 
        
        pred_superior.append(val + erro_neste_ponto)
        pred_inferior.append(max(0, val - erro_neste_ponto)) # Evita distâncias negativas

    carga_projetada = acumulado_pred[-1] if acumulado_pred else carga_atual
    minuto_final_proj = minutos_futuros[-1] if minutos_futuros else minuto_atual
    
    curva_media_acum_final = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
    media_hist_final = curva_media_acum_final.loc[minuto_final_proj] if minuto_final_proj in curva_media_acum_final.index else carga_projetada
    fator_proj = (carga_projetada / media_hist_final) if media_hist_final > 0 else 1.0

    df_time_hoje = df_base[(df_base['Data'] == jogo_atual_nome) & (df_base['Período'] == periodo) & (df_base['Interval'] <= minuto_atual)]
    df_time_hist = df_base[(df_base['Data'] != jogo_atual_nome) & (df_base['Período'] == periodo) & (df_base['Interval'] <= minuto_atual)]
    carga_hoje_time = df_time_hoje.groupby('Name')[coluna_distancia].sum().mean() if not df_time_hoje.empty else 0
    carga_hist_time = df_time_hist.groupby(['Data', 'Name'])[coluna_distancia].sum().mean() if not df_time_hist.empty else carga_hoje_time
    
    delta_time_pct  = ((carga_hoje_time / carga_hist_time) - 1) * 100 if carga_hist_time > 0 else 0.0
    
    curva_media_acum = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
    media_acum_agora = curva_media_acum.loc[minuto_atual] if minuto_atual in curva_media_acum.index else carga_atual
    delta_alvo_pct = ((carga_atual / media_acum_agora) - 1) * 100 if media_acum_agora > 0 else 0.0

    resultado.update({
        'minutos_futuros': minutos_futuros, 'acumulado_pred': acumulado_pred,
        'pred_superior': pred_superior, 'pred_inferior': pred_inferior,
        'carga_projetada': carga_projetada, 'minuto_final_proj': minuto_final_proj,
        'delta_alvo_pct': delta_alvo_pct, 'delta_pl_pct': 0.0,
        'delta_projetado_pct': (fator_proj - 1) * 100, 'delta_time_pct': delta_time_pct,
        'delta_atleta_vs_time': delta_alvo_pct - delta_time_pct, 'placar_atual': placar_atual,
        'modelo_usado': resultado['modelo_usado']
    })
    return resultado