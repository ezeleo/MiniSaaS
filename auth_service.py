import os
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Prioriza st.secrets (para Streamlit Cloud) e usa os.getenv como fallback (local)
SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.getenv("SUPABASE_URL")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.getenv("SUPABASE_KEY")

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
    Cadastra o usuário no sistema de Auth nativo do Supabase
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
            
            return True, "✅ Conta criada com sucesso! Você já pode fazer login."
        else:
            return False, "⚠️ Não foi possível registrar o usuário."

    except Exception as e:
        erro_str = str(e).lower()
        if "already registered" in erro_str or "23505" in erro_str or "duplicate" in erro_str:
            return False, "⚠️ Este e-mail já está cadastrado. Por favor, vá para a aba 'Fazer Login'."
        return False, f"❌ Erro ao cadastrar: {str(e)}"

def autenticar_usuario(email: str, senha: str):
    """
    Autentica o e-mail e senha no Supabase e recupera os dados do perfil do usuário.
    """
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

            if perfil_res.data and len(perfil_res.data) > 0:
                dados_banco = perfil_res.data[0]
                perfil_definido = dados_banco.get("perfil", "user")
                nome_loja = dados_banco.get("nome_loja", "Minha Loja")
                plano = dados_banco.get("plano", "Gratuito")
                pago = dados_banco.get("pago", False)

            dados_sessao = {
                "user_id": user_id,
                "email": user_email,
                "nome_loja": nome_loja,
                "plano": plano,
                "perfil": perfil_definido,
                "pago": pago
            }
                
            return True, dados_sessao
        else:
            return False, "❌ E-mail ou senha incorretos."

    except Exception as e:
        return False, f"❌ Erro ao autenticar: {str(e)}"

# ==============================================================================
# FUNÇÕES DE ADMINISTRAÇÃO (GESTÃO DE LICENÇAS)
# ==============================================================================

def listar_todos_lojistas():
    """Busca todas as lojas cadastradas na tabela pública."""
    try:
        resposta = supabase.table("perfis_lojistas").select("*").execute()
        return resposta.data if resposta.data else []
    except Exception as e:
        st.error(f"Erro ao buscar lojistas: {e}")
        return []

def alternar_status_pagamento(user_id: str, status_atual: bool):
    """Inverte o status de pagamento de um lojista."""
    try:
        novo_status = not status_atual
        supabase.table("perfis_lojistas").update({"pago": novo_status}).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar status de pagamento: {e}")
        return False
