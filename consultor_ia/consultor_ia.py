"""
Consultor IA - Módulo de Inteligência Artificial para Budget Engine
Utiliza Ollama para rodar modelos localmente.

Autor: Budget Engine Team
Versão: 1.1.0 - Contexto completo dos dados
"""

import requests
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# ============================================
# CONFIGURAÇÕES
# ============================================

OLLAMA_BASE_URL = "http://localhost:11434"

MODELOS_RECOMENDADOS = [
    "qwen2.5:7b",      # Bom equilíbrio velocidade/qualidade
    "llama3.1:8b",     # Meta's latest
    "mistral:7b",      # Rápido e eficiente
    "gemma2:9b",       # Google's model
]

SYSTEM_PROMPT = """Você é um Consultor Financeiro especializado em Controladoria para Clínicas de Fisioterapia.

IMPORTANTE: Você já possui TODOS os dados do orçamento da clínica no CONTEXTO abaixo. 
NÃO peça mais informações ao usuário. ANALISE os dados que você já tem.

REGRAS OBRIGATÓRIAS:
1. NUNCA peça dados ao usuário - você JÁ TEM todos os dados no contexto
2. Use os números ESPECÍFICOS do contexto em suas respostas
3. Seja direto e objetivo nas análises
4. Forneça insights acionáveis baseados nos dados reais
5. Responda sempre em português brasileiro
6. Use formatação markdown para melhor leitura

ÁREAS DE EXPERTISE:
- Análise de DRE e margens
- Fluxo de caixa e liquidez
- Ponto de equilíbrio
- Custo por serviço (ABC)
- Gestão de folha de pagamento
- Tributação (Simples Nacional)
- Taxa de ocupação

Lembre-se: Os dados já estão disponíveis. Analise-os diretamente!"""

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def verificar_instalacao() -> Dict[str, Any]:
    """Verifica se o Ollama está instalado e rodando"""
    resultado = {
        "ollama_instalado": False,
        "ollama_rodando": False,
        "modelos_disponiveis": [],
        "modelo_atual": None,
        "pronto": False,
        "instrucoes": []
    }
    
    # Verificar se Ollama está rodando
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            resultado["ollama_instalado"] = True
            resultado["ollama_rodando"] = True
            
            # Listar modelos
            data = response.json()
            modelos = [m["name"] for m in data.get("models", [])]
            resultado["modelos_disponiveis"] = modelos
            
            # Verificar se tem algum modelo recomendado
            for modelo in MODELOS_RECOMENDADOS:
                modelo_base = modelo.split(":")[0]
                for m in modelos:
                    if modelo_base in m:
                        resultado["modelo_atual"] = m
                        resultado["pronto"] = True
                        break
                if resultado["pronto"]:
                    break
            
            # Se tem modelos mas nenhum recomendado
            if modelos and not resultado["pronto"]:
                resultado["modelo_atual"] = modelos[0]
                resultado["pronto"] = True
            
            if not resultado["pronto"]:
                resultado["instrucoes"].append("⚠️ Nenhum modelo instalado. Execute: ollama pull qwen2.5:7b")
        else:
            resultado["instrucoes"].append("⚠️ Ollama respondeu com erro")
            
    except requests.exceptions.ConnectionError:
        resultado["instrucoes"].append("⚠️ Ollama não está rodando. Execute: ollama serve")
    except requests.exceptions.Timeout:
        resultado["instrucoes"].append("⚠️ Ollama não respondeu a tempo")
    except Exception as e:
        resultado["instrucoes"].append(f"⚠️ Erro: {str(e)}")
    
    return resultado


def chamar_ollama(prompt: str, modelo: str = None, system: str = None) -> str:
    """Chama o Ollama para gerar uma resposta"""
    
    if modelo is None:
        status = verificar_instalacao()
        modelo = status.get("modelo_atual", "qwen2.5:7b")
    
    payload = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 4096
        }
    }
    
    if system:
        payload["system"] = system
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=180  # 3 minutos
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("response", "Sem resposta")
        else:
            return f"Erro {response.status_code}: {response.text}"
            
    except requests.exceptions.Timeout:
        return "⏱️ Tempo esgotado. O modelo pode estar sobrecarregado."
    except Exception as e:
        return f"❌ Erro: {str(e)}"


# ============================================
# CLASSE PRINCIPAL
# ============================================

