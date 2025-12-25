"""
Supabase Manager - Budget Engine
Gerencia dados de clientes e filiais no Supabase (PostgreSQL)
Substitui o cliente_manager.py para persistência em banco
"""

import streamlit as st
from supabase import create_client, Client
from typing import Optional, Dict, List, Any
from datetime import datetime
import json

# ============================================
# CONEXÃO COM SUPABASE
# ============================================

@st.cache_resource
def get_supabase() -> Optional[Client]:
    """Retorna cliente Supabase (cached)"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Erro ao conectar com Supabase: {e}")
        return None

# ============================================
# CLASSE PRINCIPAL
# ============================================

class SupabaseManager:
    """
    Gerenciador de dados no Supabase.
    Substitui ClienteManager para uso com banco de dados.
    """
    
    def __init__(self, company_id: str = None):
        """
        Inicializa o manager.
        
        Args:
            company_id: ID da empresa (obtido do login)
        """
        self.supabase = get_supabase()
        self.company_id = company_id
    
    def set_company(self, company_id: str):
        """Define a empresa atual"""
        self.company_id = company_id
    
    # ============================================
    # EMPRESAS (COMPANIES)
    # ============================================
    
    def listar_empresas(self) -> List[Dict]:
        """Lista todas as empresas"""
        if not self.supabase:
            return []
        
        try:
            response = self.supabase.table("companies").select("*").eq("is_active", True).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Erro ao listar empresas: {e}")
            return []
    
    def obter_empresa(self, company_id: str = None) -> Optional[Dict]:
        """Obtém dados de uma empresa"""
        if not self.supabase:
            return None
        
        cid = company_id or self.company_id
        if not cid:
            return None
        
        try:
            response = self.supabase.table("companies").select("*").eq("id", cid).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao obter empresa: {e}")
            return None
    
    def criar_empresa(self, nome: str, cnpj: str = "", **kwargs) -> Optional[Dict]:
        """Cria nova empresa"""
        if not self.supabase:
            return None
        
        try:
            data = {
                "name": nome,
                "cnpj": cnpj,
                "is_active": True,
                **kwargs
            }
            response = self.supabase.table("companies").insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao criar empresa: {e}")
            return None
    
    def atualizar_empresa(self, company_id: str, data: Dict) -> bool:
        """Atualiza dados da empresa"""
        if not self.supabase:
            return False
        
        try:
            self.supabase.table("companies").update(data).eq("id", company_id).execute()
            return True
        except Exception as e:
            st.error(f"Erro ao atualizar empresa: {e}")
            return False
    
    # ============================================
    # FILIAIS (BRANCHES)
    # ============================================
    
    def listar_filiais(self, company_id: str = None) -> List[Dict]:
        """Lista filiais de uma empresa"""
        if not self.supabase:
            return []
        
        cid = company_id or self.company_id
        if not cid:
            return []
        
        try:
            response = self.supabase.table("branches").select("*").eq(
                "company_id", cid
            ).eq("is_active", True).execute()
            return response.data if response.data else []
        except Exception as e:
            st.error(f"Erro ao listar filiais: {e}")
            return []
    
    def obter_filial(self, branch_id: str = None, slug: str = None) -> Optional[Dict]:
        """Obtém dados de uma filial por ID ou slug"""
        if not self.supabase:
            return None
        
        try:
            if branch_id:
                response = self.supabase.table("branches").select("*").eq("id", branch_id).execute()
            elif slug and self.company_id:
                response = self.supabase.table("branches").select("*").eq(
                    "company_id", self.company_id
                ).eq("slug", slug).execute()
            else:
                return None
            
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao obter filial: {e}")
            return None
    
    def criar_filial(self, nome: str, slug: str, data: Dict = None) -> Optional[Dict]:
        """Cria nova filial"""
        if not self.supabase or not self.company_id:
            return None
        
        try:
            branch_data = {
                "company_id": self.company_id,
                "name": nome,
                "slug": slug,
                "is_active": True,
                "data": data or {}
            }
            response = self.supabase.table("branches").insert(branch_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            st.error(f"Erro ao criar filial: {e}")
            return None
    
    def salvar_filial(self, branch_id: str, data: Dict) -> bool:
        """Salva dados completos de uma filial"""
        if not self.supabase:
            return False
        
        try:
            self.supabase.table("branches").update({
                "data": data,
                "updated_at": datetime.now().isoformat()
            }).eq("id", branch_id).execute()
            return True
        except Exception as e:
            st.error(f"Erro ao salvar filial: {e}")
            return False
    
    def deletar_filial(self, branch_id: str) -> bool:
        """Desativa uma filial (soft delete)"""
        if not self.supabase:
            return False
        
        try:
            self.supabase.table("branches").update({
                "is_active": False
            }).eq("id", branch_id).execute()
            return True
        except Exception as e:
            st.error(f"Erro ao deletar filial: {e}")
            return False
    
    # ============================================
    # DADOS DO MOTOR (BUDGET DATA)
    # ============================================
    
    def carregar_dados_filial(self, branch_id: str = None, slug: str = None) -> Dict:
        """
        Carrega dados completos de uma filial (para o MotorCalculo).
        
        Returns:
            Dict com estrutura compatível com motor_para_dict/dict_para_motor
        """
        filial = self.obter_filial(branch_id=branch_id, slug=slug)
        
        if not filial:
            return {}
        
        return filial.get("data", {})
    
    def salvar_dados_filial(self, data: Dict, branch_id: str = None, slug: str = None) -> bool:
        """
        Salva dados completos de uma filial (do MotorCalculo).
        
        Args:
            data: Dict com estrutura de motor_para_dict
            branch_id: ID da filial
            slug: ou slug da filial
        """
        if branch_id:
            return self.salvar_filial(branch_id, data)
        elif slug:
            filial = self.obter_filial(slug=slug)
            if filial:
                return self.salvar_filial(filial["id"], data)
        return False
    
    # ============================================
    # COMPATIBILIDADE COM CLIENTE_MANAGER
    # ============================================
    
    def listar_clientes(self) -> List[str]:
        """
        Lista nomes de clientes (compatível com ClienteManager).
        Retorna lista de nomes das empresas.
        """
        empresas = self.listar_empresas()
        return [e.get("name", "") for e in empresas]
    
    def listar_filiais_cliente(self, cliente_nome: str) -> List[str]:
        """
        Lista filiais de um cliente pelo nome (compatível com ClienteManager).
        """
        # Buscar empresa pelo nome
        try:
            response = self.supabase.table("companies").select("id").eq("name", cliente_nome).execute()
            if not response.data:
                return []
            
            company_id = response.data[0]["id"]
            filiais = self.listar_filiais(company_id)
            return [f.get("slug", "") for f in filiais]
        except:
            return []
    
    def carregar_cliente(self, cliente_nome: str, filial_slug: str = None) -> Dict:
        """
        Carrega dados de cliente/filial (compatível com ClienteManager).
        
        Args:
            cliente_nome: Nome da empresa
            filial_slug: Slug da filial (opcional)
        
        Returns:
            Dict com dados da filial ou empresa
        """
        try:
            # Buscar empresa pelo nome
            response = self.supabase.table("companies").select("*").eq("name", cliente_nome).execute()
            if not response.data:
                return {}
            
            empresa = response.data[0]
            self.company_id = empresa["id"]
            
            if filial_slug:
                # Carregar dados da filial específica
                return self.carregar_dados_filial(slug=filial_slug)
            else:
                # Retornar dados da primeira filial ou vazio
                filiais = self.listar_filiais()
                if filiais:
                    return filiais[0].get("data", {})
                return {}
        except Exception as e:
            st.error(f"Erro ao carregar cliente: {e}")
            return {}
    
    def salvar_cliente(self, cliente_nome: str, filial_slug: str, data: Dict) -> bool:
        """
        Salva dados de cliente/filial (compatível com ClienteManager).
        """
        try:
            # Buscar empresa pelo nome
            response = self.supabase.table("companies").select("id").eq("name", cliente_nome).execute()
            if not response.data:
                return False
            
            company_id = response.data[0]["id"]
            self.company_id = company_id
            
            return self.salvar_dados_filial(data, slug=filial_slug)
        except Exception as e:
            st.error(f"Erro ao salvar cliente: {e}")
            return False


# ============================================
# FUNÇÕES DE CONVENIÊNCIA
# ============================================

def get_manager(company_id: str = None) -> SupabaseManager:
    """
    Retorna instância do SupabaseManager.
    Usa company_id da sessão se não fornecido.
    """
    if not company_id and "company_id" in st.session_state:
        company_id = st.session_state.get("company_id")
    
    return SupabaseManager(company_id)


def carregar_dados_usuario_logado() -> Dict:
    """
    Carrega dados da empresa/filiais do usuário logado.
    
    Returns:
        Dict com:
        - empresa: dados da empresa
        - filiais: lista de filiais
        - filial_atual: dados da filial selecionada
    """
    if "company_id" not in st.session_state:
        return {}
    
    manager = get_manager()
    
    empresa = manager.obter_empresa()
    filiais = manager.listar_filiais()
    
    # Se tem filial selecionada, carrega os dados
    filial_atual = None
    if "branch_id" in st.session_state:
        filial_atual = manager.obter_filial(st.session_state["branch_id"])
    elif filiais:
        filial_atual = filiais[0]
    
    return {
        "empresa": empresa,
        "filiais": filiais,
        "filial_atual": filial_atual
    }


# ============================================
# MIGRAÇÃO/IMPORTAÇÃO DE DADOS JSON
# ============================================

def importar_json_para_filial(json_data: Dict, branch_id: str) -> bool:
    """
    Importa dados de JSON para uma filial existente.
    Útil para migração de dados antigos.
    """
    manager = get_manager()
    return manager.salvar_filial(branch_id, json_data)


def exportar_filial_para_json(branch_id: str) -> Dict:
    """
    Exporta dados de uma filial para JSON.
    Útil para backup ou migração.
    """
    manager = get_manager()
    return manager.carregar_dados_filial(branch_id=branch_id)
