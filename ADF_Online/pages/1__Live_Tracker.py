import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objs as go
import plotly.express as px
import shutil
import os
from streamlit_autorefresh import st_autorefresh

# 1. CONFIGURAÇÃO DA PÁGINA WEB
st.set_page_config(page_title="Live Tracker Físico", layout="wide")

# =====================================================================
# AUTO-REFRESH (Atualiza a página a cada 60 segundos)
# =====================================================================
contador = st_autorefresh(interval=60000, limit=1000, key="live_tracker_refresh")

st.title('⚽ Live Tracker: Projeção de Carga Física')
st.caption(f"Última atualização automática: Ciclo {contador}")

import warnings

# 1. Esconde os avisos chatos do openpyxl sobre validação de dados
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

import os
import shutil
import warnings

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# 1. Função que descobre exatamente a que horas o ficheiro foi guardado pela última vez
def obter_hora_modificacao(caminho_ficheiro):
    try:
        return os.path.getmtime(caminho_ficheiro)
    except FileNotFoundError:
        return 0

arquivo_original = 'Teste gemini.xlsx - Planilha1.csv' # Substitua pelo nome correto do seu CSV final
hora_atualizacao = obter_hora_modificacao(arquivo_original)

# 2. CARREGAR OS DADOS (Agora SEM o ttl=10. O cache só recarrega se a "hora_mod" mudar)
import os
import shutil
import warnings

warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

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


@st.cache_resource(show_spinner=False)
def carregar_dados(hora_mod):
    arquivo_temp = 'ADF_TEMP_LIVE.xlsb'
    
    try:
        # A cópia sombra garante que o Python não brigue com o seu Excel quando você apertar "Salvar"
        shutil.copy2(arquivo_original, arquivo_temp)
        
        # 1. Lista com EXATAMENTE as colunas que o Live Tracker precisa
        colunas_necessarias = [
            'Data', 'Interval', 'Name', 'Período', 'Placar', 'Adversário',
            'Total Distance', 'V4 Dist', 'V4 To8 Eff', 'V5 To8 Eff', 
            'V6 To8 Eff', 'Acc3 Eff', 'Dec3 Eff', 'Player Load'  # <-- ADICIONADO
        ]
        
        # 2. Lemos o Excel usando o motor ultra-rápido (calamine) e SÓ as colunas que importam
        df = pd.read_excel(
            arquivo_temp, 
            engine='calamine', 
            usecols=colunas_necessarias
        ) 
        
        df.columns = df.columns.str.strip()
        return df
        
    except PermissionError:
        st.toast("⏳ O Excel está aberto e sendo salvo. O painel vai atualizar no próximo ciclo.")
        return None
    except ValueError as e:
        # Prevenção: Se faltar alguma coluna na lista acima, ele avisa em vez de quebrar
        st.error(f"Erro nas colunas: {e}")
        return None
    except Exception as e:
        st.error(f"Erro na leitura: {e}")
        return None

df_completo = carregar_dados(hora_atualizacao)

if df_completo is None:
    st.stop()

# Formatar datas para exibição bonita (dd/mm/yyyy Adversário)
df_completo['Data_Display'] = pd.to_datetime(df_completo['Data']).dt.strftime('%d/%m/%Y') + ' ' + df_completo['Adversário'].astype(str)

# Definição das colunas base
coluna_jogo = 'Data'
coluna_minuto = 'Interval'

# 3. FILTROS NA TELA
st.sidebar.header("Filtros de Análise")
lista_atletas = df_completo['Name'].dropna().unique()
atleta_selecionado = st.sidebar.selectbox("Selecione o Atleta", lista_atletas)

metrica_selecionada = st.sidebar.selectbox("Selecione a Métrica", ["Total Distance", "V4 Dist"])

# Criar mapeamento Exibição -> Data Original para usar nos selectbox
mapa_data_display = dict(zip(df_completo['Data_Display'], df_completo['Data']))


# Define as colunas conforme a métrica
if metrica_selecionada == "Total Distance":
    coluna_distancia = 'Total Distance'
    coluna_acumulada = 'Dist Acumulada'
    titulo_grafico = f'Projeção de Distância - {atleta_selecionado}'
else:
    coluna_distancia = 'V4 Dist'
    coluna_acumulada = 'V4 Dist Acumulada'
    titulo_grafico = f'Projeção de V4 Dist - {atleta_selecionado}'

# Filtrar o dataframe só para o atleta escolhido
df_atleta = df_completo[df_completo['Name'] == atleta_selecionado].copy()

# Filtro para o tempo (primeiro/segundo)
opcao_tempo = st.sidebar.radio("Tempo", ("Ambos", "1º Tempo", "2º Tempo"))

if opcao_tempo == "1º Tempo":
    df_atleta = df_atleta[df_atleta['Período'] == 1]
