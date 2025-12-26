"""
Consultor Financeiro IA
Interface unificada para análise financeira com IA

Uso:
    from consultor_ia import ConsultorFinanceiro
    
    consultor = ConsultorFinanceiro(motor=motor_calculo)
    resposta = consultor.perguntar("Por que meu fluxo de caixa está negativo em março?")
"""

from typing import Optional, Generator, List, Dict, Any
from datetime import datetime

from .providers.ollama_provider import OllamaProvider, verificar_instalacao
from .providers.claude_provider import ClaudeProvider
from .prompts import (
    SYSTEM_PROMPT_FINANCEIRO,
    PROMPT_DIAGNOSTICO,
    PROMPT_FLUXO_CAIXA,
    PROMPT_DRE,
    PROMPT_PONTO_EQUILIBRIO,
    PROMPT_SIMULACAO,
    PROMPT_RELATORIO_EXECUTIVO,
    get_contexto_financeiro,
    get_contexto_simples
)


class ConsultorFinanceiro:
    """
    Consultor Financeiro IA - Especialista em Controladoria.
    
    Suporta múltiplos providers (Ollama local, Claude API, etc.)
    com interface unificada.
    
    Args:
        motor: Instância do MotorCalculo com dados carregados
        provider: "ollama" (padrão), "claude", ou instância de provider
        model: Nome do modelo (opcional, usa padrão do provider)
        api_key: API key para providers pagos
    """
    
    def __init__(self,
                 motor = None,
                 provider: str = "ollama",
                 model: str = None,
                 api_key: str = None):
        
        self.motor = motor
        self.historico: List[Dict[str, str]] = []
        self._contexto_cache = None
        self._contexto_timestamp = None
        
        # Inicializa provider
        if isinstance(provider, str):
            self.provider = self._criar_provider(provider, model, api_key)
        else:
            self.provider = provider
    
    def _criar_provider(self, nome: str, model: str = None, api_key: str = None):
        """Cria instância do provider pelo nome."""
        
        if nome.lower() == "ollama":
            return OllamaProvider(model=model or "qwen2.5:7b")
        
        elif nome.lower() == "claude":
            if not api_key:
                raise ValueError("API key necessária para Claude")
            return ClaudeProvider(api_key=api_key, model=model or "claude-sonnet-4-20250514")
        
        else:
            raise ValueError(f"Provider desconhecido: {nome}")
    
    def verificar_status(self) -> Dict[str, Any]:
        """
        Verifica se o sistema está pronto para uso.
        
        Returns:
            Dict com status detalhado
        """
        status = {
            "provider": self.provider.name,
            "disponivel": self.provider.is_available(),
            "motor_carregado": self.motor is not None,
            "pronto": False,
            "mensagem": ""
        }
        
        if not status["disponivel"]:
            if isinstance(self.provider, OllamaProvider):
                info = verificar_instalacao()
                status["detalhes"] = info
                status["mensagem"] = "\n".join(info.get("instrucoes", []))
            else:
                status["mensagem"] = "Provider não disponível"
        
        elif not status["motor_carregado"]:
            status["mensagem"] = "Motor de cálculo não carregado"
        
        else:
            status["pronto"] = True
            status["mensagem"] = "✅ Consultor pronto para uso!"
        
        return status
    
    def carregar_motor(self, motor):
        """Carrega/atualiza o motor de cálculo."""
        self.motor = motor
        self._contexto_cache = None  # Invalida cache
    
    def _get_contexto(self, forcar_atualizacao: bool = False) -> str:
        """
        Obtém contexto financeiro (com cache de 5 minutos).
        """
        if self.motor is None:
            return "⚠️ Nenhum orçamento carregado. Carregue um cliente primeiro."
        
        agora = datetime.now()
        
        # Usa cache se válido
        if (not forcar_atualizacao 
            and self._contexto_cache 
            and self._contexto_timestamp
            and (agora - self._contexto_timestamp).seconds < 300):
            return self._contexto_cache
        
        # Gera novo contexto
        self._contexto_cache = get_contexto_financeiro(self.motor)
        self._contexto_timestamp = agora
        
        return self._contexto_cache
    
    def perguntar(self, 
                  pergunta: str, 
                  incluir_historico: bool = True,
                  stream: bool = False) -> str:
        """
        Faz uma pergunta ao consultor.
        
        Args:
            pergunta: Pergunta do usuário
            incluir_historico: Se True, mantém contexto da conversa
            stream: Se True, retorna generator para streaming
        
        Returns:
            Resposta do consultor (str ou generator)
        """
        
        # Monta mensagens
        contexto = self._get_contexto()
        
        messages = []
        
        # Adiciona histórico se solicitado
        if incluir_historico and self.historico:
            messages.extend(self.historico[-6:])  # Últimas 3 trocas
        
        # Adiciona pergunta atual com contexto
        prompt_completo = f"{contexto}\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n❓ PERGUNTA DO USUÁRIO:\n{pergunta}"
        
        messages.append({"role": "user", "content": prompt_completo})
        
        # Chama IA
        resposta = self.provider.chat(
            messages=messages,
            system_prompt=SYSTEM_PROMPT_FINANCEIRO,
            stream=stream
        )
        
        # Salva no histórico
        if not stream:
            self.historico.append({"role": "user", "content": pergunta})
            self.historico.append({"role": "assistant", "content": resposta})
        
        return resposta
    
    def diagnostico(self) -> str:
        """
        Gera diagnóstico financeiro completo.
        
        Returns:
            Análise detalhada da situação financeira
        """
        contexto = self._get_contexto(forcar_atualizacao=True)
        prompt = f"{contexto}\n\n{PROMPT_DIAGNOSTICO}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def analisar_fluxo_caixa(self) -> str:
        """Análise específica do fluxo de caixa."""
        contexto = self._get_contexto()
        prompt = f"{contexto}\n\n{PROMPT_FLUXO_CAIXA}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def analisar_dre(self) -> str:
        """Análise da DRE projetada."""
        contexto = self._get_contexto()
        prompt = f"{contexto}\n\n{PROMPT_DRE}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def analisar_ponto_equilibrio(self) -> str:
        """Análise do ponto de equilíbrio."""
        contexto = self._get_contexto()
        prompt = f"{contexto}\n\n{PROMPT_PONTO_EQUILIBRIO}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def simular(self, cenario: str) -> str:
        """
        Simula um cenário "e se?".
        
        Args:
            cenario: Descrição do cenário a simular
                Ex: "E se eu aumentar os preços em 10%?"
        
        Returns:
            Análise do impacto do cenário
        """
        contexto = self._get_contexto()
        prompt = f"{contexto}\n\n{PROMPT_SIMULACAO}\n\nCENÁRIO PROPOSTO: {cenario}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def relatorio_executivo(self) -> str:
        """
        Gera relatório executivo para apresentar a sócios.
        
        Returns:
            Relatório formatado em Markdown
        """
        contexto = self._get_contexto(forcar_atualizacao=True)
        prompt = f"{contexto}\n\n{PROMPT_RELATORIO_EXECUTIVO}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def alertas(self) -> str:
        """
        Lista alertas e riscos identificados.
        
        Returns:
            Lista de alertas prioritários
        """
        prompt_alertas = """
        Com base nos dados, liste APENAS os ALERTAS e RISCOS identificados.
        
        Para cada alerta:
        🔴 [CRÍTICO] ou 🟡 [ATENÇÃO]
        - O que é o problema
        - Impacto estimado
        - Ação recomendada
        
        Seja direto e objetivo. Não repita os dados, apenas os problemas.
        """
        
        contexto = self._get_contexto()
        prompt = f"{contexto}\n\n{prompt_alertas}"
        
        return self.provider.generate(prompt, SYSTEM_PROMPT_FINANCEIRO)
    
    def limpar_historico(self):
        """Limpa histórico de conversas."""
        self.historico = []
    
    def get_metricas_resumo(self) -> Dict[str, Any]:
        """
        Retorna métricas resumidas do motor (sem IA).
        Útil para exibição rápida.
        """
        if self.motor is None:
            return {}
        return get_contexto_simples(self.motor)


# Funções de conveniência
def criar_consultor_local(motor=None, model: str = "qwen2.5:7b") -> ConsultorFinanceiro:
    """
    Cria consultor com Ollama (local, gratuito).
    
    Args:
        motor: MotorCalculo (opcional, pode carregar depois)
        model: Modelo Ollama (padrão: qwen2.5:7b)
    """
    return ConsultorFinanceiro(motor=motor, provider="ollama", model=model)


def criar_consultor_claude(motor=None, api_key: str = None) -> ConsultorFinanceiro:
    """
    Cria consultor com Claude API (produção).
    
    Args:
        motor: MotorCalculo (opcional)
        api_key: API key da Anthropic
    """
    return ConsultorFinanceiro(motor=motor, provider="claude", api_key=api_key)
