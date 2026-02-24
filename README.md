# ADF Online - Sports Performance Analytics Dashboard

## 📋 Visão Geral

O ADF Online é uma plataforma avançada de análise de performance esportiva desenvolvida para monitoramento e projeção de métricas fisiológicas de atletas de futebol utilizando dados GPS. O sistema combina machine learning com visualizações interativas em tempo real para fornecer insights valiosos sobre carga física, fadiga e performance dos jogadores.

## 🚀 Funcionalidades Principais

### **Módulos de Análise**
- **🏠 Home**: Carregamento centralizado de dados e métricas globais
- **⚡ Live Tracker**: Projeção em tempo real com atualização automática a cada 60 segundos
- **📊 Relatório HIA**: Análise detalhada de High-Intensity Accelerations
- **🔋 Radar Fadiga**: Visualização multidimensional de indicadores de cansaço
- **📅 Temporada**: Análise histórica e tendências da temporada
- **⚔️ Comparação Atletas**: Benchmarking comparativo entre jogadores

### **Recursos Técnicos**
- **Machine Learning**: Modelos XGBoost pré-treinados para projeção de métricas
- **Análise SHAP**: Interpretação de importância de features
- **Cache Inteligente**: Otimização de performance com carregamento único
- **Auto-refresh**: Atualização automática de dados em tempo real
- **Visualizações Interativas**: Gráficos dinâmicos com Plotly

## 📁 Estrutura do Projeto

```
ADF_Online/
├── Home.py                    # Página principal e carregamento de dados
├── ml_engine.py              # Motor de machine learning
├── predictive.py             # Sistema preditivo avançado
├── requirements.txt          # Dependências Python
├── README.md                # Documentação do projeto
├── config.py                # Configurações centralizadas
├── models/                  # Modelos de ML pré-treinados
│   ├── modelo_Dist_Total.pkl
│   ├── modelo_HIA_Total.pkl
│   ├── modelo_V4_Dist.pkl
│   └── ...
├── pages/                   # Módulos de análise
│   ├── 1__Live_Tracker.py
│   ├── 2_📊_Relatorio_HIA.py
│   ├── 3_🔋_Radar_Fadiga.py
│   ├── 4_📅_Temporada.py
│   └── 5_⚔️_Comparacao_Atletas.py
└── data/                    # Dados de entrada
    └── ADF OnLine 2024.xlsb
```

## 📊 Métricas e Dados

### **Fonte de Dados**
- **Arquivo Excel**: `ADF OnLine 2024.xlsb`
- **Frequência**: Dados GPS por intervalo de tempo
- **Métricas Principais**:
  - Total Distance
  - V4/V5 Distance (velocidades)
  - V4/V5 Efficiency
  - High-Intensity Accelerations (HIA)
  - Player Load
  - Metabolic Power

### **Modelos de Machine Learning**
- **Algoritmo**: XGBoost com otimização de hiperparâmetros
- **Features**: Distância acumulada, dias de descanso, potência metabólica
- **Target**: Projeção de métricas de performance
- **Validação**: Cross-validation e métricas MAE/RMSE

## 🔧 Configuração

### **Parâmetros Configuráveis**
- Intervalo de atualização (default: 60 segundos)
- Limite de projeção de minutos
- Thresholds para alertas de fadiga
- Métricas personalizadas

## 📈 Performance e Otimização

### **Cache Strategy**
- `@st.cache_resource` para dados globais
- Session state para compartilhamento entre páginas

### **Monitoramento**
- Sistema de logging estruturado
- Métricas de performance
- Alertas de erro automaticos

## 🚀 Deploy

### **Streamlit Cloud**
1. Conecte repositório ao Streamlit Cloud
2. Configure secrets e variáveis de ambiente
3. Deploy automático via GitHub Actions

**Erro: "Base de dados principal está a ser atualizada"**
- Verifique se o arquivo Excel não está aberto em outro programa
- Confirme permissões de escrita na pasta

**Erro: "Modelo não encontrado"**
- Verifique se os arquivos `.pkl` existem na pasta
- Confirme se os modelos foram treinados corretamente

**Performance lenta**
- Limpe cache: `streamlit cache clear`
- Verifique tamanho do arquivo Excel
- Considere particionar dados por temporada
