"""
Script de Migração - Budget Engine
Migra dados de JSON local para Supabase

INSTRUÇÕES:
1. Execute supabase_setup.sql primeiro no Supabase
2. Depois rode: python migrar_dados.py
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Tenta importar supabase
try:
    from supabase import create_client, Client
    import streamlit as st
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️  Biblioteca supabase não instalada.")
    print("   Execute: pip install supabase")

# ============================================
# CONFIGURAÇÃO
# ============================================

# Diretório dos dados locais
DATA_DIR = Path(__file__).parent / "data" / "clientes"

# Credenciais Supabase (copie do .streamlit/secrets.toml)
SUPABASE_URL = "https://boffqphbqqamrnviowwj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJvZmZxcGhicXFhbXJudmlvd3dqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY2NjQ2NjAsImV4cCI6MjA4MjI0MDY2MH0.aVJdKhUxIZYccjdSshhCzKAkIQJFgw_r0gr1YF10D0A"

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def carregar_json(filepath: Path) -> dict:
    """Carrega arquivo JSON"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Erro ao carregar {filepath}: {e}")
        return {}

def listar_clientes() -> list:
    """Lista todos os clientes no diretório data/clientes"""
    clientes = []
    
    if not DATA_DIR.exists():
        print(f"❌ Diretório não encontrado: {DATA_DIR}")
        return clientes
    
    for item in DATA_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            config_file = item / "config.json"
            if config_file.exists():
                clientes.append({
                    "id": item.name,
                    "path": item,
                    "config": carregar_json(config_file)
                })
    
    return clientes

def get_supabase_client() -> Client:
    """Retorna cliente Supabase"""
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================
# MIGRAÇÃO
# ============================================

def migrar_cliente(supabase: Client, cliente: dict) -> bool:
    """
    Migra um cliente e suas filiais para o Supabase
    
    Estrutura:
    - cliente -> companies
    - cada filial -> branches (com data JSON completo)
    """
    config = cliente["config"]
    cliente_path = cliente["path"]
    
    print(f"\n📦 Migrando cliente: {config.get('nome', cliente['id'])}")
    
    try:
        # 1. Criar empresa (company)
        company_data = {
            "name": config.get("nome", cliente["id"]),
            "cnpj": config.get("cnpj", ""),
            "email": config.get("email", ""),
            "telefone": config.get("telefone", ""),
            "contato": config.get("contato", ""),
            "tax_regime": "simples_nacional",  # Será atualizado pela filial
            "premissas_macro": config.get("premissas_macro", {}),
            "is_active": True
        }
        
        # Verifica se empresa já existe
        existing = supabase.table("companies").select("id").eq("name", company_data["name"]).execute()
        
        if existing.data and len(existing.data) > 0:
            company_id = existing.data[0]["id"]
            print(f"   ℹ️  Empresa já existe, atualizando...")
            supabase.table("companies").update(company_data).eq("id", company_id).execute()
        else:
            response = supabase.table("companies").insert(company_data).execute()
            company_id = response.data[0]["id"]
            print(f"   ✅ Empresa criada: {company_id}")
        
        # 2. Migrar cada filial
        filiais = config.get("filiais", [])
        
        for filial_slug in filiais:
            filial_file = cliente_path / f"{filial_slug}.json"
            
            if not filial_file.exists():
                print(f"   ⚠️  Arquivo não encontrado: {filial_file}")
                continue
            
            filial_data = carregar_json(filial_file)
            
            if not filial_data:
                print(f"   ⚠️  Dados vazios para filial: {filial_slug}")
                continue
            
            # Determinar regime tributário da filial
            operacional = filial_data.get("operacional", {})
            modelo = operacional.get("modelo_tributario", "")
            
            if "PF" in modelo or "Carnê" in modelo.lower():
                tax_regime = "pf_carne_leao"
            else:
                tax_regime = "simples_nacional"
            
            # Dados da filial para o Supabase
            branch_data = {
                "company_id": company_id,
                "name": filial_slug.replace("_", " ").title(),
                "slug": filial_slug,
                "is_active": True,
                "data": filial_data  # JSON completo da filial!
            }
            
            # Verifica se filial já existe
            existing_branch = supabase.table("branches").select("id").eq(
                "company_id", company_id
            ).eq("slug", filial_slug).execute()
            
            if existing_branch.data and len(existing_branch.data) > 0:
                branch_id = existing_branch.data[0]["id"]
                print(f"   ℹ️  Filial '{filial_slug}' já existe, atualizando...")
                supabase.table("branches").update(branch_data).eq("id", branch_id).execute()
            else:
                response = supabase.table("branches").insert(branch_data).execute()
                branch_id = response.data[0]["id"]
                print(f"   ✅ Filial criada: {filial_slug} ({branch_id})")
            
            # Atualizar regime tributário da empresa baseado na filial principal
            if filial_slug == "matriz" or len(filiais) == 1:
                supabase.table("companies").update({
                    "tax_regime": tax_regime
                }).eq("id", company_id).execute()
        
        # 3. Criar usuário padrão para o cliente
        user_email = config.get("email") or f"{cliente['id']}@budgetengine.com"
        user_name = config.get("contato") or config.get("nome", "Usuário")
        
        # Verifica se usuário já existe
        existing_user = supabase.table("users").select("id").eq("email", user_email).execute()
        
        if not existing_user.data:
            # Hash da senha padrão "Budget2024!"
            password_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.PJ/mOi"
            
            user_data = {
                "company_id": company_id,
                "email": user_email,
                "password_hash": password_hash,
                "name": user_name,
                "role": "admin",
                "is_active": True
            }
            
            supabase.table("users").insert(user_data).execute()
            print(f"   ✅ Usuário criado: {user_email} (senha: Budget2024!)")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao migrar cliente: {e}")
        import traceback
        traceback.print_exc()
        return False

