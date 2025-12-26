"""
Módulo de Administração - Budget Engine
Gerenciamento de Empresas e Usuários (Simplificado)
"""

import streamlit as st
from auth import get_supabase_client, hash_password, get_current_user
from datetime import datetime
from typing import Optional, Dict, List

# ============================================
# FUNÇÕES DE BANCO DE DADOS
# ============================================

def listar_empresas_com_usuarios() -> List[Dict]:
    """Lista todas as empresas com seus usuários"""
    supabase = get_supabase_client()
    if not supabase:
        return []
    
    try:
        response = supabase.table("companies").select("*").order("name").execute()
        empresas = response.data if response.data else []
        
        # Buscar usuários de cada empresa
        for emp in empresas:
            users_resp = supabase.table("users").select("*").eq("company_id", emp["id"]).execute()
            emp["usuarios"] = users_resp.data if users_resp.data else []
        
        return empresas
    except Exception as e:
        st.error(f"Erro ao listar empresas: {e}")
        return []

def criar_empresa_com_usuario(
    nome_empresa: str,
    nome_responsavel: str,
    usuario: str,
    senha: str,
    perfil: str = "user"
) -> bool:
    """Cria uma empresa e seu usuário administrador"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        # Verificar se usuário já existe
        existing = supabase.table("users").select("id").eq("email", usuario.lower().strip()).execute()
        if existing.data and len(existing.data) > 0:
            st.error("⚠️ Este usuário já existe!")
            return False
        
        # 1. Criar empresa
        emp_response = supabase.table("companies").insert({
            "name": nome_empresa,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        if not emp_response.data:
            st.error("Erro ao criar empresa!")
            return False
        
        empresa_id = emp_response.data[0]["id"]
        
        # 2. Criar usuário
        password_hash = hash_password(senha)
        
        user_response = supabase.table("users").insert({
            "email": usuario.lower().strip(),
            "password_hash": password_hash,
            "name": nome_responsavel,
            "company_id": empresa_id,
            "role": perfil,  # Usa o perfil selecionado
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        if not user_response.data:
            # Se falhou, excluir empresa criada
            supabase.table("companies").delete().eq("id", empresa_id).execute()
            st.error("Erro ao criar usuário!")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao criar cadastro: {e}")
        return False

def adicionar_usuario_empresa(
    empresa_id: int,
    nome: str,
    usuario: str,
    senha: str,
    role: str = "user"
) -> bool:
    """Adiciona um usuário a uma empresa existente"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        # Verificar se usuário já existe
        existing = supabase.table("users").select("id").eq("email", usuario.lower().strip()).execute()
        if existing.data and len(existing.data) > 0:
            st.error("⚠️ Este usuário já existe!")
            return False
        
        password_hash = hash_password(senha)
        
        response = supabase.table("users").insert({
            "email": usuario.lower().strip(),
            "password_hash": password_hash,
            "name": nome,
            "company_id": empresa_id,
            "role": role,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }).execute()
        
        return bool(response.data)
        
    except Exception as e:
        st.error(f"Erro ao adicionar usuário: {e}")
        return False

def resetar_senha(user_id: int, nova_senha: str) -> bool:
    """Reseta a senha de um usuário"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        password_hash = hash_password(nova_senha)
        supabase.table("users").update({
            "password_hash": password_hash
        }).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao resetar senha: {e}")
        return False

def alterar_status_usuario(user_id: int, ativo: bool) -> bool:
    """Ativa ou desativa um usuário"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        supabase.table("users").update({
            "is_active": ativo
        }).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao alterar status: {e}")
        return False

def atualizar_usuario(user_id: int, dados: dict) -> bool:
    """Atualiza dados de um usuário (nome, email, role)"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        supabase.table("users").update(dados).eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar usuário: {e}")
        return False

def excluir_usuario(user_id: int) -> bool:
    """Exclui um usuário"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir usuário: {e}")
        return False

