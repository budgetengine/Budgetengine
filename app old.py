"""
Budget Engine - Motor de Orçamento
Aplicação principal Streamlit - Multi-Cliente/Multi-Filial
"""

import streamlit as st
import pandas as pd
import json
import copy
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import shutil
from datetime import datetime

# Importações locais
from config import *
# import database as db  # Substituído por cliente_manager
from modules.excel_parser import BudgetExcelParser, importar_budget

# ============================================
# SISTEMA DE AUTENTICAÇÃO
# ============================================
try:
    from auth import (
        is_authenticated, 
        login, 
        logout, 
        get_current_user,
        show_login_form,
        show_user_menu
    )
    from admin_users import pagina_admin
    AUTH_ENABLED = True
except ImportError:
    AUTH_ENABLED = False
    # Funções dummy se auth não estiver disponível
    def is_authenticated(): return True
    def get_current_user(): return None
    def show_user_menu(): pass
    def pagina_admin(): 
        st.warning("Módulo de administração não disponível")
from motor_calculo import MotorCalculo, criar_motor_padrao, criar_motor_vazio, Investimento, FinanciamentoExistente, Servico, Fisioterapeuta, FuncionarioCLT, DespesaFixa, Profissional
from modules.cliente_manager import ClienteManager, motor_para_dict, dict_para_motor
from realizado_manager import RealizadoManager, LancamentoMesRealizado, RealizadoAnual, AnaliseVariacao, criar_dre_comparativo
import traceback
import os

# ============================================
# SISTEMA DE LOG DE ERROS E CÓDIGOS
# ============================================

# Códigos de Erro Padronizados
CODIGOS_ERRO = {
    # Motor e Cálculos (BE-1XX)
    "BE-100": "Motor não inicializado",
    "BE-101": "Erro ao calcular DRE",
    "BE-102": "Erro ao calcular indicadores",
    "BE-103": "Erro ao calcular TDABC",
    "BE-104": "Erro ao calcular ocupação",
    "BE-105": "Erro ao calcular Simples Nacional",
    "BE-106": "Erro ao calcular Carnê Leão",
    "BE-107": "Erro ao calcular folha CLT",
    "BE-108": "Erro ao calcular fluxo de caixa",
    "BE-109": "Divisão por zero em cálculo",
    
    # Clientes e Filiais (BE-2XX)
    "BE-200": "Cliente não encontrado",
    "BE-201": "Filial não encontrada",
    "BE-202": "Erro ao criar cliente",
    "BE-203": "Erro ao criar filial",
    "BE-204": "Erro ao editar cliente",
    "BE-205": "Erro ao editar filial",
    "BE-206": "Erro ao excluir cliente",
    "BE-207": "Erro ao excluir filial",
    "BE-208": "Erro ao carregar cliente",
    "BE-209": "Erro ao carregar filial",
    
    # Persistência (BE-3XX)
    "BE-300": "Erro ao salvar dados",
    "BE-301": "Erro ao carregar dados",
    "BE-302": "Arquivo não encontrado",
    "BE-303": "JSON inválido",
    "BE-304": "Erro de serialização",
    "BE-305": "Erro de deserialização",
    "BE-306": "Diretório não existe",
    "BE-307": "Permissão negada",
    
    # Premissas (BE-4XX)
    "BE-400": "Premissas macro não configuradas",
    "BE-401": "Premissas operacionais não configuradas",
    "BE-402": "Premissas de pagamento não configuradas",
    "BE-403": "Premissas de folha não configuradas",
    "BE-404": "Salas não configuradas",
    "BE-405": "Serviços não cadastrados",
    "BE-406": "Fisioterapeutas não cadastrados",
    
    # Interface (BE-5XX)
    "BE-500": "Erro ao renderizar página",
    "BE-501": "Componente não encontrado",
    "BE-502": "Session state corrompido",
    "BE-503": "Erro de validação de formulário",
    
    # Importação/Exportação (BE-6XX)
    "BE-600": "Erro ao importar Excel",
    "BE-601": "Erro ao exportar Excel",
    "BE-602": "Formato de arquivo inválido",
    "BE-603": "Dados incompletos no arquivo",
}

# Changelog do Sistema
CHANGELOG = [
    {
        "versao": "1.86.2",
        "data": "2024-12-26",
        "tipo": "feature",
        "descricao": "Aprovação de Cenários e Consolidado Comparativo",
        "detalhes": [
            "NOVO: Botão 'Aprovar Cenário' com proteção por senha",
            "NOVO: Badge visual indicando cenário aprovado em cada filial",
            "NOVO: Consolidado mostra 3 colunas (Pessimista, Conservador, Otimista)",
            "NOVO: Total Aprovado = soma dos cenários aprovados de cada filial",
            "NOVO: Tabela detalhada por filial com destaque do aprovado",
            "Cards de cenário agora destacam visualmente o aprovado"
        ]
    },
    {
        "versao": "1.85.3",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Correção Consolidação de Filiais",
        "detalhes": [
            "BUG FIX: Valores mudavam ao trocar de Filial para Consolidado",
            "Campos de Serviços faltando: pct_reajuste, mes_reajuste, sessoes_mes_base",
            "Campos de Despesas faltando: tipo_despesa, pct_receita (CRÍTICO para variáveis)",
            "Premissas eram copiadas por referência (agora usa deepcopy)",
            "Sazonalidade agora é copiada corretamente",
            "PDF agora identifica se é Consolidado ou Filial na capa e cabeçalho",
            "Ano do relatório corrigido de 2025 para 2026"
        ]
    },
    {
        "versao": "1.84.0",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Relatório PDF Executivo para Clientes",
        "detalhes": [
            "NOVO: Exportação de relatório PDF profissional",
            "Capa personalizada com nome do cliente",
            "Sumário executivo com KPIs principais",
            "DRE resumido com análise automática",
            "Gráficos de evolução mensal (Receita vs Custos)",
            "Análise de composição de custos (pizza)",
            "Ponto de Equilíbrio com margem de segurança",
            "Projeção de Fluxo de Caixa resumida",
            "Numeração de páginas e rodapé profissional",
            "Dropdown unificado para escolher Excel ou PDF"
        ]
    },
    {
        "versao": "1.83.7",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Calculadora R$/Sessão - Mensal ou Anual",
        "detalhes": [
            "Calculadora agora permite escolher se valor é MENSAL ou ANUAL",
            "Corrigido: Usuário informava aluguel mensal mas era tratado como anual",
            "Adicionada verificação do custo mensal projetado",
            "Melhorado feedback visual com cálculo detalhado",
            "Calculadora de % Receita também suporta mensal/anual"
        ]
    },
    {
        "versao": "1.83.6",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "DRE Dinâmico - Despesas Fixas e Variáveis",
        "detalhes": [
            "Corrigido: Despesa aparecia duplicada (CV e CF) quando tipo alterado",
            "DRE agora mostra despesas FIXAS dinamicamente",
            "DRE agora mostra despesas VARIÁVEIS dinamicamente",
            "Removida lista hardcoded de despesas operacionais",
            "Despesa marcada como variável aparece APENAS em Custos Variáveis",
            "Despesa marcada como fixa aparece APENAS em Despesas Operacionais"
        ]
    },
    {
        "versao": "1.83.5",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Remoção de Hardcode de Materiais 4%",
        "detalhes": [
            "Removido: Hardcode de 4% para 'Materiais' na DRE",
            "Custos Variáveis agora vêm APENAS de despesas cadastradas pelo usuário",
            "Se não há despesas variáveis, Total CV = R$ 0",
            "DRE mostra dinamicamente todas as despesas variáveis cadastradas",
            "TDABC e Fluxo de Caixa usam Total Custos Variáveis",
            "Interface atualizada para custos variáveis dinâmicos"
        ]
    },
    {
        "versao": "1.83.4",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Despesas Variáveis na DRE",
        "detalhes": [
            "Corrigido: Despesas variáveis não sensibilizavam a DRE",
            "calcular_custos_variaveis() agora inclui despesas tipo 'variavel'",
            "Suporta % Receita e R$/Sessão conforme cadastro do usuário",
            "calcular_despesas_fixas() agora EXCLUI variáveis (evita duplicação)",
            "DRE mostra detalhamento de cada despesa variável",
            "Serialização atualizada para salvar/carregar campos variáveis",
            "Consolidação de filiais preserva configurações variáveis"
        ]
    },
    {
        "versao": "1.83.3",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Auditoria Profunda de Vínculos",
        "detalhes": [
            "Corrigido: Dashboard profissionais usava valor_2026 direto (linha 1912)",
            "Corrigido: receita_preview não considerava reajuste (linha 8279)",
            "Auditoria completa: 9 cadeias de cálculo verificadas",
            "Verificados: DRE, TDABC, PE, Simples Nacional, Folha, Ticket Médio",
            "Confirmado: 50+ locais de cálculo estão consistentes",
            "Confirmado: Serialização valores_profissional/proprietario correta"
        ]
    },
    {
        "versao": "1.83.2",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Calculadora de Despesas Variáveis",
        "detalhes": [
            "Nova calculadora para descobrir R$/Sessão ou % Receita",
            "R$/Sessão: Informe custo anual → divide por sessões cadastradas",
            "% Receita: Informe custo + receita do ano anterior → calcula %",
            "Mostra total de sessões cadastradas automaticamente",
            "Exemplo: R$ 24.000 ÷ 8.000 sessões = R$ 3,00/sessão"
        ]
    },
    {
        "versao": "1.83.1",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Interface de Despesas Variáveis Melhorada",
        "detalhes": [
            "Campo de despesas variáveis agora mostra claramente a unidade",
            "% Receita: mostra campo com '%' ao lado (ex: 2.50 %)",
            "R$/Sessão: mostra campo com '/sessão' ao lado (ex: 5.00 /sessão)",
            "Valores de % agora são inseridos como percentual (2.5 ao invés de 0.025)",
            "Tooltips explicativos adicionados aos campos"
        ]
    },
    {
        "versao": "1.83.0",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Ticket Médio no Painel de Atendimentos",
        "detalhes": [
            "Nova tabela 'Ticket Médio por Mês' para Proprietários",
            "Nova tabela 'Ticket Médio por Mês' para Profissionais",
            "Mostra evolução do valor médio por sessão ao longo do ano",
            "Evidencia impacto do reajuste no ticket médio",
            "Linha de 'Média Ano' e 'Média Geral' para comparação"
        ]
    },
    {
        "versao": "1.82.9",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Tabela Sessões/Serviço - Valor Base e Após Reajuste",
        "detalhes": [
            "Tabela agora mostra: Valor Base | Valor Mês+ (após reajuste) | Valor Unit.",
            "Ex: Valor Base R$ 322 | Valor Mar+ R$ 338,10 | Valor Unit. R$ 322 (Jan)",
            "Coluna 'Valor Mês+' indica o mês do reajuste dinamicamente"
        ]
    },
    {
        "versao": "1.82.8",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Correção Lógica de Reajuste de Valores",
        "detalhes": [
            "CORRIGIDO: Valor cadastrado agora é o valor BASE (antes do reajuste)",
            "ANTES (errado): Jan=322/1.05=306.67 | Mar+=322",
            "AGORA (correto): Jan=322 | Mar+=322×1.05=338.10",
            "Corrigido em: get_valor_servico() e calcular_valor_servico_mes()",
            "Usuário cadastra R$ 322 → espera R$ 322 em Jan e R$ 338 em Mar"
        ]
    },
    {
        "versao": "1.82.7",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Tabela Sessões/Serviço - Valores com Reajuste",
        "detalhes": [
            "Tabela 'Sessões por Serviço' agora mostra valores com reajuste",
            "Adicionado seletor de mês para visualizar valores",
            "Usa calcular_valor_servico_mes() que considera reajuste",
            "Jan/Fev: valor antes reajuste | Mar+: valor após reajuste"
        ]
    },
    {
        "versao": "1.82.6",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Auditoria Completa - Fórmulas de Crescimento",
        "detalhes": [
            "Corrigido: calcular_demanda_por_profissional_mes usava fórmula exponencial",
            "Corrigido: Dashboard profissionais usava crescimento/100 (já era decimal)",
            "Alinhado: Todas as fórmulas agora usam crescimento LINEAR da planilha",
            "Fórmula correta: sessoes = base + (base*pct)/13.1 * (mes+0.944)",
            "Verificadas 45+ funções com parâmetro 'mes'",
            "420+ chamadas ao motor auditadas"
        ]
    },
    {
        "versao": "1.82.5",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Auditoria Profunda - Mais Correções Críticas",
        "detalhes": [
            "Corrigido: get_valor_servico agora usa mes_reajuste_idx = mes_reajuste - 1",
            "Corrigido: calcular_folha_mes verificação de admissão (era mes+1, agora mes)",
            "Auditoria de 30+ funções com parâmetro 'mes'",
            "Verificado: calcular_simples_nacional_mes usa 1-12 ✓",
            "Verificado: calcular_carne_leao_mes usa 1-12 ✓",
            "Verificado: get_imposto_para_dre usa 1-12 ✓",
            "Testes de integração completos passando"
        ]
    },
    {
        "versao": "1.82.4",
        "data": "2024-12-24",
        "tipo": "fix",
        "descricao": "Correção Crítica: Consistência Cálculo Sessões",
        "detalhes": [
            "AUDITORIA PROFUNDA realizada em todas as funções",
            "Corrigido: get_sessoes_servico_mes aceitava mes 1-12, agora 0-11",
            "Corrigido: calcular_sessoes_mes agora usa fisioterapeutas primeiro",
            "Corrigido: calcular_sessoes_mes_por_tipo respeita modo_calculo",
            "Corrigido: calcular_folha_fisioterapeutas_mes converte mes 1-12 para 0-11",
            "Alinhamento entre get_sessoes, calcular_sessoes e calcular_receita",
            "Tabela 'Sessões por Serviço' agora usa valor do serviço (não repasse)"
        ]
    },
    {
        "versao": "1.82.3",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Crescimento por Profissional",
        "detalhes": [
            "Campo 'Cresc. %' por serviço em proprietários/profissionais",
            "Só aparece quando modo='profissional' e sessões > 0",
            "Permite definir meta de crescimento individual",
            "Motor já usava pct_crescimento_por_servico, agora editável"
        ]
    },
    {
        "versao": "1.82.2",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Interface Adaptativa por Modo de Sessões",
        "detalhes": [
            "Novo serviço: campos iniciam em branco (zero)",
            "Modo 'profissional': esconde sessões no cadastro de serviços",
            "Aviso informativo sobre onde definir sessões",
            "Campo de crescimento só aparece no modo correto"
        ]
    },
    {
        "versao": "1.82.1",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Validação Completa de Sessões",
        "detalhes": [
            "Nova função validar_sessoes() no motor",
            "7 tipos de validação implementados",
            "Resumo em Premissas → Operacionais",
            "Testes no Diagnóstico (categoria Validação Sessões)",
            "Alerta no Dashboard quando inconsistente",
            "Comparativo: serviços vs fisios vs capacidade"
        ]
    },
    {
        "versao": "1.82.0",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Modo de Cálculo de Sessões",
        "detalhes": [
            "Novo flag: modo_calculo_sessoes (servico/profissional)",
            "Modo 'servico': usa sessões do cadastro de serviços",
            "Modo 'profissional': soma sessões dos fisioterapeutas",
            "Toggle em Premissas → Operacionais",
            "Crescimento anual aplicado em ambos os modos",
            "Retrocompatível: padrão é 'servico'"
        ]
    },
    {
        "versao": "1.81.6",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Integração Completa de Log de Erros",
        "detalhes": [
            "registrar_erro() integrado em todos os módulos",
            "Clientes: criar, editar, excluir (BE-2XX)",
            "Filiais: criar, editar, excluir (BE-2XX)",
            "Persistência: salvar, carregar (BE-3XX)",
            "Premissas: salvar macro (BE-4XX)",
            "Importação/Exportação: Excel (BE-6XX)",
            "Interface: Consultor IA (BE-5XX)"
        ]
    },
    {
        "versao": "1.81.5",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Sistema de Log de Erros e Códigos",
        "detalhes": [
            "Códigos de erro padronizados (BE-XXX)",
            "Log de erros em arquivo (data/logs/erros.log)",
            "Changelog completo no diagnóstico",
            "Visualização de erros recentes"
        ]
    },
    {
        "versao": "1.81.4",
        "data": "2024-12-24",
        "tipo": "bugfix",
        "descricao": "Correção Editar/Excluir Filial",
        "detalhes": [
            "Editar filial salvava no lugar errado",
            "Excluir filial tratava IDs como dicionários",
            "Novo teste de arquivo de filial no diagnóstico"
        ]
    },
    {
        "versao": "1.81.3",
        "data": "2024-12-24",
        "tipo": "bugfix",
        "descricao": "Correção de Imports",
        "detalhes": [
            "Imports de motor_calculo corrigidos",
            "motor_calculo.py deve estar na raiz",
            "modules/__init__.py atualizado"
        ]
    },
    {
        "versao": "1.81.2",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Diagnóstico de Clientes/Filiais",
        "detalhes": [
            "Nova categoria 12: Clientes/Filiais",
            "Testes de ClienteManager",
            "Testes de listar/carregar clientes e filiais"
        ]
    },
    {
        "versao": "1.81.1",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Editar e Excluir Filial",
        "detalhes": [
            "Botões de editar e excluir para cada filial",
            "Confirmação antes de excluir",
            "Formulário de renomear filial"
        ]
    },
    {
        "versao": "1.81.0",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Diagnóstico Completo com Sugestões",
        "detalhes": [
            "Seção 'Problemas Encontrados e Como Resolver'",
            "Sugestões específicas por tipo de erro",
            "Correção de testes Simples Nacional e sincronizar_num_salas"
        ]
    },
    {
        "versao": "1.80.9",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Varredura Completíssima",
        "detalhes": [
            "25 testes em 11 categorias",
            "Barra de progresso",
            "Resultados agrupados por categoria"
        ]
    },
    {
        "versao": "1.80.8",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Página de Diagnóstico Completa",
        "detalhes": [
            "6 tabs de diagnóstico",
            "Tab de Testes Avançados",
            "Testes de cálculo em tempo real"
        ]
    },
    {
        "versao": "1.80.7",
        "data": "2024-12-24",
        "tipo": "bugfix",
        "descricao": "Correções de Varredura",
        "detalhes": [
            "ZeroDivisionError em max_lucro",
            "ZeroDivisionError em meses_range",
            "Função pagina_importar() criada"
        ]
    },
    {
        "versao": "1.80.6",
        "data": "2024-12-24",
        "tipo": "bugfix",
        "descricao": "Correção Cadastro de Salas",
        "detalhes": [
            "Botão Resetar Salas",
            "Correção de salas em branco",
            "ZeroDivisionError em max_lucro"
        ]
    },
    {
        "versao": "1.80.0",
        "data": "2024-12-24",
        "tipo": "feature",
        "descricao": "Módulo Realizado",
        "detalhes": [
            "Lançamento de valores realizados",
            "Comparativo Orçado x Realizado",
            "DRE Comparativo"
        ]
    },
]

def registrar_erro(codigo: str, detalhe: str = "", local: str = "") -> str:
    """
    Registra um erro no log e retorna a mensagem formatada.
    
    Args:
        codigo: Código do erro (ex: BE-205)
        detalhe: Detalhes adicionais do erro
        local: Local onde o erro ocorreu (função/linha)
    
    Returns:
        Mensagem formatada do erro
    """
    from datetime import datetime
    
    # Criar diretório de logs se não existir
    log_dir = "data/logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Preparar dados do erro
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    descricao = CODIGOS_ERRO.get(codigo, "Erro desconhecido")
    
    # Formatar mensagem
    mensagem = f"[{timestamp}] {codigo}: {descricao}"
    if local:
        mensagem += f" | Local: {local}"
    if detalhe:
        mensagem += f" | Detalhe: {detalhe}"
    
    # Salvar no arquivo de log
    log_file = os.path.join(log_dir, "erros.log")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(mensagem + "\n")
    except Exception:
        pass  # Silenciosamente ignora erro de escrita
    
    return f"{codigo}: {descricao}" + (f" - {detalhe}" if detalhe else "")

def obter_log_erros(limite: int = 50) -> list:
    """
    Obtém os últimos erros do log.
    
    Args:
        limite: Número máximo de erros a retornar
    
    Returns:
        Lista de erros (mais recentes primeiro)
    """
    log_file = "data/logs/erros.log"
    
    if not os.path.exists(log_file):
        return []
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            linhas = f.readlines()
        
        # Retornar últimas linhas (mais recentes primeiro)
        return [l.strip() for l in reversed(linhas[-limite:])]
    except Exception:
        return []

def limpar_log_erros():
    """Limpa o arquivo de log de erros."""
    log_file = "data/logs/erros.log"
    try:
        if os.path.exists(log_file):
            os.remove(log_file)
        return True
    except Exception:
        return False


# ============================================
# FUNÇÃO DE CONSOLIDAÇÃO DE FILIAIS
# ============================================

def consolidar_filiais(manager: ClienteManager, cliente_id: str, cliente_nome: str = "Cliente") -> MotorCalculo:
    """
    Consolida os dados de todas as filiais de um cliente em um único motor.
    Usa o cenário Conservador de cada filial para consolidação.
    """
    from modules.cliente_manager import carregar_motores_cenarios
    
    # Criar motor consolidado
    motor_consolidado = criar_motor_vazio(
        cliente_nome=cliente_nome,
        filial_nome="Consolidado",
        tipo_relatorio="Consolidado"
    )
    
    # Listar filiais
    filiais = manager.listar_filiais(cliente_id)
    
    if not filiais:
        return motor_consolidado
    
    # Contadores para consolidação
    servicos_consolidados = {}
    proprietarios_consolidados = {}  # ESTRUTURA ANTIGA - NECESSÁRIA!
    profissionais_consolidados = {}  # ESTRUTURA ANTIGA - NECESSÁRIA!
    fisioterapeutas_consolidados = {}
    funcionarios_consolidados = {}
    despesas_consolidadas = {}
    primeira_filial_processada = False
    
    # Iterar sobre cada filial
    for filial_info in filiais:
        filial_id = filial_info["id"]
        filial_nome_atual = filial_info["nome"]
        
        # Carregar dados da filial usando o novo sistema de cenários
        try:
            resultado = carregar_motores_cenarios(manager, cliente_id, filial_id)
            motores = resultado.get("motores", {})
            
            # Usa cenário Conservador para consolidação (ou o que estiver disponível)
            motor_filial = motores.get("Conservador") or motores.get("Pessimista") or motores.get("Otimista")
            
            if not motor_filial:
                continue
        except Exception as e:
            # Fallback para formato antigo
            dados_filial = manager.carregar_filial(cliente_id, filial_id)
            if not dados_filial:
                continue
            motor_filial = criar_motor_vazio()
            dict_para_motor(dados_filial, motor_filial)
        
        # ===== CONSOLIDAR SERVIÇOS =====
        for nome_srv, srv in motor_filial.servicos.items():
            if nome_srv not in servicos_consolidados:
                servicos_consolidados[nome_srv] = {
                    'nome': nome_srv,
                    'duracao_minutos': getattr(srv, 'duracao_minutos', 50),
                    'pacientes_por_sessao': getattr(srv, 'pacientes_por_sessao', 1),
                    'valor_2025': getattr(srv, 'valor_2025', 0),
                    'valor_2026': getattr(srv, 'valor_2026', 0),
                    'usa_sala': getattr(srv, 'usa_sala', True),
                    # NOVOS - Campos que faltavam:
                    'pct_reajuste': getattr(srv, 'pct_reajuste', 0.0),
                    'mes_reajuste': getattr(srv, 'mes_reajuste', 3),
                    'sessoes_mes_base': getattr(srv, 'sessoes_mes_base', 0),
                    'pct_crescimento': getattr(srv, 'pct_crescimento', 0.0),
                }
        
        # ===== CONSOLIDAR PROPRIETÁRIOS (ESTRUTURA ANTIGA - CRÍTICO!) =====
        for nome_prop, prop in motor_filial.proprietarios.items():
            nome_unico = f"{nome_prop} ({filial_nome_atual})"
            
            if nome_unico not in proprietarios_consolidados:
                proprietarios_consolidados[nome_unico] = {
                    'nome': nome_unico,
                    'tipo': getattr(prop, 'tipo', 'proprietario'),
                    'ativo': getattr(prop, 'ativo', True),
                    'sessoes_por_servico': dict(prop.sessoes_por_servico) if prop.sessoes_por_servico else {},
                    'pct_crescimento_por_servico': dict(prop.pct_crescimento_por_servico) if prop.pct_crescimento_por_servico else {},
                }
        
        # ===== CONSOLIDAR PROFISSIONAIS (ESTRUTURA ANTIGA - CRÍTICO!) =====
        for nome_prof, prof in motor_filial.profissionais.items():
            nome_unico = f"{nome_prof} ({filial_nome_atual})"
            
            if nome_unico not in profissionais_consolidados:
                profissionais_consolidados[nome_unico] = {
                    'nome': nome_unico,
                    'tipo': getattr(prof, 'tipo', 'profissional'),
                    'ativo': getattr(prof, 'ativo', True),
                    'sessoes_por_servico': dict(prof.sessoes_por_servico) if prof.sessoes_por_servico else {},
                    'pct_crescimento_por_servico': dict(prof.pct_crescimento_por_servico) if prof.pct_crescimento_por_servico else {},
                }
        
        # ===== CONSOLIDAR FISIOTERAPEUTAS (ESTRUTURA NOVA) =====
        for nome_fisio, fisio in motor_filial.fisioterapeutas.items():
            nome_unico = f"{nome_fisio} ({filial_nome_atual})"
            
            if nome_unico not in fisioterapeutas_consolidados:
                escala = getattr(fisio, 'escala_semanal', None)
                if escala is None:
                    escala = {"segunda": 0.0, "terca": 0.0, "quarta": 0.0, "quinta": 0.0, "sexta": 0.0, "sabado": 0.0}
                elif isinstance(escala, dict):
                    escala = dict(escala)
                else:
                    dias = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado"]
                    escala = {dias[i]: escala[i] if i < len(escala) else 0.0 for i in range(6)}
                
                fisioterapeutas_consolidados[nome_unico] = {
                    'nome': nome_unico,
                    'cargo': getattr(fisio, 'cargo', 'Fisioterapeuta'),
                    'nivel': getattr(fisio, 'nivel', 2),
                    'filial': filial_nome_atual,
                    'ativo': getattr(fisio, 'ativo', True),
                    'sessoes_por_servico': dict(fisio.sessoes_por_servico) if fisio.sessoes_por_servico else {},
                    'pct_crescimento_por_servico': dict(fisio.pct_crescimento_por_servico) if fisio.pct_crescimento_por_servico else {},
                    'tipo_remuneracao': getattr(fisio, 'tipo_remuneracao', 'percentual'),
                    'valores_fixos_por_servico': dict(fisio.valores_fixos_por_servico) if getattr(fisio, 'valores_fixos_por_servico', None) else {},
                    'pct_customizado': getattr(fisio, 'pct_customizado', 0.0),
                    'escala_semanal': escala,
                }
        
        # ===== CONSOLIDAR FUNCIONÁRIOS =====
        for nome_func, func in motor_filial.funcionarios_clt.items():
            nome_unico = f"{nome_func} ({filial_nome_atual})"
            
            if nome_unico not in funcionarios_consolidados:
                funcionarios_consolidados[nome_unico] = {
                    'nome': nome_unico,
                    'cargo': getattr(func, 'cargo', ''),
                    'salario_base': getattr(func, 'salario_base', 0),
                    'tipo_vinculo': getattr(func, 'tipo_vinculo', 'informal'),
                    'vt_dia': getattr(func, 'vt_dia', 0),
                    'vr_dia': getattr(func, 'vr_dia', 0),
                    'plano_saude': getattr(func, 'plano_saude', 0),
                    'plano_odonto': getattr(func, 'plano_odonto', 0),
                    'mes_admissao': getattr(func, 'mes_admissao', 1),
                    'ativo': getattr(func, 'ativo', True),
                }
        
        # ===== CONSOLIDAR DESPESAS FIXAS =====
        for nome_desp, desp in motor_filial.despesas_fixas.items():
            if nome_desp in despesas_consolidadas:
                # Soma valores se já existe
                despesas_consolidadas[nome_desp]['valor_mensal'] += getattr(desp, 'valor_mensal', 0)
                # Para despesas variáveis, pct_receita deve ser mantido (não somado)
            else:
                despesas_consolidadas[nome_desp] = {
                    'nome': nome_desp,
                    'valor_mensal': getattr(desp, 'valor_mensal', 0),
                    'categoria': getattr(desp, 'categoria', 'Administrativa'),
                    'tipo_reajuste': getattr(desp, 'tipo_reajuste', 'ipca'),
                    'ativa': getattr(desp, 'ativa', True),
                    # NOVOS - Campos que faltavam (CRÍTICO!):
                    'mes_reajuste': getattr(desp, 'mes_reajuste', 1),
                    'pct_adicional': getattr(desp, 'pct_adicional', 0.0),
                    'aplicar_reajuste': getattr(desp, 'aplicar_reajuste', True),
                    'tipo_sazonalidade': getattr(desp, 'tipo_sazonalidade', 'uniforme'),
                    'valores_2025': list(getattr(desp, 'valores_2025', [0.0] * 12)),
                    # CRÍTICO para despesas variáveis:
                    'tipo_despesa': getattr(desp, 'tipo_despesa', 'fixa'),
                    'pct_receita': getattr(desp, 'pct_receita', 0.0),
                    'valor_por_sessao': getattr(desp, 'valor_por_sessao', 0.0),
                    'base_variavel': getattr(desp, 'base_variavel', 'receita'),
                }
        
        # ===== COPIAR PREMISSAS (usa da primeira filial) =====
        if not primeira_filial_processada:
            # IMPORTANTE: Usar deepcopy para evitar referências compartilhadas!
            motor_consolidado.macro = copy.deepcopy(motor_filial.macro)
            motor_consolidado.pagamento = copy.deepcopy(motor_filial.pagamento)
            motor_consolidado.operacional = copy.deepcopy(motor_filial.operacional)
            motor_consolidado.premissas_simples = copy.deepcopy(motor_filial.premissas_simples)
            motor_consolidado.premissas_financeiras = copy.deepcopy(motor_filial.premissas_financeiras)
            motor_consolidado.premissas_fisio = copy.deepcopy(motor_filial.premissas_fisio)
            motor_consolidado.premissas_folha = copy.deepcopy(motor_filial.premissas_folha)
            motor_consolidado.premissas_dividendos = copy.deepcopy(motor_filial.premissas_dividendos)
            motor_consolidado.premissas_fc = copy.deepcopy(motor_filial.premissas_fc)
            motor_consolidado.sazonalidade = copy.deepcopy(motor_filial.sazonalidade)
            primeira_filial_processada = True
    
    # ===== APLICAR DADOS CONSOLIDADOS AO MOTOR =====
    
    # Serviços
    for nome, dados in servicos_consolidados.items():
        motor_consolidado.servicos[nome] = Servico(
            nome=dados['nome'],
            duracao_minutos=dados['duracao_minutos'],
            pacientes_por_sessao=dados['pacientes_por_sessao'],
            valor_2025=dados['valor_2025'],
            valor_2026=dados['valor_2026'],
            usa_sala=dados['usa_sala'],
            # Campos que faltavam:
            pct_reajuste=dados['pct_reajuste'],
            mes_reajuste=dados['mes_reajuste'],
            sessoes_mes_base=dados['sessoes_mes_base'],
            pct_crescimento=dados['pct_crescimento'],
        )
    
    # PROPRIETÁRIOS (ESTRUTURA ANTIGA - CRÍTICO PARA CÁLCULO!)
    for nome, dados in proprietarios_consolidados.items():
        motor_consolidado.proprietarios[nome] = Profissional(
            nome=dados['nome'],
            tipo=dados['tipo'],
            ativo=dados['ativo'],
            sessoes_por_servico=dados['sessoes_por_servico'],
            pct_crescimento_por_servico=dados['pct_crescimento_por_servico'],
        )
    
    # PROFISSIONAIS (ESTRUTURA ANTIGA - CRÍTICO PARA CÁLCULO!)
    for nome, dados in profissionais_consolidados.items():
        motor_consolidado.profissionais[nome] = Profissional(
            nome=dados['nome'],
            tipo=dados['tipo'],
            ativo=dados['ativo'],
            sessoes_por_servico=dados['sessoes_por_servico'],
            pct_crescimento_por_servico=dados['pct_crescimento_por_servico'],
        )
    
    # Fisioterapeutas (estrutura nova - fallback)
    for nome, dados in fisioterapeutas_consolidados.items():
        motor_consolidado.fisioterapeutas[nome] = Fisioterapeuta(
            nome=dados['nome'],
            cargo=dados['cargo'],
            nivel=dados['nivel'],
            filial=dados['filial'],
            ativo=dados['ativo'],
            sessoes_por_servico=dados['sessoes_por_servico'],
            pct_crescimento_por_servico=dados['pct_crescimento_por_servico'],
            tipo_remuneracao=dados['tipo_remuneracao'],
            valores_fixos_por_servico=dados['valores_fixos_por_servico'],
            pct_customizado=dados['pct_customizado'],
            escala_semanal=dados['escala_semanal'],
        )
    
    # Funcionários
    for nome, dados in funcionarios_consolidados.items():
        motor_consolidado.funcionarios_clt[nome] = FuncionarioCLT(
            nome=dados['nome'],
            cargo=dados['cargo'],
            salario_base=dados['salario_base'],
            tipo_vinculo=dados['tipo_vinculo'],
            vt_dia=dados['vt_dia'],
            vr_dia=dados['vr_dia'],
            plano_saude=dados['plano_saude'],
            plano_odonto=dados['plano_odonto'],
            mes_admissao=dados['mes_admissao'],
            ativo=dados['ativo'],
        )
    
    # Despesas Fixas
    for nome, dados in despesas_consolidadas.items():
        motor_consolidado.despesas_fixas[nome] = DespesaFixa(
            nome=dados['nome'],
            valor_mensal=dados['valor_mensal'],
            categoria=dados['categoria'],
            tipo_reajuste=dados['tipo_reajuste'],
            ativa=dados['ativa'],
            # Campos que faltavam:
            mes_reajuste=dados['mes_reajuste'],
            pct_adicional=dados['pct_adicional'],
            aplicar_reajuste=dados['aplicar_reajuste'],
            tipo_sazonalidade=dados['tipo_sazonalidade'],
            valores_2025=dados['valores_2025'],
            # CRÍTICO para despesas variáveis:
            tipo_despesa=dados['tipo_despesa'],
            pct_receita=dados['pct_receita'],
            valor_por_sessao=dados['valor_por_sessao'],
            base_variavel=dados['base_variavel'],
        )
    
    # Atualizar premissas operacionais com totais
    motor_consolidado.operacional.num_fisioterapeutas = len(fisioterapeutas_consolidados) + len(proprietarios_consolidados) + len(profissionais_consolidados)
    
    return motor_consolidado

# ============================================
# FUNÇÃO DE TELA DE LOGIN PERSONALIZADA
# ============================================

def mostrar_tela_login():
    """Exibe tela de login personalizada do Budget Engine"""
    
    # Configuração mínima da página para login
    st.set_page_config(
        page_title="Budget Engine - Login",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # CSS para tela de login
    st.markdown("""
    <style>
        /* Oculta sidebar no login */
        [data-testid="stSidebar"] {display: none;}
        
        /* Estilo do container de login */
        .login-box {
            background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
            padding: 2rem;
            border-radius: 16px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .login-box h1 {
            margin: 0;
            font-size: 2rem;
        }
        
        .login-box p {
            opacity: 0.9;
            margin-top: 0.5rem;
        }
        
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)
    
    # Layout centralizado
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Header
        st.markdown("""
        <div class="login-box">
            <h1>📊 Budget Engine</h1>
            <p>Sistema de Orçamento para Clínicas de Fisioterapia</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Formulário de login
        st.markdown("### 🔐 Acesse sua conta")
        
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("👤 Login", placeholder="seu.usuario")
            senha = st.text_input("🔒 Senha", type="password", placeholder="Sua senha")
            
            col_btn1, col_btn2 = st.columns([2, 1])
            with col_btn1:
                submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")
            with col_btn2:
                st.form_submit_button("Esqueci", use_container_width=True, disabled=True)
            
            if submitted:
                if not email or not senha:
                    st.error("⚠️ Preencha login e senha!")
                else:
                    with st.spinner("Verificando credenciais..."):
                        user = login(email, senha)
                        
                        if user:
                            st.session_state["user"] = user
                            st.session_state["authenticated"] = True
                            st.session_state["company_id"] = user.get("company_id")
                            st.session_state["user_id"] = user.get("id")
                            st.success(f"✅ Bem-vindo, {user.get('name', 'Usuário')}!")
                            st.rerun()
                        else:
                            st.error("❌ Login ou senha incorretos!")
        
        # Footer
        st.markdown("---")
        st.caption("Budget Engine © 2024 - Sistema de Consultoria Financeira")

# ============================================
# VERIFICAÇÃO DE AUTENTICAÇÃO
# ============================================

# Se autenticação está habilitada, verifica login
if AUTH_ENABLED and not is_authenticated():
    mostrar_tela_login()
    st.stop()

# ============================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CSS CUSTOMIZADO
# ============================================

st.markdown("""
<style>
    /* Fonte principal */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    
    /* Header principal */
    .main-header {
        background: linear-gradient(135deg, #1a365d 0%, #2c5282 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        color: white;
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    
    .main-header p {
        margin: 0.3rem 0 0 0;
        opacity: 0.85;
        font-size: 0.95rem;
    }
    
    /* Cards de métricas */
    .metric-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #2c5282;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.12);
    }
    
    .metric-card.success { border-left-color: #38a169; }
    .metric-card.warning { border-left-color: #d69e2e; }
    .metric-card.danger { border-left-color: #c53030; }
    
    .metric-label {
        font-size: 0.85rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a202c;
        font-family: 'JetBrains Mono', monospace;
    }
    
    .metric-delta {
        font-size: 0.9rem;
        margin-top: 0.3rem;
    }
    
    .metric-delta.positive { color: #38a169; }
    .metric-delta.negative { color: #c53030; }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f7fafc 0%, #edf2f7 100%);
    }
    
    [data-testid="stSidebar"] .stSelectbox label {
        font-weight: 600;
        color: #2d3748;
    }
    
    /* Tabelas */
    .dataframe {
        font-size: 0.9rem !important;
    }
    
    /* Botões */
    .stButton > button {
        background: linear-gradient(135deg, #2c5282 0%, #1a365d 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(44, 82, 130, 0.3);
    }
    
    /* Cards de cliente */
    .client-card {
        background: white;
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
    }
    
    .client-card h4 {
        margin: 0 0 0.5rem 0;
        color: #1a365d;
    }
    
    .client-card p {
        margin: 0;
        color: #718096;
        font-size: 0.9rem;
    }
    
    /* Seção */
    .section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e2e8f0;
    }
    
    .section-header h3 {
        margin: 0;
        color: #2d3748;
        font-size: 1.1rem;
    }
    
    /* Status badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    
    .badge-success { background: #c6f6d5; color: #22543d; }
    .badge-warning { background: #fefcbf; color: #744210; }
    .badge-info { background: #bee3f8; color: #2a4365; }
    
    /* Oculta elementos padrão do Streamlit (exceto header para manter sidebar toggle) */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============================================
# ESTADO DA SESSÃO - MULTI-CLIENTE
# ============================================

# Gerenciador de clientes
if 'cliente_manager' not in st.session_state:
    st.session_state.cliente_manager = ClienteManager()

# ============================================
# FUNÇÕES DE PERSISTÊNCIA (ANTES DA INICIALIZAÇÃO)
# ============================================

ULTIMA_SELECAO_PATH = "data/ultima_selecao.json"

def _carregar_ultima_selecao():
    """Carrega a última seleção de cliente/filial"""
    import os
    if os.path.exists(ULTIMA_SELECAO_PATH):
        try:
            with open(ULTIMA_SELECAO_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None

# Cliente e Filial selecionados - COM RESTAURAÇÃO AUTOMÁTICA
if 'cliente_id' not in st.session_state:
    # Tenta restaurar última seleção
    ultima = _carregar_ultima_selecao()
    if ultima and ultima.get("cliente_id"):
        st.session_state.cliente_id = ultima["cliente_id"]
        st.session_state.filial_id = ultima.get("filial_id")
        # Carrega dados do cliente
        st.session_state.cliente_atual = st.session_state.cliente_manager.carregar_cliente(ultima["cliente_id"])
    else:
        st.session_state.cliente_id = None
        st.session_state.filial_id = None
        st.session_state.cliente_atual = None
else:
    # Já tem sessão, só garante que filial_id existe
    if 'filial_id' not in st.session_state:
        st.session_state.filial_id = None
    if 'cliente_atual' not in st.session_state:
        st.session_state.cliente_atual = None

# Dados legados (manter compatibilidade)
if 'cliente_selecionado' not in st.session_state:
    st.session_state.cliente_selecionado = None
if 'projeto_selecionado' not in st.session_state:
    st.session_state.projeto_selecionado = None
if 'dados_importados' not in st.session_state:
    st.session_state.dados_importados = None
if 'pagina' not in st.session_state:
    st.session_state.pagina = "Dashboard"

# Motor - CARREGA DADOS SE CLIENTE/FILIAL SELECIONADOS
# Agora com suporte a 3 motores (um por cenário)
if 'motor' not in st.session_state:
    if st.session_state.cliente_id and st.session_state.filial_id and st.session_state.filial_id != "consolidado":
        # Importa função de carregamento com cenários
        from modules.cliente_manager import carregar_motores_cenarios
        
        # Carrega os 3 motores (com migração automática se necessário)
        resultado = carregar_motores_cenarios(
            st.session_state.cliente_manager,
            st.session_state.cliente_id,
            st.session_state.filial_id
        )
        
        # Armazena os 3 motores
        st.session_state.motores_cenarios = resultado["motores"]
        st.session_state.usar_cenarios = resultado.get("usar_cenarios", True)
        st.session_state.cenario_aprovado = resultado.get("cenario_aprovado", None)
        
        # Define cenário ativo (para visualização)
        cenario_ativo = resultado.get("cenario_ativo", "Conservador")
        if 'cenario_ativo' not in st.session_state:
            st.session_state.cenario_ativo = cenario_ativo
        
        # Define cenário de edição (para Premissas)
        if 'cenario_edicao' not in st.session_state:
            st.session_state.cenario_edicao = "Conservador"
        
        # Motor ativo = motor do cenário ativo
        st.session_state.motor = st.session_state.motores_cenarios[st.session_state.cenario_ativo]
        
        # Se foi migrado, salva no novo formato
        if resultado.get("_migrado", False):
            from modules.cliente_manager import salvar_motores_cenarios
            salvar_motores_cenarios(
                st.session_state.cliente_manager,
                st.session_state.cliente_id,
                st.session_state.filial_id,
                st.session_state.motores_cenarios,
                st.session_state.cenario_ativo,
                st.session_state.usar_cenarios,
                st.session_state.cenario_aprovado
            )
    else:
        st.session_state.motor = criar_motor_vazio()
        st.session_state.motores_cenarios = {
            "Conservador": st.session_state.motor,
            "Pessimista": criar_motor_vazio(),
            "Otimista": criar_motor_vazio()
        }
        st.session_state.cenario_ativo = "Conservador"
        st.session_state.cenario_edicao = "Conservador"
        st.session_state.usar_cenarios = True
        st.session_state.cenario_aprovado = None

# Garante que motores_cenarios existe
if 'motores_cenarios' not in st.session_state:
    st.session_state.motores_cenarios = {
        "Conservador": st.session_state.motor,
        "Pessimista": criar_motor_vazio(),
        "Otimista": criar_motor_vazio()
    }
if 'cenario_edicao' not in st.session_state:
    st.session_state.cenario_edicao = "Conservador"

# ============================================
# FUNÇÕES DE PERSISTÊNCIA (COMPLETAS)
# ============================================

def salvar_ultima_selecao():
    """Salva a última seleção de cliente/filial para restaurar ao reabrir"""
    import os
    os.makedirs(os.path.dirname(ULTIMA_SELECAO_PATH), exist_ok=True)
    dados = {
        "cliente_id": st.session_state.cliente_id,
        "filial_id": st.session_state.filial_id
    }
    try:
        with open(ULTIMA_SELECAO_PATH, 'w', encoding='utf-8') as f:
            json.dump(dados, f)
    except Exception as e:
        registrar_erro("BE-300", str(e), "salvar_ultima_selecao")  # Log silencioso

def carregar_ultima_selecao():
    """Carrega a última seleção de cliente/filial"""
    import os
    if os.path.exists(ULTIMA_SELECAO_PATH):
        try:
            with open(ULTIMA_SELECAO_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return None

def salvar_filial_atual():
    """Salva os dados da filial atual no banco de dados (3 motores)"""
    cliente_id = st.session_state.get('cliente_id')
    filial_id = st.session_state.get('filial_id')
    
    # Debug: verificar condições
    if not cliente_id:
        st.warning("⚠️ Debug: cliente_id não definido")
        return False
    if not filial_id:
        st.warning("⚠️ Debug: filial_id não definido")
        return False
    if filial_id == "consolidado":
        st.info("ℹ️ Modo Consolidado não permite salvamento")
        return False
    
    try:
        from modules.cliente_manager import salvar_motores_cenarios
        
        manager = st.session_state.cliente_manager
        
        # Garante que o motor ativo está sincronizado
        cenario_ativo = st.session_state.get('cenario_ativo', 'Conservador')
        st.session_state.motores_cenarios[cenario_ativo] = st.session_state.motor
        
        # Pega usar_cenarios do motor ativo
        usar_cenarios = getattr(st.session_state.motor, 'usar_cenarios', True)
        cenario_aprovado = st.session_state.get('cenario_aprovado', None)
        
        # Salva os 3 motores no novo formato
        salvar_motores_cenarios(
            manager,
            cliente_id,
            filial_id,
            st.session_state.motores_cenarios,
            cenario_ativo,
            usar_cenarios,
            cenario_aprovado
        )
        
        # Também salva qual cliente/filial está selecionado
        salvar_ultima_selecao()
        
        return True
    except Exception as e:
        erro_msg = registrar_erro("BE-300", str(e), "salvar_filial_atual")
        st.error(f"❌ {erro_msg}")
        import traceback
        st.code(traceback.format_exc())
        return False

# ============================================
# SIDEBAR E NAVEGAÇÃO (DEVE VIR PRIMEIRO!)
# ============================================

# Inicializa página anterior para detectar mudança
if 'pagina_anterior' not in st.session_state:
    st.session_state.pagina_anterior = None

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/combo-chart.png", width=60)
    st.title(APP_NAME)
    st.caption(f"v{APP_VERSION}")
    
    # ========== USUÁRIO LOGADO ==========
    if AUTH_ENABLED and is_authenticated():
        user = get_current_user()
        if user:
            st.markdown("---")
            st.markdown(f"👤 **{user.get('name', 'Usuário')}**")
            company = user.get("companies", {})
            if company:
                st.caption(f"🏢 {company.get('name', 'Empresa')}")
            
            if st.button("🚪 Sair", use_container_width=True):
                logout()
                st.rerun()
    # ====================================
    
    st.markdown("---")
    
    # Menu de navegação com ícones
    # Verifica se cenários está habilitado para esta filial
    motor = st.session_state.get('motor')
    usar_cenarios = getattr(motor, 'usar_cenarios', True) if motor else True
    
    # Define opções base
    opcoes_menu = []
    
    # Só adiciona Cenários se estiver habilitado
    if usar_cenarios:
        opcoes_menu.append("🎯 Cenários")
    
    opcoes_menu.extend([
        "🏠 Dashboard",
        "🤖 Consultor IA",
        "⚙️ Premissas", 
        "📈 Atendimentos", 
        "👔 Folha Funcionários", 
        "🏥 Folha Fisioterapeutas", 
        "💼 Simples Nacional", 
        "💰 Financeiro", 
        "📊 Dividendos",
        "📋 DRE Simulado", 
        "🏦 FC Simulado", 
        "📊 Taxa Ocupação",
        "⚖️ Ponto Equilíbrio",
        "🎯 Custeio ABC",
        "───────────────",  # Separador visual
        "✅ Lançar Realizado",
        "📊 Orçado x Realizado",
        "📋 DRE Comparativo",
        "───────────────",  # Separador visual
        "👥 Clientes", 
        "📥 Importar Dados", 
        "📄 DRE (Excel)", 
        "📄 FC (Excel)",
    ])
    
    # Adiciona opções de Admin apenas para administradores
    user_logado = get_current_user() if AUTH_ENABLED else None
    is_admin_user = user_logado and user_logado.get("role") == "admin" if user_logado else True
    
    if is_admin_user:
        opcoes_menu.extend([
            "───────────────",  # Separador visual
            "🔧 Admin",
            "🛠️ Diagnóstico Dev"
        ])
    
    pagina = st.radio(
        "Navegação",
        opcoes_menu,
        label_visibility="collapsed"
    )
    
    # AUTO-SAVE: Salva automaticamente ao mudar de página
    if st.session_state.pagina_anterior and st.session_state.pagina_anterior != pagina:
        if salvar_filial_atual():
            pass  # Salvamento silencioso
    st.session_state.pagina_anterior = pagina
    
    st.markdown("---")
    
    # Info do cliente/filial selecionado
    if st.session_state.cliente_atual:
        st.markdown("**👤 Cliente:**")
        st.info(st.session_state.cliente_atual.nome)
        
        if st.session_state.filial_id:
            if st.session_state.filial_id == "consolidado":
                st.markdown("**🏢 Visão:**")
                st.success("📊 Consolidado")
            else:
                filiais = st.session_state.cliente_manager.listar_filiais(st.session_state.cliente_id)
                filial_nome = next((f["nome"] for f in filiais if f["id"] == st.session_state.filial_id), st.session_state.filial_id)
                st.markdown("**🏢 Filial:**")
                st.success(filial_nome)
        
        st.markdown("---")
        
        # Botão de salvar com feedback melhorado
        if st.session_state.filial_id and st.session_state.filial_id != "consolidado":
            if st.button("💾 SALVAR DADOS", use_container_width=True, key="btn_salvar_sidebar", type="primary"):
                try:
                    salvar_filial_atual()
                    st.success("✅ Dados salvos com sucesso!")
                    st.balloons()
                except Exception as e:
                    erro_msg = registrar_erro("BE-300", str(e), "sidebar/btn_salvar")
                    st.error(f"❌ {erro_msg}")
            st.caption("⚠️ Clique SALVAR antes de fechar!")
            st.caption("🔄 Auto-save ao trocar página/filial")
        elif st.session_state.cliente_id:
            st.warning("⚠️ Selecione uma filial para salvar")
        else:
            st.info("ℹ️ Crie ou selecione um cliente")
    
    st.markdown("---")
    st.caption("© 2024 Budget Engine")
    st.caption("Desenvolvido para Consultoria")

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def render_metric_card(label, value, delta=None, card_type="default"):
    """Renderiza um card de métrica"""
    delta_html = ""
    if delta:
        delta_class = "positive" if delta.startswith("+") or delta.startswith("↑") else "negative"
        delta_html = f'<div class="metric-delta {delta_class}">{delta}</div>'
    
    st.markdown(f"""
        <div class="metric-card {card_type}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)

def render_header():
    """Renderiza o header principal"""
    st.markdown(f"""
        <div class="main-header">
            <h1>📊 {APP_NAME}</h1>
            <p>{APP_SUBTITLE} • v{APP_VERSION}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Só mostra o cenário se estiver habilitado para esta filial
    if hasattr(st.session_state, 'motor') and st.session_state.motor is not None:
        motor = st.session_state.motor
        usar_cenarios = getattr(motor, 'usar_cenarios', True)
        
        # Só mostra badge se cenários estiver habilitado
        if usar_cenarios:
            cenario_oficial = getattr(motor, 'cenario_oficial', 'Conservador')
            
            # Inicializa cenario_ativo se não existir
            if 'cenario_ativo' not in st.session_state:
                st.session_state.cenario_ativo = cenario_oficial
            
            cenario_nome = st.session_state.cenario_ativo
            
            # Cores e ícones por cenário
            config_cenario = {
                "Conservador": {"cor": "#ffc107", "icone": "⚠️", "bg": "#ffc10722"},
                "Pessimista": {"cor": "#dc3545", "icone": "📉", "bg": "#dc354522"},
                "Otimista": {"cor": "#28a745", "icone": "🚀", "bg": "#28a74522"}
            }
            
            cfg = config_cenario.get(cenario_nome, config_cenario["Conservador"])
            marca_oficial = " ⭐" if cenario_nome == cenario_oficial else ""
            
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, {cfg['bg']}, transparent);
                border-left: 4px solid {cfg['cor']};
                padding: 10px 15px;
                border-radius: 4px;
                margin: 10px 0;
            ">
                <span style="font-size: 20px; margin-right: 10px;">{cfg['icone']}</span>
                <span style="font-size: 16px; font-weight: bold; color: {cfg['cor']};">
                    CENÁRIO: {cenario_nome.upper()}{marca_oficial}
                </span>
            </div>
            """, unsafe_allow_html=True)
            
            # Aplica o cenário ao motor (garante sincronização)
            motor.aplicar_cenario(cenario_nome)


def render_cenario_badge():
    """Renderiza o badge do cenário ativo - chamar APÓS seletor de cenário"""
    if hasattr(st.session_state, 'motor') and st.session_state.motor is not None:
        motor = st.session_state.motor
        cenario_nome = motor.cenario.nome if hasattr(motor, 'cenario') else "Conservador"
        cenario_oficial = getattr(motor, 'cenario_oficial', 'Conservador')
        
        # Cores e ícones por cenário
        config_cenario = {
            "Conservador": {"cor": "#ffc107", "icone": "⚠️", "bg": "#ffc10722"},
            "Pessimista": {"cor": "#dc3545", "icone": "📉", "bg": "#dc354522"},
            "Otimista": {"cor": "#28a745", "icone": "🚀", "bg": "#28a74522"}
        }
        
        cfg = config_cenario.get(cenario_nome, config_cenario["Conservador"])
        
        # Marca se é o oficial
        marca_oficial = " ⭐" if cenario_nome == cenario_oficial else ""
        
        st.markdown(f"""
        <div style="
            background: linear-gradient(90deg, {cfg['bg']}, transparent);
            border-left: 4px solid {cfg['cor']};
            padding: 8px 15px;
            border-radius: 4px;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        ">
            <span style="font-size: 18px;">{cfg['icone']}</span>
            <span style="font-weight: bold; color: {cfg['cor']};">
                Cenário: {cenario_nome}{marca_oficial}
            </span>
        </div>
        """, unsafe_allow_html=True)


def render_seletor_cliente_filial():
    """Renderiza seletor de cliente e filial no topo"""
    manager = st.session_state.cliente_manager
    
    # Container para o seletor
    with st.container():
        col1, col2, col3, col4 = st.columns([3, 3, 1, 1])
        
        # Lista de clientes - FILTRA POR EMPRESA DO USUÁRIO
        todos_clientes = manager.listar_clientes()
        
        # Verificar se deve filtrar
        user = get_current_user() if AUTH_ENABLED else None
        is_admin = user and user.get("role") == "admin" if user else True
        
        if is_admin:
            # Admin vê todos os clientes
            clientes = todos_clientes
        else:
            # Usuário comum vê apenas clientes da sua empresa
            empresa_nome = user.get("companies", {}).get("name", "") if user else ""
            
            # CORREÇÃO: Busca mais flexível
            clientes = []
            for c in todos_clientes:
                nome_cliente = c["nome"].lower().replace(" ", "").replace("_", "")
                nome_empresa = empresa_nome.lower().replace(" ", "").replace("_", "")
                if nome_cliente == nome_empresa or nome_empresa in nome_cliente or nome_cliente in nome_empresa:
                    clientes.append(c)
            
            # AUTO-SELEÇÃO: Se só tem 1 cliente, seleciona automaticamente
            if len(clientes) == 1 and not st.session_state.cliente_id:
                st.session_state.cliente_id = clientes[0]["id"]
                st.session_state.cliente_atual = manager.carregar_cliente(clientes[0]["id"])
        
        opcoes_clientes = ["Selecione um cliente..."] + [c["nome"] for c in clientes]
        ids_clientes = [None] + [c["id"] for c in clientes]
        
        with col1:
            # Encontra índice atual
            idx_cliente = 0
            if st.session_state.cliente_id:
                try:
                    idx_cliente = ids_clientes.index(st.session_state.cliente_id)
                except ValueError:
                    idx_cliente = 0
            
            cliente_nome = st.selectbox(
                "👤 Cliente",
                opcoes_clientes,
                index=idx_cliente,
                key="sel_cliente"
            )
            
            # Atualiza cliente selecionado
            if cliente_nome != "Selecione um cliente...":
                idx = opcoes_clientes.index(cliente_nome)
                novo_cliente_id = ids_clientes[idx]
                
                if novo_cliente_id != st.session_state.cliente_id:
                    # AUTO-SAVE: Salva dados da filial atual antes de trocar de cliente
                    salvar_filial_atual()
                    
                    st.session_state.cliente_id = novo_cliente_id
                    st.session_state.cliente_atual = manager.carregar_cliente(novo_cliente_id)
                    st.session_state.filial_id = None  # Reset filial
                    
                    # RESET: Limpa cache de premissas para carregar novos valores
                    for key in ['sn_limite_fator_r', 'sn_faturamento_pf_anual', 'sn_aliquota_inss_pf']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    st.session_state.motor = criar_motor_vazio(
                        cliente_nome=cliente_nome,
                        filial_nome="Selecione uma filial",
                        tipo_relatorio="Filial"
                    )
                    st.rerun()
            else:
                if st.session_state.cliente_id is not None:
                    st.session_state.cliente_id = None
                    st.session_state.cliente_atual = None
                    st.session_state.filial_id = None
                    st.session_state.motor = criar_motor_vazio()
        
        with col2:
            # Lista de filiais do cliente
            if st.session_state.cliente_id:
                filiais = manager.listar_filiais(st.session_state.cliente_id)
                opcoes_filiais = ["📊 Consolidado"] + [f["nome"] for f in filiais]
                ids_filiais = ["consolidado"] + [f["id"] for f in filiais]
                
                # Encontra índice atual
                idx_filial = 0
                if st.session_state.filial_id:
                    try:
                        idx_filial = ids_filiais.index(st.session_state.filial_id)
                    except ValueError:
                        idx_filial = 0
                
                filial_nome = st.selectbox(
                    "🏢 Filial",
                    opcoes_filiais,
                    index=idx_filial,
                    key="sel_filial"
                )
                
                # Atualiza filial selecionada
                idx = opcoes_filiais.index(filial_nome)
                novo_filial_id = ids_filiais[idx]
                
                if novo_filial_id != st.session_state.filial_id:
                    # AUTO-SAVE: Salva dados da filial atual antes de trocar
                    salvar_filial_atual()
                    
                    st.session_state.filial_id = novo_filial_id
                    
                    # RESET: Limpa cache de premissas para carregar novos valores
                    for key in ['sn_limite_fator_r', 'sn_faturamento_pf_anual', 'sn_aliquota_inss_pf']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # Pegar nome do cliente (é um dataclass, não dict)
                    cliente_nome_atual = st.session_state.cliente_atual.nome if st.session_state.cliente_atual else 'Cliente'
                    
                    # Carrega motor da filial ou consolida para modo consolidado
                    if novo_filial_id == "consolidado":
                        # Consolida dados de TODAS as filiais
                        st.session_state.motor = consolidar_filiais(
                            manager=manager,
                            cliente_id=st.session_state.cliente_id,
                            cliente_nome=cliente_nome_atual
                        )
                        # Para consolidado, não usa cenários
                        st.session_state.motores_cenarios = {
                            "Conservador": st.session_state.motor,
                            "Pessimista": st.session_state.motor,
                            "Otimista": st.session_state.motor
                        }
                    else:
                        # Usa novo sistema de carregamento com 3 cenários
                        from modules.cliente_manager import carregar_motores_cenarios
                        
                        resultado = carregar_motores_cenarios(
                            manager,
                            st.session_state.cliente_id,
                            novo_filial_id
                        )
                        
                        # Armazena os 3 motores
                        st.session_state.motores_cenarios = resultado["motores"]
                        st.session_state.usar_cenarios = resultado.get("usar_cenarios", True)
                        
                        # Define cenário ativo
                        cenario_ativo = resultado.get("cenario_ativo", "Conservador")
                        st.session_state.cenario_ativo = cenario_ativo
                        st.session_state.cenario_edicao = "Conservador"
                        
                        # Motor ativo = motor do cenário ativo
                        st.session_state.motor = st.session_state.motores_cenarios[cenario_ativo]
                        st.session_state.cenario_aprovado = resultado.get("cenario_aprovado", None)
                        
                        # Se foi migrado, salva no novo formato
                        if resultado.get("_migrado", False):
                            from modules.cliente_manager import salvar_motores_cenarios
                            salvar_motores_cenarios(
                                manager,
                                st.session_state.cliente_id,
                                novo_filial_id,
                                st.session_state.motores_cenarios,
                                cenario_ativo,
                                st.session_state.usar_cenarios,
                                st.session_state.cenario_aprovado
                            )
                    
                    st.rerun()
            else:
                st.selectbox("🏢 Filial", ["Selecione um cliente primeiro..."], disabled=True)
        
        with col3:
            if st.button("➕ Cliente", use_container_width=True):
                st.session_state.show_modal_cliente = True
        
        with col4:
            if st.session_state.cliente_id:
                if st.button("➕ Filial", use_container_width=True):
                    st.session_state.show_modal_filial = True
    
    # Divider
    st.markdown("---")
    
    # Modal para novo cliente
    if st.session_state.get('show_modal_cliente', False):
        with st.expander("➕ NOVO CLIENTE", expanded=True):
            with st.form("form_novo_cliente"):
                nome = st.text_input("Nome do Cliente *")
                cnpj = st.text_input("CNPJ")
                contato = st.text_input("Contato")
                email = st.text_input("Email")
                telefone = st.text_input("Telefone")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("✅ Criar Cliente", use_container_width=True):
                        if nome:
                            try:
                                cliente = manager.criar_cliente(
                                    nome=nome,
                                    cnpj=cnpj,
                                    contato=contato,
                                    email=email,
                                    telefone=telefone
                                )
                                st.session_state.cliente_id = cliente.id
                                st.session_state.cliente_atual = cliente
                                
                                # IMPORTANTE: Criar filial "Matriz" automaticamente
                                filial_id = manager.criar_filial(cliente.id, "Matriz")
                                st.session_state.filial_id = filial_id
                                
                                st.session_state.show_modal_cliente = False
                                
                                # Criar motor VAZIO para cliente novo
                                st.session_state.motor = criar_motor_vazio(
                                    cliente_nome=nome,
                                    filial_nome="Matriz",
                                    tipo_relatorio="Filial"
                                )
                                
                                st.success(f"✅ Cliente '{nome}' criado com filial 'Matriz'!")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                        else:
                            st.error("Nome é obrigatório!")
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_modal_cliente = False
                        st.rerun()
    
    # Modal para nova filial
    if st.session_state.get('show_modal_filial', False) and st.session_state.cliente_id:
        with st.expander("➕ NOVA FILIAL", expanded=True):
            with st.form("form_nova_filial"):
                nome_filial = st.text_input("Nome da Filial *")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.form_submit_button("✅ Criar Filial", use_container_width=True):
                        if nome_filial:
                            try:
                                filial_id = manager.criar_filial(
                                    st.session_state.cliente_id,
                                    nome_filial
                                )
                                st.session_state.filial_id = filial_id
                                st.session_state.show_modal_filial = False
                                
                                # Carrega motor vazio para nova filial
                                st.session_state.motor = criar_motor_vazio()
                                
                                st.success(f"Filial '{nome_filial}' criada!")
                                st.rerun()
                            except ValueError as e:
                                st.error(str(e))
                        else:
                            st.error("Nome é obrigatório!")
                with col2:
                    if st.form_submit_button("❌ Cancelar", use_container_width=True):
                        st.session_state.show_modal_filial = False
                        st.rerun()


def criar_grafico_receitas_mensal(dados_dre):
    """Cria gráfico de evolução de receitas"""
    # Filtra receitas por serviço
    servicos = ['Oestopatia', 'Individual', 'Consultório', 'Domiciliar', 'Ginasio', 'Personalizado']
    
    dados_grafico = []
    for item in dados_dre:
        for servico in servicos:
            if servico.lower() in item['conta'].lower():
                for i, mes in enumerate(MESES_ABREV):
                    valor = item.get(mes.lower(), 0) or 0
                    dados_grafico.append({
                        'Mês': mes,
                        'Serviço': item['conta'].strip(),
                        'Valor': valor,
                        'Ordem': i
                    })
                break
    
    if not dados_grafico:
        return None
    
    df = pd.DataFrame(dados_grafico)
    df = df.sort_values('Ordem')
    
    fig = px.bar(
        df, x='Mês', y='Valor', color='Serviço',
        barmode='stack',
        color_discrete_sequence=px.colors.qualitative.Set2
    )
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_family="DM Sans",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=20, r=20, t=40, b=20),
        yaxis_title="Receita (R$)",
        xaxis_title=""
    )
    
    return fig

def criar_grafico_dre_resumo(dados_dre):
    """Cria gráfico resumo do DRE"""
    # Busca totais principais
    receita = None
    deducoes = None
    custos = None
    despesas = None
    resultado = None
    
    for item in dados_dre:
        conta = item['conta'].lower()
        total = item.get('total', 0) or 0
        
        if 'total da receita bruta' in conta:
            receita = total
        elif 'total deduções' in conta or 'total das deduções' in conta:
            deducoes = abs(total)
        elif 'total dos custos' in conta or 'custo total' in conta:
            custos = abs(total)
        elif 'total despesas' in conta or 'despesas operacionais' in conta:
            despesas = abs(total)
        elif 'resultado líquido' in conta or 'lucro líquido' in conta:
            resultado = total
    
    if receita is None:
        return None
    
    # Gráfico waterfall
    fig = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "relative", "total"],
        x=["Receita Bruta", "Deduções", "Custos", "Despesas", "Resultado"],
        y=[receita, -(deducoes or 0), -(custos or 0), -(despesas or 0), 0],
        connector={"line": {"color": "#718096"}},
        decreasing={"marker": {"color": "#fc8181"}},
        increasing={"marker": {"color": "#68d391"}},
        totals={"marker": {"color": "#4299e1" if (resultado or 0) >= 0 else "#fc8181"}}
    ))
    
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_family="DM Sans",
        showlegend=False,
        margin=dict(l=20, r=20, t=20, b=20),
        yaxis_title="Valor (R$)"
    )
    
    return fig

# ============================================
# PÁGINAS
# ============================================

def pagina_dashboard():
    """Página principal - Dashboard Completo de Gestão à Vista"""
    render_header()
    
    motor = st.session_state.motor
    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    # ========================================================================
    # ALERTA DE VALIDAÇÃO DE SESSÕES
    # ========================================================================
    try:
        validacao = motor.validar_sessoes()
        if not validacao["ok"]:
            with st.expander("⚠️ **Atenção: Inconsistências detectadas nas sessões**", expanded=False):
                modo = validacao["detalhes"]["modo"]
                st.caption(f"Modo atual: **{modo.upper()}** (configurado em Premissas → Operacionais)")
                
                for erro in validacao["erros"]:
                    st.error(f"❌ {erro}")
                for alerta in validacao["alertas"]:
                    st.warning(f"⚠️ {alerta}")
                
                st.markdown("**💡 Dica:** Vá em **⚙️ Premissas → Operacionais** para ver detalhes e ajustar.")
    except:
        pass  # Silencioso se falhar
    
    # ========================================================================
    # CONTROLES GLOBAIS
    # ========================================================================
    col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([2, 2, 3, 3])
    
    with col_ctrl1:
        periodo_tipo = st.selectbox(
            "📅 Período",
            ["Mês Específico", "Trimestre", "Semestre", "Ano Completo"],
            index=3,
            key="dash_periodo_tipo"
        )
    
    with col_ctrl2:
        if periodo_tipo == "Mês Específico":
            mes_selecionado = st.selectbox("Mês", meses_nomes, index=0, key="dash_mes")
            mes_idx = meses_nomes.index(mes_selecionado)
            meses_range = [mes_idx]
        elif periodo_tipo == "Trimestre":
            trimestre = st.selectbox("Trimestre", ["T1 (Jan-Mar)", "T2 (Abr-Jun)", "T3 (Jul-Set)", "T4 (Out-Dez)"], key="dash_tri")
            tri_map = {"T1 (Jan-Mar)": [0,1,2], "T2 (Abr-Jun)": [3,4,5], "T3 (Jul-Set)": [6,7,8], "T4 (Out-Dez)": [9,10,11]}
            meses_range = tri_map[trimestre]
        elif periodo_tipo == "Semestre":
            semestre = st.selectbox("Semestre", ["S1 (Jan-Jun)", "S2 (Jul-Dez)"], key="dash_sem")
            meses_range = list(range(6)) if "S1" in semestre else list(range(6, 12))
        else:
            meses_range = list(range(12))
    
    with col_ctrl3:
        # Verifica se cenários está habilitado
        usar_cenarios = getattr(motor, 'usar_cenarios', True)
        
        if usar_cenarios:
            # Lista de cenários disponíveis
            cenarios_opcoes = ["Conservador", "Pessimista", "Otimista"]
            
            cenario_oficial = getattr(motor, 'cenario_oficial', 'Conservador')
            
            # Usar session_state como fonte de verdade
            cenario_atual = st.session_state.get('cenario_ativo', cenario_oficial)
        
            # Validar que está na lista
            if cenario_atual not in cenarios_opcoes:
                cenario_atual = cenario_oficial
            
            idx_cenario = cenarios_opcoes.index(cenario_atual)
            
            cenario_selecionado = st.selectbox(
                "🎯 Cenário",
                cenarios_opcoes,
                index=idx_cenario,
                key="dash_cenario",
                format_func=lambda x: f"⭐ {x}" if x == cenario_oficial else x,
                help=f"⭐ = Cenário oficial ({cenario_oficial}). Configure em Premissas → Cenários"
            )
            
            # Se mudou o cenário, troca o motor ativo
            if cenario_selecionado != cenario_atual:
                # Salva motor atual antes de trocar
                st.session_state.motores_cenarios[cenario_atual] = st.session_state.motor
                
                # Troca para o motor do novo cenário
                st.session_state.cenario_ativo = cenario_selecionado
                st.session_state.motor = st.session_state.motores_cenarios[cenario_selecionado]
                motor = st.session_state.motor
            else:
                st.session_state.cenario_ativo = cenario_selecionado
        else:
            # Cenários desabilitado - não mostra seletor
            st.session_state.cenario_ativo = "Conservador"
    
    with col_ctrl4:
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Pegar nomes do cliente e filial (usado em ambas exportações)
        if st.session_state.cliente_atual:
            cliente_nome = st.session_state.cliente_atual.nome
        else:
            cliente_nome = 'Cliente'
        
        if st.session_state.cliente_id and st.session_state.filial_id:
            if st.session_state.filial_id == "consolidado":
                filial_nome = "Consolidado"
            else:
                filiais = st.session_state.cliente_manager.listar_filiais(st.session_state.cliente_id)
                filial_nome = next(
                    (f["nome"] for f in filiais if f["id"] == st.session_state.filial_id),
                    "Filial"
                )
        else:
            filial_nome = 'Filial'
        
        # Dropdown de exportação
        opcao_export = st.selectbox(
            "📥 Exportar",
            ["Selecione...", "📊 Excel (Completo)", "📄 PDF (Executivo)"],
            key="select_export_dashboard",
            label_visibility="collapsed"
        )
        
        if opcao_export == "📊 Excel (Completo)":
            try:
                from modules.excel_export import exportar_budget_cliente
                
                motor.cliente_nome = cliente_nome
                motor.filial_nome = filial_nome
                motor.tipo_relatorio = "Consolidado" if st.session_state.filial_id == "consolidado" else "Filial"
                
                filepath = f"/tmp/Budget_{cliente_nome}_{filial_nome}_2026.xlsx"
                exportar_budget_cliente(motor, filepath)
                
                with open(filepath, 'rb') as f:
                    st.download_button(
                        label="⬇️ Baixar Excel",
                        data=f.read(),
                        file_name=f"Budget_{cliente_nome}_{filial_nome}_2026.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            except Exception as e:
                erro_msg = registrar_erro("BE-601", str(e), "pagina_dashboard/exportar_excel")
                st.error(f"Erro ao gerar relatório: {erro_msg}")
        
        elif opcao_export == "📄 PDF (Executivo)":
            # Expander com opções de personalização
            with st.expander("⚙️ Personalizar Relatório PDF", expanded=True):
                col_pdf1, col_pdf2 = st.columns(2)
                
                with col_pdf1:
                    nome_relatorio = st.text_input(
                        "Nome da Empresa/Cliente",
                        value=f"{cliente_nome} - {filial_nome}" if filial_nome != "Cliente" else cliente_nome,
                        key="pdf_nome_cliente",
                        help="Nome que aparecerá na capa e cabeçalho do relatório"
                    )
                
                with col_pdf2:
                    st.markdown("**Conteúdo do Relatório:**")
                    st.caption("""
                    ✓ Visão Geral e KPIs  
                    ✓ Receitas por Serviço  
                    ✓ Custeio ABC (custo/sessão)  
                    ✓ Ponto de Equilíbrio  
                    ✓ Taxa de Ocupação  
                    ✓ Fluxo de Caixa  
                    """)
                
                obs_relatorio = st.text_area(
                    "Observações Adicionais (opcional)",
                    value="",
                    height=100,
                    key="pdf_observacoes",
                    help="Texto que aparecerá na seção de Conclusões do relatório",
                    placeholder="Ex: Próximos passos, considerações especiais, notas para o cliente..."
                )
                
                if st.button("📄 Gerar Relatório PDF", use_container_width=True, type="primary"):
                    try:
                        from modules.pdf_report import gerar_relatorio_do_motor
                        
                        # Determinar tipo de relatório
                        tipo_rel = "Consolidado" if st.session_state.filial_id == "consolidado" else "Filial"
                        
                        with st.spinner("Gerando relatório... Isso pode levar alguns segundos."):
                            pdf_buffer = gerar_relatorio_do_motor(
                                motor=motor,
                                nome_cliente=nome_relatorio,
                                observacoes=obs_relatorio,
                                tipo_relatorio=tipo_rel
                            )
                        
                        st.success("✅ Relatório gerado com sucesso!")
                        
                        st.download_button(
                            label="⬇️ Baixar PDF",
                            data=pdf_buffer.getvalue(),
                            file_name=f"Planejamento_Orcamentario_2026_{cliente_nome.replace(' ', '_')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                    except Exception as e:
                        erro_msg = registrar_erro("BE-602", str(e), "pagina_dashboard/exportar_pdf")
                        st.error(f"Erro ao gerar PDF: {erro_msg}")
    
    st.markdown("---")
    
    # Badge do cenário ativo (após seleção)
    # Badge no header
    
    # ========================================================================
    # CALCULAR DADOS DO PERÍODO
    # ========================================================================
    # PE e Ocupação
    pe_anual = motor.calcular_pe_anual()
    ocupacao_anual = motor.calcular_ocupacao_anual()
    tdabc_anual = motor.calcular_tdabc_anual()
    
    # Agregar para o período selecionado
    receita_periodo = sum(pe_anual.meses[m].receita_liquida for m in meses_range)
    ebitda_periodo = sum(pe_anual.meses[m].ebitda for m in meses_range)
    cf_periodo = sum(pe_anual.meses[m].custos_fixos for m in meses_range)
    cv_periodo = sum(pe_anual.meses[m].custos_variaveis for m in meses_range)
    mc_periodo = sum(pe_anual.meses[m].margem_contribuicao for m in meses_range)
    sessoes_periodo = sum(pe_anual.meses[m].total_sessoes for m in meses_range)
    pe_periodo = sum(pe_anual.meses[m].pe_contabil for m in meses_range)
    custo_ociosidade_periodo = sum(pe_anual.meses[m].custo_ociosidade for m in meses_range)
    
    margem_ebitda_periodo = ebitda_periodo / receita_periodo if receita_periodo > 0 else 0
    margem_seg_periodo = (receita_periodo - pe_periodo) / receita_periodo if receita_periodo > 0 else 0
    lucro_sessao = ebitda_periodo / sessoes_periodo if sessoes_periodo > 0 else 0
    
    # Ocupação média do período
    num_meses = len(meses_range) if meses_range else 1
    taxa_prof_media = sum(ocupacao_anual.meses[m].taxa_ocupacao_profissional for m in meses_range) / num_meses
    taxa_sala_media = sum(ocupacao_anual.meses[m].taxa_ocupacao_sala for m in meses_range) / num_meses
    gargalo = "Sala" if taxa_sala_media > taxa_prof_media else "Profissional"
    
    # ========================================================================
    # SEÇÃO 1: PAINEL EXECUTIVO (8 KPIs)
    # ========================================================================
    st.markdown("### 📊 Painel Executivo")
    
    # Linha 1: 4 KPIs principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Variação vs período anterior (simplificado)
        render_metric_card("💰 Receita Líquida", f"R$ {receita_periodo:,.0f}", card_type="success")
    
    with col2:
        cor_ebitda = "success" if ebitda_periodo > 0 else "danger"
        render_metric_card("📈 EBITDA", f"R$ {ebitda_periodo:,.0f}", card_type=cor_ebitda)
    
    with col3:
        render_metric_card("💵 Lucro/Sessão", f"R$ {lucro_sessao:.2f}", card_type="default")
    
    with col4:
        cor_margem = "success" if margem_ebitda_periodo >= 0.15 else ("warning" if margem_ebitda_periodo >= 0.10 else "danger")
        render_metric_card("📊 Margem EBITDA", f"{margem_ebitda_periodo*100:.1f}%", card_type=cor_margem)
    
    # Linha 2: 4 KPIs complementares
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card("🎯 PE Contábil", f"R$ {pe_periodo:,.0f}", card_type="warning")
    
    with col2:
        cor_ms = "success" if margem_seg_periodo >= 0.20 else ("warning" if margem_seg_periodo >= 0.10 else "danger")
        render_metric_card("⚖️ Marg. Segurança", f"{margem_seg_periodo*100:.1f}%", card_type=cor_ms)
    
    with col3:
        cor_ocup = "success" if taxa_sala_media < 0.70 else ("warning" if taxa_sala_media < 0.90 else "danger")
        emoji_garg = "🏥" if gargalo == "Sala" else "👥"
        render_metric_card("📊 Taxa Ocupação", f"{taxa_sala_media*100:.1f}% {emoji_garg}", card_type=cor_ocup)
    
    with col4:
        render_metric_card("🏥 Sessões", f"{sessoes_periodo:,.0f}", card_type="default")
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 2: EVOLUÇÃO FINANCEIRA
    # ========================================================================
    st.markdown("### 📈 Evolução Financeira")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gráfico Receita vs EBITDA
        fig = go.Figure()
        
        receitas_mes = [pe_anual.meses[m].receita_liquida for m in range(12)]
        ebitdas_mes = [pe_anual.meses[m].ebitda for m in range(12)]
        
        fig.add_trace(go.Bar(
            x=meses_nomes,
            y=receitas_mes,
            name="Receita Líquida",
            marker_color="#3498db",
            opacity=0.7
        ))
        
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=ebitdas_mes,
            name="EBITDA",
            line=dict(color="#27ae60", width=3),
            mode="lines+markers",
            yaxis="y2"
        ))
        
        fig.update_layout(
            title="Receita vs EBITDA (12 meses)",
            xaxis_title="",
            yaxis=dict(title="Receita (R$)", side="left"),
            yaxis2=dict(title="EBITDA (R$)", side="right", overlaying="y"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=350,
            margin=dict(t=50, b=30)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Waterfall DRE
        # Calcular receitas e deduções
        motor.calcular_receita_bruta_total()
        motor.calcular_deducoes_total()
        
        if len(meses_range) == 1:
            mes = meses_range[0]
            pe_mes = pe_anual.meses[mes]
            
            # Calcular deduções
            receita_bruta = motor.receita_bruta.get("Total", [0]*12)[mes]
            deducoes = motor.deducoes.get("Total Deduções", [0]*12)[mes]
            
            fig = go.Figure(go.Waterfall(
                orientation="v",
                x=["Receita Bruta", "(-) Deduções", "(-) CV", "(-) Custos Fixos", "= EBITDA"],
                y=[receita_bruta, -deducoes, -pe_mes.custos_variaveis, -pe_mes.custos_fixos, 0],
                measure=["absolute", "relative", "relative", "relative", "total"],
                connector={"line": {"color": "#888"}},
                decreasing={"marker": {"color": "#e74c3c"}},
                increasing={"marker": {"color": "#27ae60"}},
                totals={"marker": {"color": "#3498db"}}
            ))
            
            fig.update_layout(
                title=f"Waterfall DRE - {meses_nomes[mes]}",
                height=350,
                margin=dict(t=50, b=30)
            )
        else:
            # Waterfall do período
            receita_bruta_per = sum(motor.receita_bruta.get("Total", [0]*12)[m] for m in meses_range)
            deducoes_per = sum(motor.deducoes.get("Total Deduções", [0]*12)[m] for m in meses_range)
            
            fig = go.Figure(go.Waterfall(
                orientation="v",
                x=["Receita Bruta", "(-) Deduções", "(-) CV", "(-) Custos Fixos", "= EBITDA"],
                y=[receita_bruta_per, -deducoes_per, -cv_periodo, -cf_periodo, 0],
                measure=["absolute", "relative", "relative", "relative", "total"],
                connector={"line": {"color": "#888"}},
                decreasing={"marker": {"color": "#e74c3c"}},
                increasing={"marker": {"color": "#27ae60"}},
                totals={"marker": {"color": "#3498db"}}
            ))
            
            fig.update_layout(
                title=f"Waterfall DRE - Período",
                height=350,
                margin=dict(t=50, b=30)
            )
        
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 3: PERFORMANCE POR SERVIÇO
    # ========================================================================
    st.markdown("### 🏆 Performance por Serviço")
    
    col1, col2 = st.columns(2)
    
    # Helpers para obter atributos com fallback
    def get_rateio_attr(mes_obj, servico, attr, default=0):
        rateio = mes_obj.rateios.get(servico)
        if rateio:
            return getattr(rateio, attr, default)
        return default
    
    def get_lucro_attr(mes_obj, servico, attr, default=0):
        lucro = mes_obj.lucros.get(servico)
        if lucro:
            return getattr(lucro, attr, default)
        return default
    
    with col1:
        # Treemap de Mix de Receita
        import pandas as pd  # Import local para garantir
        servicos_data = []
        for servico in motor.servicos.keys():
            receita_srv = sum(get_rateio_attr(tdabc_anual.meses[m], servico, 'receita', 0) for m in meses_range)
            lucro_srv = sum(get_lucro_attr(tdabc_anual.meses[m], servico, 'lucro_abc', 0) for m in meses_range)
            margem_srv = lucro_srv / receita_srv if receita_srv > 0 else 0
            if receita_srv > 0:
                servicos_data.append({
                    'servico': servico,
                    'receita': receita_srv,
                    'lucro': lucro_srv,
                    'margem': margem_srv
                })
        
        if servicos_data:
            df_srv = pd.DataFrame(servicos_data)
            
            fig = px.treemap(
                df_srv,
                path=['servico'],
                values='receita',
                color='margem',
                color_continuous_scale=['#e74c3c', '#f39c12', '#27ae60'],
                title="Mix de Receita por Serviço (tamanho = receita, cor = margem)"
            )
            fig.update_layout(height=350, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        # Ranking de Rentabilidade
        if servicos_data:
            df_srv_sorted = df_srv.sort_values('margem', ascending=False)
            
            cores = ['#27ae60' if m >= 0.15 else ('#f39c12' if m >= 0.10 else '#e74c3c') for m in df_srv_sorted['margem']]
            
            fig = go.Figure(go.Bar(
                x=df_srv_sorted['margem'] * 100,
                y=df_srv_sorted['servico'],
                orientation='h',
                marker_color=cores,
                text=[f"{m*100:.1f}%" for m in df_srv_sorted['margem']],
                textposition='outside'
            ))
            
            fig.add_vline(x=margem_ebitda_periodo*100, line_dash="dash", line_color="blue", 
                         annotation_text=f"Média {margem_ebitda_periodo*100:.1f}%")
            
            fig.update_layout(
                title="Margem ABC por Serviço",
                xaxis_title="Margem (%)",
                height=350,
                margin=dict(t=50, b=30, l=100)
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # Tabela detalhada de serviços
    st.markdown("#### 📋 Detalhamento por Serviço")
    
    tabela_servicos = []
    
    for servico in motor.servicos.keys():
        receita_srv = sum(get_rateio_attr(tdabc_anual.meses[m], servico, 'receita', 0) for m in meses_range)
        sessoes_srv = sum(get_rateio_attr(tdabc_anual.meses[m], servico, 'sessoes', 0) for m in meses_range)
        lucro_srv = sum(get_lucro_attr(tdabc_anual.meses[m], servico, 'lucro_abc', 0) for m in meses_range)
        horas_srv = sum(get_rateio_attr(tdabc_anual.meses[m], servico, 'horas_sala', 0) for m in meses_range)
        cv_srv = sum(get_lucro_attr(tdabc_anual.meses[m], servico, 'custos_variaveis_rateados', 0) for m in meses_range)
        oh_srv = sum(get_lucro_attr(tdabc_anual.meses[m], servico, 'overhead_rateado', 0) for m in meses_range)
        
        margem_srv = lucro_srv / receita_srv if receita_srv > 0 else 0
        lucro_hora = lucro_srv / horas_srv if horas_srv > 0 else 0
        
        if receita_srv > 0:
            tabela_servicos.append({
                'Serviço': servico,
                'Sessões': f"{sessoes_srv:,.0f}",
                'Receita': f"R$ {receita_srv:,.0f}",
                'CV': f"R$ {cv_srv:,.0f}",
                'Overhead': f"R$ {oh_srv:,.0f}",
                'Lucro ABC': f"R$ {lucro_srv:,.0f}",
                'Margem': f"{margem_srv*100:.1f}%",
                'Lucro/Hora': f"R$ {lucro_hora:.2f}"
            })
    
    if tabela_servicos:
        st.dataframe(pd.DataFrame(tabela_servicos), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 4: PERFORMANCE PROFISSIONAIS
    # ========================================================================
    st.markdown("### 👥 Performance Profissionais")
    
    # Calcular dados por profissional
    prof_data = []
    for nome, fisio in motor.fisioterapeutas.items():
        if fisio.ativo:
            sessoes_prof = 0
            receita_prof = 0
            
            for m in meses_range:
                for srv in fisio.sessoes_por_servico.keys():
                    qtd_base = fisio.sessoes_por_servico.get(srv, 0)
                    if qtd_base > 0:
                        # Usar mesma fórmula de crescimento linear do motor
                        crescimento = fisio.pct_crescimento_por_servico.get(srv, 0)
                        if crescimento > 0:
                            crescimento_qtd = qtd_base * crescimento
                            cresc_mensal = crescimento_qtd / 13.1
                            sessoes_mes = qtd_base + cresc_mensal * (m + 0.944)
                        else:
                            sessoes_mes = qtd_base
                        
                        sessoes_prof += sessoes_mes
                        
                        if srv in motor.servicos:
                            # Usar calcular_valor_servico_mes para considerar reajuste
                            valor_srv = motor.calcular_valor_servico_mes(srv, m, "profissional")
                            receita_prof += sessoes_mes * valor_srv
            
            horas_mes = fisio.horas_mes * len(meses_range)
            ocupacao = sessoes_prof / (horas_mes / 0.83) if horas_mes > 0 else 0  # Assumindo 50min por sessão
            receita_hora = receita_prof / horas_mes if horas_mes > 0 else 0
            
            prof_data.append({
                'nome': nome,
                'sessoes': sessoes_prof,
                'receita': receita_prof,
                'horas': horas_mes,
                'ocupacao': ocupacao,
                'receita_hora': receita_hora
            })
    
    if prof_data:
        df_prof = pd.DataFrame(prof_data).sort_values('receita', ascending=False)
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Top 5 por Sessões
            top5_sessoes = df_prof.nlargest(5, 'sessoes')
            
            fig = go.Figure(go.Bar(
                x=top5_sessoes['sessoes'],
                y=top5_sessoes['nome'],
                orientation='h',
                marker_color='#3498db',
                text=[f"{s:,.0f}" for s in top5_sessoes['sessoes']],
                textposition='outside'
            ))
            
            fig.update_layout(
                title="Top 5 - Sessões",
                xaxis_title="Sessões",
                height=280,
                margin=dict(t=40, b=20, l=100)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Top 5 por Receita
            top5_receita = df_prof.nlargest(5, 'receita')
            
            fig = go.Figure(go.Bar(
                x=top5_receita['receita'],
                y=top5_receita['nome'],
                orientation='h',
                marker_color='#27ae60',
                text=[f"R$ {r:,.0f}" for r in top5_receita['receita']],
                textposition='outside'
            ))
            
            fig.update_layout(
                title="Top 5 - Receita Gerada",
                xaxis_title="Receita (R$)",
                height=280,
                margin=dict(t=40, b=20, l=100)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Tabela completa
        st.markdown("#### 📋 Detalhamento por Profissional")
        tabela_prof = []
        for _, row in df_prof.iterrows():
            tabela_prof.append({
                'Profissional': row['nome'],
                'Sessões': f"{row['sessoes']:,.0f}",
                'Receita': f"R$ {row['receita']:,.0f}",
                'Horas': f"{row['horas']:,.0f}h",
                'R$/Hora': f"R$ {row['receita_hora']:.2f}"
            })
        
        st.dataframe(pd.DataFrame(tabela_prof), use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 5: PONTO DE EQUILÍBRIO
    # ========================================================================
    st.markdown("### ⚖️ Ponto de Equilíbrio")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Gauge de Receita vs PE
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=receita_periodo,
            delta={'reference': pe_periodo, 'relative': False, 'valueformat': ',.0f'},
            title={'text': "Receita vs PE"},
            gauge={
                'axis': {'range': [0, receita_periodo * 1.2]},
                'bar': {'color': "#3498db"},
                'steps': [
                    {'range': [0, pe_periodo * 0.8], 'color': "#e74c3c"},
                    {'range': [pe_periodo * 0.8, pe_periodo], 'color': "#f39c12"},
                    {'range': [pe_periodo, receita_periodo * 1.2], 'color': "#27ae60"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': pe_periodo
                }
            }
        ))
        
        fig.update_layout(height=300, margin=dict(t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        
        st.info(f"**Margem de Segurança:** R$ {receita_periodo - pe_periodo:,.0f} ({margem_seg_periodo*100:.1f}%)")
    
    with col2:
        # Evolução PE vs Receita
        fig = go.Figure()
        
        receitas = [pe_anual.meses[m].receita_liquida for m in range(12)]
        pes = [pe_anual.meses[m].pe_contabil for m in range(12)]
        
        # Área da receita
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=receitas,
            fill='tozeroy',
            name='Receita',
            fillcolor='rgba(39, 174, 96, 0.3)',
            line=dict(color='#27ae60', width=2)
        ))
        
        # Linha do PE
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=pes,
            name='Ponto de Equilíbrio',
            line=dict(color='#e74c3c', width=3, dash='dash')
        ))
        
        fig.update_layout(
            title="Receita vs Ponto de Equilíbrio",
            xaxis_title="",
            yaxis_title="R$",
            height=300,
            margin=dict(t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 6: OCUPAÇÃO E CAPACIDADE
    # ========================================================================
    st.markdown("### 📊 Ocupação e Capacidade")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Dual Gauge Ocupação
        fig = go.Figure()
        
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=taxa_prof_media * 100,
            title={'text': "Profissional"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#3498db"},
                'steps': [
                    {'range': [0, 50], 'color': "#d5f5e3"},
                    {'range': [50, 70], 'color': "#82e0aa"},
                    {'range': [70, 90], 'color': "#f9e79f"},
                    {'range': [90, 100], 'color': "#f5b7b1"}
                ]
            },
            domain={'x': [0, 0.45], 'y': [0, 1]}
        ))
        
        fig.add_trace(go.Indicator(
            mode="gauge+number",
            value=taxa_sala_media * 100,
            title={'text': "Sala"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': "#e74c3c"},
                'steps': [
                    {'range': [0, 50], 'color': "#d5f5e3"},
                    {'range': [50, 70], 'color': "#82e0aa"},
                    {'range': [70, 90], 'color': "#f9e79f"},
                    {'range': [90, 100], 'color': "#f5b7b1"}
                ]
            },
            domain={'x': [0.55, 1], 'y': [0, 1]}
        ))
        
        fig.update_layout(height=280, margin=dict(t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
        st.warning(f"🎯 **Gargalo:** {gargalo} ({max(taxa_prof_media, taxa_sala_media)*100:.1f}%)")
    
    with col2:
        # Evolução da ocupação
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=[ocupacao_anual.meses[m].taxa_ocupacao_profissional * 100 for m in range(12)],
            name="Profissional",
            line=dict(color="#3498db", width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=[ocupacao_anual.meses[m].taxa_ocupacao_sala * 100 for m in range(12)],
            name="Sala",
            line=dict(color="#e74c3c", width=2)
        ))
        
        fig.add_hline(y=70, line_dash="dash", line_color="orange", annotation_text="Atenção")
        fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Crítico")
        
        fig.update_layout(
            title="Evolução da Taxa de Ocupação",
            xaxis_title="",
            yaxis_title="%",
            yaxis=dict(range=[0, 110]),
            height=280,
            margin=dict(t=50, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Custo da Ociosidade
    custo_ociosidade_ano = sum(pe_anual.meses[m].custo_ociosidade for m in range(12))
    ebitda_ano = sum(pe_anual.meses[m].ebitda for m in range(12))
    pct_ociosidade_ebitda = custo_ociosidade_ano / ebitda_ano if ebitda_ano > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("💸 Custo Ociosidade/Mês", f"R$ {custo_ociosidade_ano/12:,.0f}")
    with col2:
        st.metric("💸 Custo Ociosidade/Ano", f"R$ {custo_ociosidade_ano:,.0f}")
    with col3:
        st.metric("📊 % sobre EBITDA", f"{pct_ociosidade_ebitda*100:.1f}%")
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 7: ALERTAS E INSIGHTS
    # ========================================================================
    st.markdown("### 🚨 Alertas e Insights")
    
    alertas = []
    
    # Analisar ocupação
    meses_criticos = [m for m in range(12) if ocupacao_anual.meses[m].taxa_ocupacao_sala > 0.95]
    if meses_criticos:
        meses_str = ", ".join([meses_nomes[m] for m in meses_criticos])
        alertas.append(("🔴", "CRÍTICO", f"Taxa de ocupação de sala acima de 95% em: {meses_str}"))
    
    # Analisar margem por serviço
    for srv in servicos_data:
        if srv['margem'] < margem_ebitda_periodo * 0.5:
            alertas.append(("🟡", "ATENÇÃO", f"Serviço {srv['servico']} com margem muito baixa ({srv['margem']*100:.1f}% vs média {margem_ebitda_periodo*100:.1f}%)"))
    
    # Margem de segurança
    if margem_seg_periodo >= 0.20:
        alertas.append(("🟢", "POSITIVO", f"Margem de segurança saudável ({margem_seg_periodo*100:.1f}% > 20%)"))
    elif margem_seg_periodo < 0.10:
        alertas.append(("🔴", "CRÍTICO", f"Margem de segurança muito baixa ({margem_seg_periodo*100:.1f}% < 10%)"))
    
    # Oportunidades
    if servicos_data:
        melhor_srv = max(servicos_data, key=lambda x: x['margem'])
        alertas.append(("💡", "OPORTUNIDADE", f"{melhor_srv['servico']} tem melhor margem ({melhor_srv['margem']*100:.1f}%) - considerar expansão"))
    
    # Custo ociosidade
    if pct_ociosidade_ebitda > 0.15:
        alertas.append(("🟡", "ATENÇÃO", f"Custo de ociosidade representa {pct_ociosidade_ebitda*100:.1f}% do EBITDA"))
    
    # Exibir alertas
    if alertas:
        for emoji, tipo, msg in alertas:
            cor = "red" if tipo == "CRÍTICO" else ("orange" if tipo == "ATENÇÃO" else ("green" if tipo == "POSITIVO" else "blue"))
            st.markdown(f"""
            <div style="padding: 10px; margin: 5px 0; border-left: 4px solid {cor}; background: #f8f9fa;">
                <strong>{emoji} {tipo}:</strong> {msg}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.success("✅ Nenhum alerta crítico no momento!")
    
    st.markdown("---")
    
    # ========================================================================
    # SEÇÃO 8: VISÃO GERENCIAL VISUAL (LÚDICA)
    # ========================================================================
    st.markdown("### 🎨 Visão Gerencial - Fácil de Entender")
    st.caption("Indicadores visuais para tomada de decisão rápida")
    
    # ========== LINHA 1: 3 GAUGES PRINCIPAIS ==========
    col1, col2, col3 = st.columns(3)
    
    # ---------- GAUGE 1: SAÚDE FINANCEIRA (baseado na Margem de Segurança) ----------
    with col1:
        # Margem de segurança indica distância do PE
        margem_seg_pct = margem_seg_periodo * 100
        
        if margem_seg_pct >= 30:
            status_financeiro = "EXCELENTE"
            cor_status = "#27ae60"
        elif margem_seg_pct >= 20:
            status_financeiro = "BOM"
            cor_status = "#3498db"
        elif margem_seg_pct >= 10:
            status_financeiro = "ATENÇÃO"
            cor_status = "#f39c12"
        else:
            status_financeiro = "CRÍTICO"
            cor_status = "#e74c3c"
        
        fig_saude = go.Figure(go.Indicator(
            mode="gauge+number",
            value=margem_seg_pct,
            number={'suffix': '%', 'font': {'size': 36}},
            title={'text': f"💚 Saúde Financeira<br><span style='font-size:14px;color:{cor_status}'>{status_financeiro}</span>"},
            gauge={
                'axis': {'range': [0, 50], 'ticksuffix': '%'},
                'bar': {'color': cor_status},
                'steps': [
                    {'range': [0, 10], 'color': '#ffebee'},
                    {'range': [10, 20], 'color': '#fff3e0'},
                    {'range': [20, 30], 'color': '#e3f2fd'},
                    {'range': [30, 50], 'color': '#e8f5e9'}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 2},
                    'thickness': 0.75,
                    'value': margem_seg_pct
                }
            }
        ))
        fig_saude.update_layout(height=250, margin=dict(t=80, b=20, l=30, r=30))
        st.plotly_chart(fig_saude, use_container_width=True)
        
        st.caption("📖 **O que significa?** Quanto maior, mais longe você está do prejuízo. Acima de 20% é saudável.")
    
    # ---------- GAUGE 2: TAXA DE OCUPAÇÃO ----------
    with col2:
        taxa_ocup_pct = taxa_sala_media * 100
        
        if taxa_ocup_pct <= 70:
            status_ocup = "FOLGA"
            cor_ocup = "#27ae60"
            emoji_ocup = "😊"
        elif taxa_ocup_pct <= 85:
            status_ocup = "IDEAL"
            cor_ocup = "#3498db"
            emoji_ocup = "👍"
        elif taxa_ocup_pct <= 95:
            status_ocup = "ATENÇÃO"
            cor_ocup = "#f39c12"
            emoji_ocup = "⚠️"
        else:
            status_ocup = "LOTADO"
            cor_ocup = "#e74c3c"
            emoji_ocup = "🔥"
        
        fig_ocup = go.Figure(go.Indicator(
            mode="gauge+number",
            value=taxa_ocup_pct,
            number={'suffix': '%', 'font': {'size': 36}},
            title={'text': f"🏥 Ocupação<br><span style='font-size:14px;color:{cor_ocup}'>{emoji_ocup} {status_ocup}</span>"},
            gauge={
                'axis': {'range': [0, 100], 'ticksuffix': '%'},
                'bar': {'color': cor_ocup},
                'steps': [
                    {'range': [0, 70], 'color': '#e8f5e9'},
                    {'range': [70, 85], 'color': '#e3f2fd'},
                    {'range': [85, 95], 'color': '#fff3e0'},
                    {'range': [95, 100], 'color': '#ffebee'}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 2},
                    'thickness': 0.75,
                    'value': taxa_ocup_pct
                }
            }
        ))
        fig_ocup.update_layout(height=250, margin=dict(t=80, b=20, l=30, r=30))
        st.plotly_chart(fig_ocup, use_container_width=True)
        
        st.caption(f"📖 **O que significa?** Gargalo atual: **{gargalo}**. Ideal entre 70-85%. Acima de 95% = sem capacidade para crescer.")
    
    # ---------- GAUGE 3: MARGEM EBITDA ----------
    with col3:
        margem_ebitda_pct = margem_ebitda_periodo * 100
        
        if margem_ebitda_pct >= 20:
            status_margem = "EXCELENTE"
            cor_margem = "#27ae60"
        elif margem_ebitda_pct >= 15:
            status_margem = "BOM"
            cor_margem = "#3498db"
        elif margem_ebitda_pct >= 10:
            status_margem = "REGULAR"
            cor_margem = "#f39c12"
        else:
            status_margem = "BAIXO"
            cor_margem = "#e74c3c"
        
        fig_margem = go.Figure(go.Indicator(
            mode="gauge+number",
            value=margem_ebitda_pct,
            number={'suffix': '%', 'font': {'size': 36}},
            title={'text': f"💰 Lucro sobre Receita<br><span style='font-size:14px;color:{cor_margem}'>{status_margem}</span>"},
            gauge={
                'axis': {'range': [0, 40], 'ticksuffix': '%'},
                'bar': {'color': cor_margem},
                'steps': [
                    {'range': [0, 10], 'color': '#ffebee'},
                    {'range': [10, 15], 'color': '#fff3e0'},
                    {'range': [15, 20], 'color': '#e3f2fd'},
                    {'range': [20, 40], 'color': '#e8f5e9'}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 2},
                    'thickness': 0.75,
                    'value': margem_ebitda_pct
                }
            }
        ))
        fig_margem.update_layout(height=250, margin=dict(t=80, b=20, l=30, r=30))
        st.plotly_chart(fig_margem, use_container_width=True)
        
        st.caption("📖 **O que significa?** De cada R$100 que entra, quanto sobra de lucro. Acima de 15% é bom para saúde.")
    
    st.markdown("---")
    
    # ========== LINHA 2: PONTO DE EQUILÍBRIO VISUAL ==========
    st.markdown("#### 🎯 Termômetro do Ponto de Equilíbrio")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Gráfico de progresso tipo termômetro
        receita_ano = sum(pe_anual.meses[m].receita_liquida for m in range(12))
        pe_ano = sum(pe_anual.meses[m].pe_contabil for m in range(12))
        
        # Calcular progresso
        if pe_ano > 0:
            progresso_pe = (receita_ano / pe_ano) * 100
        else:
            progresso_pe = 100
        
        # Limitar para visualização
        progresso_visual = min(progresso_pe, 150)
        
        fig_termometro = go.Figure()
        
        # Barra de fundo (meta = 100%)
        fig_termometro.add_trace(go.Bar(
            x=[150],
            y=["Receita vs PE"],
            orientation='h',
            marker_color='#ecf0f1',
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Linha do PE (100%)
        cor_barra = '#27ae60' if progresso_pe >= 100 else '#e74c3c'
        
        fig_termometro.add_trace(go.Bar(
            x=[progresso_visual],
            y=["Receita vs PE"],
            orientation='h',
            marker_color=cor_barra,
            name=f"Receita: {progresso_pe:.0f}% do PE",
            text=f"{progresso_pe:.0f}%",
            textposition='inside',
            textfont=dict(size=20, color='white')
        ))
        
        # Linha vertical no 100%
        fig_termometro.add_vline(x=100, line_dash="dash", line_color="black", line_width=3,
                                  annotation_text="🎯 PE", annotation_position="top")
        
        fig_termometro.update_layout(
            title="📊 Quanto da Meta de Equilíbrio Foi Atingido?",
            xaxis=dict(range=[0, 150], ticksuffix='%', title=""),
            yaxis=dict(visible=False),
            height=150,
            margin=dict(t=60, b=20, l=20, r=20),
            showlegend=False,
            barmode='overlay'
        )
        
        st.plotly_chart(fig_termometro, use_container_width=True)
        
        # Explicação
        if progresso_pe >= 100:
            excedente = receita_ano - pe_ano
            st.success(f"✅ **Parabéns!** Você ultrapassou o ponto de equilíbrio em **R$ {excedente:,.0f}** ({progresso_pe-100:.0f}% acima)")
        else:
            falta = pe_ano - receita_ano
            st.error(f"❌ **Atenção!** Faltam **R$ {falta:,.0f}** para atingir o ponto de equilíbrio ({100-progresso_pe:.0f}% abaixo)")
    
    with col2:
        # Cards explicativos
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 10px; color: white; margin-bottom: 10px;">
            <div style="font-size: 12px; opacity: 0.9;">💵 Receita Anual</div>
            <div style="font-size: 24px; font-weight: bold;">R$ {receita_ano:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 15px; border-radius: 10px; color: white; margin-bottom: 10px;">
            <div style="font-size: 12px; opacity: 0.9;">🎯 Ponto de Equilíbrio</div>
            <div style="font-size: 24px; font-weight: bold;">R$ {pe_ano:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        margem_valor = receita_ano - pe_ano
        cor_margem_card = "#27ae60" if margem_valor >= 0 else "#e74c3c"
        st.markdown(f"""
        <div style="background: {cor_margem_card}; padding: 15px; border-radius: 10px; color: white;">
            <div style="font-size: 12px; opacity: 0.9;">{'✅ Margem' if margem_valor >= 0 else '❌ Deficit'}</div>
            <div style="font-size: 24px; font-weight: bold;">R$ {abs(margem_valor):,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # ========== LINHA 3: CUSTEIO ABC COMPLETO ==========
    st.markdown("#### 🏆 Custeio ABC - Rentabilidade dos Serviços")
    st.caption("Quanto cada serviço realmente contribui para o lucro da clínica")
    
    # Pegar dados do TDABC
    tdabc_resumo = motor.get_resumo_tdabc()
    ranking_abc = tdabc_resumo.get('ranking', [])
    overhead_total = tdabc_resumo.get('overhead_total', 0)
    lucro_total_abc = tdabc_resumo.get('lucro_total', 0)
    
    if ranking_abc and any(r.get('receita', 0) > 0 for r in ranking_abc):
        # ===== LINHA 3A: MÉTRICAS GERAIS DO CUSTEIO =====
        col1, col2, col3, col4 = st.columns(4)
        
        receita_total_abc = sum(r.get('receita', 0) for r in ranking_abc)
        margem_media = (lucro_total_abc / receita_total_abc * 100) if receita_total_abc > 0 else 0
        servicos_lucrativos = sum(1 for r in ranking_abc if r.get('lucro_abc', 0) > 0)
        servicos_prejuizo = sum(1 for r in ranking_abc if r.get('lucro_abc', 0) < 0)
        
        with col1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 15px; border-radius: 10px; color: white; text-align: center;">
                <div style="font-size: 11px; opacity: 0.9;">💰 LUCRO ABC ANUAL</div>
                <div style="font-size: 22px; font-weight: bold;">R$ {lucro_total_abc:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 15px; border-radius: 10px; color: white; text-align: center;">
                <div style="font-size: 11px; opacity: 0.9;">🏢 CUSTOS FIXOS (OVERHEAD)</div>
                <div style="font-size: 22px; font-weight: bold;">R$ {overhead_total:,.0f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            cor_margem = "#27ae60" if margem_media >= 15 else ("#f39c12" if margem_media >= 5 else "#e74c3c")
            st.markdown(f"""
            <div style="background: {cor_margem}; padding: 15px; border-radius: 10px; color: white; text-align: center;">
                <div style="font-size: 11px; opacity: 0.9;">📊 MARGEM MÉDIA</div>
                <div style="font-size: 22px; font-weight: bold;">{margem_media:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            if servicos_prejuizo > 0:
                cor_srv = "#e74c3c"
                texto_srv = f"⚠️ {servicos_prejuizo} em prejuízo"
            else:
                cor_srv = "#27ae60"
                texto_srv = f"✅ Todos lucrativos"
            st.markdown(f"""
            <div style="background: {cor_srv}; padding: 15px; border-radius: 10px; color: white; text-align: center;">
                <div style="font-size: 11px; opacity: 0.9;">📋 SERVIÇOS</div>
                <div style="font-size: 16px; font-weight: bold;">{texto_srv}</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ===== LINHA 3B: RANKING + CARDS =====
        col1, col2 = st.columns([3, 1])
        
        with col1:
            # Ordenar por margem (usar margem_abc que é o campo correto)
            ranking_ordenado = sorted(ranking_abc, key=lambda x: x.get('margem_abc', 0), reverse=True)[:6]
            
            servicos_nomes = [r['servico'] for r in ranking_ordenado]
            margens = [r.get('margem_abc', 0) * 100 for r in ranking_ordenado]
            lucros = [r.get('lucro_abc', 0) for r in ranking_ordenado]
            
            # Cores por faixa
            cores = []
            for m in margens:
                if m >= 30:
                    cores.append('#27ae60')  # Verde
                elif m >= 20:
                    cores.append('#3498db')  # Azul
                elif m >= 10:
                    cores.append('#f39c12')  # Amarelo
                elif m >= 0:
                    cores.append('#e67e22')  # Laranja
                else:
                    cores.append('#e74c3c')  # Vermelho
            
            fig_ranking = go.Figure()
            
            fig_ranking.add_trace(go.Bar(
                y=servicos_nomes[::-1],  # Inverter para maior no topo
                x=margens[::-1],
                orientation='h',
                marker_color=cores[::-1],
                text=[f"{m:.1f}%" for m in margens[::-1]],
                textposition='auto',
                textfont=dict(size=14, color='white'),
                hovertemplate='<b>%{y}</b><br>Margem: %{x:.1f}%<extra></extra>'
            ))
            
            fig_ranking.update_layout(
                title="📊 Margem de Lucro por Serviço (Top 6)",
                xaxis=dict(title="Margem %", ticksuffix='%'),
                yaxis=dict(title=""),
                height=280,
                margin=dict(t=50, b=30, l=120, r=20)
            )
            
            st.plotly_chart(fig_ranking, use_container_width=True)
        
        with col2:
            # Cards com destaques
            if ranking_ordenado:
                campeao = ranking_ordenado[0]
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 12px; border-radius: 10px; color: white; margin-bottom: 8px; text-align: center;">
                    <div style="font-size: 20px;">🏆</div>
                    <div style="font-size: 10px; opacity: 0.9;">CAMPEÃO</div>
                    <div style="font-size: 13px; font-weight: bold;">{campeao['servico']}</div>
                    <div style="font-size: 18px; font-weight: bold;">{campeao.get('margem_abc', 0)*100:.1f}%</div>
                    <div style="font-size: 10px;">R$ {campeao.get('lucro_abc', 0):,.0f}/ano</div>
                </div>
                """, unsafe_allow_html=True)
                
                if len(ranking_ordenado) > 1:
                    lanterna = ranking_ordenado[-1]
                    cor_lanterna = "#eb3349" if lanterna.get('margem_abc', 0) < 0.10 else "#f39c12"
                    st.markdown(f"""
                    <div style="background: linear-gradient(135deg, {cor_lanterna} 0%, #f45c43 100%); padding: 12px; border-radius: 10px; color: white; margin-bottom: 8px; text-align: center;">
                        <div style="font-size: 20px;">⚠️</div>
                        <div style="font-size: 10px; opacity: 0.9;">MENOR MARGEM</div>
                        <div style="font-size: 13px; font-weight: bold;">{lanterna['servico']}</div>
                        <div style="font-size: 18px; font-weight: bold;">{lanterna.get('margem_abc', 0)*100:.1f}%</div>
                        <div style="font-size: 10px;">R$ {lanterna.get('lucro_abc', 0):,.0f}/ano</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Legenda compacta
            st.markdown("""
            <div style="font-size: 10px; color: #666; padding: 3px;">
            🟢≥30% 🔵20-30% 🟡10-20%<br>🟠0-10% 🔴<0%
            </div>
            """, unsafe_allow_html=True)
        
        # ===== LINHA 3C: DONUT DE CONTRIBUIÇÃO + INSIGHTS =====
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # Donut mostrando contribuição de cada serviço para o lucro
            ranking_positivos = [r for r in ranking_abc if r.get('lucro_abc', 0) > 0]
            if ranking_positivos:
                # Top 5 + Outros
                ranking_sorted = sorted(ranking_positivos, key=lambda x: x.get('lucro_abc', 0), reverse=True)
                top5 = ranking_sorted[:5]
                outros_lucro = sum(r.get('lucro_abc', 0) for r in ranking_sorted[5:])
                
                labels_contrib = [r['servico'] for r in top5]
                valores_contrib = [r.get('lucro_abc', 0) for r in top5]
                
                if outros_lucro > 0:
                    labels_contrib.append("Outros")
                    valores_contrib.append(outros_lucro)
                
                cores_contrib = ['#27ae60', '#3498db', '#9b59b6', '#f39c12', '#e67e22', '#95a5a6']
                
                fig_contrib = go.Figure(data=[go.Pie(
                    labels=labels_contrib,
                    values=valores_contrib,
                    hole=0.5,
                    marker_colors=cores_contrib[:len(labels_contrib)],
                    textinfo='label+percent',
                    textfont_size=11,
                    insidetextorientation='radial'
                )])
                
                fig_contrib.update_layout(
                    title="🥧 Quem Gera o Lucro?",
                    height=280,
                    margin=dict(t=50, b=20, l=20, r=20),
                    showlegend=False,
                    annotations=[dict(text=f'R${lucro_total_abc/1000:.0f}k', x=0.5, y=0.5, font_size=14, showarrow=False)]
                )
                
                st.plotly_chart(fig_contrib, use_container_width=True)
        
        with col2:
            # Insights e Ações
            st.markdown("##### 💡 Insights Automáticos")
            
            if ranking_ordenado:
                campeao = ranking_ordenado[0]
                lanterna = ranking_ordenado[-1] if len(ranking_ordenado) > 1 else None
                
                # Calcular potencial
                potencial_campeao = campeao.get('lucro_abc', 0) * 0.2  # +20%
                
                st.markdown(f"""
                <div style="background: #e8f5e9; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #27ae60;">
                    <strong>📈 EXPANDIR:</strong> {campeao['servico']}<br>
                    <span style="font-size: 12px; color: #666;">+20% de atendimentos = +R$ {potencial_campeao:,.0f}/ano</span>
                </div>
                """, unsafe_allow_html=True)
                
                if lanterna and lanterna.get('margem_abc', 0) < 0.10:
                    st.markdown(f"""
                    <div style="background: #fff3e0; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #f39c12;">
                        <strong>💰 REAJUSTAR:</strong> {lanterna['servico']}<br>
                        <span style="font-size: 12px; color: #666;">Margem de {lanterna.get('margem_abc', 0)*100:.1f}% é baixa. Avaliar preço.</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                if overhead_total > 0:
                    overhead_mensal = overhead_total / 12
                    st.markdown(f"""
                    <div style="background: #ffebee; padding: 10px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #e74c3c;">
                        <strong>✂️ CUSTOS FIXOS:</strong> R$ {overhead_mensal:,.0f}/mês<br>
                        <span style="font-size: 12px; color: #666;">Renegociar contratos pode aumentar margem.</span>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div style="background: #e3f2fd; padding: 10px; border-radius: 8px; border-left: 4px solid #3498db;">
                    <strong>🔗 ANÁLISE COMPLETA:</strong><br>
                    <span style="font-size: 12px; color: #666;">Acesse <b>Custeio ABC</b> no menu para detalhes por sala e mês.</span>
                </div>
                """, unsafe_allow_html=True)
    else:
        # Sem dados - verificar motivo
        if ranking_abc and len(ranking_abc) > 0:
            # Há serviços mas sem receita
            st.warning("⚠️ **Dados incompletos para Custeio ABC**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                ##### 🔍 Por que está zerado?
                
                Os serviços existem, mas faltam dados para o cálculo:
                
                1. **Atendimentos:** Configure quantidade de sessões em **📅 Atendimentos**
                2. **Valores:** Configure preços dos serviços em **⚙️ Premissas**
                3. **Salas:** Configure m² em **🎯 Custeio ABC → Cadastro de Salas**
                """)
            
            with col2:
                st.markdown("""
                ##### 🔢 Serviços detectados:
                """)
                for r in ranking_abc[:6]:
                    receita = r.get('receita', 0)
                    status = "✅" if receita > 0 else "❌"
                    st.markdown(f"- {status} **{r['servico']}**: R$ {receita:,.0f}")
                
                if st.button("📅 Ir para Atendimentos", type="primary"):
                    st.session_state.pagina = "📅 Atendimentos"
                    st.rerun()
        else:
            # Sem serviços
            st.warning("⚠️ **Custeio ABC não configurado**")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                ##### 📋 O que é Custeio ABC?
                
                O **Custeio Baseado em Atividades** mostra o lucro **REAL** de cada serviço, 
                considerando todos os custos (inclusive aluguel, energia, etc).
                
                Diferente do DRE tradicional, o ABC revela quais serviços **realmente** 
                dão lucro e quais podem estar dando **prejuízo oculto**.
                """)
            
            with col2:
                st.markdown("""
                ##### 🚀 Como configurar?
                
                1. Acesse **🎯 Custeio ABC** no menu
                2. Configure as **salas** (m² e serviços atendidos)
                3. Os cálculos serão automáticos!
                
                ⏱️ **Tempo:** ~5 minutos
                """)
                
                if st.button("🎯 Ir para Custeio ABC", type="primary"):
                    st.session_state.pagina = "🎯 Custeio ABC"
                    st.rerun()
    
    st.markdown("---")
    
    # ========== LINHA 4: PARA ONDE VAI SEU DINHEIRO ==========
    st.markdown("#### 💸 Para Onde Vai Seu Dinheiro?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Donut de composição de custos
        custos_fixos_ano = sum(pe_anual.meses[m].custos_fixos for m in range(12))
        custos_var_ano = sum(pe_anual.meses[m].custos_variaveis for m in range(12))
        lucro_ano = sum(pe_anual.meses[m].ebitda for m in range(12))
        
        # Ajustar se lucro for negativo
        if lucro_ano < 0:
            valores_donut = [custos_fixos_ano, custos_var_ano, 0]
            labels_donut = ['💼 Custos Fixos', '📊 Custos Variáveis', '❌ Prejuízo']
            cores_donut = ['#e74c3c', '#f39c12', '#95a5a6']
        else:
            valores_donut = [custos_fixos_ano, custos_var_ano, lucro_ano]
            labels_donut = ['💼 Custos Fixos', '📊 Custos Variáveis', '💰 Lucro']
            cores_donut = ['#e74c3c', '#f39c12', '#27ae60']
        
        fig_donut = go.Figure(data=[go.Pie(
            labels=labels_donut,
            values=valores_donut,
            hole=0.5,
            marker_colors=cores_donut,
            textinfo='label+percent',
            textfont_size=12,
            insidetextorientation='radial'
        )])
        
        fig_donut.update_layout(
            title="📊 Composição da Receita",
            height=300,
            margin=dict(t=50, b=20),
            showlegend=False,
            annotations=[dict(text=f'R${receita_ano/1000:.0f}k', x=0.5, y=0.5, font_size=16, showarrow=False)]
        )
        
        st.plotly_chart(fig_donut, use_container_width=True)
    
    with col2:
        # Cards explicativos
        st.markdown("##### 📖 Entenda seus custos")
        
        pct_fixos = (custos_fixos_ano / receita_ano * 100) if receita_ano > 0 else 0
        pct_var = (custos_var_ano / receita_ano * 100) if receita_ano > 0 else 0
        pct_lucro = (lucro_ano / receita_ano * 100) if receita_ano > 0 else 0
        
        st.markdown(f"""
        <div style="background: #ffebee; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #e74c3c;">
            <strong>💼 Custos Fixos:</strong> R$ {custos_fixos_ano:,.0f} ({pct_fixos:.1f}%)<br>
            <span style="font-size: 12px; color: #666;">Aluguel, salários, energia... Você paga mesmo sem atender.</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown(f"""
        <div style="background: #fff3e0; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #f39c12;">
            <strong>📊 Custos Variáveis:</strong> R$ {custos_var_ano:,.0f} ({pct_var:.1f}%)<br>
            <span style="font-size: 12px; color: #666;">Impostos, taxas de cartão... Aumentam com o faturamento.</span>
        </div>
        """, unsafe_allow_html=True)
        
        cor_lucro_bg = "#e8f5e9" if lucro_ano >= 0 else "#ffebee"
        cor_lucro_borda = "#27ae60" if lucro_ano >= 0 else "#e74c3c"
        emoji_lucro = "💰" if lucro_ano >= 0 else "❌"
        texto_lucro = "Lucro" if lucro_ano >= 0 else "Prejuízo"
        
        st.markdown(f"""
        <div style="background: {cor_lucro_bg}; padding: 12px; border-radius: 8px; border-left: 4px solid {cor_lucro_borda};">
            <strong>{emoji_lucro} {texto_lucro}:</strong> R$ {abs(lucro_ano):,.0f} ({abs(pct_lucro):.1f}%)<br>
            <span style="font-size: 12px; color: #666;">O que sobra (ou falta) após pagar tudo.</span>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.caption("📊 Dashboard atualizado em tempo real com dados do motor de cálculo")


def _pagina_cenarios_consolidado():
    """Mostra comparativo de cenários para visão Consolidada (todas as filiais)"""
    from modules.cliente_manager import carregar_motores_cenarios
    import pandas as pd
    
    manager = st.session_state.cliente_manager
    cliente_id = st.session_state.cliente_id
    
    # Busca todas as filiais do cliente
    filiais = manager.listar_filiais(cliente_id)
    
    if not filiais:
        st.warning("⚠️ Nenhuma filial encontrada para este cliente.")
        return
    
    st.info("📊 **Visão Consolidada** - Soma de todas as filiais por cenário")
    
    # Carrega dados de cada filial
    dados_filiais = []
    totais = {"Pessimista": 0, "Conservador": 0, "Otimista": 0, "Aprovado": 0}
    
    for filial in filiais:
        filial_id = filial["id"]
        filial_nome = filial["nome"]
        
        try:
            resultado = carregar_motores_cenarios(manager, cliente_id, filial_id)
            motores = resultado.get("motores", {})
            cenario_aprovado = resultado.get("cenario_aprovado", None)
            
            # Calcula receita de cada cenário
            receitas = {}
            for cenario_nome, motor in motores.items():
                if motor:
                    receita = sum(
                        sum(motor.calcular_receita_servico_mes(s, m) for s in motor.servicos)
                        for m in range(12)
                    )
                    receitas[cenario_nome] = receita
                    totais[cenario_nome] += receita
            
            # Soma o cenário aprovado
            if cenario_aprovado and cenario_aprovado in receitas:
                totais["Aprovado"] += receitas[cenario_aprovado]
            
            dados_filiais.append({
                "Filial": filial_nome,
                "📉 Pessimista": f"R$ {receitas.get('Pessimista', 0)/1000:,.0f}k",
                "⚠️ Conservador": f"R$ {receitas.get('Conservador', 0)/1000:,.0f}k",
                "🚀 Otimista": f"R$ {receitas.get('Otimista', 0)/1000:,.0f}k",
                "✅ Aprovado": cenario_aprovado or "-"
            })
        except Exception as e:
            dados_filiais.append({
                "Filial": filial_nome,
                "📉 Pessimista": "R$ 0k",
                "⚠️ Conservador": "R$ 0k",
                "🚀 Otimista": "R$ 0k",
                "✅ Aprovado": "-"
            })
    
    # ===== CARDS DE TOTAIS (Componentes Nativos) =====
    st.subheader("📊 Totais Consolidados")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📉 Pessimista", f"R$ {totais['Pessimista']/1000:,.0f}k")
    
    with col2:
        st.metric("⚠️ Conservador", f"R$ {totais['Conservador']/1000:,.0f}k")
    
    with col3:
        st.metric("🚀 Otimista", f"R$ {totais['Otimista']/1000:,.0f}k")
    
    with col4:
        st.metric("✅ Total Aprovado", f"R$ {totais['Aprovado']/1000:,.0f}k")
    
    st.divider()
    
    # ===== TABELA POR FILIAL (DataFrame nativo) =====
    st.subheader("🏢 Detalhamento por Filial")
    
    if dados_filiais:
        df = pd.DataFrame(dados_filiais)
        st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Linha de totais
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.write("**TOTAL**")
    with col2:
        st.write(f"**R$ {totais['Pessimista']/1000:,.0f}k**")
    with col3:
        st.write(f"**R$ {totais['Conservador']/1000:,.0f}k**")
    with col4:
        st.write(f"**R$ {totais['Otimista']/1000:,.0f}k**")
    
    st.success(f"✅ **TOTAL APROVADO: R$ {totais['Aprovado']/1000:,.0f}k**")
    
    st.divider()
    st.caption("💡 Para aprovar um cenário, selecione a filial específica e clique em '🔒 Aprovar Cenário'")


def pagina_cenarios():
    """Página de Comparativo de Cenários - Usa 3 motores independentes"""
    render_header()
    
    st.markdown("## 🎯 Arena dos Cenários")
    st.caption("Compare Pessimista, Conservador e Otimista lado a lado")
    
    # ===== MODO CONSOLIDADO =====
    if st.session_state.get('filial_id') == 'consolidado':
        _pagina_cenarios_consolidado()
        return
    
    # Pega os 3 motores
    motores = st.session_state.get('motores_cenarios', {})
    
    if not motores or len(motores) < 3:
        st.warning("⚠️ Motores de cenários não carregados. Selecione uma filial.")
        return
    
    motor_cons = motores.get("Conservador")
    motor_pess = motores.get("Pessimista")
    motor_otim = motores.get("Otimista")
    
    if not motor_cons or not motor_pess or not motor_otim:
        st.error("❌ Erro ao carregar motores de cenário")
        return
    
    meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    # ===== CONSERVADOR (Base) - Motor próprio =====
    receitas_cons = [sum(motor_cons.calcular_receita_servico_mes(s, m) for s in motor_cons.servicos) for m in range(12)]
    total_cons = sum(receitas_cons)
    despesas_cons = motor_cons.calcular_despesas_fixas()
    total_desp_cons = sum(despesas_cons.get("Total Despesas Fixas", [0]*12))
    lucro_cons = total_cons - total_desp_cons
    
    # ===== PESSIMISTA - Motor próprio =====
    receitas_pess = [sum(motor_pess.calcular_receita_servico_mes(s, m) for s in motor_pess.servicos) for m in range(12)]
    total_pess = sum(receitas_pess)
    despesas_pess = motor_pess.calcular_despesas_fixas()
    total_desp_pess = sum(despesas_pess.get("Total Despesas Fixas", [0]*12))
    lucro_pess = total_pess - total_desp_pess
    
    # ===== OTIMISTA - Motor próprio =====
    receitas_otim = [sum(motor_otim.calcular_receita_servico_mes(s, m) for s in motor_otim.servicos) for m in range(12)]
    total_otim = sum(receitas_otim)
    despesas_otim = motor_otim.calcular_despesas_fixas()
    total_desp_otim = sum(despesas_otim.get("Total Despesas Fixas", [0]*12))
    lucro_otim = total_otim - total_desp_otim
    
    # Variações em relação ao Conservador
    var_pess = ((total_pess / total_cons) - 1) * 100 if total_cons > 0 else 0
    var_otim = ((total_otim / total_cons) - 1) * 100 if total_cons > 0 else 0
    
    # ===== CENÁRIO APROVADO =====
    cenario_aprovado = st.session_state.get('cenario_aprovado', None)
    
    col_info, col_aprovacao = st.columns([3, 1])
    
    with col_info:
        if cenario_aprovado:
            emoji_aprovado = {"Pessimista": "📉", "Conservador": "⚠️", "Otimista": "🚀"}.get(cenario_aprovado, "✅")
            st.success(f"✅ **CENÁRIO APROVADO:** {emoji_aprovado} {cenario_aprovado}")
        else:
            st.info("💡 **Dica:** Para alterar as premissas de cada cenário, vá em **⚙️ Premissas** e selecione o cenário no dropdown \"Editando cenário\"")
    
    with col_aprovacao:
        if st.button("🔒 Aprovar Cenário", use_container_width=True, type="primary"):
            st.session_state.show_modal_aprovacao = True
    
    # ===== MODAL DE APROVAÇÃO =====
    if st.session_state.get('show_modal_aprovacao', False):
        with st.container():
            st.markdown("---")
            st.markdown("### 🔐 Aprovar Cenário")
            st.caption("Selecione o cenário a ser aprovado e confirme com a senha de administrador")
            
            col_a, col_b = st.columns(2)
            with col_a:
                opcoes_cenario = ["Nenhum (remover aprovação)", "Pessimista", "Conservador", "Otimista"]
                idx_atual = 0
                if cenario_aprovado in opcoes_cenario:
                    idx_atual = opcoes_cenario.index(cenario_aprovado)
                cenario_selecionado = st.selectbox(
                    "Cenário para aprovar",
                    opcoes_cenario,
                    index=idx_atual,
                    key="select_aprovacao_cenario"
                )
            with col_b:
                senha_aprovacao = st.text_input("Senha de Admin", type="password", key="senha_aprovacao")
            
            col_confirmar, col_cancelar = st.columns(2)
            with col_confirmar:
                if st.button("✅ Confirmar", use_container_width=True, type="primary"):
                    # Verifica senha usando o sistema de autenticação
                    from auth import verify_password, get_supabase_client
                    
                    senha_valida = False
                    try:
                        supabase = get_supabase_client()
                        if supabase:
                            # Busca usuários admin
                            response = supabase.table("users").select("password_hash, role").eq("role", "admin").execute()
                            if response.data:
                                # Verifica se a senha corresponde a algum admin
                                for admin in response.data:
                                    if verify_password(senha_aprovacao, admin["password_hash"]):
                                        senha_valida = True
                                        break
                    except Exception as e:
                        # Fallback para senha padrão se der erro
                        senha_valida = (senha_aprovacao == "admin123")
                    
                    if senha_valida:
                        novo_aprovado = None if cenario_selecionado == "Nenhum (remover aprovação)" else cenario_selecionado
                        st.session_state.cenario_aprovado = novo_aprovado
                        
                        # Salva imediatamente
                        from modules.cliente_manager import salvar_motores_cenarios
                        salvar_motores_cenarios(
                            st.session_state.cliente_manager,
                            st.session_state.cliente_id,
                            st.session_state.filial_id,
                            st.session_state.motores_cenarios,
                            st.session_state.get('cenario_ativo', 'Conservador'),
                            st.session_state.get('usar_cenarios', True),
                            novo_aprovado
                        )
                        
                        st.session_state.show_modal_aprovacao = False
                        if novo_aprovado:
                            st.success(f"✅ Cenário '{novo_aprovado}' aprovado com sucesso!")
                        else:
                            st.info("Aprovação removida")
                        st.rerun()
                    else:
                        st.error("❌ Senha incorreta!")
            with col_cancelar:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.show_modal_aprovacao = False
                    st.rerun()
            st.markdown("---")
    
    # ========== 3 CARDS GRANDES (Componentes Nativos) ==========
    col1, col2, col3 = st.columns(3)
    
    with col1:
        with st.container(border=True):
            if cenario_aprovado == 'Pessimista':
                st.success("✅ APROVADO")
            st.markdown("### 📉 PESSIMISTA")
            st.caption("Cenário de Crise")
            st.divider()
            st.metric("Receita Anual", f"R$ {total_pess/1000:,.0f}k", f"{var_pess:+.1f}% vs Base")
            st.divider()
            delta_color = "inverse" if lucro_pess < 0 else "normal"
            st.metric("Resultado", f"R$ {lucro_pess/1000:,.0f}k", delta_color=delta_color)
    
    with col2:
        with st.container(border=True):
            if cenario_aprovado == 'Conservador':
                st.success("✅ APROVADO")
            st.markdown("### ⚠️ CONSERVADOR")
            st.caption("⭐ Base de Referência")
            st.divider()
            st.metric("Receita Anual", f"R$ {total_cons/1000:,.0f}k", "Base")
            st.divider()
            delta_color = "inverse" if lucro_cons < 0 else "normal"
            st.metric("Resultado", f"R$ {lucro_cons/1000:,.0f}k", delta_color=delta_color)
    
    with col3:
        with st.container(border=True):
            if cenario_aprovado == 'Otimista':
                st.success("✅ APROVADO")
            st.markdown("### 🚀 OTIMISTA")
            st.caption("Cenário Favorável")
            st.divider()
            st.metric("Receita Anual", f"R$ {total_otim/1000:,.0f}k", f"{var_otim:+.1f}% vs Base")
            st.divider()
            delta_color = "inverse" if lucro_otim < 0 else "normal"
            st.metric("Resultado", f"R$ {lucro_otim/1000:,.0f}k", delta_color=delta_color)
    
    st.write("")
    
    # ========== ABAS COM GRÁFICOS ==========
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Comparativo Visual", "📈 Evolução Mensal", "🔍 Detalhes por Cenário", "📅 vs Ano Anterior"])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de barras - Receita
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=['📉 Pessimista', '⚠️ Conservador', '🚀 Otimista'],
                y=[total_pess, total_cons, total_otim],
                marker_color=['#dc3545', '#ffc107', '#28a745'],
                text=[f'R$ {total_pess/1000:,.0f}k', f'R$ {total_cons/1000:,.0f}k', f'R$ {total_otim/1000:,.0f}k'],
                textposition='outside'
            ))
            fig.update_layout(
                title="💰 Receita Anual por Cenário",
                height=350,
                showlegend=False,
                yaxis_title="Receita (R$)"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Gráfico de barras - Resultado
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=['📉 Pessimista', '⚠️ Conservador', '🚀 Otimista'],
                y=[lucro_pess, lucro_cons, lucro_otim],
                marker_color=['#dc3545' if lucro_pess < 0 else '#28a745', 
                              '#dc3545' if lucro_cons < 0 else '#28a745',
                              '#dc3545' if lucro_otim < 0 else '#28a745'],
                text=[f'R$ {lucro_pess/1000:,.0f}k', f'R$ {lucro_cons/1000:,.0f}k', f'R$ {lucro_otim/1000:,.0f}k'],
                textposition='outside'
            ))
            fig.update_layout(
                title="📊 Resultado Anual por Cenário",
                height=350,
                showlegend=False,
                yaxis_title="Resultado (R$)"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Tabela resumo
        st.markdown("### 📋 Resumo Comparativo")
        
        import pandas as pd
        df_resumo = pd.DataFrame({
            "Métrica": ["Receita Anual", "Despesas Anuais", "Resultado", "Margem %", "Ticket Médio/Mês"],
            "📉 Pessimista": [
                f"R$ {total_pess:,.0f}",
                f"R$ {total_desp_pess:,.0f}",
                f"R$ {lucro_pess:,.0f}",
                f"{(lucro_pess/total_pess*100) if total_pess > 0 else 0:.1f}%",
                f"R$ {total_pess/12:,.0f}"
            ],
            "⚠️ Conservador": [
                f"R$ {total_cons:,.0f}",
                f"R$ {total_desp_cons:,.0f}",
                f"R$ {lucro_cons:,.0f}",
                f"{(lucro_cons/total_cons*100) if total_cons > 0 else 0:.1f}%",
                f"R$ {total_cons/12:,.0f}"
            ],
            "🚀 Otimista": [
                f"R$ {total_otim:,.0f}",
                f"R$ {total_desp_otim:,.0f}",
                f"R$ {lucro_otim:,.0f}",
                f"{(lucro_otim/total_otim*100) if total_otim > 0 else 0:.1f}%",
                f"R$ {total_otim/12:,.0f}"
            ]
        })
        st.dataframe(df_resumo, use_container_width=True, hide_index=True)
    
    with tab2:
        # Gráfico de evolução mensal
        fig = go.Figure()
        
        # Área Otimista
        fig.add_trace(go.Scatter(
            x=meses_nomes, y=receitas_otim,
            fill='tozeroy', name='🚀 Otimista',
            fillcolor='rgba(40, 167, 69, 0.2)',
            line=dict(color='#28a745', width=3)
        ))
        
        # Área Conservador
        fig.add_trace(go.Scatter(
            x=meses_nomes, y=receitas_cons,
            fill='tozeroy', name='⚠️ Conservador',
            fillcolor='rgba(255, 193, 7, 0.3)',
            line=dict(color='#ffc107', width=3)
        ))
        
        # Linha Pessimista
        fig.add_trace(go.Scatter(
            x=meses_nomes, y=receitas_pess,
            name='📉 Pessimista',
            line=dict(color='#dc3545', width=3, dash='dash')
        ))
        
        fig.update_layout(
            title="📈 Evolução Mensal da Receita por Cenário",
            height=450,
            yaxis_title="Receita (R$)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            hovermode='x unified'
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabela mês a mês
        with st.expander("📋 Ver tabela mês a mês"):
            dados_mes = []
            for m in range(12):
                dados_mes.append({
                    "Mês": meses_nomes[m],
                    "📉 Pessimista": f"R$ {receitas_pess[m]:,.0f}",
                    "⚠️ Conservador": f"R$ {receitas_cons[m]:,.0f}",
                    "🚀 Otimista": f"R$ {receitas_otim[m]:,.0f}"
                })
            df_mes = pd.DataFrame(dados_mes)
            st.dataframe(df_mes, use_container_width=True, hide_index=True)
    
    with tab3:
        # Nova aba: Detalhes por cenário - mostra diferenças nas premissas
        st.markdown("### 🔍 Diferenças nas Premissas")
        st.caption("Compare as principais premissas entre os 3 cenários")
        
        # Comparar premissas macro
        st.markdown("#### 📊 Premissas Macroeconômicas")
        df_macro = pd.DataFrame({
            "Premissa": ["IPCA", "IGP-M", "Dissídio", "Reaj. Tarifas", "Reaj. Contratos"],
            "📉 Pessimista": [
                f"{motor_pess.macro.ipca*100:.1f}%",
                f"{motor_pess.macro.igpm*100:.1f}%",
                f"{motor_pess.macro.dissidio*100:.1f}%",
                f"{motor_pess.macro.reajuste_tarifas*100:.1f}%",
                f"{motor_pess.macro.reajuste_contratos*100:.1f}%"
            ],
            "⚠️ Conservador": [
                f"{motor_cons.macro.ipca*100:.1f}%",
                f"{motor_cons.macro.igpm*100:.1f}%",
                f"{motor_cons.macro.dissidio*100:.1f}%",
                f"{motor_cons.macro.reajuste_tarifas*100:.1f}%",
                f"{motor_cons.macro.reajuste_contratos*100:.1f}%"
            ],
            "🚀 Otimista": [
                f"{motor_otim.macro.ipca*100:.1f}%",
                f"{motor_otim.macro.igpm*100:.1f}%",
                f"{motor_otim.macro.dissidio*100:.1f}%",
                f"{motor_otim.macro.reajuste_tarifas*100:.1f}%",
                f"{motor_otim.macro.reajuste_contratos*100:.1f}%"
            ]
        })
        st.dataframe(df_macro, use_container_width=True, hide_index=True)
        
        # Comparar serviços (sessões)
        st.markdown("#### 🩺 Sessões por Serviço (Base Mensal)")
        dados_servicos = []
        for nome_srv in motor_cons.servicos.keys():
            srv_cons = motor_cons.servicos.get(nome_srv)
            srv_pess = motor_pess.servicos.get(nome_srv)
            srv_otim = motor_otim.servicos.get(nome_srv)
            
            if srv_cons:
                dados_servicos.append({
                    "Serviço": nome_srv,
                    "📉 Pessimista": f"{srv_pess.sessoes_mes_base if srv_pess else 0:,.0f}",
                    "⚠️ Conservador": f"{srv_cons.sessoes_mes_base:,.0f}",
                    "🚀 Otimista": f"{srv_otim.sessoes_mes_base if srv_otim else 0:,.0f}"
                })
        
        if dados_servicos:
            df_servicos = pd.DataFrame(dados_servicos)
            st.dataframe(df_servicos, use_container_width=True, hide_index=True)
        
        # Comparar despesas principais
        st.markdown("#### 💰 Despesas Principais (Mensal Base)")
        dados_despesas = []
        despesas_principais = list(motor_cons.despesas_fixas.keys())[:5]  # Top 5
        for nome_desp in despesas_principais:
            desp_cons = motor_cons.despesas_fixas.get(nome_desp)
            desp_pess = motor_pess.despesas_fixas.get(nome_desp)
            desp_otim = motor_otim.despesas_fixas.get(nome_desp)
            
            if desp_cons:
                dados_despesas.append({
                    "Despesa": nome_desp,
                    "📉 Pessimista": f"R$ {desp_pess.valor_mensal if desp_pess else 0:,.0f}",
                    "⚠️ Conservador": f"R$ {desp_cons.valor_mensal:,.0f}",
                    "🚀 Otimista": f"R$ {desp_otim.valor_mensal if desp_otim else 0:,.0f}"
                })
        
        if dados_despesas:
            df_despesas = pd.DataFrame(dados_despesas)
            st.dataframe(df_despesas, use_container_width=True, hide_index=True)
    
    with tab4:
        # Comparativo com ano anterior
        usar_comp = getattr(motor_cons, 'usar_comparativo_anterior', False)
        ano_ant = getattr(motor_cons, 'ano_anterior', 2025)
        fat_anterior = getattr(motor_cons, 'faturamento_anterior', [0.0] * 12)
        total_anterior = sum(fat_anterior) if fat_anterior else 0
        
        if usar_comp and total_anterior > 0:
            var_ant_pess = ((total_pess / total_anterior) - 1) * 100
            var_ant_cons = ((total_cons / total_anterior) - 1) * 100
            var_ant_otim = ((total_otim / total_anterior) - 1) * 100
            
            st.markdown(f"### 📅 Crescimento vs {ano_ant}")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f"""
                <div style="background: #f8f9fa; padding: 20px; border-radius: 15px; text-align: center;">
                    <div style="font-size: 14px; color: #666;">📅 Real {ano_ant}</div>
                    <div style="font-size: 26px; font-weight: bold;">R$ {total_anterior/1000:,.0f}k</div>
                    <div style="font-size: 12px; color: #999;">Base</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                cor = "#28a745" if var_ant_pess > 0 else "#dc3545"
                emoji = "📈" if var_ant_pess > 0 else "📉"
                st.markdown(f"""
                <div style="background: #ffebee; padding: 20px; border-radius: 15px; text-align: center; border-left: 4px solid #dc3545;">
                    <div style="font-size: 14px; color: #666;">📉 Pessimista</div>
                    <div style="font-size: 26px; font-weight: bold; color: {cor};">{emoji} {var_ant_pess:+.1f}%</div>
                    <div style="font-size: 12px; color: #999;">R$ {total_pess - total_anterior:+,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                cor = "#28a745" if var_ant_cons > 0 else "#dc3545"
                emoji = "📈" if var_ant_cons > 0 else "📉"
                st.markdown(f"""
                <div style="background: #fff8e1; padding: 20px; border-radius: 15px; text-align: center; border-left: 4px solid #ffc107;">
                    <div style="font-size: 14px; color: #666;">⚠️ Conservador</div>
                    <div style="font-size: 26px; font-weight: bold; color: {cor};">{emoji} {var_ant_cons:+.1f}%</div>
                    <div style="font-size: 12px; color: #999;">R$ {total_cons - total_anterior:+,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                cor = "#28a745" if var_ant_otim > 0 else "#dc3545"
                emoji = "📈" if var_ant_otim > 0 else "📉"
                st.markdown(f"""
                <div style="background: #e8f5e9; padding: 20px; border-radius: 15px; text-align: center; border-left: 4px solid #28a745;">
                    <div style="font-size: 14px; color: #666;">🚀 Otimista</div>
                    <div style="font-size: 26px; font-weight: bold; color: {cor};">{emoji} {var_ant_otim:+.1f}%</div>
                    <div style="font-size: 12px; color: #999;">R$ {total_otim - total_anterior:+,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Gráfico comparativo
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=meses_nomes, y=fat_anterior,
                name=f'📅 Real {ano_ant}',
                line=dict(color='#6c757d', width=4, dash='dot'),
                mode='lines+markers'
            ))
            
            fig.add_trace(go.Scatter(
                x=meses_nomes, y=receitas_pess,
                name='📉 Pessimista 2026',
                line=dict(color='#dc3545', width=2)
            ))
            
            fig.add_trace(go.Scatter(
                x=meses_nomes, y=receitas_cons,
                name='⚠️ Conservador 2026',
                line=dict(color='#ffc107', width=2)
            ))
            
            fig.add_trace(go.Scatter(
                x=meses_nomes, y=receitas_otim,
                name='🚀 Otimista 2026',
                line=dict(color='#28a745', width=2)
            ))
            
            fig.update_layout(
                title=f"📈 {ano_ant} (Real) vs 2026 (Projetado)",
                height=450,
                yaxis_title="Receita (R$)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        elif usar_comp and total_anterior == 0:
            st.warning(f"⚠️ Preencha o faturamento de {ano_ant} em **Premissas → Cenários** e clique em **Salvar**")
        
        else:
            st.info("💡 Habilite o comparativo com ano anterior em **Premissas → Cenários**")
            
            st.markdown("""
            ### Como habilitar:
            1. Vá em **⚙️ Premissas**
            2. Clique na aba **🎯 Cenários**
            3. Marque **[✓] Usar comparativo**
            4. Preencha o faturamento mês a mês
            5. Clique **💾 Salvar Faturamento Anterior**
            """)
    
    st.markdown("---")
    st.caption("🎯 Edite cada cenário em **Premissas** → Selecione o cenário no dropdown")


def pagina_taxa_ocupacao():
    """Página de análise de taxa de ocupação - modelo de gargalo"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>📊 Taxa de Ocupação</h3></div>', unsafe_allow_html=True)
    st.caption("Análise de gargalo: Profissional vs Sala")
    
    motor = st.session_state.motor
    
    # Calcular ocupação anual
    analise_anual = motor.calcular_ocupacao_anual()
    
    # Cards principais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        taxa_prof = analise_anual.media_taxa_profissional * 100
        cor_prof = "success" if taxa_prof < 70 else ("warning" if taxa_prof < 90 else "danger")
        render_metric_card("Taxa Profissional", f"{taxa_prof:.1f}%", card_type=cor_prof)
    
    with col2:
        taxa_sala = analise_anual.media_taxa_sala * 100
        cor_sala = "success" if taxa_sala < 70 else ("warning" if taxa_sala < 90 else "danger")
        render_metric_card("Taxa Sala", f"{taxa_sala:.1f}%", card_type=cor_sala)
    
    with col3:
        gargalo = analise_anual.gargalo_predominante
        emoji = "🏥" if gargalo == "Sala" else "👥"
        render_metric_card("Gargalo", f"{emoji} {gargalo}", card_type="warning" if taxa_sala > 80 or taxa_prof > 80 else "default")
    
    with col4:
        render_metric_card("Sessões/Ano", f"{analise_anual.total_sessoes_ano:,.0f}", card_type="default")
    
    st.markdown("---")
    
    # Abas
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Visão Geral", "👥 Escala Profissionais", "⚙️ Parâmetros", "📋 Detalhamento"])
    
    # ========== TAB 1: VISÃO GERAL ==========
    with tab1:
        st.markdown("### Evolução Mensal")
        
        # Preparar dados para gráfico
        meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        # Gráfico de linhas
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=[m.taxa_ocupacao_profissional * 100 for m in analise_anual.meses],
            name="Profissional",
            line=dict(color="#3498db", width=3),
            mode="lines+markers"
        ))
        
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=[m.taxa_ocupacao_sala * 100 for m in analise_anual.meses],
            name="Sala",
            line=dict(color="#e74c3c", width=3),
            mode="lines+markers"
        ))
        
        # Linhas de referência
        fig.add_hline(y=70, line_dash="dash", line_color="orange", annotation_text="Atenção (70%)")
        fig.add_hline(y=90, line_dash="dash", line_color="red", annotation_text="Crítico (90%)")
        
        fig.update_layout(
            title="Taxa de Ocupação por Mês",
            xaxis_title="Mês",
            yaxis_title="Taxa de Ocupação (%)",
            yaxis=dict(range=[0, 110]),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabela resumo mensal
        st.markdown("### Resumo Mensal")
        
        dados_tabela = []
        for i, m in enumerate(analise_anual.meses):
            dados_tabela.append({
                "Mês": meses_nomes[i],
                "Cap. Prof (h)": f"{m.capacidade_profissional:,.0f}",
                "Cap. Sala (h)": f"{m.capacidade_sala:,.0f}",
                "Dem. Prof (h)": f"{m.demanda_profissional:,.1f}",
                "Dem. Sala (h)": f"{m.demanda_sala:,.1f}",
                "Taxa Prof": f"{m.taxa_ocupacao_profissional*100:.1f}%",
                "Taxa Sala": f"{m.taxa_ocupacao_sala*100:.1f}%",
                "Gargalo": m.gargalo,
                "Status": f"{m.status_emoji}"
            })
        
        st.dataframe(dados_tabela, use_container_width=True, hide_index=True)
        
        # Diagnóstico
        st.markdown("### 💡 Diagnóstico")
        
        ultimo_mes = analise_anual.meses[-1] if analise_anual.meses else None
        if ultimo_mes:
            status_cor = {
                "ociosidade": "🟢",
                "saudavel": "🟢", 
                "atencao": "🟡",
                "critico": "🔴"
            }
            
            st.info(f"""
            **Status Atual:** {status_cor.get(ultimo_mes.status, '⚪')} {ultimo_mes.status_texto}
            
            **Gargalo Principal:** {analise_anual.gargalo_predominante}
            
            **Recomendação:** {ultimo_mes.recomendacao}
            """)
    
    # ========== TAB 2: ESCALA PROFISSIONAIS ==========
    with tab2:
        st.markdown("### Escala Semanal dos Profissionais")
        st.caption("Horas de permanência na clínica por dia da semana")
        
        # Tabela de escalas
        dias = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado"]
        dias_display = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]
        
        dados_escala = []
        total_horas = 0
        profissionais_sem_escala = []
        
        for nome, fisio in motor.fisioterapeutas.items():
            if not fisio.ativo:
                continue
            
            linha = {"Profissional": nome}
            for d, d_display in zip(dias, dias_display):
                linha[d_display] = fisio.escala_semanal.get(d, 0)
            linha["Total/Sem"] = fisio.horas_semana
            linha["Horas/Mês"] = fisio.horas_mes
            dados_escala.append(linha)
            total_horas += fisio.horas_mes
            
            # Verificar se escala está zerada
            if fisio.horas_semana == 0:
                profissionais_sem_escala.append(nome)
        
        # Alerta se houver profissionais sem escala preenchida
        if profissionais_sem_escala:
            st.warning(f"""
            ⚠️ **Atenção:** {len(profissionais_sem_escala)} profissional(is) sem escala preenchida!
            
            Preencha a escala semanal para calcular corretamente a taxa de ocupação.
            
            Profissionais pendentes: **{', '.join(profissionais_sem_escala)}**
            """)
        
        # Ordenar por horas/mês decrescente
        dados_escala.sort(key=lambda x: x["Horas/Mês"], reverse=True)
        
        st.dataframe(dados_escala, use_container_width=True, hide_index=True)
        
        st.markdown(f"**Total Capacidade Profissional:** {total_horas:,.0f} horas/mês")
        
        # Edição de escala
        st.markdown("---")
        st.markdown("### ✏️ Editar Escala")
        
        fisio_selecionado = st.selectbox(
            "Selecione o profissional",
            options=list(motor.fisioterapeutas.keys())
        )
        
        if fisio_selecionado:
            fisio = motor.fisioterapeutas[fisio_selecionado]
            
            st.caption(f"Cargo: {fisio.cargo} | Nível: {fisio.nivel}")
            
            # Alerta se escala do profissional selecionado estiver zerada
            if fisio.horas_semana == 0:
                st.info("ℹ️ **Preencha a escala semanal** informando as horas de trabalho em cada dia da semana.")
            
            cols = st.columns(6)
            nova_escala = {}
            
            for i, (d, d_display) in enumerate(zip(dias, dias_display)):
                with cols[i]:
                    nova_escala[d] = st.number_input(
                        d_display,
                        min_value=0.0,
                        max_value=12.0,
                        value=float(fisio.escala_semanal.get(d, 0)),
                        step=0.5,
                        key=f"escala_{fisio_selecionado}_{d}"
                    )
            
            col_btn1, col_btn2 = st.columns([1, 3])
            with col_btn1:
                if st.button("💾 Salvar Escala", use_container_width=True):
                    fisio.escala_semanal = nova_escala
                    # Persistir no JSON do cliente
                    salvar_filial_atual()
                    st.success(f"✅ Escala de {fisio_selecionado} atualizada e salva!")
                    st.rerun()
            
            # Preview
            nova_semana = sum(nova_escala.values())
            novo_mes = nova_semana * 4
            st.caption(f"Preview: {nova_semana:.1f}h/semana = {novo_mes:.0f}h/mês")
    
    # ========== TAB 3: PARÂMETROS (SOMENTE LEITURA) ==========
    with tab3:
        st.info("ℹ️ **Estes parâmetros são definidos em ⚙️ Premissas.** Para editar, acesse o menu Premissas → Operacionais e Serviços.")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏥 Parâmetros Operacionais")
            
            # Capacidade calculada
            cap_sala = (motor.operacional.num_salas * 
                       motor.operacional.horas_atendimento_dia * 
                       motor.operacional.dias_uteis_mes)
            
            # Exibir como métricas (somente leitura)
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("Nº Salas", f"{motor.operacional.num_salas}")
            with col_m2:
                st.metric("Horas/Dia", f"{motor.operacional.horas_atendimento_dia}h")
            with col_m3:
                st.metric("Dias/Mês", f"{motor.operacional.dias_uteis_mes}")
            
            st.markdown("---")
            st.metric("Capacidade Total Salas/Mês", f"{cap_sala:,} horas")
            st.caption(f"Cálculo: {motor.operacional.num_salas} salas × {motor.operacional.horas_atendimento_dia}h/dia × {motor.operacional.dias_uteis_mes} dias")
        
        with col2:
            st.markdown("### 📋 Serviços Cadastrados")
            
            # Tabela de serviços (somente leitura)
            dados_servicos = []
            for nome, servico in motor.servicos.items():
                dados_servicos.append({
                    "Serviço": nome,
                    "Duração": f"{servico.duracao_minutos} min",
                    "Horas": f"{servico.duracao_horas:.2f}h",
                    "Usa Sala": "✅ Sim" if servico.usa_sala else "❌ Não"
                })
            
            if dados_servicos:
                st.dataframe(dados_servicos, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhum serviço cadastrado.")
            
            st.caption("💡 Serviços marcados como 'Não usa sala' (ex: Domiciliar) não consomem capacidade de sala.")
    
    # ========== TAB 4: DETALHAMENTO ==========
    with tab4:
        # Selecionar mês
        mes_selecionado = st.selectbox(
            "📅 Selecione o Mês",
            options=list(range(12)),
            format_func=lambda x: meses_nomes[x],
            key="detalhe_mes"
        )
        
        analise_mes = analise_anual.meses[mes_selecionado]
        
        # ===== RESUMO DO MÊS COM CORES =====
        st.markdown(f"### 📊 Resumo de {meses_nomes[mes_selecionado]}")
        
        # Determinar cor do status
        taxa_efetiva = analise_mes.taxa_ocupacao_efetiva * 100
        if taxa_efetiva < 50:
            status_cor = "🟢"
            status_texto = "Ociosidade Alta"
            status_dica = "Há margem para crescer a carteira de pacientes"
        elif taxa_efetiva < 70:
            status_cor = "🟢"
            status_texto = "Saudável"
            status_dica = "Operação equilibrada com margem de segurança"
        elif taxa_efetiva < 90:
            status_cor = "🟡"
            status_texto = "Atenção"
            status_dica = "Monitorar de perto, considerar expansão"
        else:
            status_cor = "🔴"
            status_texto = "Crítico"
            status_dica = "Risco de sobrecarga, ação imediata necessária"
        
        # Cards principais com destaque
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🎯 Sessões Previstas", f"{analise_mes.total_sessoes:.0f}")
        with col2:
            st.metric("👥 Demanda Profissional", f"{analise_mes.demanda_profissional:.1f}h")
        with col3:
            st.metric("🏥 Demanda Sala", f"{analise_mes.demanda_sala:.1f}h")
        with col4:
            st.metric(f"{status_cor} Taxa Efetiva", f"{taxa_efetiva:.1f}%")
        
        # Box de status
        if taxa_efetiva >= 90:
            st.error(f"⚠️ **Status: {status_texto}** - {status_dica}")
        elif taxa_efetiva >= 70:
            st.warning(f"⚡ **Status: {status_texto}** - {status_dica}")
        else:
            st.success(f"✅ **Status: {status_texto}** - {status_dica}")
        
        st.markdown("---")
        
        # ===== CAPACIDADE vs DEMANDA (VISUAL) =====
        st.markdown("### 📈 Capacidade vs Demanda")
        
        col_cap1, col_cap2 = st.columns(2)
        
        with col_cap1:
            st.markdown("#### 👥 Profissionais")
            cap_prof = analise_mes.capacidade_profissional
            dem_prof = analise_mes.demanda_profissional
            taxa_prof = analise_mes.taxa_ocupacao_profissional * 100
            
            # Barra de progresso visual
            st.progress(min(taxa_prof/100, 1.0))
            
            col_p1, col_p2, col_p3 = st.columns(3)
            with col_p1:
                st.metric("Capacidade", f"{cap_prof:.0f}h")
            with col_p2:
                st.metric("Demanda", f"{dem_prof:.1f}h")
            with col_p3:
                cor = "🟢" if taxa_prof < 70 else ("🟡" if taxa_prof < 90 else "🔴")
                st.metric("Ocupação", f"{cor} {taxa_prof:.1f}%")
            
            ociosidade_prof = max(0, cap_prof - dem_prof)
            st.caption(f"💡 Horas disponíveis: **{ociosidade_prof:.0f}h** ({(1-taxa_prof/100)*100:.0f}%)")
        
        with col_cap2:
            st.markdown("#### 🏥 Salas")
            cap_sala = analise_mes.capacidade_sala
            dem_sala = analise_mes.demanda_sala
            taxa_sala = analise_mes.taxa_ocupacao_sala * 100
            
            # Barra de progresso visual
            st.progress(min(taxa_sala/100, 1.0))
            
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                st.metric("Capacidade", f"{cap_sala:.0f}h")
            with col_s2:
                st.metric("Demanda", f"{dem_sala:.1f}h")
            with col_s3:
                cor = "🟢" if taxa_sala < 70 else ("🟡" if taxa_sala < 90 else "🔴")
                st.metric("Ocupação", f"{cor} {taxa_sala:.1f}%")
            
            ociosidade_sala = max(0, cap_sala - dem_sala)
            st.caption(f"💡 Horas disponíveis: **{ociosidade_sala:.0f}h** ({(1-taxa_sala/100)*100:.0f}%)")
        
        # Identificar gargalo
        st.markdown("---")
        gargalo = analise_mes.gargalo
        if gargalo == "Sala":
            st.info(f"🏥 **Gargalo: SALA** - A capacidade de sala limita o crescimento antes dos profissionais")
        else:
            st.info(f"👥 **Gargalo: PROFISSIONAL** - A capacidade dos profissionais limita o crescimento antes das salas")
        
        st.markdown("---")
        
        # ===== DETALHAMENTO POR PROFISSIONAL =====
        st.markdown("### 👥 Detalhamento por Profissional")
        
        dados_prof = []
        for nome, horas in analise_mes.demanda_por_profissional.items():
            fisio = motor.fisioterapeutas.get(nome)
            if fisio and fisio.horas_mes > 0:
                taxa_ind = (horas / fisio.horas_mes) * 100 if fisio.horas_mes > 0 else 0
                folga = fisio.horas_mes - horas
                dados_prof.append({
                    "Profissional": nome,
                    "Cargo": fisio.cargo,
                    "Capacidade": f"{fisio.horas_mes:.0f}h",
                    "Demanda": f"{horas:.1f}h",
                    "Folga": f"{folga:.1f}h",
                    "Taxa": f"{taxa_ind:.1f}%",
                    "Status": "🔴 Crítico" if taxa_ind > 90 else ("🟡 Atenção" if taxa_ind > 70 else "🟢 OK")
                })
        
        if dados_prof:
            dados_prof.sort(key=lambda x: float(x["Taxa"].replace("%", "")), reverse=True)
            st.dataframe(dados_prof, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum profissional com escala preenchida.")
        
        # ===== DETALHAMENTO POR SERVIÇO =====
        st.markdown("### 📋 Detalhamento por Serviço")
        
        dados_servico = []
        total_horas_servico = 0
        for srv_nome, sessoes in analise_mes.sessoes_por_servico.items():
            servico = motor.servicos.get(srv_nome)
            if servico and sessoes > 0:
                horas = sessoes * servico.duracao_horas
                total_horas_servico += horas
                dados_servico.append({
                    "Serviço": srv_nome,
                    "Sessões": f"{sessoes:.0f}",
                    "Duração": f"{servico.duracao_minutos} min",
                    "Total Horas": f"{horas:.1f}h",
                    "Usa Sala": "✅ Sim" if servico.usa_sala else "❌ Não (externo)",
                    "_horas": horas
                })
        
        if dados_servico:
            # Calcular % de cada serviço
            for d in dados_servico:
                pct = (d["_horas"] / total_horas_servico * 100) if total_horas_servico > 0 else 0
                d["% do Total"] = f"{pct:.1f}%"
                del d["_horas"]
            
            dados_servico.sort(key=lambda x: float(x["Total Horas"].replace("h", "")), reverse=True)
            st.dataframe(dados_servico, use_container_width=True, hide_index=True)
        else:
            st.warning("Nenhum serviço com sessões no mês.")
        
        # ===== SIMULAÇÃO WHAT-IF =====
        st.markdown("---")
        st.markdown("### 🔮 Simulação What-If")
        st.caption("Veja como mudanças impactariam a taxa de ocupação")
        
        # Tabs para organizar simulações
        sim_tab1, sim_tab2, sim_tab3 = st.tabs(["🏥 Cenários Sala", "👥 Cenários Profissional", "🎮 Simulador Livre"])
        
        with sim_tab1:
            st.markdown("#### 🏥 Impacto na Capacidade de Salas")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**➕ Adicionar +1 sala**")
                nova_cap_sala = ((motor.operacional.num_salas + 1) * 
                               motor.operacional.horas_atendimento_dia * 
                               motor.operacional.dias_uteis_mes)
                nova_taxa_sala = (analise_mes.demanda_sala / nova_cap_sala) * 100 if nova_cap_sala > 0 else 0.0
                delta_sala = nova_taxa_sala - analise_mes.taxa_ocupacao_sala*100
                st.metric(
                    "Nova Taxa Sala", 
                    f"{nova_taxa_sala:.1f}%",
                    delta=f"{delta_sala:.1f}%",
                    delta_color="inverse"
                )
                st.caption(f"Capacidade: {analise_mes.capacidade_sala:.0f}h → {nova_cap_sala:.0f}h")
            
            with col2:
                st.markdown("**⏰ Ampliar +2h/dia**")
                nova_cap_sala2 = (motor.operacional.num_salas * 
                                (motor.operacional.horas_atendimento_dia + 2) * 
                                motor.operacional.dias_uteis_mes)
                nova_taxa_sala2 = (analise_mes.demanda_sala / nova_cap_sala2) * 100 if nova_cap_sala2 > 0 else 0.0
                delta_sala2 = nova_taxa_sala2 - analise_mes.taxa_ocupacao_sala*100
                st.metric(
                    "Nova Taxa Sala", 
                    f"{nova_taxa_sala2:.1f}%",
                    delta=f"{delta_sala2:.1f}%",
                    delta_color="inverse"
                )
                st.caption(f"Capacidade: {analise_mes.capacidade_sala:.0f}h → {nova_cap_sala2:.0f}h")
            
            with col3:
                st.markdown("**📈 Crescer +20% demanda**")
                nova_demanda = analise_mes.demanda_sala * 1.2
                nova_taxa_sala3 = (nova_demanda / analise_mes.capacidade_sala) * 100 if analise_mes.capacidade_sala > 0 else 0.0
                delta_sala3 = nova_taxa_sala3 - analise_mes.taxa_ocupacao_sala*100
                st.metric(
                    "Nova Taxa Sala", 
                    f"{nova_taxa_sala3:.1f}%",
                    delta=f"+{delta_sala3:.1f}%",
                    delta_color="normal"
                )
                st.caption(f"Demanda: {analise_mes.demanda_sala:.0f}h → {nova_demanda:.0f}h")
        
        with sim_tab2:
            st.markdown("#### 👥 Impacto na Capacidade de Profissionais")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**👤 Contratar +1 profissional**")
                st.caption("(40h/mês - período integral)")
                nova_cap_prof = analise_mes.capacidade_profissional + 160  # 40h/sem * 4
                nova_taxa_prof = (analise_mes.demanda_profissional / nova_cap_prof) * 100 if nova_cap_prof > 0 else 0.0
                delta_prof = nova_taxa_prof - analise_mes.taxa_ocupacao_profissional*100
                st.metric(
                    "Nova Taxa Prof", 
                    f"{nova_taxa_prof:.1f}%",
                    delta=f"{delta_prof:.1f}%",
                    delta_color="inverse"
                )
                st.caption(f"Capacidade: {analise_mes.capacidade_profissional:.0f}h → {nova_cap_prof:.0f}h")
            
            with col2:
                st.markdown("**👤 Contratar meio período**")
                st.caption("(20h/mês)")
                nova_cap_prof2 = analise_mes.capacidade_profissional + 80  # 20h/sem * 4
                nova_taxa_prof2 = (analise_mes.demanda_profissional / nova_cap_prof2) * 100 if nova_cap_prof2 > 0 else 0.0
                delta_prof2 = nova_taxa_prof2 - analise_mes.taxa_ocupacao_profissional*100
                st.metric(
                    "Nova Taxa Prof", 
                    f"{nova_taxa_prof2:.1f}%",
                    delta=f"{delta_prof2:.1f}%",
                    delta_color="inverse"
                )
                st.caption(f"Capacidade: {analise_mes.capacidade_profissional:.0f}h → {nova_cap_prof2:.0f}h")
            
            with col3:
                st.markdown("**📈 Crescer +20% demanda**")
                nova_demanda_prof = analise_mes.demanda_profissional * 1.2
                nova_taxa_prof3 = (nova_demanda_prof / analise_mes.capacidade_profissional) * 100 if analise_mes.capacidade_profissional > 0 else 0.0
                delta_prof3 = nova_taxa_prof3 - analise_mes.taxa_ocupacao_profissional*100
                st.metric(
                    "Nova Taxa Prof", 
                    f"{nova_taxa_prof3:.1f}%",
                    delta=f"+{delta_prof3:.1f}%",
                    delta_color="normal"
                )
                st.caption(f"Demanda: {analise_mes.demanda_profissional:.0f}h → {nova_demanda_prof:.0f}h")
        
        with sim_tab3:
            st.markdown("#### 🎮 Simulador Interativo")
            st.caption("Ajuste os valores para ver o impacto em tempo real")
            
            col_sim1, col_sim2 = st.columns(2)
            
            with col_sim1:
                st.markdown("##### 🏥 Ajustes de Sala")
                
                sim_salas = st.slider(
                    "Número de Salas",
                    min_value=1,
                    max_value=10,
                    value=motor.operacional.num_salas,
                    key="sim_salas"
                )
                
                sim_horas = st.slider(
                    "Horas/Dia",
                    min_value=4,
                    max_value=16,
                    value=motor.operacional.horas_atendimento_dia,
                    key="sim_horas"
                )
                
                # Calcular nova capacidade sala
                nova_cap_sala_sim = sim_salas * sim_horas * motor.operacional.dias_uteis_mes
                nova_taxa_sala_sim = (analise_mes.demanda_sala / nova_cap_sala_sim) * 100 if nova_cap_sala_sim > 0 else 0.0
                
                st.markdown("---")
                delta_sim = nova_taxa_sala_sim - analise_mes.taxa_ocupacao_sala*100
                cor_delta = "🟢" if delta_sim < 0 else "🔴"
                st.metric(
                    "Taxa Sala Simulada",
                    f"{nova_taxa_sala_sim:.1f}%",
                    delta=f"{delta_sim:+.1f}%",
                    delta_color="inverse"
                )
                st.caption(f"Capacidade: {analise_mes.capacidade_sala:.0f}h → **{nova_cap_sala_sim:.0f}h**")
            
            with col_sim2:
                st.markdown("##### 👥 Ajustes de Profissional")
                
                sim_prof_extra = st.slider(
                    "Horas extras/mês (novos profissionais)",
                    min_value=0,
                    max_value=320,
                    value=0,
                    step=40,
                    help="40h = 1 profissional meio período, 160h = 1 profissional integral",
                    key="sim_prof_extra"
                )
                
                sim_crescimento = st.slider(
                    "Crescimento da Demanda (%)",
                    min_value=-20,
                    max_value=50,
                    value=0,
                    step=5,
                    key="sim_crescimento"
                )
                
                # Calcular nova capacidade profissional
                nova_cap_prof_sim = analise_mes.capacidade_profissional + sim_prof_extra
                nova_demanda_sim = analise_mes.demanda_profissional * (1 + sim_crescimento/100)
                nova_taxa_prof_sim = (nova_demanda_sim / nova_cap_prof_sim) * 100 if nova_cap_prof_sim > 0 else 0.0
                
                st.markdown("---")
                delta_prof_sim = nova_taxa_prof_sim - analise_mes.taxa_ocupacao_profissional*100
                st.metric(
                    "Taxa Prof Simulada",
                    f"{nova_taxa_prof_sim:.1f}%",
                    delta=f"{delta_prof_sim:+.1f}%",
                    delta_color="inverse" if delta_prof_sim < 0 else "normal"
                )
                st.caption(f"Cap: {analise_mes.capacidade_profissional:.0f}h → **{nova_cap_prof_sim:.0f}h** | Dem: {analise_mes.demanda_profissional:.0f}h → **{nova_demanda_sim:.0f}h**")
            
            # Resumo da simulação
            st.markdown("---")
            st.markdown("##### 📊 Resumo da Simulação")
            
            col_res1, col_res2, col_res3 = st.columns(3)
            
            with col_res1:
                # Novo gargalo
                novo_gargalo = "Sala" if nova_taxa_sala_sim > nova_taxa_prof_sim else "Profissional"
                emoji_gargalo = "🏥" if novo_gargalo == "Sala" else "👥"
                st.metric("Novo Gargalo", f"{emoji_gargalo} {novo_gargalo}")
            
            with col_res2:
                # Taxa efetiva simulada
                taxa_efetiva_sim = max(nova_taxa_sala_sim, nova_taxa_prof_sim)
                st.metric(
                    "Taxa Efetiva Simulada",
                    f"{taxa_efetiva_sim:.1f}%",
                    delta=f"{taxa_efetiva_sim - analise_mes.taxa_ocupacao_efetiva*100:+.1f}%",
                    delta_color="inverse" if taxa_efetiva_sim < analise_mes.taxa_ocupacao_efetiva*100 else "normal"
                )
            
            with col_res3:
                # Status simulado
                if taxa_efetiva_sim < 50:
                    status_sim = "🟢 Ociosidade"
                elif taxa_efetiva_sim < 70:
                    status_sim = "🟢 Saudável"
                elif taxa_efetiva_sim < 90:
                    status_sim = "🟡 Atenção"
                else:
                    status_sim = "🔴 Crítico"
                st.metric("Status Simulado", status_sim)


def pagina_ponto_equilibrio():
    """Página de análise de Ponto de Equilíbrio + Custo de Ociosidade"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>⚖️ Ponto de Equilíbrio</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    
    # Calcular análise completa
    pe_resumo = motor.get_resumo_pe()
    ocupacao_resumo = motor.get_resumo_ocupacao()
    
    # Tabs
    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📖 Visão Simplificada",
        "📈 Visão Geral", 
        "📋 Base de Dados",
        "📊 Análise Mensal", 
        "🎯 Simulador What-If",
        "📦 PE por Serviço"
    ])
    
    # ========== TAB 0: VISÃO SIMPLIFICADA (PARA LEIGOS) ==========
    with tab0:
        st.markdown("### 📖 Entenda sua Situação Financeira")
        st.info("**Esta página traduz os números financeiros em linguagem simples.** Ideal para entender rapidamente a saúde do seu negócio.")
        
        # Dados principais
        receita_media = pe_resumo['receita_total'] / 12
        pe_medio = pe_resumo['pe_contabil_medio']
        margem_seg_pct = pe_resumo['margem_seguranca_media_pct'] * 100
        ebitda_mensal = pe_resumo['ebitda_total'] / 12
        gao = pe_resumo['gao_medio']
        custo_ocio = pe_resumo['custo_ociosidade_total'] / 12
        
        # ===== SEÇÃO 1: RESUMO EM 3 FRASES =====
        st.markdown("---")
        st.markdown("## 🎯 O Essencial em 3 Frases")
        
        # Frase 1: Faturamento mínimo
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; margin: 10px 0;'>
            <h4 style='color: white; margin: 0;'>💰 Faturamento Mínimo</h4>
            <p style='color: white; font-size: 18px; margin: 10px 0 0 0;'>
                Você precisa faturar pelo menos <strong style='font-size: 24px;'>R$ {pe_medio:,.0f}/mês</strong> para cobrir todas as despesas.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Frase 2: Margem de segurança
        cor_margem = '#28a745' if margem_seg_pct >= 20 else '#ffc107' if margem_seg_pct >= 10 else '#dc3545'
        emoji_margem = '😊' if margem_seg_pct >= 20 else '😐' if margem_seg_pct >= 10 else '😟'
        
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 10px; margin: 10px 0;'>
            <h4 style='color: white; margin: 0;'>🛡️ Sua Proteção</h4>
            <p style='color: white; font-size: 18px; margin: 10px 0 0 0;'>
                {emoji_margem} Sua receita pode cair até <strong style='font-size: 24px;'>{margem_seg_pct:.0f}%</strong> antes de entrar no prejuízo.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Frase 3: Lucro
        st.markdown(f"""
        <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 10px; margin: 10px 0;'>
            <h4 style='color: white; margin: 0;'>📈 Seu Resultado</h4>
            <p style='color: white; font-size: 18px; margin: 10px 0 0 0;'>
                Você está lucrando em média <strong style='font-size: 24px;'>R$ {ebitda_mensal:,.0f}/mês</strong> (R$ {pe_resumo['ebitda_total']:,.0f}/ano).
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # ===== SEÇÃO 2: TERMÔMETRO FINANCEIRO =====
        st.markdown("---")
        st.markdown("## 🌡️ Termômetro Financeiro")
        
        # Calcular posição no termômetro
        pct_posicao = min(100, (receita_media / (pe_medio * 2)) * 100) if pe_medio > 0 else 50
        pct_pe = 50  # PE sempre no meio
        
        # Determinar cor e status
        if margem_seg_pct >= 30:
            status_cor = "#28a745"
            status_texto = "EXCELENTE"
            status_msg = "Parabéns! Sua empresa tem uma margem de segurança muito boa."
        elif margem_seg_pct >= 20:
            status_cor = "#28a745"
            status_texto = "BOM"
            status_msg = "Sua empresa está saudável, com boa folga financeira."
        elif margem_seg_pct >= 10:
            status_cor = "#ffc107"
            status_texto = "ATENÇÃO"
            status_msg = "Margem razoável, mas vale monitorar de perto."
        elif margem_seg_pct >= 0:
            status_cor = "#fd7e14"
            status_texto = "CUIDADO"
            status_msg = "Margem baixa. Considere aumentar receita ou reduzir custos."
        else:
            status_cor = "#dc3545"
            status_texto = "CRÍTICO"
            status_msg = "Atenção! A receita está abaixo do necessário."
        
        # Termômetro visual
        st.markdown(f"""
        <div style='background: #f8f9fa; padding: 25px; border-radius: 15px; margin: 15px 0;'>
            <div style='display: flex; justify-content: space-between; margin-bottom: 5px;'>
                <span style='color: #dc3545; font-weight: bold;'>🔴 Prejuízo</span>
                <span style='color: #ffc107; font-weight: bold;'>⚪ Ponto de Equilíbrio</span>
                <span style='color: #28a745; font-weight: bold;'>🟢 Lucro</span>
            </div>
            <div style='background: linear-gradient(to right, #dc3545 0%, #dc3545 45%, #ffc107 45%, #ffc107 55%, #28a745 55%, #28a745 100%); height: 40px; border-radius: 20px; position: relative; margin: 10px 0;'>
                <div style='position: absolute; left: {pct_posicao}%; top: -5px; transform: translateX(-50%);'>
                    <div style='background: {status_cor}; color: white; padding: 5px 15px; border-radius: 15px; font-weight: bold; white-space: nowrap; box-shadow: 0 2px 10px rgba(0,0,0,0.3);'>
                        📍 VOCÊ ESTÁ AQUI
                    </div>
                </div>
                <div style='position: absolute; left: 50%; bottom: -25px; transform: translateX(-50%); font-size: 12px; color: #666;'>
                    PE: R$ {pe_medio:,.0f}
                </div>
            </div>
            <div style='text-align: center; margin-top: 35px;'>
                <span style='background: {status_cor}; color: white; padding: 10px 25px; border-radius: 25px; font-size: 20px; font-weight: bold;'>
                    {status_texto}
                </span>
                <p style='margin-top: 15px; color: #333; font-size: 16px;'>{status_msg}</p>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Comparativo visual
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style='text-align: center; padding: 15px; background: #fff3cd; border-radius: 10px;'>
                <div style='font-size: 14px; color: #856404;'>Mínimo Necessário</div>
                <div style='font-size: 28px; font-weight: bold; color: #856404;'>R$ {pe_medio:,.0f}</div>
                <div style='font-size: 12px; color: #856404;'>por mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style='text-align: center; padding: 15px; background: #d4edda; border-radius: 10px;'>
                <div style='font-size: 14px; color: #155724;'>Você Fatura</div>
                <div style='font-size: 28px; font-weight: bold; color: #155724;'>R$ {receita_media:,.0f}</div>
                <div style='font-size: 12px; color: #155724;'>por mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            folga = receita_media - pe_medio
            cor_folga = '#155724' if folga >= 0 else '#721c24'
            bg_folga = '#d4edda' if folga >= 0 else '#f8d7da'
            st.markdown(f"""
            <div style='text-align: center; padding: 15px; background: {bg_folga}; border-radius: 10px;'>
                <div style='font-size: 14px; color: {cor_folga};'>Sua Folga</div>
                <div style='font-size: 28px; font-weight: bold; color: {cor_folga};'>R$ {folga:+,.0f}</div>
                <div style='font-size: 12px; color: {cor_folga};'>{'acima' if folga >= 0 else 'abaixo'} do mínimo</div>
            </div>
            """, unsafe_allow_html=True)
        
        # ===== SEÇÃO 3: PERGUNTAS E RESPOSTAS =====
        st.markdown("---")
        st.markdown("## ❓ Perguntas Frequentes")
        
        with st.expander("💰 Quanto preciso faturar por mês para não ter prejuízo?", expanded=True):
            st.markdown(f"""
            Você precisa faturar **pelo menos R$ {pe_medio:,.0f} por mês** para cobrir todas as suas despesas 
            (aluguel, salários, materiais, impostos, etc.).
            
            - **Abaixo disso:** Você terá prejuízo
            - **Igual a isso:** Você empata (nem lucro, nem prejuízo)  
            - **Acima disso:** Você terá lucro ✅
            
            Atualmente você fatura **R$ {receita_media:,.0f}/mês**, ou seja, está **R$ {receita_media - pe_medio:+,.0f}** 
            {'acima' if receita_media >= pe_medio else 'abaixo'} do mínimo necessário.
            """)
        
        with st.expander("🛡️ Quão seguro estou se a receita cair?"):
            st.markdown(f"""
            Sua **margem de segurança é de {margem_seg_pct:.0f}%**. Isso significa que:
            
            - Sua receita pode cair até **{margem_seg_pct:.0f}%** antes de começar a dar prejuízo
            - Em reais, você pode perder até **R$ {receita_media * margem_seg_pct / 100:,.0f}/mês** de faturamento
            
            **Interpretação:**
            - ✅ Acima de 30%: Muito seguro
            - ✅ Entre 20% e 30%: Seguro  
            - ⚠️ Entre 10% e 20%: Atenção
            - 🔴 Abaixo de 10%: Risco alto
            """)
        
        with st.expander("📈 O que acontece se eu faturar mais?"):
            aumento_10pct = receita_media * 0.10
            aumento_lucro = aumento_10pct * gao
            st.markdown(f"""
            Se você aumentar seu faturamento em **10% (+ R$ {aumento_10pct:,.0f}/mês)**:
            
            - Seu lucro aumentará aproximadamente **{gao*10:.0f}%** (+ R$ {aumento_lucro:,.0f}/mês)
            
            Isso acontece porque seus custos fixos (aluguel, salários) não aumentam proporcionalmente.
            Cada real a mais de receita vai quase todo para o lucro!
            
            **Alavancagem Operacional:** {gao:.1f}x
            
            _Para cada 1% de aumento na receita, seu lucro aumenta {gao:.1f}%_
            """)
        
        with st.expander("⏰ Estou pagando por horas paradas?"):
            st.markdown(f"""
            Sim! Toda empresa tem algum custo de **ociosidade** - são as horas que você paga 
            (estrutura, energia, funcionários) mas não estão sendo usadas para atender clientes.
            
            **Seu custo de ociosidade:** R$ {custo_ocio:,.0f}/mês (R$ {pe_resumo['custo_ociosidade_total']:,.0f}/ano)
            
            Isso representa **{(custo_ocio / max(1, ebitda_mensal)) * 100:.1f}%** do seu lucro mensal.
            
            **Como reduzir:**
            - Preencher mais horários vagos
            - Ajustar escala de funcionários à demanda
            - Oferecer promoções em horários ociosos
            """)
        
        # ===== SEÇÃO 4: SIMULADOR SIMPLES =====
        st.markdown("---")
        st.markdown("## 🎮 E Se...? (Simulador Simples)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            cenario = st.selectbox(
                "Escolha um cenário:",
                [
                    "📉 Receita cair 10%",
                    "📉 Receita cair 20%", 
                    "📈 Receita aumentar 10%",
                    "📈 Receita aumentar 20%",
                    "💸 Custos aumentarem 10%",
                    "✂️ Custos reduzirem 10%"
                ]
            )
        
        # Calcular cenário
        if "cair 10%" in cenario:
            nova_receita = receita_media * 0.90
            novo_lucro = ebitda_mensal - (receita_media * 0.10 * (pe_resumo['margem_seguranca_media_pct'] + 0.95))
            impacto = "negativo"
        elif "cair 20%" in cenario:
            nova_receita = receita_media * 0.80
            novo_lucro = ebitda_mensal - (receita_media * 0.20 * (pe_resumo['margem_seguranca_media_pct'] + 0.95))
            impacto = "negativo"
        elif "aumentar 10%" in cenario:
            nova_receita = receita_media * 1.10
            novo_lucro = ebitda_mensal + (receita_media * 0.10 * 0.95)
            impacto = "positivo"
        elif "aumentar 20%" in cenario:
            nova_receita = receita_media * 1.20
            novo_lucro = ebitda_mensal + (receita_media * 0.20 * 0.95)
            impacto = "positivo"
        elif "Custos aumentarem" in cenario:
            nova_receita = receita_media
            novo_lucro = ebitda_mensal - (pe_medio * 0.10)
            impacto = "negativo"
        else:  # Custos reduzirem
            nova_receita = receita_media
            novo_lucro = ebitda_mensal + (pe_medio * 0.10)
            impacto = "positivo"
        
        with col2:
            if impacto == "positivo":
                st.success(f"""
                **Resultado do Cenário:**
                
                💵 Novo lucro mensal: **R$ {novo_lucro:,.0f}**
                
                📈 Variação: **+R$ {novo_lucro - ebitda_mensal:,.0f}/mês**
                
                ✅ Cenário favorável!
                """)
            else:
                if novo_lucro > 0:
                    st.warning(f"""
                    **Resultado do Cenário:**
                    
                    💵 Novo lucro mensal: **R$ {novo_lucro:,.0f}**
                    
                    📉 Variação: **R$ {novo_lucro - ebitda_mensal:,.0f}/mês**
                    
                    ⚠️ Lucro reduzido, mas ainda positivo.
                    """)
                else:
                    st.error(f"""
                    **Resultado do Cenário:**
                    
                    💵 Novo resultado: **R$ {novo_lucro:,.0f}** (PREJUÍZO)
                    
                    📉 Variação: **R$ {novo_lucro - ebitda_mensal:,.0f}/mês**
                    
                    🚨 Cenário de prejuízo! Tome medidas preventivas.
                    """)
        
        # ===== SEÇÃO 5: RECOMENDAÇÕES =====
        st.markdown("---")
        st.markdown("## 💡 Recomendações para sua Situação")
        
        # Gerar recomendações baseadas na situação
        recomendacoes = []
        
        if margem_seg_pct >= 30:
            recomendacoes.append(("✅", "Excelente margem de segurança! Considere investir em crescimento ou criar uma reserva de emergência."))
        elif margem_seg_pct >= 20:
            recomendacoes.append(("✅", "Boa margem! Mantenha o controle de custos e busque oportunidades de crescimento."))
        elif margem_seg_pct >= 10:
            recomendacoes.append(("⚠️", "Margem razoável. Monitore de perto e evite novos custos fixos sem aumento de receita."))
        else:
            recomendacoes.append(("🚨", "Margem baixa! Priorize aumentar receita ou reduzir custos urgentemente."))
        
        if custo_ocio > ebitda_mensal * 0.20:
            recomendacoes.append(("💡", f"Custo de ociosidade alto (R$ {custo_ocio:,.0f}/mês). Tente preencher horários vagos ou ajustar escala."))
        
        if gao > 4:
            recomendacoes.append(("📊", f"Alta alavancagem operacional ({gao:.1f}x). Pequenos aumentos de receita geram grandes aumentos de lucro!"))
        
        if pe_resumo['meses_criticos'] > 0:
            recomendacoes.append(("📅", f"Há {pe_resumo['meses_criticos']} mês(es) com risco de prejuízo. Planeje ações para esses períodos."))
        
        for emoji, texto in recomendacoes:
            st.markdown(f"""
            <div style='background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 10px 0; border-left: 4px solid {'#28a745' if emoji == '✅' else '#ffc107' if emoji in ['⚠️', '💡', '📊', '📅'] else '#dc3545'};'>
                <span style='font-size: 20px;'>{emoji}</span> {texto}
            </div>
            """, unsafe_allow_html=True)
        
        # Rodapé
        st.markdown("---")
        st.caption("💡 **Dica:** Para análises mais detalhadas, consulte as outras abas desta página.")
    
    # ========== TAB 1: VISÃO GERAL ==========
    with tab1:
        st.markdown("### Indicadores Anuais")
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "PE Contábil Médio",
                f"R$ {pe_resumo['pe_contabil_medio']:,.0f}",
                help="Receita mínima mensal para cobrir custos fixos"
            )
        
        with col2:
            ms_pct = pe_resumo['margem_seguranca_media_pct'] * 100
            st.metric(
                "Margem de Segurança",
                f"{ms_pct:.1f}%",
                help="Quanto a receita pode cair antes de entrar no prejuízo"
            )
        
        with col3:
            st.metric(
                "GAO Médio",
                f"{pe_resumo['gao_medio']:.2f}x",
                help="Sensibilidade do lucro a variações de receita"
            )
        
        with col4:
            st.metric(
                "Lucro/Sessão",
                f"R$ {pe_resumo['lucro_por_sessao_medio']:,.2f}",
                help="Lucro médio gerado por cada sessão"
            )
        
        st.markdown("---")
        
        # Segunda linha de métricas
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Receita Anual",
                f"R$ {pe_resumo['receita_total']:,.0f}"
            )
        
        with col2:
            st.metric(
                "EBITDA Anual",
                f"R$ {pe_resumo['ebitda_total']:,.0f}"
            )
        
        with col3:
            st.metric(
                "Custo Ociosidade Ano",
                f"R$ {pe_resumo['custo_ociosidade_total']:,.0f}",
                help="Custo da capacidade não utilizada"
            )
        
        with col4:
            meses_criticos = pe_resumo['meses_criticos']
            cor = "🔴" if meses_criticos > 3 else "🟡" if meses_criticos > 0 else "🟢"
            st.metric(
                "Meses de Risco",
                f"{cor} {meses_criticos} de 12"
            )
        
        st.markdown("---")
        
        # Gráfico: Receita vs PE Contábil
        st.markdown("### Receita vs Ponto de Equilíbrio")
        
        
        meses_nomes = [m['nome_mes'] for m in pe_resumo['meses']]
        receitas = [m['receita_liquida'] for m in pe_resumo['meses']]
        pes = [m['pe_contabil'] for m in pe_resumo['meses']]
        margens = [m['margem_seguranca_valor'] for m in pe_resumo['meses']]
        
        fig = go.Figure()
        
        # Área de margem de segurança
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=receitas,
            fill=None,
            mode='lines+markers',
            name='Receita Líquida',
            line=dict(color='#2E86AB', width=3)
        ))
        
        fig.add_trace(go.Scatter(
            x=meses_nomes,
            y=pes,
            fill='tonexty',
            mode='lines+markers',
            name='Ponto de Equilíbrio',
            line=dict(color='#E94F37', width=2, dash='dash'),
            fillcolor='rgba(46, 134, 171, 0.2)'
        ))
        
        fig.update_layout(
            height=400,
            hovermode='x unified',
            yaxis_title="R$",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Diagnóstico
        st.markdown("### 🔍 Diagnóstico")
        
        status = pe_resumo['status_predominante']
        status_emoji = {"baixo": "🟢", "moderado": "🟡", "elevado": "🟠", "critico": "🔴"}.get(status, "⚪")
        status_texto = {"baixo": "Baixo", "moderado": "Moderado", "elevado": "Elevado", "critico": "Crítico"}.get(status, "")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.info(f"""
            **Status Predominante:** {status_emoji} Risco {status_texto}
            
            **GAO Médio:** {pe_resumo['gao_medio']:.2f}x
            
            → Para cada 1% de variação na receita, o lucro varia {pe_resumo['gao_medio']:.1f}%.
            """)
        
        with col2:
            if status == "baixo":
                msg = "✅ **Operação sólida!** Margem confortável para variações de receita. Considere investir em crescimento."
            elif status == "moderado":
                msg = "⚠️ **Atenção moderada.** Mantenha monitoramento regular e foco em manter/aumentar receita."
            elif status == "elevado":
                msg = "⚠️ **Risco elevado!** Revise estrutura de custos e busque aumento de receita."
            else:
                msg = "🚨 **ALERTA CRÍTICO!** Risco de prejuízo. Ação urgente para reduzir custos e/ou aumentar preços."
            st.warning(msg)
    
    # ========== TAB 2: BASE DE DADOS CONSOLIDADA ==========
    with tab2:
        st.markdown("### 📋 Base de Dados Consolidada")
        st.info("Visão completa de todos os indicadores mensais do Ponto de Equilíbrio (igual planilha Excel)")
        
        # Seção 1: Dados Operacionais
        st.markdown("#### 1️⃣ Dados Operacionais")
        
        dados_operacionais = []
        for m in pe_resumo['meses']:
            dados_operacionais.append({
                'Mês': m['nome_mes'],
                'Receita Líq.': f"R$ {m['receita_liquida']:,.0f}",
                'CV': f"R$ {m.get('custos_variaveis', 0):,.0f}",
                'MC': f"R$ {m['margem_contribuicao']:,.0f}",
                '% MC': f"{m['pct_mc']*100:.1f}%",
                'CF': f"R$ {m['custos_fixos']:,.0f}",
                'Overhead ABC': f"R$ {m.get('overhead_abc', 0):,.0f}",
                'EBITDA': f"R$ {m['ebitda']:,.0f}"
            })
        
        df_operacional = pd.DataFrame(dados_operacionais)
        st.dataframe(df_operacional, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Seção 2: Capacidade e Ocupação
        st.markdown("#### 2️⃣ Capacidade e Ocupação")
        
        dados_ocupacao = []
        for m in pe_resumo['meses']:
            dados_ocupacao.append({
                'Mês': m['nome_mes'],
                'Total Sessões': f"{m['total_sessoes']:,.0f}",
                'Capacidade (h)': f"{m.get('capacidade_horas', 0):,.0f}",
                'Demanda (h)': f"{m.get('demanda_horas', 0):,.0f}",
                'Taxa Ocup.': f"{m.get('taxa_ocupacao', 0)*100:.1f}%",
                'Custo Ociosidade': f"R$ {m['custo_ociosidade']:,.0f}"
            })
        
        df_ocupacao = pd.DataFrame(dados_ocupacao)
        st.dataframe(df_ocupacao, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Seção 3: Pontos de Equilíbrio
        st.markdown("#### 3️⃣ Pontos de Equilíbrio Multidimensionais")
        
        dados_pe_multi = []
        for m in pe_resumo['meses']:
            dados_pe_multi.append({
                'Mês': m['nome_mes'],
                'PE Contábil': f"R$ {m['pe_contabil']:,.0f}",
                'PE c/ Ociosidade': f"R$ {m['pe_com_ociosidade']:,.0f}",
                'PE Sessões': f"{m['pe_sessoes']:,.0f}",
                'PE Horas': f"{m['pe_horas']:,.0f}",
                'PE Taxa Ocup.': f"{m['pe_taxa_ocupacao']*100:.1f}%"
            })
        
        df_pe_multi = pd.DataFrame(dados_pe_multi)
        st.dataframe(df_pe_multi, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Seção 4: Indicadores de Risco
        st.markdown("#### 4️⃣ Indicadores de Risco e Performance")
        
        dados_risco = []
        for m in pe_resumo['meses']:
            dados_risco.append({
                'Mês': m['nome_mes'],
                'Margem Seg. R$': f"R$ {m['margem_seguranca_valor']:,.0f}",
                'Margem Seg. %': f"{m['margem_seguranca_pct']*100:.1f}%",
                'GAO': f"{m['gao']:.2f}x",
                'Lucro/Sessão': f"R$ {m['lucro_por_sessao']:.2f}",
                'Status': f"{m['status_emoji']} {m['status_texto']}"
            })
        
        df_risco = pd.DataFrame(dados_risco)
        st.dataframe(df_risco, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Resumo Anual
        st.markdown("#### 📊 Resumo Anual")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Receita Total", f"R$ {pe_resumo['receita_total']:,.0f}")
            st.metric("EBITDA Total", f"R$ {pe_resumo['ebitda_total']:,.0f}")
        
        with col2:
            st.metric("Custos Fixos Total", f"R$ {pe_resumo.get('custos_fixos_total', 0):,.0f}")
            st.metric("Overhead ABC Total", f"R$ {pe_resumo.get('overhead_abc_total', 0):,.0f}")
        
        with col3:
            st.metric("PE Contábil Médio", f"R$ {pe_resumo['pe_contabil_medio']:,.0f}")
            st.metric("Custo Ociosidade Ano", f"R$ {pe_resumo['custo_ociosidade_total']:,.0f}")
        
        with col4:
            st.metric("Sessões Ano", f"{pe_resumo['total_sessoes']:,.0f}")
            st.metric("Meses Críticos", f"{pe_resumo['meses_criticos']} de 12")
    
    # ========== TAB 3: ANÁLISE MENSAL ==========
    with tab3:
        st.markdown("### Detalhamento Mensal")
        
        # Tabela mensal
        
        dados_tabela = []
        for m in pe_resumo['meses']:
            dados_tabela.append({
                'Mês': m['nome_mes'],
                'Receita': f"R$ {m['receita_liquida']:,.0f}",
                'PE Contábil': f"R$ {m['pe_contabil']:,.0f}",
                'Margem Seg.': f"{m['margem_seguranca_pct']*100:.1f}%",
                'GAO': f"{m['gao']:.2f}x",
                'Lucro/Sessão': f"R$ {m['lucro_por_sessao']:.2f}",
                'Status': m['status_emoji']
            })
        
        df = pd.DataFrame(dados_tabela)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráfico Margem de Segurança
        st.markdown("### Margem de Segurança (%)")
        
        margens_pct = [m['margem_seguranca_pct']*100 for m in pe_resumo['meses']]
        cores = ['#2E86AB' if v >= 20 else '#F6AE2D' if v >= 10 else '#E94F37' for v in margens_pct]
        
        fig_ms = go.Figure()
        fig_ms.add_trace(go.Bar(
            x=meses_nomes,
            y=margens_pct,
            marker_color=cores,
            text=[f"{v:.1f}%" for v in margens_pct],
            textposition='outside'
        ))
        
        # Linhas de referência
        fig_ms.add_hline(y=30, line_dash="dash", line_color="green", 
                         annotation_text="Ideal (30%)")
        fig_ms.add_hline(y=15, line_dash="dash", line_color="orange", 
                         annotation_text="Atenção (15%)")
        fig_ms.add_hline(y=5, line_dash="dash", line_color="red", 
                         annotation_text="Crítico (5%)")
        
        fig_ms.update_layout(
            height=350,
            yaxis_title="Margem de Segurança (%)",
            showlegend=False,
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_ms, use_container_width=True)
        
        st.markdown("---")
        
        # Tabela de PE em diferentes métricas
        st.markdown("### Pontos de Equilíbrio em Diferentes Métricas")
        
        dados_pe = []
        for m in pe_resumo['meses']:
            dados_pe.append({
                'Mês': m['nome_mes'],
                'PE Receita': f"R$ {m['pe_contabil']:,.0f}",
                'PE c/ Ociosidade': f"R$ {m['pe_com_ociosidade']:,.0f}",
                'PE Sessões': f"{m['pe_sessoes']:.0f}",
                'PE Horas': f"{m['pe_horas']:.0f}h",
                'PE Taxa Ocup.': f"{m['pe_taxa_ocupacao']*100:.1f}%"
            })
        
        df_pe = pd.DataFrame(dados_pe)
        st.dataframe(df_pe, use_container_width=True, hide_index=True)
    
    # ========== TAB 4: SIMULADOR WHAT-IF ==========
    with tab4:
        st.markdown("### 🎯 Simulador What-If")
        st.info("Simule cenários alterando parâmetros chave para ver o impacto no Ponto de Equilíbrio.")
        
        # Valores base
        receita_base = pe_resumo['receita_total'] / 12
        cf_base = sum(m['custos_fixos'] for m in pe_resumo['meses']) / 12
        mc_pct_base = sum(m['pct_mc'] for m in pe_resumo['meses']) / 12
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            var_receita = st.slider(
                "Variação na Receita (%)",
                min_value=-30,
                max_value=30,
                value=0,
                step=5,
                help="Simule aumento ou redução de receita"
            )
        
        with col2:
            var_custos = st.slider(
                "Variação nos Custos Fixos (%)",
                min_value=-20,
                max_value=30,
                value=0,
                step=5,
                help="Simule aumento ou redução de custos fixos"
            )
        
        with col3:
            var_margem = st.slider(
                "Variação na Margem Contrib. (p.p.)",
                min_value=-10,
                max_value=10,
                value=0,
                step=1,
                help="Simule variação na margem de contribuição (pontos percentuais)"
            )
        
        # Cálculos simulados
        receita_sim = receita_base * (1 + var_receita/100)
        cf_sim = cf_base * (1 + var_custos/100)
        mc_pct_sim = mc_pct_base + (var_margem/100)
        
        # PE simulado
        if mc_pct_sim > 0:
            pe_sim = cf_sim / mc_pct_sim
            ms_sim = receita_sim - pe_sim
            ms_pct_sim = ms_sim / receita_sim if receita_sim > 0 else 0
            ebitda_sim = receita_sim * mc_pct_sim - cf_sim
        else:
            pe_sim = 0
            ms_sim = 0
            ms_pct_sim = 0
            ebitda_sim = 0
        
        st.markdown("---")
        st.markdown("### Resultado da Simulação")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            delta_pe = pe_sim - (cf_base / mc_pct_base if mc_pct_base > 0 else 0)
            st.metric(
                "PE Contábil",
                f"R$ {pe_sim:,.0f}",
                delta=f"R$ {delta_pe:,.0f}",
                delta_color="inverse"
            )
        
        with col2:
            delta_ms = ms_pct_sim - pe_resumo['margem_seguranca_media_pct']
            st.metric(
                "Margem Segurança",
                f"{ms_pct_sim*100:.1f}%",
                delta=f"{delta_ms*100:.1f} p.p."
            )
        
        with col3:
            ebitda_base = pe_resumo['ebitda_total'] / 12
            delta_ebitda = ebitda_sim - ebitda_base
            st.metric(
                "EBITDA Mensal",
                f"R$ {ebitda_sim:,.0f}",
                delta=f"R$ {delta_ebitda:,.0f}"
            )
        
        with col4:
            # Status simulado
            if ms_pct_sim >= 0.30:
                status_sim = "🟢 Baixo"
            elif ms_pct_sim >= 0.15:
                status_sim = "🟡 Moderado"
            elif ms_pct_sim >= 0.05:
                status_sim = "🟠 Elevado"
            else:
                status_sim = "🔴 Crítico"
            st.metric("Status Risco", status_sim)
        
        # Comparativo visual
        st.markdown("---")
        st.markdown("### Comparativo: Atual vs Simulado")
        
        pe_base = cf_base / mc_pct_base if mc_pct_base > 0 else 0
        ms_base = pe_resumo['margem_seguranca_media_pct']
        
        fig_comp = go.Figure()
        
        categorias = ['PE Contábil', 'Margem Segurança (%)', 'EBITDA']
        valores_base = [pe_base, ms_base * 100, ebitda_base]
        valores_sim = [pe_sim, ms_pct_sim * 100, ebitda_sim]
        
        # Normalizar para visualização (dividir pelo base)
        valores_base_norm = [1, 1, 1]
        valores_sim_norm = [
            pe_sim / pe_base if pe_base > 0 else 1,
            (ms_pct_sim * 100) / (ms_base * 100) if ms_base > 0 else 1,
            ebitda_sim / ebitda_base if ebitda_base > 0 else 1
        ]
        
        fig_comp.add_trace(go.Bar(
            name='Atual',
            x=categorias,
            y=valores_base_norm,
            marker_color='#2E86AB',
            text=['100%', '100%', '100%'],
            textposition='outside'
        ))
        
        fig_comp.add_trace(go.Bar(
            name='Simulado',
            x=categorias,
            y=valores_sim_norm,
            marker_color='#F6AE2D',
            text=[f"{v*100:.0f}%" for v in valores_sim_norm],
            textposition='outside'
        ))
        
        fig_comp.update_layout(
            height=300,
            barmode='group',
            yaxis_title="% do Valor Base",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_comp, use_container_width=True)
        
        # Conclusão
        if ebitda_sim > ebitda_base:
            st.success(f"""
            ✅ **Cenário Favorável!** 
            
            Com essas mudanças, o EBITDA aumentaria R$ {ebitda_sim - ebitda_base:,.0f}/mês 
            (R$ {(ebitda_sim - ebitda_base)*12:,.0f}/ano).
            """)
        elif ebitda_sim < 0:
            st.error(f"""
            🚨 **ALERTA: Cenário de Prejuízo!** 
            
            Com essas condições, a empresa teria prejuízo de R$ {-ebitda_sim:,.0f}/mês.
            """)
        else:
            st.warning(f"""
            ⚠️ **Cenário Desfavorável.** 
            
            O EBITDA reduziria R$ {ebitda_base - ebitda_sim:,.0f}/mês.
            """)
    
    # ========== TAB 5: PE POR SERVIÇO ==========
    with tab5:
        st.markdown("### 📦 Ponto de Equilíbrio por Serviço")
        st.info("""
        Esta análise mostra o **PE individual de cada serviço**, integrando dados do TDABC.
        Identifique quais serviços estão acima ou abaixo do ponto de equilíbrio.
        """)
        
        # Calcular PE por serviço
        pe_servicos = motor.get_resumo_pe_por_servico()
        
        # Resumo
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Receita Total Anual",
                f"R$ {pe_servicos['receita_total']:,.0f}"
            )
        
        with col2:
            st.metric(
                "PE Total",
                f"R$ {pe_servicos['pe_total']:,.0f}"
            )
        
        with col3:
            st.metric(
                "✅ Acima do PE",
                f"{pe_servicos['servicos_acima_pe']} serviços",
                delta="OK" if pe_servicos['servicos_abaixo_pe'] == 0 else None
            )
        
        with col4:
            if pe_servicos['servicos_abaixo_pe'] > 0:
                st.metric(
                    "❌ Abaixo do PE",
                    f"{pe_servicos['servicos_abaixo_pe']} serviços",
                    delta="Atenção",
                    delta_color="inverse"
                )
            else:
                st.metric(
                    "❌ Abaixo do PE",
                    "Nenhum",
                    delta="Todos OK"
                )
        
        st.markdown("---")
        
        # Tabela principal
        st.markdown("### 📋 Análise Detalhada por Serviço")
        
        dados_tabela = []
        for srv in pe_servicos['servicos']:
            dados_tabela.append({
                "Serviço": srv['servico'],
                "Receita": f"R$ {srv['receita_anual']:,.0f}",
                "Sessões": f"{srv['sessoes_ano']:,.0f}",
                "Ticket": f"R$ {srv['ticket_medio']:,.0f}",
                "Lucro ABC": f"R$ {srv['lucro_abc']:,.0f}",
                "Margem": f"{srv['margem_abc']*100:.1f}%",
                "Mix": f"{srv['pct_mix']*100:.1f}%",
                "CF Rateado": f"R$ {srv['cf_rateado']:,.0f}",
                "PE R$": f"R$ {srv['pe_receita']:,.0f}",
                "PE Sess.": f"{srv['pe_sessoes']:,.0f}",
                "Status": srv['status']
            })
        
        df_servicos = pd.DataFrame(dados_tabela)
        st.dataframe(df_servicos, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráfico: Receita vs PE por serviço
        st.markdown("### 📊 Receita vs Ponto de Equilíbrio")
        
        servicos_nomes = [s['servico'] for s in pe_servicos['servicos']]
        receitas = [s['receita_anual'] for s in pe_servicos['servicos']]
        pes = [s['pe_receita'] for s in pe_servicos['servicos']]
        
        fig_pe = go.Figure()
        
        fig_pe.add_trace(go.Bar(
            name='Receita Anual',
            x=servicos_nomes,
            y=receitas,
            marker_color='#2E86AB',
            text=[f"R$ {r:,.0f}" for r in receitas],
            textposition='outside'
        ))
        
        fig_pe.add_trace(go.Bar(
            name='Ponto de Equilíbrio',
            x=servicos_nomes,
            y=pes,
            marker_color='#E94F37',
            text=[f"R$ {p:,.0f}" for p in pes],
            textposition='outside'
        ))
        
        fig_pe.update_layout(
            barmode='group',
            height=400,
            yaxis_title="R$",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_pe, use_container_width=True)
        
        st.markdown("---")
        
        # Margem de Segurança por serviço
        st.markdown("### 🛡️ Margem de Segurança por Serviço")
        
        margens_seg = [s['margem_seguranca_pct'] * 100 for s in pe_servicos['servicos']]
        cores_margem = ['#28a745' if m >= 30 else '#ffc107' if m >= 15 else '#dc3545' for m in margens_seg]
        
        fig_margem = go.Figure()
        
        fig_margem.add_trace(go.Bar(
            x=servicos_nomes,
            y=margens_seg,
            marker_color=cores_margem,
            text=[f"{m:.1f}%" for m in margens_seg],
            textposition='outside'
        ))
        
        # Linhas de referência
        fig_margem.add_hline(y=30, line_dash="dash", line_color="green", 
                            annotation_text="Ideal (30%)", annotation_position="right")
        fig_margem.add_hline(y=15, line_dash="dash", line_color="orange",
                            annotation_text="Atenção (15%)", annotation_position="right")
        
        fig_margem.update_layout(
            height=350,
            yaxis_title="Margem de Segurança (%)",
            showlegend=False,
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_margem, use_container_width=True)
        
        st.markdown("---")
        
        # Insights
        st.markdown("### 💡 Insights")
        
        # Verificar se há serviços para analisar
        if not pe_servicos.get('servicos') or len(pe_servicos['servicos']) == 0:
            st.warning("Sem dados de serviços para análise. Configure os atendimentos primeiro.")
        else:
            # Serviço com maior folga
            melhor_margem = max(pe_servicos['servicos'], key=lambda x: x['margem_seguranca_pct'])
            menor_margem = min(pe_servicos['servicos'], key=lambda x: x['margem_seguranca_pct'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.success(f"""
                **🏆 Mais Seguro:** {melhor_margem['servico']}
                
                - Margem de Segurança: {melhor_margem['margem_seguranca_pct']*100:.1f}%
                - Folga: {melhor_margem['folga_sessoes']:,.0f} sessões acima do PE
                - Receita: R$ {melhor_margem['receita_anual']:,.0f}
                """)
            
            with col2:
                if menor_margem['margem_seguranca_pct'] < 0.15:
                    st.error(f"""
                    **⚠️ Maior Risco:** {menor_margem['servico']}
                    
                    - Margem de Segurança: {menor_margem['margem_seguranca_pct']*100:.1f}%
                    - Folga: {menor_margem['folga_sessoes']:,.0f} sessões
                    - Ação: Revisar preço ou reduzir custos
                    """)
                else:
                    st.warning(f"""
                    **⚡ Menor Margem:** {menor_margem['servico']}
                    
                    - Margem de Segurança: {menor_margem['margem_seguranca_pct']*100:.1f}%
                    - Folga: {menor_margem['folga_sessoes']:,.0f} sessões
                    - Monitorar de perto
                    """)


def pagina_custeio_abc():
    """Página de Custeio ABC (Activity-Based Costing) - TDABC"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>🎯 Custeio ABC - Activity-Based Costing</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    
    # IMPORTANTE: Sincronizar cadastro_salas com premissas operacionais ANTES de qualquer cálculo
    motor.cadastro_salas.horas_funcionamento_dia = motor.operacional.horas_atendimento_dia
    motor.cadastro_salas.dias_uteis_mes = motor.operacional.dias_uteis_mes
    
    # CORREÇÃO: Verificar se num_salas está configurado
    if motor.operacional.num_salas > 0:
        motor.cadastro_salas.sincronizar_num_salas(motor.operacional.num_salas)
    else:
        # Se num_salas = 0, mostrar aviso
        st.warning("⚠️ **Nº de Salas não configurado!** Vá em **⚙️ Premissas → 🏥 Operacionais** e configure o número de salas.")
    
    # Tabs
    tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📖 Visão Simplificada",
        "📊 Visão Geral",
        "🏢 Cadastro de Salas",
        "🔗 Mix Sala×Serviço",
        "💰 Rateio de Custos",
        "⏱️ Horas por Serviço",
        "💸 Custo Ociosidade",
        "🏆 Rentabilidade"
    ])
    
    # ========== TAB 0: DASHBOARD VISUAL (PARA LEIGOS) ==========
    with tab0:
        st.markdown("### 🎨 Dashboard de Rentabilidade")
        
        # Dados principais
        tdabc_resumo = motor.get_resumo_tdabc()
        ranking = tdabc_resumo['ranking']
        
        # Totais
        receita_total = sum(r['receita'] for r in ranking) if ranking else 0
        lucro_total = tdabc_resumo['lucro_total']
        overhead_total = tdabc_resumo['overhead_total']
        cv_total = receita_total - overhead_total - lucro_total
        margem_media = (lucro_total / receita_total * 100) if receita_total > 0 else 0
        
        # Melhor e pior serviço
        if ranking:
            melhor = max(ranking, key=lambda x: x['margem_abc'])
            pior = min(ranking, key=lambda x: x['margem_abc'])
            ranking_ordenado = sorted(ranking, key=lambda x: x['margem_abc'], reverse=True)
        else:
            melhor = pior = None
            ranking_ordenado = []
        
        # ===== LINHA 1: MÉTRICAS PRINCIPAIS =====
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 14px; color: rgba(255,255,255,0.8);'>💵 RECEITA ANUAL</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {receita_total/1000:,.0f}k</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.7);'>R$ {receita_total/12:,.0f}/mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            cor_lucro = '#28a745' if lucro_total > 0 else '#dc3545'
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 14px; color: rgba(255,255,255,0.8);'>💰 LUCRO ANUAL</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {lucro_total/1000:,.0f}k</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.7);'>R$ {lucro_total/12:,.0f}/mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 14px; color: rgba(255,255,255,0.8);'>🏢 CUSTOS FIXOS</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {overhead_total/1000:,.0f}k</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.7);'>R$ {overhead_total/12:,.0f}/mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            # Cor da margem
            if margem_media >= 25:
                cor_margem = '#28a745'
                emoji_margem = '🟢'
            elif margem_media >= 15:
                cor_margem = '#17a2b8'
                emoji_margem = '🔵'
            elif margem_media >= 5:
                cor_margem = '#ffc107'
                emoji_margem = '🟡'
            else:
                cor_margem = '#dc3545'
                emoji_margem = '🔴'
            
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 14px; color: rgba(255,255,255,0.8);'>{emoji_margem} MARGEM MÉDIA</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>{margem_media:.1f}%</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.7);'>do faturamento</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # ===== LINHA 2: GAUGE + DONUT =====
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # GAUGE - Velocímetro de Margem
            st.markdown("#### 🎯 Saúde Financeira")
            
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=margem_media,
                title={'text': "Margem de Lucro", 'font': {'size': 16}},
                number={'suffix': "%", 'font': {'size': 36}},
                gauge={
                    'axis': {'range': [0, 50], 'tickwidth': 1},
                    'bar': {'color': cor_margem},
                    'bgcolor': "white",
                    'borderwidth': 2,
                    'bordercolor': "gray",
                    'steps': [
                        {'range': [0, 10], 'color': '#f8d7da'},
                        {'range': [10, 20], 'color': '#fff3cd'},
                        {'range': [20, 30], 'color': '#d1ecf1'},
                        {'range': [30, 50], 'color': '#d4edda'}
                    ],
                    'threshold': {
                        'line': {'color': "black", 'width': 4},
                        'thickness': 0.75,
                        'value': margem_media
                    }
                }
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
            # Status
            if margem_media >= 25:
                st.success("✅ **EXCELENTE!** Margem saudável")
            elif margem_media >= 15:
                st.info("🔵 **BOM** - Pode melhorar")
            elif margem_media >= 5:
                st.warning("🟡 **ATENÇÃO** - Margem baixa")
            else:
                st.error("🔴 **CRÍTICO** - Ação urgente!")
        
        with col2:
            # DONUT - Composição da Receita
            st.markdown("#### 💵 Para Onde Vai a Receita?")
            
            fig_donut = go.Figure(data=[go.Pie(
                labels=['💰 Lucro', '🏭 Custos Variáveis', '🏢 Custos Fixos'],
                values=[max(0, lucro_total), max(0, cv_total), overhead_total],
                hole=0.6,
                marker_colors=['#28a745', '#ffc107', '#dc3545'],
                textinfo='label+percent',
                textposition='outside',
                pull=[0.05, 0, 0]
            )])
            
            fig_donut.update_layout(
                height=280,
                margin=dict(l=20, r=20, t=20, b=20),
                showlegend=False,
                annotations=[dict(
                    text=f'R$ {receita_total/1000:.0f}k',
                    x=0.5, y=0.5,
                    font_size=18,
                    showarrow=False
                )]
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        
        with col3:
            # DONUT - Lucro por Serviço
            st.markdown("#### 🏆 Quem Gera Lucro?")
            
            if ranking_ordenado:
                top_servicos = ranking_ordenado[:5]
                outros_lucro = sum(r['lucro_abc'] for r in ranking_ordenado[5:]) if len(ranking_ordenado) > 5 else 0
                
                labels = [r['servico'] for r in top_servicos]
                values = [max(0, r['lucro_abc']) for r in top_servicos]
                
                if outros_lucro > 0:
                    labels.append('Outros')
                    values.append(outros_lucro)
                
                cores = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#95969A']
                
                fig_lucro = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=0.5,
                    marker_colors=cores[:len(labels)],
                    textinfo='label+percent',
                    textposition='inside'
                )])
                
                fig_lucro.update_layout(
                    height=280,
                    margin=dict(l=20, r=20, t=20, b=20),
                    showlegend=False
                )
                st.plotly_chart(fig_lucro, use_container_width=True)
        
        # ===== LINHA 2B: INDICADORES DE PRODUTIVIDADE =====
        st.markdown("---")
        st.markdown("### 📏 Indicadores de Produtividade")
        st.caption("Quanto você lucra e gasta por unidade de recurso")
        
        # Calcular métricas
        cadastro = motor.cadastro_salas
        m2_total = cadastro.m2_ativo if cadastro.m2_ativo > 0 else 1
        num_salas = cadastro.num_salas_ativas if cadastro.num_salas_ativas > 0 else 1
        
        # Horas totais anuais
        total_horas_ano = 0
        for mes in range(12):
            tdabc_mes = motor.calcular_tdabc_mes(mes)
            for servico, rateio in tdabc_mes.rateios.items():
                total_horas_ano += rateio.horas_sala
        total_horas_ano = total_horas_ano if total_horas_ano > 0 else 1
        
        # Métricas de Lucro
        lucro_por_hora = lucro_total / total_horas_ano
        lucro_por_m2_ano = lucro_total / m2_total
        lucro_por_m2_mes = lucro_por_m2_ano / 12
        lucro_por_sala_ano = lucro_total / num_salas
        lucro_por_sala_mes = lucro_por_sala_ano / 12
        
        # Métricas de Despesas (overhead)
        desp_por_hora = overhead_total / total_horas_ano
        desp_por_m2_ano = overhead_total / m2_total
        desp_por_m2_mes = desp_por_m2_ano / 12
        desp_por_sala_ano = overhead_total / num_salas
        desp_por_sala_mes = desp_por_sala_ano / 12
        
        # Linha de LUCRO
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>⏱️💰</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>LUCRO POR HORA</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {lucro_por_hora:,.2f}</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>por hora trabalhada</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>📐💰</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>LUCRO POR M²</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {lucro_por_m2_mes:,.2f}</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>por m² / mês ({m2_total:.0f} m² ativos)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>🚪💰</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>LUCRO POR SALA</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {lucro_por_sala_mes:,.0f}</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>por sala / mês ({num_salas} salas ativas)</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Linha de DESPESAS
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>⏱️💸</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>CUSTO POR HORA</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {desp_por_hora:,.2f}</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>custo fixo por hora</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>📐💸</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>CUSTO POR M²</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {desp_por_m2_mes:,.2f}</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>custo fixo por m² / mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>🚪💸</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>CUSTO POR SALA</div>
                <div style='font-size: 28px; font-weight: bold; color: white;'>R$ {desp_por_sala_mes:,.0f}</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>custo fixo por sala / mês</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Linha de EFICIÊNCIA (Lucro vs Custo)
        col1, col2, col3 = st.columns(3)
        
        # Calcular eficiência (lucro / custo)
        eficiencia_hora = lucro_por_hora / desp_por_hora if desp_por_hora > 0 else 0
        eficiencia_m2 = lucro_por_m2_mes / desp_por_m2_mes if desp_por_m2_mes > 0 else 0
        eficiencia_sala = lucro_por_sala_mes / desp_por_sala_mes if desp_por_sala_mes > 0 else 0
        
        with col1:
            cor_ef = '#28a745' if eficiencia_hora >= 1 else '#ffc107' if eficiencia_hora >= 0.5 else '#dc3545'
            emoji_ef = '✅' if eficiencia_hora >= 1 else '⚠️' if eficiencia_hora >= 0.5 else '❌'
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>{emoji_ef}</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>EFICIÊNCIA / HORA</div>
                <div style='font-size: 28px; font-weight: bold; color: {cor_ef};'>{eficiencia_hora:.2f}x</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>lucro ÷ custo (ideal ≥ 1x)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            cor_ef = '#28a745' if eficiencia_m2 >= 1 else '#ffc107' if eficiencia_m2 >= 0.5 else '#dc3545'
            emoji_ef = '✅' if eficiencia_m2 >= 1 else '⚠️' if eficiencia_m2 >= 0.5 else '❌'
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>{emoji_ef}</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>EFICIÊNCIA / M²</div>
                <div style='font-size: 28px; font-weight: bold; color: {cor_ef};'>{eficiencia_m2:.2f}x</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>lucro ÷ custo (ideal ≥ 1x)</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            cor_ef = '#28a745' if eficiencia_sala >= 1 else '#ffc107' if eficiencia_sala >= 0.5 else '#dc3545'
            emoji_ef = '✅' if eficiencia_sala >= 1 else '⚠️' if eficiencia_sala >= 0.5 else '❌'
            st.markdown(f"""
            <div style='background: linear-gradient(135deg, #2c3e50 0%, #4ca1af 100%); padding: 20px; border-radius: 15px; text-align: center;'>
                <div style='font-size: 30px;'>{emoji_ef}</div>
                <div style='font-size: 12px; color: rgba(255,255,255,0.8); margin-top: 5px;'>EFICIÊNCIA / SALA</div>
                <div style='font-size: 28px; font-weight: bold; color: {cor_ef};'>{eficiencia_sala:.2f}x</div>
                <div style='font-size: 11px; color: rgba(255,255,255,0.7);'>lucro ÷ custo (ideal ≥ 1x)</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Explicação
        st.markdown("""
        <div style='background: #f8f9fa; padding: 15px; border-radius: 10px; margin-top: 15px;'>
            <strong>💡 Como interpretar:</strong><br>
            • <span style='color: #28a745;'>✅ Eficiência ≥ 1x</span> = Cada R$ de custo gera R$ 1+ de lucro<br>
            • <span style='color: #ffc107;'>⚠️ Eficiência 0.5-1x</span> = Lucro não cobre totalmente os custos fixos<br>
            • <span style='color: #dc3545;'>❌ Eficiência < 0.5x</span> = Atenção! Custos muito altos para o lucro gerado
        </div>
        """, unsafe_allow_html=True)
        
        # ===== LINHA 3: RANKING HORIZONTAL =====
        st.markdown("---")
        st.markdown("### 🏅 Ranking de Rentabilidade por Serviço")
        
        if ranking_ordenado:
            # Preparar dados
            servicos = [r['servico'] for r in ranking_ordenado]
            margens = [r['margem_abc'] * 100 for r in ranking_ordenado]
            lucros = [r['lucro_abc'] for r in ranking_ordenado]
            
            # Cores baseadas na margem
            cores = []
            for m in margens:
                if m >= 30:
                    cores.append('#28a745')
                elif m >= 20:
                    cores.append('#17a2b8')
                elif m >= 10:
                    cores.append('#ffc107')
                elif m >= 0:
                    cores.append('#fd7e14')
                else:
                    cores.append('#dc3545')
            
            # Gráfico de barras horizontal
            fig_ranking = go.Figure()
            
            fig_ranking.add_trace(go.Bar(
                y=servicos[::-1],  # Inverter para melhor ficar em cima
                x=margens[::-1],
                orientation='h',
                marker_color=cores[::-1],
                text=[f'{m:.0f}%' for m in margens[::-1]],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>Margem: %{x:.1f}%<extra></extra>'
            ))
            
            # Adicionar medalhas
            medalhas = ['🥇', '🥈', '🥉'] + [f'{i+1}º' for i in range(3, len(servicos))]
            
            fig_ranking.update_layout(
                height=50 + len(servicos) * 45,
                margin=dict(l=20, r=100, t=20, b=20),
                xaxis_title="Margem de Lucro (%)",
                yaxis_title="",
                showlegend=False,
                xaxis=dict(range=[0, max(margens) * 1.3])
            )
            
            st.plotly_chart(fig_ranking, use_container_width=True)
            
            # Legenda de cores
            st.markdown("""
            <div style='display: flex; justify-content: center; gap: 20px; margin-top: 10px;'>
                <span style='color: #28a745;'>🟢 Excelente (≥30%)</span>
                <span style='color: #17a2b8;'>🔵 Bom (20-30%)</span>
                <span style='color: #ffc107;'>🟡 Regular (10-20%)</span>
                <span style='color: #fd7e14;'>🟠 Baixo (0-10%)</span>
                <span style='color: #dc3545;'>🔴 Prejuízo (<0%)</span>
            </div>
            """, unsafe_allow_html=True)
        
        # ===== LINHA 4: DESTAQUES =====
        st.markdown("---")
        st.markdown("### 🎯 Destaques")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if melhor:
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%); padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #28a745;'>
                    <div style='font-size: 40px;'>🏆</div>
                    <div style='font-size: 14px; color: #155724; margin-top: 10px;'>CAMPEÃO DE LUCRO</div>
                    <div style='font-size: 22px; font-weight: bold; color: #155724;'>{melhor['servico']}</div>
                    <div style='font-size: 16px; color: #155724; margin-top: 10px;'>
                        Margem: <strong>{melhor['margem_abc']*100:.0f}%</strong>
                    </div>
                    <div style='font-size: 14px; color: #155724;'>
                        R$ {melhor['lucro_abc']:,.0f}/ano
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if pior:
                cor_bg = '#f8d7da' if pior['margem_abc'] < 0.10 else '#fff3cd'
                cor_texto = '#721c24' if pior['margem_abc'] < 0.10 else '#856404'
                cor_borda = '#dc3545' if pior['margem_abc'] < 0.10 else '#ffc107'
                emoji = '⚠️' if pior['margem_abc'] >= 0 else '🚨'
                
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, {cor_bg} 0%, {cor_bg} 100%); padding: 20px; border-radius: 15px; text-align: center; border: 2px solid {cor_borda};'>
                    <div style='font-size: 40px;'>{emoji}</div>
                    <div style='font-size: 14px; color: {cor_texto}; margin-top: 10px;'>MENOR MARGEM</div>
                    <div style='font-size: 22px; font-weight: bold; color: {cor_texto};'>{pior['servico']}</div>
                    <div style='font-size: 16px; color: {cor_texto}; margin-top: 10px;'>
                        Margem: <strong>{pior['margem_abc']*100:.0f}%</strong>
                    </div>
                    <div style='font-size: 14px; color: {cor_texto};'>
                        R$ {pior['lucro_abc']:,.0f}/ano
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            # Card de Oportunidade
            if melhor:
                oportunidade = melhor['lucro_abc'] * 0.5  # Se aumentar 50% do campeão
                st.markdown(f"""
                <div style='background: linear-gradient(135deg, #cce5ff 0%, #b8daff 100%); padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #004085;'>
                    <div style='font-size: 40px;'>💡</div>
                    <div style='font-size: 14px; color: #004085; margin-top: 10px;'>OPORTUNIDADE</div>
                    <div style='font-size: 18px; font-weight: bold; color: #004085;'>+50% em {melhor['servico']}</div>
                    <div style='font-size: 16px; color: #004085; margin-top: 10px;'>
                        Ganho potencial:
                    </div>
                    <div style='font-size: 20px; font-weight: bold; color: #004085;'>
                        +R$ {oportunidade:,.0f}/ano
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # ===== LINHA 5: GRÁFICO DE EVOLUÇÃO MENSAL =====
        st.markdown("---")
        st.markdown("### 📈 Lucro Mensal por Serviço")
        
        # Preparar dados mensais
        meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                       "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        fig_mensal = go.Figure()
        
        cores_servicos = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B', '#28a745']
        
        for i, srv in enumerate(ranking_ordenado[:6]):  # Top 6
            lucros_mensais = []
            for mes_data in tdabc_resumo['meses']:
                if srv['servico'] in mes_data['servicos']:
                    lucros_mensais.append(mes_data['servicos'][srv['servico']]['lucro_abc'])
                else:
                    lucros_mensais.append(0)
            
            fig_mensal.add_trace(go.Scatter(
                x=meses_nomes,
                y=lucros_mensais,
                mode='lines+markers',
                name=srv['servico'],
                line=dict(color=cores_servicos[i % len(cores_servicos)], width=2),
                marker=dict(size=8)
            ))
        
        fig_mensal.update_layout(
            height=350,
            margin=dict(l=50, r=50, t=20, b=50),
            xaxis_title="Mês",
            yaxis_title="Lucro (R$)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig_mensal, use_container_width=True)
        
        # ===== LINHA 6: DICAS VISUAIS =====
        st.markdown("---")
        st.markdown("### 💡 O Que Fazer?")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div style='background: #e8f5e9; padding: 20px; border-radius: 15px; text-align: center; height: 180px;'>
                <div style='font-size: 40px;'>📈</div>
                <div style='font-size: 14px; font-weight: bold; color: #2e7d32; margin-top: 10px;'>AUMENTAR</div>
                <div style='font-size: 13px; color: #2e7d32; margin-top: 5px;'>
                    Foque em <strong>{melhor['servico'] if melhor else 'serviços rentáveis'}</strong>
                </div>
                <div style='font-size: 12px; color: #666; margin-top: 10px;'>
                    Cada sessão extra = +R$ lucro
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div style='background: #fff3e0; padding: 20px; border-radius: 15px; text-align: center; height: 180px;'>
                <div style='font-size: 40px;'>💰</div>
                <div style='font-size: 14px; font-weight: bold; color: #e65100; margin-top: 10px;'>REAJUSTAR</div>
                <div style='font-size: 13px; color: #e65100; margin-top: 5px;'>
                    Avalie preços de <strong>{pior['servico'] if pior else 'serviços fracos'}</strong>
                </div>
                <div style='font-size: 12px; color: #666; margin-top: 10px;'>
                    +10% no preço = +10% no lucro
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div style='background: #e3f2fd; padding: 20px; border-radius: 15px; text-align: center; height: 180px;'>
                <div style='font-size: 40px;'>✂️</div>
                <div style='font-size: 14px; font-weight: bold; color: #1565c0; margin-top: 10px;'>REDUZIR</div>
                <div style='font-size: 13px; color: #1565c0; margin-top: 5px;'>
                    Custos fixos de <strong>R$ {overhead_total/12:,.0f}/mês</strong>
                </div>
                <div style='font-size: 12px; color: #666; margin-top: 10px;'>
                    Negocie aluguel e contratos
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div style='background: #fce4ec; padding: 20px; border-radius: 15px; text-align: center; height: 180px;'>
                <div style='font-size: 40px;'>⏰</div>
                <div style='font-size: 14px; font-weight: bold; color: #c2185b; margin-top: 10px;'>OTIMIZAR</div>
                <div style='font-size: 13px; color: #c2185b; margin-top: 5px;'>
                    Reduza tempo ocioso
                </div>
                <div style='font-size: 12px; color: #666; margin-top: 10px;'>
                    Sala vazia = dinheiro perdido
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Rodapé
        st.markdown("---")
        st.caption("💡 **Dica:** Para análises mais detalhadas e configurações, explore as outras abas desta página.")
    
    # ========== TAB 1: VISÃO GERAL ==========
    with tab1:
        st.markdown("### O que é Custeio ABC?")
        
        st.info("""
        O **Custeio ABC (Activity-Based Costing)** ou **TDABC (Time-Driven ABC)** é uma metodologia 
        que aloca custos indiretos de forma mais precisa, usando **direcionadores de custo** 
        que refletem o consumo real de recursos por cada serviço.
        
        **Diferença do custeio tradicional:**
        - Custeio tradicional: rateia custos igualmente ou por receita
        - Custeio ABC: rateia por consumo real de recursos (m², horas, sessões)
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🎯 3 Direcionadores de Custo")
            st.markdown("""
            | Direcionador | Custos Alocados | Lógica |
            |--------------|-----------------|--------|
            | **m²** | Aluguel, Energia, Limpeza | Proporcional ao espaço usado |
            | **Sessões** | Sistema, Telefone, Cursos | Proporcional ao volume |
            | **Receita** | Contabilidade, Marketing | Proporcional ao faturamento |
            """)
        
        with col2:
            st.markdown("#### 💡 Benefícios")
            st.markdown("""
            - Descobrir a **rentabilidade real** de cada serviço
            - Identificar serviços que "roubam" lucro de outros
            - Tomar decisões de **preço** e **mix** mais assertivas
            - Otimizar uso de **espaço físico**
            """)
        
        st.markdown("---")
        
        # Resumo rápido
        tdabc_resumo = motor.get_resumo_tdabc()
        cadastro = motor.cadastro_salas
        
        st.markdown("### 📈 Resumo da Configuração")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Salas Ativas", f"{cadastro.num_salas_ativas}")
        with col2:
            st.metric("m² Total", f"{cadastro.m2_ativo:.0f} m²")
        with col3:
            st.metric("Overhead/Ano", f"R$ {tdabc_resumo['overhead_total']:,.0f}")
        with col4:
            st.metric("Lucro ABC/Ano", f"R$ {tdabc_resumo['lucro_total']:,.0f}")
        
        # Top 3 serviços
        st.markdown("---")
        st.markdown("### 🏅 Top 3 Serviços Mais Rentáveis")
        
        col1, col2, col3 = st.columns(3)
        ranking = tdabc_resumo['ranking'][:3]
        emojis = ["🥇", "🥈", "🥉"]
        cols = [col1, col2, col3]
        
        for i, (col, r) in enumerate(zip(cols, ranking)):
            with col:
                st.markdown(f"""
                <div style="text-align: center; padding: 1rem; background: #f0f2f6; border-radius: 10px;">
                    <h1>{emojis[i]}</h1>
                    <h3>{r['servico']}</h3>
                    <p>Margem: <b>{r['margem_abc']*100:.1f}%</b></p>
                    <p>Lucro: R$ {r['lucro_abc']:,.0f}/ano</p>
                </div>
                """, unsafe_allow_html=True)
    
    # ========== TAB 2: CADASTRO DE SALAS ==========
    with tab2:
        st.markdown("### 🏢 Cadastro de Salas")
        st.caption("Configure a infraestrutura física da clínica")
        
        cadastro = motor.cadastro_salas
        
        # Sincronizar com premissas operacionais
        cadastro.horas_funcionamento_dia = motor.operacional.horas_atendimento_dia
        cadastro.dias_uteis_mes = motor.operacional.dias_uteis_mes
        
        # CORREÇÃO: Verificar se num_salas está configurado
        if motor.operacional.num_salas > 0:
            cadastro.sincronizar_num_salas(motor.operacional.num_salas)
        else:
            st.error("❌ **Nº de Salas = 0!** Configure em **⚙️ Premissas → 🏥 Operacionais** antes de configurar as salas.")
            st.stop()
        
        # Resumo
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Nº Salas (Premissas)", f"{motor.operacional.num_salas}")
        with col2:
            st.metric("m² Total Ativo", f"{cadastro.m2_ativo:.0f} m²")
        with col3:
            st.metric("Capacidade/Mês", f"{cadastro.capacidade_total_horas:.0f}h")
        with col4:
            st.metric("Horas/Dia", f"{motor.operacional.horas_atendimento_dia}h")
        
        st.info(f"ℹ️ Mostrando **{motor.operacional.num_salas} salas** (configurado em **⚙️ Premissas → 🏥 Operacionais**).")
        
        st.markdown("---")
        
        # Lista de salas
        st.markdown("#### 📋 Configuração das Salas")
        
        servicos_disponiveis = list(motor.servicos.keys())
        
        # Criar chave única para detectar mudança de cliente/filial
        estado_atual = f"{st.session_state.get('cliente_id', '')}_{st.session_state.get('filial_id', '')}"
        if 'abc_salas_estado' not in st.session_state or st.session_state.abc_salas_estado != estado_atual:
            # Cliente/filial mudou - limpar session_state das salas
            keys_para_limpar = [k for k in st.session_state.keys() if k.startswith('abc_sala_')]
            for k in keys_para_limpar:
                del st.session_state[k]
            st.session_state.abc_salas_estado = estado_atual
        
        # Usar salas_ativas para garantir que apenas as salas definidas em Premissas apareçam
        for sala in cadastro.salas_ativas:
            # Keys para session_state
            key_m2 = f"abc_sala_{sala.numero}_m2"
            key_tipo = f"abc_sala_{sala.numero}_tipo"
            key_servicos = f"abc_sala_{sala.numero}_servicos"
            
            # Inicializar session_state com valores do objeto (apenas se não existir)
            if key_m2 not in st.session_state:
                st.session_state[key_m2] = float(sala.metros_quadrados)
            if key_tipo not in st.session_state:
                st.session_state[key_tipo] = sala.tipo if sala.tipo in ["Individual", "Compartilhado"] else "Individual"
            if key_servicos not in st.session_state:
                servicos_validos = [s for s in (sala.servicos_atendidos or []) if s in servicos_disponiveis]
                st.session_state[key_servicos] = servicos_validos
            
            # Título do expander (usa valor do session_state)
            m2_atual = st.session_state[key_m2]
            tipo_atual = st.session_state[key_tipo]
            if m2_atual > 0:
                titulo_sala = f"✅ Sala {sala.numero} - {tipo_atual} ({m2_atual:.0f}m²)"
            else:
                titulo_sala = f"⚠️ Sala {sala.numero} - Não configurada"
            
            with st.expander(titulo_sala, expanded=(m2_atual == 0)):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    st.number_input(
                        "m²",
                        min_value=0.0,
                        max_value=200.0,
                        step=1.0,
                        key=key_m2
                    )
                
                with col2:
                    st.selectbox(
                        "Tipo",
                        options=["Individual", "Compartilhado"],
                        key=key_tipo
                    )
                
                # Aviso se sala não configurada
                if st.session_state[key_m2] == 0:
                    st.warning("⚠️ Configure o tamanho (m²) desta sala")
                
                st.markdown("**Serviços atendidos nesta sala:**")
                
                st.multiselect(
                    "Selecione os serviços",
                    options=servicos_disponiveis,
                    key=key_servicos,
                    label_visibility="collapsed"
                )
                
                if st.session_state[key_servicos] and st.session_state[key_m2] > 0:
                    num_servicos = len(st.session_state[key_servicos])
                    m2_por_srv = st.session_state[key_m2] / num_servicos if num_servicos > 0 else 0
                    st.caption(f"m²/serviço: {m2_por_srv:.2f} m²")
        
        st.markdown("---")
        
        # Função para aplicar valores do session_state ao objeto
        def aplicar_valores_salas():
            for sala in cadastro.salas_ativas:
                key_m2 = f"abc_sala_{sala.numero}_m2"
                key_tipo = f"abc_sala_{sala.numero}_tipo"
                key_servicos = f"abc_sala_{sala.numero}_servicos"
                
                if key_m2 in st.session_state:
                    sala.metros_quadrados = float(st.session_state[key_m2])
                if key_tipo in st.session_state:
                    sala.tipo = st.session_state[key_tipo]
                if key_servicos in st.session_state:
                    sala.servicos_atendidos = list(st.session_state[key_servicos])
        
        # Aplicar valores antes de mostrar o mix
        aplicar_valores_salas()
        
        # Mix de alocação
        st.markdown("#### 📊 Mix de Alocação por Serviço")
        
        mix = cadastro.get_mix_servicos()
        
        if mix:
            
            dados_mix = []
            for srv, info in mix.items():
                dados_mix.append({
                    "Serviço": srv,
                    "m² Alocado": f"{info['m2_alocado']:.2f}",
                    "% Espaço": f"{info['pct_espaco']*100:.1f}%",
                    "Nº Salas": info['num_salas'],
                    "Salas": ", ".join([f"Sala {n}" for n in info['salas']])
                })
            
            df_mix = pd.DataFrame(dados_mix)
            st.dataframe(df_mix, use_container_width=True, hide_index=True)
            
            servicos_sem_sala = [s for s in servicos_disponiveis if s not in mix]
            if servicos_sem_sala:
                st.info(f"ℹ️ Serviços sem uso de sala: **{', '.join(servicos_sem_sala)}** (atendimento externo)")
        
        # Botões de ação
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("🗑️ Resetar Salas", use_container_width=True, key="btn_resetar_salas"):
                # Limpar todas as salas para valores em branco
                for sala in cadastro.salas:
                    sala.metros_quadrados = 0.0
                    sala.tipo = "Individual"
                    sala.servicos_atendidos = []
                
                # Limpar cache do session_state
                keys_para_limpar = [k for k in st.session_state.keys() if k.startswith('abc_sala_')]
                for k in keys_para_limpar:
                    del st.session_state[k]
                
                # Salvar imediatamente
                if salvar_filial_atual():
                    st.success("✅ Salas resetadas! Todas em branco.")
                    st.rerun()
        
        with col2:
            if st.button("💾 Salvar Configuração das Salas", type="primary", use_container_width=True, key="btn_salvar_salas"):
                # Aplicar valores do session_state ao objeto ANTES de salvar
                aplicar_valores_salas()
                if salvar_filial_atual():
                    st.success("✅ Configuração das salas salva com sucesso!")
                    st.rerun()
    
    # ========== TAB 3: MIX SALA × SERVIÇO ==========
    with tab3:
        st.markdown("### 🔗 Matriz de Alocação Sala × Serviço")
        
        st.info("""
        Esta matriz mostra **quais salas atendem quais serviços** e a distribuição de m² por serviço.
        Essa informação é usada para o rateio de custos por m² no TDABC.
        """)
        
        # Criar matriz visual
        salas_ativas = motor.cadastro_salas.salas_ativas
        servicos = list(motor.servicos.keys())
        
        # Tabela de alocação
        st.markdown("#### Alocação de Serviços por Sala")
        
        dados_matriz = []
        for sala in salas_ativas:
            linha = {
                'Sala': f"Sala {sala.numero}",
                'm²': f"{sala.metros_quadrados:.0f}",
                'Tipo': sala.tipo
            }
            for servico in servicos:
                linha[servico] = "✅" if servico in sala.servicos_atendidos else "—"
            dados_matriz.append(linha)
        
        df_matriz = pd.DataFrame(dados_matriz)
        st.dataframe(df_matriz, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # m² por serviço
        st.markdown("#### m² Alocado por Serviço")
        
        dados_m2 = []
        total_m2 = motor.cadastro_salas.m2_ativo
        for servico in servicos:
            m2_servico = motor.cadastro_salas.get_m2_por_servico(servico)
            pct = (m2_servico / total_m2 * 100) if total_m2 > 0 else 0
            dados_m2.append({
                'Serviço': servico,
                'm² Alocado': f"{m2_servico:.1f}",
                '% do Total': f"{pct:.1f}%"
            })
        
        df_m2 = pd.DataFrame(dados_m2)
        st.dataframe(df_m2, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Resumo
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Salas Ativas", f"{len(salas_ativas)}")
        with col2:
            st.metric("m² Total Ativo", f"{total_m2:.0f} m²")
        with col3:
            servicos_com_sala = sum(1 for s in servicos if motor.cadastro_salas.get_m2_por_servico(s) > 0)
            st.metric("Serviços com Sala", f"{servicos_com_sala} de {len(servicos)}")
    
    # ========== TAB 4: RATEIO DE CUSTOS ==========
    with tab4:
        st.markdown("### 💰 Rateio de Custos Indiretos")
        
        tdabc_resumo = motor.get_resumo_tdabc()
        
        # Subtotais por direcionador (média mensal)
        st.markdown("#### Subtotais por Direcionador (Média Mensal)")
        
        subtotal_m2 = sum(m['subtotal_m2'] for m in tdabc_resumo['meses']) / 12
        subtotal_sessoes = sum(m['subtotal_sessoes'] for m in tdabc_resumo['meses']) / 12
        subtotal_receita = sum(m['subtotal_receita'] for m in tdabc_resumo['meses']) / 12
        total_overhead = subtotal_m2 + subtotal_sessoes + subtotal_receita
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pct_m2 = (subtotal_m2 / total_overhead * 100) if total_overhead > 0 else 0
            st.metric(
                "📐 Direcionador m²",
                f"R$ {subtotal_m2:,.0f}",
                f"{pct_m2:.0f}% do total"
            )
        
        with col2:
            pct_sess = (subtotal_sessoes / total_overhead * 100) if total_overhead > 0 else 0
            st.metric(
                "🔢 Direcionador Sessões",
                f"R$ {subtotal_sessoes:,.0f}",
                f"{pct_sess:.0f}% do total"
            )
        
        with col3:
            pct_rec = (subtotal_receita / total_overhead * 100) if total_overhead > 0 else 0
            st.metric(
                "💵 Direcionador Receita",
                f"R$ {subtotal_receita:,.0f}",
                f"{pct_rec:.0f}% do total"
            )
        
        with col4:
            st.metric(
                "📊 Total Overhead/Mês",
                f"R$ {total_overhead:,.0f}"
            )
        
        st.markdown("---")
        
        # Detalhamento mensal
        st.markdown("#### 📅 Detalhamento por Mês")
        
        
        dados_meses = []
        for m in tdabc_resumo['meses']:
            dados_meses.append({
                'Mês': m['nome_mes'],
                'Subtotal m²': f"R$ {m['subtotal_m2']:,.0f}",
                'Subtotal Sessões': f"R$ {m['subtotal_sessoes']:,.0f}",
                'Subtotal Receita': f"R$ {m['subtotal_receita']:,.0f}",
                'Total Overhead': f"R$ {m['overhead']:,.0f}"
            })
        
        df_meses = pd.DataFrame(dados_meses)
        st.dataframe(df_meses, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráfico de composição
        st.markdown("#### 📈 Composição do Overhead Mensal")
        
        meses_nomes = [m['nome_mes'] for m in tdabc_resumo['meses']]
        valores_m2 = [m['subtotal_m2'] for m in tdabc_resumo['meses']]
        valores_sess = [m['subtotal_sessoes'] for m in tdabc_resumo['meses']]
        valores_rec = [m['subtotal_receita'] for m in tdabc_resumo['meses']]
        
        fig_comp = go.Figure()
        
        fig_comp.add_trace(go.Bar(
            x=meses_nomes,
            y=valores_m2,
            name='m² (Infraestrutura)',
            marker_color='#2E86AB'
        ))
        
        fig_comp.add_trace(go.Bar(
            x=meses_nomes,
            y=valores_sess,
            name='Sessões (Operacional)',
            marker_color='#F6AE2D'
        ))
        
        fig_comp.add_trace(go.Bar(
            x=meses_nomes,
            y=valores_rec,
            name='Receita (Administrativo)',
            marker_color='#A23B72'
        ))
        
        fig_comp.update_layout(
            height=400,
            barmode='stack',
            yaxis_title="R$",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_comp, use_container_width=True)
    
    # ========== TAB 5: HORAS POR SERVIÇO ==========
    with tab5:
        st.markdown("### ⏱️ Horas de Sala Consumidas por Serviço")
        
        st.info("""
        Mostra quantas **horas de sala** cada serviço consome por mês.
        Serviços que não usam sala física (ex: Domiciliar) têm 0 horas.
        """)
        
        # Tabela mensal de horas
        st.markdown("#### Horas de Sala por Mês")
        
        meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                       "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        # Coletar dados de todos os meses
        servicos = list(motor.servicos.keys())
        dados_horas = {s: [] for s in servicos}
        dados_horas['TOTAL'] = []
        
        for mes in range(12):
            tdabc_mes = motor.calcular_tdabc_mes(mes)
            total_mes = 0
            for servico in servicos:
                if servico in tdabc_mes.rateios:
                    horas = tdabc_mes.rateios[servico].horas_sala
                    dados_horas[servico].append(horas)
                    total_mes += horas
                else:
                    dados_horas[servico].append(0)
            dados_horas['TOTAL'].append(total_mes)
        
        # Criar dataframe
        df_horas_data = []
        for servico in servicos + ['TOTAL']:
            linha = {'Serviço': servico}
            for i, mes in enumerate(meses_nomes):
                linha[mes] = f"{dados_horas[servico][i]:.0f}h"
            linha['Total Ano'] = f"{sum(dados_horas[servico]):.0f}h"
            df_horas_data.append(linha)
        
        df_horas = pd.DataFrame(df_horas_data)
        st.dataframe(df_horas, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráfico de barras - Janeiro como exemplo
        st.markdown("#### Distribuição de Horas (Janeiro)")
        
        tdabc_jan = motor.calcular_tdabc_mes(0)
        servicos_horas = [(s, tdabc_jan.rateios[s].horas_sala) for s in servicos if s in tdabc_jan.rateios]
        servicos_horas.sort(key=lambda x: x[1], reverse=True)
        
        fig_horas = go.Figure()
        fig_horas.add_trace(go.Bar(
            x=[s[0] for s in servicos_horas],
            y=[s[1] for s in servicos_horas],
            marker_color='#2E86AB',
            text=[f"{s[1]:.0f}h" for s in servicos_horas],
            textposition='outside'
        ))
        
        fig_horas.update_layout(
            height=350,
            yaxis_title="Horas de Sala",
            showlegend=False,
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_horas, use_container_width=True)
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        ocupacao = motor.calcular_ocupacao_mes(0)
        
        with col1:
            st.metric("Total Horas/Mês (Jan)", f"{sum(s[1] for s in servicos_horas):.0f}h")
        with col2:
            st.metric("Capacidade Profissionais", f"{ocupacao.capacidade_profissional:.0f}h")
        with col3:
            st.metric("Taxa Ocupação", f"{ocupacao.taxa_ocupacao_profissional*100:.1f}%")
    
    # ========== TAB 6: CUSTO OCIOSIDADE ==========
    with tab6:
        st.markdown("### 💸 Custo de Ociosidade (Capacidade Não Utilizada)")
        
        st.info("""
        O **Custo de Ociosidade** representa o custo da capacidade não utilizada.
        
        **Fórmula:** `Custo Ociosidade = (Custo Infraestrutura / Capacidade) × Horas Ociosas`
        
        Quanto maior a taxa de ocupação, menor o custo de ociosidade.
        """)
        
        # Dados de ocupação e PE
        pe_resumo = motor.get_resumo_pe()
        ocupacao_resumo = motor.get_resumo_ocupacao()
        
        # Métricas principais
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            custo_infra = motor.calcular_custo_infraestrutura_mes()
            st.metric("Custo Infraestrutura/Mês", f"R$ {custo_infra:,.0f}")
        
        with col2:
            st.metric(
                "Custo Ociosidade/Ano",
                f"R$ {pe_resumo['custo_ociosidade_total']:,.0f}"
            )
        
        with col3:
            pct_ebitda = (pe_resumo['custo_ociosidade_total'] / max(1, pe_resumo['ebitda_total'])) * 100
            st.metric("% sobre EBITDA", f"{pct_ebitda:.1f}%")
        
        with col4:
            st.metric("Taxa Ocupação Média", f"{ocupacao_resumo['media_taxa_profissional']*100:.1f}%")
        
        st.markdown("---")
        
        # Tabela mensal
        st.markdown("#### Detalhamento Mensal")
        
        meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                       "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        
        dados_ocio = []
        for i, m in enumerate(pe_resumo['meses']):
            ocup_m = ocupacao_resumo['meses'][i]
            dados_ocio.append({
                'Mês': meses_nomes[i],
                'Capacidade': f"{m.get('capacidade_horas', 0):,.0f}h",
                'Demanda': f"{m.get('demanda_horas', 0):,.0f}h",
                'Horas Ociosas': f"{m.get('horas_ociosas', 0):,.0f}h",
                'Taxa Ocupação': f"{m.get('taxa_ocupacao', 0)*100:.1f}%",
                'Custo Ociosidade': f"R$ {m['custo_ociosidade']:,.0f}",
                '% s/ EBITDA': f"{(m['custo_ociosidade']/max(1,m['ebitda']))*100:.1f}%"
            })
        
        df_ocio = pd.DataFrame(dados_ocio)
        st.dataframe(df_ocio, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Gráfico
        st.markdown("#### Custo de Ociosidade vs EBITDA")
        
        custos_ocio = [m['custo_ociosidade'] for m in pe_resumo['meses']]
        ebitdas = [m['ebitda'] for m in pe_resumo['meses']]
        
        fig_ocio = go.Figure()
        
        fig_ocio.add_trace(go.Bar(
            x=meses_nomes,
            y=ebitdas,
            name='EBITDA',
            marker_color='#2E86AB'
        ))
        
        fig_ocio.add_trace(go.Bar(
            x=meses_nomes,
            y=custos_ocio,
            name='Custo Ociosidade',
            marker_color='#E94F37'
        ))
        
        fig_ocio.update_layout(
            height=350,
            barmode='group',
            yaxis_title="R$",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=50, r=50, t=30, b=50)
        )
        
        st.plotly_chart(fig_ocio, use_container_width=True)
        
        # Insight
        st.markdown("#### 💡 Oportunidade de Otimização")
        taxa_media = ocupacao_resumo['media_taxa_profissional']
        custo_ocio_ano = pe_resumo['custo_ociosidade_total']
        
        if taxa_media < 0.7:
            economia_potencial = custo_ocio_ano * 0.5
            st.warning(f"""
            **Oportunidade identificada:** Taxa de ocupação média de {taxa_media*100:.1f}%.
            
            Se aumentar a ocupação para 85%, você poderia **reduzir R$ {economia_potencial:,.0f}** 
            em custos de ociosidade por ano, aumentando o EBITDA na mesma proporção.
            """)
        else:
            st.success(f"""
            **Boa utilização da capacidade!** Taxa de ocupação média de {taxa_media*100:.1f}%.
            
            O custo de ociosidade de R$ {custo_ocio_ano:,.0f}/ano está controlado.
            """)
    
    # ========== TAB 7: RENTABILIDADE POR SERVIÇO ==========
    with tab7:
        st.markdown("### 🏆 Rentabilidade por Serviço - Análise Completa")
        
        tdabc_resumo = motor.get_resumo_tdabc()
        
        # ====== SEÇÃO 1: RESUMO EXECUTIVO (como Excel L157-L170) ======
        st.markdown("#### 📊 Resumo Executivo Anual")
        
        # Calcular totais
        receita_total = sum(r['receita'] for r in tdabc_resumo['ranking'])
        lucro_total = tdabc_resumo['lucro_total']
        overhead_total = tdabc_resumo['overhead_total']
        
        # CV Total (Receita - Overhead - Lucro)
        cv_total = receita_total - overhead_total - lucro_total
        margem_ebitda = lucro_total / receita_total if receita_total > 0 else 0
        
        # Total sessões anual
        total_sessoes_ano = sum(
            sum(motor.calcular_sessoes_mes(s, m) for s in motor.servicos.keys())
            for m in range(12)
        )
        ticket_medio = receita_total / total_sessoes_ano if total_sessoes_ano > 0 else 0
        lucro_por_sessao = lucro_total / total_sessoes_ano if total_sessoes_ano > 0 else 0
        
        # KPIs em 2 linhas
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Receita Total", f"R$ {receita_total:,.0f}")
        with col2:
            st.metric("Custos Variáveis", f"R$ {cv_total:,.0f}")
        with col3:
            st.metric("Overhead ABC", f"R$ {overhead_total:,.0f}")
        with col4:
            st.metric("EBITDA (Lucro ABC)", f"R$ {lucro_total:,.0f}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Margem EBITDA", f"{margem_ebitda*100:.1f}%")
        with col2:
            st.metric("Total Sessões", f"{total_sessoes_ano:,.0f}")
        with col3:
            st.metric("Ticket Médio", f"R$ {ticket_medio:,.2f}")
        with col4:
            st.metric("Lucro/Sessão", f"R$ {lucro_por_sessao:,.2f}")
        
        st.markdown("---")
        
        # ====== SEÇÃO 1B: INDICADORES DE PRODUTIVIDADE ======
        st.markdown("#### 🏭 Indicadores de Produtividade")
        
        # Calcular horas totais anuais
        total_horas_ano = 0
        horas_por_servico = {}
        for mes in range(12):
            tdabc_mes = motor.calcular_tdabc_mes(mes)
            for servico, rateio in tdabc_mes.rateios.items():
                total_horas_ano += rateio.horas_sala
                if servico not in horas_por_servico:
                    horas_por_servico[servico] = 0
                horas_por_servico[servico] += rateio.horas_sala
        
        # Dados de infraestrutura
        num_salas = motor.cadastro_salas.num_salas_ativas
        m2_total = motor.cadastro_salas.m2_ativo
        
        # Métricas de produtividade
        lucro_por_hora = lucro_total / total_horas_ano if total_horas_ano > 0 else 0
        lucro_por_sala_mes = lucro_total / num_salas / 12 if num_salas > 0 else 0
        lucro_por_sala_ano = lucro_total / num_salas if num_salas > 0 else 0
        lucro_por_m2_mes = lucro_total / m2_total / 12 if m2_total > 0 else 0
        lucro_por_m2_ano = lucro_total / m2_total if m2_total > 0 else 0
        receita_por_m2_mes = receita_total / m2_total / 12 if m2_total > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("💰 Lucro/Hora", f"R$ {lucro_por_hora:,.2f}")
        with col2:
            st.metric("🏢 Lucro/Sala/Mês", f"R$ {lucro_por_sala_mes:,.0f}")
        with col3:
            st.metric("📐 Lucro/m²/Mês", f"R$ {lucro_por_m2_mes:,.2f}")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("⏱️ Total Horas/Ano", f"{total_horas_ano:,.0f}h")
        with col2:
            st.metric("🏢 Lucro/Sala/Ano", f"R$ {lucro_por_sala_ano:,.0f}")
        with col3:
            st.metric("📐 Receita/m²/Mês", f"R$ {receita_por_m2_mes:,.2f}")
        
        st.markdown("---")
        
        # ====== SEÇÃO 1C: PRODUTIVIDADE POR SERVIÇO ======
        st.markdown("#### 📊 Produtividade por Serviço")
        
        dados_produtividade = []
        for servico in motor.servicos.keys():
            # Lucro do serviço
            lucro_servico = 0
            for mes_data in tdabc_resumo['meses']:
                if servico in mes_data['servicos']:
                    lucro_servico += mes_data['servicos'][servico]['lucro_abc']
            
            # Horas do serviço
            horas_servico = horas_por_servico.get(servico, 0)
            
            # m² do serviço
            m2_servico = motor.cadastro_salas.get_m2_por_servico(servico)
            
            # Sessões do serviço
            sessoes_servico = sum(motor.calcular_sessoes_mes(servico, m) for m in range(12))
            
            # Métricas
            lucro_hora = lucro_servico / horas_servico if horas_servico > 0 else 0
            lucro_m2_mes = lucro_servico / m2_servico / 12 if m2_servico > 0 else 0
            lucro_sessao = lucro_servico / sessoes_servico if sessoes_servico > 0 else 0
            
            dados_produtividade.append({
                'Serviço': servico,
                'Lucro Anual': f"R$ {lucro_servico:,.0f}",
                'Horas/Ano': f"{horas_servico:,.0f}h",
                'm² Alocado': f"{m2_servico:.1f}",
                '💰 Lucro/Hora': f"R$ {lucro_hora:,.2f}",
                '📐 Lucro/m²/Mês': f"R$ {lucro_m2_mes:,.2f}",
                '📋 Lucro/Sessão': f"R$ {lucro_sessao:,.2f}"
            })
        
        # Ordenar por Lucro/Hora
        dados_produtividade.sort(key=lambda x: float(x['💰 Lucro/Hora'].replace('R$ ', '').replace(',', '')), reverse=True)
        
        df_prod = pd.DataFrame(dados_produtividade)
        st.dataframe(df_prod, use_container_width=True, hide_index=True)
        
        # Gráfico comparativo
        st.markdown("##### Comparativo de Produtividade")
        
        tab_prod1, tab_prod2, tab_prod3 = st.tabs(["💰 Lucro/Hora", "📐 Lucro/m²", "🏢 Por Sala"])
        
        with tab_prod1:
            servicos_prod = [d['Serviço'] for d in dados_produtividade]
            lucros_hora = [float(d['💰 Lucro/Hora'].replace('R$ ', '').replace(',', '')) for d in dados_produtividade]
            
            fig_lh = go.Figure()
            fig_lh.add_trace(go.Bar(
                x=servicos_prod,
                y=lucros_hora,
                marker_color=['#27AE60' if l > lucro_por_hora else '#E74C3C' for l in lucros_hora],
                text=[f"R$ {l:,.2f}" for l in lucros_hora],
                textposition='outside'
            ))
            fig_lh.add_hline(y=lucro_por_hora, line_dash="dash", 
                           annotation_text=f"Média: R$ {lucro_por_hora:,.2f}/h")
            fig_lh.update_layout(
                title="Lucro por Hora de Sala",
                height=350,
                yaxis_title="R$/Hora"
            )
            st.plotly_chart(fig_lh, use_container_width=True)
            
            st.info("""
            **Interpretação:** Serviços acima da média (verde) são mais produtivos por hora de sala utilizada.
            Serviços abaixo (vermelho) podem ter duração longa demais ou preço baixo.
            """)
        
        with tab_prod2:
            servicos_m2 = [d['Serviço'] for d in dados_produtividade if float(d['📐 Lucro/m²/Mês'].replace('R$ ', '').replace(',', '')) > 0]
            lucros_m2 = [float(d['📐 Lucro/m²/Mês'].replace('R$ ', '').replace(',', '')) for d in dados_produtividade if float(d['📐 Lucro/m²/Mês'].replace('R$ ', '').replace(',', '')) > 0]
            
            if servicos_m2:
                fig_m2 = go.Figure()
                fig_m2.add_trace(go.Bar(
                    x=servicos_m2,
                    y=lucros_m2,
                    marker_color='#3498DB',
                    text=[f"R$ {l:,.2f}" for l in lucros_m2],
                    textposition='outside'
                ))
                fig_m2.add_hline(y=lucro_por_m2_mes, line_dash="dash",
                               annotation_text=f"Média: R$ {lucro_por_m2_mes:,.2f}/m²")
                fig_m2.update_layout(
                    title="Lucro por m² por Mês",
                    height=350,
                    yaxis_title="R$/m²/Mês"
                )
                st.plotly_chart(fig_m2, use_container_width=True)
                
                st.info("""
                **Interpretação:** Quanto maior o Lucro/m², melhor o aproveitamento do espaço físico.
                Serviços sem sala (Domiciliar) não aparecem neste gráfico.
                """)
            else:
                st.warning("Nenhum serviço com m² alocado para exibir.")
        
        with tab_prod3:
            # Lucro por sala (distribuição)
            st.markdown("##### Distribuição de Lucro por Sala")
            
            # Calcular lucro por sala baseado em m²
            dados_sala = []
            for sala in motor.cadastro_salas.salas_ativas:
                lucro_sala = 0
                for servico in sala.servicos_atendidos:
                    # Proporção do m² da sala para o serviço
                    m2_servico_total = motor.cadastro_salas.get_m2_por_servico(servico)
                    if m2_servico_total > 0:
                        proporcao = sala.m2_por_servico / m2_servico_total
                        # Lucro do serviço
                        for mes_data in tdabc_resumo['meses']:
                            if servico in mes_data['servicos']:
                                lucro_sala += mes_data['servicos'][servico]['lucro_abc'] * proporcao
                
                dados_sala.append({
                    'Sala': f"Sala {sala.numero}",
                    'm²': f"{sala.metros_quadrados:.0f}",
                    'Serviços': ', '.join(sala.servicos_atendidos[:2]) + ('...' if len(sala.servicos_atendidos) > 2 else ''),
                    'Lucro/Ano': f"R$ {lucro_sala:,.0f}",
                    'Lucro/Mês': f"R$ {lucro_sala/12:,.0f}",
                    'Lucro/m²/Mês': f"R$ {lucro_sala/sala.metros_quadrados/12:,.2f}" if sala.metros_quadrados > 0 else "R$ 0"
                })
            
            df_sala = pd.DataFrame(dados_sala)
            st.dataframe(df_sala, use_container_width=True, hide_index=True)
            
            # Gráfico pizza de distribuição
            salas_nomes = [d['Sala'] for d in dados_sala]
            lucros_sala = [float(d['Lucro/Ano'].replace('R$ ', '').replace(',', '')) for d in dados_sala]
            
            fig_pizza = go.Figure(data=[go.Pie(
                labels=salas_nomes,
                values=lucros_sala,
                hole=0.4,
                textinfo='label+percent'
            )])
            fig_pizza.update_layout(
                title="Distribuição do Lucro por Sala",
                height=350
            )
            st.plotly_chart(fig_pizza, use_container_width=True)
        
        st.markdown("---")
        
        # ====== SEÇÃO 2: DRE ABC POR SERVIÇO ======
        st.markdown("#### 📋 DRE ABC por Serviço (Anual)")
        
        dados_dre_abc = []
        for r in tdabc_resumo['ranking']:
            servico = r['servico']
            receita = r['receita']
            lucro = r['lucro_abc']
            margem = r['margem_abc']
            
            # Calcular CV e Overhead do serviço
            cv_servico = 0
            overhead_servico = 0
            for mes_data in tdabc_resumo['meses']:
                if servico in mes_data['servicos']:
                    cv_servico += mes_data['servicos'][servico]['cv_rateado']
                    overhead_servico += mes_data['servicos'][servico]['overhead']
            
            # Sessões do serviço
            sessoes_servico = sum(motor.calcular_sessoes_mes(servico, m) for m in range(12))
            lucro_sessao = lucro / sessoes_servico if sessoes_servico > 0 else 0
            
            dados_dre_abc.append({
                'Serviço': servico,
                'Receita': f"R$ {receita:,.0f}",
                '(-) CV': f"R$ {cv_servico:,.0f}",
                '(-) Overhead': f"R$ {overhead_servico:,.0f}",
                '(=) Lucro ABC': f"R$ {lucro:,.0f}",
                'Margem %': f"{margem*100:.1f}%",
                'Sessões': f"{sessoes_servico:,.0f}",
                'Lucro/Sessão': f"R$ {lucro_sessao:,.2f}"
            })
        
        # Adicionar linha de TOTAL
        dados_dre_abc.append({
            'Serviço': '📊 TOTAL',
            'Receita': f"R$ {receita_total:,.0f}",
            '(-) CV': f"R$ {cv_total:,.0f}",
            '(-) Overhead': f"R$ {overhead_total:,.0f}",
            '(=) Lucro ABC': f"R$ {lucro_total:,.0f}",
            'Margem %': f"{margem_ebitda*100:.1f}%",
            'Sessões': f"{total_sessoes_ano:,.0f}",
            'Lucro/Sessão': f"R$ {lucro_por_sessao:,.2f}"
        })
        
        df_dre_abc = pd.DataFrame(dados_dre_abc)
        st.dataframe(df_dre_abc, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # ====== SEÇÃO 3: ANÁLISE DE CONTRIBUIÇÃO ======
        st.markdown("#### 🎯 Análise de Contribuição")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### % Contribuição para Receita")
            dados_contrib_receita = []
            for r in tdabc_resumo['ranking']:
                pct = r['receita'] / receita_total * 100 if receita_total > 0 else 0
                dados_contrib_receita.append({
                    'Serviço': r['servico'],
                    '% Receita': f"{pct:.1f}%",
                    'Valor': f"R$ {r['receita']:,.0f}"
                })
            df_contrib_rec = pd.DataFrame(dados_contrib_receita)
            st.dataframe(df_contrib_rec, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("##### % Contribuição para Lucro")
            dados_contrib_lucro = []
            for r in tdabc_resumo['ranking']:
                pct = r['lucro_abc'] / lucro_total * 100 if lucro_total > 0 else 0
                dados_contrib_lucro.append({
                    'Serviço': r['servico'],
                    '% Lucro': f"{pct:.1f}%",
                    'Valor': f"R$ {r['lucro_abc']:,.0f}"
                })
            df_contrib_luc = pd.DataFrame(dados_contrib_lucro)
            st.dataframe(df_contrib_luc, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # ====== SEÇÃO 4: GRÁFICOS ======
        st.markdown("#### 📈 Visualizações")
        
        tab_g1, tab_g2, tab_g3, tab_g4 = st.tabs([
            "📊 Lucro por Serviço",
            "📈 Margem Comparativa", 
            "🎯 Matriz Rentabilidade",
            "📉 Evolução Mensal"
        ])
        
        servicos = [r['servico'] for r in tdabc_resumo['ranking']]
        lucros = [r['lucro_abc'] for r in tdabc_resumo['ranking']]
        margens = [r['margem_abc'] * 100 for r in tdabc_resumo['ranking']]
        receitas = [r['receita'] for r in tdabc_resumo['ranking']]
        
        # Verificar se há dados para gráficos
        if not servicos or len(servicos) == 0:
            with tab_g1:
                st.warning("Sem dados de serviços. Configure os atendimentos e salas primeiro.")
            with tab_g2:
                st.warning("Sem dados de serviços. Configure os atendimentos e salas primeiro.")
            with tab_g3:
                st.warning("Sem dados de serviços. Configure os atendimentos e salas primeiro.")
            with tab_g4:
                st.warning("Sem dados de serviços. Configure os atendimentos e salas primeiro.")
        else:
            with tab_g1:
                # Gráfico de barras - Lucro ABC
                cores = ['#2E86AB' if m > 20 else '#F6AE2D' if m > 10 else '#E94F37' for m in margens]
                
                fig_lucro = go.Figure()
                fig_lucro.add_trace(go.Bar(
                    x=servicos,
                    y=lucros,
                    marker_color=cores,
                    text=[f"R$ {l:,.0f}" for l in lucros],
                    textposition='outside'
                ))
                fig_lucro.update_layout(
                    title="Lucro ABC Anual por Serviço",
                    height=400,
                    yaxis_title="Lucro ABC (R$)",
                    showlegend=False
                )
                st.plotly_chart(fig_lucro, use_container_width=True)
            
            with tab_g2:
                # Gráfico de barras - Margem %
                cores_margem = ['#27AE60' if m > 20 else '#F39C12' if m > 15 else '#E74C3C' for m in margens]
                
                fig_margem = go.Figure()
                fig_margem.add_trace(go.Bar(
                    x=servicos,
                    y=margens,
                    marker_color=cores_margem,
                    text=[f"{m:.1f}%" for m in margens],
                    textposition='outside'
                ))
                fig_margem.add_hline(y=margem_ebitda*100, line_dash="dash", 
                                    annotation_text=f"Média: {margem_ebitda*100:.1f}%")
                fig_margem.update_layout(
                    title="Margem ABC por Serviço",
                    height=400,
                    yaxis_title="Margem (%)",
                    showlegend=False
                )
                st.plotly_chart(fig_margem, use_container_width=True)
            
            with tab_g3:
                # Scatter plot - Receita vs Margem
                fig_matriz = go.Figure()
                max_lucro = max(lucros) if lucros and max(lucros) > 0 else 1  # Evita divisão por zero
                fig_matriz.add_trace(go.Scatter(
                    x=receitas,
                    y=margens,
                    mode='markers+text',
                    marker=dict(
                        size=[l/max_lucro*50 + 10 if max_lucro > 0 else 10 for l in lucros],
                        color=margens,
                        colorscale='RdYlGn',
                        showscale=True,
                        colorbar=dict(title="Margem %")
                    ),
                    text=servicos,
                    textposition='top center'
                ))
                
                # Linhas de referência (média)
                num_servicos = len(servicos) if servicos else 1
                fig_matriz.add_vline(x=receita_total/num_servicos, line_dash="dash", 
                                    line_color="gray", opacity=0.5)
                fig_matriz.add_hline(y=margem_ebitda*100, line_dash="dash", 
                                    line_color="gray", opacity=0.5)
                
                # Quadrantes
                fig_matriz.add_annotation(x=receita_total*0.8/num_servicos, y=30, text="⭐ Estrela",
                                         showarrow=False, font=dict(size=12, color="green"))
                fig_matriz.add_annotation(x=receita_total*1.5/num_servicos, y=30, text="💎 Vaca Leiteira",
                                         showarrow=False, font=dict(size=12, color="blue"))
                fig_matriz.add_annotation(x=receita_total*0.8/num_servicos, y=10, text="❓ Interrogação",
                                         showarrow=False, font=dict(size=12, color="orange"))
                fig_matriz.add_annotation(x=receita_total*1.5/num_servicos, y=10, text="🐕 Abacaxi",
                                         showarrow=False, font=dict(size=12, color="red"))
                
                fig_matriz.update_layout(
                    title="Matriz de Rentabilidade (Receita vs Margem)",
                    height=500,
                    xaxis_title="Receita Anual (R$)",
                    yaxis_title="Margem ABC (%)"
                )
                st.plotly_chart(fig_matriz, use_container_width=True)
                
                st.info("""
                **Interpretação:**
                - ⭐ **Estrela**: Alta margem, baixa receita → Potencial de crescimento
                - 💎 **Vaca Leiteira**: Alta margem, alta receita → Manter e proteger
                - ❓ **Interrogação**: Baixa margem, baixa receita → Avaliar continuidade
                - 🐕 **Abacaxi**: Baixa margem, alta receita → Otimizar custos urgente
                """)
            
            with tab_g4:
                # Evolução mensal da margem
                meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                              "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
                
                fig_evolucao = go.Figure()
                
                cores_linha = ['#2E86AB', '#E94F37', '#27AE60', '#9B59B6', '#F39C12', '#1ABC9C']
                
                for idx, servico in enumerate(servicos):
                    margens_mes = []
                    for mes_data in tdabc_resumo['meses']:
                        if servico in mes_data['servicos']:
                            margens_mes.append(mes_data['servicos'][servico]['margem_abc'] * 100)
                        else:
                            margens_mes.append(0)
                    
                    fig_evolucao.add_trace(go.Scatter(
                        x=meses_nomes,
                        y=margens_mes,
                        mode='lines+markers',
                        name=servico,
                        line=dict(color=cores_linha[idx % len(cores_linha)])
                    ))
                
                fig_evolucao.update_layout(
                    title="Evolução da Margem ABC por Serviço",
                    height=450,
                    yaxis_title="Margem ABC (%)",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(fig_evolucao, use_container_width=True)
        
        st.markdown("---")
        
        # ====== SEÇÃO 5: RANKING E INSIGHTS ======
        st.markdown("#### 🏅 Ranking de Rentabilidade")
        
        if not tdabc_resumo.get('ranking') or len(tdabc_resumo['ranking']) == 0:
            st.warning("Sem dados de ranking. Configure os atendimentos e salas primeiro.")
        else:
            posicao_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]
            ranking_data = []
            
            for i, r in enumerate(tdabc_resumo['ranking']):
                emoji = posicao_emoji[i] if i < len(posicao_emoji) else f"{i+1}º"
                pct_lucro = r['lucro_abc'] / lucro_total * 100 if lucro_total > 0 else 0
                ranking_data.append({
                    "Pos": emoji,
                    "Serviço": r['servico'],
                    "Receita": f"R$ {r['receita']:,.0f}",
                    "Lucro ABC": f"R$ {r['lucro_abc']:,.0f}",
                    "Margem": f"{r['margem_abc']*100:.1f}%",
                    "% do Lucro Total": f"{pct_lucro:.1f}%"
                })
            
            df_ranking = pd.DataFrame(ranking_data)
            st.dataframe(df_ranking, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # ====== SEÇÃO 6: INSIGHTS ESTRATÉGICOS ======
            st.markdown("#### 💡 Insights Estratégicos")
            
            melhor = tdabc_resumo['ranking'][0]
            pior = tdabc_resumo['ranking'][-1]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.success(f"""
                **🏆 Serviço Mais Rentável:** {melhor['servico']}
                
                - Margem ABC: **{melhor['margem_abc']*100:.1f}%**
                - Lucro Anual: R$ {melhor['lucro_abc']:,.0f}
                - Contribuição: {melhor['lucro_abc']/lucro_total*100 if lucro_total > 0 else 0:.1f}% do lucro total
                
                ✅ **Recomendação:** Investir na expansão deste serviço
                """)
            
            with col2:
                pct_lucro_pior = pior['lucro_abc']/lucro_total*100 if lucro_total > 0 else 0
                st.warning(f"""
                **⚠️ Menor Rentabilidade:** {pior['servico']}
                
                - Margem ABC: **{pior['margem_abc']*100:.1f}%**
                - Lucro Anual: R$ {pior['lucro_abc']:,.0f}
                - Contribuição: {pct_lucro_pior:.1f}% do lucro total
                
                🔧 **Recomendação:** Revisar precificação ou custos
                """)
            
            # Serviços sem sala (vantagem competitiva)
            mix = motor.cadastro_salas.get_mix_servicos()
            servicos_sem_sala = [s for s in motor.servicos.keys() if s not in mix]
            
            if servicos_sem_sala:
                # Verificar se serviço sem sala tem boa margem
                for r in tdabc_resumo['ranking']:
                    if r['servico'] in servicos_sem_sala:
                        st.info(f"""
                        💡 **{r['servico']}** não usa sala física (atendimento domiciliar/externo).
                        
                        Margem de **{r['margem_abc']*100:.1f}%** - sem custo de infraestrutura por m²!
                        
                        → Oportunidade: Expandir atendimentos externos para aumentar rentabilidade.
                        """)
            
            # Análise de concentração
            if lucro_total > 0:
                top3_pct = sum(r['lucro_abc'] for r in tdabc_resumo['ranking'][:3]) / lucro_total * 100
                if top3_pct > 80:
                    st.warning(f"""
                    ⚠️ **Alta Concentração:** Os 3 principais serviços representam **{top3_pct:.1f}%** do lucro total.
                    
                    Considere diversificar para reduzir riscos.
                    """)
        
        # Detalhamento mensal (expansível) - só mostra se há dados
        if tdabc_resumo.get('meses') and len(tdabc_resumo['meses']) > 0:
            with st.expander("📋 Ver Detalhamento Mensal Completo"):
                mes_sel = st.selectbox(
                    "Selecione o mês",
                    options=range(12),
                    format_func=lambda x: ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                                           "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"][x],
                    key="abc_mes_sel"
                )
                
                mes_data = tdabc_resumo['meses'][mes_sel]
                
                st.markdown(f"##### {mes_data['nome_mes']}")
                
                dados_mes = []
                total_receita_mes = 0
                total_cv_mes = 0
                total_overhead_mes = 0
                total_lucro_mes = 0
                
                for srv, info in mes_data['servicos'].items():
                    total_receita_mes += info['receita']
                    total_cv_mes += info['cv_rateado']
                    total_overhead_mes += info['overhead']
                    total_lucro_mes += info['lucro_abc']
                    
                    dados_mes.append({
                        "Serviço": srv,
                        "Receita": f"R$ {info['receita']:,.0f}",
                        "(-) CV": f"R$ {info['cv_rateado']:,.0f}",
                        "(-) Overhead": f"R$ {info['overhead']:,.0f}",
                        "(=) Lucro ABC": f"R$ {info['lucro_abc']:,.0f}",
                        "Margem": f"{info['margem_abc']*100:.1f}%"
                    })
                
                # Linha de total
                dados_mes.append({
                    "Serviço": "📊 TOTAL",
                    "Receita": f"R$ {total_receita_mes:,.0f}",
                    "(-) CV": f"R$ {total_cv_mes:,.0f}",
                    "(-) Overhead": f"R$ {total_overhead_mes:,.0f}",
                    "(=) Lucro ABC": f"R$ {total_lucro_mes:,.0f}",
                    "Margem": f"{total_lucro_mes/total_receita_mes*100:.1f}%" if total_receita_mes > 0 else "0%"
                })
                
                df_mes = pd.DataFrame(dados_mes)
                st.dataframe(df_mes, use_container_width=True, hide_index=True)


def pagina_importar():
    """Página de importação de dados de planilha Excel"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>📥 Importar Dados de Planilha</h3></div>', unsafe_allow_html=True)
    
    st.info("""
    **Importação de dados de planilha Excel**
    
    Esta funcionalidade permite importar dados de uma planilha Budget padrão.
    O sistema irá extrair automaticamente:
    - Serviços e valores
    - Fisioterapeutas e suas sessões
    - Despesas fixas
    - Premissas operacionais
    """)
    
    # Verificar se há cliente selecionado
    if not st.session_state.cliente_id:
        st.warning("⚠️ Selecione um cliente antes de importar dados.")
        return
    
    if not st.session_state.filial_id or st.session_state.filial_id == "consolidado":
        st.warning("⚠️ Selecione uma filial (não consolidado) antes de importar dados.")
        return
    
    st.markdown("---")
    
    # Upload de arquivo
    uploaded_file = st.file_uploader(
        "Selecione a planilha Excel (.xlsx)",
        type=['xlsx', 'xls'],
        help="Faça upload da planilha Budget no formato padrão"
    )
    
    if uploaded_file:
        st.success(f"✅ Arquivo carregado: {uploaded_file.name}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            importar_servicos = st.checkbox("Importar Serviços", value=True)
            importar_fisios = st.checkbox("Importar Fisioterapeutas", value=True)
        
        with col2:
            importar_despesas = st.checkbox("Importar Despesas Fixas", value=True)
            importar_premissas = st.checkbox("Importar Premissas", value=True)
        
        st.markdown("---")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Iniciar Importação", type="primary", use_container_width=True):
                with st.spinner("Processando planilha..."):
                    try:
                        from modules.excel_parser import BudgetExcelParser, importar_budget
                        
                        # Salvar arquivo temporário
                        import tempfile
                        import os
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
                            tmp.write(uploaded_file.getvalue())
                            tmp_path = tmp.name
                        
                        try:
                            # Tentar importar
                            motor = st.session_state.motor
                            
                            # Usar o parser
                            parser = BudgetExcelParser(tmp_path)
                            dados = parser.extrair_dados()
                            
                            if dados:
                                # Aplicar dados ao motor
                                if importar_servicos and 'servicos' in dados:
                                    for nome, srv in dados['servicos'].items():
                                        motor.servicos[nome] = srv
                                    st.success(f"✅ {len(dados.get('servicos', {}))} serviços importados")
                                
                                if importar_fisios and 'fisioterapeutas' in dados:
                                    for nome, fisio in dados['fisioterapeutas'].items():
                                        motor.fisioterapeutas[nome] = fisio
                                    st.success(f"✅ {len(dados.get('fisioterapeutas', {}))} fisioterapeutas importados")
                                
                                if importar_despesas and 'despesas' in dados:
                                    for nome, desp in dados['despesas'].items():
                                        motor.despesas_fixas[nome] = desp
                                    st.success(f"✅ {len(dados.get('despesas', {}))} despesas importadas")
                                
                                # Salvar alterações
                                if salvar_filial_atual():
                                    st.success("✅ Importação concluída! Dados salvos.")
                                    st.balloons()
                            else:
                                st.error("❌ Não foi possível extrair dados da planilha.")
                        
                        finally:
                            # Limpar arquivo temporário
                            os.unlink(tmp_path)
                    
                    except ImportError:
                        registrar_erro("BE-600", "Módulo excel_parser não encontrado", "pagina_clientes/importar")
                        st.error("❌ Módulo de importação não disponível (excel_parser).")
                    except Exception as e:
                        erro_msg = registrar_erro("BE-600", str(e), "pagina_clientes/importar")
                        st.error(f"❌ Erro na importação: {erro_msg}")
    else:
        st.caption("Arraste ou clique para selecionar um arquivo Excel.")


def pagina_clientes():
    """Página de gestão de clientes e projetos - usa cliente_manager"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>👥 Clientes e Filiais</h3></div>', unsafe_allow_html=True)
    
    manager = st.session_state.cliente_manager
    
    # Lista de clientes - FILTRA POR EMPRESA DO USUÁRIO
    todos_clientes = manager.listar_clientes()
    
    # Verificar se deve filtrar
    user = get_current_user() if AUTH_ENABLED else None
    is_admin = user and user.get("role") == "admin" if user else True
    
    if is_admin:
        # Admin vê todos os clientes
        clientes = todos_clientes
    else:
        # Usuário comum vê apenas clientes da sua empresa
        empresa_nome = user.get("companies", {}).get("name", "") if user else ""
        clientes = [c for c in todos_clientes if c["nome"].lower() == empresa_nome.lower()]
        
        # Se não encontrar cliente com nome exato, tenta busca parcial
        if not clientes and empresa_nome:
            clientes = [c for c in todos_clientes if empresa_nome.lower() in c["nome"].lower() or c["nome"].lower() in empresa_nome.lower()]
    
    col_header1, col_header2 = st.columns([3, 1])
    with col_header1:
        st.markdown(f"**{len(clientes)} cliente(s) cadastrado(s)**")
    with col_header2:
        # Só admin pode criar novos clientes
        if is_admin:
            if st.button("➕ Novo Cliente", use_container_width=True):
                st.session_state.show_novo_cliente = True
        else:
            st.caption("Somente admin pode criar clientes")
    
    # Formulário de novo cliente
    if st.session_state.get('show_novo_cliente', False):
        with st.expander("➕ Cadastrar Novo Cliente", expanded=True):
            with st.form("form_novo_cliente"):
                col1, col2 = st.columns(2)
                with col1:
                    nome = st.text_input("Nome da Clínica *")
                    cnpj = st.text_input("CNPJ")
                with col2:
                    contato = st.text_input("Contato Principal")
                    email = st.text_input("E-mail")
                    telefone = st.text_input("Telefone")
                
                col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
                with col_btn1:
                    submitted = st.form_submit_button("💾 Cadastrar", use_container_width=True)
                with col_btn2:
                    cancelled = st.form_submit_button("❌ Cancelar", use_container_width=True)
                
                if submitted:
                    if nome:
                        try:
                            cliente = manager.criar_cliente(
                                nome=nome,
                                cnpj=cnpj,
                                contato=contato,
                                email=email,
                                telefone=telefone
                            )
                            st.success(f"✅ Cliente '{nome}' cadastrado!")
                            st.session_state.show_novo_cliente = False
                            st.rerun()
                        except ValueError as e:
                            erro_msg = registrar_erro("BE-202", str(e), "pagina_clientes/criar_cliente")
                            st.error(f"Erro: {erro_msg}")
                    else:
                        st.error("Nome é obrigatório!")
                
                if cancelled:
                    st.session_state.show_novo_cliente = False
                    st.rerun()
    
    st.markdown("---")
    
    # Lista de clientes com filiais
    if not clientes:
        st.info("🏢 Nenhum cliente cadastrado. Clique em '➕ Novo Cliente' para começar!")
    else:
        for cliente in clientes:
            cliente_id = cliente.get('id', cliente.get('nome', ''))
            
            # Card do cliente com expander para filiais
            with st.expander(f"🏢 **{cliente.get('nome', '-')}**", expanded=False):
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown("**📋 Dados do Cliente**")
                    st.text(f"CNPJ: {cliente.get('cnpj', '-')}")
                    st.text(f"Contato: {cliente.get('contato', '-')}")
                    st.text(f"E-mail: {cliente.get('email', '-')}")
                    st.text(f"Telefone: {cliente.get('telefone', '-')}")
                
                with col2:
                    # Filiais do cliente
                    filiais = manager.listar_filiais(cliente_id)
                    st.markdown(f"**🏥 Filiais ({len(filiais)})**")
                    
                    if filiais:
                        for filial in filiais:
                            filial_id = filial.get('id', '')
                            filial_nome = filial.get('nome', filial_id)
                            
                            # Linha com nome da filial e botões
                            col_f1, col_f2, col_f3 = st.columns([3, 1, 1])
                            with col_f1:
                                st.markdown(f"• **{filial_nome}**")
                            with col_f2:
                                if st.button("✏️", key=f"edit_filial_{cliente_id}_{filial_id}", help="Editar filial"):
                                    st.session_state[f'show_edit_filial_{cliente_id}_{filial_id}'] = True
                            with col_f3:
                                if st.button("🗑️", key=f"del_filial_{cliente_id}_{filial_id}", help="Excluir filial"):
                                    st.session_state[f'confirm_del_filial_{cliente_id}_{filial_id}'] = True
                    else:
                        st.caption("Nenhuma filial cadastrada")
                    
                    # Botão para nova filial
                    if st.button("➕ Nova Filial", key=f"nova_filial_{cliente_id}"):
                        st.session_state[f'show_nova_filial_{cliente_id}'] = True
                
                with col3:
                    st.markdown("**⚡ Ações**")
                    
                    if st.button("📊 Selecionar", key=f"sel_{cliente_id}", use_container_width=True):
                        st.session_state.cliente_id = cliente_id
                        st.session_state.cliente_atual = manager.carregar_cliente(cliente_id)
                        st.success(f"✅ {cliente.get('nome')}")
                        st.rerun()
                    
                    if st.button("✏️ Editar", key=f"edit_{cliente_id}", use_container_width=True):
                        st.session_state[f'show_edit_{cliente_id}'] = True
                    
                    if st.button("🗑️ Excluir", key=f"del_{cliente_id}", use_container_width=True):
                        st.session_state[f'confirm_del_{cliente_id}'] = True
                    
                    # Visão consolidada
                    if len(filiais) > 1:
                        if st.button("📈 Consolidado", key=f"cons_{cliente_id}", use_container_width=True):
                            st.session_state.cliente_id = cliente_id
                            st.session_state.filial_id = "consolidado"
                            st.session_state.cliente_atual = manager.carregar_cliente(cliente_id)
                            st.success("✅ Visão Consolidada")
                            st.rerun()
                
                # Confirmação de exclusão
                if st.session_state.get(f'confirm_del_{cliente_id}', False):
                    st.markdown("---")
                    st.warning(f"⚠️ Confirma exclusão de **{cliente.get('nome')}**? Esta ação não pode ser desfeita!")
                    col_del1, col_del2 = st.columns(2)
                    with col_del1:
                        if st.button("✅ Sim, Excluir", key=f"confirm_yes_{cliente_id}", use_container_width=True):
                            try:
                                manager.excluir_cliente(cliente_id)
                                st.success("✅ Cliente excluído!")
                                st.session_state[f'confirm_del_{cliente_id}'] = False
                                # Limpa cliente atual se for o excluído
                                if st.session_state.get('cliente_id') == cliente_id:
                                    st.session_state.cliente_id = None
                                    st.session_state.cliente_atual = None
                                st.rerun()
                            except Exception as e:
                                erro_msg = registrar_erro("BE-206", str(e), "pagina_clientes/excluir_cliente")
                                st.error(f"Erro: {erro_msg}")
                    with col_del2:
                        if st.button("❌ Cancelar", key=f"confirm_no_{cliente_id}", use_container_width=True):
                            st.session_state[f'confirm_del_{cliente_id}'] = False
                            st.rerun()
                
                # Formulário de edição
                if st.session_state.get(f'show_edit_{cliente_id}', False):
                    st.markdown("---")
                    st.markdown("**✏️ Editar Cliente**")
                    
                    with st.form(f"form_edit_{cliente_id}"):
                        col_e1, col_e2 = st.columns(2)
                        with col_e1:
                            edit_nome = st.text_input("Nome", value=cliente.get('nome', ''), key=f"edit_nome_{cliente_id}")
                            edit_cnpj = st.text_input("CNPJ", value=cliente.get('cnpj', ''), key=f"edit_cnpj_{cliente_id}")
                        with col_e2:
                            edit_contato = st.text_input("Contato", value=cliente.get('contato', ''), key=f"edit_contato_{cliente_id}")
                            edit_email = st.text_input("E-mail", value=cliente.get('email', ''), key=f"edit_email_{cliente_id}")
                            edit_telefone = st.text_input("Telefone", value=cliente.get('telefone', ''), key=f"edit_telefone_{cliente_id}")
                        
                        col_eb1, col_eb2 = st.columns(2)
                        with col_eb1:
                            if st.form_submit_button("💾 Salvar", use_container_width=True):
                                try:
                                    # Carrega cliente atual e atualiza
                                    cliente_obj = manager.carregar_cliente(cliente_id)
                                    if cliente_obj:
                                        cliente_obj.nome = edit_nome
                                        cliente_obj.cnpj = edit_cnpj
                                        cliente_obj.contato = edit_contato
                                        cliente_obj.email = edit_email
                                        cliente_obj.telefone = edit_telefone
                                        manager.atualizar_cliente(cliente_obj)
                                        st.success("✅ Cliente atualizado!")
                                        st.session_state[f'show_edit_{cliente_id}'] = False
                                        st.rerun()
                                except Exception as e:
                                    erro_msg = registrar_erro("BE-204", str(e), "pagina_clientes/editar_cliente")
                                    st.error(f"Erro: {erro_msg}")
                        with col_eb2:
                            if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                st.session_state[f'show_edit_{cliente_id}'] = False
                                st.rerun()
                
                # Formulário de nova filial (inline)
                if st.session_state.get(f'show_nova_filial_{cliente_id}', False):
                    st.markdown("---")
                    st.markdown("**➕ Nova Filial**")
                    
                    col_f1, col_f2 = st.columns([3, 1])
                    with col_f1:
                        nome_filial = st.text_input(
                            "Nome da Filial", 
                            value="Matriz",
                            key=f"nome_filial_{cliente_id}"
                        )
                    with col_f2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("💾 Criar Filial", key=f"criar_filial_{cliente_id}"):
                            if nome_filial:
                                try:
                                    manager.criar_filial(cliente_id, nome_filial)
                                    st.success(f"✅ Filial '{nome_filial}' criada!")
                                    st.session_state[f'show_nova_filial_{cliente_id}'] = False
                                    st.rerun()
                                except Exception as e:
                                    erro_msg = registrar_erro("BE-203", str(e), "pagina_clientes/criar_filial")
                                    st.error(f"Erro: {erro_msg}")
                
                # Formulários de edição e exclusão de filiais
                for filial in filiais:
                    filial_id = filial.get('id', '')
                    filial_nome = filial.get('nome', filial_id)
                    
                    # Formulário de edição de filial
                    if st.session_state.get(f'show_edit_filial_{cliente_id}_{filial_id}', False):
                        st.markdown("---")
                        st.markdown(f"**✏️ Editar Filial: {filial_nome}**")
                        
                        with st.form(f"form_edit_filial_{cliente_id}_{filial_id}"):
                            novo_nome_filial = st.text_input(
                                "Nome da Filial",
                                value=filial_nome,
                                key=f"edit_nome_filial_{cliente_id}_{filial_id}"
                            )
                            
                            col_efb1, col_efb2 = st.columns(2)
                            with col_efb1:
                                if st.form_submit_button("💾 Salvar", use_container_width=True):
                                    try:
                                        # Renomear a filial no arquivo da filial
                                        import os
                                        filial_path = f"data/clientes/{cliente_id}/{filial_id}.json"
                                        if os.path.exists(filial_path):
                                            with open(filial_path, 'r', encoding='utf-8') as f:
                                                filial_data = json.load(f)
                                            filial_data['nome'] = novo_nome_filial
                                            with open(filial_path, 'w', encoding='utf-8') as f:
                                                json.dump(filial_data, f, ensure_ascii=False, indent=2)
                                            st.success(f"✅ Filial renomeada para '{novo_nome_filial}'!")
                                            st.session_state[f'show_edit_filial_{cliente_id}_{filial_id}'] = False
                                            st.rerun()
                                        else:
                                            erro_msg = registrar_erro("BE-302", f"filial_path={filial_path}", "pagina_clientes/editar_filial")
                                            st.error(f"Arquivo não encontrado: {filial_path}")
                                    except Exception as e:
                                        erro_msg = registrar_erro("BE-205", str(e), "pagina_clientes/editar_filial")
                                        st.error(f"Erro: {erro_msg}")
                            with col_efb2:
                                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                    st.session_state[f'show_edit_filial_{cliente_id}_{filial_id}'] = False
                                    st.rerun()
                    
                    # Confirmação de exclusão de filial
                    if st.session_state.get(f'confirm_del_filial_{cliente_id}_{filial_id}', False):
                        st.markdown("---")
                        st.warning(f"⚠️ Confirma exclusão da filial **{filial_nome}**? Esta ação não pode ser desfeita!")
                        col_df1, col_df2 = st.columns(2)
                        with col_df1:
                            if st.button("✅ Sim, Excluir", key=f"confirm_yes_filial_{cliente_id}_{filial_id}", use_container_width=True):
                                try:
                                    if hasattr(manager, 'excluir_filial'):
                                        manager.excluir_filial(cliente_id, filial_id)
                                    else:
                                        # Alternativa: excluir diretamente
                                        import os
                                        filial_json = f"data/clientes/{cliente_id}/{filial_id}.json"
                                        if os.path.exists(filial_json):
                                            os.remove(filial_json)
                                        # Atualizar config - filiais é lista de strings (IDs)
                                        config_path = f"data/clientes/{cliente_id}/config.json"
                                        if os.path.exists(config_path):
                                            with open(config_path, 'r', encoding='utf-8') as f:
                                                config = json.load(f)
                                            # Filtra removendo o ID da filial (é string, não dict)
                                            config['filiais'] = [f_id for f_id in config.get('filiais', []) if f_id != filial_id]
                                            with open(config_path, 'w', encoding='utf-8') as f:
                                                json.dump(config, f, ensure_ascii=False, indent=2)
                                    st.success("✅ Filial excluída!")
                                    st.session_state[f'confirm_del_filial_{cliente_id}_{filial_id}'] = False
                                    # Limpa filial atual se for a excluída
                                    if st.session_state.get('filial_id') == filial_id:
                                        st.session_state.filial_id = None
                                    st.rerun()
                                except Exception as e:
                                    erro_msg = registrar_erro("BE-207", str(e), "pagina_clientes/excluir_filial")
                                    st.error(f"Erro: {erro_msg}")
                        with col_df2:
                            if st.button("❌ Cancelar", key=f"confirm_no_filial_{cliente_id}_{filial_id}", use_container_width=True):
                                st.session_state[f'confirm_del_filial_{cliente_id}_{filial_id}'] = False
                                st.rerun()
    
    # Resumo no rodapé
    st.markdown("---")
    total_filiais = sum(len(manager.listar_filiais(c.get('id', c.get('nome', '')))) for c in clientes)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Clientes", len(clientes))
    with col2:
        st.metric("Total Filiais", total_filiais)
    with col3:
        cliente_ativo = st.session_state.get('cliente_atual')
        if cliente_ativo:
            nome_ativo = cliente_ativo.nome if hasattr(cliente_ativo, 'nome') else cliente_ativo.get('nome', '-')
            st.metric("Cliente Ativo", nome_ativo[:15])
        else:
            st.metric("Cliente Ativo", "Nenhum")


def pagina_dre():
    """Página de DRE detalhado"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>📊 Demonstração do Resultado (DRE)</h3></div>', unsafe_allow_html=True)
    
    if st.session_state.dados_importados is None:
        st.info("Importe um arquivo de budget para visualizar o DRE.")
        return
    
    dados = st.session_state.dados_importados
    
    if 'dre' not in dados:
        st.warning("Dados do DRE não disponíveis.")
        return
    
    # Tabela completa
    dados_tabela = []
    for item in dados['dre']:
        if item['conta'].strip():
            row = {'Conta': item['conta']}
            for mes in MESES_ABREV:
                val = item.get(mes.lower())
                row[mes] = val if val else 0
            row['Total'] = item.get('total', 0)
            dados_tabela.append(row)
    
    df = pd.DataFrame(dados_tabela)
    
    # Formata valores
    for col in df.columns[1:]:
        df[col] = df[col].apply(lambda x: format_currency(x, prefix="") if isinstance(x, (int, float)) else x)
    
    st.dataframe(df, use_container_width=True, hide_index=True, height=600)


def pagina_fluxo_caixa():
    """Página de Fluxo de Caixa"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>💰 Fluxo de Caixa</h3></div>', unsafe_allow_html=True)
    
    if st.session_state.dados_importados is None:
        st.info("Importe um arquivo de budget para visualizar o Fluxo de Caixa.")
        return
    
    dados = st.session_state.dados_importados
    
    if 'fluxo_caixa' not in dados:
        st.warning("Dados do Fluxo de Caixa não disponíveis.")
        return
    
    # Separa entradas e saídas
    entradas = [d for d in dados['fluxo_caixa'] if d['tipo'] == 'entrada']
    saidas = [d for d in dados['fluxo_caixa'] if d['tipo'] == 'saida']
    
    tab1, tab2 = st.tabs(["📈 Entradas", "📉 Saídas"])
    
    with tab1:
        if entradas:
            dados_tabela = []
            for item in entradas:
                row = {'Descrição': item['descricao']}
                for mes in MESES_ABREV:
                    row[mes] = format_currency(item.get(mes.lower()), prefix="")
                row['Total'] = format_currency(item.get('total'), prefix="")
                dados_tabela.append(row)
            st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)
    
    with tab2:
        if saidas:
            dados_tabela = []
            for item in saidas:
                row = {'Descrição': item['descricao']}
                for mes in MESES_ABREV:
                    row[mes] = format_currency(item.get(mes.lower()), prefix="")
                row['Total'] = format_currency(item.get('total'), prefix="")
                dados_tabela.append(row)
            st.dataframe(pd.DataFrame(dados_tabela), use_container_width=True, hide_index=True)



def pagina_fc_simulado():
    """Página de Fluxo de Caixa Simulado - Usa o motor de cálculo dinâmico"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>🏦 Fluxo de Caixa Simulado</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    pfc = motor.premissas_fc
    fp = motor.pagamento
    
    # ==========================================
    # RESUMO RÁPIDO DAS PREMISSAS
    # ==========================================
    with st.expander("⚙️ **Premissas do FC**", expanded=False):
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Saldo Inicial", f"R$ {pfc.caixa_inicial:,.0f}")
        with col2:
            total_ant = pfc.receita_out_ano_anterior + pfc.receita_nov_ano_anterior + pfc.receita_dez_ano_anterior
            st.metric("CR Ano Ant. (3m)", f"R$ {total_ant:,.0f}")
        with col3:
            st.metric("Mix Cartão", f"{fp.cartao_credito:.0%} crédito")
        with col4:
            st.metric("Antecipação", f"{fp.pct_antecipacao:.0%}")
        with col5:
            modo = "🎯 Realista" if pfc.recebimento_avista_no_mes else "📊 Planilha"
            st.metric("Modo", modo)
        
        # Investimentos e Financiamentos
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🏗️ Investimentos (CAPEX)**")
            for i, inv in enumerate(motor.premissas_financeiras.investimentos):
                inv.ativo = st.checkbox(
                    f"{inv.descricao} (R$ {inv.valor_total:,.0f})",
                    value=inv.ativo,
                    key=f"fc_inv_{i}"
                )
        with col2:
            st.markdown("**🏦 Financiamentos**")
            for i, fin in enumerate(motor.premissas_financeiras.financiamentos):
                fin.ativo = st.checkbox(
                    f"{fin.descricao} (Saldo R$ {fin.saldo_devedor:,.0f})",
                    value=fin.ativo,
                    key=f"fc_fin_{i}"
                )
    
    # ==========================================
    # CÁLCULOS
    # ==========================================
    # Calcular DRE primeiro (necessário para o FC)
    dre = motor.calcular_dre()
    
    # Calcular FC
    fc = motor.calcular_fluxo_caixa()
    
    # Resumo
    resumo = motor.get_resumo_fluxo_caixa()
    
    # Cards de resumo - Linha 1: Fluxo de Caixa
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Entradas", f"R$ {resumo['total_entradas']:,.0f}")
    with col2:
        st.metric("Total Saídas", f"R$ {resumo['total_saidas']:,.0f}")
    with col3:
        delta_color = "normal" if resumo['saldo_final'] >= 0 else "inverse"
        st.metric("Saldo Final Caixa", f"R$ {resumo['saldo_final']:,.0f}", 
                  delta=f"R$ {resumo['variacao_ano']:,.0f}", delta_color=delta_color)
    with col4:
        status_color = "🟢" if resumo['meses_atencao'] == 0 else "🔴"
        st.metric("Meses em Atenção", f"{status_color} {resumo['meses_atencao']}")
    
    # Cards de resumo - Linha 2: Aplicações (se houver política de saldo mínimo)
    saldo_minimo = motor.premissas_fc.saldo_minimo
    if saldo_minimo > 0 or resumo.get('saldo_aplicacoes_final', 0) > 0:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🏦 Saldo Aplicações", 
                      f"R$ {resumo.get('saldo_aplicacoes_final', 0):,.0f}",
                      delta=f"R$ {resumo.get('total_rendimentos', 0):,.0f} rend.")
        with col2:
            st.metric("📤 Total Aportes", f"R$ {resumo.get('total_aportes', 0):,.0f}")
        with col3:
            st.metric("📥 Total Resgates", f"R$ {resumo.get('total_resgates', 0):,.0f}")
        with col4:
            # Liquidez total = Caixa + Aplicações
            liquidez = resumo['saldo_final'] + resumo.get('saldo_aplicacoes_final', 0)
            st.metric("💰 Liquidez Total", f"R$ {liquidez:,.0f}")
    
    st.markdown("---")
    
    # Abas de detalhamento - AGORA COM 4 ABAS incluindo Premissas!
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visão Geral", "📈 Entradas", "📉 Saídas", "⚙️ Premissas"])
    
    MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    with tab1:
        # Tabela de Fluxo Resumido
        st.markdown("#### Fluxo de Caixa Mensal")
        
        # Construir HTML da tabela
        html = '<table style="width:100%; border-collapse:collapse; font-size:12px;">'
        html += '<tr style="background:#1e3a5f;color:white;"><th style="padding:8px;text-align:left;">Conta</th>'
        for m in MESES:
            html += f'<th style="padding:8px;text-align:right;">{m}</th>'
        html += '<th style="padding:8px;text-align:right;">TOTAL</th></tr>'
        
        # Linhas principais
        contas_resumo = [
            ("Total Entradas", "Total Entradas", "#e8f5e9", "#2e7d32"),
            ("Total Saídas", "Total Saídas", "#ffebee", "#c62828"),
            ("(+/-) Variação", "(+/-) Variação", "#fff3e0", "#ef6c00"),
            ("Saldo Inicial", "Saldo Inicial", "#e3f2fd", "#1565c0"),
            ("Saldo Final", "Saldo Final", "#e8eaf6", "#283593"),
        ]
        
        for nome, conta, bg, color in contas_resumo:
            valores = fc.get(conta, [0]*12)
            total = sum(valores)
            html += f'<tr style="background:{bg};"><td style="padding:6px;font-weight:bold;color:{color};">{nome}</td>'
            for v in valores:
                cor = "#c62828" if v < 0 else "#2e7d32" if v > 0 else "#666"
                html += f'<td style="padding:6px;text-align:right;color:{cor};">{v:,.0f}</td>'
            cor = "#c62828" if total < 0 else "#2e7d32"
            html += f'<td style="padding:6px;text-align:right;font-weight:bold;color:{cor};">{total:,.0f}</td></tr>'
        
        # Status
        status = fc.get("Status", ["OK"]*12)
        html += '<tr style="background:#f5f5f5;"><td style="padding:6px;font-weight:bold;">Status</td>'
        for s in status:
            cor = "#2e7d32" if s == "OK" else "#c62828"
            html += f'<td style="padding:6px;text-align:center;color:{cor};font-weight:bold;">{s}</td>'
        html += '<td></td></tr>'
        
        # Saldo Aplicações (se houver)
        saldo_aplic = fc.get("Saldo Aplicações", [0]*12)
        if any(v > 0 for v in saldo_aplic):
            html += '<tr style="background:#fff8e1;"><td style="padding:6px;font-weight:bold;color:#f57f17;">🏦 Saldo Aplicações</td>'
            for v in saldo_aplic:
                html += f'<td style="padding:6px;text-align:right;color:#f57f17;">{v:,.0f}</td>'
            html += f'<td style="padding:6px;text-align:right;font-weight:bold;color:#f57f17;">{saldo_aplic[-1]:,.0f}</td></tr>'
        
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
        
        # Gráfico de evolução do saldo
        st.markdown("#### Evolução do Saldo")
        
        saldo_final = fc.get("Saldo Final", [0]*12)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=MESES,
            y=saldo_final,
            marker_color=['#c62828' if v < 0 else '#2e7d32' for v in saldo_final],
            name="Saldo Caixa"
        ))
        
        # Adiciona linha de saldo mínimo se configurado
        if saldo_minimo > 0:
            fig.add_hline(y=saldo_minimo, line_dash="dash", line_color="orange", 
                         annotation_text=f"Mínimo: R$ {saldo_minimo:,.0f}")
        
        # Adiciona linha de aplicações se houver
        saldo_aplic = fc.get("Saldo Aplicações", [0]*12)
        if any(v > 0 for v in saldo_aplic):
            fig.add_trace(go.Scatter(
                x=MESES,
                y=saldo_aplic,
                mode='lines+markers',
                name="Aplicações",
                line=dict(color='#f57f17', width=2),
                marker=dict(size=6)
            ))
        
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        fig.update_layout(
            height=300,
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis_title="",
            yaxis_title="R$",
            showlegend=True if any(v > 0 for v in saldo_aplic) else False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Gráficos adicionais lado a lado
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("#### Entradas vs Saídas")
            
            entradas = fc.get("Total Entradas", [0]*12)
            saidas = [abs(v) for v in fc.get("Total Saídas", [0]*12)]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=MESES,
                y=entradas,
                name='Entradas',
                marker_color='#2e7d32'
            ))
            fig2.add_trace(go.Bar(
                x=MESES,
                y=saidas,
                name='Saídas',
                marker_color='#c62828'
            ))
            fig2.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis_title="R$",
                barmode='group',
                legend=dict(orientation="h", yanchor="bottom", y=1.02)
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        with col_g2:
            st.markdown("#### Composição das Saídas")
            
            # Busca imposto correto (Simples ou Carnê Leão)
            imposto_simples = abs(sum(fc.get("(-) DAS Simples Nacional", [0]*12)))
            imposto_carne = abs(sum(fc.get("(-) Carnê Leão (INSS+IR)", [0]*12)))
            
            saidas_componentes = {
                'Folha Proprietários': abs(sum(fc.get("(-) Folha Proprietários", [0]*12))),
                'Folha Fisioterapeutas': abs(sum(fc.get("(-) Folha Fisioterapeutas", [0]*12))),
                'Folha CLT': abs(sum(fc.get("(-) Folha CLT Líquida", [0]*12))),
                'Impostos': imposto_simples + imposto_carne,  # Soma dos dois (só um terá valor)
                'Despesas Operacionais': abs(sum(fc.get("(-) Despesas Operacionais", [0]*12))),
                'Custos Cartão': abs(sum(fc.get("(-) Custos Financeiros Cartão", [0]*12))),
                'Dividendos': abs(sum(fc.get("(-) Distribuição Dividendos", [0]*12))),
                'Outros': abs(sum(fc.get("(-) INSS + FGTS", [0]*12))) + abs(sum(fc.get("(-) Pró-labore + INSS", [0]*12))),
            }
            
            # Filtrar componentes com valor > 0
            saidas_componentes = {k: v for k, v in saidas_componentes.items() if v > 0}
            
            if saidas_componentes:
                fig3 = go.Figure(data=[go.Pie(
                    labels=list(saidas_componentes.keys()),
                    values=list(saidas_componentes.values()),
                    hole=.4,
                    textinfo='percent+label'
                )])
                
                fig3.update_layout(
                    height=300,
                    margin=dict(l=20, r=20, t=20, b=20),
                    showlegend=False
                )
                
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.info("Sem dados de saídas para exibir")
        
        # ========== SEÇÃO DE APLICAÇÕES ==========
        saldo_aplic = fc.get("Saldo Aplicações", [0]*12)
        if any(v > 0 for v in saldo_aplic) or saldo_minimo > 0:
            st.markdown("---")
            st.markdown("#### 🏦 Gestão de Aplicações")
            
            # Cards de resumo
            col_ap1, col_ap2, col_ap3, col_ap4 = st.columns(4)
            
            total_aportes = sum(fc.get("_Aportes Aplicações", [0]*12))
            total_resgates = sum(fc.get("_Resgates Aplicações", [0]*12))
            total_rendimentos = sum(fc.get("(+) Rendimentos Aplicações", [0]*12))
            saldo_inicial_aplic = motor.premissas_financeiras.aplicacoes.saldo_inicial
            saldo_final_aplic = saldo_aplic[-1] if saldo_aplic else 0
            
            with col_ap1:
                delta_aplic = saldo_final_aplic - saldo_inicial_aplic
                st.metric("Saldo Aplicações", 
                         f"R$ {saldo_final_aplic:,.0f}",
                         delta=f"R$ {delta_aplic:+,.0f}")
            with col_ap2:
                st.metric("Total Aportes", f"R$ {total_aportes:,.0f}")
            with col_ap3:
                st.metric("Total Resgates", f"R$ {total_resgates:,.0f}")
            with col_ap4:
                st.metric("Rendimentos no Ano", f"R$ {total_rendimentos:,.0f}")
            
            # Tabela de evolução mensal das aplicações
            with st.expander("📊 Evolução Mensal das Aplicações"):
                html_aplic = '<table style="width:100%; border-collapse:collapse; font-size:12px;">'
                html_aplic += '<tr style="background:linear-gradient(135deg, #f57f17 0%, #ff8f00 100%);color:white;">'
                html_aplic += '<th style="padding:8px;text-align:left;">Mês</th>'
                html_aplic += '<th style="padding:8px;text-align:right;">Saldo Início</th>'
                html_aplic += '<th style="padding:8px;text-align:right;">Aportes</th>'
                html_aplic += '<th style="padding:8px;text-align:right;">Resgates</th>'
                html_aplic += '<th style="padding:8px;text-align:right;">Rendimentos</th>'
                html_aplic += '<th style="padding:8px;text-align:right;">Saldo Final</th>'
                html_aplic += '</tr>'
                
                aportes = fc.get("_Aportes Aplicações", [0]*12)
                resgates = fc.get("_Resgates Aplicações", [0]*12)
                rendimentos = fc.get("(+) Rendimentos Aplicações", [0]*12)
                
                for m in range(12):
                    saldo_ini = saldo_inicial_aplic if m == 0 else saldo_aplic[m-1]
                    bg = "#fffde7" if m % 2 == 0 else "#fff8e1"
                    html_aplic += f'<tr style="background:{bg};">'
                    html_aplic += f'<td style="padding:6px;font-weight:bold;">{MESES[m]}</td>'
                    html_aplic += f'<td style="padding:6px;text-align:right;">{saldo_ini:,.0f}</td>'
                    html_aplic += f'<td style="padding:6px;text-align:right;color:#2e7d32;">{aportes[m]:,.0f}</td>'
                    html_aplic += f'<td style="padding:6px;text-align:right;color:#c62828;">{resgates[m]:,.0f}</td>'
                    html_aplic += f'<td style="padding:6px;text-align:right;color:#1565c0;">{rendimentos[m]:,.0f}</td>'
                    html_aplic += f'<td style="padding:6px;text-align:right;font-weight:bold;">{saldo_aplic[m]:,.0f}</td>'
                    html_aplic += '</tr>'
                
                # Linha total
                html_aplic += '<tr style="background:linear-gradient(135deg, #f57f17 0%, #ff8f00 100%);color:white;font-weight:bold;">'
                html_aplic += '<td style="padding:8px;">TOTAL</td>'
                html_aplic += f'<td style="padding:8px;text-align:right;">{saldo_inicial_aplic:,.0f}</td>'
                html_aplic += f'<td style="padding:8px;text-align:right;">{total_aportes:,.0f}</td>'
                html_aplic += f'<td style="padding:8px;text-align:right;">{total_resgates:,.0f}</td>'
                html_aplic += f'<td style="padding:8px;text-align:right;">{total_rendimentos:,.0f}</td>'
                html_aplic += f'<td style="padding:8px;text-align:right;">{saldo_final_aplic:,.0f}</td>'
                html_aplic += '</tr>'
                html_aplic += '</table>'
                
                st.markdown(html_aplic, unsafe_allow_html=True)
    
    with tab2:
        st.markdown("#### Detalhamento das Entradas")
        
        # Busca DINÂMICA de todas as contas de entrada
        contas_entradas = []
        for conta in fc.keys():
            if conta.startswith("(+)") and conta != "(+) Rendimentos Aplicações":
                valores = fc[conta]
                if sum(valores) > 0:  # Só adiciona se tiver valor
                    contas_entradas.append(conta)
        
        # Ordena alfabeticamente e adiciona Rendimentos no final
        contas_entradas.sort()
        if "(+) Rendimentos Aplicações" in fc and sum(fc["(+) Rendimentos Aplicações"]) > 0:
            contas_entradas.append("(+) Rendimentos Aplicações")
        contas_entradas.append("Total Entradas")
        
        html = '<table style="width:100%; border-collapse:collapse; font-size:12px;">'
        html += '<tr style="background:#2e7d32;color:white;"><th style="padding:8px;text-align:left;">Recebimentos por Serviço</th>'
        for m in MESES:
            html += f'<th style="padding:8px;text-align:right;">{m}</th>'
        html += '<th style="padding:8px;text-align:right;background:#1b5e20;">TOTAL</th></tr>'
        
        for i, conta in enumerate(contas_entradas):
            if conta not in fc:
                continue
            valores = fc[conta]
            total = sum(valores)
            is_total = "Total" in conta
            
            # Cores alternadas para melhor leitura
            if is_total:
                bg = "#c8e6c9"
                weight = "bold"
            else:
                bg = "#f5f5f5" if i % 2 == 0 else "#fff"
                weight = "normal"
            
            # Nome mais limpo (remove o prefixo "+")
            nome_limpo = conta.replace("(+) ", "📥 ") if not is_total else "📊 " + conta
            
            html += f'<tr style="background:{bg};"><td style="padding:6px;font-weight:{weight};">{nome_limpo}</td>'
            for v in valores:
                color = "#2e7d32" if v > 0 else "#666"
                html += f'<td style="padding:6px;text-align:right;color:{color};">{v:,.0f}</td>'
            html += f'<td style="padding:6px;text-align:right;font-weight:bold;background:#e8f5e9;">{total:,.0f}</td></tr>'
        
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
    
    with tab3:
        st.markdown("#### Detalhamento das Saídas")
        
        # Lista organizada por categoria
        categorias_saidas = {
            "💼 FOLHA DE PAGAMENTO": [
                "(-) Folha Proprietários", "(-) Folha Fisioterapeutas", 
                "(-) Folha CLT Líquida", "(-) INSS + FGTS", "(-) Pró-labore + INSS"
            ],
            "📋 IMPOSTOS": [
                "(-) DAS Simples Nacional", "(-) Carnê Leão (INSS+IR)"
            ],
            "🏢 OPERACIONAL": [
                "(-) Benefícios (VT, VR, Planos)", "(-) Despesas Operacionais", 
                "(-) Custos Financeiros Cartão"
            ],
            "💳 FINANCEIRO": [
                "(-) Parcelas Financiamentos", "(-) Parcelas Novos Invest.",
                "(-) Entrada CAPEX", "(-) Juros Cheque Especial"
            ],
            "💰 DISTRIBUIÇÃO": [
                "(-) Distribuição Dividendos"
            ]
        }
        
        html = '<table style="width:100%; border-collapse:collapse; font-size:12px;">'
        html += '<tr style="background:#c62828;color:white;"><th style="padding:8px;text-align:left;">Pagamentos</th>'
        for m in MESES:
            html += f'<th style="padding:8px;text-align:right;">{m}</th>'
        html += '<th style="padding:8px;text-align:right;background:#b71c1c;">TOTAL</th></tr>'
        
        row_idx = 0
        for categoria, contas in categorias_saidas.items():
            # Verifica se categoria tem algum valor
            tem_valores = False
            for conta in contas:
                if conta in fc and sum(fc[conta]) != 0:
                    tem_valores = True
                    break
            
            if not tem_valores:
                continue
            
            # Cabeçalho da categoria
            html += f'<tr style="background:#ffcdd2;"><td colspan="14" style="padding:6px;font-weight:bold;font-size:11px;">{categoria}</td></tr>'
            
            for conta in contas:
                if conta not in fc:
                    continue
                valores = fc[conta]
                total = sum(valores)
                
                # Pula se tudo zerado
                if total == 0:
                    continue
                
                row_idx += 1
                bg = "#fff5f5" if row_idx % 2 == 0 else "#fff"
                
                # Nome mais limpo
                nome_limpo = conta.replace("(-) ", "📤 ")
                
                html += f'<tr style="background:{bg};"><td style="padding:6px;padding-left:20px;">{nome_limpo}</td>'
                for v in valores:
                    color = "#c62828" if v < 0 else "#666"
                    html += f'<td style="padding:6px;text-align:right;color:{color};">{abs(v):,.0f}</td>'
                html += f'<td style="padding:6px;text-align:right;font-weight:bold;background:#ffebee;">{abs(total):,.0f}</td></tr>'
        
        # Total Saídas
        if "Total Saídas" in fc:
            valores = fc["Total Saídas"]
            total = sum(valores)
            html += f'<tr style="background:#ef9a9a;"><td style="padding:8px;font-weight:bold;">📊 Total Saídas</td>'
            for v in valores:
                html += f'<td style="padding:8px;text-align:right;font-weight:bold;">{abs(v):,.0f}</td>'
            html += f'<td style="padding:8px;text-align:right;font-weight:bold;background:#e57373;">{abs(total):,.0f}</td></tr>'
        
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
    
    # ==========================================
    # ABA 4: PREMISSAS DO FLUXO DE CAIXA
    # ==========================================
    with tab4:
        st.markdown("#### ⚙️ Premissas do Fluxo de Caixa")
        st.caption("Configure as premissas que afetam o cálculo do Fluxo de Caixa")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # === SALDOS INICIAIS ===
            st.markdown("##### 💰 Saldos Iniciais (01/Janeiro)")
            
            pfc.caixa_inicial = st.number_input(
                "Caixa e Bancos",
                value=float(pfc.caixa_inicial),
                min_value=0.0,
                step=1000.0,
                format="%.0f",
                key="pfc_caixa_ini",
                help="Saldo em caixa no início do ano orçado"
            )
            
            # Saldo de Aplicações Financeiras
            aplic = motor.premissas_financeiras.aplicacoes
            aplic.saldo_inicial = st.number_input(
                "💵 Aplicações Financeiras",
                value=float(aplic.saldo_inicial),
                min_value=0.0,
                step=5000.0,
                format="%.0f",
                key="pfc_aplicacoes",
                help="Saldo em aplicações que renderá juros mensalmente"
            )
            
            # Mostra taxa e rendimento estimado
            if aplic.saldo_inicial > 0:
                rend_mensal_est = aplic.saldo_inicial * aplic.taxa_mensal
                rend_anual_est = rend_mensal_est * 12
                st.caption(f"📈 Taxa: {aplic.taxa_selic_anual:.1%} a.a. ({aplic.taxa_mensal:.2%}/mês)")
                st.caption(f"💰 Rendimento estimado: ~R$ {rend_anual_est:,.0f}/ano")
            
            # CP Fornecedores - só mostra campo editável se modo manual
            if not pfc.usar_cp_folha_auto:
                # Calcular valor de dezembro para sugestão
                motor.calcular_despesas_fixas()
                motor.calcular_dre()
                despesas_dez = sum(v[11] for k, v in motor.despesas.items() if "Total" not in k)
                cv_dez = abs(motor.dre.get("Total Custos Variáveis", [0]*12)[11])
                cp_forn_sugerido = despesas_dez + cv_dez
                
                pfc.cp_fornecedores = st.number_input(
                    "CP Fornecedores",
                    value=float(pfc.cp_fornecedores) if pfc.cp_fornecedores > 0 else float(cp_forn_sugerido),
                    min_value=0.0,
                    step=500.0,
                    format="%.0f",
                    key="pfc_cp_forn",
                    help="Contas a Pagar - Fornecedores (pago em Janeiro)"
                )
            
            st.markdown("---")
            
            # === RECEITA ANO ANTERIOR ===
            st.markdown("##### 📅 Receita do Ano Anterior")
            st.caption("Valores que serão recebidos nos primeiros meses devido ao PMR")
            
            # Calcular receita média projetada para sugestão automática
            motor.calcular_dre()
            receita_bruta_total = motor.dre.get("Receita Bruta Total", [0]*12)
            receita_media_projetada = sum(receita_bruta_total) / 12 if sum(receita_bruta_total) > 0 else 0
            
            # Opção: Calcular automaticamente
            pfc.usar_receita_auto = st.checkbox(
                "📊 Calcular automaticamente (baseado na receita projetada)", 
                value=pfc.usar_receita_auto, 
                key="pfc_usar_auto",
                help="Usa a receita média mensal projetada como base para o ano anterior"
            )
            
            if pfc.usar_receita_auto:
                st.success(f"✅ Usando receita média projetada: **R$ {receita_media_projetada:,.0f}/mês**")
                st.info(f"📊 Out, Nov, Dez = R$ {receita_media_projetada:,.0f} cada → CR Total: R$ {receita_media_projetada * 3:,.0f}")
                # Valores são calculados automaticamente no motor, não precisa setar aqui
            else:
                # Modo manual
                usar_media = st.checkbox("Usar mesmo valor para Out/Nov/Dez", value=True, key="pfc_usar_media")
                
                if usar_media:
                    # Se não tem valor configurado, sugere a receita projetada
                    valor_atual = max(pfc.receita_out_ano_anterior, pfc.receita_nov_ano_anterior, pfc.receita_dez_ano_anterior)
                    if valor_atual == 0:
                        valor_atual = receita_media_projetada
                    
                    receita_media = st.number_input(
                        "Receita Média Mensal",
                        value=float(valor_atual),
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        key="pfc_rec_media",
                        help="Receita média mensal do ano anterior. Será aplicada para Out, Nov e Dez."
                    )
                    pfc.receita_out_ano_anterior = receita_media
                    pfc.receita_nov_ano_anterior = receita_media
                    pfc.receita_dez_ano_anterior = receita_media
                    total_anterior = receita_media * 3
                    st.info(f"📊 Out, Nov, Dez = R$ {receita_media:,.0f} cada → CR Total: R$ {total_anterior:,.0f}")
                else:
                    pfc.receita_out_ano_anterior = st.number_input(
                        "Outubro",
                        value=float(pfc.receita_out_ano_anterior) if pfc.receita_out_ano_anterior > 0 else float(receita_media_projetada),
                        min_value=0.0,
                        step=5000.0,
                        format="%.0f",
                        key="pfc_rec_out",
                        help="Receita de serviços de outubro que será recebida no ano orçado"
                    )
                    
                    pfc.receita_nov_ano_anterior = st.number_input(
                        "Novembro",
                        value=float(pfc.receita_nov_ano_anterior) if pfc.receita_nov_ano_anterior > 0 else float(receita_media_projetada),
                        min_value=0.0,
                        step=5000.0,
                        format="%.0f",
                        key="pfc_rec_nov",
                        help="Receita de serviços de novembro"
                    )
                    
                    pfc.receita_dez_ano_anterior = st.number_input(
                        "Dezembro",
                        value=float(pfc.receita_dez_ano_anterior) if pfc.receita_dez_ano_anterior > 0 else float(receita_media_projetada),
                        min_value=0.0,
                        step=5000.0,
                        format="%.0f",
                        key="pfc_rec_dez",
                        help="Receita de serviços de dezembro"
                    )
                    
                    total_anterior = pfc.receita_out_ano_anterior + pfc.receita_nov_ano_anterior + pfc.receita_dez_ano_anterior
                    st.metric("Total a Receber do Ano Anterior", f"R$ {total_anterior:,.0f}")
        
        with col2:
            # === FOLHA - SALDOS INICIAIS ===
            st.markdown("##### 👥 CP Folha (pago em Janeiro)")
            
            # Calcular valores de Dezembro para preview
            motor.calcular_dre()
            folha_fisio = motor.projetar_folha_fisioterapeutas_anual()
            folha_geral = motor.projetar_folha_anual()
            
            regime = motor.premissas_folha.regime_tributario
            is_pf = "Carnê" in regime or "PF" in regime
            is_simples = "Simples" in regime
            
            # Valores de Dezembro projetados
            dez_prop = folha_fisio[11]["total_proprietarios"]
            dez_fisio = folha_fisio[11]["total_fisioterapeutas"]
            dez_clt_bruto = folha_geral[11]["clt"]["salarios_brutos"]
            dez_clt_inss = folha_geral[11]["clt"]["inss"]
            dez_clt_fgts = folha_geral[11]["clt"]["fgts"]
            dez_clt_liquido = dez_clt_bruto - dez_clt_inss
            dez_informal = folha_geral[11]["informal"]["liquido"]
            dez_encargos = dez_clt_fgts if (is_simples or is_pf) else (dez_clt_fgts + dez_clt_bruto * 0.20)
            
            # Imposto de Dezembro
            if is_pf:
                imposto_dez = abs(motor.dre.get("(-) Carnê Leão (PF)", [0]*12)[11])
            else:
                imposto_dez = abs(motor.dre.get("(-) Simples Nacional", [0]*12)[11])
            
            # Despesas + Custos Variáveis de Dezembro (CP Fornecedores)
            motor.calcular_despesas_fixas()
            despesas_dez = sum(v[11] for k, v in motor.despesas.items() if "Total" not in k)
            cv_dez = abs(motor.dre.get("Total Custos Variáveis", [0]*12)[11])
            cp_forn_dez = despesas_dez + cv_dez
            
            pfc.usar_cp_folha_auto = st.checkbox(
                "📊 Calcular CP automaticamente (baseado em Dezembro)",
                value=pfc.usar_cp_folha_auto,
                key="pfc_usar_cp_auto",
                help="Usa a folha e despesas projetadas de Dezembro como saldo inicial"
            )
            
            if pfc.usar_cp_folha_auto:
                st.success("✅ CP calculado baseado em Dezembro projetado")
                
                # Mostra valores calculados
                st.caption(f"Proprietários: **R$ {dez_prop:,.0f}**")
                if not is_pf:
                    st.caption(f"Fisioterapeutas: **R$ {dez_fisio:,.0f}**")
                    st.caption(f"CLT Líquida: **R$ {dez_clt_liquido + dez_informal:,.0f}**")
                    st.caption(f"INSS+FGTS: **R$ {dez_encargos:,.0f}**")
                st.caption(f"Impostos (Dez): **R$ {imposto_dez:,.0f}**")
                st.caption(f"Fornecedores (Dez): **R$ {cp_forn_dez:,.0f}**")
            else:
                # Modo manual - campos editáveis
                pfc.cp_retirada_proprietarios = st.number_input(
                    "Retirada Proprietários",
                    value=float(pfc.cp_retirada_proprietarios) if pfc.cp_retirada_proprietarios > 0 else float(dez_prop),
                    min_value=0.0,
                    step=1000.0,
                    format="%.0f",
                    key="pfc_cp_prop",
                    help="Comissão de proprietários de dezembro"
                )
                
                if not is_pf:
                    pfc.cp_folha_fisioterapeutas = st.number_input(
                        "Folha Fisioterapeutas",
                        value=float(pfc.cp_folha_fisioterapeutas) if pfc.cp_folha_fisioterapeutas > 0 else float(dez_fisio),
                        min_value=0.0,
                        step=1000.0,
                        format="%.0f",
                        key="pfc_cp_fisio",
                        help="Comissão de fisioterapeutas de dezembro"
                    )
                    
                    pfc.cp_folha_colaboradores = st.number_input(
                        "Folha CLT",
                        value=float(pfc.cp_folha_colaboradores) if pfc.cp_folha_colaboradores > 0 else float(dez_clt_liquido + dez_informal),
                        min_value=0.0,
                        step=500.0,
                        format="%.0f",
                        key="pfc_cp_clt",
                        help="Salários CLT de dezembro"
                    )
                    
                    pfc.cp_encargos_clt = st.number_input(
                        "INSS + FGTS",
                        value=float(pfc.cp_encargos_clt) if pfc.cp_encargos_clt > 0 else float(dez_encargos),
                        min_value=0.0,
                        step=100.0,
                        format="%.0f",
                        key="pfc_cp_encargos",
                        help="Encargos CLT de dezembro (Simples: só FGTS)"
                    )
                
                pfc.cp_impostos = st.number_input(
                    "CP Impostos (Dez)",
                    value=float(pfc.cp_impostos) if pfc.cp_impostos > 0 else float(imposto_dez),
                    min_value=0.0,
                    step=500.0,
                    format="%.0f",
                    key="pfc_cp_imp_manual",
                    help="Imposto de Dezembro do ano anterior (pago em Janeiro)"
                )
            
            st.markdown("---")
            
            # === MODO DE CÁLCULO ===
            st.markdown("##### 🎯 Modo de Cálculo")
            
            pfc.recebimento_avista_no_mes = st.checkbox(
                "Modo Realista (considera formas de pagamento)",
                value=pfc.recebimento_avista_no_mes,
                key="pfc_modo_real",
                help="Se ativo: Dinheiro/PIX/Débito entra no mesmo mês. Se desativado: tudo segue PMR."
            )
            
            if pfc.recebimento_avista_no_mes:
                st.success("✅ **Modo Realista Ativo** - Considera formas de pagamento")
                
                # Mostra valores das premissas (somente leitura)
                pct_avista = fp.dinheiro_pix + fp.cartao_debito
                pct_credito = fp.cartao_credito
                pct_antecip = fp.cartao_credito * fp.pct_antecipacao
                
                st.caption(f"📊 Mix atual: À vista **{pct_avista:.0%}** | Crédito **{pct_credito:.0%}** | "
                          f"Antecipação **{fp.pct_antecipacao:.0%}**")
                st.caption("*(editar em Premissas > Pagamentos)*")
                
                # Resumo do modo
                st.info(f"**{pct_avista + pct_antecip:.0%}** da receita entra no mesmo mês")
            else:
                st.warning("📊 **Modo Planilha** - Toda receita segue PMR (compatível com Excel)")
            
            st.markdown("---")
            
            # === POLÍTICA DE CAIXA ===
            st.markdown("##### 🏦 Política de Caixa")
            pfc.saldo_minimo = st.number_input(
                "Saldo Mínimo Desejado",
                value=float(pfc.saldo_minimo),
                min_value=0.0,
                step=5000.0,
                format="%.0f",
                key="pfc_saldo_min",
                help="Saldo mínimo que deve ser mantido em caixa. O excesso será aplicado automaticamente."
            )
            
            # Explicação da política
            if pfc.saldo_minimo > 0:
                st.success(f"""
                **📊 Política Automática de Aplicações Ativa**
                
                Com saldo mínimo de **R$ {pfc.saldo_minimo:,.0f}**, o sistema irá:
                - ✅ **Aplicar** automaticamente todo excesso acima deste valor
                - ✅ **Resgatar** das aplicações quando o caixa ficar abaixo do mínimo
                - ✅ **Calcular rendimentos** sobre o saldo aplicado (taxa configurada em Financeiro > Aplicações)
                
                *O caixa será mantido próximo ao mínimo, maximizando os rendimentos.*
                """)
                
                # Mostrar configuração atual de aplicações
                st.markdown("---")
                st.markdown("##### 🏦 Configuração de Aplicações")
                
                aplic = motor.premissas_financeiras.aplicacoes
                
                col_a1, col_a2, col_a3, col_a4 = st.columns(4)
                with col_a1:
                    st.metric("Saldo Inicial", f"R$ {aplic.saldo_inicial:,.0f}")
                with col_a2:
                    st.metric("Taxa Selic", f"{aplic.taxa_selic_anual*100:.2f}% a.a.")
                with col_a3:
                    st.metric("% CDI", f"{aplic.pct_cdi*100:.0f}%")
                with col_a4:
                    st.metric("Taxa Mensal", f"{aplic.taxa_mensal*100:.4f}%")
                
                st.caption("💡 *Para alterar estas configurações, vá em **Financeiro > Aplicações***")
                
            else:
                st.info("""
                **💡 Dica:** Configure um saldo mínimo para ativar a política automática de aplicações.
                O sistema irá aplicar automaticamente o excesso de caixa e resgatar quando necessário.
                """)
                
                # Mesmo sem política, mostra configuração atual
                aplic = motor.premissas_financeiras.aplicacoes
                if aplic.saldo_inicial > 0:
                    st.markdown("---")
                    st.markdown("##### 🏦 Aplicações Existentes (sem política ativa)")
                    col_a1, col_a2, col_a3 = st.columns(3)
                    with col_a1:
                        st.metric("Saldo Inicial", f"R$ {aplic.saldo_inicial:,.0f}")
                    with col_a2:
                        st.metric("Taxa Selic", f"{aplic.taxa_selic_anual*100:.2f}% a.a.")
                    with col_a3:
                        rend_anual_est = aplic.saldo_inicial * aplic.taxa_mensal * 12
                        st.metric("Rendimento Estimado/Ano", f"R$ {rend_anual_est:,.0f}")
                    st.caption("⚠️ *Sem saldo mínimo configurado, os aportes/resgates não são automáticos.*")
        
        st.markdown("---")
        
        # === PARCELAMENTO DE CARTÃO ===
        with st.expander("🔄 Estrutura de Parcelamento do Cartão de Crédito"):
            st.caption("Como os clientes parcelam no cartão (afeta timing de recebimento)")
            
            st.info("""
            **Como funciona:** Quando um cliente paga em 3x, a operadora repassa em 3 parcelas mensais.
            Configure aqui a distribuição típica de parcelamento dos seus clientes.
            """)
            
            # Parcelamentos comuns (1x a 6x)
            st.markdown("**Parcelamentos comuns (1x a 6x):**")
            cols = st.columns(6)
            
            parcelas = [
                ("pct_cartao_1x", "1x"),
                ("pct_cartao_2x", "2x"),
                ("pct_cartao_3x", "3x"),
                ("pct_cartao_4x", "4x"),
                ("pct_cartao_5x", "5x"),
                ("pct_cartao_6x", "6x"),
            ]
            
            for i, (attr, label) in enumerate(parcelas):
                with cols[i]:
                    valor_atual = getattr(pfc, attr, 0.0)
                    novo_valor = st.number_input(
                        f"% {label}",
                        value=float(valor_atual * 100),
                        min_value=0.0,
                        max_value=100.0,
                        step=5.0,
                        format="%.0f",
                        key=f"parc_{attr}"
                    ) / 100
                    setattr(pfc, attr, novo_valor)
            
            # Parcelamentos estendidos (7x a 12x) - opcional
            with st.expander("📊 Parcelamentos estendidos (7x a 12x)"):
                cols2 = st.columns(6)
                
                parcelas_ext = [
                    ("pct_cartao_7x", "7x"),
                    ("pct_cartao_8x", "8x"),
                    ("pct_cartao_9x", "9x"),
                    ("pct_cartao_10x", "10x"),
                    ("pct_cartao_11x", "11x"),
                    ("pct_cartao_12x", "12x"),
                ]
                
                for i, (attr, label) in enumerate(parcelas_ext):
                    with cols2[i]:
                        valor_atual = getattr(pfc, attr, 0.0)
                        novo_valor = st.number_input(
                            f"% {label}",
                            value=float(valor_atual * 100),
                            min_value=0.0,
                            max_value=100.0,
                            step=5.0,
                            format="%.0f",
                            key=f"parc_{attr}"
                        ) / 100
                        setattr(pfc, attr, novo_valor)
            
            # Validação do total
            total_parc = sum(getattr(pfc, f"pct_cartao_{i}x", 0.0) for i in range(1, 13))
            
            col1, col2 = st.columns(2)
            with col1:
                if abs(total_parc - 1.0) < 0.01:
                    st.success(f"**Total parcelamento:** {total_parc:.0%} ✅")
                else:
                    st.error(f"**Total parcelamento:** {total_parc:.0%} (deve ser 100%)")
            
            with col2:
                # Calcular prazo médio de recebimento do cartão
                prazo_medio = sum(i * getattr(pfc, f"pct_cartao_{i}x", 0.0) for i in range(1, 13))
                st.metric("Prazo Médio de Parcelamento", f"{prazo_medio:.1f} parcelas")


def pagina_premissas():
    """Página de Premissas - Simulador"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>⚙️ Premissas do Budget - Simulador</h3></div>', unsafe_allow_html=True)
    
    # ========================================================================
    # SELETOR DE CENÁRIO PARA EDIÇÃO (se habilitado)
    # ========================================================================
    usar_cenarios = getattr(st.session_state.motor, 'usar_cenarios', True)
    
    if usar_cenarios:
        st.markdown("---")
        
        col_ed1, col_ed2, col_ed3 = st.columns([2, 2, 4])
        
        with col_ed1:
            cenarios_opcoes = ["Conservador", "Pessimista", "Otimista"]
            cenario_edicao_atual = st.session_state.get('cenario_edicao', 'Conservador')
            
            if cenario_edicao_atual not in cenarios_opcoes:
                cenario_edicao_atual = "Conservador"
            
            idx_edicao = cenarios_opcoes.index(cenario_edicao_atual)
            
            # Cores para o seletor
            cores_cenario = {
                "Conservador": "#ffc107",
                "Pessimista": "#dc3545",
                "Otimista": "#28a745"
            }
            
            cenario_selecionado = st.selectbox(
                "📝 Editando cenário:",
                cenarios_opcoes,
                index=idx_edicao,
                key="select_cenario_edicao",
                help="Selecione qual cenário deseja editar. Cada cenário tem suas próprias premissas."
            )
            
            # Se mudou o cenário de edição
            if cenario_selecionado != cenario_edicao_atual:
                # Salva o motor atual antes de trocar
                st.session_state.motores_cenarios[cenario_edicao_atual] = st.session_state.motor
                
                # Troca para o novo cenário
                st.session_state.cenario_edicao = cenario_selecionado
                st.session_state.motor = st.session_state.motores_cenarios[cenario_selecionado]
                st.rerun()
        
        with col_ed2:
            # Botão para copiar do Conservador
            if cenario_selecionado != "Conservador":
                if st.button(f"📋 Copiar do Conservador", key="btn_copiar_conservador", 
                            help="Copia todas as premissas do Conservador para este cenário"):
                    from modules.cliente_manager import copiar_cenario
                    copiar_cenario(
                        st.session_state.motores_cenarios["Conservador"],
                        st.session_state.motores_cenarios[cenario_selecionado]
                    )
                    st.session_state.motor = st.session_state.motores_cenarios[cenario_selecionado]
                    st.success(f"✅ Premissas copiadas do Conservador para {cenario_selecionado}!")
                    st.rerun()
        
        with col_ed3:
            # Indicador visual do cenário sendo editado
            cor = cores_cenario.get(cenario_selecionado, "#6c757d")
            icones = {"Conservador": "⚠️", "Pessimista": "📉", "Otimista": "🚀"}
            icone = icones.get(cenario_selecionado, "📊")
            
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, {cor}22, transparent);
                border-left: 4px solid {cor};
                padding: 10px 15px;
                border-radius: 4px;
                margin-top: 25px;
            ">
                <span style="font-size: 16px;">{icone}</span>
                <span style="font-weight: bold; color: {cor};">
                    Editando: {cenario_selecionado.upper()}
                </span>
                <span style="font-size: 12px; color: #666; margin-left: 10px;">
                    As alterações serão salvas apenas neste cenário
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
    
    motor = st.session_state.motor
    
    # Sincroniza proprietários entre todas as estruturas
    motor.sincronizar_proprietarios()
    
    # Abas de premissas
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs([
        "📊 Macroeconômicas", 
        "🏥 Operacionais", 
        "💳 Pagamentos",
        "📅 Sazonalidade",
        "🩺 Serviços",
        "👥 Equipe",
        "💰 Despesas",
        "👔 Folha e Pró-Labore",
        "🏥 Folha Fisioterapeutas",
        "🏢 Salas (TDABC)",
        "🎯 Cenários"
    ])
    
    # ========== ABA MACROECONÔMICAS ==========
    with tab1:
        st.markdown("### Premissas Macroeconômicas")
        st.caption("Índices de reajuste e taxas para o ano")
        
        col1, col2 = st.columns(2)
        
        with col1:
            motor.macro.ipca = st.slider(
                "IPCA - Inflação Anual (%)", 
                min_value=0.0, max_value=15.0, 
                value=float(motor.macro.ipca * 100), 
                step=0.5,
                help="Inflação projetada para o ano"
            ) / 100
            
            motor.macro.igpm = st.slider(
                "IGP-M - Reajuste Aluguel (%)", 
                min_value=0.0, max_value=20.0, 
                value=float(motor.macro.igpm * 100), 
                step=0.5,
                help="Índice de reajuste de aluguéis"
            ) / 100
            
            motor.macro.dissidio = st.slider(
                "Dissídio - Reajuste Salarial (%)", 
                min_value=0.0, max_value=15.0, 
                value=float(motor.macro.dissidio * 100), 
                step=0.5,
                help="Reajuste previsto no dissídio coletivo"
            ) / 100
        
        with col2:
            motor.macro.reajuste_tarifas = st.slider(
                "Reajuste Tarifas (Água, Luz, Tel) (%)", 
                min_value=0.0, max_value=15.0, 
                value=float(motor.macro.reajuste_tarifas * 100), 
                step=0.5
            ) / 100
            
            motor.macro.reajuste_contratos = st.slider(
                "Reajuste Contratos (%)", 
                min_value=0.0, max_value=15.0, 
                value=float(motor.macro.reajuste_contratos * 100), 
                step=0.5,
                help="Sistema, contabilidade, seguros"
            ) / 100
        
        st.markdown("---")
        st.markdown("### Taxas de Cartão")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            motor.macro.taxa_cartao_credito = st.slider(
                "Taxa Crédito (%)", 
                min_value=0.0, max_value=10.0, 
                value=float(motor.macro.taxa_cartao_credito * 100), 
                step=0.1
            ) / 100
        
        with col2:
            motor.macro.taxa_cartao_debito = st.slider(
                "Taxa Débito (%)", 
                min_value=0.0, max_value=5.0, 
                value=float(motor.macro.taxa_cartao_debito * 100), 
                step=0.1
            ) / 100
        
        with col3:
            motor.macro.taxa_antecipacao = st.slider(
                "Taxa Antecipação (%)", 
                min_value=0.0, max_value=10.0, 
                value=float(motor.macro.taxa_antecipacao * 100), 
                step=0.1
            ) / 100
        
        # Botão de salvar ao final da aba
        st.markdown("---")
        if st.button("💾 Salvar Premissas Macro", key="btn_salvar_macro", use_container_width=True, type="primary"):
            try:
                salvar_filial_atual()
                st.success("✅ Premissas macroeconômicas salvas!")
            except Exception as e:
                erro_msg = registrar_erro("BE-400", str(e), "pagina_premissas/macro")
                st.error(f"❌ {erro_msg}")
    
    # ========== ABA OPERACIONAIS ==========
    with tab2:
        st.markdown("### Premissas Operacionais")
        st.caption("Estrutura física e de atendimento da clínica")
        
        col1, col2 = st.columns(2)
        
        with col1:
            motor.operacional.num_fisioterapeutas = st.number_input(
                "Nº de Fisioterapeutas",
                min_value=0, max_value=50,
                value=max(0, motor.operacional.num_fisioterapeutas),
                help="Quantidade de profissionais ativos"
            )
            
            motor.operacional.num_salas = st.number_input(
                "Nº de Salas",
                min_value=0, max_value=20,
                value=max(0, motor.operacional.num_salas),
                help="Quantidade de salas de atendimento"
            )
        
        with col2:
            motor.operacional.horas_atendimento_dia = st.number_input(
                "Horas de Atendimento/Dia",
                min_value=0, max_value=16,
                value=max(0, motor.operacional.horas_atendimento_dia),
                help="Horas de funcionamento por dia"
            )
            
            motor.operacional.dias_uteis_mes = st.number_input(
                "Dias Úteis/Mês",
                min_value=0, max_value=26,
                value=max(0, motor.operacional.dias_uteis_mes),
                help="Média de dias úteis por mês"
            )
        
        # BOTÃO DE SALVAR - Posição destacada
        st.markdown("---")
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("💾 Salvar Parâmetros Operacionais", use_container_width=True, type="primary"):
                # IMPORTANTE: Sincronizar cadastro_salas com novo número de salas
                motor.cadastro_salas.sincronizar_num_salas(motor.operacional.num_salas)
                motor.cadastro_salas.horas_funcionamento_dia = motor.operacional.horas_atendimento_dia
                motor.cadastro_salas.dias_uteis_mes = motor.operacional.dias_uteis_mes
                
                salvar_filial_atual()
                st.success("✅ Parâmetros salvos! Alterações refletirão em todas as páginas.")
                st.rerun()
        with col_btn2:
            st.caption("⚠️ Clique para persistir")
        
        st.markdown("---")
        
        # Capacidade calculada
        capacidade_hora = motor.operacional.num_salas
        capacidade_dia = capacidade_hora * motor.operacional.horas_atendimento_dia
        capacidade_mes = capacidade_dia * motor.operacional.dias_uteis_mes
        
        st.markdown("### 📊 Capacidade Calculada")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Atendimentos/Hora", f"{capacidade_hora}")
        with col2:
            st.metric("Atendimentos/Dia", f"{capacidade_dia}")
        with col3:
            st.metric("Atendimentos/Mês", f"{capacidade_mes}")
        
        # Modelo tributário
        st.markdown("---")
        opcoes_tributario = ["PJ - Simples Nacional", "PJ - Lucro Presumido", "PF - Carnê Leão"]
        idx_tributario = 0
        if motor.operacional.modelo_tributario in opcoes_tributario:
            idx_tributario = opcoes_tributario.index(motor.operacional.modelo_tributario)
        
        motor.operacional.modelo_tributario = st.selectbox(
            "Modelo Tributário",
            opcoes_tributario,
            index=idx_tributario,
            key="modelo_tributario_operacional"
        )
        
        # Sincroniza com premissas_folha para manter compatibilidade
        motor.premissas_folha.regime_tributario = motor.operacional.modelo_tributario
        
        # Modo de cálculo de sessões
        st.markdown("---")
        st.markdown("#### 📊 Modo de Cálculo de Atendimentos")
        
        opcoes_modo = {
            "servico": "📋 Por Serviço (define qtd no cadastro de serviços)",
            "profissional": "👥 Por Profissional (soma sessões de cada fisioterapeuta)"
        }
        
        modo_atual = getattr(motor.operacional, 'modo_calculo_sessoes', 'servico')
        if modo_atual not in opcoes_modo:
            modo_atual = 'servico'
        
        modo_selecionado = st.radio(
            "Como calcular a quantidade de atendimentos?",
            options=list(opcoes_modo.keys()),
            format_func=lambda x: opcoes_modo[x],
            index=0 if modo_atual == "servico" else 1,
            key="modo_calculo_sessoes",
            horizontal=True
        )
        
        motor.operacional.modo_calculo_sessoes = modo_selecionado
        
        # Explicação do modo selecionado
        if modo_selecionado == "servico":
            st.info("""
            **📋 Modo Por Serviço:**
            - Defina a quantidade de sessões em **📈 Atendimentos → Serviços**
            - O crescimento anual também é definido por serviço
            - ✅ Mais simples para clínicas com equipe estável
            """)
        else:
            st.info("""
            **👥 Modo Por Profissional:**
            - Defina sessões por serviço em **👨‍⚕️ Folha Fisioterapeutas**
            - Cada profissional tem sua própria meta de atendimentos
            - ✅ Ideal para controle individual de produtividade
            """)
        
        # ========================================
        # VALIDAÇÃO DE CONSISTÊNCIA DE SESSÕES
        # ========================================
        st.markdown("---")
        st.markdown("#### 🔍 Validação de Consistência")
        
        try:
            validacao = motor.validar_sessoes()
            
            # Mostrar totais
            totais = validacao["detalhes"]["totais"]
            col_v1, col_v2, col_v3 = st.columns(3)
            with col_v1:
                st.metric("📋 Sessões (Serviços)", f"{totais['servicos']}")
            with col_v2:
                st.metric("👥 Sessões (Fisios)", f"{totais['fisioterapeutas']}")
            with col_v3:
                st.metric("🏢 Capacidade Salas", f"{totais['capacidade_salas']}")
            
            # Mostrar alertas e erros
            if validacao["ok"]:
                st.success("✅ Sessões consistentes!")
            else:
                if validacao["erros"]:
                    for erro in validacao["erros"]:
                        st.error(f"❌ {erro}")
                if validacao["alertas"]:
                    for alerta in validacao["alertas"]:
                        st.warning(f"⚠️ {alerta}")
            
            # Detalhes por serviço (expansível)
            with st.expander("📊 Detalhes por Serviço", expanded=False):
                dados_srv = []
                for srv_nome, info in validacao["detalhes"]["por_servico"].items():
                    diferenca = info["servico"] - info["fisios"]
                    status = "✅" if abs(diferenca) <= 5 else "⚠️"
                    dados_srv.append({
                        "Serviço": srv_nome,
                        "Serviço (qtd)": info["servico"],
                        "Fisios (soma)": info["fisios"],
                        "Diferença": diferenca,
                        "Status": status
                    })
                if dados_srv:
                    df_srv = pd.DataFrame(dados_srv)
                    st.dataframe(df_srv, use_container_width=True, hide_index=True)
                else:
                    st.info("Nenhum serviço cadastrado")
        except Exception as e:
            st.warning(f"Não foi possível validar: {e}")
    
    # ========== ABA PAGAMENTOS ==========
    with tab3:
        st.markdown("### Formas de Recebimento")
        st.caption("Distribuição dos pagamentos dos clientes")
        
        col1, col2 = st.columns(2)
        
        with col1:
            motor.pagamento.dinheiro_pix = st.slider(
                "Dinheiro / PIX (%)",
                min_value=0, max_value=100,
                value=int(motor.pagamento.dinheiro_pix * 100),
                step=5
            ) / 100
            
            motor.pagamento.cartao_credito = st.slider(
                "Cartão Crédito (%)",
                min_value=0, max_value=100,
                value=int(motor.pagamento.cartao_credito * 100),
                step=5
            ) / 100
        
        with col2:
            motor.pagamento.cartao_debito = st.slider(
                "Cartão Débito (%)",
                min_value=0, max_value=100,
                value=int(motor.pagamento.cartao_debito * 100),
                step=5
            ) / 100
            
            motor.pagamento.pct_antecipacao = st.slider(
                "% Antecipação sobre Crédito",
                min_value=0, max_value=100,
                value=int(motor.pagamento.pct_antecipacao * 100),
                step=5,
                help="Percentual do crédito que é antecipado"
            ) / 100
        
        # Validação
        total_pagamento = motor.pagamento.dinheiro_pix + motor.pagamento.cartao_credito + motor.pagamento.cartao_debito
        if abs(total_pagamento - 1.0) > 0.01:
            st.warning(f"⚠️ Total das formas de pagamento: {total_pagamento*100:.0f}% (deve ser 100%)")
        else:
            st.success("✅ Total: 100%")
    
    # ========== ABA SAZONALIDADE ==========
    with tab4:
        st.markdown("### Fatores de Sazonalidade")
        st.caption("Ajuste mensal da demanda (1.0 = normal, 0.85 = 15% menor, 1.10 = 10% maior)")
        
        meses_nome = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                      "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        
        col1, col2 = st.columns(2)
        
        for i, mes in enumerate(meses_nome):
            col = col1 if i < 6 else col2
            with col:
                motor.sazonalidade.fatores[i] = st.slider(
                    mes,
                    min_value=0.5, max_value=1.5,
                    value=float(motor.sazonalidade.fatores[i]),
                    step=0.05,
                    key=f"saz_{i}"
                )
        
        # Gráfico de sazonalidade
        st.markdown("---")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=MESES_ABREV,
            y=motor.sazonalidade.fatores,
            marker_color=['#c53030' if f < 1 else '#38a169' if f > 1 else '#4299e1' 
                         for f in motor.sazonalidade.fatores]
        ))
        fig.add_hline(y=1.0, line_dash="dash", line_color="gray")
        fig.update_layout(
            title="Fator de Sazonalidade por Mês",
            yaxis_title="Fator",
            plot_bgcolor='rgba(0,0,0,0)',
            height=300
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # ========== ABA SERVIÇOS ==========
    with tab5:
        st.markdown("### Configuração dos Serviços")
        st.caption("Valores, sessões e reajustes por tipo de serviço")
        
        # Pegar modo de cálculo
        modo_sessoes = getattr(motor.operacional, 'modo_calculo_sessoes', 'servico')
        
        # ===== ADICIONAR NOVO SERVIÇO =====
        with st.expander("➕ ADICIONAR NOVO SERVIÇO", expanded=False):
            st.markdown("##### Cadastrar Novo Serviço")
            
            col1, col2 = st.columns(2)
            
            with col1:
                novo_nome = st.text_input(
                    "Nome do Serviço",
                    placeholder="Ex: Pilates, RPG, Acupuntura...",
                    key="novo_servico_nome"
                )
                
                novo_valor = st.number_input(
                    "Valor da Sessão (R$)",
                    min_value=0.0, max_value=2000.0,
                    value=0.0,
                    step=10.0,
                    key="novo_servico_valor"
                )
                
                nova_duracao = st.number_input(
                    "Duração (minutos)",
                    min_value=15, max_value=180,
                    value=50,
                    step=5,
                    key="novo_servico_duracao"
                )
            
            with col2:
                # Só mostra sessões se modo for "servico"
                if modo_sessoes == "servico":
                    novas_sessoes = st.number_input(
                        "Sessões/Mês (base)",
                        min_value=0, max_value=1000,
                        value=0,
                        step=5,
                        key="novo_servico_sessoes"
                    )
                else:
                    novas_sessoes = 0
                    st.info("ℹ️ Sessões definidas por profissional (veja Folha Fisioterapeutas)")
                
                novo_reajuste = st.slider(
                    "Reajuste Valor (%)",
                    min_value=0, max_value=20,
                    value=0,
                    step=1,
                    key="novo_servico_reajuste"
                )
                
                novo_mes_reajuste = st.selectbox(
                    "Mês do Reajuste",
                    options=list(range(1, 13)),
                    format_func=lambda x: MESES[x-1],
                    index=2,  # Março
                    key="novo_servico_mes"
                )
            
            # Crescimento anual só se modo="servico"
            if modo_sessoes == "servico":
                novo_crescimento = st.slider(
                    "Crescimento Anual Sessões (%)",
                    min_value=-20, max_value=50,
                    value=0,
                    step=1,
                    key="novo_servico_crescimento"
                )
            else:
                novo_crescimento = 0
            
            if st.button("✅ CADASTRAR SERVIÇO", type="primary", key="btn_add_servico"):
                if novo_nome and novo_nome.strip():
                    from motor_calculo import Servico
                    
                    # Verifica se já existe
                    if novo_nome in motor.servicos:
                        st.error(f"❌ Serviço '{novo_nome}' já existe!")
                    else:
                        # Adiciona novo serviço
                        motor.servicos[novo_nome] = Servico(
                            nome=novo_nome,
                            duracao_minutos=nova_duracao,
                            valor_2026=novo_valor,
                            sessoes_mes_base=novas_sessoes,
                            pct_reajuste=novo_reajuste / 100,
                            pct_crescimento=novo_crescimento / 100,
                            mes_reajuste=novo_mes_reajuste
                        )
                        st.success(f"✅ Serviço '{novo_nome}' cadastrado com sucesso!")
                        st.rerun()
                else:
                    st.error("❌ Digite o nome do serviço!")
        
        st.markdown("---")
        
        # ===== LISTA DE SERVIÇOS EXISTENTES =====
        st.markdown("### 📋 Serviços Cadastrados")
        
        # Mostrar aviso do modo atual
        if modo_sessoes == "profissional":
            st.info("ℹ️ **Modo Profissional ativo**: Sessões e crescimento são definidos por fisioterapeuta em **👨‍⚕️ Folha Fisioterapeutas**")
        
        # Lista de serviços para remover
        servicos_para_remover = []
        
        for servico_nome, servico in motor.servicos.items():
            with st.expander(f"🩺 {servico_nome}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    servico.valor_2026 = st.number_input(
                        "Valor da Sessão (R$)",
                        min_value=0.0, max_value=2000.0,
                        value=float(servico.valor_2026),
                        step=5.0,
                        key=f"val_{servico_nome}"
                    )
                    
                    servico.duracao_minutos = st.number_input(
                        "Duração (minutos)",
                        min_value=0, max_value=180,
                        value=max(0, servico.duracao_minutos),
                        step=5,
                        key=f"dur_{servico_nome}"
                    )
                
                with col2:
                    # Só mostra sessões se modo for "servico"
                    if modo_sessoes == "servico":
                        servico.sessoes_mes_base = st.number_input(
                            "Sessões/Mês (base)",
                            min_value=0, max_value=1000,
                            value=servico.sessoes_mes_base,
                            step=5,
                            key=f"sess_{servico_nome}",
                            help="Quantidade média de sessões por mês"
                        )
                        
                        servico.pct_crescimento = st.slider(
                            "Crescimento Anual (%)",
                            min_value=-20, max_value=50,
                            value=int(servico.pct_crescimento * 100),
                            step=1,
                            key=f"cresc_{servico_nome}"
                        ) / 100
                    else:
                        # Modo profissional - mostra valores mas não permite editar
                        st.metric("Sessões/Mês (base)", f"{servico.sessoes_mes_base}", help="Edite em Folha Fisioterapeutas")
                        st.caption("_Definido por profissional_")
                
                with col3:
                    servico.pct_reajuste = st.slider(
                        "Reajuste Valor (%)",
                        min_value=0, max_value=20,
                        value=int(servico.pct_reajuste * 100),
                        step=1,
                        key=f"reaj_{servico_nome}"
                    ) / 100
                    
                    servico.mes_reajuste = st.selectbox(
                        "Mês do Reajuste",
                        options=list(range(1, 13)),
                        format_func=lambda x: MESES[x-1],
                        index=max(0, min(11, servico.mes_reajuste - 1)) if servico.mes_reajuste > 0 else 2,
                        key=f"mes_{servico_nome}"
                    )
                
                # Preview de receita do serviço
                # Primeiro tenta calcular baseado em proprietários/profissionais
                receita_anual = sum([
                    motor.calcular_receita_servico_mes(servico_nome, m) 
                    for m in range(12)
                ])
                
                # Se não tem profissionais cadastrados, usa preview baseado no serviço
                if receita_anual == 0 and servico.sessoes_mes_base > 0 and servico.valor_2026 > 0:
                    # Calcula preview considerando reajuste
                    fator_crescimento = 1 + (servico.pct_crescimento / 2)  # Média do crescimento
                    # Meses antes do reajuste usam valor base, depois usam valor reajustado
                    meses_antes = max(0, servico.mes_reajuste - 1)
                    meses_depois = 12 - meses_antes
                    valor_antes = servico.valor_2026
                    valor_depois = servico.valor_2026 * (1 + servico.pct_reajuste) if servico.pct_reajuste > 0 else servico.valor_2026
                    receita_preview = servico.sessoes_mes_base * (
                        (meses_antes * valor_antes) + (meses_depois * valor_depois)
                    ) * fator_crescimento
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(f"📊 Receita Anual Estimada: **{format_currency(receita_preview)}** _(cadastre profissionais para cálculo exato)_")
                    with col2:
                        if st.button("🗑️ Remover", key=f"rem_{servico_nome}", type="secondary"):
                            servicos_para_remover.append(servico_nome)
                else:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(f"📊 Receita Anual Projetada: **{format_currency(receita_anual)}**")
                    with col2:
                        if st.button("🗑️ Remover", key=f"rem_{servico_nome}", type="secondary"):
                            servicos_para_remover.append(servico_nome)
        
        # Remove serviços marcados
        for srv in servicos_para_remover:
            if srv in motor.servicos:
                del motor.servicos[srv]
        
        if servicos_para_remover:
            st.success(f"Serviço(s) removido(s)!")
            st.rerun()
    
    # ========== ABA EQUIPE ==========
    with tab6:
        st.markdown("### 👥 Equipe - Proprietários e Profissionais")
        st.caption("Cadastro de profissionais e suas sessões por serviço")
        
        # Sub-abas para Proprietários e Profissionais
        subtab1, subtab2 = st.tabs(["👔 Proprietários", "🩺 Profissionais"])
        
        # ===== PROPRIETÁRIOS =====
        with subtab1:
            st.markdown("#### Proprietários")
            
            # Adicionar novo proprietário
            with st.expander("➕ ADICIONAR PROPRIETÁRIO", expanded=False):
                novo_prop_nome = st.text_input("Nome do Proprietário", key="novo_prop_nome")
                
                if st.button("✅ Cadastrar Proprietário", key="btn_add_prop"):
                    if novo_prop_nome and novo_prop_nome.strip():
                        if novo_prop_nome in motor.proprietarios:
                            st.error(f"❌ '{novo_prop_nome}' já existe!")
                        else:
                            from motor_calculo import Profissional
                            motor.proprietarios[novo_prop_nome] = Profissional(
                                nome=novo_prop_nome,
                                tipo="proprietario",
                                sessoes_por_servico={},
                                pct_crescimento_por_servico={}
                            )
                            st.success(f"✅ Proprietário '{novo_prop_nome}' cadastrado!")
                            st.rerun()
                    else:
                        st.error("Digite o nome!")
            
            st.markdown("---")
            
            # Lista de proprietários
            props_para_remover = []
            
            # Verificar modo de cálculo
            modo_sessoes = getattr(motor.operacional, 'modo_calculo_sessoes', 'servico')
            
            for prop_nome, prop in motor.proprietarios.items():
                with st.expander(f"👔 {prop_nome}", expanded=True):
                    st.markdown("**Sessões por Serviço (por mês):**")
                    
                    # Grid de serviços
                    for servico in motor.servicos.keys():
                        col_srv, col_cresc = st.columns([2, 1])
                        
                        with col_srv:
                            sessoes_atual = prop.sessoes_por_servico.get(servico, 0)
                            novas_sessoes = st.number_input(
                                servico,
                                min_value=0, max_value=500,
                                value=sessoes_atual,
                                step=1,
                                key=f"prop_{prop_nome}_{servico}"
                            )
                            if novas_sessoes > 0:
                                prop.sessoes_por_servico[servico] = novas_sessoes
                            elif servico in prop.sessoes_por_servico:
                                del prop.sessoes_por_servico[servico]
                        
                        # Crescimento só aparece se modo="profissional" e tem sessões
                        with col_cresc:
                            if modo_sessoes == "profissional" and novas_sessoes > 0:
                                cresc_atual = prop.pct_crescimento_por_servico.get(servico, 0)
                                novo_cresc = st.number_input(
                                    "Cresc. %",
                                    min_value=-20, max_value=50,
                                    value=int(cresc_atual * 100) if isinstance(cresc_atual, float) and cresc_atual < 1 else int(cresc_atual),
                                    step=1,
                                    key=f"prop_cresc_{prop_nome}_{servico}",
                                    help="Crescimento anual das sessões"
                                )
                                prop.pct_crescimento_por_servico[servico] = novo_cresc / 100
                    
                    # Resumo e botão remover
                    total_sessoes = sum(prop.sessoes_por_servico.values())
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(f"📊 Total: **{total_sessoes}** sessões/mês")
                    with col2:
                        if st.button("🗑️ Remover", key=f"rem_prop_{prop_nome}"):
                            props_para_remover.append(prop_nome)
            
            for p in props_para_remover:
                if p in motor.proprietarios:
                    del motor.proprietarios[p]
                # Também remover de outras estruturas para evitar re-sincronização
                if p in motor.fisioterapeutas:
                    del motor.fisioterapeutas[p]
                if p in motor.socios_prolabore:
                    del motor.socios_prolabore[p]
            
            if props_para_remover:
                st.rerun()
        
        # ===== PROFISSIONAIS =====
        with subtab2:
            st.markdown("#### Profissionais (Fisioterapeutas)")
            
            # Adicionar novo profissional
            with st.expander("➕ ADICIONAR PROFISSIONAL", expanded=False):
                novo_prof_nome = st.text_input("Nome do Profissional", key="novo_prof_nome")
                
                if st.button("✅ Cadastrar Profissional", key="btn_add_prof"):
                    if novo_prof_nome and novo_prof_nome.strip():
                        if novo_prof_nome in motor.profissionais:
                            st.error(f"❌ '{novo_prof_nome}' já existe!")
                        else:
                            from motor_calculo import Profissional
                            motor.profissionais[novo_prof_nome] = Profissional(
                                nome=novo_prof_nome,
                                tipo="profissional",
                                sessoes_por_servico={},
                                pct_crescimento_por_servico={}
                            )
                            st.success(f"✅ Profissional '{novo_prof_nome}' cadastrado!")
                            st.rerun()
                    else:
                        st.error("Digite o nome!")
            
            st.markdown("---")
            
            # Lista de profissionais
            profs_para_remover = []
            
            for prof_nome, prof in motor.profissionais.items():
                with st.expander(f"🩺 {prof_nome}", expanded=False):
                    st.markdown("**Sessões por Serviço (por mês):**")
                    
                    # Grid de serviços
                    for servico in motor.servicos.keys():
                        col_srv, col_cresc = st.columns([2, 1])
                        
                        with col_srv:
                            sessoes_atual = prof.sessoes_por_servico.get(servico, 0)
                            novas_sessoes = st.number_input(
                                servico,
                                min_value=0, max_value=500,
                                value=sessoes_atual,
                                step=1,
                                key=f"prof_{prof_nome}_{servico}"
                            )
                            if novas_sessoes > 0:
                                prof.sessoes_por_servico[servico] = novas_sessoes
                            elif servico in prof.sessoes_por_servico:
                                del prof.sessoes_por_servico[servico]
                        
                        # Crescimento só aparece se modo="profissional" e tem sessões
                        with col_cresc:
                            if modo_sessoes == "profissional" and novas_sessoes > 0:
                                cresc_atual = prof.pct_crescimento_por_servico.get(servico, 0)
                                novo_cresc = st.number_input(
                                    "Cresc. %",
                                    min_value=-20, max_value=50,
                                    value=int(cresc_atual * 100) if isinstance(cresc_atual, float) and cresc_atual < 1 else int(cresc_atual),
                                    step=1,
                                    key=f"prof_cresc_{prof_nome}_{servico}",
                                    help="Crescimento anual das sessões"
                                )
                                prof.pct_crescimento_por_servico[servico] = novo_cresc / 100
                    
                    # Resumo e botão remover
                    total_sessoes = sum(prof.sessoes_por_servico.values())
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.info(f"📊 Total: **{total_sessoes}** sessões/mês")
                    with col2:
                        if st.button("🗑️ Remover", key=f"rem_prof_{prof_nome}"):
                            profs_para_remover.append(prof_nome)
            
            for p in profs_para_remover:
                if p in motor.profissionais:
                    del motor.profissionais[p]
                # Também remover de fisioterapeutas para evitar re-sincronização
                if p in motor.fisioterapeutas:
                    del motor.fisioterapeutas[p]
            
            if profs_para_remover:
                st.rerun()
        
        # ===== RESUMO DA EQUIPE =====
        st.markdown("---")
        st.markdown("### 📊 Resumo da Equipe")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Proprietários", len(motor.proprietarios))
        with col2:
            st.metric("Profissionais", len(motor.profissionais))
        with col3:
            total_sessoes_equipe = sum(
                sum(p.sessoes_por_servico.values()) 
                for p in list(motor.proprietarios.values()) + list(motor.profissionais.values())
            )
            st.metric("Total Sessões/Mês", f"{total_sessoes_equipe:,}")
        
        # Tabela resumo por serviço
        st.markdown("#### Sessões por Serviço")
        
        # Seletor de mês para visualizar valores com reajuste
        mes_visualizar = st.selectbox(
            "📅 Visualizar valores do mês:",
            range(12),
            format_func=lambda x: MESES[x],
            index=0,
            key="mes_sessoes_servico"
        )
        
        dados_resumo = []
        for servico in motor.servicos.keys():
            srv = motor.servicos[servico]
            sessoes_prop = sum(p.sessoes_por_servico.get(servico, 0) for p in motor.proprietarios.values())
            sessoes_prof = sum(p.sessoes_por_servico.get(servico, 0) for p in motor.profissionais.values())
            total_sessoes = sessoes_prop + sessoes_prof
            
            # Usa valor do serviço considerando reajuste do mês selecionado
            valor_servico = motor.calcular_valor_servico_mes(servico, mes_visualizar, "profissional")
            
            # Se valor profissional é 0, usa valor proprietário (ex: Osteopatia)
            if valor_servico == 0:
                valor_servico = motor.calcular_valor_servico_mes(servico, mes_visualizar, "proprietario")
            
            # Valor base (cadastrado) e valor após reajuste
            valor_base = srv.valor_2026
            valor_apos_reajuste = valor_base * (1 + srv.pct_reajuste) if srv.pct_reajuste > 0 else valor_base
            
            receita_mes = total_sessoes * valor_servico
            
            dados_resumo.append({
                "Serviço": servico,
                "Sessões Prop.": sessoes_prop,
                "Sessões Prof.": sessoes_prof,
                "Total Sessões": total_sessoes,
                "Valor Base": format_currency(valor_base),
                f"Valor {MESES[srv.mes_reajuste - 1]}+": format_currency(valor_apos_reajuste),
                "Valor Unit.": format_currency(valor_servico),
                "Receita/Mês": format_currency(receita_mes)
            })
        
        if dados_resumo:
            st.dataframe(pd.DataFrame(dados_resumo), use_container_width=True, hide_index=True)
    
    # ========== ABA DESPESAS ==========
    with tab7:
        st.markdown("### 💰 Despesas Fixas e Custo de Pessoal")
        
        # Sub-abas
        subtab_desp1, subtab_desp2, subtab_desp3 = st.tabs(["📋 Diretrizes Despesas", "📊 Projeção 2026", "👔 Custo de Pessoal"])
        
        # ===== DIRETRIZES DESPESAS (igual planilha) =====
        with subtab_desp1:
            st.markdown("#### 📋 Cadastro de Despesas")
            st.caption("Configure as despesas igual à aba 'Diretrizes Despesas' da planilha")
            
            # Índices de reajuste (referência)
            with st.expander("📊 ÍNDICES DE REAJUSTE (Referência)", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**IPCA:** {motor.macro.ipca*100:.1f}%")
                    st.write(f"**IGP-M:** {motor.macro.igpm*100:.1f}%")
                with col2:
                    st.write(f"**Dissídio:** {motor.macro.dissidio*100:.1f}%")
                    st.write(f"**Tarifas:** {motor.macro.reajuste_tarifas*100:.1f}%")
                with col3:
                    st.write(f"**Contratos:** {motor.macro.reajuste_contratos*100:.1f}%")
            
            st.markdown("---")
            
            # Tabela de despesas estilo planilha
            st.markdown("#### Cadastro de Despesas")
            
            # Cabeçalho
            cols = st.columns([2.5, 1.2, 1.5, 1.5, 1, 2, 1.5, 0.8])
            cols[0].markdown("**Despesa**")
            cols[1].markdown("**Tipo**")
            cols[2].markdown("**Índice**")
            cols[3].markdown("**Mês Reaj.**")
            cols[4].markdown("**% Adic.**")
            cols[5].markdown("**Valor/Base**")
            cols[6].markdown("**Sazonalidade**")
            cols[7].markdown("**🗑️**")
            
            st.markdown("---")
            
            # ===== CALCULADORA DE DESPESAS VARIÁVEIS =====
            with st.expander("🧮 **CALCULADORA** - Descobrir R$/Sessão ou % Receita", expanded=False):
                st.caption("Use para calcular o valor por sessão ou percentual baseado nos custos do ano anterior")
                
                # Calcula total de sessões cadastradas
                total_sessoes_ano = 0
                for fisio in motor.fisioterapeutas.values():
                    if fisio.ativo:
                        for servico, qtd in fisio.sessoes_por_servico.items():
                            # Considera crescimento médio (média do ano)
                            pct_cresc = fisio.pct_crescimento_por_servico.get(servico, 0)
                            sessoes_media = qtd * (1 + pct_cresc / 2)  # Média aproximada
                            total_sessoes_ano += sessoes_media * 12
                
                # Se não tem fisioterapeutas, usa proprietários + profissionais
                if total_sessoes_ano == 0:
                    for prop in motor.proprietarios.values():
                        for servico, qtd in prop.sessoes_por_servico.items():
                            pct_cresc = prop.pct_crescimento_por_servico.get(servico, 0.105)
                            sessoes_media = qtd * (1 + pct_cresc / 2)
                            total_sessoes_ano += sessoes_media * 12
                    for prof in motor.profissionais.values():
                        for servico, qtd in prof.sessoes_por_servico.items():
                            pct_cresc = prof.pct_crescimento_por_servico.get(servico, 0.05)
                            sessoes_media = qtd * (1 + pct_cresc / 2)
                            total_sessoes_ano += sessoes_media * 12
                
                # Sessões por mês (média)
                sessoes_mes = total_sessoes_ano / 12 if total_sessoes_ano > 0 else 0
                
                col_calc1, col_calc2 = st.columns(2)
                
                with col_calc1:
                    st.markdown("##### 💰 Calcular R$/Sessão")
                    
                    # Opção de período
                    periodo_sessao = st.radio(
                        "O valor informado é:",
                        ["Mensal", "Anual"],
                        horizontal=True,
                        key="calc_periodo_sessao",
                        help="Escolha se o custo é mensal ou anual"
                    )
                    
                    custo_informado = st.number_input(
                        f"Custo {periodo_sessao.lower()} (R$)",
                        min_value=0.0,
                        value=0.0,
                        step=500.0 if periodo_sessao == "Mensal" else 1000.0,
                        key="calc_custo_sessao",
                        help=f"Ex: Aluguel custa R$ {'8.000/mês' if periodo_sessao == 'Mensal' else '96.000/ano'}"
                    )
                    
                    # Converte para anual se necessário
                    custo_ano_sessao = custo_informado * 12 if periodo_sessao == "Mensal" else custo_informado
                    
                    st.caption(f"📊 Sessões: **{sessoes_mes:,.0f}**/mês | **{total_sessoes_ano:,.0f}**/ano")
                    
                    if custo_informado > 0 and total_sessoes_ano > 0:
                        valor_por_sessao = custo_ano_sessao / total_sessoes_ano
                        st.success(f"**R$/Sessão = R$ {valor_por_sessao:.2f}**")
                        
                        if periodo_sessao == "Mensal":
                            st.caption(f"Cálculo: R$ {custo_informado:,.2f}/mês × 12 = R$ {custo_ano_sessao:,.2f}/ano")
                            st.caption(f"R$ {custo_ano_sessao:,.2f} ÷ {total_sessoes_ano:,.0f} sessões = R$ {valor_por_sessao:.2f}")
                        else:
                            st.caption(f"Cálculo: R$ {custo_ano_sessao:,.0f} ÷ {total_sessoes_ano:,.0f} sessões")
                        
                        # Mostrar verificação
                        custo_mes_calculado = valor_por_sessao * sessoes_mes
                        st.info(f"📋 Verificação: {sessoes_mes:,.0f} sessões × R$ {valor_por_sessao:.2f} = **R$ {custo_mes_calculado:,.2f}/mês**")
                    elif custo_informado > 0:
                        st.warning("⚠️ Cadastre sessões nos profissionais primeiro")
                
                with col_calc2:
                    st.markdown("##### 📈 Calcular % Receita")
                    
                    # Opção de período
                    periodo_receita = st.radio(
                        "O valor informado é:",
                        ["Mensal", "Anual"],
                        horizontal=True,
                        key="calc_periodo_receita",
                        help="Escolha se os valores são mensais ou anuais"
                    )
                    
                    custo_informado_rec = st.number_input(
                        f"Custo {periodo_receita.lower()} (R$)",
                        min_value=0.0,
                        value=0.0,
                        step=500.0 if periodo_receita == "Mensal" else 1000.0,
                        key="calc_custo_receita",
                        help=f"Ex: Materiais custam R$ {'1.500/mês' if periodo_receita == 'Mensal' else '18.000/ano'}"
                    )
                    receita_informada = st.number_input(
                        f"Receita {periodo_receita.lower()} (R$)",
                        min_value=0.0,
                        value=0.0,
                        step=5000.0 if periodo_receita == "Mensal" else 10000.0,
                        key="calc_receita_anterior",
                        help=f"Ex: Receita bruta é R$ {'100.000/mês' if periodo_receita == 'Mensal' else '1.200.000/ano'}"
                    )
                    
                    if custo_informado_rec > 0 and receita_informada > 0:
                        pct_receita = (custo_informado_rec / receita_informada) * 100
                        st.success(f"**% Receita = {pct_receita:.2f}%**")
                        st.caption(f"Cálculo: R$ {custo_informado_rec:,.2f} ÷ R$ {receita_informada:,.2f} × 100")
                        
                        # Mostrar verificação com receita projetada
                        if motor.receita_bruta:
                            receita_proj_mes = sum(motor.receita_bruta.get("Total", [0]*12)) / 12
                            custo_proj_mes = receita_proj_mes * (pct_receita / 100)
                            st.info(f"📋 Com receita projetada de R$ {receita_proj_mes:,.2f}/mês → **R$ {custo_proj_mes:,.2f}/mês**")
                    elif custo_informado_rec > 0:
                        st.info("💡 Informe a receita")
                
                st.markdown("---")
                st.caption("💡 **Dica:** Copie o valor calculado e cole no campo da despesa correspondente")
            
            st.markdown("---")
            
            # Lista de despesas para remover
            desp_para_remover = []
            
            # Mapeamento de índices
            indices_opcoes = ["ipca", "igpm", "tarifas", "contratos", "dissidio", "nenhum"]
            indices_nomes = {
                "ipca": "IPCA",
                "igpm": "IGP-M", 
                "tarifas": "Tarifas",
                "contratos": "Contratos",
                "dissidio": "Dissídio",
                "nenhum": "Sem Reajuste"
            }
            
            sazon_opcoes = ["uniforme", "sazonal"]
            sazon_nomes = {"uniforme": "Uniforme", "sazonal": "Sazonal"}
            
            tipo_opcoes = ["fixa", "variavel"]
            tipo_nomes = {"fixa": "🔒 Fixa", "variavel": "📊 Variável"}
            
            for nome, desp in motor.despesas_fixas.items():
                # Garante que o campo tipo_despesa existe (compatibilidade)
                if not hasattr(desp, 'tipo_despesa'):
                    desp.tipo_despesa = "fixa"
                if not hasattr(desp, 'pct_receita'):
                    desp.pct_receita = 0.0
                if not hasattr(desp, 'valor_por_sessao'):
                    desp.valor_por_sessao = 0.0
                if not hasattr(desp, 'base_variavel'):
                    desp.base_variavel = "receita"
                
                cols = st.columns([2.5, 1.2, 1.5, 1.5, 1, 2, 1.5, 0.8])
                
                # Nome com checkbox
                with cols[0]:
                    desp.ativa = st.checkbox(nome, value=desp.ativa, key=f"ativo_{nome}")
                
                # Tipo (fixa/variável)
                with cols[1]:
                    tipo_atual = tipo_opcoes.index(desp.tipo_despesa) if desp.tipo_despesa in tipo_opcoes else 0
                    desp.tipo_despesa = st.selectbox(
                        "Tipo",
                        tipo_opcoes,
                        index=tipo_atual,
                        format_func=lambda x: tipo_nomes.get(x, x),
                        key=f"tipo_{nome}",
                        label_visibility="collapsed"
                    )
                
                # Índice (só para fixas)
                with cols[2]:
                    if desp.tipo_despesa == "fixa":
                        idx_atual = indices_opcoes.index(desp.tipo_reajuste) if desp.tipo_reajuste in indices_opcoes else 0
                        desp.tipo_reajuste = st.selectbox(
                            "Índice",
                            indices_opcoes,
                            index=idx_atual,
                            format_func=lambda x: indices_nomes.get(x, x),
                            key=f"idx_{nome}",
                            label_visibility="collapsed"
                        )
                    else:
                        base_opcoes = ["receita", "sessao"]
                        base_nomes = {"receita": "% Receita", "sessao": "R$/Sessão"}
                        base_atual = base_opcoes.index(desp.base_variavel) if desp.base_variavel in base_opcoes else 0
                        desp.base_variavel = st.selectbox(
                            "Base",
                            base_opcoes,
                            index=base_atual,
                            format_func=lambda x: base_nomes.get(x, x),
                            key=f"base_{nome}",
                            label_visibility="collapsed"
                        )
                
                # Mês Reajuste (só para fixas)
                with cols[3]:
                    if desp.tipo_despesa == "fixa":
                        desp.mes_reajuste = st.selectbox(
                            "Mês",
                            list(range(1, 13)),
                            index=max(0, min(11, desp.mes_reajuste - 1)) if desp.mes_reajuste > 0 else 0,
                            format_func=lambda x: MESES[x-1],
                            key=f"mes_{nome}",
                            label_visibility="collapsed"
                        )
                    else:
                        st.caption("N/A")
                
                # % Adicional (só para fixas)
                with cols[4]:
                    if desp.tipo_despesa == "fixa":
                        desp.pct_adicional = st.number_input(
                            "%",
                            min_value=0.0, max_value=1.0,
                            value=float(desp.pct_adicional),
                            step=0.01,
                            format="%.2f",
                            key=f"pct_{nome}",
                            label_visibility="collapsed"
                        )
                    else:
                        st.caption("N/A")
                
                # Valor/Base
                with cols[5]:
                    if desp.tipo_despesa == "fixa":
                        desp.valor_mensal = st.number_input(
                            "Média",
                            min_value=0.0, max_value=99999999.0,
                            value=float(desp.valor_mensal),
                            step=50.0,
                            key=f"med_{nome}",
                            label_visibility="collapsed"
                        )
                    else:
                        if desp.base_variavel == "receita":
                            # Campo para % sobre receita
                            col_pct, col_label = st.columns([2, 1])
                            with col_pct:
                                desp.pct_receita = st.number_input(
                                    "% Receita",
                                    min_value=0.0, max_value=100.0,
                                    value=float(desp.pct_receita * 100),  # Mostra como %
                                    step=0.5,
                                    format="%.2f",
                                    key=f"pct_rec_{nome}",
                                    label_visibility="collapsed",
                                    help="Percentual sobre a receita bruta"
                                ) / 100  # Converte de volta para decimal
                            with col_label:
                                st.caption("**%**")
                        else:
                            # Campo para R$/sessão
                            col_val, col_label = st.columns([2, 1])
                            with col_val:
                                desp.valor_por_sessao = st.number_input(
                                    "R$/sessão",
                                    min_value=0.0, max_value=1000.0,
                                    value=float(desp.valor_por_sessao),
                                    step=0.50,
                                    format="%.2f",
                                    key=f"vlr_ses_{nome}",
                                    label_visibility="collapsed",
                                    help="Valor cobrado por sessão realizada"
                                )
                            with col_label:
                                st.caption("**/sessão**")
                
                # Sazonalidade (só para fixas)
                with cols[6]:
                    if desp.tipo_despesa == "fixa":
                        sazon_atual = sazon_opcoes.index(desp.tipo_sazonalidade) if desp.tipo_sazonalidade in sazon_opcoes else 0
                        desp.tipo_sazonalidade = st.selectbox(
                            "Sazon",
                            sazon_opcoes,
                            index=sazon_atual,
                            format_func=lambda x: sazon_nomes.get(x, x),
                            key=f"saz_{nome}",
                            label_visibility="collapsed"
                        )
                    else:
                        st.caption("Proporcional")
                
                # Botão remover
                with cols[7]:
                    if st.button("🗑️", key=f"rem_{nome}"):
                        desp_para_remover.append(nome)
            
            # Remove despesas marcadas
            for d in desp_para_remover:
                if d in motor.despesas_fixas:
                    del motor.despesas_fixas[d]
            
            if desp_para_remover:
                st.rerun()
            
            st.markdown("---")
            
            # Adicionar nova despesa
            with st.expander("➕ ADICIONAR DESPESA", expanded=False):
                # Importa função de verificação
                from motor_calculo import verificar_tipo_despesa
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    nova_desp_nome = st.text_input("Nome da Despesa", key="nova_desp_nome")
                    
                    # ===== NOVO: Tipo FIXA/VARIÁVEL =====
                    nova_desp_tipo = st.selectbox(
                        "Tipo de Despesa",
                        ["fixa", "variavel"],
                        format_func=lambda x: "🔒 FIXA" if x == "fixa" else "📊 VARIÁVEL",
                        key="nova_desp_tipo",
                        help="FIXA: valor mensal constante | VARIÁVEL: depende da receita ou sessões"
                    )
                
                with col2:
                    nova_desp_indice = st.selectbox("Índice", indices_opcoes, format_func=lambda x: indices_nomes.get(x, x), key="nova_desp_idx")
                    nova_desp_mes = st.selectbox("Mês Reajuste", list(range(1, 13)), format_func=lambda x: MESES[x-1], key="nova_desp_mes")
                
                with col3:
                    nova_desp_categoria = st.selectbox("Categoria", ["Ocupação", "Utilidades", "Administrativa", "Operacional", "Marketing", "Desenvolvimento", "Custos Variáveis"], key="nova_desp_cat")
                    nova_desp_sazon = st.selectbox("Sazonalidade", sazon_opcoes, format_func=lambda x: sazon_nomes.get(x, x), key="nova_desp_saz")
                
                # ===== CAMPOS CONDICIONAIS =====
                if nova_desp_tipo == "fixa":
                    nova_desp_valor = st.number_input("Média 2025 (R$/mês)", min_value=0.0, value=500.0, key="nova_desp_valor")
                    nova_desp_pct_receita = 0.0
                    nova_desp_valor_sessao = 0.0
                    nova_desp_base = "receita"
                else:
                    st.markdown("##### Configuração da Despesa Variável")
                    
                    nova_desp_base = st.radio(
                        "Base de cálculo",
                        ["receita", "sessao"],
                        format_func=lambda x: "% sobre Receita Bruta" if x == "receita" else "R$ por Sessão",
                        horizontal=True,
                        key="nova_desp_base"
                    )
                    
                    if nova_desp_base == "receita":
                        nova_desp_pct_receita = st.number_input(
                            "% sobre Receita Bruta",
                            min_value=0.0, max_value=100.0,
                            value=2.0, step=0.5,
                            help="Ex: 2% = material de consumo proporcional à receita",
                            key="nova_desp_pct_rec"
                        ) / 100
                        nova_desp_valor_sessao = 0.0
                        nova_desp_valor = 0.0
                    else:
                        nova_desp_valor_sessao = st.number_input(
                            "Valor por Sessão (R$)",
                            min_value=0.0, max_value=100.0,
                            value=5.0, step=0.5,
                            help="Ex: R$ 5,00 de material descartável por sessão",
                            key="nova_desp_vlr_sessao"
                        )
                        nova_desp_pct_receita = 0.0
                        nova_desp_valor = 0.0
                
                # ===== AVISO DE INCONSISTÊNCIA =====
                if nova_desp_nome:
                    aviso = verificar_tipo_despesa(nova_desp_nome, nova_desp_tipo)
                    if aviso:
                        st.warning(aviso)
                
                if st.button("✅ Cadastrar Despesa", key="btn_add_desp"):
                    if nova_desp_nome and nova_desp_nome.strip():
                        if nova_desp_nome in motor.despesas_fixas:
                            st.error(f"❌ '{nova_desp_nome}' já existe!")
                        else:
                            from motor_calculo import DespesaFixa
                            motor.despesas_fixas[nova_desp_nome] = DespesaFixa(
                                nome=nova_desp_nome,
                                categoria=nova_desp_categoria,
                                valor_mensal=nova_desp_valor,
                                tipo_reajuste=nova_desp_indice,
                                mes_reajuste=nova_desp_mes,
                                tipo_sazonalidade=nova_desp_sazon,
                                valores_2025=[nova_desp_valor] * 12,
                                tipo_despesa=nova_desp_tipo,
                                pct_receita=nova_desp_pct_receita,
                                valor_por_sessao=nova_desp_valor_sessao,
                                base_variavel=nova_desp_base
                            )
                            tipo_txt = "FIXA" if nova_desp_tipo == "fixa" else "VARIÁVEL"
                            st.success(f"✅ Despesa '{nova_desp_nome}' ({tipo_txt}) cadastrada!")
                            st.rerun()
                    else:
                        st.error("Digite o nome da despesa!")
            
            # Total (agora separando fixas e variáveis)
            total_fixas = sum(d.valor_mensal for d in motor.despesas_fixas.values() if d.ativa and d.tipo_despesa == "fixa")
            qtd_variaveis = len([d for d in motor.despesas_fixas.values() if d.ativa and d.tipo_despesa == "variavel"])
            
            # Calcula estimativa de variáveis (média mensal)
            if qtd_variaveis > 0:
                # Calcula receita e sessões para estimar variáveis
                motor.calcular_receita_bruta_total()
                receita_media_mes = sum(motor.receita_bruta.get("Total", [0]*12)) / 12
                
                # Calcula sessões médias por mês
                sessoes_media_mes = 0
                for fisio in motor.fisioterapeutas.values():
                    if fisio.ativo:
                        for srv, qtd in fisio.sessoes_por_servico.items():
                            pct = fisio.pct_crescimento_por_servico.get(srv, 0)
                            sessoes_media_mes += qtd * (1 + pct / 2)  # Média do ano
                
                # Soma das variáveis estimadas
                total_variaveis_estimado = 0
                for d in motor.despesas_fixas.values():
                    if d.ativa and d.tipo_despesa == "variavel":
                        if d.base_variavel == "receita":
                            total_variaveis_estimado += receita_media_mes * d.pct_receita
                        else:  # sessao
                            total_variaveis_estimado += sessoes_media_mes * d.valor_por_sessao
            else:
                total_variaveis_estimado = 0
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("🔒 Despesas Fixas", format_currency(total_fixas), "média mensal")
            with col2:
                if qtd_variaveis > 0:
                    st.metric("📊 Despesas Variáveis", format_currency(total_variaveis_estimado), f"{qtd_variaveis} {'item' if qtd_variaveis == 1 else 'itens'} · média mensal")
                else:
                    st.metric("📊 Despesas Variáveis", "Nenhuma", "cadastre para acompanhar custos")
        
        # ===== PROJEÇÃO 2026 =====
        with subtab_desp2:
            st.markdown("#### 📊 Projeção de Despesas 2026")
            st.caption("Valores projetados com reajustes aplicados")
            
            # Monta tabela de projeção
            indices = {
                'ipca': motor.macro.ipca,
                'igpm': motor.macro.igpm,
                'dissidio': motor.macro.dissidio,
                'tarifas': motor.macro.reajuste_tarifas,
                'contratos': motor.macro.reajuste_contratos,
                'nenhum': 0
            }
            
            # Dados para tabela
            dados_proj = []
            totais_mes = [0.0] * 12
            
            for nome, desp in motor.despesas_fixas.items():
                if not desp.ativa:
                    continue
                    
                linha = {"Despesa": nome}
                total_ano = 0
                
                for mes in range(12):
                    valor = desp.calcular_valor_mes(mes, indices)
                    linha[MESES_ABREV[mes]] = valor
                    total_ano += valor
                    totais_mes[mes] += valor
                
                linha["TOTAL"] = total_ano
                dados_proj.append(linha)
            
            # Adiciona linha de totais
            linha_total = {"Despesa": "**TOTAL**"}
            for i, mes in enumerate(MESES_ABREV):
                linha_total[mes] = totais_mes[i]
            linha_total["TOTAL"] = sum(totais_mes)
            dados_proj.append(linha_total)
            
            # Exibe tabela
            df_proj = pd.DataFrame(dados_proj)
            
            # Formata valores
            cols_valor = MESES_ABREV + ["TOTAL"]
            for col in cols_valor:
                df_proj[col] = df_proj[col].apply(lambda x: f"R$ {x:,.2f}")
            
            st.dataframe(df_proj, use_container_width=True, hide_index=True)
            
            # Resumo
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Projetado 2026", format_currency(sum(totais_mes)))
            with col2:
                st.metric("Média Mensal", format_currency(sum(totais_mes)/12))
        
        # ===== CUSTO DE PESSOAL =====
        with subtab_desp3:
            st.markdown("#### Custo de Pessoal")
            st.caption("Folha de pagamento e encargos")
            
            col1, col2 = st.columns(2)
            
            with col1:
                motor.custo_pessoal_mensal = st.number_input(
                    "Custo Total de Pessoal (R$/mês)",
                    min_value=0.0, max_value=500000.0,
                    value=float(motor.custo_pessoal_mensal),
                    step=1000.0,
                    help="Inclui salários, encargos, benefícios, pró-labore"
                )
                
                # Garante que mes_dissidio seja válido (1-12)
                mes_dissidio_idx = max(0, min(11, motor.mes_dissidio - 1)) if motor.mes_dissidio > 0 else 4  # Default: Maio
                motor.mes_dissidio = st.selectbox(
                    "Mês do Dissídio",
                    options=list(range(1, 13)),
                    format_func=lambda x: MESES[x-1],
                    index=mes_dissidio_idx,
                    help="Mês em que ocorre o reajuste salarial"
                )
            
            with col2:
                # Preview com dissídio
                st.markdown("**Projeção com Dissídio:**")
                
                custo_antes = motor.custo_pessoal_mensal
                custo_depois = custo_antes * (1 + motor.macro.dissidio)
                
                # Protege contra mes_dissidio = 0
                mes_diss = motor.mes_dissidio if motor.mes_dissidio > 0 else 5  # Default: Maio
                
                mes_anterior = MESES[mes_diss - 2] if mes_diss > 1 else 'Dez'
                st.write(f"Jan a {mes_anterior}: **{format_currency(custo_antes)}**/mês")
                st.write(f"{MESES[mes_diss - 1]} a Dez: **{format_currency(custo_depois)}**/mês")
                
                # Custo anual
                meses_antes = mes_diss - 1
                meses_depois = 12 - meses_antes
                custo_anual = (custo_antes * meses_antes) + (custo_depois * meses_depois)
                st.metric("Custo Anual de Pessoal", format_currency(custo_anual))
    
    # ========== ABA FOLHA E PRÓ-LABORE ==========
    with tab8:
        st.markdown("### 👔 Folha de Pagamento e Pró-Labore")
        
        # Sincroniza proprietários automaticamente
        motor.sincronizar_proprietarios()
        
        # Sub-abas
        subtab_f1, subtab_f2, subtab_f3 = st.tabs(["📋 Premissas Folha", "📊 Projeção 2026", "➕ Cadastros"])
        
        # ===== PREMISSAS FOLHA =====
        with subtab_f1:
            st.markdown("#### 📋 Premissas para Cálculo de Folha")
            
            pf = motor.premissas_folha
            
            # ===== REGIME TRIBUTÁRIO (SOMENTE LEITURA) =====
            st.markdown("##### 🏢 Regime Tributário")
            
            col_reg1, col_reg2 = st.columns([2, 1])
            with col_reg1:
                regime_atual = motor.operacional.modelo_tributario if motor.operacional.modelo_tributario else "PJ - Simples Nacional"
                st.info(f"📋 **Regime Selecionado:** {regime_atual}")
                st.caption("⚙️ Para alterar, vá em: **Premissas → Operacional**")
            
            with col_reg2:
                if "Simples" in regime_atual or "PJ" in regime_atual:
                    st.success("📊 **PJ - DAS**")
                    st.caption("Imposto unificado mensal")
                else:
                    st.warning("📋 **PF - IRRF + INSS**")
                    st.caption("Carnê Leão + contribuição")
            
            st.markdown("---")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Parâmetros Gerais**")
                
                pf.deducao_dependente_ir = st.number_input(
                    "Dedução por Dependente IR (R$)",
                    min_value=0.0, max_value=500.0,
                    value=float(pf.deducao_dependente_ir),
                    step=10.0,
                    key="ded_dep_ir"
                )
                
                pf.aliquota_fgts = st.number_input(
                    "Alíquota FGTS (%)",
                    min_value=0.0, max_value=0.20,
                    value=float(pf.aliquota_fgts),
                    step=0.01,
                    format="%.2f",
                    key="aliq_fgts"
                )
            
            with col2:
                st.markdown("**Dissídio**")
                
                # Garante que mes_dissidio seja válido (1-12)
                mes_diss_idx = max(0, min(11, pf.mes_dissidio - 1)) if pf.mes_dissidio > 0 else 4  # Default: Maio
                pf.mes_dissidio = st.selectbox(
                    "Mês do Dissídio",
                    list(range(1, 13)),
                    index=mes_diss_idx,
                    format_func=lambda x: MESES[x-1],
                    key="mes_diss_folha"
                )
                
                pf.pct_dissidio = st.number_input(
                    "% Dissídio",
                    min_value=0.0, max_value=0.30,
                    value=float(pf.pct_dissidio),
                    step=0.01,
                    format="%.2f",
                    key="pct_diss_folha"
                )
                
                pf.dias_uteis_mes = st.number_input(
                    "Dias Úteis/Mês",
                    min_value=0, max_value=25,
                    value=max(0, int(pf.dias_uteis_mes)),
                    key="dias_uteis"
                )
            
            st.markdown("---")
            
            # ===== TABELAS INSS E IR =====
            st.markdown("#### 📊 Tabelas de INSS e IR (Atualize conforme legislação vigente)")
            
            col_inss, col_ir = st.columns(2)
            
            with col_inss:
                st.markdown("**Tabela INSS (método dedução)**")
                st.caption("Faixas (limite, alíquota, dedução)")
                
                # Editar tabela INSS
                for i, (limite, aliq, deduc) in enumerate(pf.tabela_inss):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        novo_limite = st.number_input(
                            f"Faixa {i+1} - Limite",
                            min_value=0.0, max_value=20000.0,
                            value=float(limite),
                            step=100.0,
                            key=f"inss_lim_{i}"
                        )
                    with c2:
                        nova_aliq = st.number_input(
                            f"Alíquota",
                            min_value=0.0, max_value=0.20,
                            value=float(aliq),
                            step=0.005,
                            format="%.3f",
                            key=f"inss_aliq_{i}"
                        )
                    with c3:
                        nova_deduc = st.number_input(
                            f"Dedução",
                            min_value=0.0, max_value=500.0,
                            value=float(deduc),
                            step=5.0,
                            key=f"inss_ded_{i}"
                        )
                    pf.tabela_inss[i] = (novo_limite, nova_aliq, nova_deduc)
            
            with col_ir:
                st.markdown("**Tabela IR Retido na Fonte**")
                st.caption("Faixas (limite, alíquota, dedução)")
                
                # Editar tabela IR
                for i, (limite, aliq, deduc) in enumerate(pf.tabela_ir):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        novo_limite = st.number_input(
                            f"Faixa {i+1} - Limite",
                            min_value=0.0, max_value=99999999.0,
                            value=float(limite),
                            step=100.0,
                            key=f"ir_lim_{i}"
                        )
                    with c2:
                        nova_aliq = st.number_input(
                            f"Alíquota",
                            min_value=0.0, max_value=0.30,
                            value=float(aliq),
                            step=0.005,
                            format="%.3f",
                            key=f"ir_aliq_{i}"
                        )
                    with c3:
                        nova_deduc = st.number_input(
                            f"Dedução",
                            min_value=0.0, max_value=5000.0,
                            value=float(deduc),
                            step=10.0,
                            key=f"ir_ded_{i}"
                        )
                    pf.tabela_ir[i] = (novo_limite, nova_aliq, nova_deduc)
            
            st.caption("💡 Tabela IR 2026: Isenção para base de cálculo até R$ 5.000,00")
            
            st.markdown("---")
            
            # Cadastro de Sócios (Pró-Labore)
            st.markdown("#### 👔 Cadastro de Sócios (Pró-Labore)")
            st.caption("💡 Proprietários cadastrados em 'Atendimentos' ou 'Folha Fisioterapeutas' aparecem aqui automaticamente.")
            
            # Cabeçalho
            cols = st.columns([3, 2, 1, 2, 1, 1])
            cols[0].markdown("**Nome**")
            cols[1].markdown("**Pró-Labore**")
            cols[2].markdown("**Dep. IR**")
            cols[3].markdown("**Mês Reajuste**")
            cols[4].markdown("**% Aum.**")
            cols[5].markdown("**🗑️**")
            
            socios_remover = []
            for nome, socio in motor.socios_prolabore.items():
                cols = st.columns([3, 2, 1, 2, 1, 1])
                
                with cols[0]:
                    socio.ativo = st.checkbox(nome, value=socio.ativo, key=f"socio_ativo_{nome}")
                
                with cols[1]:
                    socio.prolabore = st.number_input(
                        "PL", min_value=0.0, max_value=50000.0,
                        value=float(socio.prolabore), step=100.0,
                        key=f"socio_pl_{nome}", label_visibility="collapsed"
                    )
                
                with cols[2]:
                    socio.dependentes_ir = st.number_input(
                        "Dep", min_value=0, max_value=10,
                        value=int(socio.dependentes_ir),
                        key=f"socio_dep_{nome}", label_visibility="collapsed"
                    )
                
                with cols[3]:
                    socio.mes_reajuste = st.selectbox(
                        "Mês", list(range(1, 13)),
                        index=max(0, min(11, socio.mes_reajuste - 1)) if socio.mes_reajuste > 0 else 4,
                        format_func=lambda x: MESES[x-1],
                        key=f"socio_mes_{nome}", label_visibility="collapsed"
                    )
                
                with cols[4]:
                    socio.pct_aumento = st.number_input(
                        "%", min_value=0.0, max_value=0.50,
                        value=float(socio.pct_aumento), step=0.01,
                        format="%.2f", key=f"socio_pct_{nome}", label_visibility="collapsed"
                    )
                
                with cols[5]:
                    if st.button("🗑️", key=f"rem_socio_{nome}"):
                        socios_remover.append(nome)
            
            for s in socios_remover:
                if s in motor.socios_prolabore:
                    del motor.socios_prolabore[s]
                # Também remover de estruturas relacionadas (sócios são proprietários)
                if s in motor.proprietarios:
                    del motor.proprietarios[s]
                if s in motor.fisioterapeutas:
                    del motor.fisioterapeutas[s]
            
            if socios_remover:
                st.rerun()
            
            st.markdown("---")
            
            # Cadastro de Funcionários
            st.markdown("#### 👥 Cadastro de Funcionários (CLT e Informal)")
            
            # Cabeçalho
            cols = st.columns([2, 2, 1.5, 1.5, 1, 0.5])
            cols[0].markdown("**Nome**")
            cols[1].markdown("**Cargo**")
            cols[2].markdown("**Vínculo**")
            cols[3].markdown("**Salário Base**")
            cols[4].markdown("**Dep. IR**")
            cols[5].markdown("**🗑️**")
            
            func_remover = []
            for nome, func in motor.funcionarios_clt.items():
                cols = st.columns([2, 2, 1.5, 1.5, 1, 0.5])
                
                with cols[0]:
                    func.ativo = st.checkbox(nome, value=func.ativo, key=f"func_ativo_{nome}")
                
                with cols[1]:
                    func.cargo = st.text_input(
                        "Cargo", value=func.cargo,
                        key=f"func_cargo_{nome}", label_visibility="collapsed"
                    )
                
                with cols[2]:
                    vinculo_opcoes = ["clt", "informal"]
                    vinculo_nomes = {"clt": "CLT", "informal": "Informal"}
                    vinculo_atual = vinculo_opcoes.index(func.tipo_vinculo) if func.tipo_vinculo in vinculo_opcoes else 1
                    func.tipo_vinculo = st.selectbox(
                        "Vínculo", vinculo_opcoes,
                        index=vinculo_atual,
                        format_func=lambda x: vinculo_nomes.get(x, x),
                        key=f"func_vinculo_{nome}", label_visibility="collapsed"
                    )
                
                with cols[3]:
                    func.salario_base = st.number_input(
                        "Sal", min_value=0.0, max_value=30000.0,
                        value=float(func.salario_base), step=50.0,
                        key=f"func_sal_{nome}", label_visibility="collapsed"
                    )
                
                with cols[4]:
                    func.dependentes_ir = st.number_input(
                        "Dep", min_value=0, max_value=10,
                        value=int(func.dependentes_ir),
                        key=f"func_dep_{nome}", label_visibility="collapsed"
                    )
                
                with cols[5]:
                    if st.button("🗑️", key=f"rem_func_{nome}"):
                        func_remover.append(nome)
            
            for f in func_remover:
                if f in motor.funcionarios_clt:
                    del motor.funcionarios_clt[f]
            
            if func_remover:
                st.rerun()
            
            # Totais
            st.markdown("---")
            total_clt = sum(f.salario_base for f in motor.funcionarios_clt.values() if f.ativo and f.tipo_vinculo == "clt")
            total_informal = sum(f.salario_base for f in motor.funcionarios_clt.values() if f.ativo and f.tipo_vinculo == "informal")
            total_prolabore = sum(s.prolabore for s in motor.socios_prolabore.values() if s.ativo)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total CLT", format_currency(total_clt))
            col2.metric("Total Informal", format_currency(total_informal))
            col3.metric("Total Pró-Labore", format_currency(total_prolabore))
            col4.metric("Total Geral", format_currency(total_clt + total_informal + total_prolabore))
        
        # ===== PROJEÇÃO 2026 =====
        with subtab_f2:
            st.markdown("#### 📊 Projeção Folha e Pró-Labore 2026")
            
            # Calcula projeção anual
            projecao = motor.projetar_folha_anual()
            
            # RESUMO GERAL
            st.markdown("##### Resumo Geral (CLT + Sócios)")
            
            dados_resumo = []
            totais_col = {"salarios": 0, "inss": 0, "irrf": 0, "fgts": 0, "custo": 0}
            
            for mes_idx, folha in enumerate(projecao):
                dados_resumo.append({
                    "Mês": MESES_ABREV[mes_idx],
                    "Salários + PL": folha["total"]["salarios"],
                    "INSS": folha["total"]["inss"],
                    "IRRF": folha["total"]["irrf"],
                    "FGTS": folha["total"]["fgts"],
                    "Custo Total": folha["total"]["custo_total"]
                })
                totais_col["salarios"] += folha["total"]["salarios"]
                totais_col["inss"] += folha["total"]["inss"]
                totais_col["irrf"] += folha["total"]["irrf"]
                totais_col["fgts"] += folha["total"]["fgts"]
                totais_col["custo"] += folha["total"]["custo_total"]
            
            # Linha total
            dados_resumo.append({
                "Mês": "TOTAL",
                "Salários + PL": totais_col["salarios"],
                "INSS": totais_col["inss"],
                "IRRF": totais_col["irrf"],
                "FGTS": totais_col["fgts"],
                "Custo Total": totais_col["custo"]
            })
            
            df_resumo = pd.DataFrame(dados_resumo)
            for col in ["Salários + PL", "INSS", "IRRF", "FGTS", "Custo Total"]:
                df_resumo[col] = df_resumo[col].apply(lambda x: f"R$ {x:,.2f}")
            
            st.dataframe(df_resumo, use_container_width=True, hide_index=True)
            
            # Métricas
            col1, col2 = st.columns(2)
            col1.metric("Custo Total Anual", format_currency(totais_col["custo"]))
            col2.metric("Média Mensal", format_currency(totais_col["custo"] / 12))
            
            st.markdown("---")
            
            # DETALHAMENTO PRÓ-LABORE
            st.markdown("##### Projeção Pró-Labore Sócios")
            
            dados_pl = []
            for mes_idx, folha in enumerate(projecao):
                dados_pl.append({
                    "Mês": MESES_ABREV[mes_idx],
                    "Bruto": folha["prolabore"]["bruto"],
                    "INSS": folha["prolabore"]["inss"],
                    "IRRF": folha["prolabore"]["irrf"],
                    "Líquido": folha["prolabore"]["liquido"]
                })
            
            # Total
            total_pl = {
                "bruto": sum(f["prolabore"]["bruto"] for f in projecao),
                "inss": sum(f["prolabore"]["inss"] for f in projecao),
                "irrf": sum(f["prolabore"]["irrf"] for f in projecao),
                "liquido": sum(f["prolabore"]["liquido"] for f in projecao)
            }
            dados_pl.append({
                "Mês": "TOTAL",
                "Bruto": total_pl["bruto"],
                "INSS": total_pl["inss"],
                "IRRF": total_pl["irrf"],
                "Líquido": total_pl["liquido"]
            })
            
            df_pl = pd.DataFrame(dados_pl)
            for col in ["Bruto", "INSS", "IRRF", "Líquido"]:
                df_pl[col] = df_pl[col].apply(lambda x: f"R$ {x:,.2f}")
            
            st.dataframe(df_pl, use_container_width=True, hide_index=True)
            
            st.markdown("---")
            
            # DETALHAMENTO CLT
            st.markdown("##### Projeção Folha CLT")
            
            dados_clt = []
            for mes_idx, folha in enumerate(projecao):
                dados_clt.append({
                    "Mês": MESES_ABREV[mes_idx],
                    "Salários": folha["clt"]["salarios_brutos"],
                    "INSS": folha["clt"]["inss"],
                    "IRRF": folha["clt"]["irrf"],
                    "FGTS": folha["clt"]["fgts"],
                    "Líquido": folha["clt"]["liquido"]
                })
            
            # Total
            total_clt = {
                "sal": sum(f["clt"]["salarios_brutos"] for f in projecao),
                "inss": sum(f["clt"]["inss"] for f in projecao),
                "irrf": sum(f["clt"]["irrf"] for f in projecao),
                "fgts": sum(f["clt"]["fgts"] for f in projecao),
                "liq": sum(f["clt"]["liquido"] for f in projecao)
            }
            dados_clt.append({
                "Mês": "TOTAL",
                "Salários": total_clt["sal"],
                "INSS": total_clt["inss"],
                "IRRF": total_clt["irrf"],
                "FGTS": total_clt["fgts"],
                "Líquido": total_clt["liq"]
            })
            
            df_clt = pd.DataFrame(dados_clt)
            for col in ["Salários", "INSS", "IRRF", "FGTS", "Líquido"]:
                df_clt[col] = df_clt[col].apply(lambda x: f"R$ {x:,.2f}")
            
            st.dataframe(df_clt, use_container_width=True, hide_index=True)
        
        # ===== CADASTROS =====
        with subtab_f3:
            st.markdown("#### ➕ Adicionar Novo Cadastro")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("##### Novo Sócio (Pró-Labore)")
                from motor_calculo import SocioProLabore
                
                novo_socio_nome = st.text_input("Nome do Sócio", key="novo_socio_nome")
                novo_socio_pl = st.number_input("Pró-Labore (R$)", min_value=0.0, value=1500.0, key="novo_socio_pl")
                
                if st.button("✅ Adicionar Sócio", key="btn_add_socio"):
                    if novo_socio_nome and novo_socio_nome.strip():
                        if novo_socio_nome in motor.socios_prolabore:
                            st.error(f"❌ '{novo_socio_nome}' já existe!")
                        else:
                            motor.socios_prolabore[novo_socio_nome] = SocioProLabore(
                                nome=novo_socio_nome,
                                prolabore=novo_socio_pl,
                                mes_reajuste=5
                            )
                            st.success(f"✅ Sócio '{novo_socio_nome}' adicionado!")
                            st.rerun()
                    else:
                        st.error("Digite o nome do sócio!")
            
            with col2:
                st.markdown("##### Novo Funcionário")
                from motor_calculo import FuncionarioCLT
                
                novo_func_nome = st.text_input("Nome do Funcionário", key="novo_func_nome")
                novo_func_cargo = st.text_input("Cargo", key="novo_func_cargo")
                novo_func_vinculo = st.selectbox(
                    "Tipo de Vínculo",
                    ["informal", "clt"],
                    format_func=lambda x: {"informal": "Informal", "clt": "CLT"}.get(x, x),
                    key="novo_func_vinculo"
                )
                novo_func_sal = st.number_input("Salário Base (R$)", min_value=0.0, value=1500.0, key="novo_func_sal")
                
                if st.button("✅ Adicionar Funcionário", key="btn_add_func"):
                    if novo_func_nome and novo_func_nome.strip():
                        if novo_func_nome in motor.funcionarios_clt:
                            st.error(f"❌ '{novo_func_nome}' já existe!")
                        else:
                            motor.funcionarios_clt[novo_func_nome] = FuncionarioCLT(
                                nome=novo_func_nome,
                                cargo=novo_func_cargo,
                                tipo_vinculo=novo_func_vinculo,
                                salario_base=novo_func_sal
                            )
                            st.success(f"✅ Funcionário '{novo_func_nome}' adicionado!")
                            st.rerun()
                    else:
                        st.error("Digite o nome do funcionário!")
    
    # ========== ABA FOLHA FISIOTERAPEUTAS ==========
    with tab9:
        st.markdown("### 🏥 Folha de Pagamento Fisioterapeutas")
        
        # Sincroniza proprietários automaticamente
        motor.sincronizar_proprietarios()
        
        # Info sobre sincronização
        st.info("💡 **Integração automática:** Proprietários cadastrados em 'Atendimentos' são sincronizados automaticamente com esta aba e 'Folha e Pró-Labore'.")
        
        # Sub-abas
        subtab_fisio1, subtab_fisio2, subtab_fisio3 = st.tabs(["📋 Premissas", "👥 Cadastro", "📊 Projeção 2026"])
        
        # ===== PREMISSAS =====
        with subtab_fisio1:
            st.markdown("#### 📋 Premissas de Remuneração")
            
            pf = motor.premissas_fisio
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Níveis de Remuneração (% s/ faturamento próprio)**")
                for nivel in [1, 2, 3, 4]:
                    pf.niveis_remuneracao[nivel] = st.number_input(
                        f"Nível {nivel} (%)",
                        min_value=0.0, max_value=1.0,
                        value=float(pf.niveis_remuneracao.get(nivel, 0.25)),
                        step=0.05,
                        format="%.2f",
                        key=f"nivel_rem_{nivel}"
                    )
            
            with col2:
                st.markdown("**Proprietário**")
                pf.pct_producao_propria = st.number_input(
                    "% s/ Produção Própria",
                    min_value=0.0, max_value=1.0,
                    value=float(pf.pct_producao_propria),
                    step=0.05,
                    format="%.2f",
                    key="pct_prod_propria"
                )
                pf.pct_faturamento_total = st.number_input(
                    "% s/ Faturamento Total",
                    min_value=0.0, max_value=1.0,
                    value=float(pf.pct_faturamento_total),
                    step=0.05,
                    format="%.2f",
                    key="pct_fat_total"
                )
                
                st.markdown("**Gerência**")
                pf.pct_gerencia_equipe = st.number_input(
                    "% Gerência s/ Equipe",
                    min_value=0.0, max_value=0.10,
                    value=float(pf.pct_gerencia_equipe),
                    step=0.01,
                    format="%.2f",
                    key="pct_ger_equipe"
                )
        
        # ===== CADASTRO =====
        with subtab_fisio2:
            st.markdown("#### 👥 Cadastro de Fisioterapeutas")
            st.caption("💡 Escolha entre: **Percentual** (nível), **Valor Fixo** (R$/sessão) ou **Misto** (% + fixo)")
            
            # Verificar se há profissionais com R$ Fixo sem valores configurados
            fisios_sem_valores = []
            for nome, fisio in motor.fisioterapeutas.items():
                if fisio.cargo != "Proprietário" and fisio.ativo:
                    if fisio.tipo_remuneracao == "valor_fixo":
                        # Verificar se tem valores configurados para os serviços que atende
                        servicos_atendidos = [s for s in fisio.sessoes_por_servico.keys() if fisio.sessoes_por_servico[s] > 0]
                        valores_configurados = [s for s in servicos_atendidos if fisio.valores_fixos_por_servico.get(s, 0) > 0]
                        if servicos_atendidos and len(valores_configurados) < len(servicos_atendidos):
                            fisios_sem_valores.append(nome)
            
            if fisios_sem_valores:
                st.error(f"⚠️ **ATENÇÃO:** Os seguintes profissionais estão com 'R$ Fixo' mas SEM valores configurados: **{', '.join(fisios_sem_valores)}**. Configure os valores ou mude para 'Percentual'.")
            
            # Cabeçalho
            cols = st.columns([2, 1.5, 1.2, 1, 1.3])
            cols[0].markdown("**Nome**")
            cols[1].markdown("**Cargo**")
            cols[2].markdown("**Tipo Rem.**")
            cols[3].markdown("**Nível/%**")
            cols[4].markdown("**Config.**")
            
            for nome, fisio in motor.fisioterapeutas.items():
                if fisio.cargo == "Proprietário":
                    continue  # Proprietário exibido separadamente
                    
                cols = st.columns([2, 1.5, 1.2, 1, 1.3])
                
                with cols[0]:
                    fisio.ativo = st.checkbox(nome, value=fisio.ativo, key=f"fisio_ativo_{nome}")
                
                with cols[1]:
                    cargo_opcoes = ["Fisioterapeuta", "Gerente"]
                    cargo_atual = cargo_opcoes.index(fisio.cargo) if fisio.cargo in cargo_opcoes else 0
                    fisio.cargo = st.selectbox(
                        "Cargo", cargo_opcoes,
                        index=cargo_atual,
                        key=f"fisio_cargo_{nome}",
                        label_visibility="collapsed"
                    )
                
                with cols[2]:
                    tipo_opcoes = ["percentual", "valor_fixo", "misto"]
                    tipo_nomes = {"percentual": "% Nível", "valor_fixo": "R$ Fixo", "misto": "Misto"}
                    tipo_atual = tipo_opcoes.index(fisio.tipo_remuneracao) if fisio.tipo_remuneracao in tipo_opcoes else 0
                    fisio.tipo_remuneracao = st.selectbox(
                        "Tipo", tipo_opcoes,
                        index=tipo_atual,
                        format_func=lambda x: tipo_nomes.get(x, x),
                        key=f"fisio_tipo_{nome}",
                        label_visibility="collapsed"
                    )
                
                with cols[3]:
                    if fisio.tipo_remuneracao in ["percentual", "misto"]:
                        fisio.nivel = st.selectbox(
                            "Nível", [1, 2, 3, 4],
                            index=fisio.nivel - 1 if fisio.nivel >= 1 else 0,
                            key=f"fisio_nivel_{nome}",
                            label_visibility="collapsed"
                        )
                        pct = motor.premissas_fisio.niveis_remuneracao.get(fisio.nivel, 0.25)
                        if fisio.tipo_remuneracao == "misto":
                            st.caption(f"{pct*100:.0f}% + fixo")
                        else:
                            st.caption(f"{pct*100:.0f}%")
                    else:
                        total_valores = sum(fisio.valores_fixos_por_servico.values())
                        if total_valores > 0:
                            st.caption(f"R$ {total_valores:.0f}/sessão")
                        else:
                            st.caption("⚠️ Configurar")
                
                with cols[4]:
                    if fisio.tipo_remuneracao in ["valor_fixo", "misto"]:
                        label_exp = "💰 Valores" if fisio.tipo_remuneracao == "valor_fixo" else "💰 + Fixo"
                        with st.expander(label_exp, expanded=False):
                            st.caption(f"**Valores por sessão - {nome}**")
                            if fisio.tipo_remuneracao == "misto":
                                st.caption("_(adicional ao percentual)_")
                            for srv in motor.servicos.keys():
                                valor_atual = fisio.valores_fixos_por_servico.get(srv, 0.0)
                                novo_valor = st.number_input(
                                    srv,
                                    min_value=0.0,
                                    max_value=500.0,
                                    value=float(valor_atual),
                                    step=5.0,
                                    key=f"fisio_vf_{nome}_{srv}",
                                    format="%.2f"
                                )
                                if novo_valor > 0:
                                    fisio.valores_fixos_por_servico[srv] = novo_valor
                                elif srv in fisio.valores_fixos_por_servico:
                                    del fisio.valores_fixos_por_servico[srv]
                    else:
                        st.caption("—")
            
            st.markdown("---")
            
            # Proprietário
            st.markdown("#### 👔 Proprietário")
            for nome, fisio in motor.fisioterapeutas.items():
                if fisio.cargo != "Proprietário":
                    continue
                
                col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1.5])
                
                with col1:
                    st.write(f"**{nome}**")
                
                with col2:
                    # Tipo de remuneração - 3 opções
                    tipo_atual = fisio.tipo_remuneracao if hasattr(fisio, 'tipo_remuneracao') else "percentual"
                    opcoes_tipo = ["Percentual", "Valor Fixo", "Misto"]
                    idx_tipo = {"percentual": 0, "valor_fixo": 1, "misto": 2}.get(tipo_atual, 0)
                    tipo_rem = st.selectbox(
                        "Tipo Rem.",
                        opcoes_tipo,
                        index=idx_tipo,
                        key=f"tipo_rem_prop_{nome}",
                        label_visibility="collapsed"
                    )
                    fisio.tipo_remuneracao = {"Percentual": "percentual", "Valor Fixo": "valor_fixo", "Misto": "misto"}[tipo_rem]
                
                with col3:
                    if fisio.tipo_remuneracao in ["percentual", "misto"]:
                        # Percentuais editáveis
                        pct_prod = st.number_input(
                            "% Produção",
                            min_value=0.0,
                            max_value=100.0,
                            value=motor.premissas_fisio.pct_producao_propria * 100,
                            step=5.0,
                            key=f"pct_prod_prop_{nome}",
                            format="%.0f"
                        )
                        motor.premissas_fisio.pct_producao_propria = pct_prod / 100
                    else:
                        st.write("—")
                
                with col4:
                    if fisio.tipo_remuneracao in ["percentual", "misto"]:
                        pct_fat = st.number_input(
                            "% Fat. Total",
                            min_value=0.0,
                            max_value=100.0,
                            value=motor.premissas_fisio.pct_faturamento_total * 100,
                            step=5.0,
                            key=f"pct_fat_prop_{nome}",
                            format="%.0f"
                        )
                        motor.premissas_fisio.pct_faturamento_total = pct_fat / 100
                    else:
                        st.write("—")
                
                # Valores fixos (para Valor Fixo e Misto)
                if fisio.tipo_remuneracao in ["valor_fixo", "misto"]:
                    with st.expander(f"💰 Valores Fixos por Sessão {'(adicional)' if fisio.tipo_remuneracao == 'misto' else ''}"):
                        cols_vf = st.columns(min(len(fisio.sessoes_por_servico), 4)) if fisio.sessoes_por_servico else [st]
                        for idx, srv in enumerate(fisio.sessoes_por_servico.keys()):
                            with cols_vf[idx % len(cols_vf)]:
                                valor_atual = fisio.valores_fixos_por_servico.get(srv, 0) if hasattr(fisio, 'valores_fixos_por_servico') else 0
                                novo_valor = st.number_input(
                                    f"{srv}",
                                    min_value=0.0,
                                    value=float(valor_atual),
                                    step=10.0,
                                    key=f"vf_prop_{nome}_{srv}",
                                    format="%.2f"
                                )
                                if not hasattr(fisio, 'valores_fixos_por_servico'):
                                    fisio.valores_fixos_por_servico = {}
                                if novo_valor > 0:
                                    fisio.valores_fixos_por_servico[srv] = novo_valor
                                elif srv in fisio.valores_fixos_por_servico:
                                    del fisio.valores_fixos_por_servico[srv]
                
                with col5:
                    # Mostra serviços dinâmicos do proprietário
                    servicos_prop = []
                    for srv, qtd in fisio.sessoes_por_servico.items():
                        if qtd > 0:
                            servicos_prop.append(f"{srv}: {qtd}")
                    if servicos_prop:
                        st.caption(f"{', '.join(servicos_prop)} sess/mês")
                    else:
                        st.caption("Nenhum serviço")
        
        # ===== PROJEÇÃO 2026 =====
        with subtab_fisio3:
            st.markdown("#### 📊 Projeção Folha Fisioterapeutas 2026")
            
            # Calcula projeção
            projecao_fisio = motor.projetar_folha_fisioterapeutas_anual()
            
            # Resumo Geral
            st.markdown("##### Resumo Geral")
            
            dados_resumo = []
            for mes_idx, folha in enumerate(projecao_fisio):
                dados_resumo.append({
                    "Mês": MESES[mes_idx],
                    "Produção Bruta": folha["producao_bruta"],
                    "Folha Fisios": folha["total_fisioterapeutas"],
                    "Folha Proprie.": folha["total_proprietarios"],
                    "Margem Clínica": folha["margem_clinica"],
                    "% Margem": folha["margem_clinica"] / folha["producao_bruta"] * 100 if folha["producao_bruta"] > 0 else 0
                })
            
            df_resumo = pd.DataFrame(dados_resumo)
            
            # Totais
            totais = {
                "Mês": "TOTAL",
                "Produção Bruta": df_resumo["Produção Bruta"].sum(),
                "Folha Fisios": df_resumo["Folha Fisios"].sum(),
                "Folha Proprie.": df_resumo["Folha Proprie."].sum(),
                "Margem Clínica": df_resumo["Margem Clínica"].sum(),
                "% Margem": df_resumo["Margem Clínica"].sum() / df_resumo["Produção Bruta"].sum() * 100
            }
            df_resumo = pd.concat([df_resumo, pd.DataFrame([totais])], ignore_index=True)
            
            # Formatação
            st.dataframe(
                df_resumo.style.format({
                    "Produção Bruta": "R$ {:,.2f}",
                    "Folha Fisios": "R$ {:,.2f}",
                    "Folha Proprie.": "R$ {:,.2f}",
                    "Margem Clínica": "R$ {:,.2f}",
                    "% Margem": "{:.1f}%"
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Métricas
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Produção Anual", format_currency(totais["Produção Bruta"]))
            col2.metric("Folha Fisioterapeutas", format_currency(totais["Folha Fisios"]))
            col3.metric("Folha Proprietários", format_currency(totais["Folha Proprie."]))
            col4.metric("Margem Clínica", format_currency(totais["Margem Clínica"]))
            
            st.markdown("---")
            
            # Obter nomes dinâmicos
            nome_gerente = "Gerente"
            nome_proprietario = "Proprietário"
            for nome, fisio in motor.fisioterapeutas.items():
                if fisio.cargo == "Gerente":
                    nome_gerente = nome
                elif fisio.cargo == "Proprietário":
                    nome_proprietario = nome
            
            # Explicação das remunerações especiais
            with st.expander("ℹ️ Regras de Remuneração", expanded=False):
                st.markdown(f"""
                **Fisioterapeutas:**
                - Remuneração = Faturamento Próprio × % Nível × 75%
                - Níveis: 1=35%, 2=30%, 3=25%, 4=20%
                
                **Gerente ({nome_gerente}):**
                - Remuneração Normal + Bônus de 1% sobre faturamento da equipe × 75%
                
                **Proprietário ({nome_proprietario}):**
                - 60% sobre Produção Própria (Osteopatia) → *informativo, não entra na folha*
                - 20% sobre Faturamento Total × 75% → **entra na Folha Proprietários**
                """)
            
            # Detalhamento por Fisioterapeuta
            st.markdown("##### 👥 Detalhamento Fisioterapeutas (Janeiro)")
            
            folha_jan = projecao_fisio[0]
            
            # Separar Gerente dos demais
            gerente = None
            fisios_normais = []
            for f in folha_jan["fisioterapeutas"]:
                if f["cargo"] == "Gerente":
                    gerente = f
                else:
                    fisios_normais.append(f)
            
            # Gerente em destaque
            if gerente:
                st.markdown("**🏆 Gerente:**")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric(gerente["nome"], f"Nível {gerente['nivel']}")
                col2.metric("Faturamento", format_currency(gerente["faturamento"]))
                col3.metric("Bônus Gerência 1%", format_currency(gerente["bonus_gerencia"]))
                col4.metric("Total Remuneração", format_currency(gerente["remuneracao"]))
            
            # Fisioterapeutas normais
            if fisios_normais:
                st.markdown("**Fisioterapeutas:**")
                dados_fisios = []
                for f in fisios_normais:
                    dados_fisios.append({
                        "Nome": f["nome"],
                        "Nível": f["nivel"],
                        "Sessões": f["sessoes"],
                        "Faturamento": f["faturamento"],
                        "% Nível": f["pct_nivel"] * 100,
                        "Remuneração": f["remuneracao"]
                    })
                
                df_fisios = pd.DataFrame(dados_fisios)
                st.dataframe(
                    df_fisios.style.format({
                        "Sessões": "{:.1f}",
                        "Faturamento": "R$ {:,.2f}",
                        "% Nível": "{:.0f}%",
                        "Remuneração": "R$ {:,.2f}"
                    }),
                    use_container_width=True,
                    hide_index=True
                )
            
            # Proprietários
            st.markdown("##### 👔 Proprietário (Janeiro)")
            if folha_jan["proprietarios"]:
                for p in folha_jan["proprietarios"]:
                    st.markdown(f"**{p['nome']}** - Osteopatia")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Sessões Osteopatia", f"{p['sessoes']:.1f}")
                        st.metric("Produção Própria", format_currency(p["producao_propria"]))
                        st.caption("60% Produção (informativo)")
                        st.write(f"**{format_currency(p['rem_producao_propria'])}**")
                    
                    with col2:
                        st.metric("20% s/ Faturamento Total", format_currency(p["rem_faturamento_total"]))
                        st.caption("↑ Este valor entra na Folha Proprietários")
                        st.metric("**FOLHA PROPRIETÁRIO**", format_currency(p["remuneracao"]), delta=None)
    
    # ========== BOTÃO CALCULAR ==========
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 CALCULAR SIMULAÇÃO", type="primary", use_container_width=True):
            with st.spinner("Calculando..."):
                # Recalcula tudo
                motor.calcular_dre()
                indicadores = motor.calcular_indicadores()
                
                st.success("✅ Simulação calculada com sucesso!")
                
                # Mostra indicadores
                st.markdown("### 📊 Resultados da Simulação")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    render_metric_card(
                        "Receita Bruta", 
                        format_currency(indicadores['Receita Bruta Total']),
                        card_type="success"
                    )
                with col2:
                    render_metric_card(
                        "EBITDA", 
                        format_currency(indicadores['EBITDA']),
                        card_type="success" if indicadores['EBITDA'] > 0 else "danger"
                    )
                with col3:
                    render_metric_card(
                        "Margem EBITDA", 
                        format_percent(indicadores['Margem EBITDA']),
                        card_type="success" if indicadores['Margem EBITDA'] > 0.15 else "warning"
                    )
                with col4:
                    render_metric_card(
                        "Total Sessões", 
                        format_number(indicadores['Total Sessões Ano']),
                        card_type="default"
                    )
    
    # ========== ABA SALAS (TDABC) ==========
    with tab10:
        st.markdown("### 🏢 Cadastro de Salas - TDABC")
        st.caption("Configure a infraestrutura física da clínica para custeio ABC")
        
        cadastro = motor.cadastro_salas
        
        # Sincronizar com premissas operacionais
        cadastro.horas_funcionamento_dia = motor.operacional.horas_atendimento_dia
        cadastro.dias_uteis_mes = motor.operacional.dias_uteis_mes
        
        # CORREÇÃO: Verificar se num_salas está configurado
        if motor.operacional.num_salas > 0:
            cadastro.sincronizar_num_salas(motor.operacional.num_salas)
        else:
            st.error("❌ **Nº de Salas = 0!** Configure na aba **🏥 Operacionais** antes de configurar as salas.")
            st.stop()
        
        # Resumo - MOSTRA O VALOR DE PREMISSAS
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Nº Salas (Premissas)", f"{motor.operacional.num_salas}")
        with col2:
            st.metric("m² Total Ativo", f"{cadastro.m2_ativo:.0f} m²")
        with col3:
            st.metric("Capacidade/Mês", f"{cadastro.capacidade_total_horas:.0f}h")
        with col4:
            st.metric("Horas/Dia", f"{motor.operacional.horas_atendimento_dia}h")
        
        st.info(f"ℹ️ Mostrando **{motor.operacional.num_salas} salas** (configurado na aba **🏥 Operacionais**).")
        
        st.markdown("---")
        
        # Lista de salas ativas
        st.markdown("#### 📋 Configuração das Salas")
        
        servicos_disponiveis = list(motor.servicos.keys())
        
        # Usar salas_ativas para garantir que apenas as salas definidas em Premissas apareçam
        salas_para_mostrar = cadastro.salas_ativas
        
        if not salas_para_mostrar:
            st.warning("⚠️ Nenhuma sala ativa. Configure o Nº de Salas em **🏥 Operacionais**.")
        
        for sala in salas_para_mostrar:
            # Título do expander
            if sala.metros_quadrados > 0:
                titulo_sala = f"✅ Sala {sala.numero} - {sala.tipo} ({sala.metros_quadrados:.0f}m²)"
            else:
                titulo_sala = f"⚠️ Sala {sala.numero} - Não configurada"
            
            with st.expander(titulo_sala, expanded=(sala.metros_quadrados == 0)):
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    sala.metros_quadrados = st.number_input(
                        "m²",
                        min_value=0.0,
                        max_value=200.0,
                        value=float(sala.metros_quadrados),
                        step=1.0,
                        key=f"sala_{sala.numero}_m2"
                    )
                
                with col2:
                    sala.tipo = st.selectbox(
                        "Tipo",
                        options=["Individual", "Compartilhado"],
                        index=0 if sala.tipo == "Individual" else 1,
                        key=f"sala_{sala.numero}_tipo"
                    )
                
                # Aviso se sala não configurada
                if sala.metros_quadrados == 0:
                    st.warning("⚠️ Configure o tamanho (m²) desta sala")
                
                st.markdown("**Serviços atendidos nesta sala:**")
                
                # Filtrar serviços salvos que ainda existem nas opções
                servicos_validos = [s for s in (sala.servicos_atendidos or []) if s in servicos_disponiveis]
                
                # Multiselect para serviços
                servicos_selecionados = st.multiselect(
                    "Selecione os serviços",
                    options=servicos_disponiveis,
                    default=servicos_validos,
                    key=f"sala_{sala.numero}_servicos",
                    label_visibility="collapsed"
                )
                sala.servicos_atendidos = servicos_selecionados
                
                if servicos_selecionados and sala.metros_quadrados > 0:
                    st.caption(f"m²/serviço: {sala.m2_por_servico:.2f} m²")
        
        # Botões de ação
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button("🗑️ Resetar Salas", use_container_width=True, key="btn_resetar_salas_prem"):
                # Limpar todas as salas para valores em branco
                for sala in cadastro.salas:
                    sala.metros_quadrados = 0.0
                    sala.tipo = "Individual"
                    sala.servicos_atendidos = []
                
                # Limpar cache do session_state
                keys_para_limpar = [k for k in st.session_state.keys() if k.startswith('sala_')]
                for k in keys_para_limpar:
                    del st.session_state[k]
                
                # Salvar imediatamente
                if salvar_filial_atual():
                    st.success("✅ Salas resetadas! Todas em branco.")
                    st.rerun()
        
        with col2:
            if st.button("💾 Salvar Configuração das Salas", type="primary", use_container_width=True, key="btn_salvar_salas_prem"):
                if salvar_filial_atual():
                    st.success("✅ Configuração das salas salva com sucesso!")
                    st.rerun()
        
        st.markdown("---")
        
        # Mix de Serviços
        st.markdown("#### 📊 Mix de Alocação por Serviço")
        
        mix = cadastro.get_mix_servicos()
        
        if mix:
            
            dados_mix = []
            for srv, info in mix.items():
                dados_mix.append({
                    "Serviço": srv,
                    "m² Alocado": f"{info['m2_alocado']:.2f}",
                    "% Espaço": f"{info['pct_espaco']*100:.1f}%",
                    "Nº Salas": info['num_salas'],
                    "Salas": ", ".join([f"Sala {n}" for n in info['salas']])
                })
            
            df_mix = pd.DataFrame(dados_mix)
            st.dataframe(df_mix, use_container_width=True, hide_index=True)
            
            # Serviços sem sala (Domiciliar)
            servicos_sem_sala = [s for s in servicos_disponiveis if s not in mix]
            if servicos_sem_sala:
                st.info(f"ℹ️ Serviços sem uso de sala: **{', '.join(servicos_sem_sala)}** (atendimento externo)")
        else:
            st.warning("Nenhum serviço alocado às salas. Configure os serviços atendidos em cada sala.")

    # ========== ABA CENÁRIOS ==========
    with tab11:
        st.markdown("### 🎯 Configuração de Cenários")
        
        # Toggle para habilitar/desabilitar módulo de cenários
        if not hasattr(motor, 'usar_cenarios'):
            motor.usar_cenarios = True
        
        col_toggle1, col_toggle2 = st.columns([1, 3])
        with col_toggle1:
            usar_cenarios = st.checkbox(
                "Usar módulo de Cenários",
                value=motor.usar_cenarios,
                key="chk_usar_cenarios",
                help="Habilita/desabilita análise de cenários para esta filial"
            )
            motor.usar_cenarios = usar_cenarios
        
        with col_toggle2:
            if usar_cenarios:
                st.success("✅ Módulo habilitado - O menu '🎯 Cenários' está visível")
            else:
                st.warning("⚠️ Módulo desabilitado - O menu '🎯 Cenários' ficará oculto")
        
        # Se desabilitado, mostra apenas o toggle
        if not usar_cenarios:
            st.info("💡 Marque a opção acima para habilitar análise de cenários (Pessimista/Conservador/Otimista)")
            st.caption("🔄 Após habilitar, clique em **💾 Salvar** na barra lateral e recarregue a página")
        
        else:
            # Conteúdo normal da aba
            st.caption("O **Conservador** usa as premissas cadastradas. Configure ajustes para os cenários Pessimista e Otimista.")
            
            # Inicializa ajustes se não existir
            if not hasattr(motor, 'ajustes_cenarios') or motor.ajustes_cenarios is None:
                motor.restaurar_ajustes_padrao()
            
            if not hasattr(motor, 'cenario_oficial'):
                motor.cenario_oficial = "Conservador"
            
            # Inicializa campos de faturamento anterior
            if not hasattr(motor, 'usar_comparativo_anterior'):
                motor.usar_comparativo_anterior = False
            if not hasattr(motor, 'faturamento_anterior'):
                motor.faturamento_anterior = [0.0] * 12
            if not hasattr(motor, 'ano_anterior'):
                motor.ano_anterior = 2025
            
            st.markdown("---")
            
            # ========================================================================
            # FATURAMENTO DO EXERCÍCIO ANTERIOR
            # ========================================================================
            st.markdown("#### 📅 Comparativo com Exercício Anterior")
        
            col_comp1, col_comp2 = st.columns([1, 3])
        
            with col_comp1:
                usar_comp = st.checkbox(
                    "Usar comparativo",
                    value=motor.usar_comparativo_anterior,
                    key="chk_usar_comparativo",
                    help="Habilita comparação do orçamento com faturamento real do ano anterior"
                )
                motor.usar_comparativo_anterior = usar_comp
            
            with col_comp2:
                ano_ant = st.number_input(
                    "Ano de referência",
                    min_value=2020, max_value=2030,
                    value=motor.ano_anterior,
                    key="input_ano_anterior",
                    disabled=not usar_comp
                )
                motor.ano_anterior = ano_ant
            
            if usar_comp:
                st.markdown(f"##### 💰 Faturamento Bruto {ano_ant} (Real)")
                st.caption("Informe o faturamento mensal realizado no ano anterior")
                
                meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
                
                # Linha 1: Jan-Jun
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                cols_1 = [col1, col2, col3, col4, col5, col6]
                
                for i, col in enumerate(cols_1):
                    with col:
                        valor = st.number_input(
                            meses[i],
                            min_value=0.0,
                            value=float(motor.faturamento_anterior[i]),
                            step=1000.0,
                            format="%.0f",
                            key=f"fat_ant_{i}"
                        )
                        motor.faturamento_anterior[i] = valor
                
                # Linha 2: Jul-Dez
                col7, col8, col9, col10, col11, col12 = st.columns(6)
                cols_2 = [col7, col8, col9, col10, col11, col12]
                
                for i, col in enumerate(cols_2):
                    with col:
                        idx = i + 6
                        valor = st.number_input(
                            meses[idx],
                            min_value=0.0,
                            value=float(motor.faturamento_anterior[idx]),
                            step=1000.0,
                            format="%.0f",
                            key=f"fat_ant_{idx}"
                        )
                        motor.faturamento_anterior[idx] = valor
                
                # Total
                total_anterior = sum(motor.faturamento_anterior)
                st.success(f"**Total {ano_ant}: R$ {total_anterior:,.0f}**")
                
                # Botão para salvar faturamento anterior
                if st.button("💾 Salvar Faturamento Anterior", key="btn_salvar_fat_anterior", type="primary"):
                    if salvar_filial_atual():
                        st.success("✅ Faturamento salvo! Agora vá em **🎯 Cenários** para ver o comparativo.")
                        st.balloons()
                    else:
                        st.error("❌ Erro ao salvar. Verifique se uma filial está selecionada.")
            
            st.markdown("---")
            
            # CENÁRIO OFICIAL
            st.markdown("#### ✅ Cenário Oficial para Relatórios")
            
            cenarios_opcoes = ["Conservador", "Pessimista", "Otimista"]
            idx_oficial = cenarios_opcoes.index(motor.cenario_oficial) if motor.cenario_oficial in cenarios_opcoes else 0
            
            col_of1, col_of2 = st.columns([2, 3])
            with col_of1:
                novo_oficial = st.selectbox(
                    "Cenário que aparece por padrão",
                    cenarios_opcoes,
                    index=idx_oficial,
                    key="select_cenario_oficial",
                    format_func=lambda x: f"⚠️ {x}" if x == "Conservador" else (f"📉 {x}" if x == "Pessimista" else f"🚀 {x}")
                )
                if novo_oficial != motor.cenario_oficial:
                    motor.cenario_oficial = novo_oficial
            
            with col_of2:
                descricoes = {
                    "Conservador": "Premissas cadastradas (base de referência)",
                    "Pessimista": "Base com ajustes negativos (cenário de crise)",
                    "Otimista": "Base com ajustes positivos (cenário favorável)"
                }
                st.info(f"💡 {descricoes[novo_oficial]}")
            
            st.markdown("---")
            
            # AJUSTES POR CENÁRIO
            st.markdown("#### 📊 Ajustes por Cenário")
            st.caption("Os ajustes são valores que **somam** às premissas base (Conservador). Positivo = aumenta, Negativo = diminui.")
            
            tab_pess, tab_otim = st.tabs(["📉 Pessimista", "🚀 Otimista"])
            
            # ========== PESSIMISTA ==========
            with tab_pess:
                st.markdown("##### 📉 Ajustes do Cenário Pessimista")
                st.caption("Configure reduções de sessões, valores ou aumentos de despesas")
                
                if "Pessimista" not in motor.ajustes_cenarios:
                    motor.ajustes_cenarios["Pessimista"] = {"sessoes": {}, "valores": {}, "despesas": {}, "descricao": ""}
                
                # Descrição
                desc_pess = st.text_input(
                    "Descrição do cenário",
                    value=motor.ajustes_cenarios["Pessimista"].get("descricao", "Cenário de crise"),
                    key="desc_pessimista"
                )
                motor.ajustes_cenarios["Pessimista"]["descricao"] = desc_pess
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🩺 Ajustes de Sessões/Mês**")
                    for servico in motor.servicos:
                        ajuste_atual = motor.ajustes_cenarios["Pessimista"].get("sessoes", {}).get(servico, 0)
                        novo_ajuste = st.number_input(
                            f"{servico}",
                            value=float(ajuste_atual),
                            step=5.0,
                            key=f"pess_sessoes_{servico}",
                            help=f"Ajuste sobre a base. Ex: -10 = reduz 10 sessões/mês"
                        )
                        if novo_ajuste != ajuste_atual:
                            if "sessoes" not in motor.ajustes_cenarios["Pessimista"]:
                                motor.ajustes_cenarios["Pessimista"]["sessoes"] = {}
                            motor.ajustes_cenarios["Pessimista"]["sessoes"][servico] = novo_ajuste
                
                with col2:
                    st.markdown("**💰 Ajustes de Despesas (R$/mês)**")
                    despesas_principais = ["Aluguel", "Energia Elétrica", "Marketing", "Contador", "Software"]
                    for desp in despesas_principais:
                        if desp in motor.despesas_fixas:
                            ajuste_atual = motor.ajustes_cenarios["Pessimista"].get("despesas", {}).get(desp, 0)
                            novo_ajuste = st.number_input(
                                f"{desp}",
                                value=float(ajuste_atual),
                                step=100.0,
                                key=f"pess_desp_{desp}",
                                help=f"Ajuste sobre a base. Ex: +500 = aumenta R$500/mês"
                            )
                            if novo_ajuste != ajuste_atual:
                                if "despesas" not in motor.ajustes_cenarios["Pessimista"]:
                                    motor.ajustes_cenarios["Pessimista"]["despesas"] = {}
                                motor.ajustes_cenarios["Pessimista"]["despesas"][desp] = novo_ajuste
            
            # ========== OTIMISTA ==========
            with tab_otim:
                st.markdown("##### 🚀 Ajustes do Cenário Otimista")
                st.caption("Configure aumentos de sessões, valores ou reduções de despesas")
                
                if "Otimista" not in motor.ajustes_cenarios:
                    motor.ajustes_cenarios["Otimista"] = {"sessoes": {}, "valores": {}, "despesas": {}, "descricao": ""}
                
                # Descrição
                desc_otim = st.text_input(
                    "Descrição do cenário",
                    value=motor.ajustes_cenarios["Otimista"].get("descricao", "Cenário favorável"),
                    key="desc_otimista"
                )
                motor.ajustes_cenarios["Otimista"]["descricao"] = desc_otim
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🩺 Ajustes de Sessões/Mês**")
                    for servico in motor.servicos:
                        ajuste_atual = motor.ajustes_cenarios["Otimista"].get("sessoes", {}).get(servico, 0)
                        novo_ajuste = st.number_input(
                            f"{servico}",
                            value=float(ajuste_atual),
                            step=5.0,
                            key=f"otim_sessoes_{servico}",
                            help=f"Ajuste sobre a base. Ex: +20 = aumenta 20 sessões/mês"
                        )
                        if novo_ajuste != ajuste_atual:
                            if "sessoes" not in motor.ajustes_cenarios["Otimista"]:
                                motor.ajustes_cenarios["Otimista"]["sessoes"] = {}
                            motor.ajustes_cenarios["Otimista"]["sessoes"][servico] = novo_ajuste
                
                with col2:
                    st.markdown("**💰 Ajustes de Despesas (R$/mês)**")
                    despesas_principais = ["Aluguel", "Energia Elétrica", "Marketing", "Contador", "Software"]
                    for desp in despesas_principais:
                        if desp in motor.despesas_fixas:
                            ajuste_atual = motor.ajustes_cenarios["Otimista"].get("despesas", {}).get(desp, 0)
                            novo_ajuste = st.number_input(
                                f"{desp}",
                                value=float(ajuste_atual),
                                step=100.0,
                                key=f"otim_desp_{desp}",
                                help=f"Ajuste sobre a base. Ex: -300 = reduz R$300/mês"
                            )
                            if novo_ajuste != ajuste_atual:
                                if "despesas" not in motor.ajustes_cenarios["Otimista"]:
                                    motor.ajustes_cenarios["Otimista"]["despesas"] = {}
                                motor.ajustes_cenarios["Otimista"]["despesas"][desp] = novo_ajuste
            
            st.markdown("---")
            
            # BOTÕES
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            
            with col_btn1:
                if st.button("🔄 Limpar Ajustes", key="btn_limpar_cenarios", use_container_width=True):
                    motor.restaurar_ajustes_padrao()
                    st.success("✅ Ajustes limpos!")
                    st.rerun()
            
            with col_btn2:
                if st.button("💾 Salvar", key="btn_salvar_cenarios", use_container_width=True, type="primary"):
                    if salvar_filial_atual():
                        st.success("✅ Cenários salvos!")
                    else:
                        st.error("❌ Erro ao salvar. Verifique se uma filial está selecionada.")
            
            # RESUMO
            st.markdown("---")
            st.markdown("#### 📋 Resumo dos Cenários")
            
            # Calcular totais para comparação
            motor.aplicar_cenario("Conservador")
            receita_conserv = sum(motor.calcular_receita_servico_mes(s, 5) for s in motor.servicos)
            
            motor.aplicar_cenario("Pessimista")
            receita_pess = sum(motor.calcular_receita_servico_mes(s, 5) for s in motor.servicos)
            
            motor.aplicar_cenario("Otimista")
            receita_otim = sum(motor.calcular_receita_servico_mes(s, 5) for s in motor.servicos)
            
            # Restaura cenário oficial
            motor.aplicar_cenario(motor.cenario_oficial)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📉 Pessimista (Jun)", f"R$ {receita_pess:,.0f}", 
                         f"{((receita_pess/receita_conserv)-1)*100:+.1f}%" if receita_conserv > 0 else "")
            with col2:
                st.metric("⚠️ Conservador (Jun)", f"R$ {receita_conserv:,.0f}", "Base")
            with col3:
                st.metric("🚀 Otimista (Jun)", f"R$ {receita_otim:,.0f}", 
                         f"{((receita_otim/receita_conserv)-1)*100:+.1f}%" if receita_conserv > 0 else "")


def pagina_simulador_dre():
    """Página de DRE Simulado - Formato Profissional"""
    render_header()
    # Badge no header
    
    st.markdown('<div class="section-header"><h3>📊 DRE - Demonstração do Resultado do Exercício</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    
    # Calcula DRE
    dre = motor.calcular_dre()
    
    # ========== CARDS DE RESUMO ==========
    # Calcular totais
    receita_bruta = sum(dre.get("Receita Bruta Total", [0]*12))
    
    # Encontrar imposto (pode ser Simples ou Carnê Leão)
    imposto_total = 0
    nome_imposto = "Impostos"
    for conta in dre.keys():
        if "Simples" in conta or "Carnê" in conta:
            imposto_total = abs(sum(dre[conta]))
            nome_imposto = conta.replace("(-) ", "")
            break
    
    receita_liquida = sum(dre.get("Receita Líquida", [0]*12))
    ebitda = sum(dre.get("EBITDA", [0]*12))
    resultado = sum(dre.get("Resultado Líquido", [0]*12))
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("📈 Receita Bruta", format_currency(receita_bruta), card_type="success")
    with col2:
        render_metric_card("💰 Receita Líquida", format_currency(receita_liquida), card_type="default")
    with col3:
        margem_ebitda = (ebitda / receita_bruta * 100) if receita_bruta > 0 else 0
        render_metric_card("📊 EBITDA", format_currency(ebitda), f"{margem_ebitda:.1f}%", card_type="warning")
    with col4:
        margem_liq = (resultado / receita_bruta * 100) if receita_bruta > 0 else 0
        card_type = "success" if resultado > 0 else "danger"
        render_metric_card("✅ Resultado", format_currency(resultado), f"{margem_liq:.1f}%", card_type=card_type)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Info do regime tributário
    regime = motor.premissas_folha.regime_tributario
    st.info(f"📋 **Regime Tributário:** {regime} | **{nome_imposto}:** {format_currency(imposto_total)}")
    
    st.markdown("---")
    
    # ========== TABS ==========
    tab1, tab2, tab3 = st.tabs(["📋 DRE Completo", "📊 Análise Gráfica", "📈 Evolução Mensal"])
    
    with tab1:
        # ========== DRE FORMATADO ==========
        
        # Monta HTML da tabela
        html = '<div style="max-height: 700px; overflow-y: auto;">'
        html += '<table style="width:100%; border-collapse:collapse; font-size:13px;">'
        
        # Header
        html += '<thead><tr style="background:#1a365d; color:white; position:sticky; top:0;">'
        html += '<th style="padding:10px 8px; text-align:left; font-weight:600; min-width:250px;">Conta</th>'
        for m in MESES_ABREV:
            html += f'<th style="padding:10px 8px; text-align:right; font-weight:600;">{m}</th>'
        html += '<th style="padding:10px 8px; text-align:right; font-weight:600; background:#0d2137;">TOTAL</th>'
        html += '</tr></thead>'
        html += '<tbody>'
        
        def format_val(v):
            """Formata valor com cor"""
            if v < 0:
                return f'<span style="color:#c53030;">({abs(v):,.2f})</span>'
            return f'{v:,.2f}'
        
        def get_row_style(conta):
            """Retorna style inline baseado na conta"""
            conta_lower = conta.lower()
            
            # Subtotais importantes
            if conta in ["Receita Bruta Total", "Receita Líquida", "Margem de Contribuição", 
                         "Total Deduções", "Total Custos Variáveis", "Subtotal Pessoal",
                         "Total Despesas Fixas", "Total Custos Fixos",
                         "Total Despesas Financeiras", "Total Receitas Financeiras", 
                         "Resultado Financeiro Líquido", "Resultado Antes IR"]:
                return "background:#edf2f7; font-weight:600; border-top:2px solid #cbd5e0;"
            
            # EBITDA
            elif conta == "EBITDA":
                return "background:#1a365d; color:white; font-weight:700; font-size:14px;"
            
            # Resultado Líquido (verde se positivo, vermelho se negativo)
            elif conta in ["Resultado Líquido", "Lucro no Período"]:
                total = sum(dre.get(conta, [0]*12))
                if total >= 0:
                    return "background:#38a169; color:white; font-weight:700; font-size:14px;"
                else:
                    return "background:#c53030; color:white; font-weight:700; font-size:14px;"
            
            # Receitas
            elif "(+)" in conta or conta in servicos_cadastrados:
                return "background:#f0fff4;"
            
            # Deduções
            elif "(-)" in conta:
                if "simples" in conta_lower or "carnê" in conta_lower or "taxa" in conta_lower:
                    return "background:#fff5f5;"
                elif "material" in conta_lower or "custo" in conta_lower:
                    return "background:#fffaf0;"
                elif "reserva" in conta_lower or "dividendo" in conta_lower:
                    return "background:#fef3f2;"
                else:
                    return "background:#fef3f2;"
            
            else:
                return "background:#f0fff4;"
        
        # Ordem das contas para exibição - SERVIÇOS DINÂMICOS
        servicos_cadastrados = list(motor.servicos.keys())
        
        ordem_contas = (
            # Receitas (serviços dinâmicos)
            servicos_cadastrados +
            [
            "Receita Bruta Total",
            # Deduções
            "(-) Simples Nacional", "(-) Carnê Leão (PF)", "(-) Taxa Cartão", "Total Deduções",
            "Receita Líquida",
            # Custos Variáveis - adicionados dinamicamente
            "Total Custos Variáveis",
            "Margem de Contribuição",
            # Custos Fixos - Pessoal (detalhado)
            "(-) Folha Fisioterapeutas", "(-) Folha Proprietários", "(-) Pró-Labore", "(-) Folha CLT + Encargos",
            "Subtotal Pessoal",
            # Despesas Operacionais - DINÂMICAS (apenas as que são FIXAS)
            "Total Despesas Fixas",
            "Total Custos Fixos",
            "EBITDA",
            # Resultado Financeiro
            "(+) Rendimentos Aplicações",
            "(-) Juros Novos Investimentos", "(-) Juros Financ. Existentes", "(-) Juros Cheque Especial",
            "Total Despesas Financeiras", "Total Receitas Financeiras",
            "Resultado Financeiro Líquido",
            "Resultado Antes IR",
            "Resultado Líquido",
            # Destinação dos Resultados (somente PJ)
            "(-) Reserva Legal", "(-) Reserva Investimentos", "(-) Dividendos Distribuídos",
            "Lucro no Período"
            ]
        )
        
        # Adiciona custos variáveis dinâmicos (antes de Total Custos Variáveis)
        custos_variaveis_dinamicos = [k for k in dre.keys() if k.startswith("(-)") and k in [f"(-) {nome}" for nome in motor.custos.keys() if nome != "Total Custos Variáveis"]]
        
        # Adiciona despesas fixas dinâmicas (antes de Total Despesas Fixas)
        despesas_fixas_dinamicas = [f"(-) {nome}" for nome, desp in motor.despesas_fixas.items() if desp.ativa and desp.tipo_despesa == "fixa"]
        
        # Filtra contas que existem e adiciona separadores
        secao_atual = None
        primeiro_cv = True  # Flag para identificar primeiro custo variável
        primeiro_df = True  # Flag para identificar primeira despesa fixa
        for conta in ordem_contas:
            # Se for Total Custos Variáveis, insere os CVs dinâmicos antes
            if conta == "Total Custos Variáveis":
                for cv in custos_variaveis_dinamicos:
                    if cv in dre:
                        valores = dre[cv]
                        total = sum(valores)
                        
                        # Cabeçalho da seção apenas no primeiro CV
                        if primeiro_cv:
                            html += '<tr><td colspan="14" style="background:#2c5282;color:white;font-weight:700;padding:6px 8px;">▸ CUSTOS VARIÁVEIS</td></tr>'
                            secao_atual = "CUSTOS VARIÁVEIS"
                            primeiro_cv = False
                        
                        row_style = get_row_style(cv)
                        nome_conta = "&nbsp;&nbsp;&nbsp;" + cv
                        
                        valores_html = ""
                        for v in valores:
                            valores_html += f'<td style="padding:8px; text-align:right; border-bottom:1px solid #e2e8f0;">{format_val(v)}</td>'
                        
                        total_html = format_val(total)
                        html += f'<tr style="{row_style}"><td style="padding:8px; text-align:left; border-bottom:1px solid #e2e8f0;">{nome_conta}</td>{valores_html}<td style="padding:8px; text-align:right; border-bottom:1px solid #e2e8f0;"><strong>{total_html}</strong></td></tr>'
            
            # Se for Total Despesas Fixas, insere as despesas fixas dinâmicas antes
            if conta == "Total Despesas Fixas":
                for df in despesas_fixas_dinamicas:
                    if df in dre:
                        valores = dre[df]
                        total = sum(valores)
                        
                        # Cabeçalho da seção apenas na primeira despesa fixa
                        if primeiro_df:
                            html += '<tr><td colspan="14" style="background:#2c5282;color:white;font-weight:700;padding:6px 8px;">▸ DESPESAS OPERACIONAIS</td></tr>'
                            secao_atual = "DESPESAS OPERACIONAIS"
                            primeiro_df = False
                        
                        row_style = get_row_style(df)
                        nome_conta = "&nbsp;&nbsp;&nbsp;" + df
                        
                        valores_html = ""
                        for v in valores:
                            valores_html += f'<td style="padding:8px; text-align:right; border-bottom:1px solid #e2e8f0;">{format_val(v)}</td>'
                        
                        total_html = format_val(total)
                        html += f'<tr style="{row_style}"><td style="padding:8px; text-align:left; border-bottom:1px solid #e2e8f0;">{nome_conta}</td>{valores_html}<td style="padding:8px; text-align:right; border-bottom:1px solid #e2e8f0;"><strong>{total_html}</strong></td></tr>'
            
            if conta not in dre:
                continue
            
            valores = dre[conta]
            total = sum(valores)
            
            # Adiciona separador de seção
            nova_secao = None
            # Verifica se é o primeiro serviço (para iniciar seção RECEITA BRUTA)
            if conta in servicos_cadastrados and conta == servicos_cadastrados[0]:
                nova_secao = "RECEITA BRUTA"
            elif conta in ["(-) Simples Nacional", "(-) Carnê Leão (PF)"]:
                nova_secao = "DEDUÇÕES"
            # CUSTOS VARIÁVEIS e DESPESAS OPERACIONAIS são tratados nos loops acima
            elif conta == "(-) Folha Fisioterapeutas":
                nova_secao = "CUSTOS DE PESSOAL"
            elif conta in ["(+) Rendimentos Aplicações", "(-) Juros Novos Investimentos"]:
                nova_secao = "RESULTADO FINANCEIRO"
            elif conta == "(-) Reserva Legal":
                nova_secao = "DESTINAÇÃO DOS RESULTADOS"
            
            if nova_secao and nova_secao != secao_atual:
                secao_atual = nova_secao
                html += f'<tr><td colspan="14" style="background:#2c5282;color:white;font-weight:700;padding:6px 8px;">▸ {nova_secao}</td></tr>'
            
            row_style = get_row_style(conta)
            
            # Formata nome da conta
            nome_conta = conta
            if conta.startswith("(-)"):
                nome_conta = "&nbsp;&nbsp;&nbsp;" + conta
            
            # Valores mensais
            valores_html = ""
            for v in valores:
                valores_html += f'<td style="padding:8px; text-align:right; border-bottom:1px solid #e2e8f0;">{format_val(v)}</td>'
            
            total_html = format_val(total)
            
            html += f'<tr style="{row_style}"><td style="padding:8px; text-align:left; border-bottom:1px solid #e2e8f0;">{nome_conta}</td>{valores_html}<td style="padding:8px; text-align:right; border-bottom:1px solid #e2e8f0;"><strong>{total_html}</strong></td></tr>'
        
        html += """
        </tbody>
        </table>
        </div>
        """
        
        st.markdown(html, unsafe_allow_html=True)
        
        # Legenda
        st.markdown("""
        <div style="margin-top: 15px; font-size: 12px; color: #718096;">
            <span style="display:inline-block;width:12px;height:12px;background:#f0fff4;border:1px solid #ccc;margin-right:5px;"></span> Receitas
            <span style="display:inline-block;width:12px;height:12px;background:#fff5f5;border:1px solid #ccc;margin-right:5px;margin-left:15px;"></span> Deduções
            <span style="display:inline-block;width:12px;height:12px;background:#fffaf0;border:1px solid #ccc;margin-right:5px;margin-left:15px;"></span> Custos
            <span style="display:inline-block;width:12px;height:12px;background:#fef3f2;border:1px solid #ccc;margin-right:5px;margin-left:15px;"></span> Despesas
            <span style="display:inline-block;width:12px;height:12px;background:#edf2f7;border:1px solid #ccc;margin-right:5px;margin-left:15px;"></span> Subtotais
        </div>
        """, unsafe_allow_html=True)
    
    with tab2:
        # ========== ANÁLISE GRÁFICA ==========
        st.markdown("#### 📊 Composição do Resultado")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de Waterfall
            custos_variaveis = abs(sum(dre.get("Total Custos Variáveis", [0]*12)))
            custos_fixos = abs(sum(dre.get("Total Custos Fixos", [0]*12)))
            deducoes_total = abs(sum(dre.get("Total Deduções", [0]*12)))
            
            fig_waterfall = go.Figure(go.Waterfall(
                name="DRE",
                orientation="v",
                x=["Receita Bruta", "Deduções", "Custos Variáveis", "Custos Fixos", "Resultado"],
                y=[receita_bruta, -deducoes_total, -custos_variaveis, -custos_fixos, resultado],
                connector={"line": {"color": "rgb(63, 63, 63)"}},
                decreasing={"marker": {"color": "#c53030"}},
                increasing={"marker": {"color": "#38a169"}},
                totals={"marker": {"color": "#2c5282"}}
            ))
            fig_waterfall.update_layout(
                title="Formação do Resultado",
                height=400,
                showlegend=False
            )
            st.plotly_chart(fig_waterfall, use_container_width=True)
        
        with col2:
            # Pizza de despesas
            despesas_lista = []
            for conta, valores in dre.items():
                if conta.startswith("(-)") and "Total" not in conta and "Custo de Pessoal" not in conta:
                    despesas_lista.append({
                        "Despesa": conta.replace("(-) ", ""),
                        "Valor": abs(sum(valores))
                    })
            
            if despesas_lista:
                df_desp = pd.DataFrame(despesas_lista)
                df_desp = df_desp[df_desp["Valor"] > 0].sort_values("Valor", ascending=False)
                
                fig_pizza = px.pie(
                    df_desp,
                    values="Valor",
                    names="Despesa",
                    title="Composição das Despesas",
                    hole=0.4
                )
                fig_pizza.update_layout(height=400)
                st.plotly_chart(fig_pizza, use_container_width=True)
        
        # Indicadores
        st.markdown("#### 📈 Indicadores de Performance")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        margem_bruta = ((receita_bruta - deducoes_total) / receita_bruta * 100) if receita_bruta > 0 else 0
        margem_contrib = (sum(dre.get("Margem de Contribuição", [0]*12)) / receita_bruta * 100) if receita_bruta > 0 else 0
        margem_ebitda = (ebitda / receita_bruta * 100) if receita_bruta > 0 else 0
        margem_liquida = (resultado / receita_bruta * 100) if receita_bruta > 0 else 0
        
        with col1:
            st.metric("Margem Bruta", f"{margem_bruta:.1f}%")
        with col2:
            st.metric("Margem Contribuição", f"{margem_contrib:.1f}%")
        with col3:
            st.metric("Margem EBITDA", f"{margem_ebitda:.1f}%")
        with col4:
            st.metric("Margem Líquida", f"{margem_liquida:.1f}%")
        with col5:
            ticket_medio = receita_bruta / 12
            st.metric("Ticket Médio/Mês", format_currency(ticket_medio))
    
    with tab3:
        # ========== EVOLUÇÃO MENSAL ==========
        st.markdown("#### 📈 Evolução Mensal")
        
        # Gráfico de evolução
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Receita Bruta',
            x=MESES_ABREV,
            y=dre.get("Receita Bruta Total", [0]*12),
            marker_color='#38a169'
        ))
        
        fig.add_trace(go.Bar(
            name='Custos + Despesas',
            x=MESES_ABREV,
            y=[-abs(v) for v in dre.get("Total Custos Fixos", [0]*12)],
            marker_color='#c53030'
        ))
        
        fig.add_trace(go.Scatter(
            name='Resultado',
            x=MESES_ABREV,
            y=dre.get("Resultado Líquido", [0]*12),
            mode='lines+markers',
            line=dict(color='#2c5282', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            barmode='relative',
            height=400,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis2=dict(title='Resultado', overlaying='y', side='right')
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Tabela resumida mensal
        st.markdown("#### 📊 Resumo Mensal")
        
        df_resumo = pd.DataFrame({
            'Mês': MESES_ABREV,
            'Receita Bruta': dre.get("Receita Bruta Total", [0]*12),
            'Deduções': [abs(v) for v in dre.get("Total Deduções", [0]*12)],
            'Receita Líquida': dre.get("Receita Líquida", [0]*12),
            'Custos Fixos': [abs(v) for v in dre.get("Total Custos Fixos", [0]*12)],
            'EBITDA': dre.get("EBITDA", [0]*12),
            'Margem %': [(e/r*100) if r > 0 else 0 for e, r in zip(dre.get("EBITDA", [0]*12), dre.get("Receita Bruta Total", [0]*12))]
        })
        
        # Linha de total
        total_row = pd.DataFrame([{
            'Mês': 'TOTAL',
            'Receita Bruta': df_resumo['Receita Bruta'].sum(),
            'Deduções': df_resumo['Deduções'].sum(),
            'Receita Líquida': df_resumo['Receita Líquida'].sum(),
            'Custos Fixos': df_resumo['Custos Fixos'].sum(),
            'EBITDA': df_resumo['EBITDA'].sum(),
            'Margem %': (df_resumo['EBITDA'].sum() / df_resumo['Receita Bruta'].sum() * 100) if df_resumo['Receita Bruta'].sum() > 0 else 0
        }])
        df_resumo = pd.concat([df_resumo, total_row], ignore_index=True)
        
        st.dataframe(
            df_resumo.style.format({
                'Receita Bruta': 'R$ {:,.2f}',
                'Deduções': 'R$ {:,.2f}',
                'Receita Líquida': 'R$ {:,.2f}',
                'Custos Fixos': 'R$ {:,.2f}',
                'EBITDA': 'R$ {:,.2f}',
                'Margem %': '{:.1f}%'
            }),
            use_container_width=True,
            hide_index=True
        )


def pagina_atendimentos():
    """Página de Evolução de Atendimentos e Faturamento"""
    render_header()
    # Badge no header
    
    st.markdown('<div class="section-header"><h3>📈 Painel de Atendimentos e Faturamento</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    
    # Sincroniza proprietários entre todas as estruturas
    motor.sincronizar_proprietarios()
    
    # Abas
    tab1, tab2, tab3 = st.tabs(["👔 Proprietários", "🩺 Profissionais", "📊 Consolidado"])
    
    # ========== PROPRIETÁRIOS ==========
    with tab1:
        st.markdown("### 👔 Evolução - Proprietários")
        
        if not motor.proprietarios:
            st.info("Nenhum proprietário cadastrado. Vá em Premissas → Equipe para cadastrar.")
        else:
            # Tabela de sessões por proprietário
            st.markdown("#### 📅 Sessões por Mês")
            
            dados_sessoes = []
            for prop_nome, prop in motor.proprietarios.items():
                row = {'Profissional': f"👔 {prop_nome}"}
                total_ano = 0
                
                for mes_idx, mes in enumerate(MESES_ABREV):
                    sessoes_mes = 0
                    for servico, qtd_base in prop.sessoes_por_servico.items():
                        pct_cresc = prop.pct_crescimento_por_servico.get(servico, 0.105)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes_mes += qtd_base + cresc_mensal * (mes_idx + 0.944)
                    
                    row[mes] = round(sessoes_mes, 2)
                    total_ano += sessoes_mes
                
                row['Total Ano'] = round(total_ano, 2)
                dados_sessoes.append(row)
            
            if dados_sessoes:
                st.dataframe(pd.DataFrame(dados_sessoes), use_container_width=True, hide_index=True)
            
            # Tabela de faturamento por proprietário
            st.markdown("#### 💰 Faturamento por Mês")
            
            dados_faturamento = []
            for prop_nome, prop in motor.proprietarios.items():
                row = {'Profissional': f"👔 {prop_nome}"}
                total_ano = 0
                
                for mes_idx, mes in enumerate(MESES_ABREV):
                    faturamento_mes = 0
                    
                    for servico, qtd_base in prop.sessoes_por_servico.items():
                        # Calcula sessões
                        pct_cresc = prop.pct_crescimento_por_servico.get(servico, 0.105)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                        
                        # Calcula valor (antes/depois do reajuste)
                        valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'proprietario')
                        faturamento_mes += sessoes * valor
                    
                    row[mes] = format_currency(faturamento_mes, prefix="")
                    total_ano += faturamento_mes
                
                row['Total Ano'] = format_currency(total_ano, prefix="")
                dados_faturamento.append(row)
            
            if dados_faturamento:
                st.dataframe(pd.DataFrame(dados_faturamento), use_container_width=True, hide_index=True)
            
            # Tabela de ticket médio por proprietário
            st.markdown("#### 🎫 Ticket Médio por Mês")
            st.caption("Faturamento ÷ Sessões = Valor médio por atendimento")
            
            dados_ticket = []
            for prop_nome, prop in motor.proprietarios.items():
                row = {'Profissional': f"👔 {prop_nome}"}
                total_faturamento = 0
                total_sessoes = 0
                
                for mes_idx, mes in enumerate(MESES_ABREV):
                    faturamento_mes = 0
                    sessoes_mes = 0
                    
                    for servico, qtd_base in prop.sessoes_por_servico.items():
                        # Calcula sessões
                        pct_cresc = prop.pct_crescimento_por_servico.get(servico, 0.105)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                        sessoes_mes += sessoes
                        
                        # Calcula valor (antes/depois do reajuste)
                        valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'proprietario')
                        faturamento_mes += sessoes * valor
                    
                    ticket = faturamento_mes / sessoes_mes if sessoes_mes > 0 else 0
                    row[mes] = format_currency(ticket, prefix="")
                    total_faturamento += faturamento_mes
                    total_sessoes += sessoes_mes
                
                ticket_medio_ano = total_faturamento / total_sessoes if total_sessoes > 0 else 0
                row['Média Ano'] = format_currency(ticket_medio_ano, prefix="")
                dados_ticket.append(row)
            
            if dados_ticket:
                st.dataframe(pd.DataFrame(dados_ticket), use_container_width=True, hide_index=True)
            
            # Gráfico de evolução
            st.markdown("#### 📈 Gráfico de Evolução")
            
            fig = go.Figure()
            for prop_nome, prop in motor.proprietarios.items():
                valores_mes = []
                
                for mes_idx in range(12):
                    faturamento_mes = 0
                    for servico, qtd_base in prop.sessoes_por_servico.items():
                        pct_cresc = prop.pct_crescimento_por_servico.get(servico, 0.105)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                        valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'proprietario')
                        faturamento_mes += sessoes * valor
                    valores_mes.append(faturamento_mes)
                
                fig.add_trace(go.Scatter(
                    x=MESES_ABREV,
                    y=valores_mes,
                    mode='lines+markers',
                    name=prop_nome
                ))
            
            fig.update_layout(
                title="Faturamento Mensal - Proprietários",
                xaxis_title="Mês",
                yaxis_title="R$",
                plot_bgcolor='rgba(0,0,0,0)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # ========== PROFISSIONAIS ==========
    with tab2:
        st.markdown("### 🩺 Evolução - Profissionais")
        
        if not motor.profissionais:
            st.info("Nenhum profissional cadastrado. Vá em Premissas → Equipe para cadastrar.")
        else:
            # Filtro de profissional
            profs_ativos = [n for n, p in motor.profissionais.items() if sum(p.sessoes_por_servico.values()) > 0]
            
            prof_selecionado = st.selectbox(
                "Selecione o Profissional",
                ["Todos"] + profs_ativos,
                key="filtro_prof"
            )
            
            # Tabela de sessões
            st.markdown("#### 📅 Sessões por Mês")
            
            dados_sessoes = []
            profs_mostrar = motor.profissionais.items() if prof_selecionado == "Todos" else [(prof_selecionado, motor.profissionais[prof_selecionado])]
            
            for prof_nome, prof in profs_mostrar:
                if sum(prof.sessoes_por_servico.values()) == 0:
                    continue
                    
                row = {'Profissional': f"🩺 {prof_nome}"}
                total_ano = 0
                
                for mes_idx, mes in enumerate(MESES_ABREV):
                    sessoes_mes = 0
                    for servico, qtd_base in prof.sessoes_por_servico.items():
                        pct_cresc = prof.pct_crescimento_por_servico.get(servico, 0.05)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes_mes += qtd_base + cresc_mensal * (mes_idx + 0.944)
                    row[mes] = round(sessoes_mes, 2)
                    total_ano += sessoes_mes
                
                row['Total Ano'] = round(total_ano, 2)
                dados_sessoes.append(row)
            
            # Linha de total
            if len(dados_sessoes) > 1:
                row_total = {'Profissional': '📊 TOTAL'}
                for mes in MESES_ABREV:
                    row_total[mes] = round(sum(r[mes] for r in dados_sessoes), 2)
                row_total['Total Ano'] = round(sum(r['Total Ano'] for r in dados_sessoes), 2)
                dados_sessoes.append(row_total)
            
            if dados_sessoes:
                st.dataframe(pd.DataFrame(dados_sessoes), use_container_width=True, hide_index=True)
            
            # Tabela de faturamento
            st.markdown("#### 💰 Faturamento por Mês")
            
            dados_faturamento = []
            
            for prof_nome, prof in profs_mostrar:
                if sum(prof.sessoes_por_servico.values()) == 0:
                    continue
                    
                row = {'Profissional': f"🩺 {prof_nome}"}
                total_ano = 0
                valores_numericos = []
                
                for mes_idx, mes in enumerate(MESES_ABREV):
                    faturamento_mes = 0
                    for servico, qtd_base in prof.sessoes_por_servico.items():
                        # Calcula sessões com crescimento linear
                        pct_cresc = prof.pct_crescimento_por_servico.get(servico, 0.05)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                        
                        # Calcula valor (antes/depois do reajuste)
                        valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'profissional')
                        faturamento_mes += sessoes * valor
                    
                    row[mes] = format_currency(faturamento_mes, prefix="")
                    valores_numericos.append(faturamento_mes)
                    total_ano += faturamento_mes
                
                row['Total Ano'] = format_currency(total_ano, prefix="")
                row['_valores'] = valores_numericos
                row['_total'] = total_ano
                dados_faturamento.append(row)
            
            # Linha de total
            if len(dados_faturamento) > 1:
                row_total = {'Profissional': '📊 TOTAL'}
                for i, mes in enumerate(MESES_ABREV):
                    total_mes = sum(r['_valores'][i] for r in dados_faturamento)
                    row_total[mes] = format_currency(total_mes, prefix="")
                row_total['Total Ano'] = format_currency(sum(r['_total'] for r in dados_faturamento), prefix="")
                dados_faturamento.append(row_total)
            
            # Remove colunas auxiliares
            for r in dados_faturamento:
                r.pop('_valores', None)
                r.pop('_total', None)
            
            if dados_faturamento:
                st.dataframe(pd.DataFrame(dados_faturamento), use_container_width=True, hide_index=True)
            
            # Tabela de ticket médio
            st.markdown("#### 🎫 Ticket Médio por Mês")
            st.caption("Faturamento ÷ Sessões = Valor médio por atendimento")
            
            dados_ticket = []
            totais_ticket = {'faturamento': [0]*12, 'sessoes': [0]*12}
            
            for prof_nome, prof in profs_mostrar:
                if sum(prof.sessoes_por_servico.values()) == 0:
                    continue
                    
                row = {'Profissional': f"🩺 {prof_nome}"}
                total_faturamento = 0
                total_sessoes = 0
                
                for mes_idx, mes in enumerate(MESES_ABREV):
                    faturamento_mes = 0
                    sessoes_mes = 0
                    
                    for servico, qtd_base in prof.sessoes_por_servico.items():
                        # Calcula sessões com crescimento linear
                        pct_cresc = prof.pct_crescimento_por_servico.get(servico, 0.05)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                        sessoes_mes += sessoes
                        
                        # Calcula valor (antes/depois do reajuste)
                        valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'profissional')
                        faturamento_mes += sessoes * valor
                    
                    ticket = faturamento_mes / sessoes_mes if sessoes_mes > 0 else 0
                    row[mes] = format_currency(ticket, prefix="")
                    total_faturamento += faturamento_mes
                    total_sessoes += sessoes_mes
                    totais_ticket['faturamento'][mes_idx] += faturamento_mes
                    totais_ticket['sessoes'][mes_idx] += sessoes_mes
                
                ticket_medio_ano = total_faturamento / total_sessoes if total_sessoes > 0 else 0
                row['Média Ano'] = format_currency(ticket_medio_ano, prefix="")
                dados_ticket.append(row)
            
            # Linha de média geral
            if len(dados_ticket) > 1:
                row_media = {'Profissional': '📊 MÉDIA GERAL'}
                for i, mes in enumerate(MESES_ABREV):
                    ticket_geral = totais_ticket['faturamento'][i] / totais_ticket['sessoes'][i] if totais_ticket['sessoes'][i] > 0 else 0
                    row_media[mes] = format_currency(ticket_geral, prefix="")
                ticket_ano = sum(totais_ticket['faturamento']) / sum(totais_ticket['sessoes']) if sum(totais_ticket['sessoes']) > 0 else 0
                row_media['Média Ano'] = format_currency(ticket_ano, prefix="")
                dados_ticket.append(row_media)
            
            if dados_ticket:
                st.dataframe(pd.DataFrame(dados_ticket), use_container_width=True, hide_index=True)
            
            # Gráfico
            st.markdown("#### 📈 Gráfico de Evolução")
            
            fig = go.Figure()
            
            for prof_nome, prof in profs_mostrar:
                if sum(prof.sessoes_por_servico.values()) == 0:
                    continue
                    
                valores_mes = []
                for mes_idx in range(12):
                    faturamento_mes = 0
                    for servico, qtd_base in prof.sessoes_por_servico.items():
                        pct_cresc = prof.pct_crescimento_por_servico.get(servico, 0.05)
                        crescimento_qtd = qtd_base * pct_cresc
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                        valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'profissional')
                        faturamento_mes += sessoes * valor
                    valores_mes.append(faturamento_mes)
                
                fig.add_trace(go.Scatter(
                    x=MESES_ABREV,
                    y=valores_mes,
                    mode='lines+markers',
                    name=prof_nome
                ))
            
            fig.update_layout(
                title="Faturamento Mensal - Profissionais",
                xaxis_title="Mês",
                yaxis_title="R$",
                plot_bgcolor='rgba(0,0,0,0)',
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # ========== CONSOLIDADO ==========
    with tab3:
        st.markdown("### 📊 Visão Consolidada")
        
        # Calcula totais
        dados_consolidado = []
        
        # Linha Proprietários
        row_prop = {'Categoria': '👔 Proprietários'}
        total_prop = 0
        for mes_idx, mes in enumerate(MESES_ABREV):
            faturamento_mes = 0
            for prop in motor.proprietarios.values():
                for servico, qtd_base in prop.sessoes_por_servico.items():
                    pct_cresc = prop.pct_crescimento_por_servico.get(servico, 0.105)
                    crescimento_qtd = qtd_base * pct_cresc
                    cresc_mensal = crescimento_qtd / 13.1
                    sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                    # APLICA SAZONALIDADE
                    fator_saz = motor.sazonalidade.fatores[mes_idx] if hasattr(motor, 'sazonalidade') else 1.0
                    sessoes = sessoes * fator_saz
                    valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'proprietario')
                    faturamento_mes += sessoes * valor
            row_prop[mes] = faturamento_mes
            total_prop += faturamento_mes
        row_prop['Total Ano'] = total_prop
        dados_consolidado.append(row_prop)
        
        # Linha Profissionais
        row_prof = {'Categoria': '🩺 Profissionais'}
        total_prof = 0
        for mes_idx, mes in enumerate(MESES_ABREV):
            faturamento_mes = 0
            for prof in motor.profissionais.values():
                for servico, qtd_base in prof.sessoes_por_servico.items():
                    pct_cresc = prof.pct_crescimento_por_servico.get(servico, 0.05)
                    crescimento_qtd = qtd_base * pct_cresc
                    cresc_mensal = crescimento_qtd / 13.1
                    sessoes = qtd_base + cresc_mensal * (mes_idx + 0.944)
                    # APLICA SAZONALIDADE
                    fator_saz = motor.sazonalidade.fatores[mes_idx] if hasattr(motor, 'sazonalidade') else 1.0
                    sessoes = sessoes * fator_saz
                    valor = motor.calcular_valor_servico_mes(servico, mes_idx, 'profissional')
                    faturamento_mes += sessoes * valor
            row_prof[mes] = faturamento_mes
            total_prof += faturamento_mes
        row_prof['Total Ano'] = total_prof
        dados_consolidado.append(row_prof)
        
        # Linha Total
        row_total = {'Categoria': '📊 TOTAL GERAL'}
        for mes in MESES_ABREV:
            row_total[mes] = row_prop[mes] + row_prof[mes]
        row_total['Total Ano'] = total_prop + total_prof
        dados_consolidado.append(row_total)
        
        # Formata para exibição
        df_consolidado = pd.DataFrame(dados_consolidado)
        for col in df_consolidado.columns[1:]:
            df_consolidado[col] = df_consolidado[col].apply(lambda x: format_currency(x, prefix=""))
        
        st.dataframe(df_consolidado, use_container_width=True, hide_index=True)
        
        # Gráfico comparativo
        st.markdown("#### 📈 Comparativo Proprietários x Profissionais")
        
        fig = go.Figure()
        
        # Valores proprietários
        valores_prop = [row_prop[mes] for mes in MESES_ABREV]
        valores_prof = [row_prof[mes] for mes in MESES_ABREV]
        
        fig.add_trace(go.Bar(
            x=MESES_ABREV,
            y=valores_prop,
            name='Proprietários',
            marker_color='#1e3a5f'
        ))
        
        fig.add_trace(go.Bar(
            x=MESES_ABREV,
            y=valores_prof,
            name='Profissionais',
            marker_color='#38a169'
        ))
        
        fig.update_layout(
            title="Faturamento Mensal - Proprietários x Profissionais",
            xaxis_title="Mês",
            yaxis_title="R$",
            barmode='stack',
            plot_bgcolor='rgba(0,0,0,0)',
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # KPIs
        st.markdown("#### 📊 Resumo")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            pct_prop = (total_prop / (total_prop + total_prof) * 100) if (total_prop + total_prof) > 0 else 0
            st.metric("% Proprietários", f"{pct_prop:.1f}%")
        
        with col2:
            pct_prof = (total_prof / (total_prop + total_prof) * 100) if (total_prop + total_prof) > 0 else 0
            st.metric("% Profissionais", f"{pct_prof:.1f}%")
        
        with col3:
            total_sessoes_prop = sum(sum(p.sessoes_por_servico.values()) for p in motor.proprietarios.values()) * 12
            total_sessoes_prof = sum(sum(p.sessoes_por_servico.values()) for p in motor.profissionais.values()) * 12
            st.metric("Total Sessões/Ano", f"{int(total_sessoes_prop + total_sessoes_prof):,}")
        
        with col4:
            ticket_medio = (total_prop + total_prof) / (total_sessoes_prop + total_sessoes_prof) if (total_sessoes_prop + total_sessoes_prof) > 0 else 0
            st.metric("Ticket Médio", format_currency(ticket_medio))


# ============================================
# PÁGINA FOLHA FUNCIONÁRIOS
# ============================================

def pagina_folha_funcionarios():
    """Página de Resumo da Folha de Funcionários"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>👔 Folha de Pagamento - Funcionários</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    pf = motor.premissas_folha
    
    # Calcular projeção anual
    projecao = []
    for mes in range(1, 13):
        folha = motor.calcular_folha_mes(mes)
        projecao.append({
            'mes': MESES[mes-1],
            'salarios_clt': folha['clt']['salarios_brutos'],
            'salarios_inf': folha['informal']['salarios_brutos'],
            'inss': folha['clt']['inss'] + folha['prolabore']['inss'],
            'irrf': folha['clt']['irrf'] + folha['prolabore']['irrf'],
            'fgts': folha['clt']['fgts'],
            'provisao_13': folha['clt']['provisao_13'],
            'provisao_ferias': folha['clt']['provisao_ferias'],
            'prolabore': folha['prolabore']['bruto'],
            'total_sal': folha['clt']['salarios_brutos'] + folha['informal']['salarios_brutos'],
            'total_encargos': folha['clt']['fgts'] + folha['clt']['provisao_13'] + folha['clt']['provisao_ferias'],
        })
    
    # Totais anuais
    total_sal = sum(p['total_sal'] for p in projecao)
    total_encargos = sum(p['total_encargos'] for p in projecao)
    total_prolabore = sum(p['prolabore'] for p in projecao)
    total_inss = sum(p['inss'] for p in projecao)
    total_fgts = sum(p['fgts'] for p in projecao)
    total_geral = total_sal + total_encargos + total_prolabore
    
    # Cards de resumo
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("👥 Salários (Anual)", format_currency(total_sal), card_type="default")
    with col2:
        render_metric_card("📋 Encargos CLT", format_currency(total_encargos), card_type="warning")
    with col3:
        render_metric_card("👔 Pró-Labore", format_currency(total_prolabore), card_type="default")
    with col4:
        render_metric_card("💰 TOTAL GERAL", format_currency(total_geral), card_type="success")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Segunda linha de cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_clt = len([f for f in motor.funcionarios_clt.values() if f.tipo_vinculo == "clt" and f.ativo])
        st.metric("Funcionários CLT", n_clt)
    with col2:
        n_inf = len([f for f in motor.funcionarios_clt.values() if f.tipo_vinculo == "informal" and f.ativo])
        st.metric("Informais", n_inf)
    with col3:
        n_socios = len([s for s in motor.socios_prolabore.values() if s.ativo])
        st.metric("Sócios", n_socios)
    with col4:
        st.metric("INSS Total (Anual)", format_currency(total_inss))
    
    st.markdown("---")
    
    # ===== TABELA POR FUNCIONÁRIO MÊS A MÊS =====
    st.markdown("#### 👥 Remuneração por Funcionário (Mês a Mês)")
    st.caption("💡 Apenas CLT tem encargos (FGTS, 13º, Férias). Informais recebem apenas salário.")
    
    # Construir dados por funcionário
    dados_funcionarios = []
    
    for nome, func in motor.funcionarios_clt.items():
        if not func.ativo:
            continue
        
        salarios_mes = []
        for mes in range(1, 13):
            # Salário com dissídio
            salario = func.salario_base
            if mes >= pf.mes_dissidio:
                salario = salario * (1 + pf.pct_dissidio)
            salarios_mes.append(salario)
        
        dados_funcionarios.append({
            'Nome': nome,
            'Cargo': func.cargo or '-',
            'Vínculo': func.tipo_vinculo.upper(),
            'Sal. Base': func.salario_base,
            **{MESES[i]: salarios_mes[i] for i in range(12)},
            'TOTAL': sum(salarios_mes)
        })
    
    # Adicionar sócios (pró-labore)
    for nome, socio in motor.socios_prolabore.items():
        if not socio.ativo:
            continue
        
        prolabore_mes = []
        for mes in range(1, 13):
            pl = socio.prolabore
            if mes >= socio.mes_reajuste:
                pl = pl * (1 + pf.pct_dissidio)
            prolabore_mes.append(pl)
        
        dados_funcionarios.append({
            'Nome': nome,
            'Cargo': 'Sócio',
            'Vínculo': 'PRÓ-LABORE',
            'Sal. Base': socio.prolabore,
            **{MESES[i]: prolabore_mes[i] for i in range(12)},
            'TOTAL': sum(prolabore_mes)
        })
    
    if dados_funcionarios:
        df_func = pd.DataFrame(dados_funcionarios)
        
        # Ordenar por vínculo (CLT primeiro, depois Informal, depois PL)
        ordem_vinculo = {'CLT': 0, 'INFORMAL': 1, 'PRÓ-LABORE': 2}
        df_func['_ordem'] = df_func['Vínculo'].map(ordem_vinculo)
        df_func = df_func.sort_values('_ordem').drop('_ordem', axis=1)
        
        # Linha de total
        total_row = {'Nome': 'TOTAL', 'Cargo': '', 'Vínculo': '', 'Sal. Base': df_func['Sal. Base'].sum()}
        for mes in MESES:
            total_row[mes] = df_func[mes].sum()
        total_row['TOTAL'] = df_func['TOTAL'].sum()
        
        df_func = pd.concat([df_func, pd.DataFrame([total_row])], ignore_index=True)
        
        # Formatação
        format_dict = {'Sal. Base': 'R$ {:,.2f}', 'TOTAL': 'R$ {:,.2f}'}
        for mes in MESES:
            format_dict[mes] = 'R$ {:,.2f}'
        
        st.dataframe(
            df_func.style.format(format_dict),
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        # Resumo por tipo de vínculo
        st.markdown("##### 📊 Resumo por Tipo de Vínculo")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            total_clt = sum(f.salario_base for f in motor.funcionarios_clt.values() if f.ativo and f.tipo_vinculo == "clt")
            n_clt = len([f for f in motor.funcionarios_clt.values() if f.ativo and f.tipo_vinculo == "clt"])
            st.metric(f"👔 CLT ({n_clt})", format_currency(total_clt * 12.48))  # com dissídio
        
        with col2:
            total_inf = sum(f.salario_base for f in motor.funcionarios_clt.values() if f.ativo and f.tipo_vinculo == "informal")
            n_inf = len([f for f in motor.funcionarios_clt.values() if f.ativo and f.tipo_vinculo == "informal"])
            st.metric(f"📋 Informal ({n_inf})", format_currency(total_inf * 12.48))
        
        with col3:
            total_pl = sum(s.prolabore for s in motor.socios_prolabore.values() if s.ativo)
            n_pl = len([s for s in motor.socios_prolabore.values() if s.ativo])
            st.metric(f"💼 Pró-Labore ({n_pl})", format_currency(total_pl * 12.48))
        
    else:
        st.info("Nenhum funcionário cadastrado.")
    
    st.markdown("---")
    
    # Gráfico de evolução mensal
    st.markdown("#### 📈 Evolução Mensal (Totais)")
    
    df_chart = pd.DataFrame(projecao)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Salários', x=df_chart['mes'], y=df_chart['total_sal'], marker_color='#3498db'))
    fig.add_trace(go.Bar(name='Encargos', x=df_chart['mes'], y=df_chart['total_encargos'], marker_color='#e74c3c'))
    fig.add_trace(go.Bar(name='Pró-Labore', x=df_chart['mes'], y=df_chart['prolabore'], marker_color='#2ecc71'))
    
    fig.update_layout(
        barmode='stack',
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Tabela resumo mensal
    st.markdown("#### 📊 Resumo Mensal (Encargos)")
    
    df_tabela = pd.DataFrame([{
        'Mês': p['mes'],
        'Salários CLT': p['salarios_clt'],
        'Salários Inf.': p['salarios_inf'],
        'FGTS': p['fgts'],
        'Prov. 13º': p['provisao_13'],
        'Prov. Férias': p['provisao_ferias'],
        'Pró-Labore': p['prolabore'],
        'INSS': p['inss'],
        'TOTAL': p['total_sal'] + p['total_encargos'] + p['prolabore']
    } for p in projecao])
    
    # Linha de total
    total_row = pd.DataFrame([{
        'Mês': 'TOTAL',
        'Salários CLT': df_tabela['Salários CLT'].sum(),
        'Salários Inf.': df_tabela['Salários Inf.'].sum(),
        'FGTS': df_tabela['FGTS'].sum(),
        'Prov. 13º': df_tabela['Prov. 13º'].sum(),
        'Prov. Férias': df_tabela['Prov. Férias'].sum(),
        'Pró-Labore': df_tabela['Pró-Labore'].sum(),
        'INSS': df_tabela['INSS'].sum(),
        'TOTAL': df_tabela['TOTAL'].sum()
    }])
    df_tabela = pd.concat([df_tabela, total_row], ignore_index=True)
    
    st.dataframe(
        df_tabela.style.format({
            'Salários CLT': 'R$ {:,.2f}',
            'Salários Inf.': 'R$ {:,.2f}',
            'FGTS': 'R$ {:,.2f}',
            'Prov. 13º': 'R$ {:,.2f}',
            'Prov. Férias': 'R$ {:,.2f}',
            'Pró-Labore': 'R$ {:,.2f}',
            'INSS': 'R$ {:,.2f}',
            'TOTAL': 'R$ {:,.2f}'
        }),
        use_container_width=True,
        hide_index=True
    )


# ============================================
# PÁGINA FOLHA FISIOTERAPEUTAS
# ============================================

def pagina_folha_fisioterapeutas():
    """Página de Resumo da Folha de Fisioterapeutas"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>🏥 Folha de Pagamento - Fisioterapeutas</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    
    # Verificar se há profissionais com R$ Fixo sem valores configurados
    fisios_sem_valores = []
    for nome, fisio in motor.fisioterapeutas.items():
        if fisio.cargo != "Proprietário" and fisio.ativo:
            if fisio.tipo_remuneracao in ["valor_fixo", "misto"]:
                servicos_atendidos = [s for s in fisio.sessoes_por_servico.keys() if fisio.sessoes_por_servico.get(s, 0) > 0]
                valores_configurados = [s for s in servicos_atendidos if fisio.valores_fixos_por_servico.get(s, 0) > 0]
                # Para valor_fixo, precisa de todos os valores; para misto, é opcional
                if fisio.tipo_remuneracao == "valor_fixo" and servicos_atendidos and len(valores_configurados) < len(servicos_atendidos):
                    fisios_sem_valores.append(nome)
    
    if fisios_sem_valores:
        st.error(f"⚠️ **ATENÇÃO:** Profissionais com 'R$ Fixo' sem valores configurados: **{', '.join(fisios_sem_valores)}**. Isso resulta em R$ 0,00 de remuneração! Configure em Premissas > Folha Fisioterapeutas > Cadastro.")
    
    # Calcular projeção anual
    projecao = motor.projetar_folha_fisioterapeutas_anual()
    
    # Totais anuais
    total_fisio = sum(p['total_fisioterapeutas'] for p in projecao)
    total_prop = sum(p['total_proprietarios'] for p in projecao)
    total_producao = sum(p['producao_bruta'] for p in projecao)
    total_margem = sum(p['margem_clinica'] for p in projecao)
    total_geral = total_fisio + total_prop
    
    # Cards de resumo
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("🩺 Fisioterapeutas", format_currency(total_fisio), card_type="default")
    with col2:
        render_metric_card("👔 Proprietários", format_currency(total_prop), card_type="default")
    with col3:
        render_metric_card("📈 Produção Bruta", format_currency(total_producao), card_type="success")
    with col4:
        render_metric_card("💰 Margem Clínica", format_currency(total_margem), card_type="success")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Segunda linha de cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        n_fisio = len([f for f in motor.fisioterapeutas.values() if f.cargo in ["Fisioterapeuta", "Gerente"] and f.ativo])
        st.metric("Qtd. Fisioterapeutas", n_fisio)
    with col2:
        n_prop = len([f for f in motor.fisioterapeutas.values() if f.cargo == "Proprietário" and f.ativo])
        st.metric("Qtd. Proprietários", n_prop)
    with col3:
        pct_margem = (total_margem / total_producao * 100) if total_producao > 0 else 0
        st.metric("% Margem s/ Produção", f"{pct_margem:.1f}%")
    with col4:
        render_metric_card("💰 TOTAL FOLHA", format_currency(total_geral), card_type="warning")
    
    st.markdown("---")
    
    # ===== TABELA POR FISIOTERAPEUTA MÊS A MÊS =====
    st.markdown("#### 🩺 Remuneração por Fisioterapeuta (Mês a Mês)")
    
    # Obter detalhamento mensal por profissional
    dados_fisios = []
    niveis_pct = {0: 0, 1: 0.25, 2: 0.30, 3: 0.35, 4: 0.40}
    
    for nome, fisio in motor.fisioterapeutas.items():
        if not fisio.ativo:
            continue
        
        # Determinar tipo de remuneração para exibição
        if fisio.cargo == "Proprietário":
            tipo_rem = "Prop"
        elif fisio.tipo_remuneracao == "valor_fixo":
            # Mostra "R$ Fixo" para valor fixo
            tipo_rem = "R$ Fixo"
        elif fisio.tipo_remuneracao == "misto":
            # Mostra o nível + indicador de misto
            nivel_pct = {1: "35%", 2: "30%", 3: "25%", 4: "20%"}.get(fisio.nivel, "?")
            tipo_rem = f"Misto Nv{fisio.nivel}"
        else:
            # Mostra o nível e percentual
            nivel_pct = {1: "35%", 2: "30%", 3: "25%", 4: "20%"}.get(fisio.nivel, "?")
            tipo_rem = f"Nv{fisio.nivel} ({nivel_pct})"
        
        # Calcular remuneração mês a mês
        remuneracao_mes = []
        for mes_idx, proj in enumerate(projecao):
            if fisio.cargo == "Proprietário":
                # Proprietário: pega do detalhamento
                rem = proj['detalhes_proprietarios'].get(nome, {}).get('total', 0)
            else:
                # Fisioterapeuta/Gerente: pega do detalhamento
                rem = proj['detalhes_fisioterapeutas'].get(nome, {}).get('total', 0)
            remuneracao_mes.append(rem)
        
        dados_fisios.append({
            'Nome': nome,
            'Cargo': fisio.cargo,
            'Tipo': tipo_rem,
            **{MESES[i]: remuneracao_mes[i] for i in range(12)},
            'TOTAL': sum(remuneracao_mes)
        })
    
    if dados_fisios:
        df_fisios = pd.DataFrame(dados_fisios)
        
        # Ordenar por cargo (Proprietário primeiro, depois por total)
        df_fisios['_ordem'] = df_fisios['Cargo'].map({'Proprietário': 0, 'Gerente': 1, 'Fisioterapeuta': 2})
        df_fisios = df_fisios.sort_values(['_ordem', 'TOTAL'], ascending=[True, False]).drop('_ordem', axis=1)
        
        # Linha de total
        total_row = {'Nome': 'TOTAL', 'Cargo': '', 'Tipo': ''}
        for mes in MESES:
            total_row[mes] = df_fisios[mes].sum()
        total_row['TOTAL'] = df_fisios['TOTAL'].sum()
        
        df_fisios = pd.concat([df_fisios, pd.DataFrame([total_row])], ignore_index=True)
        
        # Formatação
        format_dict = {'TOTAL': 'R$ {:,.2f}'}
        for mes in MESES:
            format_dict[mes] = 'R$ {:,.2f}'
        
        st.dataframe(
            df_fisios.style.format(format_dict),
            use_container_width=True,
            hide_index=True,
            height=400
        )
    else:
        st.info("Nenhum fisioterapeuta cadastrado.")
    
    st.markdown("---")
    
    # Gráfico de evolução mensal
    st.markdown("#### 📈 Evolução Mensal (Totais)")
    
    meses_chart = [MESES[i] for i in range(12)]
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Fisioterapeutas', 
        x=meses_chart, 
        y=[p['total_fisioterapeutas'] for p in projecao], 
        marker_color='#3498db'
    ))
    fig.add_trace(go.Bar(
        name='Proprietários', 
        x=meses_chart, 
        y=[p['total_proprietarios'] for p in projecao], 
        marker_color='#9b59b6'
    ))
    fig.add_trace(go.Scatter(
        name='Margem Clínica', 
        x=meses_chart, 
        y=[p['margem_clinica'] for p in projecao], 
        mode='lines+markers',
        line=dict(color='#2ecc71', width=3),
        yaxis='y2'
    ))
    
    fig.update_layout(
        barmode='stack',
        height=350,
        margin=dict(l=20, r=20, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis2=dict(
            title='Margem Clínica',
            overlaying='y',
            side='right'
        )
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Tabela resumo mensal
    st.markdown("#### 📊 Resumo Mensal")
    
    df_tabela = pd.DataFrame([{
        'Mês': MESES[i],
        'Produção Bruta': p['producao_bruta'],
        'Fisioterapeutas': p['total_fisioterapeutas'],
        'Proprietários': p['total_proprietarios'],
        'Total Folha': p['total_fisioterapeutas'] + p['total_proprietarios'],
        'Margem Clínica': p['margem_clinica'],
        '% Margem': (p['margem_clinica'] / p['producao_bruta'] * 100) if p['producao_bruta'] > 0 else 0
    } for i, p in enumerate(projecao)])
    
    # Linha de total
    total_row = pd.DataFrame([{
        'Mês': 'TOTAL',
        'Produção Bruta': df_tabela['Produção Bruta'].sum(),
        'Fisioterapeutas': df_tabela['Fisioterapeutas'].sum(),
        'Proprietários': df_tabela['Proprietários'].sum(),
        'Total Folha': df_tabela['Total Folha'].sum(),
        'Margem Clínica': df_tabela['Margem Clínica'].sum(),
        '% Margem': (df_tabela['Margem Clínica'].sum() / df_tabela['Produção Bruta'].sum() * 100) if df_tabela['Produção Bruta'].sum() > 0 else 0
    }])
    df_tabela = pd.concat([df_tabela, total_row], ignore_index=True)
    
    st.dataframe(
        df_tabela.style.format({
            'Produção Bruta': 'R$ {:,.2f}',
            'Fisioterapeutas': 'R$ {:,.2f}',
            'Proprietários': 'R$ {:,.2f}',
            'Total Folha': 'R$ {:,.2f}',
            'Margem Clínica': 'R$ {:,.2f}',
            '% Margem': '{:.1f}%'
        }),
        use_container_width=True,
        hide_index=True
    )


# ============================================
# PÁGINA SIMPLES NACIONAL
# ============================================

def pagina_simples_nacional():
    """Página de cálculo do Simples Nacional e Carnê Leão"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>💼 Simples Nacional / Carnê Leão</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    ps = motor.premissas_simples
    
    # ===== PROCESSAR PREMISSAS PRIMEIRO (usando session_state para valores persistentes) =====
    # Isso garante que os valores sejam aplicados antes do cálculo
    
    # Inicializa valores no session_state se não existirem
    if 'sn_limite_fator_r' not in st.session_state:
        st.session_state.sn_limite_fator_r = ps.limite_fator_r
    if 'sn_faturamento_pf_anual' not in st.session_state:
        st.session_state.sn_faturamento_pf_anual = ps.faturamento_pf_anual
    if 'sn_aliquota_inss_pf' not in st.session_state:
        st.session_state.sn_aliquota_inss_pf = ps.aliquota_inss_pf
    
    # Aplica valores do session_state ao motor (valores mais recentes)
    ps.limite_fator_r = st.session_state.sn_limite_fator_r
    ps.faturamento_pf_anual = st.session_state.sn_faturamento_pf_anual
    ps.aliquota_inss_pf = st.session_state.sn_aliquota_inss_pf
    
    # ===== EXIBE REGIME (somente leitura - configurado nas Premissas) =====
    st.markdown("#### ⚙️ Regime Tributário")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        regime_atual = motor.operacional.modelo_tributario if motor.operacional.modelo_tributario else "PJ - Simples Nacional"
        
        # Exibe como info box (não editável)
        st.info(f"📋 **Regime Selecionado:** {regime_atual}")
    
    with col2:
        if "Simples" in regime_atual or "PJ" in regime_atual:
            st.success("📊 PJ - DAS")
        else:
            st.warning("📋 PF - IRRF")
    
    with col3:
        st.caption("⚙️ Para alterar o regime, vá em:")
        st.caption("**Premissas → Operacional**")
    
    st.markdown("---")
    
    # Calcular
    calc = motor.calcular_simples_nacional_anual()
    
    # Cards de resumo
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("📈 Receita Anual", format_currency(calc['receita_total']), card_type="success")
    with col2:
        render_metric_card("🏢 DAS (PJ)", format_currency(calc['total_pj']), card_type="warning")
    with col3:
        render_metric_card("👤 IR+INSS (PF)", format_currency(calc['total_pf']), card_type="default")
    with col4:
        card_type = "success" if calc['mais_vantajoso'] == "PF" else "warning"
        render_metric_card("✅ Mais Vantajoso", calc['mais_vantajoso'], card_type=card_type)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Segunda linha - comparativo
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        aliq_media_pj = calc['total_pj'] / calc['receita_total'] * 100 if calc['receita_total'] > 0 else 0
        st.metric("Alíquota Média PJ", f"{aliq_media_pj:.2f}%")
    with col2:
        # Usa a receita do próprio cálculo PF (soma das receitas mensais)
        receita_pf_total = sum(p['receita_mensal'] for p in calc['projecao_pf'])
        aliq_media_pf = calc['total_pf'] / receita_pf_total * 100 if receita_pf_total > 0 else 0
        st.metric("Alíquota Média PF", f"{aliq_media_pf:.2f}%")
    with col3:
        st.metric("Economia", format_currency(abs(calc['diferenca'])))
    with col4:
        imposto_dre = sum(motor.get_impostos_para_dre_anual())
        st.metric("→ Imposto p/ DRE", format_currency(imposto_dre))
    
    st.markdown("---")
    
    # Tabs para PJ e PF
    tab1, tab2, tab3 = st.tabs(["🏢 Simples Nacional (PJ)", "👤 Carnê Leão (PF)", "⚙️ Premissas"])
    
    with tab1:
        st.markdown("#### 📊 Cálculo DAS - Simples Nacional")
        
        df_pj = pd.DataFrame([{
            'Mês': MESES[p['mes']-1],
            'Receita': p['receita_mensal'],
            'Folha': p['folha_mensal'],
            'RBT12': p['rbt12'],
            'Folha 12m': p['folha_12m'],
            'Fator r': p['fator_r'],
            'Anexo': p['anexo'],
            'Alíq. Efetiva': p['aliquota_efetiva'],
            'DAS': p['das']
        } for p in calc['projecao_pj']])
        
        # Linha de total
        total_row = pd.DataFrame([{
            'Mês': 'TOTAL',
            'Receita': df_pj['Receita'].sum(),
            'Folha': df_pj['Folha'].sum(),
            'RBT12': '',
            'Folha 12m': '',
            'Fator r': '',
            'Anexo': '',
            'Alíq. Efetiva': df_pj['DAS'].sum() / df_pj['Receita'].sum() if df_pj['Receita'].sum() > 0 else 0,
            'DAS': df_pj['DAS'].sum()
        }])
        df_pj = pd.concat([df_pj, total_row], ignore_index=True)
        
        st.dataframe(
            df_pj.style.format({
                'Receita': 'R$ {:,.2f}',
                'Folha': 'R$ {:,.2f}',
                'RBT12': lambda x: f'R$ {x:,.2f}' if isinstance(x, (int, float)) else '',
                'Folha 12m': lambda x: f'R$ {x:,.2f}' if isinstance(x, (int, float)) else '',
                'Fator r': lambda x: f'{x*100:.2f}%' if isinstance(x, (int, float)) and x != '' else '',
                'Alíq. Efetiva': lambda x: f'{x*100:.2f}%' if isinstance(x, (int, float)) else '',
                'DAS': 'R$ {:,.2f}'
            }),
            use_container_width=True,
            hide_index=True,
            height=500
        )
        
        # Gráfico
        st.markdown("#### 📈 Evolução DAS e Alíquota")
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='DAS',
            x=[MESES[p['mes']-1] for p in calc['projecao_pj']],
            y=[p['das'] for p in calc['projecao_pj']],
            marker_color='#e74c3c'
        ))
        fig.add_trace(go.Scatter(
            name='Alíquota Efetiva',
            x=[MESES[p['mes']-1] for p in calc['projecao_pj']],
            y=[p['aliquota_efetiva'] * 100 for p in calc['projecao_pj']],
            mode='lines+markers',
            line=dict(color='#3498db', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            height=350,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis2=dict(title='Alíquota (%)', overlaying='y', side='right')
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.markdown("#### 📊 Cálculo Carnê Leão - Pessoa Física")
        st.caption(f"💡 Faturamento PF anual: R$ {ps.faturamento_pf_anual:,.2f} (editável nas premissas)")
        
        df_pf = pd.DataFrame([{
            'Mês': MESES[p['mes']-1],
            'Receita PF': p['receita_mensal'],
            'INSS': p['inss'],
            'Base IR': p['base_ir'],
            'IR': p['ir'],
            'Status': p['status'],
            'Total': p['total'],
            'Alíq. Efetiva': p['aliquota_efetiva']
        } for p in calc['projecao_pf']])
        
        # Linha de total
        total_row = pd.DataFrame([{
            'Mês': 'TOTAL',
            'Receita PF': df_pf['Receita PF'].sum(),
            'INSS': df_pf['INSS'].sum(),
            'Base IR': '',
            'IR': df_pf['IR'].sum(),
            'Status': '',
            'Total': df_pf['Total'].sum(),
            'Alíq. Efetiva': df_pf['Total'].sum() / df_pf['Receita PF'].sum() if df_pf['Receita PF'].sum() > 0 else 0
        }])
        df_pf = pd.concat([df_pf, total_row], ignore_index=True)
        
        st.dataframe(
            df_pf.style.format({
                'Receita PF': 'R$ {:,.2f}',
                'INSS': 'R$ {:,.2f}',
                'Base IR': lambda x: f'R$ {x:,.2f}' if isinstance(x, (int, float)) else '',
                'IR': 'R$ {:,.2f}',
                'Total': 'R$ {:,.2f}',
                'Alíq. Efetiva': lambda x: f'{x*100:.2f}%' if isinstance(x, (int, float)) else ''
            }),
            use_container_width=True,
            hide_index=True,
            height=500
        )
    
    with tab3:
        st.markdown("#### ⚙️ Premissas Simples Nacional")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🏢 Parâmetros Gerais")
            novo_limite_fator_r = st.number_input(
                "Limite Fator R (para Anexo III)",
                min_value=0.0, max_value=1.0, value=float(st.session_state.sn_limite_fator_r),
                step=0.01, format="%.2f",
                key="input_limite_fator_r"
            )
            if novo_limite_fator_r != st.session_state.sn_limite_fator_r:
                st.session_state.sn_limite_fator_r = novo_limite_fator_r
                ps.limite_fator_r = novo_limite_fator_r
                st.rerun()
            st.caption("Se Fator r >= 28% → Anexo III (mais favorável)")
        
        with col2:
            st.markdown("##### 👤 Carnê Leão (PF)")
            novo_faturamento_pf = st.number_input(
                "Faturamento PF Anual (R$)",
                min_value=0.0, max_value=5000000.0, value=float(st.session_state.sn_faturamento_pf_anual),
                step=1000.0, format="%.2f",
                key="input_fat_pf_anual",
                help="Se zerado, usa a mesma receita do PJ para comparação"
            )
            if novo_faturamento_pf != st.session_state.sn_faturamento_pf_anual:
                st.session_state.sn_faturamento_pf_anual = novo_faturamento_pf
                ps.faturamento_pf_anual = novo_faturamento_pf
                st.rerun()
            
            aliq_inss_opcoes = {"Sem INSS (0%)": 0.0, "Simplificado (11%)": 0.11, "Normal (20%)": 0.20}
            aliq_atual = next((k for k, v in aliq_inss_opcoes.items() if abs(v - st.session_state.sn_aliquota_inss_pf) < 0.001), "Simplificado (11%)")
            nova_aliq = st.selectbox("Alíquota INSS PF", list(aliq_inss_opcoes.keys()), 
                                     index=list(aliq_inss_opcoes.keys()).index(aliq_atual),
                                     key="input_aliq_inss_pf")
            nova_aliq_valor = aliq_inss_opcoes[nova_aliq]
            if abs(nova_aliq_valor - st.session_state.sn_aliquota_inss_pf) > 0.001:
                st.session_state.sn_aliquota_inss_pf = nova_aliq_valor
                ps.aliquota_inss_pf = nova_aliq_valor
                st.rerun()
        
        st.markdown("---")
        
        # Tabelas de Alíquotas
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 📋 Tabela Anexo III (Fator r ≥ 28%)")
            df_anexo3 = pd.DataFrame([
                {"Faixa RBT12": f"Até R$ {l:,.0f}", "Alíquota": f"{a*100:.1f}%", "Dedução": f"R$ {d:,.0f}"}
                for l, a, d in ps.tabela_anexo_iii
            ])
            st.dataframe(df_anexo3, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("##### 📋 Tabela Anexo V (Fator r < 28%)")
            df_anexo5 = pd.DataFrame([
                {"Faixa RBT12": f"Até R$ {l:,.0f}", "Alíquota": f"{a*100:.1f}%", "Dedução": f"R$ {d:,.0f}"}
                for l, a, d in ps.tabela_anexo_v
            ])
            st.dataframe(df_anexo5, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.markdown("##### 📋 Premissas IR 2026 (Lei 15.270/2025)")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Limite Isenção", f"R$ {ps.limite_isencao_ir:,.2f}")
        with col2:
            st.metric("Teto Redutor", f"R$ {ps.teto_redutor_ir:,.2f}")
        with col3:
            st.metric("Dedução Fixa", f"R$ {ps.deducao_fixa_ir:,.2f}")


def pagina_financeiro():
    """Página do Módulo Financeiro - Investimentos, Financiamentos, Aplicações"""
    render_header()
    
    st.markdown('<div class="section-header"><h3>💰 Módulo Financeiro</h3></div>', unsafe_allow_html=True)
    
    motor = st.session_state.motor
    pf = motor.premissas_financeiras
    
    # Calcula resumo
    resumo = motor.get_resumo_financeiro()
    
    # ========== CARDS DE RESUMO ==========
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            "📉 Despesas Financeiras", 
            format_currency(resumo["resumo"]["total_despesas_financeiras"]),
            card_type="danger"
        )
    with col2:
        render_metric_card(
            "📈 Receitas Financeiras",
            format_currency(resumo["resumo"]["total_receitas_financeiras"]),
            card_type="success"
        )
    with col3:
        resultado = resumo["resumo"]["resultado_financeiro_liquido"]
        card_type = "success" if resultado >= 0 else "danger"
        render_metric_card(
            "💰 Resultado Financeiro",
            format_currency(resultado),
            card_type=card_type
        )
    with col4:
        render_metric_card(
            "🏦 Saldo Aplicações (Dez)",
            format_currency(resumo["aplicacoes"]["saldo_final"]),
            card_type="default"
        )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # ========== TABS ==========
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Resumo", 
        "🏗️ Investimentos (CAPEX)", 
        "📋 Financiamentos", 
        "💳 Cheque Especial",
        "📈 Aplicações"
    ])
    
    # ========== TAB 1: RESUMO ==========
    with tab1:
        st.markdown("#### 📊 Resumo Financeiro Mensal")
        
        mensal = resumo["mensal"]
        
        # ===== TABELA ESTILIZADA DE RESUMO =====
        html = '<table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:20px;">'
        
        # Header
        html += '<tr style="background:linear-gradient(135deg, #1a365d 0%, #2c5282 100%); color:white;">'
        html += '<th style="padding:10px 8px; text-align:left; font-weight:600;">Mês</th>'
        html += '<th style="padding:10px 8px; text-align:center; font-weight:600;">💰 Juros Invest.</th>'
        html += '<th style="padding:10px 8px; text-align:center; font-weight:600;">🏦 Juros Financ.</th>'
        html += '<th style="padding:10px 8px; text-align:center; font-weight:600;">💳 Juros Cheque</th>'
        html += '<th style="padding:10px 8px; text-align:center; font-weight:600;">📉 Total Despesas</th>'
        html += '<th style="padding:10px 8px; text-align:center; font-weight:600;">📈 Rendimentos</th>'
        html += '<th style="padding:10px 8px; text-align:center; font-weight:600;">💵 Resultado</th>'
        html += '</tr>'
        
        for m in range(12):
            bg_color = "#f7fafc" if m % 2 == 0 else "#edf2f7"
            juros_inv = mensal["juros_investimentos"][m]
            juros_fin = mensal["juros_financiamentos"][m]
            juros_chq = mensal["juros_cheque"][m]
            total_desp = mensal["total_despesas"][m]
            rendim = mensal["rendimentos_aplicacoes"][m]
            resultado = mensal["resultado_liquido"][m]
            
            result_color = "#276749" if resultado >= 0 else "#c53030"
            
            html += f'<tr style="background:{bg_color};">'
            html += f'<td style="padding:8px; text-align:left; font-weight:600;">{MESES_ABREV[m]}</td>'
            html += f'<td style="padding:8px; text-align:right; color:#c53030;">R$ {juros_inv:,.0f}</td>'
            html += f'<td style="padding:8px; text-align:right; color:#c53030;">R$ {juros_fin:,.0f}</td>'
            html += f'<td style="padding:8px; text-align:right; color:#c53030;">R$ {juros_chq:,.0f}</td>'
            html += f'<td style="padding:8px; text-align:right; color:#c53030; font-weight:600;">R$ {total_desp:,.0f}</td>'
            html += f'<td style="padding:8px; text-align:right; color:#276749;">R$ {rendim:,.0f}</td>'
            html += f'<td style="padding:8px; text-align:right; color:{result_color}; font-weight:600;">R$ {resultado:,.0f}</td>'
            html += '</tr>'
        
        # Linha TOTAL
        total_juros_inv = sum(mensal["juros_investimentos"])
        total_juros_fin = sum(mensal["juros_financiamentos"])
        total_juros_chq = sum(mensal["juros_cheque"])
        total_desp = sum(mensal["total_despesas"])
        total_rend = sum(mensal["rendimentos_aplicacoes"])
        total_result = sum(mensal["resultado_liquido"])
        
        result_color_total = "#9ae6b4" if total_result >= 0 else "#feb2b2"
        
        html += f'<tr style="background:linear-gradient(135deg, #2c5282 0%, #2b6cb0 100%); color:white; font-weight:bold;">'
        html += f'<td style="padding:10px 8px; text-align:left;">TOTAL</td>'
        html += f'<td style="padding:10px 8px; text-align:right;">R$ {total_juros_inv:,.0f}</td>'
        html += f'<td style="padding:10px 8px; text-align:right;">R$ {total_juros_fin:,.0f}</td>'
        html += f'<td style="padding:10px 8px; text-align:right;">R$ {total_juros_chq:,.0f}</td>'
        html += f'<td style="padding:10px 8px; text-align:right;">R$ {total_desp:,.0f}</td>'
        html += f'<td style="padding:10px 8px; text-align:right; color:#9ae6b4;">R$ {total_rend:,.0f}</td>'
        html += f'<td style="padding:10px 8px; text-align:right; color:{result_color_total};">R$ {total_result:,.0f}</td>'
        html += '</tr>'
        html += '</table>'
        st.markdown(html, unsafe_allow_html=True)
        
        # ===== TABELA DE PARCELAS (se houver financiamentos) =====
        if pf.financiamentos or pf.investimentos:
            st.markdown("---")
            st.markdown("#### 📅 Cronograma de Parcelas")
            
            # Monta dados de parcelas
            parcelas_data = []
            
            # Financiamentos existentes
            for fin in pf.financiamentos:
                if not fin.ativo:
                    continue
                for mes in range(1, 13):
                    amort = fin.calcular_amortizacao_mes(mes)
                    juros = fin.calcular_juros_mes(mes)
                    parcela = amort + juros
                    if parcela > 0:
                        parcelas_data.append({
                            "mes": mes,
                            "tipo": "🏦 Financ.",
                            "descricao": fin.descricao or "Financiamento",
                            "amortizacao": amort,
                            "juros": juros,
                            "parcela": parcela
                        })
            
            # Investimentos novos
            for inv in pf.investimentos:
                if not inv.ativo:
                    continue
                # Entrada
                if inv.entrada > 0:
                    parcelas_data.append({
                        "mes": inv.mes_aquisicao,
                        "tipo": "🏗️ CAPEX",
                        "descricao": f"{inv.descricao} (Entrada)",
                        "amortizacao": inv.entrada,
                        "juros": 0,
                        "parcela": inv.entrada
                    })
                # Parcelas
                for mes in range(1, 13):
                    amort = inv.calcular_amortizacao_mes(mes)
                    juros = inv.calcular_juros_mes(mes)
                    parcela = amort + juros
                    if parcela > 0:
                        parcelas_data.append({
                            "mes": mes,
                            "tipo": "🏗️ Invest.",
                            "descricao": inv.descricao or "Investimento",
                            "amortizacao": amort,
                            "juros": juros,
                            "parcela": parcela
                        })
            
            if parcelas_data:
                # Ordena por mês
                parcelas_data.sort(key=lambda x: (x["mes"], x["tipo"]))
                
                html_parc = '<table style="width:100%; border-collapse:collapse; font-size:12px;">'
                
                # Header
                html_parc += '<tr style="background:linear-gradient(135deg, #744210 0%, #975a16 100%); color:white;">'
                html_parc += '<th style="padding:10px 8px; text-align:left; font-weight:600;">Mês</th>'
                html_parc += '<th style="padding:10px 8px; text-align:left; font-weight:600;">Tipo</th>'
                html_parc += '<th style="padding:10px 8px; text-align:left; font-weight:600;">Descrição</th>'
                html_parc += '<th style="padding:10px 8px; text-align:center; font-weight:600;">Amortização</th>'
                html_parc += '<th style="padding:10px 8px; text-align:center; font-weight:600;">Juros</th>'
                html_parc += '<th style="padding:10px 8px; text-align:center; font-weight:600;">💵 Parcela</th>'
                html_parc += '</tr>'
                
                total_amort = 0
                total_juros = 0
                total_parcela = 0
                
                for idx, p in enumerate(parcelas_data):
                    bg_color = "#fffff0" if idx % 2 == 0 else "#fefcbf"
                    total_amort += p["amortizacao"]
                    total_juros += p["juros"]
                    total_parcela += p["parcela"]
                    
                    html_parc += f'<tr style="background:{bg_color};">'
                    html_parc += f'<td style="padding:8px; font-weight:600; color:#744210;">{MESES_ABREV[p["mes"]-1]}</td>'
                    html_parc += f'<td style="padding:8px; font-size:11px;">{p["tipo"]}</td>'
                    html_parc += f'<td style="padding:8px;">{p["descricao"]}</td>'
                    html_parc += f'<td style="padding:8px; text-align:right;">R$ {p["amortizacao"]:,.0f}</td>'
                    html_parc += f'<td style="padding:8px; text-align:right; color:#c53030;">R$ {p["juros"]:,.0f}</td>'
                    html_parc += f'<td style="padding:8px; text-align:right; font-weight:600;">R$ {p["parcela"]:,.0f}</td>'
                    html_parc += '</tr>'
                
                # Linha TOTAL
                html_parc += f'<tr style="background:linear-gradient(135deg, #975a16 0%, #b7791f 100%); color:white; font-weight:bold;">'
                html_parc += f'<td colspan="3" style="padding:10px 8px; text-align:right;">TOTAL ANO</td>'
                html_parc += f'<td style="padding:10px 8px; text-align:right;">R$ {total_amort:,.0f}</td>'
                html_parc += f'<td style="padding:10px 8px; text-align:right;">R$ {total_juros:,.0f}</td>'
                html_parc += f'<td style="padding:10px 8px; text-align:right;">R$ {total_parcela:,.0f}</td>'
                html_parc += '</tr>'
                html_parc += '</table>'
                
                st.markdown(html_parc, unsafe_allow_html=True)
                
                # Cards resumo
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("💰 Total Amortização", f"R$ {total_amort:,.0f}")
                with col2:
                    st.metric("📉 Total Juros", f"R$ {total_juros:,.0f}", delta=f"-{total_juros/total_parcela*100:.1f}%" if total_parcela > 0 else None, delta_color="inverse")
                with col3:
                    st.metric("💵 Total Parcelas", f"R$ {total_parcela:,.0f}")
            else:
                st.info("Nenhum financiamento ou investimento cadastrado com parcelas no período.")
        
        # Gráfico
        st.markdown("---")
        st.markdown("#### 📈 Evolução Mensal")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Despesas Financeiras',
            x=MESES_ABREV,
            y=[-v for v in mensal["total_despesas"]],
            marker_color='#c53030'
        ))
        
        fig.add_trace(go.Bar(
            name='Receitas Financeiras',
            x=MESES_ABREV,
            y=mensal["rendimentos_aplicacoes"],
            marker_color='#38a169'
        ))
        
        fig.add_trace(go.Scatter(
            name='Resultado Líquido',
            x=MESES_ABREV,
            y=mensal["resultado_liquido"],
            mode='lines+markers',
            line=dict(color='#2c5282', width=3)
        ))
        
        fig.update_layout(
            barmode='relative',
            height=400,
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # ========== TAB 2: INVESTIMENTOS ==========
    with tab2:
        st.markdown("#### 🏗️ Investimentos (CAPEX)")
        
        # Lista de investimentos existentes
        if pf.investimentos:
            st.markdown("##### 📋 Investimentos Cadastrados")
            
            for idx, inv in enumerate(pf.investimentos):
                with st.expander(f"{'✅' if inv.ativo else '⬜'} {inv.descricao or f'Investimento {idx+1}'} - {inv.categoria}", expanded=inv.ativo):
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    with col1:
                        inv.ativo = st.checkbox("Ativo", value=inv.ativo, key=f"inv_ativo_{idx}")
                        inv.descricao = st.text_input("Descrição", value=inv.descricao, key=f"inv_desc_{idx}")
                        inv.categoria = st.selectbox(
                            "Categoria",
                            ["Equipamentos", "Mobiliário", "Tecnologia/Software", "Reforma/Ampliação", "Veículo", "Outros"],
                            index=["Equipamentos", "Mobiliário", "Tecnologia/Software", "Reforma/Ampliação", "Veículo", "Outros"].index(inv.categoria) if inv.categoria in ["Equipamentos", "Mobiliário", "Tecnologia/Software", "Reforma/Ampliação", "Veículo", "Outros"] else 0,
                            key=f"inv_cat_{idx}"
                        )
                    
                    with col2:
                        inv.valor_total = st.number_input("Valor Total (R$)", value=float(inv.valor_total), step=10000.0, key=f"inv_valor_{idx}")
                        inv.entrada = st.number_input("Entrada (R$)", value=float(inv.entrada), step=10000.0, key=f"inv_entrada_{idx}")
                        mes_idx = max(0, min(11, inv.mes_aquisicao - 1)) if inv.mes_aquisicao > 0 else 0
                        inv.mes_aquisicao = st.selectbox("Mês Aquisição", list(range(1, 13)), index=mes_idx, format_func=lambda x: MESES_ABREV[x-1], key=f"inv_mes_{idx}")
                    
                    with col3:
                        inv.taxa_mensal = st.number_input("Taxa a.m. (%)", value=float(inv.taxa_mensal*100), step=0.5, key=f"inv_taxa_{idx}") / 100
                        inv.parcelas = int(st.number_input("Parcelas", value=int(inv.parcelas), step=1, min_value=1, key=f"inv_parc_{idx}"))
                        inv.beneficio_mensal = st.number_input("Benefício Mensal (R$)", value=float(inv.beneficio_mensal), step=1000.0, key=f"inv_benef_{idx}")
                    
                    # Resumo do investimento
                    if inv.valor_total > 0:
                        st.markdown("---")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Valor Financiado", format_currency(inv.valor_financiado))
                        with col2:
                            st.metric("Valor Parcela (PMT)", format_currency(inv.calcular_pmt()))
                        with col3:
                            st.metric("Custo Total", format_currency(inv.calcular_custo_total()))
                        with col4:
                            st.metric("Total Juros", format_currency(inv.calcular_juros_total()))
                        
                        if inv.beneficio_mensal > 0:
                            st.metric("Payback", f"{inv.calcular_payback():.1f} meses")
            
            # Botão para adicionar novo
            if st.button("➕ Adicionar Investimento", key="add_inv"):
                pf.investimentos.append(Investimento(
                    descricao="Novo Investimento",
                    categoria="Equipamentos",
                    valor_total=0.0,
                    mes_aquisicao=1,
                    entrada=0.0,
                    taxa_mensal=0.03,
                    parcelas=24,
                    ativo=True
                ))
                st.rerun()
        
        else:
            st.info("Nenhum investimento cadastrado.")
            if st.button("➕ Adicionar Primeiro Investimento"):
                pf.investimentos.append(Investimento(
                    descricao="Novo Investimento",
                    categoria="Equipamentos",
                    valor_total=0.0,
                    mes_aquisicao=1,
                    entrada=0.0,
                    taxa_mensal=0.03,
                    parcelas=24,
                    ativo=True
                ))
                st.rerun()
        
        # Tabela de juros mensais
        if any(inv.ativo for inv in pf.investimentos):
            st.markdown("---")
            st.markdown("##### 📊 Juros Mensais - Investimentos")
            
            dados_juros = []
            for m in range(12):
                row = {"Mês": MESES_ABREV[m]}
                total_mes = 0
                for idx, inv in enumerate(pf.investimentos):
                    if inv.ativo:
                        juros = inv.calcular_juros_mes(m + 1)
                        row[inv.descricao or f"Inv {idx+1}"] = juros
                        total_mes += juros
                row["Total"] = total_mes
                dados_juros.append(row)
            
            # Total anual
            row_total = {"Mês": "TOTAL"}
            for col in dados_juros[0].keys():
                if col != "Mês":
                    row_total[col] = sum(r[col] for r in dados_juros)
            dados_juros.append(row_total)
            
            df_juros = pd.DataFrame(dados_juros)
            
            # Formatar colunas
            format_dict = {col: "R$ {:,.2f}" for col in df_juros.columns if col != "Mês"}
            st.dataframe(df_juros.style.format(format_dict), use_container_width=True, hide_index=True)
    
    # ========== TAB 3: FINANCIAMENTOS ==========
    with tab3:
        st.markdown("#### 📋 Financiamentos Existentes")
        
        if pf.financiamentos:
            for idx, fin in enumerate(pf.financiamentos):
                with st.expander(f"{'✅' if fin.ativo else '⬜'} {fin.descricao or f'Financiamento {idx+1}'}", expanded=fin.ativo):
                    col1, col2, col3 = st.columns([1, 1, 1])
                    
                    with col1:
                        fin.ativo = st.checkbox("Ativo", value=fin.ativo, key=f"fin_ativo_{idx}")
                        fin.descricao = st.text_input("Descrição", value=fin.descricao, key=f"fin_desc_{idx}")
                        fin.saldo_devedor = st.number_input("Saldo Devedor (R$)", value=float(fin.saldo_devedor), step=10000.0, key=f"fin_saldo_{idx}")
                    
                    with col2:
                        fin.taxa_mensal = st.number_input("Taxa a.m. (%)", value=float(fin.taxa_mensal*100), step=0.5, key=f"fin_taxa_{idx}") / 100
                        fin.parcelas_total = int(st.number_input("Parcelas Total", value=int(fin.parcelas_total), step=1, min_value=1, key=f"fin_parc_tot_{idx}"))
                        fin.parcelas_pagas = int(st.number_input("Parcelas Pagas", value=int(fin.parcelas_pagas), step=1, min_value=0, key=f"fin_parc_pag_{idx}"))
                    
                    with col3:
                        mes_idx = max(0, min(11, fin.mes_inicio_2026 - 1)) if fin.mes_inicio_2026 > 0 else 0
                        fin.mes_inicio_2026 = st.selectbox("Início Pagamento 2026", list(range(1, 13)), index=mes_idx, format_func=lambda x: MESES_ABREV[x-1], key=f"fin_mes_{idx}")
                        fin.valor_parcela = st.number_input("Valor Parcela (R$)", value=float(fin.valor_parcela), step=1000.0, key=f"fin_vlr_parc_{idx}")
                    
                    # Resumo
                    if fin.saldo_devedor > 0:
                        st.markdown("---")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Parcelas Restantes", fin.parcelas_restantes)
                        with col2:
                            juros_ano = sum(fin.calcular_juros_mes(m) for m in range(1, 13))
                            st.metric("Juros Previstos 2026", format_currency(juros_ano))
            
            if st.button("➕ Adicionar Financiamento", key="add_fin"):
                pf.financiamentos.append(FinanciamentoExistente(
                    descricao="Novo Financiamento",
                    saldo_devedor=0.0,
                    taxa_mensal=0.02,
                    parcelas_total=60,
                    parcelas_pagas=0,
                    mes_inicio_2026=1,
                    valor_parcela=0.0,
                    ativo=True
                ))
                st.rerun()
        
        else:
            st.info("Nenhum financiamento cadastrado.")
            if st.button("➕ Adicionar Primeiro Financiamento"):
                pf.financiamentos.append(FinanciamentoExistente(
                    descricao="Novo Financiamento",
                    saldo_devedor=0.0,
                    taxa_mensal=0.02,
                    parcelas_total=60,
                    parcelas_pagas=0,
                    mes_inicio_2026=1,
                    valor_parcela=0.0,
                    ativo=True
                ))
                st.rerun()
        
        # Tabela de juros mensais
        if any(fin.ativo for fin in pf.financiamentos):
            st.markdown("---")
            st.markdown("##### 📊 Juros Mensais - Financiamentos")
            
            dados_juros = []
            for m in range(12):
                row = {"Mês": MESES_ABREV[m]}
                total_mes = 0
                for idx, fin in enumerate(pf.financiamentos):
                    if fin.ativo:
                        juros = fin.calcular_juros_mes(m + 1)
                        row[fin.descricao or f"Fin {idx+1}"] = juros
                        total_mes += juros
                row["Total"] = total_mes
                dados_juros.append(row)
            
            # Total anual
            row_total = {"Mês": "TOTAL"}
            for col in dados_juros[0].keys():
                if col != "Mês":
                    row_total[col] = sum(r[col] for r in dados_juros)
            dados_juros.append(row_total)
            
            df_juros = pd.DataFrame(dados_juros)
            format_dict = {col: "R$ {:,.2f}" for col in df_juros.columns if col != "Mês"}
            st.dataframe(df_juros.style.format(format_dict), use_container_width=True, hide_index=True)
    
    # ========== TAB 4: CHEQUE ESPECIAL ==========
    with tab4:
        st.markdown("#### 💳 Cheque Especial")
        
        cheque = pf.cheque_especial
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("##### ⚙️ Configuração")
            cheque.taxa_mensal = st.number_input(
                "Taxa Mensal (%)", 
                value=float(cheque.taxa_mensal * 100), 
                step=0.5,
                key="cheque_taxa"
            ) / 100
            st.caption(f"Taxa equivalente: {cheque.taxa_mensal*100:.2f}% a.m.")
        
        with col2:
            st.markdown("##### 📊 Uso Mensal")
            
            dados_cheque = []
            for m in range(12):
                dados_cheque.append({
                    "Mês": MESES_ABREV[m],
                    "Valor Utilizado": cheque.valores_utilizados[m],
                    "Dias de Uso": cheque.dias_uso[m],
                    "Juros": cheque.calcular_juros_mes(m + 1)
                })
            
            # Edição em formato de tabela
            df_cheque = pd.DataFrame(dados_cheque)
            
            # Inputs editáveis
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**Valor Utilizado (R$)**")
                for m in range(12):
                    cheque.valores_utilizados[m] = st.number_input(
                        MESES_ABREV[m],
                        value=float(cheque.valores_utilizados[m]),
                        step=1000.0,
                        key=f"cheque_valor_{m}",
                        label_visibility="collapsed" if m > 0 else "visible"
                    )
            
            with col_b:
                st.markdown("**Dias de Uso**")
                for m in range(12):
                    cheque.dias_uso[m] = int(st.number_input(
                        MESES_ABREV[m],
                        value=int(cheque.dias_uso[m]),
                        step=1,
                        min_value=0,
                        max_value=30,
                        key=f"cheque_dias_{m}",
                        label_visibility="collapsed" if m > 0 else "visible"
                    ))
        
        # Resumo
        st.markdown("---")
        st.markdown("##### 📊 Resumo de Juros")
        
        dados_resumo_cheque = []
        total_juros = 0
        for m in range(12):
            juros = cheque.calcular_juros_mes(m + 1)
            total_juros += juros
            dados_resumo_cheque.append({
                "Mês": MESES_ABREV[m],
                "Valor Utilizado": format_currency(cheque.valores_utilizados[m]),
                "Dias": cheque.dias_uso[m],
                "Juros": format_currency(juros)
            })
        
        dados_resumo_cheque.append({
            "Mês": "TOTAL",
            "Valor Utilizado": "-",
            "Dias": "-",
            "Juros": format_currency(total_juros)
        })
        
        st.dataframe(pd.DataFrame(dados_resumo_cheque), use_container_width=True, hide_index=True)
    
    # ========== TAB 5: APLICAÇÕES ==========
    with tab5:
        st.markdown("#### 📈 Aplicações Financeiras")
        
        aplic = pf.aplicacoes
        
        # Verifica se política automática está ativa
        saldo_minimo_fc = motor.premissas_fc.saldo_minimo
        if saldo_minimo_fc > 0:
            st.info(f"""
            **🔄 Política Automática de Aplicações Ativa**
            
            Com saldo mínimo de **R$ {saldo_minimo_fc:,.0f}** configurado no FC, os aportes e resgates 
            são calculados **automaticamente**. Os valores manuais abaixo serão substituídos.
            
            *Para desativar, defina Saldo Mínimo = 0 em FC Simulado > Premissas.*
            """)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("##### ⚙️ Premissas")
            
            aplic.saldo_inicial = st.number_input(
                "Saldo Inicial (Dez/Ano Anterior)",
                value=float(aplic.saldo_inicial),
                step=10000.0,
                key="aplic_saldo"
            )
            
            aplic.taxa_selic_anual = st.number_input(
                "Taxa Selic Anual (%)",
                value=float(aplic.taxa_selic_anual * 100),
                step=0.25,
                key="aplic_selic"
            ) / 100
            
            aplic.pct_cdi = st.number_input(
                "% do CDI",
                value=float(aplic.pct_cdi * 100),
                step=5.0,
                min_value=0.0,
                max_value=150.0,
                key="aplic_cdi"
            ) / 100
            
            st.markdown("---")
            st.metric("Taxa Mensal Equivalente", f"{aplic.taxa_mensal*100:.4f}%")
        
        with col2:
            st.markdown("##### 📊 Movimentação Mensal")
            
            # Se política automática ativa, desabilita edição manual
            disabled_manual = saldo_minimo_fc > 0
            
            if disabled_manual:
                st.caption("⚠️ *Valores calculados automaticamente pela política de saldo mínimo*")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.markdown("**Aportes (R$)**")
                for m in range(12):
                    aplic.aportes[m] = st.number_input(
                        f"Aporte {MESES_ABREV[m]}",
                        value=float(aplic.aportes[m]),
                        step=1000.0,
                        key=f"aplic_aporte_{m}",
                        label_visibility="collapsed",
                        disabled=disabled_manual
                    )
            
            with col_b:
                st.markdown("**Resgates (R$)**")
                for m in range(12):
                    aplic.resgates[m] = st.number_input(
                        f"Resgate {MESES_ABREV[m]}",
                        value=float(aplic.resgates[m]),
                        step=1000.0,
                        key=f"aplic_resgate_{m}",
                        label_visibility="collapsed",
                        disabled=disabled_manual
                    )
        
        # Evolução
        st.markdown("---")
        st.markdown("##### 📊 Evolução das Aplicações")
        
        evolucao = aplic.calcular_evolucao_anual()
        
        dados_evol = []
        for ev in evolucao:
            dados_evol.append({
                "Mês": MESES_ABREV[ev["mes"] - 1],
                "Saldo Inicial": ev["saldo_inicial"],
                "Aportes": ev["aportes"],
                "Resgates": ev["resgates"],
                "Rendimento": ev["rendimento"],
                "Saldo Final": ev["saldo_final"]
            })
        
        # Linha total
        dados_evol.append({
            "Mês": "TOTAL",
            "Saldo Inicial": evolucao[0]["saldo_inicial"],
            "Aportes": sum(e["aportes"] for e in evolucao),
            "Resgates": sum(e["resgates"] for e in evolucao),
            "Rendimento": sum(e["rendimento"] for e in evolucao),
            "Saldo Final": evolucao[-1]["saldo_final"]
        })
        
        df_evol = pd.DataFrame(dados_evol)
        
        st.dataframe(
            df_evol.style.format({
                "Saldo Inicial": "R$ {:,.2f}",
                "Aportes": "R$ {:,.2f}",
                "Resgates": "R$ {:,.2f}",
                "Rendimento": "R$ {:,.2f}",
                "Saldo Final": "R$ {:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Gráfico de evolução
        if aplic.saldo_inicial > 0 or sum(aplic.aportes) > 0:
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                name='Saldo',
                x=MESES_ABREV,
                y=[e["saldo_final"] for e in evolucao],
                mode='lines+markers',
                fill='tozeroy',
                line=dict(color='#38a169', width=2)
            ))
            
            fig.update_layout(
                title="Evolução do Saldo das Aplicações",
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)


# ============================================
# PÁGINA DIVIDENDOS
# ============================================

def pagina_dividendos():
    """Página de distribuição de dividendos"""
    st.title("📊 Dividendos")
    
    motor = st.session_state.motor
    
    # Sincronizar proprietários
    motor.sincronizar_proprietarios()
    
    # NOTA: DRE será calculado APÓS os checkboxes serem processados
    
    # Tabs principais
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "👥 Quadro Societário",
        "⚙️ Política de Distribuição",
        "📈 Resultado Disponível",
        "💰 Dividendos por Período",
        "👤 Dividendos por Sócio",
        "📋 Resumo"
    ])
    
    prem_div = motor.premissas_dividendos
    
    # ===== TAB 1: QUADRO SOCIETÁRIO =====
    with tab1:
        st.markdown("### 👥 Quadro Societário")
        st.info("💡 Os sócios são os mesmos cadastrados em **Folha e Pró-Labore**. Edite lá para adicionar/remover sócios.")
        
        socios_ativos = {k: v for k, v in motor.socios_prolabore.items() if v.ativo}
        
        if not socios_ativos:
            st.warning("⚠️ Nenhum sócio cadastrado. Vá em 'Folha Funcionários' para cadastrar.")
        else:
            # Edição de participação e capital
            st.markdown("#### Participação e Capital Social")
            
            for nome, socio in socios_ativos.items():
                with st.expander(f"👤 {nome}", expanded=True):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Pró-Labore", f"R$ {socio.prolabore:,.2f}")
                    
                    with col2:
                        socio.participacao = st.number_input(
                            "Participação (%)",
                            min_value=0.0,
                            max_value=100.0,
                            value=float(socio.participacao * 100),
                            step=1.0,
                            key=f"part_{nome}"
                        ) / 100
                    
                    with col3:
                        socio.capital = st.number_input(
                            "Capital Investido (R$)",
                            min_value=0.0,
                            value=float(socio.capital),
                            step=1000.0,
                            key=f"capital_{nome}"
                        )
            
            # Validação e totais
            st.markdown("---")
            
            total_participacao = sum(s.participacao for s in socios_ativos.values())
            total_capital = sum(s.capital for s in socios_ativos.values())
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Sócios", len(socios_ativos))
            col2.metric("Total Participação", f"{total_participacao*100:.1f}%", 
                       delta="OK" if abs(total_participacao - 1.0) < 0.01 else f"⚠️ {(total_participacao-1)*100:+.1f}%")
            col3.metric("Capital Social Total", f"R$ {total_capital:,.2f}")
            
            if abs(total_participacao - 1.0) > 0.01:
                st.warning(f"⚠️ A soma das participações deve ser 100%. Atualmente: {total_participacao*100:.1f}%")
    
    # ===== TAB 2: POLÍTICA DE DISTRIBUIÇÃO =====
    with tab2:
        st.markdown("### ⚙️ Política de Distribuição")
        
        # Flag principal de ativação
        prem_div.distribuir = st.checkbox(
            "💰 Distribuir Dividendos",
            value=prem_div.distribuir,
            help="Se desmarcado, não calcula nem distribui dividendos. Todo lucro fica retido."
        )
        
        if not prem_div.distribuir:
            st.info("📋 Distribuição de dividendos **desativada**. Todo o lucro ficará retido na empresa.")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Reservas")
            
            prem_div.pct_reserva_legal = st.slider(
                "Reserva Legal (%)",
                min_value=0.0,
                max_value=10.0,
                value=float(prem_div.pct_reserva_legal * 100),
                step=0.5,
                help="5% é o padrão para S.A. LTDAs podem definir valores diferentes.",
                disabled=not prem_div.distribuir
            ) / 100
            
            prem_div.pct_reserva_investimento = st.slider(
                "Reserva para Investimentos (%)",
                min_value=0.0,
                max_value=50.0,
                value=float(prem_div.pct_reserva_investimento * 100),
                step=1.0,
                help="Percentual destinado a reinvestimento na empresa.",
                disabled=not prem_div.distribuir
            ) / 100
            
            if prem_div.distribuir:
                pct_lucro_distribuivel = 1 - prem_div.pct_reserva_legal - prem_div.pct_reserva_investimento
                st.info(f"📊 **Lucro Distribuível:** {pct_lucro_distribuivel*100:.1f}% do Resultado Líquido")
        
        with col2:
            st.markdown("#### Distribuição")
            
            frequencias = ["Mensal", "Trimestral", "Semestral", "Anual"]
            # Normaliza a frequência para capitalizada
            freq_atual = prem_div.frequencia.capitalize() if prem_div.frequencia else "Mensal"
            freq_idx = frequencias.index(freq_atual) if freq_atual in frequencias else 0
            
            prem_div.frequencia = st.selectbox(
                "Frequência de Distribuição",
                frequencias,
                index=freq_idx,
                disabled=not prem_div.distribuir
            )
            
            prem_div.pct_distribuir = st.slider(
                "% do Lucro Distribuível a Pagar",
                min_value=0.0,
                max_value=100.0,
                value=float(prem_div.pct_distribuir * 100),
                step=5.0,
                help="Quanto do lucro distribuível será pago em dividendos.",
                disabled=not prem_div.distribuir
            ) / 100
            
            if prem_div.distribuir:
                meses_pgto = prem_div.get_meses_pagamento()
                meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
                meses_str = ", ".join([meses_nomes[m-1] for m in meses_pgto])
                st.info(f"📅 **Meses de Pagamento:** {meses_str}")
        
        # Resumo da política
        if prem_div.distribuir:
            st.markdown("---")
            st.markdown("#### 📋 Resumo da Política")
            
            pct_lucro_distribuivel = 1 - prem_div.pct_reserva_legal - prem_div.pct_reserva_investimento
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Reserva Legal", f"{prem_div.pct_reserva_legal*100:.1f}%")
            col2.metric("Reserva Investimento", f"{prem_div.pct_reserva_investimento*100:.1f}%")
            col3.metric("Lucro Distribuível", f"{pct_lucro_distribuivel*100:.1f}%")
            col4.metric("% a Distribuir", f"{prem_div.pct_distribuir*100:.1f}%")
            
            # Payout efetivo
            payout_efetivo = pct_lucro_distribuivel * prem_div.pct_distribuir
            st.success(f"💰 **Payout Efetivo:** {payout_efetivo*100:.2f}% do Resultado Líquido será distribuído")
            
            # Flag para DRE
            st.markdown("---")
            st.markdown("#### 📊 Exibição no DRE")
            prem_div.mostrar_no_dre = st.checkbox(
                "Mostrar Dividendos no DRE",
                value=prem_div.mostrar_no_dre,
                help="Se marcado, as linhas de Reserva Legal, Reserva Investimentos e Dividendos Distribuídos aparecerão no DRE. Se desmarcado, apenas o Resultado Líquido será exibido."
            )
    
    # ===== CALCULAR DRE E DIVIDENDOS =====
    # Força recálculo do DRE para aplicar as flags atualizadas
    motor.calcular_dre()
    resultado = motor.calcular_dividendos()
    
    # ===== TAB 3: RESULTADO DISPONÍVEL =====
    with tab3:
        st.markdown("### 📈 Resultado Disponível para Distribuição")
        
        # Tabela mensal
        dados = []
        for m in range(12):
            dados.append({
                "Mês": MESES_ABREV[m],
                "Resultado Líquido": resultado["resultado_liquido"][m],
                "(-) Reserva Legal": -resultado["reserva_legal"][m],
                "(-) Reserva Invest.": -resultado["reserva_investimento"][m],
                "= Lucro Distribuível": resultado["lucro_distribuivel"][m]
            })
        
        # Linha total
        dados.append({
            "Mês": "TOTAL",
            "Resultado Líquido": sum(resultado["resultado_liquido"]),
            "(-) Reserva Legal": -sum(resultado["reserva_legal"]),
            "(-) Reserva Invest.": -sum(resultado["reserva_investimento"]),
            "= Lucro Distribuível": sum(resultado["lucro_distribuivel"])
        })
        
        df = pd.DataFrame(dados)
        
        st.dataframe(
            df.style.format({
                "Resultado Líquido": "R$ {:,.2f}",
                "(-) Reserva Legal": "R$ {:,.2f}",
                "(-) Reserva Invest.": "R$ {:,.2f}",
                "= Lucro Distribuível": "R$ {:,.2f}"
            }).applymap(
                lambda x: 'color: red' if isinstance(x, (int, float)) and x < 0 else '',
                subset=["Resultado Líquido", "= Lucro Distribuível"]
            ),
            use_container_width=True,
            hide_index=True
        )
        
        # Cards resumo
        st.markdown("---")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Resultado Líquido", f"R$ {resultado['indicadores']['total_resultado_liquido']:,.2f}")
        col2.metric("Reserva Legal", f"R$ {resultado['indicadores']['total_reserva_legal']:,.2f}")
        col3.metric("Reserva Investimento", f"R$ {resultado['indicadores']['total_reserva_investimento']:,.2f}")
        col4.metric("Lucro Distribuível", f"R$ {resultado['indicadores']['total_lucro_distribuivel']:,.2f}")
    
    # ===== TAB 4: DIVIDENDOS POR PERÍODO =====
    with tab4:
        st.markdown("### 💰 Dividendos por Período")
        
        # Tabela de dividendos por período
        dados_periodo = []
        for dp in resultado["dividendos_periodo"]:
            dados_periodo.append({
                "Período": dp["periodo"],
                "Meses": f"{dp['inicio']} a {dp['fim']}",
                "Lucro Acumulado": dp["lucro_acumulado"],
                "Dividendo Total": dp["dividendo"],
                "Mês Pagamento": MESES_ABREV[dp["mes_pagamento"] - 1]
            })
        
        # Linha total
        dados_periodo.append({
            "Período": "TOTAL ANUAL",
            "Meses": "1 a 12",
            "Lucro Acumulado": sum(dp["lucro_acumulado"] for dp in resultado["dividendos_periodo"]),
            "Dividendo Total": resultado["indicadores"]["total_dividendos"],
            "Mês Pagamento": "-"
        })
        
        df_periodo = pd.DataFrame(dados_periodo)
        
        st.dataframe(
            df_periodo.style.format({
                "Lucro Acumulado": "R$ {:,.2f}",
                "Dividendo Total": "R$ {:,.2f}"
            }),
            use_container_width=True,
            hide_index=True
        )
        
        # Gráfico
        if resultado["indicadores"]["total_dividendos"] > 0:
            fig = go.Figure()
            
            periodos = [dp["periodo"] for dp in resultado["dividendos_periodo"]]
            lucros = [dp["lucro_acumulado"] for dp in resultado["dividendos_periodo"]]
            dividendos = [dp["dividendo"] for dp in resultado["dividendos_periodo"]]
            
            fig.add_trace(go.Bar(
                name='Lucro Distribuível',
                x=periodos,
                y=lucros,
                marker_color='#4299e1'
            ))
            
            fig.add_trace(go.Bar(
                name='Dividendos',
                x=periodos,
                y=dividendos,
                marker_color='#48bb78'
            ))
            
            fig.update_layout(
                title="Lucro Distribuível vs Dividendos por Período",
                barmode='group',
                height=350
            )
            st.plotly_chart(fig, use_container_width=True)
    
    # ===== TAB 5: DIVIDENDOS POR SÓCIO =====
    with tab5:
        st.markdown("### 👤 Dividendos por Sócio")
        
        if not resultado["dividendos_por_socio"]:
            st.warning("⚠️ Nenhum sócio ativo para distribuição.")
        else:
            # Tabela por sócio
            dados_socio = []
            periodos = [dp["periodo"] for dp in resultado["dividendos_periodo"]]
            
            for nome, dados in resultado["dividendos_por_socio"].items():
                row = {
                    "Sócio": nome,
                    "Participação": f"{dados['participacao']*100:.1f}%"
                }
                for periodo in periodos:
                    row[periodo] = dados["por_periodo"].get(periodo, 0)
                row["Total Anual"] = dados["total_anual"]
                dados_socio.append(row)
            
            # Linha total
            row_total = {"Sócio": "TOTAL", "Participação": "100%"}
            for periodo in periodos:
                row_total[periodo] = sum(d["por_periodo"].get(periodo, 0) for d in resultado["dividendos_por_socio"].values())
            row_total["Total Anual"] = resultado["indicadores"]["total_dividendos"]
            dados_socio.append(row_total)
            
            df_socio = pd.DataFrame(dados_socio)
            
            # Formatar colunas numéricas
            format_dict = {"Total Anual": "R$ {:,.2f}"}
            for periodo in periodos:
                format_dict[periodo] = "R$ {:,.2f}"
            
            st.dataframe(
                df_socio.style.format(format_dict),
                use_container_width=True,
                hide_index=True
            )
            
            # Detalhes por sócio
            st.markdown("---")
            st.markdown("#### 📊 Detalhes por Sócio")
            
            for nome, dados in resultado["dividendos_por_socio"].items():
                with st.expander(f"👤 {nome}", expanded=False):
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Participação", f"{dados['participacao']*100:.1f}%")
                    col2.metric("Capital", f"R$ {dados['capital']:,.2f}")
                    col3.metric("Dividendo Anual", f"R$ {dados['total_anual']:,.2f}")
                    div_capital = dados['total_anual'] / dados['capital'] if dados['capital'] > 0 else 0
                    col4.metric("Retorno s/ Capital", f"{div_capital*100:.1f}%")
    
    # ===== TAB 6: RESUMO =====
    with tab6:
        st.markdown("### 📋 Resumo e Indicadores")
        
        ind = resultado["indicadores"]
        
        # Cards principais
        col1, col2, col3, col4 = st.columns(4)
        
        payout_display = ind['payout'] * 100 if ind['total_resultado_liquido'] > 0 else 0
        col1.metric(
            "Payout",
            f"{payout_display:.2f}%",
            help="% do lucro total distribuído como dividendos"
        )
        col2.metric(
            "Dividendo por R$ Capital",
            f"R$ {ind['dividendo_por_capital']:.2f}",
            help="Retorno por cada R$ 1 investido"
        )
        col3.metric(
            "Total Dividendos",
            f"R$ {ind['total_dividendos']:,.2f}"
        )
        col4.metric(
            "Lucro Retido",
            f"R$ {ind['lucro_retido']:,.2f}",
            help="Resultado líquido menos dividendos pagos"
        )
        
        # Cronograma de pagamentos
        st.markdown("---")
        st.markdown("#### 📅 Cronograma de Pagamentos (para Fluxo de Caixa)")
        
        cronograma_data = []
        for m in range(12):
            if resultado["cronograma"][m] > 0:
                cronograma_data.append({
                    "Mês": MESES_ABREV[m],
                    "Dividendos a Pagar": resultado["cronograma"][m]
                })
        
        if cronograma_data:
            df_cronograma = pd.DataFrame(cronograma_data)
            st.dataframe(
                df_cronograma.style.format({"Dividendos a Pagar": "R$ {:,.2f}"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("📭 Nenhum pagamento de dividendos programado (resultado negativo ou política define 0%).")
        
        # Gráfico de composição
        st.markdown("---")
        st.markdown("#### 📊 Composição do Resultado")
        
        if ind['total_resultado_liquido'] != 0:
            # Valores para o gráfico
            labels = ['Reserva Legal', 'Reserva Investimento', 'Dividendos', 'Lucro Retido (outros)']
            
            lucro_retido_outros = ind['lucro_retido'] - ind['total_reserva_legal'] - ind['total_reserva_investimento']
            if lucro_retido_outros < 0:
                lucro_retido_outros = 0
            
            values = [
                max(0, ind['total_reserva_legal']),
                max(0, ind['total_reserva_investimento']),
                max(0, ind['total_dividendos']),
                max(0, lucro_retido_outros)
            ]
            
            # Só mostra se houver valores positivos
            if sum(values) > 0:
                fig = go.Figure(data=[go.Pie(
                    labels=labels,
                    values=values,
                    hole=.4,
                    marker_colors=['#e53e3e', '#ed8936', '#48bb78', '#4299e1']
                )])
                
                fig.update_layout(
                    title="Destinação do Resultado Líquido Positivo",
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("⚠️ Não há resultado líquido positivo para distribuição.")
        
        # Premissas utilizadas
        st.markdown("---")
        st.markdown("#### ⚙️ Premissas Utilizadas")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            **Reservas:**
            - Reserva Legal: {resultado['premissas']['pct_reserva_legal']*100:.1f}%
            - Reserva Investimento: {resultado['premissas']['pct_reserva_investimento']*100:.1f}%
            """)
        with col2:
            st.markdown(f"""
            **Distribuição:**
            - Frequência: {resultado['premissas']['frequencia']}
            - % a Distribuir: {resultado['premissas']['pct_distribuir']*100:.1f}%
            """)


# ============================================
# MÓDULO REALIZADO - LANÇAMENTOS
# ============================================

def pagina_lancar_realizado():
    """Página para lançar dados realizados mensais"""
    
    st.title("✅ Lançar Realizado")
    st.markdown("*Registre os valores realizados para comparar com o orçado*")
    
    motor = st.session_state.motor
    
    # Verificar se tem cliente/filial selecionado
    if not st.session_state.cliente_id or not st.session_state.filial_id:
        st.warning("⚠️ Selecione um cliente e filial para lançar dados realizados.")
        return
    
    if st.session_state.filial_id == "consolidado":
        st.warning("⚠️ Não é possível lançar realizado na visão consolidada. Selecione uma filial específica.")
        return
    
    # Inicializar manager de realizado
    if 'realizado_manager' not in st.session_state:
        st.session_state.realizado_manager = RealizadoManager()
    
    realizado_mgr = st.session_state.realizado_manager
    
    # Seletor de mês
    MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        mes_selecionado = st.selectbox(
            "📅 Mês de Referência",
            range(12),
            format_func=lambda x: MESES[x],
            key="mes_realizado"
        )
    
    with col2:
        ano = st.number_input("Ano", value=2026, min_value=2024, max_value=2030)
    
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Carregar Mês", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    
    # Carregar dados existentes ou criar novo
    realizado_anual = realizado_mgr.carregar_realizado(
        st.session_state.cliente_id,
        st.session_state.filial_id,
        ano
    )
    
    lancamento = realizado_anual.get_mes(mes_selecionado)
    if not lancamento:
        lancamento = LancamentoMesRealizado(mes=mes_selecionado, ano=ano)
    
    # Tabs de lançamento
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "💰 Receitas/Sessões", 
        "📋 Despesas Fixas", 
        "👥 Folha de Pagamento",
        "💳 Impostos",
        "📝 Observações"
    ])
    
    # ===== TAB 1: RECEITAS/SESSÕES =====
    with tab1:
        st.subheader("📊 Sessões e Receitas por Serviço")
        
        # Calcular orçado para comparação
        motor.calcular_receita_bruta_total()
        
        st.markdown("##### Serviços")
        
        cols_header = st.columns([3, 2, 2, 2, 2])
        cols_header[0].markdown("**Serviço**")
        cols_header[1].markdown("**Sessões Orçadas**")
        cols_header[2].markdown("**Sessões Realizadas**")
        cols_header[3].markdown("**Receita Orçada**")
        cols_header[4].markdown("**Receita Realizada**")
        
        sessoes_realizadas = {}
        receitas_realizadas = {}
        
        for nome_servico in motor.servicos.keys():
            cols = st.columns([3, 2, 2, 2, 2])
            
            sessoes_orcadas = motor.calcular_sessoes_mes(nome_servico, mes_selecionado)
            receita_orcada = motor.calcular_receita_servico_mes(nome_servico, mes_selecionado)
            
            cols[0].markdown(f"**{nome_servico}**")
            cols[1].markdown(f"{sessoes_orcadas:.0f}")
            
            sessoes_realizadas[nome_servico] = cols[2].number_input(
                f"Sessões {nome_servico}",
                min_value=0,
                value=int(lancamento.sessoes_por_servico.get(nome_servico, 0)),
                key=f"sess_real_{nome_servico}",
                label_visibility="collapsed"
            )
            
            cols[3].markdown(f"R$ {receita_orcada:,.2f}")
            
            receitas_realizadas[nome_servico] = cols[4].number_input(
                f"Receita {nome_servico}",
                min_value=0.0,
                value=float(lancamento.receita_por_servico.get(nome_servico, 0.0)),
                key=f"rec_real_{nome_servico}",
                label_visibility="collapsed",
                format="%.2f"
            )
        
        # Totais
        st.markdown("---")
        total_sessoes_orcadas = sum(motor.calcular_sessoes_mes(s, mes_selecionado) for s in motor.servicos.keys())
        total_receita_orcada = motor.receita_bruta.get("Total", [0]*12)[mes_selecionado]
        total_sessoes_realizadas = sum(sessoes_realizadas.values())
        total_receita_realizada = sum(receitas_realizadas.values())
        
        cols_total = st.columns([3, 2, 2, 2, 2])
        cols_total[0].markdown("**TOTAL**")
        cols_total[1].markdown(f"**{total_sessoes_orcadas:.0f}**")
        cols_total[2].markdown(f"**{total_sessoes_realizadas}**")
        cols_total[3].markdown(f"**R$ {total_receita_orcada:,.2f}**")
        cols_total[4].markdown(f"**R$ {total_receita_realizada:,.2f}**")
        
        # Variação
        var_sessoes = total_sessoes_realizadas - total_sessoes_orcadas
        var_receita = total_receita_realizada - total_receita_orcada
        
        col_var1, col_var2 = st.columns(2)
        with col_var1:
            cor = "green" if var_sessoes >= 0 else "red"
            st.markdown(f"**Variação Sessões:** :{cor}[{'+' if var_sessoes >= 0 else ''}{var_sessoes:.0f}]")
        with col_var2:
            cor = "green" if var_receita >= 0 else "red"
            st.markdown(f"**Variação Receita:** :{cor}[{'+' if var_receita >= 0 else ''}R$ {var_receita:,.2f}]")
    
    # ===== TAB 2: DESPESAS FIXAS =====
    with tab2:
        st.subheader("📋 Despesas Fixas Realizadas")
        
        cols_header = st.columns([3, 2, 2, 2])
        cols_header[0].markdown("**Despesa**")
        cols_header[1].markdown("**Orçado**")
        cols_header[2].markdown("**Realizado**")
        cols_header[3].markdown("**Variação**")
        
        despesas_realizadas = {}
        
        for nome_desp, desp in motor.despesas_fixas.items():
            if not desp.ativa:
                continue
                
            cols = st.columns([3, 2, 2, 2])
            
            cols[0].markdown(f"{nome_desp}")
            cols[1].markdown(f"R$ {desp.valor_mensal:,.2f}")
            
            valor_realizado = cols[2].number_input(
                f"Realizado {nome_desp}",
                min_value=0.0,
                value=float(lancamento.despesas_fixas.get(nome_desp, desp.valor_mensal)),
                key=f"desp_real_{nome_desp}",
                label_visibility="collapsed",
                format="%.2f"
            )
            despesas_realizadas[nome_desp] = valor_realizado
            
            variacao = valor_realizado - desp.valor_mensal
            cor = "green" if variacao <= 0 else "red"  # Despesa menor é bom
            cols[3].markdown(f":{cor}[{'+' if variacao >= 0 else ''}R$ {variacao:,.2f}]")
        
        # Total
        st.markdown("---")
        total_desp_orcado = sum(d.valor_mensal for d in motor.despesas_fixas.values() if d.ativa)
        total_desp_realizado = sum(despesas_realizadas.values())
        
        cols_total = st.columns([3, 2, 2, 2])
        cols_total[0].markdown("**TOTAL DESPESAS**")
        cols_total[1].markdown(f"**R$ {total_desp_orcado:,.2f}**")
        cols_total[2].markdown(f"**R$ {total_desp_realizado:,.2f}**")
        var_desp = total_desp_realizado - total_desp_orcado
        cor = "green" if var_desp <= 0 else "red"
        cols_total[3].markdown(f"**:{cor}[{'+' if var_desp >= 0 else ''}R$ {var_desp:,.2f}]**")
    
    # ===== TAB 3: FOLHA DE PAGAMENTO =====
    with tab3:
        st.subheader("👥 Folha de Pagamento Realizada")
        
        folha_func_realizada = {}
        folha_fisio_realizada = {}
        prolabore_realizado = {}
        
        # Funcionários CLT
        if motor.funcionarios_clt:
            st.markdown("##### 👔 Funcionários CLT")
            for nome, func in motor.funcionarios_clt.items():
                if not func.ativo:
                    continue
                cols = st.columns([3, 2, 2])
                cols[0].markdown(f"{nome} ({func.cargo})")
                cols[1].markdown(f"Orçado: R$ {func.salario_base:,.2f}")
                folha_func_realizada[nome] = cols[2].number_input(
                    f"Folha {nome}",
                    min_value=0.0,
                    value=float(lancamento.folha_funcionarios.get(nome, func.salario_base)),
                    key=f"folha_func_{nome}",
                    label_visibility="collapsed",
                    format="%.2f"
                )
        
        # Sócios Pró-labore
        if motor.socios_prolabore:
            st.markdown("##### 👔 Sócios (Pró-labore)")
            for nome, socio in motor.socios_prolabore.items():
                if not socio.ativo:
                    continue
                cols = st.columns([3, 2, 2])
                cols[0].markdown(f"{nome}")
                cols[1].markdown(f"Orçado: R$ {socio.prolabore:,.2f}")
                prolabore_realizado[nome] = cols[2].number_input(
                    f"Prolabore {nome}",
                    min_value=0.0,
                    value=float(lancamento.prolabore_socios.get(nome, socio.prolabore)),
                    key=f"prolabore_{nome}",
                    label_visibility="collapsed",
                    format="%.2f"
                )
        
        # Total Folha
        st.markdown("---")
        total_folha_realizada = (
            sum(folha_func_realizada.values()) + 
            sum(folha_fisio_realizada.values()) + 
            sum(prolabore_realizado.values())
        )
        st.metric("Total Folha Realizada", f"R$ {total_folha_realizada:,.2f}")
    
    # ===== TAB 4: IMPOSTOS =====
    with tab4:
        st.subheader("💳 Impostos e Taxas")
        
        col1, col2 = st.columns(2)
        
        with col1:
            imposto_simples = st.number_input(
                "Simples Nacional / DAS",
                min_value=0.0,
                value=float(lancamento.imposto_simples),
                format="%.2f",
                key="imposto_simples"
            )
        
        with col2:
            taxas_cartao = st.number_input(
                "Taxas de Cartão",
                min_value=0.0,
                value=float(lancamento.taxas_cartao),
                format="%.2f",
                key="taxas_cartao"
            )
        
        outros_impostos = st.number_input(
            "Outros Impostos/Taxas",
            min_value=0.0,
            value=float(lancamento.outros_impostos),
            format="%.2f",
            key="outros_impostos"
        )
    
    # ===== TAB 5: OBSERVAÇÕES =====
    with tab5:
        st.subheader("📝 Observações do Mês")
        
        observacoes = st.text_area(
            "Observações",
            value=lancamento.observacoes,
            height=150,
            placeholder="Registre observações importantes sobre o mês...",
            key="obs_realizado"
        )
        
        status = st.selectbox(
            "Status do Lançamento",
            ["rascunho", "confirmado", "fechado"],
            index=["rascunho", "confirmado", "fechado"].index(lancamento.status),
            key="status_realizado"
        )
    
    # ===== SALVAR =====
    st.markdown("---")
    
    col_save1, col_save2, col_save3 = st.columns([2, 1, 1])
    
    with col_save1:
        if st.button("💾 Salvar Lançamento", type="primary", use_container_width=True):
            # Atualizar objeto de lançamento
            lancamento.sessoes_por_servico = {k: int(v) for k, v in sessoes_realizadas.items()}
            lancamento.receita_por_servico = receitas_realizadas
            lancamento.despesas_fixas = despesas_realizadas
            lancamento.folha_funcionarios = folha_func_realizada
            lancamento.folha_fisioterapeutas = folha_fisio_realizada
            lancamento.prolabore_socios = prolabore_realizado
            lancamento.imposto_simples = imposto_simples
            lancamento.taxas_cartao = taxas_cartao
            lancamento.outros_impostos = outros_impostos
            lancamento.observacoes = observacoes
            lancamento.status = status
            lancamento.data_lancamento = datetime.now().isoformat()
            
            # Salvar
            realizado_mgr.salvar_lancamento_mes(
                st.session_state.cliente_id,
                st.session_state.filial_id,
                lancamento,
                ano
            )
            
            st.success(f"✅ Lançamento de {MESES[mes_selecionado]}/{ano} salvo com sucesso!")
    
    with col_save2:
        if st.button("🗑️ Limpar", use_container_width=True):
            st.rerun()
    
    with col_save3:
        # Mostrar última atualização
        if lancamento.data_lancamento:
            try:
                dt = datetime.fromisoformat(lancamento.data_lancamento)
                st.caption(f"📅 Última atualização: {dt.strftime('%d/%m/%Y %H:%M')}")
            except:
                pass


# ============================================
# MÓDULO REALIZADO - COMPARATIVO
# ============================================

def pagina_orcado_realizado():
    """Página de comparativo Orçado x Realizado - Análise Mensal"""
    
    st.title("📊 Orçado x Realizado")
    st.markdown("*Análise comparativa mensal de performance*")
    
    motor = st.session_state.motor
    
    # Verificar se tem cliente/filial selecionado
    if not st.session_state.cliente_id or not st.session_state.filial_id:
        st.warning("⚠️ Selecione um cliente e filial para ver o comparativo.")
        return
    
    # Inicializar manager de realizado
    if 'realizado_manager' not in st.session_state:
        st.session_state.realizado_manager = RealizadoManager()
    
    realizado_mgr = st.session_state.realizado_manager
    
    MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    MESES_FULL = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    # Seletor de período
    col1, col2 = st.columns(2)
    
    with col1:
        ano = st.number_input("Ano", value=2026, min_value=2024, max_value=2030, key="ano_comparativo")
    
    with col2:
        mes_selecionado = st.selectbox(
            "📅 Mês de Análise",
            range(12),
            format_func=lambda x: MESES_FULL[x],
            key="mes_comparativo"
        )
    
    st.markdown("---")
    
    # Carregar dados
    realizado_anual = realizado_mgr.carregar_realizado(
        st.session_state.cliente_id,
        st.session_state.filial_id,
        ano
    )
    
    # Calcular orçado
    motor.calcular_receita_bruta_total()
    motor.calcular_deducoes_total()
    
    # Obter lançamento do mês
    lanc = realizado_anual.get_mes(mes_selecionado) or LancamentoMesRealizado(mes=mes_selecionado)
    
    # ===== HEADER DO MÊS =====
    st.subheader(f"🎯 Análise de {MESES_FULL[mes_selecionado]}/{ano}")
    
    # Status do lançamento
    if lanc.status == "fechado":
        st.success("✅ Mês fechado e conferido")
    elif lanc.status == "confirmado":
        st.info("📋 Lançamento confirmado")
    else:
        st.warning("⏳ Lançamento pendente ou em rascunho")
    
    # ===== KPIs DO MÊS =====
    st.markdown("### 📊 Indicadores do Mês")
    
    # Valores ORÇADOS do mês específico
    receita_orcada = motor.receita_bruta.get("Total", [0]*12)[mes_selecionado]
    receita_realizada = lanc.receita_bruta
    
    sessoes_orcadas = sum(motor.calcular_sessoes_mes(s, mes_selecionado) for s in motor.servicos.keys())
    sessoes_realizadas = lanc.total_sessoes
    
    despesas_orcadas = sum(d.valor_mensal for d in motor.despesas_fixas.values() if d.ativa)
    despesas_realizadas = lanc.total_despesas_fixas
    
    folha_orcada = motor.custo_pessoal_mensal
    folha_realizada = lanc.total_folha
    
    # Cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        var_receita = receita_realizada - receita_orcada
        var_pct = (var_receita / receita_orcada * 100) if receita_orcada > 0 else 0
        icone = "🟢" if var_pct >= -5 else ("🟡" if var_pct >= -15 else "🔴")
        
        st.metric(
            label="💰 Receita",
            value=f"R$ {receita_realizada:,.0f}",
            delta=f"{var_pct:+.1f}% ({'+' if var_receita >= 0 else ''}R$ {var_receita:,.0f})",
            delta_color="normal" if var_receita >= 0 else "inverse"
        )
        st.caption(f"Orçado: R$ {receita_orcada:,.0f}")
    
    with col2:
        var_sessoes = sessoes_realizadas - sessoes_orcadas
        var_pct_sess = (var_sessoes / sessoes_orcadas * 100) if sessoes_orcadas > 0 else 0
        
        st.metric(
            label="📊 Sessões",
            value=f"{sessoes_realizadas:,.0f}",
            delta=f"{var_pct_sess:+.1f}% ({'+' if var_sessoes >= 0 else ''}{var_sessoes:.0f})",
            delta_color="normal" if var_sessoes >= 0 else "inverse"
        )
        st.caption(f"Orçado: {sessoes_orcadas:,.0f}")
    
    with col3:
        var_desp = despesas_realizadas - despesas_orcadas
        var_pct_desp = (var_desp / despesas_orcadas * 100) if despesas_orcadas > 0 else 0
        
        st.metric(
            label="📋 Despesas Fixas",
            value=f"R$ {despesas_realizadas:,.0f}",
            delta=f"{var_pct_desp:+.1f}%",
            delta_color="inverse" if var_desp > 0 else "normal"  # Menor é melhor
        )
        st.caption(f"Orçado: R$ {despesas_orcadas:,.0f}")
    
    with col4:
        var_folha = folha_realizada - folha_orcada
        var_pct_folha = (var_folha / folha_orcada * 100) if folha_orcada > 0 else 0
        
        st.metric(
            label="👥 Folha",
            value=f"R$ {folha_realizada:,.0f}",
            delta=f"{var_pct_folha:+.1f}%",
            delta_color="inverse" if var_folha > 0 else "normal"
        )
        st.caption(f"Orçado: R$ {folha_orcada:,.0f}")
    
    st.markdown("---")
    
    # ===== DETALHAMENTO POR SERVIÇO =====
    st.markdown("### 💼 Detalhamento por Serviço")
    
    dados_servicos = []
    for nome_srv in motor.servicos.keys():
        sessoes_orc = motor.calcular_sessoes_mes(nome_srv, mes_selecionado)
        receita_orc = motor.calcular_receita_servico_mes(nome_srv, mes_selecionado)
        
        sessoes_real = lanc.sessoes_por_servico.get(nome_srv, 0)
        receita_real = lanc.receita_por_servico.get(nome_srv, 0.0)
        
        var_sess = sessoes_real - sessoes_orc
        var_rec = receita_real - receita_orc
        
        var_pct_sess = (var_sess / sessoes_orc * 100) if sessoes_orc > 0 else 0
        var_pct_rec = (var_rec / receita_orc * 100) if receita_orc > 0 else 0
        
        status = "🟢" if abs(var_pct_rec) <= 5 else ("🟡" if abs(var_pct_rec) <= 15 else "🔴")
        
        dados_servicos.append({
            "Serviço": nome_srv,
            "Sessões Orç.": f"{sessoes_orc:.0f}",
            "Sessões Real.": f"{sessoes_real}",
            "Var. Sessões": f"{var_pct_sess:+.1f}%",
            "Receita Orç.": f"R$ {receita_orc:,.2f}",
            "Receita Real.": f"R$ {receita_real:,.2f}",
            "Var. Receita": f"{var_pct_rec:+.1f}%",
            "Status": status
        })
    
    df_servicos = pd.DataFrame(dados_servicos)
    st.dataframe(df_servicos, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # ===== DETALHAMENTO DESPESAS FIXAS =====
    st.markdown("### 📋 Detalhamento Despesas Fixas")
    
    dados_despesas = []
    for nome_desp, desp in motor.despesas_fixas.items():
        if not desp.ativa:
            continue
        
        valor_orc = desp.valor_mensal
        valor_real = lanc.despesas_fixas.get(nome_desp, 0.0)
        var = valor_real - valor_orc
        var_pct = (var / valor_orc * 100) if valor_orc > 0 else 0
        
        # Para despesas, menor é melhor
        status = "🟢" if var_pct <= 5 else ("🟡" if var_pct <= 15 else "🔴")
        
        dados_despesas.append({
            "Despesa": nome_desp,
            "Categoria": desp.categoria,
            "Orçado": f"R$ {valor_orc:,.2f}",
            "Realizado": f"R$ {valor_real:,.2f}",
            "Variação R$": f"R$ {var:+,.2f}",
            "Variação %": f"{var_pct:+.1f}%",
            "Status": status
        })
    
    if dados_despesas:
        df_despesas = pd.DataFrame(dados_despesas)
        st.dataframe(df_despesas, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma despesa fixa cadastrada")
    
    st.markdown("---")
    
    # ===== EVOLUÇÃO ANUAL =====
    st.markdown("### 📈 Evolução Anual (Todos os Meses)")
    
    # Preparar dados
    receitas_orcadas = motor.receita_bruta.get("Total", [0]*12)
    receitas_realizadas = realizado_anual.get_receita_por_mes()
    
    # Gráfico
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        name="Orçado",
        x=MESES,
        y=receitas_orcadas,
        marker_color="#90CAF9",
        text=[f"R$ {v:,.0f}" for v in receitas_orcadas],
        textposition='outside'
    ))
    
    fig.add_trace(go.Bar(
        name="Realizado",
        x=MESES,
        y=receitas_realizadas,
        marker_color="#4CAF50",
        text=[f"R$ {v:,.0f}" if v > 0 else "" for v in receitas_realizadas],
        textposition='outside'
    ))
    
    # Destacar mês selecionado
    fig.add_vline(
        x=mes_selecionado, 
        line_dash="dash", 
        line_color="red",
        annotation_text=f"← {MESES[mes_selecionado]}"
    )
    
    fig.update_layout(
        barmode='group',
        title="Receita Orçada x Realizada por Mês",
        xaxis_title="Mês",
        yaxis_title="Receita (R$)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # ===== TABELA RESUMO ANUAL =====
    st.markdown("### 📋 Resumo Mensal")
    
    dados_tabela = []
    acum_orcado = 0
    acum_realizado = 0
    
    for m in range(12):
        lanc_m = realizado_anual.get_mes(m) or LancamentoMesRealizado(mes=m)
        orcado = receitas_orcadas[m]
        realizado = lanc_m.receita_bruta
        variacao = realizado - orcado
        var_pct = (variacao / orcado * 100) if orcado > 0 else 0
        
        acum_orcado += orcado
        acum_realizado += realizado
        
        status = "🟢" if abs(var_pct) <= 5 else ("🟡" if abs(var_pct) <= 15 else "🔴")
        lancado = "✅" if lanc_m.receita_bruta > 0 else "⏳"
        
        # Destacar mês atual
        mes_nome = f"**{MESES[m]}**" if m == mes_selecionado else MESES[m]
        
        dados_tabela.append({
            "Mês": MESES[m],
            "Orçado": f"R$ {orcado:,.2f}",
            "Realizado": f"R$ {realizado:,.2f}" if realizado > 0 else "-",
            "Variação": f"{var_pct:+.1f}%" if realizado > 0 else "-",
            "Acum. Orç.": f"R$ {acum_orcado:,.2f}",
            "Acum. Real.": f"R$ {acum_realizado:,.2f}" if acum_realizado > 0 else "-",
            "Status": status if realizado > 0 else "⏳",
            "Lançado": lancado
        })
    
    df_tabela = pd.DataFrame(dados_tabela)
    
    # Destacar linha do mês selecionado
    st.dataframe(
        df_tabela, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "Mês": st.column_config.TextColumn("Mês", width="small"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Lançado": st.column_config.TextColumn("", width="small"),
        }
    )
    
    # ===== RESULTADO DO MÊS (MINI DRE) =====
    st.markdown("---")
    st.markdown(f"### 📊 Resultado de {MESES_FULL[mes_selecionado]} (Mini DRE)")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**ORÇADO**")
        rec_liq_orc = receita_orcada * 0.94  # Estimativa deduções 6%
        resultado_orc = rec_liq_orc - despesas_orcadas - folha_orcada
        margem_orc = (resultado_orc / receita_orcada * 100) if receita_orcada > 0 else 0
        
        st.write(f"Receita Bruta: R$ {receita_orcada:,.2f}")
        st.write(f"(-) Deduções (~6%): R$ {receita_orcada * 0.06:,.2f}")
        st.write(f"Receita Líquida: R$ {rec_liq_orc:,.2f}")
        st.write(f"(-) Despesas Fixas: R$ {despesas_orcadas:,.2f}")
        st.write(f"(-) Folha: R$ {folha_orcada:,.2f}")
        st.markdown(f"**Resultado: R$ {resultado_orc:,.2f}**")
        st.markdown(f"**Margem: {margem_orc:.1f}%**")
    
    with col2:
        st.markdown("**REALIZADO**")
        deducoes_real = lanc.taxas_cartao + lanc.imposto_simples + lanc.outros_impostos
        rec_liq_real = receita_realizada - deducoes_real
        resultado_real = rec_liq_real - despesas_realizadas - folha_realizada
        margem_real = (resultado_real / receita_realizada * 100) if receita_realizada > 0 else 0
        
        st.write(f"Receita Bruta: R$ {receita_realizada:,.2f}")
        st.write(f"(-) Deduções: R$ {deducoes_real:,.2f}")
        st.write(f"Receita Líquida: R$ {rec_liq_real:,.2f}")
        st.write(f"(-) Despesas Fixas: R$ {despesas_realizadas:,.2f}")
        st.write(f"(-) Folha: R$ {folha_realizada:,.2f}")
        st.markdown(f"**Resultado: R$ {resultado_real:,.2f}**")
        st.markdown(f"**Margem: {margem_real:.1f}%**")
    
    with col3:
        st.markdown("**VARIAÇÃO**")
        var_resultado = resultado_real - resultado_orc
        var_margem = margem_real - margem_orc
        
        cor_res = "green" if var_resultado >= 0 else "red"
        cor_marg = "green" if var_margem >= 0 else "red"
        
        st.write(f"Receita: {'+' if receita_realizada - receita_orcada >= 0 else ''}R$ {receita_realizada - receita_orcada:,.2f}")
        st.write(f"Deduções: {'+' if deducoes_real - receita_orcada * 0.06 >= 0 else ''}R$ {deducoes_real - receita_orcada * 0.06:,.2f}")
        st.write(f"Rec. Líquida: {'+' if rec_liq_real - rec_liq_orc >= 0 else ''}R$ {rec_liq_real - rec_liq_orc:,.2f}")
        st.write(f"Despesas: {'+' if despesas_realizadas - despesas_orcadas >= 0 else ''}R$ {despesas_realizadas - despesas_orcadas:,.2f}")
        st.write(f"Folha: {'+' if folha_realizada - folha_orcada >= 0 else ''}R$ {folha_realizada - folha_orcada:,.2f}")
        st.markdown(f"**Resultado: :{cor_res}[{'+' if var_resultado >= 0 else ''}R$ {var_resultado:,.2f}]**")
        st.markdown(f"**Margem: :{cor_marg}[{'+' if var_margem >= 0 else ''}{var_margem:.1f}pp]**")
    
    # ===== AÇÕES =====
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✏️ Editar Lançamento", use_container_width=True):
            st.session_state.mes_realizado = mes_selecionado
            st.info("👆 Vá para '✅ Lançar Realizado' no menu lateral")
    
    with col2:
        if st.button("📥 Exportar Excel", use_container_width=True):
            st.info("🚧 Em desenvolvimento...")
    
    with col3:
        if st.button("📄 Gerar Relatório", use_container_width=True):
            st.info("🚧 Em desenvolvimento...")


# ============================================
# MÓDULO REALIZADO - DRE COMPARATIVO
# ============================================

def pagina_dre_comparativo():
    """Página de DRE Comparativo Orçado x Realizado"""
    
    st.title("📊 DRE Comparativo")
    st.markdown("*Demonstração de Resultado: Orçado x Realizado*")
    
    motor = st.session_state.motor
    
    # Verificar se tem cliente/filial selecionado
    if not st.session_state.cliente_id or not st.session_state.filial_id:
        st.warning("⚠️ Selecione um cliente e filial para ver o DRE comparativo.")
        return
    
    # Inicializar manager de realizado
    if 'realizado_manager' not in st.session_state:
        st.session_state.realizado_manager = RealizadoManager()
    
    realizado_mgr = st.session_state.realizado_manager
    
    MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    MESES_FULL = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    
    # Seletor de período
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        ano = st.number_input("Ano", value=2026, min_value=2024, max_value=2030, key="ano_dre_comp")
    
    with col2:
        mes_selecionado = st.selectbox(
            "📅 Mês",
            range(12),
            format_func=lambda x: MESES_FULL[x],
            key="mes_dre_comp"
        )
    
    with col3:
        visao = st.radio(
            "Visão",
            ["Mensal", "Acumulado YTD"],
            horizontal=True,
            key="visao_dre_comp"
        )
    
    st.markdown("---")
    
    # Carregar dados realizados
    realizado_anual = realizado_mgr.carregar_realizado(
        st.session_state.cliente_id,
        st.session_state.filial_id,
        ano
    )
    
    # Calcular orçado
    motor.calcular_receita_bruta_total()
    motor.calcular_deducoes_total()
    
    # ===== FUNÇÃO AUXILIAR PARA CALCULAR DRE =====
    def calcular_linha_dre(meses_range):
        """Calcula valores do DRE para um range de meses"""
        
        # ORÇADO
        receita_bruta_orc = sum(motor.receita_bruta.get("Total", [0]*12)[m] for m in meses_range)
        
        # Deduções orçadas
        impostos_orc = sum(motor.deducoes.get("Simples Nacional", [0]*12)[m] for m in meses_range)
        taxas_cartao_orc = sum(motor.deducoes.get("Taxa Cartão Crédito", [0]*12)[m] + 
                               motor.deducoes.get("Taxa Cartão Débito", [0]*12)[m] +
                               motor.deducoes.get("Taxa Antecipação", [0]*12)[m] 
                               for m in meses_range)
        total_deducoes_orc = sum(motor.deducoes.get("Total Deduções", [0]*12)[m] for m in meses_range)
        
        receita_liq_orc = receita_bruta_orc - total_deducoes_orc
        
        # Custos de pessoal orçados (mensal * qtd meses)
        num_meses = len(meses_range)
        folha_fisio_orc = motor.custo_pessoal_mensal * 0.5 * num_meses  # Estimativa 50% fisios
        folha_func_orc = sum(f.salario_base for f in motor.funcionarios_clt.values() if f.ativo) * num_meses
        prolabore_orc = sum(s.prolabore for s in motor.socios_prolabore.values() if s.ativo) * num_meses
        total_pessoal_orc = folha_fisio_orc + folha_func_orc + prolabore_orc
        
        # Despesas fixas orçadas
        despesas_fixas_orc = sum(d.valor_mensal for d in motor.despesas_fixas.values() if d.ativa) * num_meses
        
        # EBITDA
        ebitda_orc = receita_liq_orc - total_pessoal_orc - despesas_fixas_orc
        margem_orc = (ebitda_orc / receita_bruta_orc * 100) if receita_bruta_orc > 0 else 0
        
        # REALIZADO
        receita_bruta_real = 0
        impostos_real = 0
        taxas_cartao_real = 0
        folha_fisio_real = 0
        folha_func_real = 0
        prolabore_real = 0
        despesas_fixas_real = 0
        
        for m in meses_range:
            lanc = realizado_anual.get_mes(m)
            if lanc:
                receita_bruta_real += lanc.receita_bruta
                impostos_real += lanc.imposto_simples + lanc.outros_impostos
                taxas_cartao_real += lanc.taxas_cartao
                folha_fisio_real += sum(lanc.folha_fisioterapeutas.values())
                folha_func_real += sum(lanc.folha_funcionarios.values())
                prolabore_real += sum(lanc.prolabore_socios.values())
                despesas_fixas_real += lanc.total_despesas_fixas
        
        total_deducoes_real = impostos_real + taxas_cartao_real
        receita_liq_real = receita_bruta_real - total_deducoes_real
        total_pessoal_real = folha_fisio_real + folha_func_real + prolabore_real
        ebitda_real = receita_liq_real - total_pessoal_real - despesas_fixas_real
        margem_real = (ebitda_real / receita_bruta_real * 100) if receita_bruta_real > 0 else 0
        
        return {
            "receita_bruta": {"orc": receita_bruta_orc, "real": receita_bruta_real},
            "impostos": {"orc": impostos_orc, "real": impostos_real},
            "taxas_cartao": {"orc": taxas_cartao_orc, "real": taxas_cartao_real},
            "total_deducoes": {"orc": total_deducoes_orc, "real": total_deducoes_real},
            "receita_liq": {"orc": receita_liq_orc, "real": receita_liq_real},
            "folha_fisio": {"orc": folha_fisio_orc, "real": folha_fisio_real},
            "folha_func": {"orc": folha_func_orc, "real": folha_func_real},
            "prolabore": {"orc": prolabore_orc, "real": prolabore_real},
            "total_pessoal": {"orc": total_pessoal_orc, "real": total_pessoal_real},
            "despesas_fixas": {"orc": despesas_fixas_orc, "real": despesas_fixas_real},
            "ebitda": {"orc": ebitda_orc, "real": ebitda_real},
            "margem": {"orc": margem_orc, "real": margem_real},
        }
    
    # Calcular DRE baseado na visão
    if visao == "Mensal":
        meses_range = [mes_selecionado]
        titulo_periodo = f"{MESES_FULL[mes_selecionado]}/{ano}"
    else:
        meses_range = list(range(mes_selecionado + 1))
        titulo_periodo = f"Jan a {MESES[mes_selecionado]}/{ano}"
    
    dre = calcular_linha_dre(meses_range)
    
    # ===== HEADER =====
    st.subheader(f"📊 DRE - {titulo_periodo}")
    
    # Status do mês
    lanc_atual = realizado_anual.get_mes(mes_selecionado)
    if lanc_atual and lanc_atual.receita_bruta > 0:
        st.success(f"✅ Dados realizados lançados para {MESES_FULL[mes_selecionado]}")
    else:
        st.warning(f"⚠️ Dados realizados pendentes para {MESES_FULL[mes_selecionado]}")
    
    # ===== TABELA DRE =====
    st.markdown("### 📋 Demonstração de Resultado")
    
    # Função para formatar linha com cor
    def get_status_icon(var_pct, inverter=False):
        """Retorna ícone baseado na variação"""
        if inverter:
            if var_pct <= -5:
                return "🟢"
            elif var_pct <= 5:
                return "🟡"
            else:
                return "🔴"
        else:
            if var_pct >= 5:
                return "🟢"
            elif var_pct >= -5:
                return "🟡"
            else:
                return "🔴"
    
    # Construir dados para DataFrame
    dados_dre = []
    
    # RECEITA BRUTA
    var_pct = ((dre['receita_bruta']['real'] - dre['receita_bruta']['orc']) / dre['receita_bruta']['orc'] * 100) if dre['receita_bruta']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "📈 RECEITA BRUTA",
        "Orçado": f"R$ {dre['receita_bruta']['orc']:,.2f}",
        "Realizado": f"R$ {dre['receita_bruta']['real']:,.2f}",
        "Variação R$": f"R$ {dre['receita_bruta']['real'] - dre['receita_bruta']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct)} {var_pct:+.1f}%"
    })
    
    # Impostos
    var_pct = ((dre['impostos']['real'] - dre['impostos']['orc']) / dre['impostos']['orc'] * 100) if dre['impostos']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "    (-) Impostos (Simples/DAS)",
        "Orçado": f"R$ {dre['impostos']['orc']:,.2f}",
        "Realizado": f"R$ {dre['impostos']['real']:,.2f}",
        "Variação R$": f"R$ {dre['impostos']['real'] - dre['impostos']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%"
    })
    
    # Taxas Cartão
    var_pct = ((dre['taxas_cartao']['real'] - dre['taxas_cartao']['orc']) / dre['taxas_cartao']['orc'] * 100) if dre['taxas_cartao']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "    (-) Taxas de Cartão",
        "Orçado": f"R$ {dre['taxas_cartao']['orc']:,.2f}",
        "Realizado": f"R$ {dre['taxas_cartao']['real']:,.2f}",
        "Variação R$": f"R$ {dre['taxas_cartao']['real'] - dre['taxas_cartao']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%" if dre['taxas_cartao']['orc'] > 0 else "—"
    })
    
    # Total Deduções
    var_pct = ((dre['total_deducoes']['real'] - dre['total_deducoes']['orc']) / dre['total_deducoes']['orc'] * 100) if dre['total_deducoes']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "📉 (-) TOTAL DEDUÇÕES",
        "Orçado": f"R$ {dre['total_deducoes']['orc']:,.2f}",
        "Realizado": f"R$ {dre['total_deducoes']['real']:,.2f}",
        "Variação R$": f"R$ {dre['total_deducoes']['real'] - dre['total_deducoes']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%"
    })
    
    # Receita Líquida
    var_pct = ((dre['receita_liq']['real'] - dre['receita_liq']['orc']) / dre['receita_liq']['orc'] * 100) if dre['receita_liq']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "💰 RECEITA LÍQUIDA",
        "Orçado": f"R$ {dre['receita_liq']['orc']:,.2f}",
        "Realizado": f"R$ {dre['receita_liq']['real']:,.2f}",
        "Variação R$": f"R$ {dre['receita_liq']['real'] - dre['receita_liq']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct)} {var_pct:+.1f}%"
    })
    
    # Remuneração Fisioterapeutas
    var_pct = ((dre['folha_fisio']['real'] - dre['folha_fisio']['orc']) / dre['folha_fisio']['orc'] * 100) if dre['folha_fisio']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "    (-) Remuneração Fisioterapeutas",
        "Orçado": f"R$ {dre['folha_fisio']['orc']:,.2f}",
        "Realizado": f"R$ {dre['folha_fisio']['real']:,.2f}",
        "Variação R$": f"R$ {dre['folha_fisio']['real'] - dre['folha_fisio']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%" if dre['folha_fisio']['orc'] > 0 else "—"
    })
    
    # Folha Funcionários
    var_pct = ((dre['folha_func']['real'] - dre['folha_func']['orc']) / dre['folha_func']['orc'] * 100) if dre['folha_func']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "    (-) Folha Funcionários CLT",
        "Orçado": f"R$ {dre['folha_func']['orc']:,.2f}",
        "Realizado": f"R$ {dre['folha_func']['real']:,.2f}",
        "Variação R$": f"R$ {dre['folha_func']['real'] - dre['folha_func']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%" if dre['folha_func']['orc'] > 0 else "—"
    })
    
    # Pró-labore
    var_pct = ((dre['prolabore']['real'] - dre['prolabore']['orc']) / dre['prolabore']['orc'] * 100) if dre['prolabore']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "    (-) Pró-labore Sócios",
        "Orçado": f"R$ {dre['prolabore']['orc']:,.2f}",
        "Realizado": f"R$ {dre['prolabore']['real']:,.2f}",
        "Variação R$": f"R$ {dre['prolabore']['real'] - dre['prolabore']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%" if dre['prolabore']['orc'] > 0 else "—"
    })
    
    # Total Pessoal
    var_pct = ((dre['total_pessoal']['real'] - dre['total_pessoal']['orc']) / dre['total_pessoal']['orc'] * 100) if dre['total_pessoal']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "👥 (-) TOTAL CUSTO PESSOAL",
        "Orçado": f"R$ {dre['total_pessoal']['orc']:,.2f}",
        "Realizado": f"R$ {dre['total_pessoal']['real']:,.2f}",
        "Variação R$": f"R$ {dre['total_pessoal']['real'] - dre['total_pessoal']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%"
    })
    
    # Despesas Fixas
    var_pct = ((dre['despesas_fixas']['real'] - dre['despesas_fixas']['orc']) / dre['despesas_fixas']['orc'] * 100) if dre['despesas_fixas']['orc'] > 0 else 0
    dados_dre.append({
        "Conta": "🏢 (-) Despesas Fixas",
        "Orçado": f"R$ {dre['despesas_fixas']['orc']:,.2f}",
        "Realizado": f"R$ {dre['despesas_fixas']['real']:,.2f}",
        "Variação R$": f"R$ {dre['despesas_fixas']['real'] - dre['despesas_fixas']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct, True)} {var_pct:+.1f}%"
    })
    
    # EBITDA
    var_pct = ((dre['ebitda']['real'] - dre['ebitda']['orc']) / dre['ebitda']['orc'] * 100) if dre['ebitda']['orc'] != 0 else 0
    dados_dre.append({
        "Conta": "⭐ EBITDA",
        "Orçado": f"R$ {dre['ebitda']['orc']:,.2f}",
        "Realizado": f"R$ {dre['ebitda']['real']:,.2f}",
        "Variação R$": f"R$ {dre['ebitda']['real'] - dre['ebitda']['orc']:+,.2f}",
        "Var %": f"{get_status_icon(var_pct)} {var_pct:+.1f}%"
    })
    
    # Margem EBITDA
    margem_var = dre['margem']['real'] - dre['margem']['orc']
    dados_dre.append({
        "Conta": "📊 Margem EBITDA",
        "Orçado": f"{dre['margem']['orc']:.1f}%",
        "Realizado": f"{dre['margem']['real']:.1f}%",
        "Variação R$": f"{margem_var:+.1f}pp",
        "Var %": f"{'🟢' if margem_var >= 0 else '🔴'}"
    })
    
    # Criar DataFrame e exibir
    df_dre = pd.DataFrame(dados_dre)
    
    st.dataframe(
        df_dre,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Conta": st.column_config.TextColumn("Conta", width="large"),
            "Orçado": st.column_config.TextColumn("Orçado", width="medium"),
            "Realizado": st.column_config.TextColumn("Realizado", width="medium"),
            "Variação R$": st.column_config.TextColumn("Variação R$", width="medium"),
            "Var %": st.column_config.TextColumn("Var %", width="small"),
        }
    )
    
    st.markdown("---")
    
    # ===== CARDS RESUMO =====
    st.markdown("### 🎯 Resumo de Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        var_rec = dre['receita_bruta']['real'] - dre['receita_bruta']['orc']
        var_pct = (var_rec / dre['receita_bruta']['orc'] * 100) if dre['receita_bruta']['orc'] > 0 else 0
        st.metric(
            "💰 Receita Bruta",
            f"R$ {dre['receita_bruta']['real']:,.0f}",
            f"{var_pct:+.1f}%",
            delta_color="normal" if var_pct >= 0 else "inverse"
        )
    
    with col2:
        var_ded = dre['total_deducoes']['real'] - dre['total_deducoes']['orc']
        var_pct = (var_ded / dre['total_deducoes']['orc'] * 100) if dre['total_deducoes']['orc'] > 0 else 0
        st.metric(
            "📉 Deduções",
            f"R$ {dre['total_deducoes']['real']:,.0f}",
            f"{var_pct:+.1f}%",
            delta_color="inverse" if var_pct > 0 else "normal"
        )
    
    with col3:
        var_desp = dre['despesas_fixas']['real'] - dre['despesas_fixas']['orc']
        var_pct = (var_desp / dre['despesas_fixas']['orc'] * 100) if dre['despesas_fixas']['orc'] > 0 else 0
        st.metric(
            "📋 Despesas Fixas",
            f"R$ {dre['despesas_fixas']['real']:,.0f}",
            f"{var_pct:+.1f}%",
            delta_color="inverse" if var_pct > 0 else "normal"
        )
    
    with col4:
        var_ebitda = dre['ebitda']['real'] - dre['ebitda']['orc']
        var_pct = (var_ebitda / dre['ebitda']['orc'] * 100) if dre['ebitda']['orc'] != 0 else 0
        st.metric(
            "📈 EBITDA",
            f"R$ {dre['ebitda']['real']:,.0f}",
            f"{var_pct:+.1f}%",
            delta_color="normal" if var_pct >= 0 else "inverse"
        )
    
    st.markdown("---")
    
    # ===== GRÁFICO EVOLUÇÃO MENSAL =====
    st.markdown("### 📈 Evolução Mensal do EBITDA")
    
    # Calcular EBITDA de cada mês
    ebitda_orcado = []
    ebitda_realizado = []
    
    for m in range(12):
        dre_mes = calcular_linha_dre([m])
        ebitda_orcado.append(dre_mes['ebitda']['orc'])
        ebitda_realizado.append(dre_mes['ebitda']['real'])
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        name="EBITDA Orçado",
        x=MESES,
        y=ebitda_orcado,
        mode='lines+markers',
        line=dict(color="#90CAF9", width=2),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        name="EBITDA Realizado",
        x=MESES,
        y=ebitda_realizado,
        mode='lines+markers',
        line=dict(color="#4CAF50", width=3),
        marker=dict(size=10)
    ))
    
    # Destacar mês selecionado
    fig.add_vline(
        x=mes_selecionado,
        line_dash="dash",
        line_color="red",
        annotation_text=f"← {MESES[mes_selecionado]}"
    )
    
    fig.update_layout(
        title="EBITDA Orçado x Realizado",
        xaxis_title="Mês",
        yaxis_title="EBITDA (R$)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        height=400,
        hovermode="x unified"
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # ===== DETALHAMENTO DESPESAS FIXAS =====
    with st.expander("📋 Detalhamento Despesas Fixas por Categoria"):
        
        # Agrupar por categoria
        categorias = {}
        for nome_desp, desp in motor.despesas_fixas.items():
            if not desp.ativa:
                continue
            cat = desp.categoria or "Outras"
            if cat not in categorias:
                categorias[cat] = {"orc": 0, "real": 0, "itens": []}
            
            # Orçado (por mês ou acumulado)
            valor_orc = desp.valor_mensal * len(meses_range)
            
            # Realizado
            valor_real = 0
            for m in meses_range:
                lanc = realizado_anual.get_mes(m)
                if lanc:
                    valor_real += lanc.despesas_fixas.get(nome_desp, 0)
            
            categorias[cat]["orc"] += valor_orc
            categorias[cat]["real"] += valor_real
            categorias[cat]["itens"].append({
                "nome": nome_desp,
                "orc": valor_orc,
                "real": valor_real
            })
        
        for cat, dados in categorias.items():
            var = dados["real"] - dados["orc"]
            var_pct = (var / dados["orc"] * 100) if dados["orc"] > 0 else 0
            icone = "🟢" if var_pct <= 5 else ("🟡" if var_pct <= 15 else "🔴")
            
            st.markdown(f"**{cat}** - Orç: R$ {dados['orc']:,.2f} | Real: R$ {dados['real']:,.2f} | {icone} {var_pct:+.1f}%")
            
            for item in dados["itens"]:
                var_item = item["real"] - item["orc"]
                st.caption(f"  • {item['nome']}: R$ {item['orc']:,.2f} → R$ {item['real']:,.2f} ({'+' if var_item >= 0 else ''}R$ {var_item:,.2f})")
    
    # ===== AÇÕES =====
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("✏️ Lançar Realizado", use_container_width=True, key="btn_lancar_dre"):
            st.info("👆 Vá para '✅ Lançar Realizado' no menu lateral")
    
    with col2:
        if st.button("📥 Exportar DRE Excel", use_container_width=True, key="btn_export_dre"):
            st.info("🚧 Em desenvolvimento...")
    
    with col3:
        if st.button("📄 Gerar Relatório", use_container_width=True, key="btn_relat_dre"):
            st.info("🚧 Em desenvolvimento...")



def pagina_consultor_ia():
    """Página do Consultor Financeiro IA"""
    
    st.title("🤖 Consultor Financeiro IA")
    st.markdown("*Especialista em Controladoria para Clínicas de Fisioterapia*")
    
    # Tenta importar o módulo
    try:
        from consultor_ia import (
            criar_consultor_local,
            verificar_instalacao,
            MODELOS_RECOMENDADOS
        )
        modulo_disponivel = True
    except ImportError as e:
        modulo_disponivel = False
        erro_import = str(e)
    
    if not modulo_disponivel:
        st.error(f"❌ Módulo consultor_ia não disponível: {erro_import}")
        return
    
    # Verifica Ollama
    status = verificar_instalacao()
    
    if not status["pronto"]:
        st.error("❌ **Ollama não está pronto**")
        
        for instrucao in status.get("instrucoes", []):
            st.warning(instrucao)
        
        st.markdown("""
        ### 📥 Como Instalar:
        
        **1. Baixe o Ollama:** https://ollama.ai/download
        
        **2. Inicie o servidor:**
        ```bash
        ollama serve
        ```
        
        **3. Baixe um modelo:**
        ```bash
        ollama pull qwen2.5:7b
        ```
        
        **4. Recarregue esta página**
        """)
        return
    
    st.success(f"✅ **Ollama Pronto** | Modelo: `{status['modelo_atual']}`")
    
    # Verifica se tem motor carregado
    motor = st.session_state.get("motor", None)
    
    if motor is None:
        st.warning("⚠️ **Nenhum orçamento carregado.**")
        st.info("👆 Selecione um cliente e filial no menu superior para usar o consultor.")
        return
    
    # Inicializa consultor
    if "consultor_ia" not in st.session_state:
        st.session_state.consultor_ia = criar_consultor_local(motor=motor)
    else:
        st.session_state.consultor_ia.carregar_motor(motor)
    
    consultor = st.session_state.consultor_ia
    
    # Métricas do cliente
    try:
        metricas = consultor.get_metricas_resumo()
        if metricas and "erro" not in metricas:
            st.markdown(f"### 📊 {metricas.get('empresa', '')} - {metricas.get('filial', '')}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("💰 Receita Mensal", f"R$ {metricas.get('receita_mensal', 0):,.0f}")
            with col2:
                st.metric("👥 Folha % Receita", f"{metricas.get('folha_pct', 0):.1f}%")
            with col3:
                st.metric("🩺 Profissionais", metricas.get('qtd_fisios', 0))
            with col4:
                st.metric("📋 Serviços", metricas.get('qtd_servicos', 0))
    except:
        pass
    
    st.markdown("---")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Análises Rápidas", "🎮 Simulador"])
    
    # TAB 1: CHAT
    with tab1:
        st.markdown("### 💬 Chat com o Consultor")
        
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = []
        
        # Histórico
        for msg in st.session_state.chat_messages:
            if msg["role"] == "user":
                st.markdown(f"**👤 Você:** {msg['content']}")
            else:
                st.markdown(f"**🤖 Consultor:**\n\n{msg['content']}")
            st.markdown("---")
        
        # Input
        col1, col2 = st.columns([5, 1])
        with col1:
            pergunta = st.text_input(
                "Faça uma pergunta:",
                placeholder="Ex: Por que meu fluxo de caixa fica negativo em março?",
                key="chat_input",
                label_visibility="collapsed"
            )
        with col2:
            enviar = st.button("📤 Enviar", use_container_width=True)
        
        if enviar and pergunta:
            with st.spinner("🤔 Analisando... (pode levar 15-30 segundos)"):
                try:
                    resposta = consultor.perguntar(pergunta)
                    st.session_state.chat_messages.append({"role": "user", "content": pergunta})
                    st.session_state.chat_messages.append({"role": "assistant", "content": resposta})
                    st.rerun()
                except Exception as e:
                    erro_msg = registrar_erro("BE-500", str(e), "pagina_consultor_ia/perguntar")
                    st.error(f"❌ {erro_msg}")
        
        if st.session_state.chat_messages:
            if st.button("🗑️ Limpar Conversa"):
                st.session_state.chat_messages = []
                consultor.limpar_historico()
                st.rerun()
    
    # TAB 2: ANÁLISES RÁPIDAS
    with tab2:
        st.markdown("### 📊 Análises Rápidas")
        st.markdown("Clique em um botão para gerar uma análise automática.")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🩺 Diagnóstico Completo", use_container_width=True):
                with st.spinner("Gerando diagnóstico... (30-60 segundos)"):
                    resultado = consultor.diagnostico()
                st.session_state.ultima_analise = ("Diagnóstico", resultado)
        
        with col2:
            if st.button("⚠️ Alertas e Riscos", use_container_width=True):
                with st.spinner("Identificando alertas..."):
                    resultado = consultor.alertas()
                st.session_state.ultima_analise = ("Alertas", resultado)
        
        with col3:
            if st.button("💵 Fluxo de Caixa", use_container_width=True):
                with st.spinner("Analisando fluxo de caixa..."):
                    resultado = consultor.analisar_fluxo_caixa()
                st.session_state.ultima_analise = ("Fluxo de Caixa", resultado)
        
        col4, col5, col6 = st.columns(3)
        
        with col4:
            if st.button("📈 Análise DRE", use_container_width=True):
                with st.spinner("Analisando DRE..."):
                    resultado = consultor.analisar_dre()
                st.session_state.ultima_analise = ("DRE", resultado)
        
        with col5:
            if st.button("⚖️ Ponto de Equilíbrio", use_container_width=True):
                with st.spinner("Analisando PE..."):
                    resultado = consultor.analisar_ponto_equilibrio()
                st.session_state.ultima_analise = ("Ponto de Equilíbrio", resultado)
        
        with col6:
            if st.button("📋 Relatório Executivo", use_container_width=True):
                with st.spinner("Gerando relatório... (pode levar 1 minuto)"):
                    resultado = consultor.relatorio_executivo()
                st.session_state.ultima_analise = ("Relatório Executivo", resultado)
        
        # Exibe última análise
        if "ultima_analise" in st.session_state:
            titulo, conteudo = st.session_state.ultima_analise
            st.markdown("---")
            st.markdown(f"## 📄 {titulo}")
            st.markdown(conteudo)
            
            st.download_button(
                "📥 Baixar como TXT",
                conteudo,
                file_name=f"{titulo.lower().replace(' ', '_')}.txt",
                mime="text/plain"
            )
    
    # TAB 3: SIMULADOR
    with tab3:
        st.markdown("### 🎮 Simulador 'E se?'")
        
        st.markdown("""
        Teste cenários hipotéticos e veja o impacto no orçamento.
        
        **Exemplos:**
        - "E se eu aumentar os preços em 10%?"
        - "E se eu contratar mais 2 fisioterapeutas?"
        - "E se eu reduzir o aluguel em R$ 2.000?"
        - "E se eu perder 20% das sessões de Pilates?"
        """)
        
        cenario = st.text_area(
            "Descreva o cenário que quer simular:",
            height=100,
            placeholder="Ex: E se eu demitir 1 recepcionista e aumentar o marketing em R$ 1.000/mês?"
        )
        
        if st.button("🚀 Simular Cenário", disabled=not cenario):
            with st.spinner("Simulando cenário... (30-60 segundos)"):
                try:
                    resultado = consultor.simular(cenario)
                    st.markdown("---")
                    st.markdown("## 📊 Resultado da Simulação")
                    st.markdown(resultado)
                except Exception as e:
                    erro_msg = registrar_erro("BE-500", str(e), "pagina_consultor_ia/simular")
                    st.error(f"❌ {erro_msg}")


# ============================================
# SELETOR DE CLIENTE/FILIAL (TOPO)
# ============================================

render_seletor_cliente_filial()

# ============================================
# ROTEAMENTO
# ============================================

# ============================================
# PÁGINA DE DIAGNÓSTICO PARA DESENVOLVIMENTO
# ============================================

def pagina_diagnostico_dev():
    """Página de diagnóstico COMPLETO - SOMENTE LEITURA - para identificar problemas"""
    
    st.title("🛠️ Diagnóstico Completo do Sistema")
    st.caption(f"Budget Engine v{APP_VERSION} - Ferramenta de desenvolvimento")
    
    st.warning("⚠️ Esta página é para **diagnóstico técnico**. Nenhuma edição é permitida aqui.")
    
    # Tabs de diagnóstico
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Status Geral",
        "💾 Persistência",
        "🔍 Motor Atual",
        "📁 Arquivos",
        "🧪 Validações",
        "🔬 Testes Avançados",
        "📋 Changelog",
        "🚨 Log de Erros"
    ])
    
    # ===== TAB 1: STATUS GERAL =====
    with tab1:
        st.markdown("### 📊 Status Geral do Sistema")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Versão", APP_VERSION)
            st.metric("Cliente ID", st.session_state.get('cliente_id', 'Nenhum') or "Nenhum")
        
        with col2:
            st.metric("Filial ID", st.session_state.get('filial_id', 'Nenhuma') or "Nenhuma")
            cliente_nome = st.session_state.cliente_atual.nome if st.session_state.get('cliente_atual') else "N/A"
            st.metric("Cliente Nome", cliente_nome)
        
        with col3:
            # Contar clientes e filiais
            manager = st.session_state.get('cliente_manager')
            if manager:
                clientes = manager.listar_clientes()
                st.metric("Total Clientes", len(clientes))
                
                total_filiais = 0
                for c in clientes:
                    filiais = manager.listar_filiais(c["id"])
                    total_filiais += len(filiais)
                st.metric("Total Filiais", total_filiais)
            else:
                st.metric("Total Clientes", "N/A")
                st.metric("Total Filiais", "N/A")
        
        st.markdown("---")
        st.markdown("### 🔧 Session State")
        
        # Mostrar variáveis importantes do session_state
        variaveis_importantes = [
            'cliente_id', 'filial_id', 'cliente_atual', 'pagina', 
            'motor', 'cliente_manager'
        ]
        
        dados_session = {}
        for var in variaveis_importantes:
            if var in st.session_state:
                valor = st.session_state[var]
                if var == 'motor':
                    dados_session[var] = f"MotorCalculo (cliente: {getattr(valor, 'cliente_nome', 'N/A')})"
                elif var == 'cliente_atual':
                    dados_session[var] = f"Cliente({getattr(valor, 'nome', 'N/A')})" if valor else "None"
                elif var == 'cliente_manager':
                    dados_session[var] = "ClienteManager (ativo)"
                else:
                    dados_session[var] = str(valor)[:50]
            else:
                dados_session[var] = "❌ NÃO DEFINIDO"
        
        st.json(dados_session)
        
        # Informações do sistema
        st.markdown("---")
        st.markdown("### 💻 Informações do Sistema")
        
        import sys
        import os
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Python:** {sys.version.split()[0]}")
            st.write(f"**Diretório atual:** `{os.getcwd()}`")
        with col2:
            st.write(f"**Streamlit:** {st.__version__}")
            st.write(f"**Pandas:** {pd.__version__}")
    
    # ===== TAB 2: PERSISTÊNCIA =====
    with tab2:
        st.markdown("### 💾 Diagnóstico de Persistência")
        
        import os
        
        if not st.session_state.get('cliente_id') or not st.session_state.get('filial_id'):
            st.info("ℹ️ Selecione um cliente e filial para diagnosticar persistência.")
        elif st.session_state.filial_id == "consolidado":
            st.info("ℹ️ Modo consolidado não tem arquivo próprio.")
        else:
            # Caminho do arquivo
            path_arquivo = f"data/clientes/{st.session_state.cliente_id}/{st.session_state.filial_id}.json"
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🧠 Dados em Memória (Motor)")
                motor = st.session_state.motor
                
                dados_memoria = {
                    "macro.ipca": f"{motor.macro.ipca * 100:.2f}%",
                    "macro.igpm": f"{motor.macro.igpm * 100:.2f}%",
                    "macro.dissidio": f"{motor.macro.dissidio * 100:.2f}%",
                    "operacional.num_salas": motor.operacional.num_salas,
                    "operacional.horas_dia": motor.operacional.horas_atendimento_dia,
                    "operacional.dias_uteis": motor.operacional.dias_uteis_mes,
                    "pagamento.pix": f"{motor.pagamento.dinheiro_pix * 100:.1f}%",
                    "pagamento.credito": f"{motor.pagamento.cartao_credito * 100:.1f}%",
                    "qtd_servicos": len(motor.servicos),
                    "qtd_fisioterapeutas": len(motor.fisioterapeutas),
                    "qtd_funcionarios": len(motor.funcionarios_clt),
                    "qtd_despesas": len(motor.despesas_fixas),
                }
                
                for k, v in dados_memoria.items():
                    st.write(f"**{k}:** {v}")
            
            with col2:
                st.markdown("#### 📁 Dados no Disco (JSON)")
                
                if os.path.exists(path_arquivo):
                    st.success(f"✅ Arquivo existe")
                    st.caption(f"Path: `{path_arquivo}`")
                    
                    try:
                        with open(path_arquivo, 'r', encoding='utf-8') as f:
                            dados_disco = json.load(f)
                        
                        st.write(f"**Tamanho:** {os.path.getsize(path_arquivo):,} bytes")
                        st.write(f"**Chaves:** {len(dados_disco)}")
                        
                        # Detectar formato v2 (cenários) ou v1 (antigo)
                        is_v2 = dados_disco.get('_version') == '2.0' and 'cenarios' in dados_disco
                        
                        if is_v2:
                            st.info(f"📦 Formato v2.0 (3 cenários)")
                            cenario_ativo = dados_disco.get('cenario_ativo', 'Conservador')
                            st.write(f"**Cenário ativo:** {cenario_ativo}")
                            dados_cenario = dados_disco.get('cenarios', {}).get(cenario_ativo, {})
                            
                            if 'macro' in dados_cenario:
                                m = dados_cenario['macro']
                                st.write(f"**macro.ipca:** {m.get('ipca', 0) * 100:.2f}%")
                                st.write(f"**macro.igpm:** {m.get('igpm', 0) * 100:.2f}%")
                            
                            if 'operacional' in dados_cenario:
                                o = dados_cenario['operacional']
                                st.write(f"**operacional.salas:** {o.get('num_salas', 0)}")
                                st.write(f"**operacional.horas:** {o.get('horas_atendimento_dia', 0)}")
                        else:
                            st.info(f"📦 Formato v1.x (antigo)")
                            # Mostrar valores salvos no formato antigo
                            if 'macro' in dados_disco:
                                m = dados_disco['macro']
                                st.write(f"**macro.ipca:** {m.get('ipca', 0) * 100:.2f}%")
                                st.write(f"**macro.igpm:** {m.get('igpm', 0) * 100:.2f}%")
                            else:
                                st.error("❌ Campo 'macro' NÃO EXISTE!")
                            
                            if 'operacional' in dados_disco:
                                o = dados_disco['operacional']
                                st.write(f"**operacional.salas:** {o.get('num_salas', 0)}")
                                st.write(f"**operacional.horas:** {o.get('horas_atendimento_dia', 0)}")
                            else:
                                st.error("❌ Campo 'operacional' NÃO EXISTE!")
                            
                    except Exception as e:
                        erro_msg = registrar_erro("BE-301", str(e), "diagnostico/ler_arquivo_filial")
                        st.error(f"❌ {erro_msg}")
                else:
                    st.error(f"❌ Arquivo NÃO existe!")
                    st.caption(f"Path esperado: `{path_arquivo}`")
            
            # Comparação
            st.markdown("---")
            st.markdown("#### 🔄 Comparação Memória vs Disco")
            
            if os.path.exists(path_arquivo):
                try:
                    with open(path_arquivo, 'r', encoding='utf-8') as f:
                        dados_disco = json.load(f)
                    
                    comparacoes = []
                    
                    # Detectar formato v2 (cenários) ou v1 (antigo)
                    is_v2 = dados_disco.get('_version') == '2.0' and 'cenarios' in dados_disco
                    
                    if is_v2:
                        cenario_ativo = st.session_state.get('cenario_ativo', 'Conservador')
                        dados_cenario = dados_disco.get('cenarios', {}).get(cenario_ativo, {})
                        st.caption(f"Comparando com cenário: {cenario_ativo}")
                    else:
                        dados_cenario = dados_disco
                    
                    # IPCA
                    mem_ipca = motor.macro.ipca
                    disco_ipca = dados_cenario.get('macro', {}).get('ipca', 0)
                    status_ipca = "✅" if abs(mem_ipca - disco_ipca) < 0.0001 else "❌ DIFERENTE!"
                    comparacoes.append({"Campo": "IPCA", "Memória": f"{mem_ipca*100:.2f}%", "Disco": f"{disco_ipca*100:.2f}%", "Status": status_ipca})
                    
                    # Salas
                    mem_salas = motor.operacional.num_salas
                    disco_salas = dados_cenario.get('operacional', {}).get('num_salas', 0)
                    status_salas = "✅" if mem_salas == disco_salas else "❌ DIFERENTE!"
                    comparacoes.append({"Campo": "Nº Salas", "Memória": str(mem_salas), "Disco": str(disco_salas), "Status": status_salas})
                    
                    # Horas
                    mem_horas = motor.operacional.horas_atendimento_dia
                    disco_horas = dados_cenario.get('operacional', {}).get('horas_atendimento_dia', 0)
                    status_horas = "✅" if mem_horas == disco_horas else "❌ DIFERENTE!"
                    comparacoes.append({"Campo": "Horas/Dia", "Memória": str(mem_horas), "Disco": str(disco_horas), "Status": status_horas})
                    
                    # Serviços
                    mem_srv = len(motor.servicos)
                    disco_srv = len(dados_cenario.get('servicos', {}))
                    status_srv = "✅" if mem_srv == disco_srv else "⚠️ Qtd diferente"
                    comparacoes.append({"Campo": "Serviços", "Memória": str(mem_srv), "Disco": str(disco_srv), "Status": status_srv})
                    
                    # Fisioterapeutas
                    mem_fisio = len(motor.fisioterapeutas)
                    disco_fisio = len(dados_cenario.get('fisioterapeutas', {}))
                    status_fisio = "✅" if mem_fisio == disco_fisio else "⚠️ Qtd diferente"
                    comparacoes.append({"Campo": "Fisioterapeutas", "Memória": str(mem_fisio), "Disco": str(disco_fisio), "Status": status_fisio})
                    
                    df_comp = pd.DataFrame(comparacoes)
                    st.dataframe(df_comp, use_container_width=True, hide_index=True)
                    
                except Exception as e:
                    erro_msg = registrar_erro("BE-301", str(e), "diagnostico/comparacao_mem_disco")
                    st.error(f"Erro na comparação: {erro_msg}")
            
            # Última seleção
            st.markdown("---")
            st.markdown("#### 📌 Última Seleção Salva")
            
            if os.path.exists(ULTIMA_SELECAO_PATH):
                try:
                    with open(ULTIMA_SELECAO_PATH, 'r') as f:
                        ultima = json.load(f)
                    st.json(ultima)
                except:
                    erro_msg = registrar_erro("BE-301", "JSON inválido", "diagnostico/ultima_selecao")
                    st.error(f"Erro: {erro_msg}")
            else:
                st.warning("Arquivo ultima_selecao.json não existe")
    
    # ===== TAB 3: MOTOR ATUAL =====
    with tab3:
        st.markdown("### 🔍 Detalhes do Motor Atual")
        
        motor = st.session_state.motor
        
        # Informações gerais
        st.markdown("#### ℹ️ Informações Gerais")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Cliente:** {getattr(motor, 'cliente_nome', 'N/A')}")
            st.write(f"**Filial:** {getattr(motor, 'filial_nome', 'N/A')}")
        with col2:
            st.write(f"**Tipo:** {getattr(motor, 'tipo_relatorio', 'N/A')}")
        with col3:
            st.write(f"**Modelo Tributário:** {motor.operacional.modelo_tributario}")
        
        # Premissas Macro
        st.markdown("#### 📊 Premissas Macroeconômicas")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"IPCA: {motor.macro.ipca * 100:.2f}%")
            st.write(f"IGP-M: {motor.macro.igpm * 100:.2f}%")
        with col2:
            st.write(f"Dissídio: {motor.macro.dissidio * 100:.2f}%")
            st.write(f"Reajuste Tarifas: {motor.macro.reajuste_tarifas * 100:.2f}%")
        with col3:
            st.write(f"Taxa Crédito: {motor.macro.taxa_cartao_credito * 100:.2f}%")
            st.write(f"Taxa Débito: {motor.macro.taxa_cartao_debito * 100:.2f}%")
        
        # Operacional
        st.markdown("#### 🏥 Premissas Operacionais")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"Fisioterapeutas: {motor.operacional.num_fisioterapeutas}")
            st.write(f"Salas: {motor.operacional.num_salas}")
        with col2:
            st.write(f"Horas/dia: {motor.operacional.horas_atendimento_dia}")
            st.write(f"Dias úteis/mês: {motor.operacional.dias_uteis_mes}")
        with col3:
            capacidade = motor.operacional.num_salas * motor.operacional.horas_atendimento_dia * motor.operacional.dias_uteis_mes
            st.write(f"Capacidade/mês: {capacidade}h")
            modo_sessoes = getattr(motor.operacional, 'modo_calculo_sessoes', 'servico')
            st.write(f"**Modo Sessões:** {modo_sessoes.upper()}")
        
        # Cadastro de Salas
        st.markdown("#### 🏢 Cadastro de Salas")
        cadastro = motor.cadastro_salas
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"Total salas cadastradas: {len(cadastro.salas)}")
            st.write(f"Salas ativas: {cadastro.num_salas_ativas}")
        with col2:
            st.write(f"m² total ativo: {cadastro.m2_ativo:.0f}")
            st.write(f"Capacidade: {cadastro.capacidade_total_horas:.0f}h/mês")
        with col3:
            salas_zeradas = sum(1 for s in cadastro.salas_ativas if s.metros_quadrados == 0)
            st.write(f"Salas sem m²: {salas_zeradas}")
        
        # Serviços
        st.markdown("#### 🩺 Serviços Cadastrados")
        if motor.servicos:
            dados_srv = []
            for nome, srv in motor.servicos.items():
                dados_srv.append({
                    "Nome": nome,
                    "Duração": f"{srv.duracao_minutos} min",
                    "Valor 2026": f"R$ {srv.valor_2026:,.2f}",
                    "Usa Sala": "Sim" if srv.usa_sala else "Não"
                })
            st.dataframe(pd.DataFrame(dados_srv), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum serviço cadastrado")
        
        # Fisioterapeutas
        st.markdown("#### 👥 Fisioterapeutas")
        if motor.fisioterapeutas:
            dados_fisio = []
            for nome, fisio in motor.fisioterapeutas.items():
                dados_fisio.append({
                    "Nome": nome,
                    "Cargo": getattr(fisio, 'cargo', 'N/A'),
                    "Nível": getattr(fisio, 'nivel', 'N/A'),
                    "Ativo": "Sim" if fisio.ativo else "Não"
                })
            st.dataframe(pd.DataFrame(dados_fisio), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum fisioterapeuta cadastrado")
        
        # Despesas
        st.markdown("#### 💰 Despesas Fixas")
        if motor.despesas_fixas:
            dados_desp = []
            for nome, desp in motor.despesas_fixas.items():
                dados_desp.append({
                    "Nome": nome,
                    "Categoria": desp.categoria,
                    "Valor Mensal": f"R$ {desp.valor_mensal:,.2f}",
                    "Ativa": "Sim" if desp.ativa else "Não"
                })
            st.dataframe(pd.DataFrame(dados_desp), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma despesa cadastrada")
    
    # ===== TAB 4: ARQUIVOS =====
    with tab4:
        st.markdown("### 📁 Arquivos do Sistema")
        
        import os
        
        # Diretório de dados
        data_dir = "data/clientes"
        
        if os.path.exists(data_dir):
            st.success(f"✅ Diretório existe: `{data_dir}`")
            
            # Listar clientes
            clientes_dirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
            
            st.write(f"**Total de pastas de clientes:** {len(clientes_dirs)}")
            
            for cliente_dir in sorted(clientes_dirs):
                cliente_path = os.path.join(data_dir, cliente_dir)
                
                with st.expander(f"📂 {cliente_dir}", expanded=False):
                    arquivos = os.listdir(cliente_path)
                    
                    dados_arquivos = []
                    for arq in sorted(arquivos):
                        arq_path = os.path.join(cliente_path, arq)
                        tamanho = os.path.getsize(arq_path)
                        
                        # Verificar integridade
                        status = "❓"
                        if arq.endswith('.json'):
                            try:
                                with open(arq_path, 'r', encoding='utf-8') as f:
                                    dados = json.load(f)
                                if 'macro' in dados and 'operacional' in dados:
                                    status = "✅ OK"
                                elif 'macro' not in dados:
                                    status = "⚠️ Sem macro"
                                elif 'operacional' not in dados:
                                    status = "⚠️ Sem operacional"
                            except:
                                status = "❌ Erro JSON"
                        
                        dados_arquivos.append({
                            "Arquivo": arq,
                            "Tamanho": f"{tamanho:,} bytes",
                            "Status": status
                        })
                    
                    st.dataframe(pd.DataFrame(dados_arquivos), use_container_width=True, hide_index=True)
        else:
            st.error(f"❌ Diretório NÃO existe: `{data_dir}`")
        
        # Arquivo de última seleção
        st.markdown("---")
        st.markdown("#### 📌 Arquivo ultima_selecao.json")
        
        if os.path.exists(ULTIMA_SELECAO_PATH):
            st.success(f"✅ Existe: `{ULTIMA_SELECAO_PATH}`")
            st.write(f"Tamanho: {os.path.getsize(ULTIMA_SELECAO_PATH)} bytes")
        else:
            st.warning("⚠️ Não existe")
    
    # ===== TAB 5: VALIDAÇÕES =====
    with tab5:
        st.markdown("### 🧪 Validações do Sistema")
        
        resultados = []
        
        import os
        
        # 1. Session State
        st.markdown("#### 1️⃣ Session State")
        
        resultados.append({
            "Categoria": "Session State",
            "Teste": "motor",
            "Resultado": "✅ OK" if 'motor' in st.session_state else "❌ FALHA",
            "Detalhe": "Presente" if 'motor' in st.session_state else "Ausente"
        })
        
        resultados.append({
            "Categoria": "Session State",
            "Teste": "cliente_manager",
            "Resultado": "✅ OK" if 'cliente_manager' in st.session_state else "❌ FALHA",
            "Detalhe": "Presente" if 'cliente_manager' in st.session_state else "Ausente"
        })
        
        resultados.append({
            "Categoria": "Session State",
            "Teste": "cliente_id",
            "Resultado": "✅ OK" if st.session_state.get('cliente_id') else "⚠️ Não selecionado",
            "Detalhe": st.session_state.get('cliente_id', 'Nenhum')
        })
        
        # 2. Diretórios
        st.markdown("#### 2️⃣ Diretórios")
        
        diretorios = ["data", "data/clientes", "modules"]
        for d in diretorios:
            resultados.append({
                "Categoria": "Diretório",
                "Teste": d,
                "Resultado": "✅ OK" if os.path.exists(d) else "❌ FALHA",
                "Detalhe": "Existe" if os.path.exists(d) else "Não existe"
            })
        
        # 3. Arquivos essenciais
        st.markdown("#### 3️⃣ Arquivos Essenciais")
        
        arquivos = [
            ("config.py", "Configuração"),
            ("motor_calculo.py", "Motor de cálculo"),
            ("modules/cliente_manager.py", "Gerenciador de clientes"),
        ]
        for arq, desc in arquivos:
            resultados.append({
                "Categoria": "Arquivo",
                "Teste": arq,
                "Resultado": "✅ OK" if os.path.exists(arq) else "❌ FALHA",
                "Detalhe": desc
            })
        
        # 4. Motor
        st.markdown("#### 4️⃣ Estrutura do Motor")
        
        motor = st.session_state.motor
        
        atributos_motor = [
            ('macro', 'Premissas Macro'),
            ('operacional', 'Premissas Operacionais'),
            ('pagamento', 'Formas de Pagamento'),
            ('servicos', 'Serviços'),
            ('fisioterapeutas', 'Fisioterapeutas'),
            ('despesas_fixas', 'Despesas Fixas'),
            ('cadastro_salas', 'Cadastro de Salas'),
            ('premissas_folha', 'Premissas Folha'),
        ]
        
        for attr, desc in atributos_motor:
            tem = hasattr(motor, attr)
            resultados.append({
                "Categoria": "Motor",
                "Teste": attr,
                "Resultado": "✅ OK" if tem else "❌ FALHA",
                "Detalhe": desc
            })
        
        # 5. Imports
        st.markdown("#### 5️⃣ Imports de Módulos")
        
        try:
            from motor_calculo import MotorCalculo, criar_motor_vazio, criar_motor_padrao
            resultados.append({
                "Categoria": "Import",
                "Teste": "motor_calculo",
                "Resultado": "✅ OK",
                "Detalhe": "Todas as funções"
            })
        except Exception as e:
            resultados.append({
                "Categoria": "Import",
                "Teste": "motor_calculo",
                "Resultado": "❌ FALHA",
                "Detalhe": str(e)[:50]
            })
        
        try:
            from modules.cliente_manager import ClienteManager, motor_para_dict, dict_para_motor
            resultados.append({
                "Categoria": "Import",
                "Teste": "cliente_manager",
                "Resultado": "✅ OK",
                "Detalhe": "Todas as funções"
            })
        except Exception as e:
            resultados.append({
                "Categoria": "Import",
                "Teste": "cliente_manager",
                "Resultado": "❌ FALHA",
                "Detalhe": str(e)[:50]
            })
        
        try:
            from realizado_manager import RealizadoManager
            resultados.append({
                "Categoria": "Import",
                "Teste": "realizado_manager",
                "Resultado": "✅ OK",
                "Detalhe": "Módulo carregado"
            })
        except Exception as e:
            resultados.append({
                "Categoria": "Import",
                "Teste": "realizado_manager",
                "Resultado": "⚠️ Aviso",
                "Detalhe": str(e)[:50]
            })
        
        # Mostrar resultados
        df_resultados = pd.DataFrame(resultados)
        st.dataframe(df_resultados, use_container_width=True, hide_index=True)
        
        # Resumo
        st.markdown("---")
        total = len(resultados)
        ok = len([r for r in resultados if "✅" in r["Resultado"]])
        falhas = len([r for r in resultados if "❌" in r["Resultado"]])
        avisos = len([r for r in resultados if "⚠️" in r["Resultado"]])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Testes", total)
        with col2:
            st.metric("✅ OK", ok)
        with col3:
            st.metric("⚠️ Avisos", avisos)
        with col4:
            st.metric("❌ Falhas", falhas)
        
        if falhas == 0:
            st.success("🎉 Todos os testes de estrutura passaram!")
        else:
            st.error(f"⚠️ {falhas} teste(s) falharam. Verifique os detalhes acima.")
    
    # ===== TAB 6: TESTES AVANÇADOS =====
    with tab6:
        st.markdown("### 🔬 Testes Avançados de Funcionamento - VARREDURA COMPLETA")
        
        st.info("Clique no botão abaixo para executar **TODOS** os testes de cálculo e funcionalidades do sistema.")
        
        if st.button("🚀 Executar Varredura Completa", type="primary", use_container_width=True):
            
            testes_avancados = []
            motor = st.session_state.motor
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_testes = 40  # Total de testes (13 categorias incluindo Cenários)
            teste_atual = 0
            
            def atualizar_progresso(nome_teste):
                nonlocal teste_atual
                teste_atual += 1
                progress_bar.progress(teste_atual / total_testes)
                status_text.text(f"Executando: {nome_teste}...")
            
            # ========================================
            # CATEGORIA 1: CÁLCULOS BÁSICOS
            # ========================================
            st.markdown("---")
            st.markdown("#### 📊 1. Cálculos Básicos")
            
            # Teste 1.1: calcular_dre
            atualizar_progresso("calcular_dre()")
            try:
                dre = motor.calcular_dre()
                tem_receita = 'Receita Bruta Total' in dre
                tem_12_meses = len(dre.get('Receita Bruta Total', [])) == 12
                testes_avancados.append({
                    "Categoria": "Cálculos Básicos",
                    "Teste": "calcular_dre()",
                    "Resultado": "✅ OK" if tem_receita and tem_12_meses else "⚠️ Incompleto",
                    "Detalhe": f"Receita: {'Sim' if tem_receita else 'Não'}, 12 meses: {'Sim' if tem_12_meses else 'Não'}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cálculos Básicos",
                    "Teste": "calcular_dre()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 1.2: calcular_indicadores
            atualizar_progresso("calcular_indicadores()")
            try:
                indicadores = motor.calcular_indicadores()
                tem_dados = len(indicadores) > 0
                testes_avancados.append({
                    "Categoria": "Cálculos Básicos",
                    "Teste": "calcular_indicadores()",
                    "Resultado": "✅ OK" if tem_dados else "⚠️ Vazio",
                    "Detalhe": f"{len(indicadores)} indicadores"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cálculos Básicos",
                    "Teste": "calcular_indicadores()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 1B: VALIDAÇÃO DE SESSÕES
            # ========================================
            st.markdown("#### 📊 1B. Validação de Sessões")
            
            # Teste 1B.1: validar_sessoes()
            atualizar_progresso("validar_sessoes()")
            try:
                validacao = motor.validar_sessoes()
                modo = validacao["detalhes"]["modo"]
                totais = validacao["detalhes"]["totais"]
                
                # Teste modo configurado
                testes_avancados.append({
                    "Categoria": "Validação Sessões",
                    "Teste": "Modo de Cálculo",
                    "Resultado": "✅ OK",
                    "Detalhe": f"Modo: {modo.upper()}"
                })
                
                # Teste sessões nos serviços
                if modo == "servico":
                    status_srv = "✅ OK" if totais["servicos"] > 0 else "⚠️ Zero"
                    testes_avancados.append({
                        "Categoria": "Validação Sessões",
                        "Teste": "Sessões nos Serviços",
                        "Resultado": status_srv,
                        "Detalhe": f"{totais['servicos']} sessões/mês"
                    })
                
                # Teste sessões nos fisios
                if modo == "profissional":
                    status_fisio = "✅ OK" if totais["fisioterapeutas"] > 0 else "❌ Zero"
                    testes_avancados.append({
                        "Categoria": "Validação Sessões",
                        "Teste": "Sessões nos Fisioterapeutas",
                        "Resultado": status_fisio,
                        "Detalhe": f"{totais['fisioterapeutas']} sessões/mês"
                    })
                
                # Teste consistência
                diff = abs(totais["servicos"] - totais["fisioterapeutas"])
                if totais["servicos"] > 0 and totais["fisioterapeutas"] > 0:
                    status_consist = "✅ OK" if diff <= 5 else "⚠️ Divergente"
                    testes_avancados.append({
                        "Categoria": "Validação Sessões",
                        "Teste": "Consistência Serviços vs Fisios",
                        "Resultado": status_consist,
                        "Detalhe": f"Diferença: {diff} sessões"
                    })
                
                # Teste capacidade
                sessoes_usadas = totais["servicos"] if modo == "servico" else totais["fisioterapeutas"]
                if totais["capacidade_salas"] > 0:
                    status_cap = "✅ OK" if sessoes_usadas <= totais["capacidade_salas"] else "⚠️ Acima"
                    testes_avancados.append({
                        "Categoria": "Validação Sessões",
                        "Teste": "Sessões vs Capacidade Salas",
                        "Resultado": status_cap,
                        "Detalhe": f"{sessoes_usadas}/{totais['capacidade_salas']} sessões"
                    })
                
                # Alertas e erros
                for erro in validacao["erros"]:
                    testes_avancados.append({
                        "Categoria": "Validação Sessões",
                        "Teste": "Erro Crítico",
                        "Resultado": "❌ ERRO",
                        "Detalhe": erro[:60]
                    })
                
                for alerta in validacao["alertas"]:
                    testes_avancados.append({
                        "Categoria": "Validação Sessões",
                        "Teste": "Alerta",
                        "Resultado": "⚠️ Aviso",
                        "Detalhe": alerta[:60]
                    })
                    
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Validação Sessões",
                    "Teste": "validar_sessoes()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 2: TDABC / CUSTEIO ABC
            # ========================================
            st.markdown("#### 🎯 2. Custeio ABC (TDABC)")
            
            # Teste 2.1: calcular_tdabc_mes
            atualizar_progresso("calcular_tdabc_mes()")
            try:
                tdabc = motor.calcular_tdabc_mes(0)
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "calcular_tdabc_mes(0)",
                    "Resultado": "✅ OK" if tdabc else "⚠️ Vazio",
                    "Detalhe": f"Rateios: {len(tdabc.rateios) if tdabc else 0}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "calcular_tdabc_mes(0)",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 2.2: get_resumo_tdabc
            atualizar_progresso("get_resumo_tdabc()")
            try:
                resumo = motor.get_resumo_tdabc()
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "get_resumo_tdabc()",
                    "Resultado": "✅ OK" if resumo else "⚠️ Vazio",
                    "Detalhe": f"Tipo: {type(resumo).__name__}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "get_resumo_tdabc()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 2.3: CadastroSalas
            atualizar_progresso("CadastroSalas")
            try:
                cadastro = motor.cadastro_salas
                tem_salas = len(cadastro.salas) > 0
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "CadastroSalas",
                    "Resultado": "✅ OK" if tem_salas else "⚠️ Sem salas",
                    "Detalhe": f"Total: {len(cadastro.salas)}, Ativas: {cadastro.num_salas_ativas}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "CadastroSalas",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 2.4: sincronizar_num_salas
            atualizar_progresso("sincronizar_num_salas()")
            try:
                cadastro = motor.cadastro_salas
                # Verificar se há salas para sincronizar
                if len(cadastro.salas) == 0:
                    testes_avancados.append({
                        "Categoria": "TDABC",
                        "Teste": "sincronizar_num_salas()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Sem salas cadastradas para testar"
                    })
                else:
                    num_original = cadastro.num_salas_ativas
                    cadastro.sincronizar_num_salas(5)
                    ok_5 = cadastro.num_salas_ativas == 5 or cadastro.num_salas_ativas == len(cadastro.salas)
                    cadastro.sincronizar_num_salas(num_original)  # Restaurar
                    testes_avancados.append({
                        "Categoria": "TDABC",
                        "Teste": "sincronizar_num_salas()",
                        "Resultado": "✅ OK" if ok_5 else "❌ FALHA",
                        "Detalhe": f"Sincronização: {'OK' if ok_5 else 'Falhou'}"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "TDABC",
                    "Teste": "sincronizar_num_salas()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 3: OCUPAÇÃO E CAPACIDADE
            # ========================================
            st.markdown("#### 📈 3. Ocupação e Capacidade")
            
            # Teste 3.1: calcular_ocupacao_anual
            atualizar_progresso("calcular_ocupacao_anual()")
            try:
                ocupacao = motor.calcular_ocupacao_anual()
                testes_avancados.append({
                    "Categoria": "Ocupação",
                    "Teste": "calcular_ocupacao_anual()",
                    "Resultado": "✅ OK" if ocupacao else "⚠️ Vazio",
                    "Detalhe": f"Meses: {len(ocupacao.meses) if ocupacao else 0}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Ocupação",
                    "Teste": "calcular_ocupacao_anual()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 3.2: calcular_ocupacao_mes
            atualizar_progresso("calcular_ocupacao_mes()")
            try:
                ocup_mes = motor.calcular_ocupacao_mes(0)
                testes_avancados.append({
                    "Categoria": "Ocupação",
                    "Teste": "calcular_ocupacao_mes(0)",
                    "Resultado": "✅ OK" if ocup_mes else "⚠️ Vazio",
                    "Detalhe": f"Taxa prof: {ocup_mes.taxa_ocupacao_profissional*100:.1f}%" if ocup_mes else "N/A"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Ocupação",
                    "Teste": "calcular_ocupacao_mes(0)",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 4: TRIBUTAÇÃO
            # ========================================
            st.markdown("#### 💼 4. Tributação")
            
            # Teste 4.1: Simples Nacional
            atualizar_progresso("calcular_simples_nacional_anual()")
            try:
                if hasattr(motor, 'calcular_simples_nacional_anual'):
                    sn = motor.calcular_simples_nacional_anual()
                    testes_avancados.append({
                        "Categoria": "Tributação",
                        "Teste": "calcular_simples_nacional_anual()",
                        "Resultado": "✅ OK" if sn else "⚠️ Vazio",
                        "Detalhe": f"Chaves: {len(sn) if sn else 0}"
                    })
                else:
                    # Tenta calcular via DRE
                    dre = motor.calcular_dre()
                    tem_sn = any('Simples' in k for k in dre.keys())
                    testes_avancados.append({
                        "Categoria": "Tributação",
                        "Teste": "Simples Nacional (via DRE)",
                        "Resultado": "✅ OK" if tem_sn else "⚠️ Não encontrado",
                        "Detalhe": "Calculado no DRE" if tem_sn else "Usar Carnê Leão?"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Tributação",
                    "Teste": "Simples Nacional",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 4.2: Carnê Leão
            atualizar_progresso("Carnê Leão")
            try:
                dre = motor.calcular_dre()
                tem_cl = any('Carnê' in k for k in dre.keys())
                testes_avancados.append({
                    "Categoria": "Tributação",
                    "Teste": "Carnê Leão (via DRE)",
                    "Resultado": "✅ OK" if tem_cl else "⚠️ Não encontrado",
                    "Detalhe": "Calculado no DRE" if tem_cl else "Usando Simples?"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Tributação",
                    "Teste": "Carnê Leão",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 5: FOLHA DE PAGAMENTO
            # ========================================
            st.markdown("#### 👔 5. Folha de Pagamento")
            
            # Teste 5.1: Premissas Folha
            atualizar_progresso("premissas_folha")
            try:
                pf = motor.premissas_folha
                tem_regime = hasattr(pf, 'regime_tributario')
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "premissas_folha",
                    "Resultado": "✅ OK" if tem_regime else "⚠️ Incompleto",
                    "Detalhe": f"Regime: {pf.regime_tributario}" if tem_regime else "Sem regime"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "premissas_folha",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 5.2: Funcionários CLT
            atualizar_progresso("funcionarios_clt")
            try:
                func = motor.funcionarios_clt
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "funcionarios_clt",
                    "Resultado": "✅ OK",
                    "Detalhe": f"Total: {len(func)} funcionários"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "funcionarios_clt",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 5.3: Sócios Pró-labore
            atualizar_progresso("socios_prolabore")
            try:
                socios = motor.socios_prolabore
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "socios_prolabore",
                    "Resultado": "✅ OK",
                    "Detalhe": f"Total: {len(socios)} sócios"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "socios_prolabore",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 5.4: calcular_folha_clt
            atualizar_progresso("calcular_folha_clt()")
            try:
                if hasattr(motor, 'calcular_folha_clt'):
                    folha_clt = motor.calcular_folha_clt()
                    testes_avancados.append({
                        "Categoria": "Folha",
                        "Teste": "calcular_folha_clt()",
                        "Resultado": "✅ OK" if folha_clt else "⚠️ Vazio",
                        "Detalhe": f"Tipo: {type(folha_clt).__name__}"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Folha",
                        "Teste": "calcular_folha_clt()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Método não encontrado"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Folha",
                    "Teste": "calcular_folha_clt()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 6: FISIOTERAPEUTAS
            # ========================================
            st.markdown("#### 🏥 6. Fisioterapeutas")
            
            # Teste 6.1: fisioterapeutas
            atualizar_progresso("fisioterapeutas")
            try:
                fisios = motor.fisioterapeutas
                testes_avancados.append({
                    "Categoria": "Fisioterapeutas",
                    "Teste": "fisioterapeutas",
                    "Resultado": "✅ OK",
                    "Detalhe": f"Total: {len(fisios)} cadastrados"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Fisioterapeutas",
                    "Teste": "fisioterapeutas",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 6.2: premissas_fisio
            atualizar_progresso("premissas_fisio")
            try:
                pf = motor.premissas_fisio
                tem_niveis = hasattr(pf, 'niveis_remuneracao')
                testes_avancados.append({
                    "Categoria": "Fisioterapeutas",
                    "Teste": "premissas_fisio",
                    "Resultado": "✅ OK" if tem_niveis else "⚠️ Incompleto",
                    "Detalhe": f"Níveis: {len(pf.niveis_remuneracao) if tem_niveis else 0}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Fisioterapeutas",
                    "Teste": "premissas_fisio",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 7: FLUXO DE CAIXA
            # ========================================
            st.markdown("#### 🏦 7. Fluxo de Caixa")
            
            # Teste 7.1: premissas_fc
            atualizar_progresso("premissas_fc")
            try:
                pfc = motor.premissas_fc
                testes_avancados.append({
                    "Categoria": "Fluxo Caixa",
                    "Teste": "premissas_fc",
                    "Resultado": "✅ OK",
                    "Detalhe": f"Caixa inicial: R$ {pfc.caixa_inicial:,.0f}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Fluxo Caixa",
                    "Teste": "premissas_fc",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 7.2: calcular_fluxo_caixa
            atualizar_progresso("calcular_fluxo_caixa()")
            try:
                if hasattr(motor, 'calcular_fluxo_caixa'):
                    fc = motor.calcular_fluxo_caixa()
                    testes_avancados.append({
                        "Categoria": "Fluxo Caixa",
                        "Teste": "calcular_fluxo_caixa()",
                        "Resultado": "✅ OK" if fc else "⚠️ Vazio",
                        "Detalhe": f"Chaves: {len(fc) if fc else 0}"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Fluxo Caixa",
                        "Teste": "calcular_fluxo_caixa()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Método não encontrado"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Fluxo Caixa",
                    "Teste": "calcular_fluxo_caixa()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 8: DIVIDENDOS
            # ========================================
            st.markdown("#### 📊 8. Dividendos")
            
            # Teste 8.1: premissas_dividendos
            atualizar_progresso("premissas_dividendos")
            try:
                pd_div = motor.premissas_dividendos
                testes_avancados.append({
                    "Categoria": "Dividendos",
                    "Teste": "premissas_dividendos",
                    "Resultado": "✅ OK",
                    "Detalhe": f"Distribuir: {pd_div.pct_distribuir*100:.0f}%"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Dividendos",
                    "Teste": "premissas_dividendos",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 9: PONTO DE EQUILÍBRIO
            # ========================================
            st.markdown("#### ⚖️ 9. Ponto de Equilíbrio")
            
            # Teste 9.1: get_resumo_pe_por_servico
            atualizar_progresso("get_resumo_pe_por_servico()")
            try:
                if hasattr(motor, 'get_resumo_pe_por_servico'):
                    pe = motor.get_resumo_pe_por_servico()
                    testes_avancados.append({
                        "Categoria": "Ponto Equilíbrio",
                        "Teste": "get_resumo_pe_por_servico()",
                        "Resultado": "✅ OK" if pe else "⚠️ Vazio",
                        "Detalhe": f"Serviços: {len(pe.get('servicos', []))}" if pe else "N/A"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Ponto Equilíbrio",
                        "Teste": "get_resumo_pe_por_servico()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Método não encontrado"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Ponto Equilíbrio",
                    "Teste": "get_resumo_pe_por_servico()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 10: SERIALIZAÇÃO
            # ========================================
            st.markdown("#### 💾 10. Serialização e Persistência")
            
            # Teste 10.1: motor_para_dict
            atualizar_progresso("motor_para_dict()")
            try:
                from modules.cliente_manager import motor_para_dict
                dados = motor_para_dict(motor)
                campos_obrigatorios = ['macro', 'operacional', 'pagamento', 'servicos']
                campos_ok = all(c in dados for c in campos_obrigatorios)
                testes_avancados.append({
                    "Categoria": "Serialização",
                    "Teste": "motor_para_dict()",
                    "Resultado": "✅ OK" if campos_ok else "⚠️ Incompleto",
                    "Detalhe": f"Chaves: {len(dados)}, Obrigatórios: {'OK' if campos_ok else 'Faltando'}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Serialização",
                    "Teste": "motor_para_dict()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 10.2: Realizado Manager
            atualizar_progresso("RealizadoManager")
            try:
                from realizado_manager import RealizadoManager
                rm = RealizadoManager('data')
                testes_avancados.append({
                    "Categoria": "Serialização",
                    "Teste": "RealizadoManager",
                    "Resultado": "✅ OK",
                    "Detalhe": "Import e instância OK"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Serialização",
                    "Teste": "RealizadoManager",
                    "Resultado": "⚠️ Aviso",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 11: PÁGINAS DO SISTEMA
            # ========================================
            st.markdown("#### 📄 11. Páginas do Sistema")
            
            # Lista de todas as páginas
            paginas = [
                'pagina_dashboard', 'pagina_consultor_ia', 'pagina_premissas',
                'pagina_atendimentos', 'pagina_folha_funcionarios', 'pagina_folha_fisioterapeutas',
                'pagina_simples_nacional', 'pagina_financeiro', 'pagina_dividendos',
                'pagina_simulador_dre', 'pagina_fc_simulado', 'pagina_taxa_ocupacao',
                'pagina_ponto_equilibrio', 'pagina_custeio_abc', 'pagina_lancar_realizado',
                'pagina_orcado_realizado', 'pagina_dre_comparativo', 'pagina_clientes',
                'pagina_importar', 'pagina_dre', 'pagina_fluxo_caixa', 'pagina_diagnostico_dev'
            ]
            
            atualizar_progresso("Verificando 22 páginas...")
            
            paginas_ok = 0
            paginas_erro = []
            for pag in paginas:
                if pag in globals():
                    paginas_ok += 1
                else:
                    paginas_erro.append(pag)
            
            testes_avancados.append({
                "Categoria": "Páginas",
                "Teste": f"22 páginas definidas",
                "Resultado": "✅ OK" if paginas_ok == 22 else f"⚠️ {paginas_ok}/22",
                "Detalhe": "Todas OK" if paginas_ok == 22 else f"Faltam: {', '.join(paginas_erro[:3])}"
            })
            
            # ========================================
            # CATEGORIA 12: GERENCIAMENTO DE CLIENTES/FILIAIS
            # ========================================
            st.markdown("#### 👥 12. Gerenciamento de Clientes/Filiais")
            
            # Teste 12.1: ClienteManager existe
            atualizar_progresso("ClienteManager")
            try:
                manager = st.session_state.get('cliente_manager')
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "ClienteManager",
                    "Resultado": "✅ OK" if manager else "❌ FALHA",
                    "Detalhe": "Ativo" if manager else "Não inicializado"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "ClienteManager",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 12.2: listar_clientes
            atualizar_progresso("listar_clientes()")
            try:
                if manager:
                    clientes = manager.listar_clientes()
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "listar_clientes()",
                        "Resultado": "✅ OK",
                        "Detalhe": f"{len(clientes)} cliente(s)"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "listar_clientes()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Manager não disponível"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "listar_clientes()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 12.3: listar_filiais
            atualizar_progresso("listar_filiais()")
            try:
                if manager and st.session_state.get('cliente_id'):
                    filiais = manager.listar_filiais(st.session_state.cliente_id)
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "listar_filiais()",
                        "Resultado": "✅ OK",
                        "Detalhe": f"{len(filiais)} filial(is) no cliente atual"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "listar_filiais()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Selecione um cliente primeiro"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "listar_filiais()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 12.4: carregar_cliente
            atualizar_progresso("carregar_cliente()")
            try:
                if manager and st.session_state.get('cliente_id'):
                    cliente = manager.carregar_cliente(st.session_state.cliente_id)
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "carregar_cliente()",
                        "Resultado": "✅ OK" if cliente else "⚠️ Vazio",
                        "Detalhe": f"Cliente: {cliente.nome if cliente else 'N/A'}"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "carregar_cliente()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Selecione um cliente primeiro"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "carregar_cliente()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 12.5: carregar_filial
            atualizar_progresso("carregar_filial()")
            try:
                if manager and st.session_state.get('cliente_id') and st.session_state.get('filial_id'):
                    filial_id = st.session_state.filial_id
                    if filial_id != "consolidado":
                        motor_filial = manager.carregar_filial(st.session_state.cliente_id, filial_id)
                        testes_avancados.append({
                            "Categoria": "Clientes/Filiais",
                            "Teste": "carregar_filial()",
                            "Resultado": "✅ OK" if motor_filial else "⚠️ Vazio",
                            "Detalhe": f"Filial: {filial_id}"
                        })
                    else:
                        testes_avancados.append({
                            "Categoria": "Clientes/Filiais",
                            "Teste": "carregar_filial()",
                            "Resultado": "⚠️ N/A",
                            "Detalhe": "Modo consolidado selecionado"
                        })
                else:
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "carregar_filial()",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Selecione cliente e filial primeiro"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "carregar_filial()",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 12.6: Estrutura de diretórios
            atualizar_progresso("Estrutura de diretórios")
            try:
                import os
                data_dir = "data/clientes"
                if os.path.exists(data_dir):
                    num_pastas = len([d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))])
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "Estrutura de diretórios",
                        "Resultado": "✅ OK",
                        "Detalhe": f"{num_pastas} pasta(s) de clientes"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "Estrutura de diretórios",
                        "Resultado": "⚠️ Aviso",
                        "Detalhe": "Diretório data/clientes não existe"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "Estrutura de diretórios",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 12.7: Estrutura de arquivos de filial
            atualizar_progresso("Arquivos de filial")
            try:
                import os
                if st.session_state.get('cliente_id') and st.session_state.get('filial_id'):
                    cliente_id = st.session_state.cliente_id
                    filial_id = st.session_state.filial_id
                    if filial_id != "consolidado":
                        filial_path = f"data/clientes/{cliente_id}/{filial_id}.json"
                        if os.path.exists(filial_path):
                            with open(filial_path, 'r', encoding='utf-8') as f:
                                filial_data = json.load(f)
                            
                            # Verificar formato v2 (cenários) ou v1 (macro/operacional)
                            is_v2 = filial_data.get('_version') == '2.0' and 'cenarios' in filial_data
                            is_v1 = 'macro' in filial_data and 'operacional' in filial_data
                            
                            if is_v2:
                                testes_avancados.append({
                                    "Categoria": "Clientes/Filiais",
                                    "Teste": "Arquivo de filial",
                                    "Resultado": "✅ OK",
                                    "Detalhe": f"Formato v2.0 (3 cenários) - {filial_id}"
                                })
                            elif is_v1:
                                testes_avancados.append({
                                    "Categoria": "Clientes/Filiais",
                                    "Teste": "Arquivo de filial",
                                    "Resultado": "✅ OK",
                                    "Detalhe": f"Formato v1 (será migrado) - {filial_id}"
                                })
                            else:
                                testes_avancados.append({
                                    "Categoria": "Clientes/Filiais",
                                    "Teste": "Arquivo de filial",
                                    "Resultado": "⚠️ Formato desconhecido",
                                    "Detalhe": f"Chaves: {list(filial_data.keys())[:3]}..."
                                })
                        else:
                            testes_avancados.append({
                                "Categoria": "Clientes/Filiais",
                                "Teste": "Arquivo de filial",
                                "Resultado": "⚠️ Aviso",
                                "Detalhe": f"Arquivo não encontrado: {filial_path}"
                            })
                    else:
                        testes_avancados.append({
                            "Categoria": "Clientes/Filiais",
                            "Teste": "Arquivo de filial",
                            "Resultado": "⚠️ N/A",
                            "Detalhe": "Modo consolidado selecionado"
                        })
                else:
                    testes_avancados.append({
                        "Categoria": "Clientes/Filiais",
                        "Teste": "Arquivo de filial",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Selecione cliente e filial primeiro"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Clientes/Filiais",
                    "Teste": "Arquivo de filial",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # CATEGORIA 13: SISTEMA DE CENÁRIOS
            # ========================================
            st.markdown("#### 🎯 13. Sistema de Cenários (3 Motores)")
            
            # Teste 13.1: motores_cenarios no session_state
            atualizar_progresso("motores_cenarios")
            try:
                motores_cenarios = st.session_state.get('motores_cenarios')
                if motores_cenarios:
                    tem_3 = len(motores_cenarios) == 3
                    cenarios_presentes = list(motores_cenarios.keys())
                    testes_avancados.append({
                        "Categoria": "Cenários",
                        "Teste": "motores_cenarios",
                        "Resultado": "✅ OK" if tem_3 else "⚠️ Incompleto",
                        "Detalhe": f"Cenários: {', '.join(cenarios_presentes)}"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Cenários",
                        "Teste": "motores_cenarios",
                        "Resultado": "❌ FALHA",
                        "Detalhe": "Não carregado no session_state"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "motores_cenarios",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 13.2: cenario_ativo
            atualizar_progresso("cenario_ativo")
            try:
                cenario_ativo = st.session_state.get('cenario_ativo', 'N/A')
                cenarios_validos = ["Conservador", "Pessimista", "Otimista"]
                valido = cenario_ativo in cenarios_validos
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "cenario_ativo",
                    "Resultado": "✅ OK" if valido else "⚠️ Inválido",
                    "Detalhe": f"Ativo: {cenario_ativo}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "cenario_ativo",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 13.3: usar_cenarios flag
            atualizar_progresso("usar_cenarios")
            try:
                usar_cenarios = getattr(motor, 'usar_cenarios', None)
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "usar_cenarios (flag)",
                    "Resultado": "✅ OK" if usar_cenarios is not None else "⚠️ Não definido",
                    "Detalhe": f"Habilitado: {'Sim' if usar_cenarios else 'Não'}"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "usar_cenarios",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 13.4: Independência dos motores
            atualizar_progresso("Independência dos motores")
            try:
                motores_cenarios = st.session_state.get('motores_cenarios', {})
                if len(motores_cenarios) == 3:
                    # Verifica se os motores são objetos diferentes (não compartilham referência)
                    m_cons = motores_cenarios.get("Conservador")
                    m_pess = motores_cenarios.get("Pessimista")
                    m_otim = motores_cenarios.get("Otimista")
                    
                    # Verifica IDs únicos (objetos diferentes)
                    ids_unicos = len(set([id(m_cons), id(m_pess), id(m_otim)])) == 3
                    
                    testes_avancados.append({
                        "Categoria": "Cenários",
                        "Teste": "Independência dos motores",
                        "Resultado": "✅ OK" if ids_unicos else "❌ FALHA",
                        "Detalhe": "Motores independentes" if ids_unicos else "Motores compartilham referência!"
                    })
                else:
                    testes_avancados.append({
                        "Categoria": "Cenários",
                        "Teste": "Independência dos motores",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "motores_cenarios não tem 3 cenários"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "Independência dos motores",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 13.5: Funções de cenário importáveis
            atualizar_progresso("Funções de cenário")
            try:
                from modules.cliente_manager import (
                    carregar_motores_cenarios,
                    salvar_motores_cenarios,
                    copiar_cenario,
                    criar_estrutura_cenarios,
                    migrar_formato_antigo
                )
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "Funções de cenário",
                    "Resultado": "✅ OK",
                    "Detalhe": "5 funções importadas com sucesso"
                })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "Funções de cenário",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # Teste 13.6: Formato de dados no arquivo
            atualizar_progresso("Formato de dados cenários")
            try:
                import os
                if st.session_state.get('cliente_id') and st.session_state.get('filial_id'):
                    cliente_id = st.session_state.cliente_id
                    filial_id = st.session_state.filial_id
                    if filial_id != "consolidado":
                        filial_path = f"data/clientes/{cliente_id}/{filial_id}.json"
                        if os.path.exists(filial_path):
                            with open(filial_path, 'r', encoding='utf-8') as f:
                                filial_data = json.load(f)
                            
                            is_v2 = filial_data.get('_version') == '2.0'
                            tem_cenarios = 'cenarios' in filial_data
                            
                            if is_v2 and tem_cenarios:
                                cenarios_salvos = list(filial_data.get('cenarios', {}).keys())
                                testes_avancados.append({
                                    "Categoria": "Cenários",
                                    "Teste": "Formato de dados (v2.0)",
                                    "Resultado": "✅ OK",
                                    "Detalhe": f"Cenários: {', '.join(cenarios_salvos)}"
                                })
                            else:
                                testes_avancados.append({
                                    "Categoria": "Cenários",
                                    "Teste": "Formato de dados",
                                    "Resultado": "⚠️ Formato antigo",
                                    "Detalhe": "Será migrado ao salvar"
                                })
                        else:
                            testes_avancados.append({
                                "Categoria": "Cenários",
                                "Teste": "Formato de dados",
                                "Resultado": "⚠️ N/A",
                                "Detalhe": "Arquivo não encontrado"
                            })
                    else:
                        testes_avancados.append({
                            "Categoria": "Cenários",
                            "Teste": "Formato de dados",
                            "Resultado": "⚠️ N/A",
                            "Detalhe": "Consolidado não tem arquivo"
                        })
                else:
                    testes_avancados.append({
                        "Categoria": "Cenários",
                        "Teste": "Formato de dados",
                        "Resultado": "⚠️ N/A",
                        "Detalhe": "Selecione cliente/filial"
                    })
            except Exception as e:
                testes_avancados.append({
                    "Categoria": "Cenários",
                    "Teste": "Formato de dados",
                    "Resultado": "❌ ERRO",
                    "Detalhe": str(e)[:60]
                })
            
            # ========================================
            # FINALIZAÇÃO
            # ========================================
            progress_bar.progress(1.0)
            status_text.text("✅ Varredura completa!")
            
            # Mostrar resultados
            st.markdown("---")
            st.markdown("### 📋 Resultados da Varredura Completa")
            
            df_avancados = pd.DataFrame(testes_avancados)
            
            # Agrupar por categoria
            for categoria in df_avancados['Categoria'].unique():
                with st.expander(f"📁 {categoria}", expanded=True):
                    df_cat = df_avancados[df_avancados['Categoria'] == categoria][['Teste', 'Resultado', 'Detalhe']]
                    st.dataframe(df_cat, use_container_width=True, hide_index=True)
            
            # Resumo geral
            st.markdown("---")
            st.markdown("### 📊 Resumo Geral")
            
            total = len(testes_avancados)
            ok = len([t for t in testes_avancados if "✅" in t["Resultado"]])
            erros = len([t for t in testes_avancados if "❌" in t["Resultado"]])
            avisos = len([t for t in testes_avancados if "⚠️" in t["Resultado"]])
            
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Testes", total)
            with col2:
                st.metric("✅ OK", ok)
            with col3:
                st.metric("⚠️ Avisos", avisos)
            with col4:
                st.metric("❌ Erros", erros)
            with col5:
                pct_ok = (ok / total * 100) if total > 0 else 0
                st.metric("% Sucesso", f"{pct_ok:.0f}%")
            
            # ========================================
            # SEÇÃO DE PROBLEMAS ENCONTRADOS
            # ========================================
            if erros > 0 or avisos > 0:
                st.markdown("---")
                st.markdown("### 🔧 Problemas Encontrados e Como Resolver")
                
                # Filtrar erros e avisos
                problemas = [t for t in testes_avancados if "❌" in t["Resultado"] or "⚠️" in t["Resultado"]]
                
                for prob in problemas:
                    categoria = prob["Categoria"]
                    teste = prob["Teste"]
                    resultado = prob["Resultado"]
                    detalhe = prob["Detalhe"]
                    
                    # Determinar cor e ícone
                    if "❌" in resultado:
                        cor = "red"
                        titulo = f"❌ ERRO: {teste}"
                    else:
                        cor = "orange"
                        titulo = f"⚠️ AVISO: {teste}"
                    
                    with st.expander(titulo, expanded=True):
                        st.write(f"**Categoria:** {categoria}")
                        st.write(f"**Detalhe:** {detalhe}")
                        
                        # Sugestões de correção baseadas no tipo de problema
                        st.markdown("**💡 Possível Solução:**")
                        
                        if "Sem salas" in detalhe or "salas cadastradas" in detalhe:
                            st.info("""
                            1. Vá em **⚙️ Premissas → Operacionais**
                            2. Configure o **Nº de Salas** (ex: 4)
                            3. Clique em **💾 Salvar**
                            4. Vá em **🎯 Custeio ABC → Cadastro de Salas**
                            5. Configure os m² de cada sala
                            """)
                        elif "Simples" in teste or "Carnê" in teste:
                            st.info("""
                            1. Vá em **⚙️ Premissas → Operacionais**
                            2. Configure o **Modelo Tributário** (PJ-Simples ou PF-Carnê Leão)
                            3. Clique em **💾 Salvar**
                            """)
                        elif "Folha" in teste or "CLT" in teste:
                            st.info("""
                            1. Vá em **👔 Folha Funcionários**
                            2. Cadastre os funcionários CLT
                            3. Configure salários e benefícios
                            """)
                        elif "Fisio" in teste:
                            st.info("""
                            1. Vá em **🏥 Folha Fisioterapeutas**
                            2. Cadastre os fisioterapeutas
                            3. Configure níveis de remuneração
                            """)
                        elif "Fluxo" in teste or "FC" in teste:
                            st.info("""
                            1. Vá em **💰 Financeiro**
                            2. Configure as premissas de fluxo de caixa
                            3. Defina caixa inicial e prazos
                            """)
                        elif "Dividendos" in teste:
                            st.info("""
                            1. Vá em **📊 Dividendos**
                            2. Configure o % de distribuição
                            3. Configure os sócios
                            """)
                        elif "Clientes" in categoria or "Filiais" in categoria:
                            st.info("""
                            1. Vá em **👥 Clientes**
                            2. Crie um novo cliente ou selecione um existente
                            3. Crie uma filial para o cliente
                            4. Selecione a filial para começar a configurar
                            """)
                        elif "Páginas" in categoria:
                            st.info("""
                            Algumas páginas podem não estar definidas.
                            Verifique se todos os arquivos foram atualizados corretamente.
                            """)
                        else:
                            st.info("""
                            Verifique as configurações relacionadas e tente salvar novamente.
                            Se o problema persistir, entre em contato com o suporte.
                            """)
            
            # Mensagem final
            if erros == 0 and avisos == 0:
                st.success("🎉 VARREDURA COMPLETA: Todos os testes passaram com sucesso!")
                st.balloons()
            elif erros == 0:
                st.warning(f"⚠️ VARREDURA COMPLETA: {avisos} aviso(s), mas sem erros críticos.")
            else:
                st.error(f"❌ VARREDURA COMPLETA: {erros} erro(s) encontrado(s). Veja as sugestões acima.")
    
    # ===== TAB 7: CHANGELOG =====
    with tab7:
        st.markdown("### 📋 Histórico de Modificações (Changelog)")
        st.info("Registro de todas as alterações feitas no sistema por versão.")
        
        # Filtros
        col_filter1, col_filter2 = st.columns([1, 3])
        with col_filter1:
            filtro_tipo = st.selectbox(
                "Filtrar por tipo:",
                ["Todos", "feature", "bugfix", "breaking"],
                index=0
            )
        
        # Exibir changelog
        for item in CHANGELOG:
            # Aplicar filtro
            if filtro_tipo != "Todos" and item.get("tipo") != filtro_tipo:
                continue
            
            # Ícone por tipo
            if item.get("tipo") == "feature":
                icone = "🆕"
                cor = "green"
            elif item.get("tipo") == "bugfix":
                icone = "🔧"
                cor = "orange"
            elif item.get("tipo") == "breaking":
                icone = "⚠️"
                cor = "red"
            else:
                icone = "📝"
                cor = "blue"
            
            with st.expander(f"{icone} **v{item['versao']}** - {item['descricao']} ({item['data']})", expanded=False):
                st.markdown(f"**Tipo:** {item.get('tipo', 'N/A').upper()}")
                st.markdown("**Detalhes:**")
                for detalhe in item.get("detalhes", []):
                    st.markdown(f"  • {detalhe}")
        
        # Estatísticas
        st.markdown("---")
        st.markdown("### 📊 Estatísticas")
        
        total_versoes = len(CHANGELOG)
        total_features = len([c for c in CHANGELOG if c.get("tipo") == "feature"])
        total_bugfixes = len([c for c in CHANGELOG if c.get("tipo") == "bugfix"])
        
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Total Versões", total_versoes)
        with col_s2:
            st.metric("🆕 Features", total_features)
        with col_s3:
            st.metric("🔧 Bugfixes", total_bugfixes)
    
    # ===== TAB 8: LOG DE ERROS =====
    with tab8:
        st.markdown("### 🚨 Log de Erros do Sistema")
        st.info("Registro de erros que ocorreram durante o uso do sistema.")
        
        # Botões de ação
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
        with col_btn1:
            if st.button("🔄 Atualizar", use_container_width=True):
                st.rerun()
        with col_btn2:
            if st.button("🗑️ Limpar Log", use_container_width=True):
                if limpar_log_erros():
                    st.success("Log limpo com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao limpar log")
        
        # Exibir códigos de erro disponíveis
        with st.expander("📖 Códigos de Erro (Referência)", expanded=False):
            # Agrupar por categoria
            categorias = {
                "Motor e Cálculos (BE-1XX)": [(k, v) for k, v in CODIGOS_ERRO.items() if k.startswith("BE-1")],
                "Clientes e Filiais (BE-2XX)": [(k, v) for k, v in CODIGOS_ERRO.items() if k.startswith("BE-2")],
                "Persistência (BE-3XX)": [(k, v) for k, v in CODIGOS_ERRO.items() if k.startswith("BE-3")],
                "Premissas (BE-4XX)": [(k, v) for k, v in CODIGOS_ERRO.items() if k.startswith("BE-4")],
                "Interface (BE-5XX)": [(k, v) for k, v in CODIGOS_ERRO.items() if k.startswith("BE-5")],
                "Importação/Exportação (BE-6XX)": [(k, v) for k, v in CODIGOS_ERRO.items() if k.startswith("BE-6")],
            }
            
            for cat_nome, codigos in categorias.items():
                st.markdown(f"**{cat_nome}**")
                for cod, desc in codigos:
                    st.markdown(f"  `{cod}`: {desc}")
                st.markdown("")
        
        # Obter e exibir log
        st.markdown("---")
        st.markdown("### 📜 Erros Recentes")
        
        erros_log = obter_log_erros(limite=100)
        
        if not erros_log:
            st.success("✅ Nenhum erro registrado! O sistema está funcionando normalmente.")
        else:
            st.warning(f"⚠️ {len(erros_log)} erro(s) registrado(s)")
            
            # Filtro por código
            codigos_unicos = list(set([e.split("]")[1].split(":")[0].strip() if "]" in e else "" for e in erros_log]))
            codigos_unicos = [c for c in codigos_unicos if c.startswith("BE-")]
            
            if codigos_unicos:
                filtro_codigo = st.selectbox(
                    "Filtrar por código:",
                    ["Todos"] + sorted(codigos_unicos),
                    index=0
                )
            else:
                filtro_codigo = "Todos"
            
            # Exibir erros
            for erro in erros_log:
                # Aplicar filtro
                if filtro_codigo != "Todos" and filtro_codigo not in erro:
                    continue
                
                # Extrair partes do erro
                try:
                    timestamp = erro.split("]")[0].replace("[", "")
                    resto = erro.split("]")[1].strip()
                    codigo = resto.split(":")[0].strip()
                    descricao = ":".join(resto.split(":")[1:]).strip()
                    
                    # Cor baseada no código
                    if codigo.startswith("BE-1"):
                        st.error(f"🔴 **{codigo}** | {timestamp}")
                    elif codigo.startswith("BE-2"):
                        st.warning(f"🟠 **{codigo}** | {timestamp}")
                    elif codigo.startswith("BE-3"):
                        st.info(f"🔵 **{codigo}** | {timestamp}")
                    else:
                        st.write(f"⚪ **{codigo}** | {timestamp}")
                    
                    st.caption(f"   {descricao}")
                except:
                    st.text(erro)
            
            # Exportar log
            st.markdown("---")
            if st.button("📥 Exportar Log Completo"):
                log_text = "\n".join(erros_log)
                st.download_button(
                    label="💾 Baixar erros.log",
                    data=log_text,
                    file_name="budget_engine_erros.log",
                    mime="text/plain"
                )

if pagina == "🏠 Dashboard":
    pagina_dashboard()
elif pagina == "🎯 Cenários":
    pagina_cenarios()
elif pagina == "🤖 Consultor IA":
    pagina_consultor_ia()
elif pagina == "⚙️ Premissas":
    pagina_premissas()
elif pagina == "📈 Atendimentos":
    pagina_atendimentos()
elif pagina == "👔 Folha Funcionários":
    pagina_folha_funcionarios()
elif pagina == "🏥 Folha Fisioterapeutas":
    pagina_folha_fisioterapeutas()
elif pagina == "💼 Simples Nacional":
    pagina_simples_nacional()
elif pagina == "💰 Financeiro":
    pagina_financeiro()
elif pagina == "📊 Dividendos":
    pagina_dividendos()
elif pagina == "📋 DRE Simulado":
    pagina_simulador_dre()
elif pagina == "🏦 FC Simulado":
    pagina_fc_simulado()
elif pagina == "📊 Taxa Ocupação":
    pagina_taxa_ocupacao()
elif pagina == "⚖️ Ponto Equilíbrio":
    pagina_ponto_equilibrio()
elif pagina == "🎯 Custeio ABC":
    pagina_custeio_abc()
elif pagina == "✅ Lançar Realizado":
    pagina_lancar_realizado()
elif pagina == "📊 Orçado x Realizado":
    pagina_orcado_realizado()
elif pagina == "📋 DRE Comparativo":
    pagina_dre_comparativo()
elif pagina == "👥 Clientes":
    pagina_clientes()
elif pagina == "📥 Importar Dados":
    pagina_importar()
elif pagina == "📄 DRE (Excel)":
    pagina_dre()
elif pagina == "📄 FC (Excel)":
    pagina_fluxo_caixa()
elif pagina == "🔧 Admin":
    pagina_admin()
elif pagina == "🛠️ Diagnóstico Dev":
    pagina_diagnostico_dev()