def executar_migracao():
    """Executa migração completa"""
    print("=" * 50)
    print("🚀 MIGRAÇÃO BUDGET ENGINE - JSON → SUPABASE")
    print("=" * 50)
    
    if not SUPABASE_AVAILABLE:
        print("\n❌ Biblioteca supabase não disponível!")
        print("   Instale com: pip install supabase")
        return
    
    # Conectar ao Supabase
    print("\n📡 Conectando ao Supabase...")
    try:
        supabase = get_supabase_client()
        print("   ✅ Conectado!")
    except Exception as e:
        print(f"   ❌ Erro de conexão: {e}")
        return
    
    # Listar clientes
    print("\n📂 Buscando clientes locais...")
    clientes = listar_clientes()
    
    if not clientes:
        print("   ⚠️  Nenhum cliente encontrado!")
        return
    
    print(f"   ✅ Encontrados {len(clientes)} clientes:")
    for c in clientes:
        nome = c["config"].get("nome", c["id"])
        filiais = c["config"].get("filiais", [])
        print(f"      - {nome} ({len(filiais)} filiais)")
    
    # Migrar cada cliente
    print("\n" + "=" * 50)
    print("📦 INICIANDO MIGRAÇÃO")
    print("=" * 50)
    
    sucesso = 0
    erro = 0
    
    for cliente in clientes:
        if migrar_cliente(supabase, cliente):
            sucesso += 1
        else:
            erro += 1
    
    # Resumo
    print("\n" + "=" * 50)
    print("📊 RESUMO DA MIGRAÇÃO")
    print("=" * 50)
    print(f"   ✅ Sucesso: {sucesso} clientes")
    print(f"   ❌ Erros: {erro} clientes")
    
    if sucesso > 0:
        print("\n🎉 Migração concluída!")
        print("\n📋 PRÓXIMOS PASSOS:")
        print("   1. Verifique os dados no Supabase Dashboard")
        print("   2. Teste o login com: admin@demo.com / Budget2024!")
        print("   3. Ou use os emails dos clientes migrados")

# ============================================
# EXECUÇÃO
# ============================================

if __name__ == "__main__":
    executar_migracao()
