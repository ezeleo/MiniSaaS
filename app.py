import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io
import unicodedata
from auth_service import (
    autenticar_usuario, 
    criar_novo_usuario, 
    listar_todos_lojistas, 
    alternar_status_pagamento,
    gerar_link_pagamento_mp,
    verificar_e_atualizar_pagamento_mp
)

# ==============================================================================
# CONFIGURAÇÃO E AUTENTICAÇÃO (SUPABASE SAAS)
# ==============================================================================
st.set_page_config(
    page_title="Gestor Financeiro & Inteligência E-Commerce",
    page_icon="📊",
    layout="wide"
)

if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = False
if "dados_usuario" not in st.session_state:
    st.session_state.dados_usuario = None

# --- TELA DE AUTENTICAÇÃO (LOGIN / CADASTRO) ---
if not st.session_state.usuario_logado:
    st.title("🔒 Acesso ao Sistema SaaS")
    st.caption("Acesse sua conta ou cadastre sua loja para utilizar a plataforma.")
    
    aba_login, aba_cadastro = st.tabs(["Fazer Login", "Criar Nova Conta"])
    
    with aba_login:
        st.subheader("Login de Lojista")
        email_login = st.text_input("E-mail", key="login_email")
        senha_login = st.text_input("Senha", type="password", key="login_senha")
        
        if st.button("Entrar", type="primary"):
            if not email_login or not senha_login:
                st.warning("Preencha o e-mail e a senha.")
            else:
                sucesso, resultado = autenticar_usuario(email_login, senha_login)
                if sucesso:
                    st.session_state.usuario_logado = True
                    st.session_state.dados_usuario = resultado
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error(resultado)

    with aba_cadastro:
        st.subheader("Cadastrar Novo Lojista")
        nome_loja = st.text_input("Nome da sua Loja")
        email_cadastro = st.text_input("E-mail", key="cad_email")
        senha_cadastro = st.text_input("Senha (mínimo 6 caracteres)", type="password", key="cad_senha")
        
        if st.button("Cadastrar Loja"):
            if not nome_loja or not email_cadastro or not senha_cadastro:
                st.warning("Preencha todos os campos para continuar.")
            else:
                sucesso, mensagem = criar_novo_usuario(email_cadastro, senha_cadastro, nome_loja)
                if sucesso:
                    st.success(mensagem)
                else:
                    st.error(mensagem)

    st.stop()

# --- BARRA LATERAL (INFORMAÇÕES DO LOJISTA LOGADO) ---
st.sidebar.title("🏢 Painel do Lojista")
dados_user = st.session_state.dados_usuario or {}

st.sidebar.success(f"**{dados_user.get('nome_loja', 'Minha Loja')}**")
st.sidebar.caption(f"👤 {dados_user.get('email', '')}")

perfil_atual = str(dados_user.get("perfil", "user")).strip().lower()
eh_admin = (perfil_atual == "admin")
est_pago = True if eh_admin else dados_user.get("pago", False)

st.sidebar.caption(f"⭐ Plano: {'Administrador' if eh_admin else dados_user.get('plano', 'Gratuito')}")

if st.sidebar.button("🚪 Sair / Logout"):
    st.session_state.usuario_logado = False
    st.session_state.dados_usuario = None
    st.rerun()

st.sidebar.markdown("---")

# --- MENU NAVEGACIONAL ---
if eh_admin:
    opcoes_menu = [
        "📊 Fluxo de Caixa & DRE Universal", 
        "🧮 Calculadora de Precificação",
        "⚡ Mineração de Mercado (Mercado Livre)",
        "👑 Painel Admin (Gestão de Licenças)"
    ]
elif est_pago:
    opcoes_menu = [
        "📊 Fluxo de Caixa & DRE Universal", 
        "🧮 Calculadora de Precificação",
        "⚡ Mineração de Mercado (Mercado Livre)"
    ]
else:
    opcoes_menu = ["🔒 Acesso Bloqueado"]

st.sidebar.title("📌 Menu Principal")
pagina = st.sidebar.radio("Navegar para:", opcoes_menu)

