import streamlit as st
import pandas as pd
import plotly.express as px
import io

st.sidebar.title("🔐 Acesso Restrito")
senha_cliente = st.sidebar.text_input("Digite sua Chave de Licença:", type="password")

# Chave válida para o cliente (pode ser consultada em banco de dados ou lista)
CHAVE_VALIDA = "CLIENTE_PREMIUM_2026"

if senha_cliente != CHAVE_VALIDA:
    st.title("🔒 Sistema Bloqueado")
    st.warning("Insira uma chave de licença válida na barra lateral para liberar o acesso ao dashboard.")
    st.info("💡 **Ainda não possui acesso?** Entre em contato para adquirir sua licença.")
    st.stop() # Interrompe a execução do restante do código


st.set_page_config(
    page_title="Gestor Financeiro & Precificação E-Commerce",
    page_icon="📊",
    layout="wide"
)

# --- NAVEGAÇÃO / MENU DE NAVEGAÇÃO ---
st.sidebar.title("📌 Menu Principal")
pagina = st.sidebar.radio(
    "Navegar para:",
    ["📊 Fluxo de Caixa & DRE", "🧮 Calculadora de Precificação"]
)

# ==============================================================================
# FUNÇÕES DE SUPORTE & UX
# ==============================================================================

def limpar_e_converter_valor(serie):
    """Converte valores monetários/string em float de forma robusta."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.fillna(0)
    
    serie_limpa = serie.astype(str).str.replace('R$', '', regex=False).str.strip()
    serie_limpa = serie_limpa.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    return pd.to_numeric(serie_limpa, errors='coerce').fillna(0)


def auto_detectar_colunas(df_cols):
    """Mapeia automaticamente colunas prováveis por palavras-chave."""
    cols_norm = {col: str(col).strip().lower() for col in df_cols}
    
    col_data = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in ['data', 'dt', 'date'])), None)
    col_desc = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in ['descrição', 'descricao', 'historico', 'produto', 'detalhe'])), None)
    col_cat  = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in ['categoria', 'cat', 'classificacao'])), None)
    col_tipo = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in ['tipo', 'movimento', 'operacao', 'natureza'])), None)
    col_val  = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in ['valor', 'total', 'monto', 'preço', 'preco', 'bruto', 'liquido'])), None)
    
    return col_data, col_desc, col_cat, col_tipo, col_val


@st.cache_data
def gerar_template_excel():
    """Gera um arquivo Excel de exemplo para o cliente baixar como gabarito."""
    output = io.BytesIO()
    df_modelo = pd.DataFrame({
        'Data': ['2026-05-01', '2026-05-02', '2026-05-03', '2026-05-04', '2026-05-05'],
        'Descrição': ['Venda Mercado Livre #1023', 'Fornecedor de Embalagens', 'Venda Shopee #8841', 'Anúncios Meta Ads', 'Aluguel do Galpão'],
        'Categoria': ['Vendas', 'Insumos', 'Vendas', 'Marketing', 'Estrutura'],
        'Tipo': ['Entrada', 'Saída', 'Entrada', 'Saída', 'Saída'],
        'Valor (R$)': [250.00, 45.00, 180.50, 60.00, 1200.00]
    })
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_modelo.to_excel(writer, sheet_name='Lançamentos', index=False)
        
    output.seek(0)
    return output.getvalue()


# ==============================================================================
# PÁGINA 1: FLUXO DE CAIXA & DRE
# ==============================================================================
if pagina == "📊 Fluxo de Caixa & DRE":
    st.title("📊 Financeiro & Fluxo de Caixa")
    st.caption("Visão consolidada de entradas, saídas e saldo operacional do e-commerce")

    st.sidebar.header("📁 Importação de Dados")
    
    # Download do Template/Gabarito em 1 Clique
    st.sidebar.download_button(
        label="📥 Baixar Modelo de Planilha (.xlsx)",
        data=gerar_template_excel(),
        file_name="Modelo_Fluxo_de_Caixa_Ecommerce.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Baixe esta planilha de exemplo caso prefira preencher seus dados manualmente."
    )
    st.sidebar.markdown("---")

    arquivo_carregado = st.sidebar.file_uploader(
        "Envie sua planilha ou extrato (.xlsx ou .csv)", 
        type=["xlsx", "csv"]
    )

    if arquivo_carregado is not None:
        try:
            if arquivo_carregado.name.endswith('.csv'):
                df_bruto = pd.read_csv(arquivo_carregado)
            else:
                excel_file = pd.ExcelFile(arquivo_carregado)
                nomes_abas = excel_file.sheet_names

                index_padrao = 0
                for i, aba in enumerate(nomes_abas):
                    if any(k in aba.lower() for k in ['lançamento', 'lancamento', 'vendas', 'extrato', 'base']):
                        index_padrao = i
                        break

                aba_selecionada = st.sidebar.selectbox("Selecione a aba:", nomes_abas, index=index_padrao)

                df_bruto = None
                for skip in range(0, 15):
                    df_temp = pd.read_excel(excel_file, sheet_name=aba_selecionada, skiprows=skip).dropna(how='all', axis=1)
                    cols_unidas = " ".join([str(c).lower() for c in df_temp.columns])
                    if 'tipo' in cols_unidas or 'valor' in cols_unidas or 'data' in cols_unidas:
                        df_bruto = df_temp
                        break
                
                if df_bruto is None:
                    df_bruto = pd.read_excel(excel_file, sheet_name=aba_selecionada)

            df_bruto = df_bruto.dropna(how='all', axis=1).dropna(how='all', axis=0)

            if df_bruto.empty:
                st.warning("⚠️ O arquivo enviado parece estar vazio. Verifique a planilha e tente novamente.")
                st.stop()

            col_dt_auto, col_desc_auto, col_cat_auto, col_tipo_auto, col_val_auto = auto_detectar_colunas(df_bruto.columns)

            st.sidebar.markdown("---")
            st.sidebar.subheader("⚙️ Mapeamento de Colunas")

            todas_cols = ["-- Não utilizar --"] + list(df_bruto.columns)

            def get_index(col_auto):
                return todas_cols.index(col_auto) if col_auto in todas_cols else 0

            sel_data = st.sidebar.selectbox("Coluna de Data:", todas_cols, index=get_index(col_dt_auto))
            sel_desc = st.sidebar.selectbox("Coluna de Descrição:", todas_cols, index=get_index(col_desc_auto))
            sel_cat  = st.sidebar.selectbox("Coluna de Categoria:", todas_cols, index=get_index(col_cat_auto))
            sel_tipo = st.sidebar.selectbox("Coluna de Tipo (Entrada/Saída):", todas_cols, index=get_index(col_tipo_auto))
            sel_val  = st.sidebar.selectbox("Coluna de Valor (R$):", todas_cols, index=get_index(col_val_auto))

            if sel_val != "-- Não utilizar --":
                df = pd.DataFrame()
                df['Valor'] = limpar_e_converter_valor(df_bruto[sel_val])

                if sel_tipo != "-- Não utilizar --":
                    df['Tipo'] = df_bruto[sel_tipo].astype(str).str.strip().str.capitalize()
                    df['Tipo'] = df['Tipo'].replace({'Entradas': 'Entrada', 'Saídas': 'Saída', 'Receita': 'Entrada', 'Despesa': 'Saída'})
                else:
                    df['Tipo'] = df['Valor'].apply(lambda x: 'Saída' if x < 0 else 'Entrada')
                    df['Valor'] = df['Valor'].abs()

                if sel_cat != "-- Não utilizar --":
                    df['Categoria'] = df_bruto[sel_cat].fillna("Sem Categoria").astype(str)
                else:
                    df['Categoria'] = "Geral"

                if sel_desc != "-- Não utilizar --":
                    df['Descrição'] = df_bruto[sel_desc].fillna("-").astype(str)

                if sel_data != "-- Não utilizar --":
                    df['Data'] = pd.to_datetime(df_bruto[sel_data], errors='coerce')

                df = df[df['Tipo'].isin(['Entrada', 'Saída'])]

                if df.empty:
                    st.warning("⚠️ Não encontramos lançamentos válidos de Entrada ou Saída com os filtros e mapeamentos selecionados.")
                    st.stop()

                total_entradas = df[df['Tipo'] == 'Entrada']['Valor'].sum()
                total_saidas = df[df['Tipo'] == 'Saída']['Valor'].sum()
                saldo_atual = total_entradas - total_saidas

                # --- EXIBIÇÃO DE KPIS PRINCIPAIS ---
                col1, col2, col3 = st.columns(3)
                col1.metric("TOTAL ENTRADAS (RECEITA)", f"R$ {total_entradas:,.2f}")
                col2.metric("TOTAL SAÍDAS (DESPESAS)", f"R$ {total_saidas:,.2f}")
                col3.metric("SALDO ATUAL OPERACIONAL", f"R$ {saldo_atual:,.2f}")

                # --- DIAGNÓSTICO INTELIGENTE ---
                st.markdown("---")
                st.subheader("💡 Diagnóstico Executivo Automático")

                margem_lucro_operacional = (saldo_atual / total_entradas * 100) if total_entradas > 0 else 0
                c_diag1, c_diag2 = st.columns(2)

                with c_diag1:
                    if saldo_atual < 0:
                        st.error(f"🚨 **Déficit Operacional Detectado:** Suas despesas superam as receitas em **R$ {abs(saldo_atual):,.2f}**. Atenção imediata à redução de custos!")
                    elif margem_lucro_operacional < 10:
                        st.warning(f"⚠️ **Margem Operacional Estreita ({margem_lucro_operacional:.1f}%):** O saldo está positivo em **R$ {saldo_atual:,.2f}**, mas a margem é baixa para o setor de e-commerce.")
                    else:
                        st.success(f"✅ **Operação Saudável:** Margem operacional em **{margem_lucro_operacional:.1f}%** com saldo livre de **R$ {saldo_atual:,.2f}**.")

                with c_diag2:
                    df_saidas = df[df['Tipo'] == 'Saída']
                    if not df_saidas.empty:
                        categoria_maior = df_saidas.groupby('Categoria')['Valor'].sum().idxmax()
                        valor_maior = df_saidas.groupby('Categoria')['Valor'].sum().max()
                        pct_maior = (valor_maior / total_saidas * 100) if total_saidas > 0 else 0

                        st.info(f"📌 **Maior Impacto no Caixa:** A categoria **'{categoria_maior}'** representa **{pct_maior:.1f}%** de todas as suas despesas (R$ {valor_maior:,.2f}).")
                    else:
                        st.info("📌 Nenhuma saída registrada para análise de maior impacto.")

                st.markdown("---")

                col_graf1, col_graf2 = st.columns(2)

                with col_graf1:
                    st.subheader("Comparativo: Entradas vs Saídas")
                    df_fluxo = pd.DataFrame({
                        'Tipo': ['Entradas', 'Saídas'],
                        'Valor': [total_entradas, total_saidas]
                    })
                    fig_barras = px.bar(
                        df_fluxo, 
                        x='Tipo', 
                        y='Valor', 
                        color='Tipo',
                        text_auto='.2f',
                        color_discrete_map={'Entradas': '#2E7D32', 'Saídas': '#C62828'}
                    )
                    fig_barras.update_layout(showlegend=False, yaxis_title="Valor (R$)", xaxis_title="")
                    st.plotly_chart(fig_barras, use_container_width=True)

                with col_graf2:
                    st.subheader("Distribuição por Categoria (Saídas)")
                    if not df_saidas.empty:
                        df_cat_grp = df_saidas.groupby('Categoria')['Valor'].sum().reset_index()
                        fig_rosca = px.pie(
                            df_cat_grp, 
                            names='Categoria', 
                            values='Valor', 
                            hole=0.5,
                            color_discrete_sequence=px.colors.qualitative.Safe
                        )
                        fig_rosca.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_rosca, use_container_width=True)
                    else:
                        st.info("Não há saídas registradas para exibir o gráfico por categoria.")

                # Tabela de Dados Mapeados e Exportação
                with st.expander("🔍 Visualizar e Exportar Tabela Processada"):
                    st.dataframe(df, use_container_width=True)
                    
                    # Botão para baixar os dados limpos em CSV
                    csv_data = df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                    st.download_button(
                        label="📥 Baixar Dados Tratados (.csv)",
                        data=csv_data,
                        file_name="Dados_Tratados_Fluxo_de_Caixa.csv",
                        mime="text/csv"
                    )

            else:
                st.warning("⚠️ Selecione a coluna correspondente ao **Valor (R$)** no menu lateral.")

        except Exception as e:
            st.error("💡 **Não foi possível ler este arquivo automaticamente.**")
            st.info("Por favor, verifique se a planilha não possui senhas ou proteções e tente selecionar as colunas manualmente no menu lateral.")

    else:
        st.info("👈 Faça o upload de uma planilha no menu lateral para visualizar o dashboard, ou baixe nosso modelo de exemplo para testar!")


# ==============================================================================
# PÁGINA 2: CALCULADORA DE PRECIFICAÇÃO E-COMMERCE
# ==============================================================================
elif pagina == "🧮 Calculadora de Precificação":
    st.title("🧮 Calculadora de Precificação Inteligente")
    st.caption("Descubra o preço ideal de venda e a margem de lucro real descontando impostos, taxas e custos de envio.")

    PRESETS_CANAL = {
        "Mercado Livre (Clássico - 14%)": {"comissao": 14.0, "taxa_fixa": 6.50},
        "Mercado Livre (Premium - 19%)": {"comissao": 19.0, "taxa_fixa": 6.50},
        "Shopee (Padrão + Frete Grátis - 20%)": {"comissao": 20.0, "taxa_fixa": 4.00},
        "Shein (16%)": {"comissao": 16.0, "taxa_fixa": 0.00},
        "Amazon Brasil (15%)": {"comissao": 15.0, "taxa_fixa": 2.00},
        "Loja Própria / Nuvemshop (Gateway 3.5%)": {"comissao": 3.5, "taxa_fixa": 0.50},
        "Personalizado": {"comissao": 0.0, "taxa_fixa": 0.00}
    }

    col_esq, col_dir = st.columns([1, 1], gap="large")

    with col_esq:
        st.subheader("1. Custos do Produto & Operação")
        
        nome_prod = st.text_input("Nome do Produto", value="Camiseta Algodão Premium")
        custo_unitario = st.number_input("Custo de Aquisição/Produção (COGS) [R$]", min_value=0.0, value=35.0, step=1.0)
        custo_embalagem = st.number_input("Embalagem, Etiqueta e Sacaria [R$]", min_value=0.0, value=2.50, step=0.5)
        custo_frete = st.number_input("Frete do Vendedor / Subsídio [R$]", min_value=0.0, value=0.0, step=1.0)

        st.subheader("2. Canal de Venda & Impostos")
        canal_selecionado = st.selectbox("Selecione o Canal de Venda / Marketplace:", list(PRESETS_CANAL.keys()))

        preset_padrao = PRESETS_CANAL[canal_selecionado]
        
        comissao_pct = st.number_input(
            "Comissão do Marketplace (%)", 
            min_value=0.0, max_value=100.0, 
            value=preset_padrao["comissao"], 
            step=0.5
        )
        taxa_fixa_canal = st.number_input(
            "Taxa Fixa por Item Vendido [R$]", 
            min_value=0.0, 
            value=preset_padrao["taxa_fixa"], 
            step=0.50
        )
        imposto_pct = st.number_input(
            "Imposto sobre Nota Fiscal / Simples Nacional (%)", 
            min_value=0.0, max_value=100.0, 
            value=6.0, 
            step=0.5
        )

        st.subheader("3. Meta de Lucro")
        tipo_meta = st.radio("Como prefere definir sua meta?", ["Margem Líquida Desejada (%)", "Lucro Líquido Fixo por Unidade (R$)"])

        if tipo_meta == "Margem Líquida Desejada (%)":
            margem_alvo_pct = st.slider("Margem Líquida Alvo (% sobre Preço de Venda)", 5.0, 60.0, 20.0, step=1.0)
        else:
            lucro_fixo_alvo = st.number_input("Lucro Líquido Desejado [R$]", min_value=1.0, value=25.0, step=1.0)

    # --- CÁLCULOS MATEMÁTICOS DA PRECIFICAÇÃO ---
    custo_direto_total = custo_unitario + custo_embalagem + custo_frete + taxa_fixa_canal
    taxas_percentuais_totais = comissao_pct + imposto_pct

    if tipo_meta == "Margem Líquida Desejada (%)":
        denominador = 1 - ((taxas_percentuais_totais + margem_alvo_pct) / 100)
        preco_sugerido = (custo_direto_total / denominador) if denominador > 0 else 0.0
    else:
        denominador = 1 - (taxas_percentuais_totais / 100)
        preco_sugerido = ((custo_direto_total + lucro_fixo_alvo) / denominador) if denominador > 0 else 0.0

    v_comissao = preco_sugerido * (comissao_pct / 100)
    v_imposto = preco_sugerido * (imposto_pct / 100)
    lucro_liquido_real = preco_sugerido - v_comissao - v_imposto - custo_direto_total
    margem_real_efetiva = (lucro_liquido_real / preco_sugerido * 100) if preco_sugerido > 0 else 0.0
    markup_multiplicador = (preco_sugerido / custo_unitario) if custo_unitario > 0 else 0.0

    with col_dir:
        st.subheader("💡 Diagnóstico do Preço Sugerido")

        if preco_sugerido > 0:
            st.metric(
                label="PREÇO DE VENDA RECOMENDADO", 
                value=f"R$ {preco_sugerido:,.2f}",
                delta=f"Markup: {markup_multiplicador:.2f}x o custo"
            )

            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Lucro Líquido por Venda", f"R$ {lucro_liquido_real:,.2f}")
            col_m2.metric("Margem Real Efetiva", f"{margem_real_efetiva:.1f}%")

            if taxa_fixa_canal > 0 and (taxa_fixa_canal / preco_sugerido * 100) > 15:
                st.warning(f"⚠️ **Atenção à Taxa Fixa:** A taxa fixa de R$ {taxa_fixa_canal:.2f} consome **{(taxa_fixa_canal/preco_sugerido*100):.1f}%** do valor final deste produto! Tente vender em kits/combos para diluir esse custo.")
            
            if lucro_liquido_real < 5.00:
                st.warning(f"⚠️ **Lucro em Reais Baixo:** Seu lucro é de apenas **R$ {lucro_liquido_real:.2f}** por unidade. Qualquer imprevisto (como trocas/devoluções) pode zerar a margem.")
            else:
                st.success(f"✅ **Margem Protegida:** Produto com excelente retorno líquido unitário.")

            st.markdown("---")
            st.subheader("📊 DRE Unitarismo (Para onde vai cada R$):")

            df_dre_unit = pd.DataFrame({
                "Componente": [
                    "Custo do Produto (COGS)", 
                    "Embalagem & Envio", 
                    "Comissão Marketplace", 
                    "Taxa Fixa do Canal", 
                    "Impostos (NF)", 
                    "LUCRO LÍQUIDO FINAL"
                ],
                "Valor (R$)": [
                    custo_unitario, 
                    custo_embalagem + custo_frete, 
                    v_comissao, 
                    taxa_fixa_canal, 
                    v_imposto, 
                    lucro_liquido_real
                ]
            })

            fig_pizza_prec = px.pie(
                df_dre_unit, 
                names="Componente", 
                values="Valor (R$)", 
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_pizza_prec.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pizza_prec, use_container_width=True)

            st.markdown("---")
            st.subheader("⚡ Testar um Preço do seu Concorrente:")
            preco_concorrente = st.number_input("Se você vendesse este produto por [R$]:", min_value=1.0, value=round(preco_sugerido, 2))
            
            v_comiss_conc = preco_concorrente * (comissao_pct / 100)
            v_imp_conc = preco_concorrente * (imposto_pct / 100)
            lucro_conc = preco_concorrente - v_comiss_conc - v_imp_conc - custo_direto_total
            margem_conc = (lucro_conc / preco_concorrente * 100) if preco_concorrente > 0 else 0.0

            if lucro_conc < 0:
                st.error(f"🚨 Perigo! Vendendo por R$ {preco_concorrente:.2f}, você terá um PREJUÍZO de R$ {abs(lucro_conc):.2f} por item!")
            else:
                st.success(f"✅ Vendendo por R$ {preco_concorrente:.2f}, seu lucro será de R$ {lucro_conc:.2f} (Margem: {margem_conc:.1f}%).")

        else:
            st.error("Soma das taxas e margem desejada ultrapassa 100%! Reduza as margens ou taxas para calcular o preço.")