@dataclass
class ConsultorIA:
    """Consultor de IA para análise financeira"""
    
    motor: Any = None
    modelo: str = None
    historico: List[Dict] = field(default_factory=list)
    _contexto_cache: str = None
    
    def __post_init__(self):
        if self.modelo is None:
            status = verificar_instalacao()
            self.modelo = status.get("modelo_atual", "qwen2.5:7b")
    
    def carregar_motor(self, motor):
        """Carrega/atualiza o motor de cálculo"""
        self.motor = motor
        self._contexto_cache = None  # Limpa cache
    
    def _get_contexto_completo(self) -> str:
        """Gera contexto COMPLETO com TODOS os dados do motor"""
        if self.motor is None:
            return "ERRO: Nenhum orçamento carregado no sistema."
        
        # Usar cache se disponível
        if self._contexto_cache:
            return self._contexto_cache
        
        try:
            contexto = []
            contexto.append("=" * 60)
            contexto.append("DADOS COMPLETOS DO ORÇAMENTO - USE ESTES DADOS!")
            contexto.append("=" * 60)
            contexto.append("")
            
            # ===== INFORMAÇÕES DA EMPRESA =====
            empresa = getattr(self.motor, 'cliente_nome', 'Clínica')
            filial = getattr(self.motor, 'filial_nome', 'Principal')
            contexto.append(f"🏥 EMPRESA: {empresa}")
            contexto.append(f"📍 FILIAL: {filial}")
            contexto.append("")
            
            # ===== SERVIÇOS E PREÇOS =====
            if hasattr(self.motor, 'servicos') and self.motor.servicos:
                contexto.append("📋 SERVIÇOS OFERECIDOS:")
                contexto.append("-" * 40)
                for nome, srv in self.motor.servicos.items():
                    valor = getattr(srv, 'valor_2026', 0)
                    duracao = getattr(srv, 'duracao_minutos', 50)
                    contexto.append(f"  • {nome}: R$ {valor:.2f} ({duracao} min)")
                contexto.append("")
            
            # ===== EQUIPE DE PROFISSIONAIS =====
            if hasattr(self.motor, 'fisioterapeutas') and self.motor.fisioterapeutas:
                contexto.append("👥 EQUIPE DE FISIOTERAPEUTAS:")
                contexto.append("-" * 40)
                for nome, fisio in self.motor.fisioterapeutas.items():
                    if fisio.ativo:
                        tipo = "Proprietário" if fisio.tipo == "proprietario" else "Contratado"
                        horas = getattr(fisio, 'horas_mes', 0)
                        contexto.append(f"  • {nome} ({tipo}) - {horas}h/mês")
                        
                        # Sessões por serviço
                        if hasattr(fisio, 'sessoes_por_servico') and fisio.sessoes_por_servico:
                            for srv, qtd in fisio.sessoes_por_servico.items():
                                if qtd > 0:
                                    contexto.append(f"      └─ {srv}: {qtd} sessões/mês")
                contexto.append("")
            
            # ===== FUNCIONÁRIOS =====
            if hasattr(self.motor, 'funcionarios') and self.motor.funcionarios:
                contexto.append("👔 FUNCIONÁRIOS ADMINISTRATIVOS:")
                contexto.append("-" * 40)
                for nome, func in self.motor.funcionarios.items():
                    if func.ativo:
                        salario = getattr(func, 'salario', 0)
                        cargo = getattr(func, 'cargo', 'Funcionário')
                        contexto.append(f"  • {nome} ({cargo}): R$ {salario:,.2f}")
                contexto.append("")
            
            # ===== DESPESAS FIXAS =====
            if hasattr(self.motor, 'despesas_fixas') and self.motor.despesas_fixas:
                contexto.append("💼 DESPESAS FIXAS MENSAIS:")
                contexto.append("-" * 40)
                total_fixas = 0
                for nome, desp in self.motor.despesas_fixas.items():
                    valor = getattr(desp, 'valor_mensal', 0)
                    total_fixas += valor
                    if valor > 0:
                        contexto.append(f"  • {nome}: R$ {valor:,.2f}")
                contexto.append(f"  TOTAL DESPESAS FIXAS: R$ {total_fixas:,.2f}/mês")
                contexto.append("")
            
            # ===== DRE COMPLETO =====
            try:
                dre = self.motor.calcular_dre()
                meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
                
                contexto.append("📊 DRE - DEMONSTRATIVO DE RESULTADOS:")
                contexto.append("-" * 40)
                
                # Receita Bruta
                if "Receita Bruta" in dre:
                    receita_bruta = dre["Receita Bruta"]
                    total_rb = sum(receita_bruta)
                    contexto.append(f"  Receita Bruta Anual: R$ {total_rb:,.0f}")
                    contexto.append(f"    Mensal: {', '.join([f'{meses[i]}={receita_bruta[i]:,.0f}' for i in range(12)])}")
                
                # Receita Líquida
                if "Receita Líquida" in dre:
                    receita_liq = dre["Receita Líquida"]
                    total_rl = sum(receita_liq)
                    contexto.append(f"  Receita Líquida Anual: R$ {total_rl:,.0f}")
                
                # Custos Variáveis
                if "Total Custos Variáveis" in dre:
                    cv = dre["Total Custos Variáveis"]
                    total_cv = sum(cv)
                    contexto.append(f"  Custos Variáveis Anual: R$ {abs(total_cv):,.0f}")
                
                # Custos Fixos
                if "Total Custos Fixos" in dre:
                    cf = dre["Total Custos Fixos"]
                    total_cf = sum(cf)
                    contexto.append(f"  Custos Fixos Anual: R$ {abs(total_cf):,.0f}")
                
                # Folha de Pagamento
                if "Total Folha de Pagamento" in dre:
                    folha = dre["Total Folha de Pagamento"]
                    total_folha = sum(folha)
                    contexto.append(f"  Folha de Pagamento Anual: R$ {abs(total_folha):,.0f}")
                
                # EBITDA
                if "EBITDA" in dre:
                    ebitda = dre["EBITDA"]
                    total_ebitda = sum(ebitda)
                    margem = (total_ebitda / total_rl * 100) if total_rl > 0 else 0
                    contexto.append(f"  EBITDA Anual: R$ {total_ebitda:,.0f}")
                    contexto.append(f"  Margem EBITDA: {margem:.1f}%")
                    contexto.append(f"    Mensal: {', '.join([f'{meses[i]}={ebitda[i]:,.0f}' for i in range(12)])}")
                
                contexto.append("")
            except Exception as e:
                contexto.append(f"  (Erro ao calcular DRE: {e})")
                contexto.append("")
            
            # ===== PONTO DE EQUILÍBRIO =====
            try:
                pe = self.motor.calcular_pe_anual()
                
                contexto.append("⚖️ PONTO DE EQUILÍBRIO:")
                contexto.append("-" * 40)
                
                pe_anual = sum(m.pe_contabil for m in pe.meses)
                receita_anual = sum(m.receita_liquida for m in pe.meses)
                margem_seg = ((receita_anual - pe_anual) / receita_anual * 100) if receita_anual > 0 else 0
                
                contexto.append(f"  PE Contábil Anual: R$ {pe_anual:,.0f}")
                contexto.append(f"  Receita Anual: R$ {receita_anual:,.0f}")
                contexto.append(f"  Margem de Segurança: {margem_seg:.1f}%")
                
                if margem_seg > 0:
                    contexto.append(f"  Status: ✅ ACIMA do Ponto de Equilíbrio")
                else:
                    contexto.append(f"  Status: ❌ ABAIXO do Ponto de Equilíbrio")
                
                contexto.append("")
            except Exception as e:
                contexto.append(f"  (Erro ao calcular PE: {e})")
                contexto.append("")
            
            # ===== TAXA DE OCUPAÇÃO =====
            try:
                ocup = self.motor.calcular_ocupacao_anual()
                
                contexto.append("📊 TAXA DE OCUPAÇÃO:")
                contexto.append("-" * 40)
                
                taxa_prof = sum(m.taxa_ocupacao_profissional for m in ocup.meses) / 12 * 100
                taxa_sala = sum(m.taxa_ocupacao_sala for m in ocup.meses) / 12 * 100
                
                contexto.append(f"  Ocupação Profissionais: {taxa_prof:.1f}%")
                contexto.append(f"  Ocupação Salas: {taxa_sala:.1f}%")
                
                gargalo = "Sala" if taxa_sala > taxa_prof else "Profissional"
                contexto.append(f"  Gargalo Principal: {gargalo}")
                
                contexto.append("")
            except Exception as e:
                contexto.append(f"  (Erro ao calcular ocupação: {e})")
                contexto.append("")
            
            # ===== FLUXO DE CAIXA =====
            try:
                fc = self.motor.calcular_fluxo_caixa()
                
                if "Saldo Final" in fc:
                    saldos = fc["Saldo Final"]
                    
                    contexto.append("💵 FLUXO DE CAIXA:")
                    contexto.append("-" * 40)
                    
                    meses_negativos = [meses[i] for i, s in enumerate(saldos) if s < 0]
                    saldo_final = saldos[-1] if saldos else 0
                    
                    contexto.append(f"  Saldo Final Dezembro: R$ {saldo_final:,.0f}")
                    
                    if meses_negativos:
                        contexto.append(f"  ⚠️ Meses com Saldo Negativo: {', '.join(meses_negativos)}")
                    else:
                        contexto.append(f"  ✅ Todos os meses com saldo positivo")
                    
                    contexto.append("")
            except:
                pass
            
            # ===== CUSTEIO ABC =====
            try:
                tdabc = self.motor.get_resumo_tdabc()
                ranking = tdabc.get('ranking', [])
                
                if ranking:
                    contexto.append("🎯 CUSTEIO ABC - RENTABILIDADE POR SERVIÇO:")
                    contexto.append("-" * 40)
                    
                    for r in ranking[:6]:
                        servico = r.get('servico', '')
                        receita = r.get('receita', 0)
                        lucro = r.get('lucro_abc', 0)
                        margem = r.get('margem_abc', 0) * 100
                        contexto.append(f"  • {servico}:")
                        contexto.append(f"      Receita: R$ {receita:,.0f} | Lucro: R$ {lucro:,.0f} | Margem: {margem:.1f}%")
                    
                    contexto.append("")
            except:
                pass
            
            contexto.append("=" * 60)
            contexto.append("FIM DOS DADOS - ANALISE COM BASE NESTAS INFORMAÇÕES!")
            contexto.append("=" * 60)
            
            self._contexto_cache = "\n".join(contexto)
            return self._contexto_cache
            
        except Exception as e:
            return f"Erro ao gerar contexto: {str(e)}"
    
    def get_metricas_resumo(self) -> Dict:
        """Retorna métricas resumidas para exibição"""
        if self.motor is None:
            return {"erro": "Motor não carregado"}
        
        try:
            resultado = {
                "empresa": getattr(self.motor, 'cliente_nome', 'Clínica'),
                "filial": getattr(self.motor, 'filial_nome', 'Principal'),
                "qtd_servicos": len(self.motor.servicos) if hasattr(self.motor, 'servicos') else 0,
                "qtd_fisios": sum(1 for f in self.motor.fisioterapeutas.values() if f.ativo) if hasattr(self.motor, 'fisioterapeutas') else 0,
                "receita_mensal": 0,
                "folha_pct": 0
            }
            
            # Calcular receita mensal
            try:
                dre = self.motor.calcular_dre()
                receita_anual = sum(dre.get("Receita Líquida", [0]*12))
                resultado["receita_mensal"] = receita_anual / 12
                
                # Folha como % da receita
                folha_anual = abs(sum(dre.get("Total Folha de Pagamento", [0]*12)))
                resultado["folha_pct"] = (folha_anual / receita_anual * 100) if receita_anual > 0 else 0
            except:
                pass
            
            return resultado
            
        except Exception as e:
            return {"erro": str(e)}
    
    def perguntar(self, pergunta: str) -> str:
        """Responde uma pergunta sobre os dados"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
PERGUNTA DO USUÁRIO: {pergunta}
═══════════════════════════════════════════════════════════════

INSTRUÇÕES:
1. Use APENAS os dados acima para responder
2. NÃO peça mais informações - você já tem tudo
3. Cite números específicos do contexto
4. Seja direto e objetivo

RESPOSTA:"""
        
        resposta = chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
        
        # Adiciona ao histórico
        self.historico.append({"role": "user", "content": pergunta})
        self.historico.append({"role": "assistant", "content": resposta})
        
        return resposta
    
    def limpar_historico(self):
        """Limpa o histórico de conversa"""
        self.historico = []
    
    def diagnostico(self) -> str:
        """Gera um diagnóstico completo da situação financeira"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
TAREFA: Gere um DIAGNÓSTICO FINANCEIRO COMPLETO
═══════════════════════════════════════════════════════════════

Com base nos dados acima, analise:

1. **SAÚDE FINANCEIRA GERAL** - Nota de 0 a 10 com justificativa baseada nos números
2. **PONTOS FORTES** - O que está indo bem (cite números)
3. **PONTOS DE ATENÇÃO** - O que precisa melhorar (cite números)
4. **RISCOS IDENTIFICADOS** - Potenciais problemas baseados nos dados
5. **RECOMENDAÇÕES PRIORITÁRIAS** - 3 ações imediatas com impacto esperado

RESPOSTA (use os dados fornecidos):"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
    
    def alertas(self) -> str:
        """Lista alertas e riscos identificados"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