# ==============================================================================
# TELA DE BLOQUEIO
# ==============================================================================
if pagina == "🔒 Acesso Bloqueado" or (not eh_admin and not est_pago):
    st.error("⛔ Acesso Restrito / Licença Inativa ou Expirada")
    st.warning(
        "Sua licença atual de acesso está **inativa ou expirou**. "
        "Realize a renovação abaixo para continuar acessando os módulos do sistema."
    )
    
    user_id_atual = dados_user.get("user_id")
    link_mp = gerar_link_pagamento_mp(user_id=user_id_atual, email=dados_user.get("email"))

    if link_mp:
        st.markdown(
            f"""
            <a href="{link_mp}" target="_blank">
                <button style="
                    background-color: #009EE3;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 6px;
                    font-size: 16px;
                    font-weight: bold;
                    cursor: pointer;
                    width: 100%;
                    margin-top: 10px;
                ">
                    💳 Renovar Acesso por 30 Dias no Mercado Pago (Pix / Cartão)
                </button>
            </a>
            """,
            unsafe_allow_html=True
        )
        st.caption("Após concluir o pagamento, retorne nesta página e clique no botão de checagem abaixo.")
    else:
        st.info("Entre em contato com o suporte para ativar seu acesso.")
    
    st.markdown("---")

    if st.button("🔄 Já efetuei o pagamento / Checar Aprovação"):
        with st.spinner("Consultando renovação no Mercado Pago..."):
            foi_pago = verificar_e_atualizar_pagamento_mp(user_id_atual)
            if foi_pago:
                st.session_state.dados_usuario["pago"] = True
                st.success("🎉 Pagamento confirmado com sucesso! Licença estendida por 30 dias.")
                st.rerun()
            else:
                st.error("Ainda não identificamos a aprovação do seu pagamento. Aguarde alguns instantes e tente novamente.")

    st.stop()

# ==============================================================================
# MOTOR INTELIGENTE DE PROCESSAMENTO DE PLANILHAS
# ==============================================================================
def remover_acentos(texto):
    if not isinstance(texto, str):
        return str(texto)
    return ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()

def limpar_e_converter_valor(serie):
    if pd.api.types.is_numeric_dtype(serie):
        return serie.fillna(0.0).astype(float)
    
    s = serie.astype(str).str.replace('R$', '', regex=False).str.strip()
    com_virgula = s.str.contains(',', regex=False, na=False)
    s_br = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
    s_final = s.where(~com_virgula, s_br)

    return pd.to_numeric(s_final, errors='coerce').fillna(0.0)

def auto_detectar_estrutura(df):
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
    df_proc = pd.DataFrame()
    df_proc['Valor_Bruto'] = limpar_e_converter_valor(df[col_val])
    
    if col_tipo and col_tipo != "-- Não utilizar --":
        tipo_limpo = df[col_tipo].astype(str).apply(remover_acentos)
        mapeamento_tipos = {
            'entrada': 'Entrada', 'entradas': 'Entrada', 'receita': 'Entrada', 'receitas': 'Entrada',
            'credito': 'Entrada', 'c': 'Entrada', 'venda': 'Entrada', 'vendas': 'Entrada',
            'saida': 'Saída', 'saidas': 'Saída', 'despesa': 'Saída', 'despesas': 'Saída',
            'debito': 'Saída', 'd': 'Saída', 'custo': 'Saída', 'custos': 'Saída', 'pagamento': 'Saída'
        }
        df_proc['Tipo'] = tipo_limpo.map(mapeamento_tipos).fillna('Outros')
        df_proc.loc[df_proc['Valor_Bruto'] < 0, 'Tipo'] = 'Saída'
        df_proc['Valor'] = df_proc['Valor_Bruto'].abs()
    else:
        df_proc['Tipo'] = df_proc['Valor_Bruto'].apply(lambda x: 'Saída' if x < 0 else 'Entrada')
        df_proc['Valor'] = df_proc['Valor_Bruto'].abs()
        
    if col_cat and col_cat != "-- Não utilizar --":
        df_proc['Categoria'] = df[col_cat].fillna("Geral / Outros").astype(str)
    else:
        df_proc['Categoria'] = "Geral"
        
    if col_desc and col_desc != "-- Não utilizar --":
        df_proc['Descrição'] = df[col_desc].fillna("-").astype(str)
    else:
        df_proc['Descrição'] = "Sem Descrição"
        
    if col_data and col_data != "-- Não utilizar --":
        df_proc['Data'] = pd.to_datetime(df[col_data], errors='coerce')
    else:
        df_proc['Data'] = pd.NaT

    return df_proc[df_proc['Tipo'].isin(['Entrada', 'Saída'])]

