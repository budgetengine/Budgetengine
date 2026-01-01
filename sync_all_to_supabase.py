#!/usr/bin/env python3
"""
Script para sincronizar TODOS os JSONs locais para Supabase
Inclui: copacabana, leblon, meta
"""
import json
import os
import sys
from datetime import datetime

print("=" * 60)
print("🔄 SYNC LOCAL → SUPABASE")
print("=" * 60)

# Carrega credenciais do secrets.toml
secrets_path = ".streamlit/secrets.toml"
if not os.path.exists(secrets_path):
    print(f"❌ Arquivo {secrets_path} não encontrado!")
    sys.exit(1)

# Parse do TOML (formato [supabase])
supabase_url = None
supabase_key = None

with open(secrets_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith("url"):
            supabase_url = line.split("=")[1].strip().strip('"').strip("'")
        elif line.startswith("key"):
            supabase_key = line.split("=")[1].strip().strip('"').strip("'")

if not supabase_url or not supabase_key:
    print("❌ Credenciais Supabase não encontradas!")
    sys.exit(1)

print(f"✅ Credenciais carregadas")

# Conecta ao Supabase
try:
    from supabase import create_client
    supabase = create_client(supabase_url, supabase_key)
    print("✅ Conectado ao Supabase")
except Exception as e:
    print(f"❌ Erro ao conectar: {e}")
    sys.exit(1)

# Busca company FVS
all_companies = supabase.table('companies').select('*').execute()
company_id = None
for c in all_companies.data:
    name = c.get('name', '').lower()
    if 'fvs' in name:
        company_id = c.get('id')
        print(f"✅ Company FVS encontrada: {company_id}")
        break

if not company_id:
    print("❌ Company FVS não encontrada!")
    sys.exit(1)

# Busca todas as branches
branches = supabase.table('branches').select('*').eq('company_id', company_id).execute()
print(f"✅ {len(branches.data)} branches encontradas no Supabase")

# Mapeia branches por nome
branch_map = {}
for b in branches.data:
    name = b.get('name', '').lower()
    branch_map[name] = b.get('id')

print(f"   Branches: {list(branch_map.keys())}")

# Filiais para sincronizar
filiais = ['copacabana', 'leblon', 'meta']
base_path = "data/clientes/fvs"

print("")
print("-" * 60)
print("📤 INICIANDO UPLOAD")
print("-" * 60)

success_count = 0
error_count = 0

for filial in filiais:
    json_path = f"{base_path}/{filial}.json"

    if not os.path.exists(json_path):
        print(f"⚠️  {filial}: arquivo não encontrado")
        continue

    # Carrega dados locais
    with open(json_path) as f:
        data = json.load(f)

    file_size = os.path.getsize(json_path)
    print(f"\n📁 {filial}.json ({file_size/1024:.1f} KB)")

    # Mostra resumo dos cenários
    cenario_ativo = data.get('cenario_ativo', 'N/A')
    print(f"   Cenário ativo: {cenario_ativo}")

    for cenario in ['Conservador', 'Pessimista', 'Otimista']:
        cen_data = data.get('cenarios', {}).get(cenario, {})

        # Conta profissionais
        fisios = cen_data.get('fisioterapeutas', {})
        props = cen_data.get('proprietarios', {})
        profs = cen_data.get('profissionais', {})
        total_pessoas = len(fisios) + len(props) + len(profs)

        # Conta sessões
        total_sessoes = 0
        for p in list(fisios.values()) + list(props.values()) + list(profs.values()):
            total_sessoes += sum(p.get('sessoes_por_servico', {}).values())

        if total_pessoas > 0:
            print(f"   {cenario}: {total_pessoas} pessoas, {total_sessoes:.0f} sessões/mês")

    # Busca branch no Supabase
    branch_id = branch_map.get(filial.lower())

    if not branch_id:
        # Tenta criar a branch
        print(f"   ⚠️  Branch '{filial}' não existe no Supabase")
        try:
            new_branch = supabase.table('branches').insert({
                'company_id': company_id,
                'name': filial.capitalize(),
                'data': data,
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }).execute()

            if new_branch.data:
                branch_id = new_branch.data[0].get('id')
                print(f"   ✅ Branch '{filial}' CRIADA: {branch_id}")
                success_count += 1
            else:
                print(f"   ❌ Erro ao criar branch")
                error_count += 1
        except Exception as e:
            print(f"   ❌ Erro ao criar: {e}")
            error_count += 1
        continue

    # Atualiza branch existente
    try:
        result = supabase.table('branches').update({
            'data': data,
            'updated_at': datetime.now().isoformat()
        }).eq('id', branch_id).execute()

        if result.data:
            print(f"   ✅ ATUALIZADO com sucesso!")
            success_count += 1
        else:
            print(f"   ❌ Erro - resultado vazio")
            error_count += 1
    except Exception as e:
        print(f"   ❌ Erro ao atualizar: {e}")
        error_count += 1

print("")
print("=" * 60)
if error_count == 0:
    print(f"✅ ✅ ✅ SUCESSO! {success_count} filiais sincronizadas ✅ ✅ ✅")
else:
    print(f"⚠️  {success_count} OK, {error_count} erros")
print("=" * 60)
print("")
print("🔄 Recarregue o app no navegador (F5)")
