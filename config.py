"""
Configurações do Budget Engine
Motor de Orçamento para Consultoria em Controladoria
"""

import os
from pathlib import Path

# Diretórios
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = BASE_DIR / "uploads"
ASSETS_DIR = BASE_DIR / "assets"

# Criar diretórios se não existirem
for dir_path in [DATA_DIR, UPLOADS_DIR, ASSETS_DIR]:
    dir_path.mkdir(exist_ok=True)

# Banco de dados
DATABASE_PATH = DATA_DIR / "budget_engine.db"

# Configurações do sistema
APP_NAME = "Budget Engine"
APP_VERSION = "1.99.41"
APP_SUBTITLE = "Motor de Orçamento | Consultoria em Controladoria"

# Mapeamento de abas do Excel para o sistema
EXCEL_SHEETS_MAP = {
    "premissas": "Premissas Metas",
    "dre": "DRE",
    "fluxo_caixa": "9_Fluxo_Caixa",
    "despesas": "Projeção Despesas",
    "folha": "Projeção Folha e Pró-labore ",
    "resumo": "Resumo",
    "dashboard": "1_Dashboard",
    "tdabc": "TDABC",
    "faturamento": "Faturamento Ated. Profissional",
    "simples": "Simples Nacional",
    "investimentos": "Investimentos - Proximo Ano",
    "financiamentos": "Financiamentos - Existentes",
    "ponto_equilibrio": "Ponto de Equilibrio",
}

# Meses
MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

MESES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
               "Jul", "Ago", "Set", "Out", "Nov", "Dez"]

# Cores do tema
COLORS = {
    "primary": "#1a365d",      # Azul escuro
    "secondary": "#2c5282",    # Azul médio
    "accent": "#38a169",       # Verde
    "warning": "#d69e2e",      # Amarelo
    "danger": "#c53030",       # Vermelho
    "success": "#38a169",      # Verde
    "background": "#f7fafc",   # Cinza claro
    "text": "#1a202c",         # Quase preto
    "muted": "#718096",        # Cinza
}

# Formatação de valores
def format_currency(value, prefix="R$ "):
    """Formata valor como moeda brasileira"""
    if value is None or (isinstance(value, float) and str(value) == 'nan'):
        return "-"
    try:
        return f"{prefix}{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "-"

def format_percent(value, decimals=1):
    """Formata valor como percentual"""
    if value is None or (isinstance(value, float) and str(value) == 'nan'):
        return "-"
    try:
        return f"{value * 100:,.{decimals}f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "-"

def format_number(value, decimals=0):
    """Formata número com separador de milhar"""
    if value is None or (isinstance(value, float) and str(value) == 'nan'):
        return "-"
    try:
        return f"{value:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "-"
