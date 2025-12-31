"""
Sistema de Autenticação - Budget Engine
Integração com Supabase para multi-tenancy
"""

import streamlit as st
from supabase import create_client, Client
import bcrypt
from datetime import datetime
from typing import Optional, Dict, Any

# ============================================
# CONFIGURAÇÃO DO SUPABASE - SINGLETON v1.99.85
# ============================================

_supabase_client = None

def get_supabase_client() -> Client:
    """
    Retorna cliente Supabase configurado.
    Credenciais devem estar em .streamlit/secrets.toml
    USA SINGLETON para evitar "Too many open files"
    """
    global _supabase_client

    # Reutiliza conexão existente
    if _supabase_client is not None:
        return _supabase_client

    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        st.error(f"Erro ao conectar com Supabase: {e}")
        st.info("Configure as credenciais em .streamlit/secrets.toml")
        return None

# ============================================
# FUNÇÕES DE HASH DE SENHA
# ============================================

def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Verifica se senha corresponde ao hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# ============================================
# FUNÇÕES DE AUTENTICAÇÃO
# ============================================

def login(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Autentica usuário e retorna dados se sucesso.
    
    Returns:
        Dict com dados do usuário ou None se falhar
    """
    supabase = get_supabase_client()
    if not supabase:
        return None
    
    try:
        # Busca usuário pelo email
        response = supabase.table("users").select(
            "*, companies(*)"
        ).eq("email", email.lower().strip()).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        user = response.data[0]
        
        # Verifica senha
        if not verify_password(password, user["password_hash"]):
            return None
        
        # Verifica se usuário está ativo
        if not user.get("is_active", True):
            return None
        
        # Atualiza último login
        supabase.table("users").update({
            "last_login": datetime.now().isoformat()
        }).eq("id", user["id"]).execute()
        
        # Remove hash da senha antes de retornar
        user.pop("password_hash", None)
        
        return user
        
    except Exception as e:
        st.error(f"Erro no login: {e}")
        return None

def logout():
    """Limpa sessão do usuário"""
    keys_to_clear = ["user", "authenticated", "company_id", "user_id"]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]

def is_authenticated() -> bool:
    """Verifica se usuário está autenticado"""
    return st.session_state.get("authenticated", False) and "user" in st.session_state

def get_current_user() -> Optional[Dict[str, Any]]:
    """Retorna dados do usuário logado"""
    if is_authenticated():
        return st.session_state.get("user")
    return None

def get_current_company_id() -> Optional[str]:
    """Retorna ID da empresa do usuário logado"""
    user = get_current_user()
    if user:
        return user.get("company_id")
    return None

# ============================================
# FUNÇÕES DE REGISTRO
# ============================================

def create_company(
    name: str,
    cnpj: str = None,
    tax_regime: str = "simples_nacional"
) -> Optional[Dict[str, Any]]:
    """
    Cria nova empresa (tenant).
    
    Returns:
        Dict com dados da empresa ou None se falhar
    """
    supabase = get_supabase_client()
    if not supabase:
        return None
    
    try:
        response = supabase.table("companies").insert({
            "name": name,
            "cnpj": cnpj,
            "tax_regime": tax_regime,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        st.error(f"Erro ao criar empresa: {e}")
        return None

def create_user(
    email: str,
    password: str,
    name: str,
    company_id: str,
    role: str = "user"
) -> Optional[Dict[str, Any]]:
    """
    Cria novo usuário.
    
    Returns:
        Dict com dados do usuário ou None se falhar
    """
    supabase = get_supabase_client()
    if not supabase:
        return None
    
    try:
        # Verifica se email já existe
        existing = supabase.table("users").select("id").eq(
            "email", email.lower().strip()
        ).execute()
        
        if existing.data and len(existing.data) > 0:
            st.error("Email já cadastrado!")
            return None
        
        # Cria usuário
        password_hash = hash_password(password)
        
        response = supabase.table("users").insert({
            "email": email.lower().strip(),
            "password_hash": password_hash,
            "name": name,
            "company_id": company_id,
            "role": role,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        if response.data:
            user = response.data[0]
            user.pop("password_hash", None)
            return user
        return None
        
    except Exception as e:
        st.error(f"Erro ao criar usuário: {e}")
        return None

# ============================================
# COMPONENTES DE INTERFACE
# ============================================

def show_login_form():
    """
    Exibe formulário de login.
    Retorna True se login bem sucedido.
    """
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("## 🔐 Budget Engine")
        st.markdown("### Login")
        
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="seu@email.com")
            password = st.text_input("Senha", type="password", placeholder="Sua senha")
            
            submitted = st.form_submit_button("Entrar", use_container_width=True)
            
            if submitted:
                if not email or not password:
                    st.error("Preencha email e senha!")
                    return False
                
                with st.spinner("Verificando..."):
                    user = login(email, password)
                    
                    if user:
                        st.session_state["user"] = user
                        st.session_state["authenticated"] = True
                        st.session_state["company_id"] = user.get("company_id")
                        st.session_state["user_id"] = user.get("id")
                        st.success(f"Bem-vindo, {user.get('name', 'Usuário')}!")
                        st.rerun()
                        return True
                    else:
                        st.error("Email ou senha incorretos!")
                        return False
        
        # Informações de demo (remover em produção)
        with st.expander("🧪 Credenciais de Teste"):
            st.code("""
Email: admin@demo.com
Senha: Budget2024!
            """)
    
    return False

def show_user_menu():
    """Exibe menu do usuário logado no sidebar"""
    user = get_current_user()
    if not user:
        return
    
    with st.sidebar:
        st.markdown("---")
        st.markdown(f"👤 **{user.get('name', 'Usuário')}**")
        
        company = user.get("companies", {})
        if company:
            st.caption(f"🏢 {company.get('name', 'Empresa')}")
        
        if st.button("🚪 Sair", use_container_width=True):
            logout()
            st.rerun()

def require_auth(func):
    """
    Decorator para proteger páginas que requerem autenticação.
    
    Uso:
        @require_auth
        def minha_pagina():
            st.write("Conteúdo protegido")
    """
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            show_login_form()
            st.stop()
        return func(*args, **kwargs)
    return wrapper

# ============================================
# FUNÇÕES AUXILIARES DE MULTI-TENANCY
# ============================================

def get_tenant_data(table: str, filters: Dict = None) -> list:
    """
    Busca dados filtrados pelo tenant (empresa) do usuário logado.
    
    Args:
        table: Nome da tabela no Supabase
        filters: Filtros adicionais opcionais
    
    Returns:
        Lista de registros
    """
    supabase = get_supabase_client()
    company_id = get_current_company_id()
    
    if not supabase or not company_id:
        return []
    
    try:
        query = supabase.table(table).select("*").eq("company_id", company_id)
        
        if filters:
            for key, value in filters.items():
                query = query.eq(key, value)
        
        response = query.execute()
        return response.data if response.data else []
        
    except Exception as e:
        st.error(f"Erro ao buscar dados: {e}")
        return []

def save_tenant_data(table: str, data: Dict) -> Optional[Dict]:
    """
    Salva dados com company_id do usuário logado.
    
    Args:
        table: Nome da tabela no Supabase
        data: Dados a serem salvos
    
    Returns:
        Registro salvo ou None
    """
    supabase = get_supabase_client()
    company_id = get_current_company_id()
    
    if not supabase or not company_id:
        return None
    
    try:
        # Adiciona company_id aos dados
        data["company_id"] = company_id
        data["updated_at"] = datetime.now().isoformat()
        
        if "id" in data and data["id"]:
            # Update
            response = supabase.table(table).update(data).eq(
                "id", data["id"]
            ).eq("company_id", company_id).execute()
        else:
            # Insert
            data["created_at"] = datetime.now().isoformat()
            response = supabase.table(table).insert(data).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        st.error(f"Erro ao salvar dados: {e}")
        return None

def delete_tenant_data(table: str, record_id: str) -> bool:
    """
    Deleta registro verificando company_id.
    
    Args:
        table: Nome da tabela
        record_id: ID do registro
    
    Returns:
        True se deletado com sucesso
    """
    supabase = get_supabase_client()
    company_id = get_current_company_id()
    
    if not supabase or not company_id:
        return False
    
    try:
        response = supabase.table(table).delete().eq(
            "id", record_id
        ).eq("company_id", company_id).execute()
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao deletar: {e}")
        return False
