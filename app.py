import streamlit as st
import pandas as pd
import plotly.express as px
import io
import unicodedata

# ==============================================================================
# CONFIGURAÇÃO E AUTENTICAÇÃO (BANCO DE LICENÇAS)
# ==============================================================================
st.set_page_config(
    page_title="Gestor Financeiro & Precificação E-Commerce",
    page_icon="📊",
    layout="wide"
)

# Banco de Licenças Ativas (Chave -> Dados do Cliente)
BANCO_DE_LICENCAS = {
    "LICENSA-2026": {"cliente": "Demonstração", "ativo": True},
    "CLI-8849-X9": {"cliente": "Loja Exemplo 1", "ativo": True},
    "CLI-9921-A2": {"cliente": "Loja Exemplo 2", "ativo": True},
    "Python.2026": {"cliente": "Master Admin", "ativo": True},
}

st.sidebar.title("🔐 Acesso Restrito")
senha_cliente = st.sidebar.text_input("Digite sua Chave de Licença:", type="password").strip()

if not senha_cliente:
    st.title("🔒 Sistema Bloqueado")
    st.info("👋 Seja bem-vindo! Insira sua chave de licença na barra lateral para liberar as ferramentas.")
    st.stop()

if senha_cliente not in BANCO_DE_LICENCAS or not BANCO_DE_LICENCAS[senha_cliente]["ativo"]:
    st.title("🔒 Licença Inválida ou Expirada")
    st.error("A chave informada não existe ou foi desativada.")
    st.info("💡 Adquira seu acesso ou solicite suporte para reativar sua licença.")
    st.stop()

# Saudação personalizada após validação
st.sidebar.success(f"Bem-vindo, **{BANCO_DE_LICENCAS[senha_cliente]['cliente']}**!")

# --- NAVEGAÇÃO ---
st.sidebar.title("📌 Menu Principal")
pagina = st.sidebar.radio(
    "Navegar para:",
    ["📊 Fluxo de Caixa & DRE Universal", "🧮 Calculadora de Precificação"]
)

# ==============================================================================
# MOTOR INTELIGENTE DE PROCESSAMENTO DE PLANILHAS (MOTOR HEURÍSTICO)
# ==============================================================================

def remover_acentos(texto):
    """Remove acentos, caracteres especiais e espaços extras de uma string."""
    if not isinstance(texto, str):
        return str(texto)
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


