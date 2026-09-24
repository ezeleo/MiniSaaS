import os
import time
from datetime import datetime, timedelta, timezone
import mercadopago
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# CARREGAMENTO DE VARIÁVEIS DE AMBIENTE / SECRETS
# ==============================================================================
def _obter_secret_ou_env(chave: str) -> str | None:
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except Exception:
        pass
    return os.getenv(chave)

SUPABASE_URL = _obter_secret_ou_env("SUPABASE_URL")
SUPABASE_KEY = _obter_secret_ou_env("SUPABASE_KEY")

@st.cache_resource
def get_supabase_client() -> Client:
    """Cria e mantém a conexão padrão do cliente Supabase no Streamlit."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("❌ As chaves SUPABASE_URL e SUPABASE_KEY não foram encontradas no .env ou nos Secrets do Streamlit.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = get_supabase_client()

# ==============================================================================
# AUTENTICAÇÃO E GESTÃO DE USUÁRIOS
# ==============================================================================
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
                "pago": False,
                "data_expiracao": None
            }
            
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
    Autentica o e-mail e senha no Supabase e valida a validade do acesso de 30 dias.
    """
    tentativas = 3
    for i in range(tentativas):
        try:
            resposta = supabase.auth.sign_in_with_password({"email": email, "password": senha})
            
            if resposta.user:
                user_id = resposta.user.id
                user_email = resposta.user.email
                
                perfil_res = supabase.table("perfis_lojistas").select("*").eq("id", user_id).execute()
                
                perfil_definido = "user"
                nome_loja = "Minha Loja"
                plano = "Gratuito"
                pago = False
                data_expiracao_str = None

                if perfil_res.data and len(perfil_res.data) > 0:
                    dados_banco = perfil_res.data[0]
                    perfil_definido = str(dados_banco.get("perfil", "user")).strip().lower()
                    nome_loja = dados_banco.get("nome_loja", "Minha Loja")
                    plano = dados_banco.get("plano", "Gratuito")
                    data_expiracao_str = dados_banco.get("data_expiracao")
                    
                    if perfil_definido == "admin":
                        pago = True
                    else:
                        pago = dados_banco.get("pago", False)
                        if pago and data_expiracao_str:
                            try:
                                dt_exp = datetime.fromisoformat(data_expiracao_str.replace('Z', '+00:00'))
                                if datetime.now(timezone.utc) > dt_exp:
                                    pago = False
                                    _garantir_autenticacao()
                                    supabase.table("perfis_lojistas").update({"pago": False}).eq("id", user_id).execute()
                            except Exception:
                                pass

                dados_sessao = {
                    "user_id": user_id,
                    "email": user_email,
                    "nome_loja": nome_loja,
                    "plano": plano,
                    "perfil": perfil_definido,
                    "pago": pago,
                    "data_expiracao": data_expiracao_str,
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
def gerar_link_pagamento_mp(user_id: str, email: str, valor: float = 49.90) -> str | None:
    """Gera link de pagamento individual para renovação mensal de 30 dias."""
    try:
        mp_token = _obter_secret_ou_env("MP_ACCESS_TOKEN")
        if not mp_token:
            st.error("Chave MP_ACCESS_TOKEN não configurada no ambiente.")
            return None

        sdk = mercadopago.SDK(mp_token)

        preference_data = {
            "items": [{
                "title": "Acesso 30 Dias - Gestor Financeiro SaaS",
                "quantity": 1,
                "unit_price": float(valor),
                "currency_id": "BRL"
            }],
            "payer": {
                "email": email
            },
            "external_reference": str(user_id),
            "auto_return": "approved"
        }

        preference_response = sdk.preference().create(preference_data)
        preference = preference_response.get("response", {})
        return preference.get("init_point")

    except Exception as e:
        st.error(f"Erro ao comunicar com Mercado Pago: {str(e)}")
        return None

def verificar_e_atualizar_pagamento_mp(user_id: str) -> bool:
    """
    Consulta o Mercado Pago e, ao confirmar pagamento aprovado,
    renova a licença concedendo +30 dias a partir de hoje.
    """
    try:
        mp_token = _obter_secret_ou_env("MP_ACCESS_TOKEN")
        if not mp_token:
            return False

        sdk = mercadopago.SDK(mp_token)
        filters = {
            "external_reference": str(user_id),
            "status": "approved"
        }

        search_result = sdk.payment().search(filters)
        results = search_result.get("response", {}).get("results", [])

        if len(results) > 0:
            nova_expiracao = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            _garantir_autenticacao()
            
            supabase.table("perfis_lojistas").update({
                "pago": True,
                "plano": "Pro Mensal",
                "data_expiracao": nova_expiracao
            }).eq("id", user_id).execute()
            
            return True

        return False

    except Exception as e:
        st.error(f"Erro ao verificar pagamento: {str(e)}")
        return False

# ==============================================================================
# FUNÇÕES DE ADMINISTRAÇÃO (GESTÃO DE LICENÇAS)
# ==============================================================================
def _garantir_autenticacao():
    if "dados_usuario" in st.session_state and st.session_state.dados_usuario:
        token = st.session_state.dados_usuario.get("access_token")
        if token:
            supabase.postgrest.auth(token)

def listar_todos_lojistas():
    try:
        _garantir_autenticacao()
        resposta = supabase.table("perfis_lojistas").select("*").order("nome_loja").execute()
        return resposta.data if resposta.data else []
    except Exception as e:
        st.error(f"Erro ao buscar lojistas: {e}")
        return []

def alternar_status_pagamento(user_id: str, status_atual: bool):
    try:
        novo_status = not status_atual
        nova_expiracao = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat() if novo_status else None
        
        _garantir_autenticacao()
        supabase.table("perfis_lojistas").update({
            "pago": novo_status,
            "data_expiracao": nova_expiracao
        }).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar status de pagamento: {e}")
        return False