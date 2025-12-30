#!/usr/bin/env python3
"""
Script para sincronizar JSON local para Supabase
"""
import json
import os
import sys

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

# Carrega JSON local
json_path = "data/clientes/fvs/copacabana.json"
if not os.path.exists(json_path):
    print(f"❌ Arquivo {json_path} não encontrado!")
    sys.exit(1)

with open(json_path) as f:
    data = json.load(f)

print(f"✅ JSON carregado: {len(str(data))} chars")

# Verifica dados
for cenario in ['Conservador', 'Pessimista', 'Otimista']:
    cen_data = data.get('cenarios', {}).get(cenario, {})
    fisios = cen_data.get('fisioterapeutas', {})
    total_sessoes = sum(
        sum(f.get('sessoes_por_servico', {}).values()) 
        for f in fisios.values()
    )
    print(f"   {cenario}: {len(fisios)} fisios, {total_sessoes:.0f} sessões")

# Busca company FVS
all_companies = supabase.table('companies').select('*').execute()
company_id = None
for c in all_companies.data:
    name = c.get('name', '').lower()
    if 'fvs' in name:
        company_id = c.get('id')
        print(f"✅ Company FVS: {company_id}")
        break

# Busca branch Copacabana
branches = supabase.table('branches').select('*').eq('company_id', company_id).execute()
branch_id = None
for b in branches.data:
    name = b.get('name', '').lower()
    if 'copacabana' in name:
        branch_id = b.get('id')
        print(f"✅ Branch Copacabana: {branch_id}")
        break

# Atualiza dados na coluna 'data'
try:
    result = supabase.table('branches').update({'data': data}).eq('id', branch_id).execute()
    if result.data:
        print("")
        print("✅ ✅ ✅ DADOS ATUALIZADOS COM SUCESSO! ✅ ✅ ✅")
        print("")
        print("Agora recarregue o app no navegador (F5)")
    else:
        print("❌ Erro ao atualizar - resultado vazio")
except Exception as e:
    print(f"❌ Erro ao atualizar: {e}")
    sys.exit(1)
