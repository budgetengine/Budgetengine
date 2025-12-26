#!/usr/bin/env python3
"""
Script de Verificação e Setup do Consultor IA
=============================================

Execute este script para verificar se tudo está configurado corretamente.

Uso:
    python setup_consultor.py
"""

import subprocess
import sys
import os


def print_header(texto):
    print("\n" + "=" * 60)
    print(f"  {texto}")
    print("=" * 60)


def print_ok(texto):
    print(f"  ✅ {texto}")


def print_erro(texto):
    print(f"  ❌ {texto}")


def print_info(texto):
    print(f"  ℹ️  {texto}")


def verificar_python():
    """Verifica versão do Python."""
    print_header("1. Verificando Python")
    
    versao = sys.version_info
    if versao >= (3, 8):
        print_ok(f"Python {versao.major}.{versao.minor}.{versao.micro}")
        return True
    else:
        print_erro(f"Python {versao.major}.{versao.minor} - Necessário 3.8+")
        return False


def verificar_dependencias():
    """Verifica bibliotecas necessárias."""
    print_header("2. Verificando Dependências Python")
    
    deps = ["requests", "streamlit"]
    todas_ok = True
    
    for dep in deps:
        try:
            __import__(dep)
            print_ok(f"{dep}")
        except ImportError:
            print_erro(f"{dep} - Instale com: pip install {dep}")
            todas_ok = False
    
    return todas_ok


def verificar_ollama():
    """Verifica se Ollama está instalado e rodando."""
    print_header("3. Verificando Ollama")
    
    # Verifica se está rodando
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        
        if response.status_code == 200:
            print_ok("Ollama está rodando")
            
            # Lista modelos
            data = response.json()
            modelos = [m['name'] for m in data.get('models', [])]
            
            if modelos:
                print_info(f"Modelos instalados: {', '.join(modelos)}")
                
                # Verifica modelo recomendado
                if any('qwen' in m.lower() for m in modelos):
                    print_ok("Modelo Qwen encontrado (recomendado)")
                elif any('llama' in m.lower() for m in modelos):
                    print_ok("Modelo Llama encontrado")
                elif any('mistral' in m.lower() for m in modelos):
                    print_ok("Modelo Mistral encontrado")
                else:
                    print_info("Recomendamos: ollama pull qwen2.5:7b")
            else:
                print_erro("Nenhum modelo instalado")
                print_info("Execute: ollama pull qwen2.5:7b")
                return False
            
            return True
        else:
            print_erro("Ollama não respondeu corretamente")
            return False
            
    except Exception as e:
        print_erro(f"Ollama não está rodando: {e}")
        print_info("")
        print_info("Para instalar o Ollama:")
        print_info("  Windows/Mac: https://ollama.ai/download")
        print_info("  Linux: curl -fsSL https://ollama.ai/install.sh | sh")
        print_info("")
        print_info("Para iniciar:")
        print_info("  ollama serve")
        print_info("")
        print_info("Para baixar um modelo:")
        print_info("  ollama pull qwen2.5:7b")
        return False


def verificar_modulo():
    """Verifica se o módulo consultor_ia está funcionando."""
    print_header("4. Verificando Módulo Consultor IA")
    
    try:
        # Adiciona path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from consultor_ia import (
            ConsultorFinanceiro,
            criar_consultor_local,
            verificar_instalacao
        )
        
        print_ok("Módulo importado com sucesso")
        
        # Verifica status
        status = verificar_instalacao()
        
        if status["pronto"]:
            print_ok(f"Consultor pronto com modelo: {status['modelo_atual']}")
            return True
        else:
            print_erro("Consultor não está pronto")
            for msg in status.get("instrucoes", []):
                print_info(msg)
            return False
            
    except ImportError as e:
        print_erro(f"Erro ao importar: {e}")
        return False


def teste_rapido():
    """Faz um teste rápido do consultor."""
    print_header("5. Teste Rápido")
    
    try:
        from consultor_ia import criar_consultor_local
        
        print_info("Criando consultor...")
        consultor = criar_consultor_local()
        
        print_info("Testando comunicação com IA...")
        
        # Teste simples
        resposta = consultor.provider.generate(
            "Responda apenas 'OK' se você entendeu.",
            system_prompt="Você é um assistente. Responda de forma muito breve."
        )
        
        if "OK" in resposta.upper() or len(resposta) < 50:
            print_ok(f"IA respondeu: {resposta[:50]}...")
            return True
        else:
            print_info(f"Resposta recebida: {resposta[:100]}...")
            return True
            
    except Exception as e:
        print_erro(f"Erro no teste: {e}")
        return False


def main():
    print("\n" + "🤖 " * 20)
    print("   SETUP DO CONSULTOR FINANCEIRO IA")
    print("🤖 " * 20)
    
    resultados = {
        "Python": verificar_python(),
        "Dependências": verificar_dependencias(),
        "Ollama": verificar_ollama(),
        "Módulo": verificar_modulo(),
    }
    
    # Só faz teste se tudo OK
    if all(resultados.values()):
        resultados["Teste"] = teste_rapido()
    
    # Resumo
    print_header("RESUMO")
    
    tudo_ok = True
    for item, ok in resultados.items():
        if ok:
            print_ok(item)
        else:
            print_erro(item)
            tudo_ok = False
    
    print()
    
    if tudo_ok:
        print("🎉 " * 10)
        print("   TUDO PRONTO! O Consultor IA está funcionando!")
        print("🎉 " * 10)
        print()
        print("Para usar no Budget Engine:")
        print("  1. Carregue um cliente")
        print("  2. Acesse a página 'Consultor IA'")
        print("  3. Faça suas perguntas!")
    else:
        print("⚠️ " * 10)
        print("   CONFIGURAÇÃO INCOMPLETA")
        print("⚠️ " * 10)
        print()
        print("Siga as instruções acima para resolver.")
    
    print()


if __name__ == "__main__":
    main()
