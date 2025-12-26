-- ============================================
-- BUDGET ENGINE - SETUP DO SUPABASE
-- Execute este SQL no SQL Editor do Supabase
-- ============================================

-- Habilitar extensão UUID
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TABELA: companies (Empresas/Clientes)
-- ============================================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    cnpj VARCHAR(20),
    email VARCHAR(255),
    telefone VARCHAR(20),
    contato VARCHAR(255),
    tax_regime VARCHAR(50) DEFAULT 'simples_nacional',
    is_active BOOLEAN DEFAULT true,
    
    -- Premissas Macro (compartilhadas entre filiais)
    premissas_macro JSONB DEFAULT '{
        "ipca": 0.045,
        "igpm": 0.05,
        "dissidio": 0.06,
        "reajuste_tarifas": 0.08,
        "reajuste_contratos": 0.05,
        "taxa_credito": 0.0354,
        "taxa_debito": 0.0211,
        "taxa_antecipacao": 0.05
    }'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- TABELA: users (Usuários)
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user', -- 'admin', 'user', 'viewer'
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- TABELA: branches (Filiais)
-- ============================================
CREATE TABLE IF NOT EXISTS branches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL, -- 'matriz', 'copacabana', 'leblon'
    is_active BOOLEAN DEFAULT true,
    
    -- Todos os dados da filial em um JSONB
    -- Isso preserva a estrutura atual do sistema
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint: uma empresa não pode ter duas filiais com mesmo slug
    UNIQUE(company_id, slug)
);

-- ============================================
-- TABELA: realizado (Dados Realizados - futuro)
-- ============================================
CREATE TABLE IF NOT EXISTS realizado (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    branch_id UUID REFERENCES branches(id) ON DELETE CASCADE,
    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL CHECK (mes >= 1 AND mes <= 12),
    
    -- Dados do mês realizado
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Um registro por mês/ano/filial
    UNIQUE(branch_id, ano, mes)
);

-- ============================================
-- ÍNDICES PARA PERFORMANCE
-- ============================================
CREATE INDEX IF NOT EXISTS idx_users_company ON users(company_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_branches_company ON branches(company_id);
CREATE INDEX IF NOT EXISTS idx_branches_slug ON branches(company_id, slug);
CREATE INDEX IF NOT EXISTS idx_realizado_branch ON realizado(branch_id);
CREATE INDEX IF NOT EXISTS idx_realizado_periodo ON realizado(branch_id, ano, mes);

-- ============================================
-- ROW LEVEL SECURITY (RLS) - MULTI-TENANCY
-- ============================================

-- Habilitar RLS em todas as tabelas
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE branches ENABLE ROW LEVEL SECURITY;
ALTER TABLE realizado ENABLE ROW LEVEL SECURITY;

-- Políticas para companies (todos podem ler, só admin cria)
CREATE POLICY "companies_select" ON companies FOR SELECT USING (true);
CREATE POLICY "companies_insert" ON companies FOR INSERT WITH CHECK (true);
CREATE POLICY "companies_update" ON companies FOR UPDATE USING (true);
CREATE POLICY "companies_delete" ON companies FOR DELETE USING (true);

-- Políticas para users
CREATE POLICY "users_select" ON users FOR SELECT USING (true);
CREATE POLICY "users_insert" ON users FOR INSERT WITH CHECK (true);
CREATE POLICY "users_update" ON users FOR UPDATE USING (true);
CREATE POLICY "users_delete" ON users FOR DELETE USING (true);

-- Políticas para branches
CREATE POLICY "branches_select" ON branches FOR SELECT USING (true);
CREATE POLICY "branches_insert" ON branches FOR INSERT WITH CHECK (true);
CREATE POLICY "branches_update" ON branches FOR UPDATE USING (true);
CREATE POLICY "branches_delete" ON branches FOR DELETE USING (true);

-- Políticas para realizado
CREATE POLICY "realizado_select" ON realizado FOR SELECT USING (true);
CREATE POLICY "realizado_insert" ON realizado FOR INSERT WITH CHECK (true);
CREATE POLICY "realizado_update" ON realizado FOR UPDATE USING (true);
CREATE POLICY "realizado_delete" ON realizado FOR DELETE USING (true);

-- ============================================
-- FUNÇÃO: Atualizar updated_at automaticamente
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para updated_at
DROP TRIGGER IF EXISTS update_companies_updated_at ON companies;
CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_branches_updated_at ON branches;
CREATE TRIGGER update_branches_updated_at
    BEFORE UPDATE ON branches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_realizado_updated_at ON realizado;
CREATE TRIGGER update_realizado_updated_at
    BEFORE UPDATE ON realizado
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- DADOS INICIAIS: Usuário Admin de Teste
-- ============================================

-- Criar empresa demo
INSERT INTO companies (id, name, cnpj, tax_regime)
VALUES (
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'Empresa Demo',
    '00.000.000/0001-00',
    'simples_nacional'
) ON CONFLICT DO NOTHING;

-- Criar usuário admin (senha: Budget2024!)
-- Hash bcrypt de 'Budget2024!'
INSERT INTO users (id, company_id, email, password_hash, name, role)
VALUES (
    'b0eebc99-9c0b-4ef8-bb6d-6bb9bd380a22',
    'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
    'admin@demo.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/RK.PJ/mOi',
    'Administrador',
    'admin'
) ON CONFLICT DO NOTHING;

-- ============================================
-- VERIFICAÇÃO
-- ============================================
-- Execute para verificar se tudo foi criado:
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';
