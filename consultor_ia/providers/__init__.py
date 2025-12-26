"""
Providers de IA disponíveis
"""

from .ollama_provider import OllamaProvider, verificar_instalacao, MODELOS_RECOMENDADOS
from .claude_provider import ClaudeProvider, MODELOS_CLAUDE, estimar_custo

__all__ = [
    'OllamaProvider',
    'ClaudeProvider',
    'verificar_instalacao',
    'MODELOS_RECOMENDADOS',
    'MODELOS_CLAUDE',
    'estimar_custo'
]
