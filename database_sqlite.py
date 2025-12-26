"""
Gestão de Banco de Dados - Clientes e Projetos
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from config import DATABASE_PATH

def get_connection():
    """Retorna conexão com o banco de dados"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Inicializa o banco de dados com as tabelas necessárias"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabela de clientes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cnpj TEXT,
            segmento TEXT DEFAULT 'Fisioterapia',
            contato TEXT,
            email TEXT,
            telefone TEXT,
            observacoes TEXT,
            ativo INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tabela de projetos/budgets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projetos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL,
            nome TEXT NOT NULL,
            ano_referencia INTEGER NOT NULL,
            arquivo_origem TEXT,
            status TEXT DEFAULT 'Em elaboração',
            observacoes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)
    
    # Tabela de dados do DRE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dre_dados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            conta TEXT NOT NULL,
            tipo TEXT NOT NULL,
            jan REAL, fev REAL, mar REAL, abr REAL, mai REAL, jun REAL,
            jul REAL, ago REAL, set_ REAL, out REAL, nov REAL, dez REAL,
            total REAL,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    """)
    
    # Tabela de dados do Fluxo de Caixa
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fluxo_caixa_dados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            descricao TEXT NOT NULL,
            tipo TEXT NOT NULL,
            jan REAL, fev REAL, mar REAL, abr REAL, mai REAL, jun REAL,
            jul REAL, ago REAL, set_ REAL, out REAL, nov REAL, dez REAL,
            total REAL,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    """)
    
    # Tabela de premissas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS premissas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            parametro TEXT NOT NULL,
            valor TEXT,
            unidade TEXT,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    """)
    
    # Tabela de indicadores calculados (cache)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indicadores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            projeto_id INTEGER NOT NULL,
            indicador TEXT NOT NULL,
            valor REAL,
            meta REAL,
            unidade TEXT,
            categoria TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (projeto_id) REFERENCES projetos(id)
        )
    """)
    
    conn.commit()
    conn.close()

# ============================================
# CRUD de Clientes
# ============================================

def criar_cliente(nome, cnpj=None, segmento="Fisioterapia", contato=None, 
                  email=None, telefone=None, observacoes=None):
    """Cria um novo cliente"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clientes (nome, cnpj, segmento, contato, email, telefone, observacoes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (nome, cnpj, segmento, contato, email, telefone, observacoes))
    cliente_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return cliente_id

def listar_clientes(apenas_ativos=True):
    """Lista todos os clientes"""
    conn = get_connection()
    cursor = conn.cursor()
    if apenas_ativos:
        cursor.execute("SELECT * FROM clientes WHERE ativo = 1 ORDER BY nome")
    else:
        cursor.execute("SELECT * FROM clientes ORDER BY nome")
    clientes = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return clientes

def buscar_cliente(cliente_id):
    """Busca um cliente pelo ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
    cliente = cursor.fetchone()
    conn.close()
    return dict(cliente) if cliente else None

def atualizar_cliente(cliente_id, **kwargs):
    """Atualiza dados de um cliente"""
    conn = get_connection()
    cursor = conn.cursor()
    campos = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    valores = list(kwargs.values()) + [datetime.now(), cliente_id]
    cursor.execute(f"""
        UPDATE clientes SET {campos}, updated_at = ? WHERE id = ?
    """, valores)
    conn.commit()
    conn.close()

def desativar_cliente(cliente_id):
    """Desativa um cliente (soft delete)"""
    atualizar_cliente(cliente_id, ativo=0)

# ============================================
# CRUD de Projetos
# ============================================

def criar_projeto(cliente_id, nome, ano_referencia, arquivo_origem=None, observacoes=None):
    """Cria um novo projeto de budget"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO projetos (cliente_id, nome, ano_referencia, arquivo_origem, observacoes)
        VALUES (?, ?, ?, ?, ?)
    """, (cliente_id, nome, ano_referencia, arquivo_origem, observacoes))
    projeto_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return projeto_id

def listar_projetos(cliente_id=None):
    """Lista projetos, opcionalmente filtrados por cliente"""
    conn = get_connection()
    cursor = conn.cursor()
    if cliente_id:
        cursor.execute("""
            SELECT p.*, c.nome as cliente_nome 
            FROM projetos p 
            JOIN clientes c ON p.cliente_id = c.id 
            WHERE p.cliente_id = ? 
            ORDER BY p.ano_referencia DESC, p.created_at DESC
        """, (cliente_id,))
    else:
        cursor.execute("""
            SELECT p.*, c.nome as cliente_nome 
            FROM projetos p 
            JOIN clientes c ON p.cliente_id = c.id 
            ORDER BY p.created_at DESC
        """)
    projetos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return projetos

def buscar_projeto(projeto_id):
    """Busca um projeto pelo ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.nome as cliente_nome 
        FROM projetos p 
        JOIN clientes c ON p.cliente_id = c.id 
        WHERE p.id = ?
    """, (projeto_id,))
    projeto = cursor.fetchone()
    conn.close()
    return dict(projeto) if projeto else None

def atualizar_projeto(projeto_id, **kwargs):
    """Atualiza dados de um projeto"""
    conn = get_connection()
    cursor = conn.cursor()
    campos = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    valores = list(kwargs.values()) + [datetime.now(), projeto_id]
    cursor.execute(f"""
        UPDATE projetos SET {campos}, updated_at = ? WHERE id = ?
    """, valores)
    conn.commit()
    conn.close()

# ============================================
# Dados do Projeto (DRE, Fluxo, etc)
# ============================================

def salvar_dre(projeto_id, dados_dre):
    """Salva dados do DRE"""
    conn = get_connection()
    cursor = conn.cursor()
    # Limpa dados anteriores
    cursor.execute("DELETE FROM dre_dados WHERE projeto_id = ?", (projeto_id,))
    # Insere novos dados
    for row in dados_dre:
        cursor.execute("""
            INSERT INTO dre_dados 
            (projeto_id, conta, tipo, jan, fev, mar, abr, mai, jun, jul, ago, set_, out, nov, dez, total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (projeto_id, row['conta'], row['tipo'], 
              row.get('jan'), row.get('fev'), row.get('mar'), row.get('abr'),
              row.get('mai'), row.get('jun'), row.get('jul'), row.get('ago'),
              row.get('set'), row.get('out'), row.get('nov'), row.get('dez'),
              row.get('total')))
    conn.commit()
    conn.close()

def buscar_dre(projeto_id):
    """Busca dados do DRE de um projeto"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dre_dados WHERE projeto_id = ?", (projeto_id,))
    dados = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return dados

def salvar_indicadores(projeto_id, indicadores):
    """Salva indicadores calculados"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM indicadores WHERE projeto_id = ?", (projeto_id,))
    for ind in indicadores:
        cursor.execute("""
            INSERT INTO indicadores (projeto_id, indicador, valor, meta, unidade, categoria)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (projeto_id, ind['indicador'], ind.get('valor'), ind.get('meta'),
              ind.get('unidade'), ind.get('categoria')))
    conn.commit()
    conn.close()

def buscar_indicadores(projeto_id):
    """Busca indicadores de um projeto"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM indicadores WHERE projeto_id = ?", (projeto_id,))
    dados = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return dados

# Inicializa o banco ao importar
init_database()
