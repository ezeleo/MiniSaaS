import os
import time
import mercadopago
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Tenta obter as credenciais via st.secrets de forma segura sem lançar exceção
SUPABASE_URL = None
SUPABASE_KEY = None

try:
    if "SUPABASE_URL" in st.secrets:
        SUPABASE_URL = st.secrets["SUPABASE_URL"]
    if "SUPABASE_KEY" in st.secrets:
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except Exception:
    pass

# Se não encontrou em st.secrets, utiliza as variáveis de ambiente (.env)
if not SUPABASE_URL:
    SUPABASE_URL = os.getenv("SUPABASE_URL")
if not SUPABASE_KEY:
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@st.cache_resource
def get_supabase_client() -> Client:
    """Cria e mantém a conexão padrão do cliente Supabase no Streamlit."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ As chaves SUPABASE_URL e SUPABASE_KEY não foram encontradas no .env ou nos Secrets do Streamlit.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

def criar_novo_usuario(email: str, senha: str, nome_loja: str):
    """
    Cadastra o utilizador no sistema de Auth nativo do Supabase
    e salva o perfil da loja na tabela pública.
    """
    try:
        resposta_auth = supabase.auth.sign_up({"email": email, "password": senha})
        
        if resposta_auth.user:
            user_id = resposta_auth.user.id
            
            dados_perfil = {
                "id": user_id,
                "email": email,
                "nome_loja": nome_loja,
                "plano": "Gratuito",
                "perfil": "user",
                "pago": False
            }
            
            # Insere o perfil do lojista utilizando a chave pública anon
            supabase.table("perfis_lojistas").upsert(dados_perfil).execute()
            
            return True, "✅ Conta criada com sucesso! Já pode fazer login."
        else:
            return False, "⚠️ Não foi possível registrar o utilizador."

    except Exception as e:
        erro_str = str(e).lower()
        if "already registered" in erro_str or "23505" in erro_str or "duplicate" in erro_str:
            return False, "⚠️ Este e-mail já está cadastrado. Por favor, vá para a aba 'Fazer Login'."
        return False, f"❌ Erro ao cadastrar: {str(e)}"

def autenticar_usuario(email: str, senha: str):
    """
    Autentica o e-mail e senha no Supabase com resiliência a falhas temporárias (ex: 503 Service Unavailable).
    """
    tentativas = 3
    for i in range(tentativas):
        try:
            resposta = supabase.auth.sign_in_with_password({"email": email, "password": senha})
            
            if resposta.user:
                user_id = resposta.user.id
                user_email = resposta.user.email
                
                # Busca perfil no banco
                perfil_res = supabase.table("perfis_lojistas").select("*").eq("id", user_id).execute()
                
                perfil_definido = "user"
                nome_loja = "Minha Loja"
                plano = "Gratuito"
                pago = False

                if perfil_res.data and len(perfil_res.data) > 0:
                    dados_banco = perfil_res.data[0]
                    perfil_definido = str(dados_banco.get("perfil", "user")).strip().lower()
                    nome_loja = dados_banco.get("nome_loja", "Minha Loja")
                    plano = dados_banco.get("plano", "Gratuito")
                    
                    # REGRA DE ISENÇÃO DE ADMIN: Admin tem pago=True automaticamente
                    if perfil_definido == "admin":
                        pago = True
                    else:
                        pago = dados_banco.get("pago", False)

                dados_sessao = {
                    "user_id": user_id,
                    "email": user_email,
                    "nome_loja": nome_loja,
                    "plano": plano,
                    "perfil": perfil_definido,
                    "pago": pago,
                    "access_token": resposta.session.access_token if resposta.session else None
                }
                    
                return True, dados_sessao
            else:
                return False, "❌ E-mail ou senha incorretos."

        except Exception as e:
            erro_msg = str(e)
            if ("503" in erro_msg or "unavailable" in erro_msg.lower()) and i < tentativas - 1:
                time.sleep(1)
                continue
            return False, f"❌ Erro ao conectar ao servidor de autenticação: {erro_msg}"

# ==============================================================================
# INTEGRAÇÃO MERCADO PAGO
# ==============================================================================

def _obter_mp_token():
    """Busca o token do Mercado Pago nos Secrets ou no .env"""
    try:
        if "MP_ACCESS_TOKEN" in st.secrets:
            return st.secrets["MP_ACCESS_TOKEN"]
    except Exception:
        pass
    return os.getenv("MP_ACCESS_TOKEN")


def gerar_link_pagamento_mp(user_id: str, email: str, valor: float = 49.90) -> str | None:
    """Gera um link de checkout preference do Mercado Pago passando o user_id como external_reference."""
    try:
        mp_token = _obter_mp_token()
        if not mp_token:
            st.error("Chave MP_ACCESS_TOKEN não configurada no ambiente.")
            return None

        sdk = mercadopago.SDK(mp_token)

        preference_data = {
            "items": [{
                "title": "Assinatura Mensal - Gestor Financeiro SaaS",
                "quantity": 1,
                "unit_price": float(valor),
                "currency_id": "BRL"
            }],
            "payer": {
                "email": email
            },
            "external_reference": str(user_id),
            "back_urls": {
                "success": "https://seu-saas.streamlit.app",
                "failure": "https://seu-saas.streamlit.app",
                "pending": "https://seu-saas.streamlit.app"
            },
            "auto_return": "approved"
        }

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {})
        
        # Se for teste/sandbox pode trocar por preference.get("sandbox_init_point")
        return preference.get("init_point")

    except Exception as e:
        st.error(f"Erro ao comunicar com Mercado Pago: {str(e)}")
        return None


def verificar_e_atualizar_pagamento_mp(user_id: str) -> bool:
    """
    Consulta o Mercado Pago buscando se existe algum pagamento aprovado para este user_id.
    Se encontrar, atualiza a tabela 'perfis_lojistas' no Supabase para pago = True.
    """
    try:
        mp_token = _obter_mp_token()
        if not mp_token:
            return False

        sdk = mercadopago.SDK(mp_token)
        filters = {
            "external_reference": str(user_id),
            "status": "approved"
        }

        search_result = sdk.payment().search(filters)
        results = search_result.get("response", {}).get("results", [])

        # Se encontrou pelo menos 1 pagamento aprovado para este usuário
        if len(results) > 0:
            _garantir_autenticacao()
            supabase.table("perfis_lojistas").update({"pago": True}).eq("id", user_id).execute()
            return True

        return False

    except Exception as e:
        st.error(f"Erro ao verificar pagamento: {str(e)}")
        return False

# ==============================================================================
# FUNÇÕES DE ADMINISTRAÇÃO (GESTÃO DE LICENÇAS)
# ==============================================================================

def _garantir_autenticacao():
    """Garante que as chamadas autenticadas contenham o cabeçalho Bearer do utilizador atual."""
    if "dados_usuario" in st.session_state and st.session_state.dados_usuario:
        token = st.session_state.dados_usuario.get("access_token")
        if token:
            supabase.postgrest.auth(token)

def listar_todos_lojistas():
    """Busca todas as lojas cadastradas autenticando a requisição com o token JWT ativo."""
    try:
        _garantir_autenticacao()
        resposta = supabase.table("perfis_lojistas").select("*").order("nome_loja").execute()
        return resposta.data if resposta.data else []
    except Exception as e:
        st.error(f"Erro ao buscar lojistas: {e}")
        return []

def alternar_status_pagamento(user_id: str, status_atual: bool):
    """Inverte o status de pagamento de um lojista com a permissão do utilizador logado."""
    try:
        novo_status = not status_atual
        _garantir_autenticacao()
        supabase.table("perfis_lojistas").update({"pago": novo_status}).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar status de pagamento: {e}")
        return False