elif opcao_tempo == "2º Tempo":
    df_atleta = df_atleta[df_atleta['Período'] == 2]

# Calcular o Acumulado DEPOIS de filtrar o Tempo (Garante que o 2º tempo comece do zero)
df_atleta['Dist Acumulada'] = df_atleta.groupby(coluna_jogo)['Total Distance'].cumsum()
df_atleta['V4 Dist Acumulada'] = df_atleta.groupby(coluna_jogo)['V4 Dist'].cumsum()
df_atleta['Player Load Acumulada'] = df_atleta.groupby(coluna_jogo)['Player Load'].cumsum()

# Novo filtro para o jogo
lista_jogos = df_atleta[coluna_jogo].unique()
lista_jogos_com_display = [(jogo, df_completo[df_completo['Data'] == jogo]['Data_Display'].iloc[0]) for jogo in lista_jogos if jogo in df_completo['Data'].values]
# Ordenar em ordem decrescente por data (mais recentes primeiro)
lista_jogos_com_display = sorted(lista_jogos_com_display, key=lambda x: x[0], reverse=True)
lista_jogos_display = [display for _, display in lista_jogos_com_display]
jogo_selecionado_display = st.sidebar.selectbox("Selecione o Jogo para Projeção", lista_jogos_display)
# Encontrar a data original correspondente
jogo_selecionado = next((data for data, display in lista_jogos_com_display if display == jogo_selecionado_display), jogo_selecionado_display)

df = df_atleta.dropna(subset=[coluna_minuto, coluna_acumulada]).copy()