def excluir_empresa(empresa_id: int) -> bool:
    """Exclui uma empresa e todos seus usuários"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        # Usuários são excluídos automaticamente pelo CASCADE
        supabase.table("companies").delete().eq("id", empresa_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao excluir empresa: {e}")
        return False

def atualizar_empresa(empresa_id: int, nome: str) -> bool:
    """Atualiza o nome de uma empresa"""
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        supabase.table("companies").update({
            "name": nome,
            "updated_at": datetime.now().isoformat()
        }).eq("id", empresa_id).execute()
        return True
    except Exception as e:
        st.error(f"Erro ao atualizar empresa: {e}")
        return False

# ============================================
# PÁGINA DE ADMINISTRAÇÃO
# ============================================

def pagina_admin():
    """Página principal de administração"""
    
    st.markdown("""
    <div class="main-header">
        <h1>🔧 Administração</h1>
        <p>Gerenciar acessos ao sistema</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificar se é admin
    user = get_current_user()
    if user and user.get("role") != "admin":
        st.error("⛔ Acesso restrito a administradores!")
        return
    
    # Layout em duas colunas
    col_lista, col_form = st.columns([3, 2])
    
    # ========== COLUNA ESQUERDA: LISTA ==========
    with col_lista:
        st.markdown("### 📋 Empresas e Usuários Cadastrados")
        
        empresas = listar_empresas_com_usuarios()
        
        if empresas:
            for emp in empresas:
                usuarios = emp.get("usuarios", [])
                qtd_users = len(usuarios)
                
                with st.expander(f"🏢 **{emp['name']}** ({qtd_users} usuário{'s' if qtd_users != 1 else ''})", expanded=False):
                    
                    # Lista de usuários
                    if usuarios:
                        for usr in usuarios:
                            status_icon = "🟢" if usr.get("is_active", True) else "🔴"
                            role_badge = "👑" if usr.get("role") == "admin" else "👤"
                            
                            st.markdown(f"""
                            **{status_icon} {usr['name']}** {role_badge}  
                            `{usr['email']}`
                            """)
                            
                            # Botões de ação principais
                            col1, col2, col3, col4 = st.columns(4)
                            
                            with col1:
                                if st.button("✏️ Editar", key=f"edit_{usr['id']}", use_container_width=True):
                                    st.session_state[f"show_edit_{usr['id']}"] = True
                                    st.session_state[f"show_pwd_{usr['id']}"] = False
                            
                            with col2:
                                if st.button("🔑 Senha", key=f"pwd_btn_{usr['id']}", use_container_width=True):
                                    st.session_state[f"show_pwd_{usr['id']}"] = True
                                    st.session_state[f"show_edit_{usr['id']}"] = False
                            
                            with col3:
                                novo_status = not usr.get("is_active", True)
                                btn_label = "🟢 Ativar" if novo_status else "🔴 Desativar"
                                if st.button(btn_label, key=f"status_{usr['id']}", use_container_width=True):
                                    if alterar_status_usuario(usr['id'], novo_status):
                                        st.success("✅ Status alterado!")
                                        st.rerun()
                            
                            with col4:
                                if st.button("🗑️ Excluir", key=f"del_{usr['id']}", use_container_width=True):
                                    st.session_state[f"confirm_del_user_{usr['id']}"] = True
                            
                            # Formulário de EDIÇÃO
                            if st.session_state.get(f"show_edit_{usr['id']}", False):
                                st.markdown("---")
                                st.markdown("**✏️ Editar Cadastro:**")
                                
                                novo_nome = st.text_input("Nome", value=usr['name'], key=f"edit_name_{usr['id']}")
                                novo_login = st.text_input("Usuário/Login", value=usr['email'], key=f"edit_login_{usr['id']}")
                                novo_perfil = st.selectbox(
                                    "Perfil",
                                    ["user", "admin"],
                                    index=0 if usr.get('role') == 'user' else 1,
                                    format_func=lambda x: "👤 Usuário" if x == "user" else "👑 Administrador",
                                    key=f"edit_role_{usr['id']}"
                                )
                                
                                col_x, col_y = st.columns(2)
                                with col_x:
                                    if st.button("💾 Salvar", key=f"save_edit_{usr['id']}", use_container_width=True):
                                        if novo_nome and novo_login:
                                            if atualizar_usuario(usr['id'], {
                                                "name": novo_nome,
                                                "email": novo_login.lower().strip(),
                                                "role": novo_perfil
                                            }):
                                                st.success("✅ Cadastro atualizado!")
                                                st.session_state[f"show_edit_{usr['id']}"] = False
                                                st.rerun()
                                        else:
                                            st.error("Preencha todos os campos!")
                                with col_y:
                                    if st.button("❌ Cancelar", key=f"cancel_edit_{usr['id']}", use_container_width=True):
                                        st.session_state[f"show_edit_{usr['id']}"] = False
                                        st.rerun()
                            
                            # Formulário de TROCAR SENHA
                            if st.session_state.get(f"show_pwd_{usr['id']}", False):
                                st.markdown("---")
                                st.markdown("**🔑 Trocar Senha:**")
                                
                                nova_senha = st.text_input("Nova Senha", type="password", key=f"new_pwd_{usr['id']}", placeholder="Mínimo 6 caracteres")
                                confirma_nova = st.text_input("Confirmar Senha", type="password", key=f"conf_pwd_{usr['id']}", placeholder="Repita a senha")
                                
                                col_x, col_y = st.columns(2)
                                with col_x:
                                    if st.button("💾 Salvar Senha", key=f"save_pwd_{usr['id']}", use_container_width=True):
                                        if nova_senha and len(nova_senha) >= 6:
                                            if nova_senha == confirma_nova:
                                                if resetar_senha(usr['id'], nova_senha):
                                                    st.success("✅ Senha alterada!")
                                                    st.session_state[f"show_pwd_{usr['id']}"] = False
                                                    st.rerun()
                                            else:
                                                st.error("As senhas não conferem!")
                                        else:
                                            st.error("Mínimo 6 caracteres!")
                                with col_y:
                                    if st.button("❌ Cancelar", key=f"cancel_pwd_{usr['id']}", use_container_width=True):
                                        st.session_state[f"show_pwd_{usr['id']}"] = False
                                        st.rerun()
                            
                            # Confirmação de exclusão de usuário
                            if st.session_state.get(f"confirm_del_user_{usr['id']}", False):
                                st.markdown("---")
                                st.warning(f"⚠️ Excluir usuário **{usr['name']}**?")
                                col_x, col_y = st.columns(2)
                                with col_x:
                                    if st.button("✅ Sim", key=f"yes_del_{usr['id']}", use_container_width=True):
                                        if excluir_usuario(usr['id']):
                                            st.success("✅ Usuário excluído!")
                                            st.session_state[f"confirm_del_user_{usr['id']}"] = False
                                            st.rerun()
                                with col_y:
                                    if st.button("❌ Não", key=f"no_del_{usr['id']}", use_container_width=True):
                                        st.session_state[f"confirm_del_user_{usr['id']}"] = False
                                        st.rerun()
                            
                            st.markdown("---")
                    else:
                        st.info("Nenhum usuário cadastrado para esta empresa.")
                    
                    # Ações da empresa
                    st.markdown("**⚙️ Ações da Empresa:**")
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        if st.button("✏️ Editar Empresa", key=f"edit_emp_{emp['id']}", use_container_width=True):
                            st.session_state[f"show_edit_emp_{emp['id']}"] = True
                    
                    with col_b:
                        if st.button("➕ Add Usuário", key=f"add_user_{emp['id']}", use_container_width=True):
                            st.session_state[f"show_add_user_{emp['id']}"] = True
                    
                    with col_c:
                        if st.button("🗑️ Excluir", key=f"del_emp_{emp['id']}", use_container_width=True):
                            st.session_state[f"confirm_del_emp_{emp['id']}"] = True
                    
                    # Formulário para EDITAR EMPRESA
                    if st.session_state.get(f"show_edit_emp_{emp['id']}", False):
                        st.markdown("---")
                        st.markdown("**✏️ Editar Nome da Empresa:**")
                        
                        novo_nome_emp = st.text_input("Nome da Empresa", value=emp['name'], key=f"edit_emp_name_{emp['id']}")
                        
                        col_x, col_y = st.columns(2)
                        with col_x:
                            if st.button("💾 Salvar", key=f"save_emp_{emp['id']}", use_container_width=True):
                                if novo_nome_emp:
                                    if atualizar_empresa(emp['id'], novo_nome_emp):
                                        st.success("✅ Empresa atualizada!")
                                        st.session_state[f"show_edit_emp_{emp['id']}"] = False
                                        st.rerun()
                                else:
                                    st.error("Nome não pode ser vazio!")
                        with col_y:
                            if st.button("❌ Cancelar", key=f"cancel_emp_{emp['id']}", use_container_width=True):
                                st.session_state[f"show_edit_emp_{emp['id']}"] = False
                                st.rerun()
                    
                    # Formulário para adicionar usuário
                    if st.session_state.get(f"show_add_user_{emp['id']}", False):
                        st.markdown("---")
                        st.markdown("**➕ Novo Usuário:**")
                        
                        nome_novo = st.text_input("Nome", key=f"new_name_{emp['id']}")
                        user_novo = st.text_input("Usuário/Login", key=f"new_user_{emp['id']}")
                        pwd_novo = st.text_input("Senha", type="password", key=f"new_pwd_{emp['id']}")
                        
                        col_x, col_y = st.columns(2)
                        with col_x:
                            if st.button("✅ Criar", key=f"create_user_{emp['id']}", use_container_width=True):
                                if nome_novo and user_novo and pwd_novo:
                                    if len(pwd_novo) >= 6:
                                        if adicionar_usuario_empresa(emp['id'], nome_novo, user_novo, pwd_novo):
                                            st.success("✅ Usuário criado!")
                                            st.session_state[f"show_add_user_{emp['id']}"] = False
                                            st.rerun()
                                    else:
                                        st.error("Senha: mínimo 6 caracteres!")
                                else:
                                    st.error("Preencha todos os campos!")
                        with col_y:
                            if st.button("❌ Cancelar", key=f"cancel_user_{emp['id']}", use_container_width=True):
                                st.session_state[f"show_add_user_{emp['id']}"] = False
                                st.rerun()
                    
                    # Confirmação para excluir empresa
                    if st.session_state.get(f"confirm_del_emp_{emp['id']}", False):
                        st.markdown("---")
                        st.warning(f"⚠️ Tem certeza que deseja excluir **{emp['name']}** e todos os seus usuários?")
                        col_x, col_y = st.columns(2)
                        with col_x:
                            if st.button("✅ Sim, excluir", key=f"confirm_yes_{emp['id']}", use_container_width=True):
                                if excluir_empresa(emp['id']):
                                    st.success("✅ Empresa excluída!")
                                    st.session_state[f"confirm_del_emp_{emp['id']}"] = False
                                    st.rerun()
                        with col_y:
                            if st.button("❌ Cancelar", key=f"confirm_no_{emp['id']}", use_container_width=True):
                                st.session_state[f"confirm_del_emp_{emp['id']}"] = False
                                st.rerun()
        else:
            st.info("🏢 Nenhuma empresa cadastrada ainda.")
    
    # ========== COLUNA DIREITA: FORMULÁRIO ==========
    with col_form:
        st.markdown("### ➕ Novo Cadastro")
        st.markdown("Cadastre uma nova empresa e seu usuário administrador:")
        
        with st.form("form_novo_cadastro", clear_on_submit=True):
            st.markdown("**🏢 Dados da Empresa:**")
            nome_empresa = st.text_input("Nome da Empresa*", placeholder="Ex: Clínica FVS")
            
            st.markdown("---")
            st.markdown("**👤 Dados do Responsável:**")
            nome_responsavel = st.text_input("Nome do Responsável*", placeholder="Ex: Dr. Fernando")
            usuario = st.text_input("Usuário (login)*", placeholder="Ex: fernando ou fvs")
            senha = st.text_input("Senha*", type="password", placeholder="Mínimo 6 caracteres")
            confirma_senha = st.text_input("Confirmar Senha*", type="password", placeholder="Repita a senha")
            
            st.markdown("---")
            st.markdown("**🔐 Tipo de Acesso:**")
            perfil = st.selectbox(
                "Perfil do Usuário",
                ["user", "admin"],
                format_func=lambda x: "👤 Usuário (vê só a própria empresa)" if x == "user" else "👑 Administrador (vê tudo + gerencia)"
            )
            
            st.markdown("---")
            
            submitted = st.form_submit_button("✅ Criar Cadastro", use_container_width=True, type="primary")
            
            if submitted:
                # Validações
                erros = []
                
                if not nome_empresa:
                    erros.append("Nome da empresa é obrigatório")
                if not nome_responsavel:
                    erros.append("Nome do responsável é obrigatório")
                if not usuario:
                    erros.append("Usuário é obrigatório")
                if not senha:
                    erros.append("Senha é obrigatória")
                elif len(senha) < 6:
                    erros.append("Senha deve ter no mínimo 6 caracteres")
                elif senha != confirma_senha:
                    erros.append("As senhas não conferem")
                
                if erros:
                    for erro in erros:
                        st.error(f"⚠️ {erro}")
                else:
                    if criar_empresa_com_usuario(nome_empresa, nome_responsavel, usuario, senha, perfil):
                        st.success(f"✅ Cadastro criado com sucesso!")
                        st.balloons()
                        st.rerun()
        
        # Dica
        st.markdown("---")
        st.info("""
        💡 **Dica:** Após criar o cadastro, o usuário poderá fazer login usando o **Usuário** e **Senha** definidos aqui.
        """)
