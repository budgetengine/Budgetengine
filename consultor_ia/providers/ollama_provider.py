"""
Provider Ollama - IA Local Gratuita
Roda modelos como Llama, Mistral, Qwen localmente
"""

import requests
import json
from typing import Generator, Optional

class OllamaProvider:
    """
    Provider para Ollama (IA local).
    
    Requisitos:
    1. Instalar Ollama: https://ollama.ai
    2. Baixar modelo: ollama pull qwen2.5:7b
    3. Iniciar servidor: ollama serve
    """
    
    def __init__(self, 
                 base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5:7b",
                 timeout: int = 120):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.name = "Ollama (Local)"
    
    def is_available(self) -> bool:
        """Verifica se Ollama está rodando."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def list_models(self) -> list:
        """Lista modelos disponíveis."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return [m['name'] for m in data.get('models', [])]
        except:
            pass
        return []
    
    def has_model(self, model_name: str = None) -> bool:
        """Verifica se o modelo está instalado."""
        model = model_name or self.model
        models = self.list_models()
        # Verifica nome exato ou parcial
        return any(model in m or m in model for m in models)
    
    def chat(self, 
             messages: list,
             system_prompt: str = "",
             temperature: float = 0.7,
             stream: bool = False) -> str:
        """
        Envia mensagem para o modelo.
        
        Args:
            messages: Lista de mensagens [{"role": "user", "content": "..."}]
            system_prompt: Prompt de sistema
            temperature: Criatividade (0-1)
            stream: Se True, retorna generator
        
        Returns:
            Resposta do modelo (str ou generator)
        """
        
        # Monta payload
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": 8192,  # Contexto grande para dados financeiros
            }
        }
        
        if system_prompt:
            payload["messages"] = [
                {"role": "system", "content": system_prompt}
            ] + messages
        
        try:
            if stream:
                return self._chat_stream(payload)
            else:
                return self._chat_sync(payload)
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                "❌ Ollama não está rodando!\n\n"
                "Para iniciar:\n"
                "1. Abra um terminal\n"
                "2. Execute: ollama serve\n"
                "3. Tente novamente"
            )
        except Exception as e:
            raise Exception(f"Erro na comunicação com Ollama: {str(e)}")
    
    def _chat_sync(self, payload: dict) -> str:
        """Chat síncrono - aguarda resposta completa."""
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise Exception(f"Erro Ollama: {response.status_code} - {response.text}")
        
        data = response.json()
        return data.get('message', {}).get('content', '')
    
    def _chat_stream(self, payload: dict) -> Generator[str, None, None]:
        """Chat com streaming - retorna tokens conforme são gerados."""
        payload["stream"] = True
        
        response = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=self.timeout
        )
        
        if response.status_code != 200:
            raise Exception(f"Erro Ollama: {response.status_code}")
        
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    content = data.get('message', {}).get('content', '')
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
    
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Geração simples (sem histórico de chat).
        Útil para análises únicas.
        """
        messages = [{"role": "user", "content": prompt}]
        return self.chat(messages, system_prompt)


# Modelos recomendados para finanças
MODELOS_RECOMENDADOS = {
    "qwen2.5:7b": {
        "nome": "Qwen 2.5 7B",
        "ram": "8GB",
        "qualidade": "⭐⭐⭐⭐⭐",
        "velocidade": "Média",
        "descricao": "Melhor para português e raciocínio"
    },
    "llama3.2:8b": {
        "nome": "Llama 3.2 8B",
        "ram": "8GB",
        "qualidade": "⭐⭐⭐⭐",
        "velocidade": "Média",
        "descricao": "Bom equilíbrio geral"
    },
    "mistral:7b": {
        "nome": "Mistral 7B",
        "ram": "8GB",
        "qualidade": "⭐⭐⭐⭐",
        "velocidade": "Rápida",
        "descricao": "Rápido e eficiente"
    },
    "phi3:mini": {
        "nome": "Phi-3 Mini",
        "ram": "4GB",
        "qualidade": "⭐⭐⭐",
        "velocidade": "Muito Rápida",
        "descricao": "Leve, para PCs mais fracos"
    },
}


def verificar_instalacao() -> dict:
    """
    Verifica status completo da instalação Ollama.
    Retorna dict com status e instruções se necessário.
    """
    provider = OllamaProvider()
    
    result = {
        "ollama_instalado": False,
        "ollama_rodando": False,
        "modelo_disponivel": False,
        "modelos_instalados": [],
        "modelo_atual": provider.model,
        "pronto": False,
        "instrucoes": []
    }
    
    # Verifica se Ollama está rodando
    if provider.is_available():
        result["ollama_instalado"] = True
        result["ollama_rodando"] = True
        result["modelos_instalados"] = provider.list_models()
        
        if provider.has_model():
            result["modelo_disponivel"] = True
            result["pronto"] = True
        else:
            result["instrucoes"].append(
                f"Modelo '{provider.model}' não encontrado.\n"
                f"Execute: ollama pull {provider.model}"
            )
    else:
        result["instrucoes"].append(
            "Ollama não está rodando.\n\n"
            "1. Instale: https://ollama.ai/download\n"
            "2. Execute: ollama serve\n"
            "3. Baixe modelo: ollama pull qwen2.5:7b"
        )
    
    return result
