import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import plotly.express as px
import warnings

warnings.filterwarnings('ignore')

# 1. CARREGAR OS DADOS
print("Carregando banco de dados...")
df = pd.read_excel('ADF OnLine 2024.xlsb', engine='calamine')
df.columns = df.columns.str.strip()

# Criar a coluna HIA se não existir
df['HIA'] = df.get('V4 To8 Eff', 0) + df.get('V5 To8 Eff', 0) + df.get('V6 To8 Eff', 0) + \
            df.get('Acc3 Eff', 0) + df.get('Dec3 Eff', 0)

# Garantir que V5 Dist exista (ou usar V5 To8 Eff como proxy)
col_v5 = 'V5 Dist' if 'V5 Dist' in df.columns else 'V5 To8 Eff'

# 2. PREPARAÇÃO DOS DADOS (AGRUPAR POR JOGO E ATLETA)
# Como queremos prever o final do jogo/tempo, agrupamos tudo o que aconteceu
df_agrupado = df.groupby(['Data', 'Name', 'Período', 'Resultado']).agg({
    'Total Distance': 'sum',
    'V4 Dist': 'sum',
    col_v5: 'sum',
    'HIA': 'sum',
    'Player Load': 'sum',
    'Interval': 'max' # Minutos jogados naquele período
}).reset_index()

df_agrupado = df_agrupado.sort_values(by=['Name', 'Data'])

# 3. ENGENHARIA DE RECURSOS (CRIANDO AS VARIÁVEIS DE CONTEXTO)
print("Calculando médias históricas e contextuais...")

# A. Média Histórica Geral do Atleta (Tudo o que ele jogou até hoje)
df_agrupado['Media_Dist_Geral'] = df_agrupado.groupby('Name')['Total Distance'].transform(lambda x: x.expanding().mean().shift(1))
df_agrupado['Media_V4_Geral'] = df_agrupado.groupby('Name')['V4 Dist'].transform(lambda x: x.expanding().mean().shift(1))
df_agrupado['Media_HIA_Geral'] = df_agrupado.groupby('Name')['HIA'].transform(lambda x: x.expanding().mean().shift(1))

# B. Média Histórica do Atleta por RESULTADO (V, E, D)
# Isso responde à sua pergunta: "Ele corre igual quando está ganhando/perdendo?"
df_agrupado['Media_Dist_Contexto'] = df_agrupado.groupby(['Name', 'Resultado'])['Total Distance'].transform(lambda x: x.expanding().mean().shift(1))
df_agrupado['Media_HIA_Contexto'] = df_agrupado.groupby(['Name', 'Resultado'])['HIA'].transform(lambda x: x.expanding().mean().shift(1))

# Preencher os primeiros jogos (onde não há histórico) com a média do time ou 0
df_agrupado = df_agrupado.fillna(0)
# Remover jogos onde o atleta não jogou (0 minutos)
df_agrupado = df_agrupado[df_agrupado['Interval'] > 5] 

# 4. TREINAMENTO DO MODELO E ANÁLISE DE IMPORTÂNCIA
# Vamos testar o que prevê melhor a Distância Total
recursos_para_analisar = [
    'Interval',           # Minutos em campo
    'Media_Dist_Geral',   # Histórico geral do atleta
    'Media_Dist_Contexto',# Histórico do atleta só em vitórias/derrotas/empates iguais a de hoje
    'Player Load'         # Carga interna acumulada
]

X = df_agrupado[recursos_para_analisar]
y_dist = df_agrupado['Total Distance'] # Nosso alvo (o que queremos prever)

# Dividir os dados: treinar com jogos antigos, testar com jogos recentes
X_train, X_test, y_train, y_test = train_test_split(X, y_dist, test_size=0.2, shuffle=False)

print("Treinando Inteligência Artificial...")
modelo_rf = RandomForestRegressor(n_estimators=100, random_state=42)
modelo_rf.fit(X_train, y_train)

# Avaliar o Erro (Quantos metros de erro o modelo tem em média?)
previsoes = modelo_rf.predict(X_test)
erro_medio = mean_absolute_error(y_test, previsoes)
print(f"✅ Erro Médio de Previsão (Distância Total): {erro_medio:.0f} metros")

# 5. DESCOBRINDO O QUE MAIS IMPORTA (FEATURE IMPORTANCE)
importancias = modelo_rf.feature_importances_
df_importancia = pd.DataFrame({
    'Variável': recursos_para_analisar,
    'Importância (%)': importancias * 100
}).sort_values(by='Importância (%)', ascending=True)

# Gerar o gráfico
fig = px.bar(
    df_importancia, 
    x='Importância (%)', 
    y='Variável', 
    orientation='h',
    title='O que mais influencia a Distância Corrida de um Atleta?',
    text_auto='.1f',
    color='Importância (%)',
    color_continuous_scale='Blues'
)
fig.update_layout(template='plotly_white')
fig.show()