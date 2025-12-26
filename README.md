# 📊 Budget Engine

**Motor de Orçamento para Consultoria em Controladoria**

Sistema profissional para gestão de budgets de múltiplos clientes, importação de dados do Excel e geração de dashboards financeiros.

---

## 🚀 Como Rodar

### 1. Pré-requisitos
- Python 3.10 ou superior
- pip (gerenciador de pacotes Python)

### 2. Instalação

```bash
# Navegar para a pasta do projeto
cd budget_engine

# Criar ambiente virtual (recomendado)
python -m venv venv

# Ativar ambiente virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt
```

### 3. Executar

```bash
streamlit run app.py
```

O sistema abrirá automaticamente no navegador em `http://localhost:8501`

---

## 📁 Estrutura do Projeto

```
budget_engine/
├── app.py                    # Aplicação principal Streamlit
├── config.py                 # Configurações e constantes
├── database.py               # Gestão de banco de dados (SQLite)
├── requirements.txt          # Dependências Python
├── modules/
│   ├── __init__.py
│   └── excel_parser.py       # Parser do modelo Excel
├── data/
│   └── budget_engine.db      # Banco de dados SQLite (criado automaticamente)
├── uploads/                  # Arquivos dos clientes
└── assets/                   # Recursos visuais
```

---

## 🎯 Funcionalidades

### ✅ Implementadas (v1.0)
- **Gestão de Clientes**: Cadastro, listagem e seleção de clientes
- **Importação de Budget**: Upload do arquivo Excel e extração automática de dados
- **Dashboard de Indicadores**: KPIs principais (Receita, Resultado, Margens)
- **Visualização do DRE**: Tabela completa e gráficos
- **Fluxo de Caixa**: Entradas e saídas organizadas
- **Gráficos Interativos**: Receita por serviço, composição do resultado (waterfall)

### 🔜 Próximas Versões
- [ ] Simulador de cenários (what-if)
- [ ] Comparativo orçado vs. realizado
- [ ] Exportação de relatórios PDF
- [ ] Análise de ponto de equilíbrio
- [ ] Projeção de fluxo de caixa
- [ ] Dashboard executivo para cliente

---

## 📊 Formato do Excel Esperado

O sistema foi projetado para o modelo de budget com as seguintes abas:

| Aba | Descrição |
|-----|-----------|
| `DRE` | Demonstração do Resultado do Exercício |
| `9_Fluxo_Caixa` | Fluxo de Caixa Projetado |
| `Projeção Despesas` | Despesas mensais projetadas |
| `Premissas Metas` | Parâmetros e premissas |
| `TDABC` | Custeio ABC |
| `Simples Nacional` | Cálculo de impostos |

---

## 🛠️ Customização

### Adicionar Nova Aba do Excel

Edite `config.py`:

```python
EXCEL_SHEETS_MAP = {
    "nova_aba": "Nome da Aba no Excel",
    # ...
}
```

### Alterar Cores do Tema

Edite `config.py`:

```python
COLORS = {
    "primary": "#1a365d",
    "accent": "#38a169",
    # ...
}
```

---

## 📞 Suporte

Desenvolvido para uso interno na consultoria de controladoria.

**Versão:** 1.0.0  
**Data:** Dezembro 2024
