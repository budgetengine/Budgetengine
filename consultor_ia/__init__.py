"""
Consultor Financeiro IA
========================

Módulo de IA especializada em controladoria para o Budget Engine.
Suporta múltiplos providers (Ollama local, Claude API).

Uso básico:
-----------
    from consultor_ia import ConsultorFinanceiro, criar_consultor_local
    
    # Com Ollama (local, gratuito)
    consultor = criar_consultor_local(motor=motor_calculo)
    
    # Pergunta livre
    resposta = consultor.perguntar("Por que meu FC está negativo em março?")
    
    # Análises prontas
    diagnostico = consultor.diagnostico()
    alertas = consultor.alertas()
    relatorio = consultor.relatorio_executivo()

Configuração Ollama:
--------------------
    1. Instale Ollama: https://ollama.ai/download
    2. Baixe um modelo: ollama pull qwen2.5:7b
    3. Inicie o servidor: ollama serve

Migrar para produção (Claude):
-------------------------------
    from consultor_ia import criar_consultor_claude
    
    consultor = criar_consultor_claude(
        motor=motor_calculo,
        api_key="sua-api-key"
    )
"""

from .consultor import (
    ConsultorFinanceiro,
    criar_consultor_local,
    criar_consultor_claude
)

from .providers import (
    OllamaProvider,
    ClaudeProvider,
    verificar_instalacao,
    MODELOS_RECOMENDADOS,
    MODELOS_CLAUDE
)

from .prompts import (
    SYSTEM_PROMPT_FINANCEIRO,
    get_contexto_financeiro,
    get_contexto_simples
)

__version__ = "1.0.0"

__all__ = [
    # Classes principais
    'ConsultorFinanceiro',
    'OllamaProvider',
    'ClaudeProvider',
    
    # Funções de conveniência
    'criar_consultor_local',
    'criar_consultor_claude',
    'verificar_instalacao',
    
    # Prompts e contexto
    'SYSTEM_PROMPT_FINANCEIRO',
    'get_contexto_financeiro',
    'get_contexto_simples',
    
    # Constantes
    'MODELOS_RECOMENDADOS',
    'MODELOS_CLAUDE',
]