TAREFA: Liste ALERTAS E RISCOS com base nos dados
═══════════════════════════════════════════════════════════════

Analise os dados e classifique em:

🔴 **CRÍTICO** - Requer ação imediata (cite os números problemáticos)
🟡 **ATENÇÃO** - Monitorar de perto (explique por quê)
🟢 **POSITIVO** - Pontos fortes (destaque os bons resultados)

Para cada alerta, indique:
- O problema/oportunidade identificado nos dados
- O impacto potencial
- A ação recomendada

RESPOSTA:"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
    
    def analisar_fluxo_caixa(self) -> str:
        """Analisa o fluxo de caixa"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
TAREFA: ANÁLISE DO FLUXO DE CAIXA
═══════════════════════════════════════════════════════════════

Com base nos dados de fluxo de caixa acima:

1. **SITUAÇÃO ATUAL** - Como está a liquidez? (cite saldos)
2. **MESES CRÍTICOS** - Quais meses têm problema? Por quê?
3. **CICLO FINANCEIRO** - Análise de entradas vs saídas
4. **RECOMENDAÇÕES** - Como melhorar o fluxo?

RESPOSTA:"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
    
    def analisar_dre(self) -> str:
        """Analisa o DRE"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
TAREFA: ANÁLISE DO DRE
═══════════════════════════════════════════════════════════════

