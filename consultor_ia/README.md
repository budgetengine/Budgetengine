# 🤖 Consultor Financeiro IA

**Módulo de Inteligência Artificial Especializada em Controladoria**

Um assistente de IA local, gratuito e poderoso para análise financeira de clínicas de fisioterapia.

## ✨ Funcionalidades

- 💬 **Chat Inteligente**: Pergunte qualquer coisa sobre os números
- 🩺 **Diagnóstico Automático**: Análise completa da situação financeira
- ⚠️ **Alertas Proativos**: Identifica riscos e problemas
- 💵 **Análise de Fluxo de Caixa**: Entenda entradas e saídas
- 📈 **Análise de DRE**: Receitas, custos e margem
- ⚖️ **Ponto de Equilíbrio**: Quanto precisa faturar para empatar
- 🎮 **Simulador "E se?"**: Teste cenários hipotéticos
- 📋 **Relatório Executivo**: Documento para apresentar a sócios

## 🚀 Instalação Rápida

### 1. Instale o Ollama

```bash
# Windows/Mac
# Baixe em: https://ollama.ai/download

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Baixe um Modelo

```bash
# Recomendado (melhor para português)
ollama pull qwen2.5:7b

# Alternativas
ollama pull llama3.2:8b
ollama pull mistral:7b
ollama pull phi3:mini  # Para PCs com pouca RAM
```

### 3. Inicie o Servidor

```bash
ollama serve
```

### 4. Verifique a Instalação

```bash
python consultor_ia/setup_consultor.py
```

## 📊 Uso no Código

```python
from consultor_ia import criar_consultor_local

# Cria consultor (precisa do motor com dados carregados)
consultor = criar_consultor_local(motor=motor_calculo)

# Pergunta livre
resposta = consultor.perguntar("Por que meu FC está negativo em março?")

# Análises prontas
diagnostico = consultor.diagnostico()
alertas = consultor.alertas()
relatorio = consultor.relatorio_executivo()

# Simulação de cenário
impacto = consultor.simular("E se eu aumentar os preços em 10%?")
```

## 🏗️ Arquitetura

```
consultor_ia/
├── __init__.py           # Exports principais
├── consultor.py          # Classe principal ConsultorFinanceiro
├── prompts.py            # System prompts especializados
├── pagina_streamlit.py   # Interface Streamlit
├── setup_consultor.py    # Script de verificação
└── providers/
    ├── ollama_provider.py   # IA Local (gratuito)
    └── claude_provider.py   # Claude API (produção)
```

## 🔄 Migração para Produção

Quando quiser colocar online, basta trocar o provider:

```python
# ANTES (desenvolvimento local)
from consultor_ia import criar_consultor_local
consultor = criar_consultor_local(motor=motor)

# DEPOIS (produção com Claude)
from consultor_ia import criar_consultor_claude
consultor = criar_consultor_claude(
    motor=motor,
    api_key="sua-api-key-anthropic"
)

# Mesma interface! Nada mais muda!
resposta = consultor.perguntar("...")
```

## 💰 Custos

| Provider | Custo | Qualidade | Quando Usar |
|----------|-------|-----------|-------------|
| **Ollama** | R$ 0 | ⭐⭐⭐⭐ | Desenvolvimento, uso pessoal |
| **Claude Haiku** | ~R$ 0,01/consulta | ⭐⭐⭐⭐ | Produção econômica |
| **Claude Sonnet** | ~R$ 0,05/consulta | ⭐⭐⭐⭐⭐ | Produção padrão |

## 🎯 Requisitos de Hardware (Ollama)

| Modelo | RAM | Qualidade |
|--------|-----|-----------|
| phi3:mini | 4GB | ⭐⭐⭐ |
| qwen2.5:7b | 8GB | ⭐⭐⭐⭐⭐ |
| llama3.2:8b | 8GB | ⭐⭐⭐⭐ |
| mistral:7b | 8GB | ⭐⭐⭐⭐ |

## 🧠 Especialidades da IA

O consultor é treinado com conhecimento específico de:

- 📊 Contabilidade brasileira (CPC, NBC)
- 💼 Simples Nacional (Anexos III e V, Fator R)
- 🏥 Gestão de clínicas de saúde
- 💵 Análise de fluxo de caixa
- ⚖️ Ponto de equilíbrio e margem de contribuição
- 📈 Custeio ABC/TDABC
- 🏦 Capital de giro e liquidez
- 📋 Folha de pagamento (INSS, FGTS, IR)

## 🔧 Troubleshooting

### "Ollama não está rodando"
```bash
# Inicie o servidor
ollama serve
```

### "Modelo não encontrado"
```bash
# Baixe o modelo
ollama pull qwen2.5:7b
```

### "Resposta muito lenta"
- Use um modelo menor: `ollama pull phi3:mini`
- Verifique RAM disponível
- Feche outros programas pesados

### "Erro de conexão"
- Verifique se Ollama está na porta 11434
- Teste: `curl http://localhost:11434/api/tags`

## 📝 Licença

Parte do projeto Budget Engine - Uso interno.

---

Desenvolvido com 🧠 para otimizar a controladoria financeira.
