# 🚀 GUIA: Implementar Banco de Dados no Budget Engine

## 📋 RESUMO

Este guia vai te ajudar a:
1. Criar as tabelas no Supabase
2. Migrar dados da Amanda Packer e FVS
3. Testar o sistema com autenticação

---

## PASSO 1: Criar Tabelas no Supabase

### 1.1 Acesse o Supabase
1. Vá para: https://supabase.com/dashboard
2. Faça login
3. Clique no seu projeto: **Budget Engine**

### 1.2 Execute o SQL
1. No menu lateral, clique em **SQL Editor**
2. Clique em **+ New Query**
3. Copie TODO o conteúdo do arquivo `supabase_setup.sql`
4. Cole no editor
5. Clique no botão **Run** (ou Ctrl+Enter)

### 1.3 Verifique se funcionou
No menu lateral, clique em **Table Editor**. Você deve ver:
- ✅ companies
- ✅ users
- ✅ branches
- ✅ realizado

---

## PASSO 2: Migrar Dados Existentes

### 2.1 No seu Mac, abra o Terminal

### 2.2 Navegue até a pasta do projeto
```bash
cd ~/Downloads/budget_engine-75
```

### 2.3 Instale as dependências (se ainda não instalou)
```bash
pip install supabase
```

### 2.4 Execute a migração
```bash
python migrar_dados.py
```

### 2.5 Você deve ver algo assim:
```
🚀 MIGRAÇÃO BUDGET ENGINE - JSON → SUPABASE
📡 Conectando ao Supabase...
   ✅ Conectado!
📂 Buscando clientes locais...
   ✅ Encontrados 2 clientes:
      - Amanda Packer (1 filiais)
      - FVS (2 filiais)
📦 INICIANDO MIGRAÇÃO
   ✅ Empresa criada
   ✅ Filial criada: matriz
   ✅ Usuário criado: amanda_packer@budgetengine.com
...
🎉 Migração concluída!
```

---

## PASSO 3: Testar o Sistema

### 3.1 Execute o Streamlit local
```bash
streamlit run app.py
```

### 3.2 Teste o login com:
- **Email:** `admin@demo.com`
- **Senha:** `Budget2024!`

### 3.3 Ou use os logins dos clientes migrados:
- `amanda_packer@budgetengine.com` / `Budget2024!`
- `fvs@budgetengine.com` / `Budget2024!`

---

## PASSO 4: Subir para Produção (GitHub)

### 4.1 Atualize os arquivos no GitHub
Suba os novos arquivos:
- `supabase_manager.py`
- `requirements.txt` (atualizado)

### 4.2 Configure os Secrets no Streamlit Cloud
1. Vá para: https://share.streamlit.io/
2. Clique no seu app
3. Clique em **Settings** → **Secrets**
4. Adicione:
```toml
[supabase]
url = "https://boffqphbqqamrnviowwj.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJvZmZxcGhicXFhbXJudmlvd3dqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY2NjQ2NjAsImV4cCI6MjA4MjI0MDY2MH0.aVJdKhUxIZYccjdSshhCzKAkIQJFgw_r0gr1YF10D0A"
```

---

## ✅ CHECKLIST

- [ ] SQL executado no Supabase
- [ ] Tabelas criadas (companies, users, branches, realizado)
- [ ] Migração executada
- [ ] Dados de Amanda Packer migrados
- [ ] Dados de FVS migrados
- [ ] Login testado localmente
- [ ] Arquivos atualizados no GitHub
- [ ] Secrets configurados no Streamlit Cloud
- [ ] Sistema funcionando em produção

---

## 🆘 PROBLEMAS COMUNS

### "Erro de conexão com Supabase"
- Verifique se as credenciais em `.streamlit/secrets.toml` estão corretas
- Verifique se o projeto Supabase está ativo

### "Tabela não existe"
- Execute o `supabase_setup.sql` novamente
- Verifique no Table Editor se as tabelas foram criadas

### "Email ou senha incorretos"
- Use: `admin@demo.com` / `Budget2024!`
- Ou recrie o usuário no SQL Editor

### "Dados não aparecem"
- Verifique se a migração rodou sem erros
- Verifique no Supabase se os dados estão nas tabelas

---

## 📞 SUPORTE

Se tiver problemas, me mande:
1. A mensagem de erro completa
2. Print do que aparece no Supabase
3. O que você tentou fazer

**Vamos resolver!** 🚀