Com base nos dados do DRE acima:

1. **RECEITAS** - Composição e evolução (cite valores)
2. **CUSTOS VARIÁVEIS** - Análise de proporção sobre receita
3. **CUSTOS FIXOS** - Principais componentes e impacto
4. **MARGENS** - EBITDA e margem de contribuição
5. **RECOMENDAÇÕES** - Como melhorar o resultado?

RESPOSTA:"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
    
    def analisar_ponto_equilibrio(self) -> str:
        """Analisa o ponto de equilíbrio"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
TAREFA: ANÁLISE DO PONTO DE EQUILÍBRIO
═══════════════════════════════════════════════════════════════

Com base nos dados de PE acima:

1. **SITUAÇÃO ATUAL** - Está acima ou abaixo do PE? Por quanto?
2. **MARGEM DE SEGURANÇA** - Quanto pode cair antes de dar prejuízo?
3. **ESTRUTURA DE CUSTOS** - Análise fixos vs variáveis
4. **CENÁRIOS** - O que acontece se receita cair 10%? 20%?
5. **RECOMENDAÇÕES** - Como aumentar a margem de segurança?

RESPOSTA:"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
    
    def relatorio_executivo(self) -> str:
        """Gera um relatório executivo completo"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
TAREFA: RELATÓRIO EXECUTIVO COMPLETO
═══════════════════════════════════════════════════════════════

