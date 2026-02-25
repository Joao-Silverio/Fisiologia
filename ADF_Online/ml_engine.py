"""
=====================================================================
BLOCO DE ML MELHORADO — Substituir no live_tracker.py
Baseado nos resultados SHAP:
  1. Usa o modelo XGBoost treinado pelo predictive_v3.py (se disponível)
  2. Fallback inteligente com pesos derivados do SHAP quando modelo ausente
  3. Projeção dinâmica: fator de fadiga varia por minuto (curvas não-planas)
  4. Incorpora Metabolic Power, Dias_Descanso e Dist_Acum em tempo real
=====================================================================
"""

import os
import pickle
import numpy as np
import pandas as pd
import config # <-- Importamos as configurações


import os
import pickle
import numpy as np
import pandas as pd
import config # <-- Importamos as configurações

def carregar_modelo_treinado(diretorio, metrica_selecionada):
    """Carrega o modelo específico baseado no config.py, buscando na pasta models."""
    if metrica_selecionada not in config.METRICAS_CONFIG:
        return None
        
    nome_arquivo = config.METRICAS_CONFIG[metrica_selecionada]["arquivo_modelo"]
    
    # Agora ele usa o caminho DIRETORIO_MODELOS configurado no config.py
    caminho = os.path.join(config.DIRETORIO_MODELOS, nome_arquivo)
    
    try:
        with open(caminho, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return None

def calcular_dias_descanso(df_atleta, jogo_atual):
    """Calcula dias desde o jogo anterior do atleta."""
    datas = sorted(df_atleta['Data'].unique())
    datas_anteriores = [d for d in datas if d < jogo_atual]
    if not datas_anteriores:
        return 7  # valor padrão neutro
    ultimo_jogo = max(datas_anteriores)
    return min((jogo_atual - ultimo_jogo).days, 30)


def calcular_media_historica_atleta(df_historico, coluna_distancia):
    """Média de distância total por jogo no histórico."""
    if df_historico.empty:
        return 0
    return df_historico.groupby('Data')[coluna_distancia].sum().mean()


def calcular_media_por_contexto(df_historico, coluna_distancia, resultado_atual):
    """Média histórica filtrando pelo mesmo contexto de resultado (V/E/D)."""
    if 'Resultado' not in df_historico.columns or df_historico.empty:
        return None
    df_ctx = df_historico[df_historico['Resultado'] == resultado_atual]
    if len(df_ctx['Data'].unique()) < 3:
        return None
    return df_ctx.groupby('Data')[coluna_distancia].sum().mean()


def fator_fadiga_por_minuto(minuto, minuto_max_periodo=45):
    """
    Modela o decaimento fisiológico ao longo do tempo.
    Baseado no SHAP: Metabolic Power negativo sugere que atletas intensos
    decaem mais rápido. Curva sigmoide suavizada.
    Retorna um multiplicador entre 0.85 e 1.0
    """
    progresso = minuto / max(minuto_max_periodo, 1)
    # Decaimento leve nos primeiros 60%, acelerado após isso
    decaimento = 1.0 - (0.15 * (progresso ** 2))
    return max(0.75, decaimento)


def projetar_com_modelo_treinado(modelo_dict, row_atleta, minutos_futuros,
                                  dist_acumulada_atual, minuto_atual):
    """
    Usa o XGBoost treinado para projetar a distância final.
    Interpola linearmente entre o acumulado atual e a previsão do modelo.
    """
    features  = modelo_dict['features']
    modelo    = modelo_dict['modelo']

    sample = {f: row_atleta.get(f, 0) for f in features}
    sample['Minutos'] = 90  # prever o jogo completo
    sample_df = pd.DataFrame([sample])[features]

    dist_final_prevista = float(modelo.predict(sample_df)[0])

    # Distribui linearmente entre acumulado atual e o total previsto
    dist_restante = max(0, dist_final_prevista - dist_acumulada_atual)
    minutos_restantes = max(1, len(minutos_futuros))

    acumulado_pred = []
    acum = dist_acumulada_atual

    for i, m in enumerate(minutos_futuros):
        progresso = (i + 1) / minutos_restantes
        # Aplica fator de fadiga: ritmo não é constante, cai no fim
        fator = fator_fadiga_por_minuto(m)
        dist_este_minuto = (dist_restante / minutos_restantes) * fator
        acum += dist_este_minuto
        acumulado_pred.append(acum)

    return acumulado_pred, dist_final_prevista


def projetar_fallback_shap(df_historico, coluna_distancia, coluna_acumulada,
                            coluna_minuto, minutos_futuros, carga_atual,
                            minuto_atual, fator_hoje, placar_atual,
                            media_min_geral, media_min_cenario, peso_placar,
                            metabolic_power_atual=None):
    """
    Fallback melhorado quando o modelo treinado não está disponível.
    Incorpora:
      - Fator de fadiga dinâmico por minuto (baseado no SHAP)
      - Ajuste por Metabolic Power (2ª feature mais importante no SHAP)
      - Pesos derivados do SHAP (não mais fixos em 70/30)
    """

    # Ajuste por Metabolic Power (SHAP mostrou efeito negativo na distância)
    # Atletas de alta potência metabólica tendem a rodar MENOS distância
    fator_met_power = 1.0
    if metabolic_power_atual is not None and metabolic_power_atual > 0:
        # Normalizado: se MetPow > média histórica, ligeiramente reduz projeção
        media_met = df_historico['Metabolic Power'].mean() if 'Metabolic Power' in df_historico.columns else metabolic_power_atual
        if media_met > 0:
            ratio_met = metabolic_power_atual / media_met
            # Efeito suave: +10% MetPow → -2% distância (baseado no SHAP negativo)
            fator_met_power = 1.0 - ((ratio_met - 1.0) * 0.15)
            fator_met_power = np.clip(fator_met_power, 0.85, 1.15)

    acumulado_pred = []
    valor_acum = carga_atual

    for m in minutos_futuros:
        dist_g = media_min_geral.loc[m]   if m in media_min_geral.index   else 0
        dist_c = media_min_cenario.loc[m] if m in media_min_cenario.index else dist_g

        # Mescla cenário tático + geral (pesos do SHAP: contexto tem ~6% do SHAP)
        dist_mesclada = (dist_c * peso_placar) + (dist_g * (1 - peso_placar))
        dist_mesclada = max(0, dist_mesclada)

        # Aplica fator do atleta hoje + fadiga dinâmica + metabolic power
        fator_fadiga  = fator_fadiga_por_minuto(m)
        dist_projetada = dist_mesclada * fator_hoje * fator_fadiga * fator_met_power

        valor_acum += dist_projetada
        acumulado_pred.append(valor_acum)

    return acumulado_pred


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÃO PRINCIPAL — Substituir o bloco "Inteligência Artificial Ativada"
# ─────────────────────────────────────────────────────────────────────────────
def executar_ml_ao_vivo(
    df_historico, df_atual, df_base,
    coluna_distancia, coluna_acumulada, coluna_minuto, coluna_jogo,
    jogo_atual_nome, periodo, minuto_projecao_ate, metrica_selecionada,
    atleta_selecionado, DIRETORIO_ATUAL
):
    """
    Motor ML unificado. Retorna dict com todos os valores para KPIs e gráfico.
    """
    resultado = {
        'minutos_futuros': [], 'acumulado_pred': [],
        'pred_superior': [], 'pred_inferior': [],
        'carga_projetada': 0, 'minuto_final_proj': 0,
        'delta_alvo_pct': 0.0, 'delta_pl_pct': 0.0,
        'delta_projetado_pct': 0.0, 'delta_time_pct': 0.0,
        'delta_atleta_vs_time': 0.0, 'modelo_usado': 'Sem histórico',
        'mae_modelo': None
    }

    if df_historico.empty or df_atual.empty:
        return resultado

    carga_atual       = df_atual[coluna_acumulada].iloc[-1]
    minuto_atual      = int(df_atual[coluna_minuto].iloc[-1])
    pl_atual_acumulado = df_atual['Player Load Acumulada'].iloc[-1] \
                         if 'Player Load Acumulada' in df_atual.columns else 1

    minutos_futuros = list(range(minuto_atual + 1, minuto_projecao_ate + 1))
    if not minutos_futuros:
        resultado['carga_projetada']  = carga_atual
        resultado['minuto_final_proj'] = minuto_atual
        return resultado

    # ── Placar e resultado ───────────────────────────────────────────────────
    placar_atual  = df_atual['Placar'].iloc[-1]   if 'Placar'    in df_atual.columns else 'N/A'
    resultado_ctx = df_atual['Resultado'].iloc[-1] if 'Resultado' in df_atual.columns else 'E'

    media_min_geral   = df_historico.groupby(coluna_minuto)[coluna_distancia].mean()
    df_hist_cenario   = df_historico[df_historico.get('Placar', pd.Series()) == placar_atual] \
                        if 'Placar' in df_historico.columns else pd.DataFrame()
    n_jogos_cenario   = df_hist_cenario[coluna_jogo].nunique() if not df_hist_cenario.empty else 0
    peso_placar       = 0.6 if n_jogos_cenario >= 3 else (0.3 if n_jogos_cenario > 0 else 0.0)
    media_min_cenario = df_hist_cenario.groupby(coluna_minuto)[coluna_distancia].mean() \
                        if not df_hist_cenario.empty else media_min_geral

    # ── Fator do atleta hoje vs histórico (baseado no SHAP: Media_Dist_Geral) ─
    curva_media_acum = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
    media_acum_agora = curva_media_acum.loc[minuto_atual] \
                       if minuto_atual in curva_media_acum.index else carga_atual
    fator_alvo = (carga_atual / media_acum_agora) if media_acum_agora > 0 else 1.0

    curva_media_pl   = df_historico.groupby(coluna_minuto)['Player Load Acumulada'].mean() \
                       if 'Player Load Acumulada' in df_historico.columns else curva_media_acum
    media_pl_agora   = curva_media_pl.loc[minuto_atual] \
                       if minuto_atual in curva_media_pl.index else pl_atual_acumulado
    fator_pl = (pl_atual_acumulado / media_pl_agora) if media_pl_agora > 0 else 1.0

    # Pesos baseados no SHAP: Media_Dist_Geral (1011) >> Player Load (290)
    # Proporção aproximada: 78% distância, 22% carga
    fator_hoje = (fator_alvo * 0.78) + (fator_pl * 0.22)

    # ── Metabolic Power atual (2ª feature mais importante no SHAP) ───────────
    # Em vez de média geral do jogo, puxamos a média apenas até o momento do CORTE
    met_power_atual = 0.0
    if 'Metabolic Power' in df_atual.columns:
        # Pega a média dos últimos 5 minutos ANTES do corte, se possível
        ultimos_5_minutos = df_atual.tail(5) 
        met_power_atual = ultimos_5_minutos['Metabolic Power'].mean()
        
        # Se mesmo assim der nulo (NaN), substitui pela média histórica para não bugar o XGBoost
        if np.isnan(met_power_atual):
             met_power_atual = df_historico['Metabolic Power'].mean() if 'Metabolic Power' in df_historico.columns else 0.0

    # ── Dias de descanso ─────────────────────────────────────────────────────
    dias_desc = calcular_dias_descanso(
        df_historico, pd.to_datetime(jogo_atual_nome)
    ) if hasattr(jogo_atual_nome, 'year') or isinstance(jogo_atual_nome, str) else 7

    # ── Tentar modelo treinado primeiro ──────────────────────────────────────
    modelo_dict = carregar_modelo_treinado(DIRETORIO_ATUAL, metrica_selecionada)
    acumulado_pred = []

    if modelo_dict is not None:
        # Montar o vetor de features para o último estado do atleta
        row_atleta = {
            'Minutos':              minuto_atual,
            'Dias_Descanso':        dias_desc,
            'Media_Dist_Geral':     calcular_media_historica_atleta(df_historico, coluna_distancia),
            'Media_Dist_Contexto':  calcular_media_por_contexto(df_historico, coluna_distancia, resultado_ctx) or
                                    calcular_media_historica_atleta(df_historico, coluna_distancia),
            'Media_HIA_Geral':      df_historico['HIA'].mean() if 'HIA' in df_historico.columns else 0,
            'Media_HIA_Contexto':   0,
            'Media_Load_Geral':     df_historico['Player Load'].sum() / max(df_historico[coluna_jogo].nunique(), 1)
                                    if 'Player Load' in df_historico.columns else 0,
            'Media_HS_Geral':       0,
            'Media_Sprint_Geral':   0,
            'Media_HR_Geral':       df_historico['HR_Pct'].mean() if 'HR_Pct' in df_historico.columns else 0,
            'Media_Load_Contexto':  0,
            'Carga_3Jogos':         df_historico.groupby(coluna_jogo)['Player Load'].sum().tail(3).sum()
                                    if 'Player Load' in df_historico.columns else 0,
            'Carga_7Jogos':         df_historico.groupby(coluna_jogo)['Player Load'].sum().tail(7).sum()
                                    if 'Player Load' in df_historico.columns else 0,
            'Trend_Dist':           fator_alvo,
            'Diff_Gols':            1 if resultado_ctx == 'V' else (-1 if resultado_ctx == 'D' else 0),
            'N_Jogos':              df_historico[coluna_jogo].nunique(),
            'Metabolic Power':      met_power_atual or 0,
            'Equiv Distance Index': df_historico['Equiv Distance Index'].mean()
                                    if 'Equiv Distance Index' in df_historico.columns else 0,
            'Work Rate Dist':       df_historico['Work Rate Dist'].mean()
                                    if 'Work Rate Dist' in df_historico.columns else 0,
        }

        try:
            acumulado_pred, dist_final_prev = projetar_com_modelo_treinado(
                modelo_dict, row_atleta, minutos_futuros, carga_atual, minuto_atual
            )
            resultado['modelo_usado'] = f"XGBoost (MAE histórico: {modelo_dict['mae']:.0f}m)"
            resultado['mae_modelo']   = modelo_dict['mae']
        except Exception as e:
            acumulado_pred = []  # vai cair no fallback abaixo
            print(f"Modelo treinado falhou: {e}, usando fallback")

    if not acumulado_pred:
        # Fallback com pesos derivados do SHAP
        acumulado_pred = projetar_fallback_shap(
            df_historico, coluna_distancia, coluna_acumulada,
            coluna_minuto, minutos_futuros, carga_atual,
            minuto_atual, fator_hoje, placar_atual,
            media_min_geral, media_min_cenario, peso_placar,
            metabolic_power_atual=met_power_atual
        )
        resultado['modelo_usado'] = f"Fallback SHAP (pesos: Dist 78%, PL 22%, MetPow ajustado)"

    # ── Margem de erro dinâmica (maior no futuro distante) ───────────────────
    # Em vez de margem fixa de 5%, cresce com a distância no tempo
    pred_superior = []
    pred_inferior = []
    for i, val in enumerate(acumulado_pred):
        margem = 0.04 + (i / max(len(acumulado_pred), 1)) * 0.08  # 4% a 12%
        pred_superior.append(val * (1 + margem))
        pred_inferior.append(val * (1 - margem))

    # ── KPIs ─────────────────────────────────────────────────────────────────
    carga_projetada  = acumulado_pred[-1] if acumulado_pred else carga_atual
    minuto_final_proj = minutos_futuros[-1] if minutos_futuros else minuto_atual

    media_hist_final = curva_media_acum.loc[minuto_final_proj] \
                       if minuto_final_proj in curva_media_acum.index else media_acum_agora
    fator_proj       = (carga_projetada / media_hist_final) if media_hist_final > 0 else 1.0

    # Ritmo coletivo
    df_time_hoje = df_base[
        (df_base['Data'] == jogo_atual_nome) &
        (df_base['Período'] == periodo) &
        (df_base['Interval'] <= minuto_atual)
    ]
    df_time_hist = df_base[
        (df_base['Data'] != jogo_atual_nome) &
        (df_base['Período'] == periodo) &
        (df_base['Interval'] <= minuto_atual)
    ]
    carga_hoje_time = df_time_hoje.groupby('Name')[coluna_distancia].sum().mean() \
                      if not df_time_hoje.empty else 0
    carga_hist_time = df_time_hist.groupby(['Data', 'Name'])[coluna_distancia].sum().mean() \
                      if not df_time_hist.empty else carga_hoje_time
    delta_time_pct  = ((carga_hoje_time / carga_hist_time) - 1) * 100 \
                      if carga_hist_time > 0 else 0.0
    delta_alvo_pct  = (fator_alvo - 1) * 100
    delta_pl_pct    = (fator_pl - 1) * 100

    resultado.update({
        'minutos_futuros':     minutos_futuros,
        'acumulado_pred':      acumulado_pred,
        'pred_superior':       pred_superior,
        'pred_inferior':       pred_inferior,
        'carga_projetada':     carga_projetada,
        'minuto_final_proj':   minuto_final_proj,
        'delta_alvo_pct':      delta_alvo_pct,
        'delta_pl_pct':        delta_pl_pct,
        'delta_projetado_pct': (fator_proj - 1) * 100,
        'delta_time_pct':      delta_time_pct,
        'delta_atleta_vs_time': delta_alvo_pct - delta_time_pct,
        'placar_atual':        placar_atual,
        'peso_placar':         peso_placar,
        'fator_hoje':          fator_hoje,
        'dias_descanso':       dias_desc,
        'met_power_atual':     met_power_atual,
    })
    return resultado