def limpar_e_converter_valor(serie):
    """Converte valores monetários/texto em float sem multiplicar casas decimais."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.fillna(0.0).astype(float)
    
    # Remove R$, espaços e caracteres invisíveis
    s = serie.astype(str).str.replace('R$', '', regex=False).str.strip()
    
    # Identifica formato brasileiro com vírgula
    com_virgula = s.str.contains(',', regex=False, na=False)
    s_br = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    
    # Substitui apenas se houver vírgula, preservando floats normais em string
    s_final = s.where(~com_virgula, s_br)

    return pd.to_numeric(s_final, errors='coerce').fillna(0.0)


def auto_detectar_estrutura(df):
    """
    Analisa os nomes das colunas de QUALQUER planilha e tenta mapear
    automaticamente os conceitos de Data, Descrição, Categoria, Tipo e Valor.
    """
    cols_norm = {col: remover_acentos(col) for col in df.columns}
    
    kw_data = ['data', 'dt', 'date', 'mes', 'periodo', 'vencimento']
    kw_desc = ['descricao', 'historico', 'produto', 'detalhe', 'transacao', 'nome']
    kw_cat  = ['categoria', 'cat', 'classificacao', 'grupo', 'setor']
    kw_tipo = ['tipo', 'movimento', 'operacao', 'natureza', 'sinal', 'dc']
    kw_val  = ['valor', 'total', 'monto', 'preco', 'bruto', 'liquido', 'saldo', 'lancamento']
    
    col_data = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in kw_data)), None)
    col_desc = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in kw_desc)), None)
    col_cat  = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in kw_cat)), None)
    col_tipo = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in kw_tipo)), None)
    col_val  = next((orig for orig, norm in cols_norm.items() if any(k in norm for k in kw_val)), None)
    
    if not col_val:
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                col_val = col
                break
                
    return col_data, col_desc, col_cat, col_tipo, col_val


def normalizar_df_financeiro(df, col_data, col_desc, col_cat, col_tipo, col_val):
    """
    Normaliza qualquer Dataframe bruto para uma estrutura padrão.
    Aplica remoção de acentos para classificar Entrada e Saída sem falhas.
    """
    df_proc = pd.DataFrame()
    
    # 1. Trata Valor
    df_proc['Valor_Bruto'] = limpar_e_converter_valor(df[col_val])
    
    # 2. Trata Tipo (Entrada / Saída)
    if col_tipo and col_tipo != "-- Não utilizar --":
        tipo_limpo = df[col_tipo].astype(str).apply(remover_acentos)
        
        mapeamento_tipos = {
            'entrada': 'Entrada', 'entradas': 'Entrada', 'receita': 'Entrada', 'receitas': 'Entrada',
            'credito': 'Entrada', 'c': 'Entrada', 'venda': 'Entrada', 'vendas': 'Entrada',
            'saida': 'Saída', 'saidas': 'Saída', 'despesa': 'Saída', 'despesas': 'Saída',
            'debito': 'Saída', 'd': 'Saída', 'custo': 'Saída', 'custos': 'Saída', 'pagamento': 'Saída'
        }
        
        df_proc['Tipo'] = tipo_limpo.map(mapeamento_tipos).fillna('Outros')
        
        # Fallback: Se o valor for negativo na planilha, ajusta como Saída
        df_proc.loc[df_proc['Valor_Bruto'] < 0, 'Tipo'] = 'Saída'
        df_proc['Valor'] = df_proc['Valor_Bruto'].abs()
    else:
        # Se não há coluna de Tipo na planilha, deduce pelo sinal (- Saída / + Entrada)
        df_proc['Tipo'] = df_proc['Valor_Bruto'].apply(lambda x: 'Saída' if x < 0 else 'Entrada')
        df_proc['Valor'] = df_proc['Valor_Bruto'].abs()
        
    # 3. Trata Categoria
    if col_cat and col_cat != "-- Não utilizar --":
        df_proc['Categoria'] = df[col_cat].fillna("Geral / Outros").astype(str)
    else:
        df_proc['Categoria'] = "Geral"
        
    # 4. Trata Descrição
    if col_desc and col_desc != "-- Não utilizar --":
        df_proc['Descrição'] = df[col_desc].fillna("-").astype(str)
    else:
        df_proc['Descrição'] = "Sem Descrição"
        
    # 5. Trata Data
    if col_data and col_data != "-- Não utilizar --":
        df_proc['Data'] = pd.to_datetime(df[col_data], errors='coerce')
    else:
        df_proc['Data'] = pd.NaT

    return df_proc[df_proc['Tipo'].isin(['Entrada', 'Saída'])]


def carregar_dataframe_seguro(uploaded_file):
    """
    Leitor universal resiliente para Excel/CSV que trata abas,
    cabeçalhos deslocados e limpa espaços vazios.
    """
    try:
        nome_arquivo = uploaded_file.name.lower()
        
        if nome_arquivo.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, sep=';')
                if len(df.columns) <= 1:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, sep=',')
            except Exception:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='latin1', sep=None, engine='python')
        else:
            excel_file = pd.ExcelFile(uploaded_file)
            nomes_abas = excel_file.sheet_names
            
            index_padrao = 0
            for i, aba in enumerate(nomes_abas):
                if any(k in aba.lower() for k in ['lançamento', 'lancamento', 'vendas', 'extrato', 'base', 'financeiro']):
                    index_padrao = i
                    break
                    
            aba_selecionada = st.sidebar.selectbox("Selecione a aba:", nomes_abas, index=index_padrao)
            
            df = None
            for skip in range(0, 15):
                df_temp = pd.read_excel(excel_file, sheet_name=aba_selecionada, skiprows=skip).dropna(how='all', axis=1)
                cols_unidas = " ".join([str(c).lower() for c in df_temp.columns])
                if any(k in cols_unidas for k in ['valor', 'total', 'tipo', 'entrada', 'saida', 'saldo', 'data']):
                    df = df_temp
                    break
            
            if df is None:
                df = pd.read_excel(excel_file, sheet_name=aba_selecionada)

        # Limpa cabeçalhos (remove espaços extras no início/fim)
        df.columns = [str(col).strip() for col in df.columns]
        df = df.dropna(how='all', axis=1).dropna(how='all', axis=0)
        return df

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {str(e)}")
        return None


@st.cache_data
def gerar_template_excel():
    output = io.BytesIO()
    df_modelo = pd.DataFrame({
        'Data': ['01/05/2026', '01/05/2026', '02/05/2026', '02/05/2026', '03/05/2026', '03/05/2026', '04/05/2026', '05/05/2026'],
        'Descrição': [
            'Venda Mercado Livre #1023', 'Fornecedor de Embalagens', 
            'Venda Shopee #8841', 'Anúncios Meta Ads', 
            'Aluguel do Galpão', 'Venda Site Próprio #101', 
            'Taxa de Gateway PagSeguro', 'Venda Mercado Livre #1024'
        ],
        'Categoria': ['Vendas', 'Insumos', 'Vendas', 'Marketing', 'Estrutura', 'Vendas', 'Taxas', 'Vendas'],
        'Tipo': ['Entrada', 'Saída', 'Entrada', 'Saída', 'Saída', 'Entrada', 'Saída', 'Entrada'],
        'Valor (R$)': [250.00, 45.00, 180.50, 60.00, 1200.00, 320.00, 15.50, 410.00]
    })
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_modelo.to_excel(writer, sheet_name='Extrato_Exemplo', index=False)
        
    output.seek(0)
    return output.getvalue()


# ==============================================================================
# PÁGINA 1: FLUXO DE CAIXA UNIVERSAL
# ==============================================================================
if pagina == "📊 Fluxo de Caixa & DRE Universal":
    st.title("📊 Gestor Financeiro Universal")
    st.caption("Insira qualquer extrato ou planilha e o sistema identificará entradas, saídas e o saldo atual.")

    st.sidebar.header("📁 Importação de Dados")
    
    st.sidebar.download_button(
        label="📥 Baixar Modelo Gabarito (.xlsx)",
        data=gerar_template_excel(),
        file_name="Modelo_Fluxo_de_Caixa.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.sidebar.markdown("---")

    arquivo_carregado = st.sidebar.file_uploader(
        "Envie sua planilha (.xlsx ou .csv)", 
        type=["xlsx", "csv"]
    )

    if arquivo_carregado is not None:
        df_bruto = carregar_dataframe_seguro(arquivo_carregado)

        if df_bruto is not None and not df_bruto.empty:
            # 2. Detecção Automática das Colunas
            col_dt_auto, col_desc_auto, col_cat_auto, col_tipo_auto, col_val_auto = auto_detectar_estrutura(df_bruto)

            st.sidebar.markdown("---")
            st.sidebar.subheader("⚙️ Mapeamento Inteligente")
            st.sidebar.caption("Confirme ou corrija como o sistema leu as colunas:")

            todas_cols = ["-- Não utilizar --"] + list(df_bruto.columns)

            def get_index(col_auto):
                return todas_cols.index(col_auto) if col_auto in todas_cols else 0

            sel_data = st.sidebar.selectbox("Coluna de Data:", todas_cols, index=get_index(col_dt_auto))
            sel_desc = st.sidebar.selectbox("Coluna de Descrição:", todas_cols, index=get_index(col_desc_auto))
            sel_cat  = st.sidebar.selectbox("Coluna de Categoria:", todas_cols, index=get_index(col_cat_auto))
            sel_tipo = st.sidebar.selectbox("Coluna de Tipo (Entrada/Saída):", todas_cols, index=get_index(col_tipo_auto))
            sel_val  = st.sidebar.selectbox("Coluna de Valor (R$):", todas_cols, index=get_index(col_val_auto))

            # 3. Processamento e Normalização dos Dados
            if sel_val != "-- Não utilizar --":
                df_tratado = normalizar_df_financeiro(
                    df_bruto, sel_data, sel_desc, sel_cat, sel_tipo, sel_val
                )

                if df_tratado.empty:
                    st.warning("⚠️ Não foram encontrados lançamentos válidos com os parâmetros atuais.")
                    st.stop()

                # --- MÉTRICAS PRINCIPAIS (ENTRADA, SAÍDA E SALDO) ---
                total_entradas = df_tratado[df_tratado['Tipo'] == 'Entrada']['Valor'].sum()
                total_saidas = df_tratado[df_tratado['Tipo'] == 'Saída']['Valor'].sum()
                saldo_atual = total_entradas - total_saidas

                col1, col2, col3 = st.columns(3)
                col1.metric("🟢 ENTRADAS (RECEITAS)", f"R$ {total_entradas:,.2f}")
                col2.metric("🔴 SAÍDAS (DESPESAS)", f"R$ {total_saidas:,.2f}")
                col3.metric("🔵 SALDO ATUAL OPERACIONAL", f"R$ {saldo_atual:,.2f}")

                st.markdown("---")

                # --- ANÁLISE GRÁFICA ---
                cG1, cG2 = st.columns(2)

                with cG1:
                    st.subheader("Entradas vs Saídas")
                    df_resumo = pd.DataFrame({
                        'Operação': ['Entradas', 'Saídas'],
                        'Total (R$)': [total_entradas, total_saidas]
                    })
                    fig_bar = px.bar(
                        df_resumo, x='Operação', y='Total (R$)', color='Operação',
                        text_auto='.2f',
                        color_discrete_map={'Entradas': '#2E7D32', 'Saídas': '#C62828'}
                    )
                    fig_bar.update_layout(showlegend=False)
                    st.plotly_chart(fig_bar, use_container_width=True)

                with cG2:
                    st.subheader("Distribuição por Categoria (Saídas)")
                    df_saidas = df_tratado[df_tratado['Tipo'] == 'Saída']
                    if not df_saidas.empty:
                        df_cat_summary = df_saidas.groupby('Categoria')['Valor'].sum().reset_index()
                        fig_pie = px.pie(
                            df_cat_summary, names='Categoria', values='Valor', hole=0.4,
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.info("Nenhuma saída identificada nesta planilha.")

                # Tabela Consolidada
                with st.expander("🔍 Visualizar Planilha Normalizada"):
                    st.dataframe(df_tratado, use_container_width=True)

            else:
                st.warning("⚠️ Selecione ao menos a coluna de **Valor (R$)** no menu lateral.")
        else:
            st.warning("⚠️ O arquivo enviado não contém linhas válidas.")

    else:
        st.info("👈 Faça o upload de qualquer planilha de fluxo de caixa ou extrato no menu lateral!")

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
        
        comissao_pct = st.number_input("Comissão do Marketplace (%)", min_value=0.0, max_value=100.0, value=preset_padrao["comissao"], step=0.5)
        taxa_fixa_canal = st.number_input("Taxa Fixa por Item Vendido [R$]", min_value=0.0, value=preset_padrao["taxa_fixa"], step=0.50)
        imposto_pct = st.number_input("Imposto sobre Nota Fiscal / Simples Nacional (%)", min_value=0.0, max_value=100.0, value=6.0, step=0.5)

        st.subheader("3. Meta de Lucro")
        tipo_meta = st.radio("Como prefere definir sua meta?", ["Margem Líquida Desejada (%)", "Lucro Líquido Fixo por Unidade (R$)"])

        if tipo_meta == "Margem Líquida Desejada (%)":
            margem_alvo_pct = st.slider("Margem Líquida Alvo (% sobre Preço de Venda)", 5.0, 60.0, 20.0, step=1.0)
        else:
            lucro_fixo_alvo = st.number_input("Lucro Líquido Desejado [R$]", min_value=1.0, value=25.0, step=1.0)

    # CÁLCULOS MATEMÁTICOS DA PRECIFICAÇÃO
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
                st.warning(f"⚠️ **Atenção à Taxa Fixa:** Consome **{(taxa_fixa_canal/preco_sugerido*100):.1f}%** do valor final do produto!")
            
            if lucro_liquido_real < 5.00:
                st.warning(f"⚠️ **Lucro Baixo:** Apenas R$ {lucro_liquido_real:.2f} de margem líquida unitária.")
            else:
                st.success(f"✅ **Margem Protegida:** Excelente retorno líquido.")

            st.markdown("---")
            st.subheader("📊 DRE Unitário")

            df_dre_unit = pd.DataFrame({
                "Componente": ["Custo (COGS)", "Embalagem/Frete", "Comissão ML/Shopee", "Taxa Fixa", "Impostos (NF)", "LUCRO LÍQUIDO"],
                "Valor (R$)": [custo_unitario, custo_embalagem + custo_frete, v_comissao, taxa_fixa_canal, v_imposto, lucro_liquido_real]
            })

            fig_pizza_prec = px.pie(df_dre_unit, names="Componente", values="Valor (R$)", hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
            fig_pizza_prec.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pizza_prec, use_container_width=True)
        else:
            st.error("A soma das taxas e margens ultrapassa 100%.")