if not df.empty:
    max_minutos_por_jogo = df.groupby(coluna_jogo)[coluna_minuto].max()
    jogo_atual_nome = jogo_selecionado
    minuto_atual_max = int(max_minutos_por_jogo[jogo_atual_nome])
    minuto_final_partida = int(max_minutos_por_jogo.max())
    
    # Slider para controlar até que minuto fazer a projeção
    minuto_projecao_ate = st.sidebar.slider(
        "Projete até o minuto:",
        min_value=minuto_atual_max,
        max_value=minuto_final_partida,
        value=minuto_final_partida,
        step=1
    ) 

    # Separar os dados atuais dos históricos
    df_historico = df[df[coluna_jogo] != jogo_atual_nome].copy()
    df_atual = df[df[coluna_jogo] == jogo_atual_nome].sort_values(coluna_minuto)

    if not df_historico.empty and not df_atual.empty:
        
        # =====================================================================
        # INTELIGÊNCIA ARTIFICIAL: PROJEÇÃO HÍBRIDA (TÁTICA + HISTÓRICO)
        # =====================================================================
        col_placar = 'Placar' # <--- MUDE AQUI se o nome da coluna de placar for outro
        
        media_min_geral = df_historico.groupby(coluna_minuto)[coluna_distancia].mean()
        
        if col_placar in df_atual.columns and col_placar in df_historico.columns:
            placar_atual = df_atual[col_placar].iloc[-1]
            df_hist_cenario = df_historico[df_historico[col_placar] == placar_atual]
            
            if not df_hist_cenario.empty:
                media_min_cenario = df_hist_cenario.groupby(coluna_minuto)[coluna_distancia].mean()
                peso_placar = 0.7 if len(df_hist_cenario[coluna_jogo].unique()) >= 3 else 0.4
            else:
                media_min_cenario = media_min_geral
                peso_placar = 0.0
                placar_atual = "Sem dados prévios"
        else:
            media_min_cenario = media_min_geral
            peso_placar = 0.0
            placar_atual = "Coluna não encontrada"
            
        # Exibe como o algoritmo está pensando para o Treinador ver
        st.info(f"🧠 **ML Engine:** Projeção baseada **{peso_placar*100:.0f}%** no cenário tático ('{placar_atual}') e **{(1-peso_placar)*100:.0f}%** no perfil físico geral.")

        # Curvas médias acumuladas GERAIS (Métrica Alvo e Player Load)
        curva_media_acumulada_geral = df_historico.groupby(coluna_minuto)[coluna_acumulada].mean()
        curva_media_pl_geral = df_historico.groupby(coluna_minuto)['Player Load Acumulada'].mean()
        
        valor_atual_acumulado = df_atual[coluna_acumulada].iloc[-1]
        pl_atual_acumulado = df_atual['Player Load Acumulada'].iloc[-1]
        minuto_atual = df_atual[coluna_minuto].iloc[-1]
        
        # Busca a média histórica EXATAMENTE neste minuto
        if minuto_atual in curva_media_acumulada_geral.index:
            media_acumulada_neste_minuto = curva_media_acumulada_geral.loc[minuto_atual]
            media_pl_neste_minuto = curva_media_pl_geral.loc[minuto_atual] if minuto_atual in curva_media_pl_geral.index else pl_atual_acumulado
        else:
            media_acumulada_neste_minuto = valor_atual_acumulado 
            media_pl_neste_minuto = pl_atual_acumulado
            
        # 1. Fator da Métrica (Ele está correndo mais rápido hoje?)
        fator_alvo = (valor_atual_acumulado / media_acumulada_neste_minuto) if media_acumulada_neste_minuto > 0 else 1.0
        
        # 2. Fator Metabólico (Ele está gastando mais energia hoje?)
        fator_pl = (pl_atual_acumulado / media_pl_neste_minuto) if media_pl_neste_minuto > 0 else 1.0
        
        # 3. BLENDING: O ML agora usa o Player Load para punir ou impulsionar a projeção
        # Ex: 70% da projeção vem do ritmo atual da métrica, 30% vem do desgaste geral do corpo (PL)
        peso_player_load = 0.3 
        fator_hoje = (fator_alvo * (1 - peso_player_load)) + (fator_pl * peso_player_load)

        # Atualiza a mensagem na tela para você saber que o PL está ativado
        st.info(f"🧠 **ML Engine v2:** Projeção Tática ('{placar_atual}'). Curva ajustada usando **{100-peso_player_load*100:.0f}%** do ritmo alvo e **{peso_player_load*100:.0f}%** da carga mecânica sistêmica (Player Load).")
        
        # Projeta os minutos futuros até o minuto selecionado no slider
        minutos_futuros = list(range(minuto_atual + 1, minuto_projecao_ate + 1))
        acumulado_pred = []
        valor_projetado_atual = valor_atual_acumulado 
        
        for m in minutos_futuros:
            dist_g = media_min_geral.loc[m] if m in media_min_geral.index else 0
            dist_c = media_min_cenario.loc[m] if m in media_min_cenario.index else dist_g
            
            # BLENDING: Mescla o comportamento do placar com a média histórica
            dist_mesclada = (dist_c * peso_placar) + (dist_g * (1 - peso_placar))
            dist_mesclada = max(0, dist_mesclada)
            
            dist_projetada_minuto = dist_mesclada * fator_hoje
            valor_projetado_atual += dist_projetada_minuto
            acumulado_pred.append(valor_projetado_atual)
        
        margem_erro = 0.05
        pred_superior = [val * (1 + margem_erro) for val in acumulado_pred]
        pred_inferior = [val * (1 - margem_erro) for val in acumulado_pred]

        # =====================================================================
        # KPIs - ACIMA DO GRÁFICO (AGORA COM 5 COLUNAS)
        # =====================================================================
        carga_atual = valor_atual_acumulado
        carga_projetada = acumulado_pred[-1] if len(acumulado_pred) > 0 else carga_atual
        
        # Define qual é o minuto final que está no seu slider de projeção
        minuto_final_proj = minutos_futuros[-1] if len(minutos_futuros) > 0 else minuto_atual

        # Diferença percentual específica para o minuto ATUAL
        delta_alvo_pct = (fator_alvo - 1) * 100 
        delta_pl_pct = (fator_pl - 1) * 100
        
        # --- NOVO CÁLCULO: Ritmo para o Minuto Previsto ---
        # 1. Pega a média histórica exata no minuto final da projeção
        if minuto_final_proj in curva_media_acumulada_geral.index:
            media_historica_futura = curva_media_acumulada_geral.loc[minuto_final_proj]
        else:
            media_historica_futura = media_acumulada_neste_minuto

        # 2. Calcula se a projeção vai terminar acima ou abaixo da média histórica
        fator_projetado = (carga_projetada / media_historica_futura) if media_historica_futura > 0 else 1.0
        delta_projetado_pct = (fator_projetado - 1) * 100
        # --------------------------------------------------
        
        def fmt_dist(x): return f"{x:.0f} m" if not np.isnan(x) else "N/A"
        def fmt_pct(x): return f"{x:+.1f}%" if not np.isnan(x) else "N/A"

        # Criamos 5 colunas para acomodar a nova métrica
        k0, k1, k2, k3, k4 = st.columns(5)
        
        k0.metric("Carga Atual", fmt_dist(carga_atual))
        k1.metric(f"Carga Proj. (min {minuto_final_proj})", fmt_dist(carga_projetada))
        
        # Regra de cor (verde para aumento de V4, vermelho para queda)
        cor_delta = "normal" if metrica_selecionada in ["V4 Dist", "HIA", "Total Distance"] else "inverse"
        
        # KPI 3: Ritmo Atual (Realidade agora)
        k2.metric(f"Ritmo Atual (min {minuto_atual})", fmt_pct(delta_alvo_pct), delta=fmt_pct(delta_alvo_pct), delta_color=cor_delta)
        
        # KPI 4: Ritmo Projetado (O NOVO BOTÃO DE PREVISÃO)
        k3.metric(f"Ritmo Previsto (min {minuto_final_proj})", fmt_pct(delta_projetado_pct), delta=fmt_pct(delta_projetado_pct), delta_color=cor_delta)
        
        # KPI 5: O Botão do Player Load
        k4.metric(f"Desgaste Sistêmico (PL)", f"{pl_atual_acumulado:.0f}", delta=fmt_pct(delta_pl_pct), delta_color="inverse")

        
        # =====================================================================
        # DESENHAR O GRÁFICO COM PLOTLY 
        # =====================================================================
        fig = go.Figure()
        jogos_historicos = df_historico[coluna_jogo].unique()
        colors = px.colors.qualitative.Plotly

        # Plota os jogos antigos
        for idx, jogo in enumerate(jogos_historicos):
            df_j = df_historico[df_historico[coluna_jogo] == jogo].sort_values(coluna_minuto)
            jogo_display = df_completo[df_completo['Data'] == jogo]['Data_Display'].iloc[0] if jogo in df_completo['Data'].values else str(jogo)
            fig.add_trace(go.Scatter(
                x=df_j[coluna_minuto],
                y=df_j[coluna_acumulada],
                mode='lines',
                name=jogo_display,
                opacity=0.6,
                line=dict(color=colors[idx % len(colors)], dash='dot', width=1.5),
                hovertemplate='Valor: %{y:.1f}<extra></extra>'
            ))

        # Plota o jogo atual selecionado (Linha sólida mais grossa)
        jogo_display = df_completo[df_completo['Data'] == jogo_atual_nome]['Data_Display'].iloc[0] if jogo_atual_nome in df_completo['Data'].values else str(jogo_atual_nome)
        fig.add_trace(go.Scatter(
            x=df_atual[coluna_minuto],
            y=df_atual[coluna_acumulada],
            mode='lines',
            name=f'{jogo_display} (Atual)',
            line=dict(color='#00E676', width=4), # Coloquei verde neon para dar bastante destaque
            hovertemplate='Atual: %{y:.1f}m<extra></extra>'
        ))

        # Plota a Projeção (Se houver minutos futuros)
        if len(minutos_futuros) > 0:
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=pred_superior,
                mode='lines', line=dict(width=0),
                showlegend=False, hoverinfo='skip'
            ))
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=pred_inferior,
                mode='lines', line=dict(width=0),
                fill='tonexty', fillcolor='rgba(255, 215, 0, 0.15)', # Amarelo transparente
                name='Margem de Variação', hoverinfo='skip'
            ))
            fig.add_trace(go.Scatter(
                x=minutos_futuros, y=acumulado_pred,
                mode='lines', name='Projeção com ML',
                line=dict(color='#FFD700', width=3, dash='dash'), 
                hovertemplate='Projeção: %{y:.1f}m<extra></extra>'
            ))
            fig.add_vline(x=minuto_atual, line_dash="dash", line_color="gray")
            fig.add_annotation(x=minuto_atual, y=1, text="Agora", showarrow=False, yref="paper", xanchor="left", yanchor="top")

        # Ajuste dos eixos
        x_min = 0
        x_max = minuto_projecao_ate + 2  # Margem visual no gráfico

        # dtick=1 força o gráfico a mostrar TODOS os números (1, 2, 3...)
        fig.update_xaxes(
            tickmode='linear', 
            dtick=1, # <-- Alterado de 5 para 1
            range=[x_min, x_max], 
            tickfont=dict(size=10), 
            tickangle=0 # <-- Alterado para 0 para os números ficarem retos e mais fáceis de ler
        )

        fig.update_layout(
            title=titulo_grafico,
            xaxis_title='Minutos de Jogo',
            yaxis_title=metrica_selecionada,
            template='plotly_dark',
            
            # Ajuste agressivo na legenda para jogá-y para baixo e impedir sobreposição
            legend=dict(
                bgcolor='rgba(0,0,0,0)', # Fundo transparente para não tapar linhas
                orientation="h", 
                yanchor="top",  # <-- Alterado de bottom para top
                y=-0.35,        # <-- Valor negativo joga a legenda para baixo do gráfico
                xanchor="center", 
                x=0.5
            ),
            
            # Aumentamos a altura total para a legenda "respirar"
            height=650, # <-- Aumentado de 600 para 700
            
            hovermode='x unified',
            
            # b=200 é a margem inferior em pixels. Dá espaço de sobra para a legenda
            margin=dict(l=20, r=20, t=50, b=200) # <-- Aumentado de 100 para 200
        )

        st.plotly_chart(fig, use_container_width=True)
            
    else:
        st.warning("Não há histórico de jogos antigos suficientes para criar uma linha base para este atleta.")
else:
    st.info("Selecione um atleta com dados válidos.")