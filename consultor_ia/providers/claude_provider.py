"""
Provider Claude - API Anthropic
Para uso em produção (quando decidir migrar para nuvem)
"""

from typing import Generator, Optional

class ClaudeProvider:
    """
    Provider para Claude API (Anthropic).
    
    Requisitos:
    1. Criar conta em console.anthropic.com
    2. Gerar API key
    3. pip install anthropic
    """
    
    def __init__(self,
                 api_key: str = None,
                 model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.name = "Claude (Anthropic)"
        self._client = None
    
    def _get_client(self):
        """Inicializa cliente Anthropic."""
        if self._client is None:
            try:
                from anthropic import Anthropic
                if not self.api_key:
                    raise ValueError("API key não configurada")
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "Biblioteca 'anthropic' não instalada.\n"
                    "Execute: pip install anthropic"
                )
        return self._client
    
    def is_available(self) -> bool:
        """Verifica se API está configurada e funcionando."""
        if not self.api_key:
            return False
        try:
            client = self._get_client()
            # Faz uma chamada mínima para testar
            response = client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "ok"}]
            )
            return True
        except:
            return False
    
    def chat(self,
             messages: list,
             system_prompt: str = "",
             temperature: float = 0.7,
             stream: bool = False,
             max_tokens: int = 4096) -> str:
        """
        Envia mensagem para Claude.
        
        Args:
            messages: Lista de mensagens
            system_prompt: Prompt de sistema
            temperature: Criatividade (0-1)
            stream: Se True, retorna generator
            max_tokens: Máximo de tokens na resposta
        
        Returns:
            Resposta do modelo
        """
        client = self._get_client()
        
        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        
        if system_prompt:
            kwargs["system"] = system_prompt
        
        if stream:
            return self._chat_stream(client, kwargs)
        else:
            return self._chat_sync(client, kwargs)
    
    def _chat_sync(self, client, kwargs: dict) -> str:
        """Chat síncrono."""
        response = client.messages.create(**kwargs)
        return response.content[0].text
    
    def _chat_stream(self, client, kwargs: dict) -> Generator[str, None, None]:
        """Chat com streaming."""
        with client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text
    
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Geração simples."""
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, system_prompt)


# Modelos disponíveis
MODELOS_CLAUDE = {
    "claude-sonnet-4-20250514": {
        "nome": "Claude Sonnet 4",
        "custo_input": "$3/M tokens",
        "custo_output": "$15/M tokens",
        "qualidade": "⭐⭐⭐⭐⭐",
        "velocidade": "Rápida",
        "recomendado": True
    },
    "claude-haiku-4-20250514": {
        "nome": "Claude Haiku",
        "custo_input": "$0.25/M tokens",
        "custo_output": "$1.25/M tokens",
        "qualidade": "⭐⭐⭐⭐",
        "velocidade": "Muito Rápida",
        "recomendado": False,
        "descricao": "Mais barato, bom para volume alto"
    },
}


def estimar_custo(tokens_input: int, tokens_output: int, model: str = "claude-sonnet-4-20250514") -> float:
    """
    Estima custo de uma consulta em USD.
    
    Args:
        tokens_input: Quantidade de tokens no prompt
        tokens_output: Quantidade de tokens na resposta
        model: Modelo utilizado
    
    Returns:
        Custo estimado em USD
    """
    precos = {
        "claude-sonnet-4-20250514": (3.0, 15.0),  # (input/M, output/M)
        "claude-haiku-4-20250514": (0.25, 1.25),
    }
    
    preco = precos.get(model, (3.0, 15.0))
    custo = (tokens_input / 1_000_000 * preco[0]) + (tokens_output / 1_000_000 * preco[1])
    return custo