Gere um relatório executivo estruturado:

# SUMÁRIO EXECUTIVO
(Visão geral em 3 parágrafos com números-chave)

# INDICADORES PRINCIPAIS
| Indicador | Valor | Status |
|-----------|-------|--------|
(preencha com os dados)

# ANÁLISE FINANCEIRA
## Receitas
## Custos
## Margens
## Liquidez

# PONTOS DE ATENÇÃO
(Lista de riscos e alertas com números)

# RECOMENDAÇÕES ESTRATÉGICAS
(5 ações prioritárias com prazo e impacto esperado)

# CONCLUSÃO
(Prognóstico para os próximos 12 meses)

RESPOSTA:"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)
    
    def simular(self, cenario: str) -> str:
        """Simula um cenário hipotético"""
        contexto = self._get_contexto_completo()
        
        prompt = f"""{contexto}

═══════════════════════════════════════════════════════════════
CENÁRIO PARA SIMULAÇÃO: {cenario}
═══════════════════════════════════════════════════════════════

Com base nos dados ATUAIS acima, simule o impacto do cenário proposto:

1. **INTERPRETAÇÃO** - O que exatamente está sendo proposto?
2. **IMPACTO NA RECEITA** - Como afeta o faturamento? (calcule)
3. **IMPACTO NOS CUSTOS** - Como afeta as despesas? (calcule)
4. **IMPACTO NO RESULTADO** - Como afeta o EBITDA? (calcule)
5. **IMPACTO NO CAIXA** - Como afeta a liquidez?
6. **RISCOS DO CENÁRIO** - O que pode dar errado?
7. **RECOMENDAÇÃO** - Vale a pena implementar? Sim/Não e por quê

Use os números atuais como base para os cálculos.

RESPOSTA:"""
        
        return chamar_ollama(prompt, self.modelo, SYSTEM_PROMPT)


# ============================================
# FUNÇÃO FACTORY
# ============================================

def criar_consultor_local(motor=None) -> ConsultorIA:
    """Cria uma instância do consultor"""
    return ConsultorIA(motor=motor)
