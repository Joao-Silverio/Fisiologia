import streamlit as st
import pandas as pd
import numpy as np 
import warnings
import plotly.express as px
import plotly.graph_objects as go

import Source.Dados.config as config
from Source.Dados.data_loader import obter_hora_modificacao, load_global_data
import Source.UI.visual as visual
import Source.UI.components as ui

ui.renderizar_cabecalho("Relatório Individual", "Análise de performance e comparação histórica")

# Carregamento inicial fora do fragmento — garante que df existe
hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
df_novo, _ = load_global_data(hora_atual)
if not df_novo.empty:
    st.session_state['df_global'] = df_novo

if 'df_global' not in st.session_state:
    st.warning("⚠️ Carregue os dados na Home primeiro.")
    st.stop()

# =====================================================================
# FUNÇÃO DE GERAÇÃO DE PDF
# =====================================================================
def gerar_pdf_atleta(atleta, jogo, periodo, df_comp, df_evolucao, metrica_grafico):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    cor_primaria = colors.HexColor('#3B82F6')
    cor_alerta   = colors.HexColor('#EF4444')
    cor_ok       = colors.HexColor('#22C55E')

    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Title'], textColor=cor_primaria, fontSize=20)
    estilo_sub    = ParagraphStyle('Sub', parent=styles['Normal'], textColor=colors.HexColor('#94A3B8'), fontSize=10)
    estilo_secao  = ParagraphStyle('Secao', parent=styles['Heading2'], textColor=cor_primaria, fontSize=13)

    story = []
    story.append(Paragraph(f"Relatorio Individual - {atleta}", estilo_titulo))
    story.append(Paragraph(f"Jogo: {jogo} | {periodo}", estilo_sub))
    story.append(HRFlowable(width="100%", thickness=1, color=cor_primaria))
    story.append(Spacer(1, 0.4*cm))

    if df_comp is not None and not df_comp.empty:
        story.append(Paragraph("Comparativo vs Media Historica", estilo_secao))
        story.append(Spacer(1, 0.2*cm))
        dados_tabela = [["Metrica", "Jogo Atual", "Media Historica", "Variacao %"]]
        for _, row in df_comp.iterrows():
            diff = row['Diferença %']
            sinal = f"+{diff:.1f}%" if diff >= 0 else f"{diff:.1f}%"
            dados_tabela.append([row['Métrica'], f"{row['Jogo Atual']:.1f}", f"{row['Média (Outros Jogos)']:.1f}", sinal])

        tabela = Table(dados_tabela, colWidths=[5*cm, 3*cm, 4*cm, 3*cm])
        estilo_tab = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), cor_primaria),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#1E293B'), colors.HexColor('#0F172A')]),
            ('TEXTCOLOR',  (0,1), (-1,-1), colors.white),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#334155')),
        ])
        for i, row in enumerate(df_comp.itertuples(), start=1):
            cor_var = cor_ok if row._4 >= 0 else cor_alerta
            estilo_tab.add('TEXTCOLOR', (3, i), (3, i), cor_var)
            estilo_tab.add('FONTNAME',  (3, i), (3, i), 'Helvetica-Bold')
        tabela.setStyle(estilo_tab)
        story.append(tabela)
        story.append(Spacer(1, 0.5*cm))

    if df_evolucao is not None and not df_evolucao.empty:
        story.append(Paragraph(f"Evolucao: {metrica_grafico} (Ultimos 5 Jogos)", estilo_secao))
        story.append(Spacer(1, 0.2*cm))
        df_ult5 = df_evolucao[['Data_Display', metrica_grafico, 'Minutagem']].tail(5)
        media_val = df_evolucao[metrica_grafico].mean()
        dados_evo = [["Jogo", metrica_grafico, "Minutagem", "vs Media"]]
        for _, row in df_ult5.iterrows():
            diff_pct = ((row[metrica_grafico] / media_val) - 1) * 100 if media_val > 0 else 0
            sinal = f"+{diff_pct:.1f}%" if diff_pct >= 0 else f"{diff_pct:.1f}%"
            dados_evo.append([row['Data_Display'], f"{row[metrica_grafico]:.1f}", f"{row['Minutagem']:.0f} min", sinal])

        tabela_evo = Table(dados_evo, colWidths=[5*cm, 3*cm, 3*cm, 4*cm])
        tabela_evo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#334155')),
            ('TEXTCOLOR',  (0,0), (-1,0), colors.white),
            ('FONTNAME',   (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('ALIGN',      (1,0), (-1,-1), 'CENTER'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#1E293B'), colors.HexColor('#0F172A')]),
            ('TEXTCOLOR',  (0,1), (-1,-1), colors.white),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.HexColor('#334155')),
        ]))
        story.append(tabela_evo)

    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#334155')))
    story.append(Paragraph(f"Gerado por ADF Online | {pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}", estilo_sub))
    doc.build(story)
    buffer.seek(0)
    return buffer

