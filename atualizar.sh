#!/bin/bash
# =============================================
# BUDGET ENGINE - Script de Instalação/Atualização
# Para Mac/Linux
# =============================================

echo ""
echo "🚀 BUDGET ENGINE - Instalação/Atualização"
echo "=========================================="
echo ""

# Vai para Downloads
cd ~/Downloads

# Cria ambiente virtual se não existir
if [ ! -d "venv" ]; then
    echo "📦 Criando ambiente virtual..."
    python3 -m venv venv
fi

# Ativa ambiente virtual
echo "🔌 Ativando ambiente virtual..."
source venv/bin/activate

# Instala dependências
echo "📥 Instalando dependências..."
pip install -q streamlit pandas openpyxl plotly numpy

# Executa
echo ""
echo "✅ Iniciando Budget Engine..."
echo "   Acesse: http://localhost:8501"
echo ""
echo "   Para parar: Ctrl+C"
echo ""

cd budget_engine
streamlit run app.py