def carregar_dataframe_seguro(uploaded_file):
    try:
        TAMANHO_MAX_MB = 15
        if uploaded_file.size > TAMANHO_MAX_MB * 1024 * 1024:
            st.error(f"⚠️ O arquivo excede o tamanho máximo permitido de {TAMANHO_MAX_MB}MB.")
            return None

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

            if sel_val != "-- Não utilizar --":
                df_tratado = normalizar_df_financeiro(
                    df_bruto, sel_data, sel_desc, sel_cat, sel_tipo, sel_val
                )

                if df_tratado.empty:
                    st.warning("⚠️ Não foram encontrados lançamentos válidos com os parâmetros atuais.")
                    st.stop()

                total_entradas = df_tratado[df_tratado['Tipo'] == 'Entrada']['Valor'].sum()
                total_saidas = df_tratado[df_tratado['Tipo'] == 'Saída']['Valor'].sum()
                saldo_atual = total_entradas - total_saidas

                col1, col2, col3 = st.columns(3)
                col1.metric("🟢 ENTRADAS (RECEITAS)", f"R$ {total_entradas:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'))
                col2.metric("🔴 SAÍDAS (DESPESAS)", f"R$ {total_saidas:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'))
                col3.metric("🔵 SALDO ATUAL OPERACIONAL", f"R$ {saldo_atual:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'))

                st.markdown("---")

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
                value=f"R$ {preco_sugerido:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'),
                delta=f"Markup: {markup_multiplicador:.2f}x o custo"
            )

            col_m1, col_m2 = st.columns(2)
            col_m1.metric("Lucro Líquido por Venda", f"R$ {lucro_liquido_real:,.2f}".replace(',', 'v').replace('.', ',').replace('v', '.'))
            col_m2.metric("Margem Real Efetiva", f"{margem_real_efetiva:.1f}%")

            if taxa_fixa_canal > 0 and (taxa_fixa_canal / preco_sugerido * 100) > 15:
                st.warning(f"⚠️ **Atenção à Taxa Fixa:** Consome **{(taxa_fixa_canal/preco_sugerido*100):.1f}%** do valor final do produto!")
            
            if lucro_liquido_real < 5.00:
                st.warning(f"⚠️ **Lucro Baixo:** Apenas R$ {lucro_liquido_real:.2f} de margem líquida unitária.")
            else:
                st.success("✅ **Margem Protegida:** Excelente retorno líquido.")

            st.markdown("---")
            st.subheader("📊 DRE Unitário")

            df_dre_unit = pd.DataFrame({
                "Componente": ["Custo (COGS)", "Embalagem/Frete", "Comissão ML/Shopee", "Taxa Fixa", "Impostos (NF)", "LUCRO LÍQUIDO"],
                "Valor (R$)": [custo_unitario, custo_embalagem + custo_frete, v_comissao, taxa_fixa_canal, v_imposto, lucro_liquido_real]
            })

            fig_pizza_prec = px.pie(df_dre_unit, names="Componente", values="Valor (R$)", hole=0.4, color_discrete_sequence=px.colors.qualitative.Bold)
            fig_pizza_prec.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pizza_prec, use_container_width=True)

            st.markdown("---")
            st.subheader("📥 Exportar Relatório do Produto")
            df_export = pd.DataFrame([
                {"Métrica": "Produto", "Valor": nome_prod},
                {"Métrica": "Preço Recomendado", "Valor": f"R$ {preco_sugerido:.2f}"},
                {"Métrica": "Custo Unitário (COGS)", "Valor": f"R$ {custo_unitario:.2f}"},
                {"Métrica": "Embalagem + Frete", "Valor": f"R$ {custo_embalagem + custo_frete:.2f}"},
                {"Métrica": "Comissão Marketplace", "Valor": f"R$ {v_comissao:.2f} ({comissao_pct}%)"},
                {"Métrica": "Taxa Fixa Canal", "Valor": f"R$ {taxa_fixa_canal:.2f}"},
                {"Métrica": "Imposto Nota Fiscal", "Valor": f"R$ {v_imposto:.2f} ({imposto_pct}%)"},
                {"Métrica": "Lucro Líquido Real", "Valor": f"R$ {lucro_liquido_real:.2f}"},
                {"Métrica": "Margem Efetiva", "Valor": f"{margem_real_efetiva:.2f}%"}
            ])
            
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_export.to_excel(writer, sheet_name='Diagnostico', index=False)
            buffer_excel.seek(0)

            st.download_button(
                label="📄 Baixar Diagnóstico (.xlsx)",
                data=buffer_excel.getvalue(),
                file_name=f"Diagnostico_{nome_prod.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        else:
            st.error("A soma das taxas e margens ultrapassa 100%. Ajuste as porcentagens.")

# ==============================================================================
# PÁGINA 3: MINERAÇÃO DE MERCADO (MERCADO LIVRE API)
# ==============================================================================
elif pagina == "⚡ Mineração de Mercado (Mercado Livre)":
    st.title("⚡ Mineração de Mercado & Análise Concorrencial")
    st.caption("Pesquise concorrentes em tempo real e analise faixas de preço no Mercado Livre.")

    # Busca segura das chaves em Secrets
    APP_ID = str(st.secrets.get("ML_APP_ID", "SEU_APP_ID_AQUI"))
    CLIENT_SECRET = str(st.secrets.get("ML_CLIENT_SECRET", "SEU_CLIENT_SECRET_AQUI"))

    @st.cache_data(ttl=20000)
    def obter_access_token(app_id, client_secret):
        if not app_id or not client_secret or app_id == "SEU_APP_ID_AQUI" or client_secret == "SEU_CLIENT_SECRET_AQUI":
            return None
        url = "https://api.mercadolibre.com/oauth/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": app_id,
            "client_secret": client_secret
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            response = requests.post(url, data=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json().get("access_token")
            return None
        except Exception:
            return None

    # Parâmetros na Sidebar
    st.sidebar.header("🎯 Parâmetros da Mineração")
    termo_busca = st.sidebar.text_input("Produto / Termo", value="micro retifica")
    custo_unitario = st.sidebar.number_input("Seu Custo Unitário (R$)", value=90.00, step=5.0)
    investimento_total = st.sidebar.number_input("Investimento Total (R$)", value=5000.00, step=500.0)

    st.sidebar.subheader("⚙️ Taxas da Operação")
    taxa_ml = st.sidebar.slider("Taxa Marketplace (%)", 10.0, 25.0, 16.5) / 100
    imposto = st.sidebar.slider("Imposto (%)", 0.0, 20.0, 6.0) / 100
    frete_fixo = st.sidebar.number_input("Frete Médio (R$)", value=21.00, step=1.0)

    btn_buscar = st.sidebar.button("🚀 Analisar Mercado", use_container_width=True)

    def buscar_produtos_api(termo):
        token = obter_access_token(APP_ID, CLIENT_SECRET)
        url = "https://api.mercadolibre.com/sites/MLB/search"
        params = {"q": termo, "limit": 30}
        headers = {"User-Agent": "Mozilla/5.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code in [401, 403] and not token:
                st.error("🔒 **Acesso Restrito:** As credenciais `ML_APP_ID` e `ML_CLIENT_SECRET` precisam ser configuradas no menu Secrets do Streamlit.")
                return None
            elif response.status_code != 200:
                st.error(f"Erro na comunicação com a API (Status: {response.status_code}).")
                return None

            dados = response.json()
            resultados = dados.get("results", [])
            if not resultados:
                return None

            dados_produtos = []
            for item in resultados:
                preco = item.get("price", 0.0)
                titulo = item.get("title", "")
                permalink = item.get("permalink", "")
                condicao = item.get("condition", "new")
                if preco > 15.0 and condicao == "new":
                    dados_produtos.append({"Produto": titulo, "Preco": float(preco), "Link": permalink})
            
            df = pd.DataFrame(dados_produtos).drop_duplicates(subset=["Produto"]).head(20)
            return df
        except Exception as e:
            st.error(f"Erro na conexão: {e}")
            return None

    if btn_buscar:
        with st.spinner("Consultando anúncios no Mercado Livre..."):
            df_m = buscar_produtos_api(termo_busca)

        if df_m is not None and not df_m.empty:
            preco_medio = df_m["Preco"].mean()
            preco_venda = preco_medio * 0.95 
            receita_liquida = preco_venda - (preco_venda * taxa_ml) - (preco_venda * imposto) - frete_fixo
            lucro_unidade = receita_liquida - custo_unitario
            margem_percentual = (lucro_unidade / preco_venda) * 100 if preco_venda > 0 else 0
            estoque_inicial = investimento_total // custo_unitario if custo_unitario > 0 else 0
            roi = ((lucro_unidade * estoque_inicial) / investimento_total) * 100 if investimento_total > 0 else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preço Médio", f"R$ {preco_medio:.2f}")
            c2.metric("Sugestão (-5%)", f"R$ {preco_venda:.2f}")
            c3.metric("Margem Est.", f"{margem_percentual:.1f}%")
            c4.metric("ROI Previsto", f"{roi:.1f}%")

            st.markdown("---")
            col_l, col_r = st.columns([2, 1])
            with col_l:
                fig = px.histogram(df_m, x="Preco", nbins=10, title="Distribuição de Preços", color_discrete_sequence=['#00D4B1'])
                st.plotly_chart(fig, use_container_width=True)
            with col_r:
                st.subheader("💡 Diagnóstico")
                st.write(f"• **Estoque Inicial:** {int(estoque_inicial)} un")
                st.write(f"• **Lucro Líquido / Un:** R$ {lucro_unidade:.2f}")
                if roi > 30 and margem_percentual > 15:
                    st.success("🚀 Oportunidade de alta viabilidade.")
                else:
                    st.warning("⚖️ Margem comprimida, avalie seus custos.")

            st.dataframe(df_m, column_config={"Link": st.column_config.LinkColumn("Anúncio ML")}, use_container_width=True)

# ==============================================================================
# PÁGINA 4: PAINEL ADMINISTRATIVO
# ==============================================================================
elif pagina == "👑 Painel Admin (Gestão de Licenças)" and eh_admin:
    st.title("👑 Painel Administrativo")
    st.caption("Gerencie o acesso das lojas cadastradas e libere pagamentos.")

    if st.button("🔄 Atualizar Lista de Lojas"):
        st.rerun()

    lojistas = listar_todos_lojistas()

    if lojistas:
        st.subheader("📋 Lista de Lojas Registradas")
        st.markdown("---")
        
        for item in lojistas:
            col_info, col_status, col_acao = st.columns([3, 2, 2])
            
            with col_info:
                st.write(f"**{item.get('nome_loja', 'Loja Sem Nome')}**")
                st.caption(f"E-mail: {item.get('email', 'N/A')}")
            
            with col_status:
                es_admin_item = str(item.get("perfil", "")).strip().lower() == "admin"
                if item.get("pago") or es_admin_item:
                    st.success("🟢 Acesso Liberado" + (" (Admin)" if es_admin_item else ""))
                else:
                    st.error("🔴 Aguardando Pagamento")
                    
            with col_acao:
                if not es_admin_item:
                    btn_rotulo = "Bloquear" if item.get("pago") else "Liberar Acesso (+30 dias)"
                    if st.button(btn_rotulo, key=f"btn_{item['id']}"):
                        if alternar_status_pagamento(item['id'], item.get("pago", False)):
                            st.success("Status atualizado com sucesso!")
                            st.rerun()
                else:
                    st.info("Conta Mestra")
    else:
        st.info("Nenhum lojista cadastrado até o momento.")