# =====================================================================
# FRAGMENTO PRINCIPAL — tudo dentro para o auto-refresh funcionar
# =====================================================================
@st.fragment(run_every="5s")
def pagina_individual():
    hora_atual = obter_hora_modificacao(config.ARQUIVO_ORIGINAL)
    df_novo, _ = load_global_data(hora_atual)
    if not df_novo.empty:
        st.session_state['df_global'] = df_novo

    df_completo = st.session_state['df_global'].copy()

    # FILTROS
    st.markdown("### 🔍 Seleção de Análise")
    with st.container():
        col_j, col_a, col_p = st.columns([2, 2, 1])
        lista_jogos = df_completo.drop_duplicates(subset=['Data']).sort_values(by='Data', ascending=False)['Data_Display'].tolist()
        with col_j:
            jogo_destaque_display = st.selectbox("🎯 Jogo em Destaque:", lista_jogos)
        jogo_destaque_data = df_completo[df_completo['Data_Display'] == jogo_destaque_display]['Data'].iloc[0]
        df_jogo_base = df_completo[df_completo['Data'] == jogo_destaque_data]
        lista_atletas = sorted(df_jogo_base['Name'].dropna().unique())
        with col_a:
            atleta_selecionado = st.selectbox("🏃 Atleta:", lista_atletas)
        with col_p:
            periodo_selecionado = st.selectbox("⏱️ Período:", ["Jogo Completo", "1º Tempo", "2º Tempo"])

    # PROCESSAMENTO
    df_atleta_total = df_completo[df_completo['Name'] == atleta_selecionado].copy()
    df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('1|2', regex=True, na=False)]
    if periodo_selecionado == "1º Tempo":
        df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('1', na=False)]
    elif periodo_selecionado == "2º Tempo":
        df_atleta_total = df_atleta_total[df_atleta_total['Período'].astype(str).str.contains('2', na=False)]

    df_jogo_atleta     = df_atleta_total[df_atleta_total['Data'] == jogo_destaque_data]
    df_historico_atleta = df_atleta_total[df_atleta_total['Data'] != jogo_destaque_data]

    # KPIs
    st.markdown(f"#### 👤 Painel Individual: {atleta_selecionado} | Jogo {jogo_destaque_display} ({periodo_selecionado})")
    total_jogos = df_atleta_total['Data'].nunique()
    total_minutos = df_jogo_atleta.groupby('Período')['Min_Num'].max().sum() if 'Min_Num' in df_jogo_atleta.columns and not df_jogo_atleta.empty else 0
    media_minutos = df_atleta_total.groupby(['Data', 'Período'])['Min_Num'].max().groupby('Data').sum().mean() if 'Min_Num' in df_atleta_total.columns and total_jogos > 0 else 0

    col_kpi_1, col_kpi_2, col_kpi_3, col_pdf = st.columns([2, 2, 2, 1])
    with col_kpi_1:
        ui.renderizar_card_kpi("Jogos no Histórico", f"{total_jogos}", cor_borda=visual.CORES["primaria"])
    with col_kpi_2:
        ui.renderizar_card_kpi(f"Minutagem ({periodo_selecionado})", f"{total_minutos:.0f} min", cor_borda=visual.CORES["secundaria"])
    with col_kpi_3:
        ui.renderizar_card_kpi(f"Média de Minutos", f"{media_minutos:.0f} min", cor_borda=visual.CORES["aviso_carga"])

    # ABAS
    st.markdown("### 🧭 Estrutura de Análise Jogo a Jogo")
    aba_timeline, aba_comparativo, aba_clusters, aba_insights, aba_perfil = st.tabs([
        "📈 Linha do tempo", "⚔️ Comparativo", "🏃 Clusters Intensidade", "💡 Insights", "📊 Perfil Estatístico"
    ])

    # Variáveis compartilhadas entre abas e PDF
    df_comp = None
    df_evolucao = None
    metrica_grafico = "Total Distance"

    # ABA 1: TIMELINE
    with aba_timeline:
        st.markdown("#### Evolução de performance por partida")
        cols_analise = ['Total Distance', 'Player Load', 'HIA', 'V4 Dist', 'V5 Dist']
        metrica_grafico = st.pills("Visualizar Evolução de:", cols_analise, default="Total Distance")

        df_metricas_timeline = df_atleta_total.groupby(['Data', 'Data_Display'])[cols_analise].sum().reset_index()
        if 'Min_Num' in df_atleta_total.columns:
            df_minutos_timeline = df_atleta_total.groupby(['Data', 'Data_Display', 'Período'])['Min_Num'].max().groupby(['Data', 'Data_Display']).sum().reset_index(name='Minutagem')
        else:
            df_minutos_timeline = pd.DataFrame({'Data': df_metricas_timeline['Data'], 'Data_Display': df_metricas_timeline['Data_Display'], 'Minutagem': 0})

        df_evolucao = pd.merge(df_metricas_timeline, df_minutos_timeline, on=['Data', 'Data_Display']).sort_values('Data')

        if not df_evolucao.empty:
            col_a, col_b = st.columns([2, 1])
            with col_a:
                media_metrica = df_evolucao[metrica_grafico].mean()
                cores_marcadores = [
                    visual.CORES["ok_prontidao"] if val >= media_metrica else visual.CORES["alerta_fadiga"]
                    for val in df_evolucao[metrica_grafico]
                ]
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_evolucao['Data_Display'], y=df_evolucao[metrica_grafico],
                    mode='lines+markers+text', name=metrica_grafico,
                    text=df_evolucao[metrica_grafico].round(1), textposition='top center',
                    line=dict(color=visual.CORES["secundaria"], width=2),
                    marker=dict(size=10, color=cores_marcadores, line=dict(width=1, color=visual.CORES["fundo_card"])),
                    customdata=df_evolucao[['Minutagem']],
                    hovertemplate="<b>Jogo:</b> %{x}<br><b>Valor:</b> %{y:.1f}<br><b>Minutagem:</b> %{customdata[0]:.0f} min<extra></extra>"
                ))
                fig.add_hline(y=media_metrica, line_dash="dash", line_color=visual.CORES["texto_claro"],
                              annotation_text=f"Média: {media_metrica:.1f}", annotation_position="top left",
                              annotation_font_color=visual.CORES["texto_claro"])
                fig.update_layout(title=f"Evolução: {metrica_grafico} ({periodo_selecionado})", **visual.PLOTLY_TEMPLATE['layout'])
                st.plotly_chart(fig, width='stretch')

            with col_b:
                st.markdown("**Resumo (Últimos 5 jogos)**")
                df_resumo = df_evolucao[['Data_Display', metrica_grafico, 'Minutagem']].tail(5).sort_values('Data_Display', ascending=False)
                for _, row in df_resumo.iterrows():
                    val = row[metrica_grafico]
                    media = df_evolucao[metrica_grafico].mean()

                    # 1. Calcula historico_ate PRIMEIRO
                    idx = df_evolucao[df_evolucao['Data_Display'] == row['Data_Display']].index[0]
                    historico_ate = df_evolucao.loc[:idx, metrica_grafico].tail(5).tolist()

                    # 2. Agora usa historico_ate para cor_spark
                    if len(historico_ate) >= 2:
                        tendencia = historico_ate[-1] - historico_ate[0]
                        cor_spark = visual.CORES["ok_prontidao"] if tendencia >= 0 else visual.CORES["alerta_fadiga"]
                    else:
                        cor_spark = visual.CORES["texto_claro"]

                    # 3. Cor do valor vs média
                    cor_valor = visual.CORES["ok_prontidao"] if val >= media else visual.CORES["alerta_fadiga"]
                    delta_pct = ((val / media) - 1) * 100 if media > 0 else 0
                    seta = "▲" if delta_pct >= 0 else "▼"

                    # 4. Sparkline
                    if len(historico_ate) < 2:
                        c_jogo, c_val, c_spark_col = st.columns([2, 1, 1])
                        c_jogo.caption(row['Data_Display'])
                        c_val.markdown(f"<span style='color:{cor_valor}; font-weight:800;'>{seta} {val:.0f}</span>", unsafe_allow_html=True)
                        c_spark_col.caption("—")
                    else:
                        fig_spark = go.Figure(go.Scatter(
                            y=historico_ate, mode='lines',
                            line=dict(color=cor_spark, width=2),
                            fill='tozeroy',
                            fillcolor=f"rgba({int(cor_spark[1:3],16)},{int(cor_spark[3:5],16)},{int(cor_spark[5:7],16)},0.13)"
                        ))
                        fig_spark.update_layout(
                            height=40, margin=dict(t=0, b=0, l=0, r=0),
                            xaxis=dict(visible=False), yaxis=dict(visible=False),
                            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                            showlegend=False
                        )
                        c_jogo, c_val, c_spark_col = st.columns([2, 1, 1])
                        c_jogo.caption(row['Data_Display'])
                        c_val.markdown(f"<span style='color:{cor_valor}; font-weight:800;'>{seta} {val:.0f}</span>", unsafe_allow_html=True)
                        c_spark_col.plotly_chart(fig_spark, width='stretch', key=f"spark_{row['Data_Display']}_{metrica_grafico}")

        else:
            st.info("Não há dados suficientes para gerar a linha do tempo neste recorte.")

    # ABA 2: COMPARATIVO
    with aba_comparativo:
        st.markdown("#### Diferenças do jogo selecionado para a sua média histórica")
        metricas_alvo = ["Total Distance", "Player Load", "HIA", "V5 To8 Eff", "V4 Dist", "V5 Dist"]
        if not df_jogo_atleta.empty and not df_historico_atleta.empty:
            jogo_atual_stats = df_jogo_atleta[metricas_alvo].sum()
            df_agrupado_hist = df_historico_atleta.groupby('Data')[metricas_alvo].sum()
            media_historica  = df_agrupado_hist.mean().fillna(0).infer_objects(copy=False)
            df_comp = pd.DataFrame({
                "Métrica": metricas_alvo,
                "Jogo Atual": jogo_atual_stats.values.round(1),
                "Média (Outros Jogos)": media_historica.values.round(1)
            })
            df_comp['Diferença %'] = ((df_comp['Jogo Atual'] - df_comp['Média (Outros Jogos)']) / df_comp['Média (Outros Jogos)'] * 100).fillna(0).infer_objects(copy=False)

            def formatar_cor(val):
                cor = visual.CORES["ok_prontidao"] if val >= 0 else visual.CORES["alerta_fadiga"]
                return f'<span style="color:{cor}; font-weight:bold;">{val:+.1f}%</span>'
            df_comp_display = df_comp.copy()
            df_comp_display['Diferença %'] = df_comp_display['Diferença %'].apply(formatar_cor)
            st.write(df_comp_display.to_html(escape=False, index=False), unsafe_allow_html=True)
        else:
            st.warning("Não há dados suficientes para gerar o comparativo.")

    # ABA 3: CLUSTERS
    with aba_clusters:
        st.markdown(f"#### Perfil de Intensidade: V4 Dist vs Distância Total ({periodo_selecionado})")
        df_intensidade = df_atleta_total.groupby(['Data', 'Data_Display'])[['Total Distance', 'V4 Dist']].sum().reset_index()
        df_intensidade['Intensidade (%)'] = (df_intensidade['V4 Dist'] / df_intensidade['Total Distance'].replace(0, 1)) * 100

        if not df_jogo_atleta.empty and len(df_intensidade) > 0:
            jogo_atual_row = df_intensidade[df_intensidade['Data'] == jogo_destaque_data]
            if not jogo_atual_row.empty:
                intensidade_atual = jogo_atual_row['Intensidade (%)'].values[0]
                dist_total_atual  = jogo_atual_row['Total Distance'].values[0]
                v4_atual          = jogo_atual_row['V4 Dist'].values[0]
            else:
                intensidade_atual = dist_total_atual = v4_atual = 0

            p33 = df_intensidade['Intensidade (%)'].quantile(0.33)
            p66 = df_intensidade['Intensidade (%)'].quantile(0.66)

            if intensidade_atual >= p66:
                nome_cluster = "🔴 Alta Intensidade"
                desc_cluster = "O atleta correu em alta velocidade numa proporção muito maior que o seu normal."
            elif intensidade_atual >= p33:
                nome_cluster = "🟡 Intensidade Moderada"
                desc_cluster = "A relação entre a distância percorrida e o esforço intenso está no padrão habitual."
            else:
                nome_cluster = "🟢 Baixa Intensidade"
                desc_cluster = "Jogo cadenciado. O volume de V4 foi baixo em relação à distância total percorrida."

            c1, c2, c3 = st.columns([1, 1, 1.5])
            with c1:
                st.markdown("**Jogo Analisado**")
                st.metric("Índice de Intensidade", f"{intensidade_atual:.1f}%")
                st.caption(f"**V4 Dist:** {v4_atual:.1f} m")
                st.caption(f"**Dist Total:** {dist_total_atual:.1f} m")
            with c2:
                st.markdown("**Classificação do Jogo**")
                st.info(f"**{nome_cluster}**\n\n{desc_cluster}")
                st.write(f"Média Histórica do Atleta: **{df_intensidade['Intensidade (%)'].mean():.1f}%**")
            with c3:
                st.markdown("**🏆 Top 3 Jogos Mais Intensos (Histórico)**")
                top_3 = df_intensidade.sort_values(by='Intensidade (%)', ascending=False).head(3)
                top_3_display = top_3[['Data_Display', 'Intensidade (%)', 'V4 Dist']].rename(columns={'Data_Display': 'Jogo'})
                top_3_display['Intensidade (%)'] = top_3_display['Intensidade (%)'].round(1).astype(str) + '%'
                top_3_display['V4 Dist'] = top_3_display['V4 Dist'].round(1)
                st.dataframe(top_3_display, width='stretch', hide_index=True)
        else:
            st.info("Dados insuficientes para calcular clusters de intensidade.")

    # ABA 4: INSIGHTS
    with aba_insights:
        st.markdown("#### 💡 Insights Automatizados")
        if df_comp is not None and not df_jogo_atleta.empty and not df_historico_atleta.empty:
            hia_diff  = df_comp[df_comp['Métrica'] == 'HIA']['Diferença %'].values[0]
            dist_diff = df_comp[df_comp['Métrica'] == 'Total Distance']['Diferença %'].values[0]
            if hia_diff > 10:
                st.success(f"📈 **Alta Intensidade Elevada:** HIA {hia_diff:.1f}% acima da média. Monitorar fadiga muscular/recuperação.")
            elif hia_diff < -10:
                st.warning(f"📉 **Queda de Intensidade:** {abs(hia_diff):.1f}% menos ações intensas que o padrão normal.")
            else:
                st.info(f"⚖️ **Intensidade Padrão:** HIA equilibrado com a média histórica no {periodo_selecionado.lower()}.")
            st.markdown(f"- Distância Total variou **{dist_diff:+.1f}%** em relação à média do atleta.")
        else:
            st.write("Sem base histórica suficiente para gerar insights comparativos.")

    # ABA 5: PERFIL ESTATÍSTICO
    with aba_perfil:
        col_perc, col_corr = st.columns(2)
        
        # ----- PERCENTIL POR POSIÇÃO -----
        with col_perc:
            st.markdown("#### 🏅 Percentil vs Posição")
            from Source.Dados.positions import get_position, POSITION_CONFIG
            
            posicao_atl = get_position(atleta_selecionado)
            metricas_perc = ['Total Distance', 'Player Load', 'HIA', 'V4 Dist', 'V5 Dist']
            
            if posicao_atl:
                # Pega todos os atletas da mesma posição no histórico
                atletas_mesma_pos = [n for n in df_completo['Name'].unique() if get_position(n) == posicao_atl]
                df_pos_grupo = df_completo[df_completo['Name'].isin(atletas_mesma_pos)]
                df_pos_agg   = df_pos_grupo.groupby(['Name','Data'])[[m for m in metricas_perc if m in df_completo.columns]].sum().reset_index()
                
                vals_atleta_p, percentis, labels_p = [], [], []
                for m in metricas_perc:
                    if m not in df_pos_agg.columns: continue
                    val_atual = df_jogo_atleta[m].sum() if m in df_jogo_atleta.columns else 0
                    todos_vals = df_pos_agg[m].dropna().values
                    if len(todos_vals) > 0:
                        pct = (todos_vals < val_atual).mean() * 100
                        percentis.append(pct)
                        vals_atleta_p.append(val_atual)
                        labels_p.append(m.replace('Total Distance','Distância').replace('Player Load','P.Load'))
                
                if percentis:
                    cores_perc = ['#22C55E' if p >= 75 else '#F59E0B' if p >= 50 else '#EF4444' for p in percentis]
                    fig_perc = go.Figure(go.Bar(
                        x=percentis, y=labels_p,
                        orientation='h',
                        marker_color=cores_perc,
                        text=[f"P{p:.0f}  ({v:.0f})" for p, v in zip(percentis, vals_atleta_p)],
                        textposition='inside',
                        hovertemplate="<b>%{y}</b><br>Percentil: %{x:.0f}<extra></extra>"
                    ))
                    cfg_pos = POSITION_CONFIG[posicao_atl]
                    fig_perc.add_vline(x=50, line_dash="dash", line_color="rgba(255,255,255,0.3)",
                                    annotation_text="Mediana", annotation_position="top")
                    fig_perc.update_layout(
                        height=320, xaxis=dict(range=[0,100], title="Percentil (%)"),
                        title=f"{cfg_pos['emoji']} vs {cfg_pos['label']}s",
                        template='plotly_dark', paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=40, b=10)
                    )
                    st.plotly_chart(fig_perc, width='stretch')
            else:
                st.info("Posição não mapeada — adicione em positions.py")
        
        # ----- CORRELAÇÃO CARGA vs PERFORMANCE -----
        with col_corr:
            st.markdown("#### 🔗 Carga vs Performance")
            
            df_corr = df_atleta_total.groupby(['Data','Data_Display']).agg(
                Player_Load=('Player Load', 'sum'),
                HIA=('HIA', 'sum'),
                Distancia=('Total Distance', 'sum')
            ).reset_index()
            
            if len(df_corr) >= 3:
                # Destaca jogo atual
                df_corr['is_atual'] = df_corr['Data'] == jogo_destaque_data
                
                fig_corr = px.scatter(
                    df_corr, x='Player_Load', y='HIA',
                    size='Distancia', color='is_atual',
                    color_discrete_map={True: '#EF4444', False: '#60A5FA'},
                    text='Data_Display',
                    hover_data=['Distancia'],
                    labels={'Player_Load': 'Player Load', 'HIA': 'HIA Total',
                            'is_atual': 'Jogo Atual'}
                )
                fig_corr.update_traces(textposition='top center', textfont_size=8)
                
                # Linha de tendência
                if len(df_corr) >= 4:
                    z = np.polyfit(df_corr['Player_Load'], df_corr['HIA'], 1)
                    p = np.poly1d(z)
                    x_line = np.linspace(df_corr['Player_Load'].min(), df_corr['Player_Load'].max(), 50)
                    fig_corr.add_trace(go.Scatter(
                        x=x_line, y=p(x_line), mode='lines',
                        name='Tendência', line=dict(color='rgba(255,255,255,0.3)', dash='dot', width=1)
                    ))
                
                fig_corr.update_layout(
                    height=320, template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    margin=dict(t=10, b=10), showlegend=False
                )
                st.plotly_chart(fig_corr, width='stretch')
            else:
                st.info("Mínimo de 3 jogos para o gráfico de correlação.")
        
        # ----- DISTRIBUIÇÃO (VIOLIN) -----
        st.markdown("#### 🎻 Distribuição Histórica por Métrica")
        
        metricas_violin = ['Total Distance', 'Player Load', 'HIA', 'V4 Dist']
        metricas_violin = [m for m in metricas_violin if m in df_atleta_total.columns]
        
        df_violin = df_atleta_total.groupby('Data')[metricas_violin].sum().reset_index()
        
        if len(df_violin) >= 4:
            metrica_viol = st.radio("Métrica:", metricas_violin, horizontal=True, key="rad_violin")
            val_atual_viol = df_jogo_atleta[metrica_viol].sum() if metrica_viol in df_jogo_atleta.columns else 0
            
            fig_viol = go.Figure()
            fig_viol.add_trace(go.Violin(
                y=df_violin[metrica_viol],
                box_visible=True, meanline_visible=True,
                fillcolor='rgba(96,165,250,0.3)',
                line_color='#60A5FA', name='Histórico',
                points='all', pointpos=0,
                marker=dict(color='#60A5FA', size=6, opacity=0.6)
            ))
            
            # Marca o jogo atual
            fig_viol.add_hline(
                y=val_atual_viol, line_dash="solid", line_color="#EF4444", line_width=2,
                annotation_text=f"  Jogo atual: {val_atual_viol:.0f}",
                annotation_font=dict(color="#EF4444", size=12),
                annotation_position="right"
            )
            
            fig_viol.update_layout(
                height=320, template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                yaxis_title=metrica_viol, showlegend=False,
                margin=dict(t=10, b=10, r=120)
            )
            st.plotly_chart(fig_viol, width='stretch')
        else:
            st.info("Mínimo de 4 jogos para o gráfico de distribuição.")

    # =====================================================================
    # 🟢 CORREÇÃO: Totalmente alinhado à esquerda (fora do 'with aba_perfil')
    # e sem o st.button encapsulando o st.download_button
    # =====================================================================
    st.markdown("---")
    _, col_pdf = st.columns([5, 1])
    with col_pdf:
        # Gera o PDF diretamente para colocar no botão
        pdf_buffer = gerar_pdf_atleta(
            atleta_selecionado, jogo_destaque_display, periodo_selecionado,
            df_comp, df_evolucao, metrica_grafico
        )
        
        st.download_button(
            label="📄 Exportar PDF",
            data=pdf_buffer,
            file_name=f"relatorio_{atleta_selecionado.replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            key="btn_download_pdf"
        )

pagina_individual()