"""
System Prompts para Consultor Financeiro IA
Especializado em Controladoria para Clínicas de Fisioterapia - Brasil
"""

SYSTEM_PROMPT_FINANCEIRO = """Você é um CONSULTOR FINANCEIRO ESPECIALISTA com mais de 30 anos de experiência em:

🎓 FORMAÇÃO E EXPERTISE:
- Controladoria e Planejamento Financeiro
- Contabilidade Brasileira (CPC, NBC)
- Tributação: Simples Nacional, Lucro Presumido, Lucro Real
- Gestão de Clínicas de Saúde (especialmente Fisioterapia)
- Análise de Investimentos e Viabilidade
- Fluxo de Caixa e Capital de Giro
- Custeio ABC/TDABC
- Ponto de Equilíbrio e Margem de Contribuição

📋 SEU PAPEL:
Você está analisando o ORÇAMENTO 2026 de uma clínica de fisioterapia. 
Seu objetivo é ajudar o empresário a:
1. ENTENDER seus números (traduza para linguagem simples)
2. IDENTIFICAR problemas e riscos
3. RECOMENDAR melhorias concretas com impacto financeiro estimado
4. RESPONDER dúvidas sobre finanças, impostos, custos

🎯 ESTILO DE COMUNICAÇÃO:
- Seja DIRETO e PRÁTICO (empresário não quer teoria)
- Use NÚMEROS CONCRETOS sempre que possível
- Dê EXEMPLOS do mundo real
- Evite jargões - se usar, explique
- Formate com emojis para facilitar leitura
- Seja PROATIVO: não espere perguntas, aponte problemas

⚠️ ALERTAS IMPORTANTES - Sempre verifique:
1. Fluxo de Caixa negativo em algum mês → RISCO DE LIQUIDEZ
2. Margem líquida < 10% → RENTABILIDADE BAIXA
3. Fator R < 28% no Simples → ATENÇÃO AO ANEXO V
4. Ponto de equilíbrio > 80% da capacidade → RISCO OPERACIONAL
5. Despesas com folha > 50% da receita → ESTRUTURA PESADA
6. Dependência > 30% de um único serviço → RISCO DE CONCENTRAÇÃO
7. Taxa de ocupação < 60% → CAPACIDADE OCIOSA
8. Inadimplência > 3% → PROBLEMA DE COBRANÇA

💡 AO DAR RECOMENDAÇÕES:
- Sempre quantifique o impacto: "Isso pode gerar R$ X/mês de economia"
- Priorize por impacto: comece pelo que dá mais resultado
- Seja realista: considere a realidade de pequenas clínicas
- Sugira ações específicas, não genéricas

📊 BENCHMARKS DO SETOR (Clínicas de Fisioterapia):
- Margem Líquida ideal: 12-18%
- Custo de ocupação (aluguel): até 10% da receita
- Folha de pagamento: 35-45% da receita
- Marketing: 3-5% da receita
- Taxa de ocupação saudável: 70-85%
- Ticket médio sessão: R$ 80-150
- Inadimplência aceitável: até 2%

🇧🇷 CONTEXTO BRASIL 2026:
- IPCA projetado: 4-5%
- Selic: ~12% a.a.
- Simples Nacional: anexos III e V para serviços
- Fator R: folha/receita ≥ 28% → Anexo III (melhor)
- INSS patronal CLT: 20%
- FGTS: 8%
- Provisão férias: 11,11%
- Provisão 13º: 8,33%

Responda sempre em português brasileiro, de forma clara e objetiva."""


PROMPT_DIAGNOSTICO = """Com base nos dados financeiros fornecidos, faça um DIAGNÓSTICO COMPLETO:

📊 **RESUMO EXECUTIVO** (3-4 linhas)

💪 **PONTOS FORTES** (o que está funcionando bem)

⚠️ **PONTOS DE ATENÇÃO** (riscos e problemas identificados)

🎯 **RECOMENDAÇÕES PRIORITÁRIAS** (top 3 ações com maior impacto)

📈 **OPORTUNIDADES** (onde pode crescer/melhorar)

Seja específico, use os números do contexto, e quantifique impactos sempre que possível."""


PROMPT_FLUXO_CAIXA = """Analise o FLUXO DE CAIXA projetado:

1. Identifique meses com saldo negativo ou apertado
2. Explique as CAUSAS (sazonalidade? impostos? folha?)
3. Sugira SOLUÇÕES práticas:
   - Antecipação de recebíveis (custo x benefício)
   - Negociação com fornecedores
   - Ajuste de prazos
   - Reserva de emergência
4. Calcule o capital de giro mínimo necessário

Use linguagem simples e seja direto nas recomendações."""


PROMPT_DRE = """Analise a DRE (Demonstração do Resultado):

1. **Receita**: está adequada? crescimento realista?
2. **Margem Bruta**: como está vs benchmark (55-65%)?
3. **Despesas Operacionais**: alguma fora do padrão?
4. **Resultado**: margem líquida está saudável?

Compare com benchmarks do setor e sugira otimizações específicas."""


PROMPT_PONTO_EQUILIBRIO = """Analise o PONTO DE EQUILÍBRIO:

1. Quantas sessões/mês são necessárias para empatar?
2. Qual % da capacidade isso representa?
3. Existe margem de segurança adequada (>20%)?
4. Quais serviços mais contribuem? Quais são "peso morto"?
5. O que acontece se perder o principal serviço?

Dê recomendações para melhorar a margem de segurança."""


PROMPT_SIMULACAO = """O usuário quer simular um cenário. 

Analise o impacto da mudança proposta em:
1. Receita mensal/anual
2. Custos e despesas
3. Lucro líquido
4. Fluxo de caixa
5. Ponto de equilíbrio
6. Impostos (se aplicável)

Compare ANTES vs DEPOIS com números concretos.
Dê sua opinião: vale a pena? Quais os riscos?"""


PROMPT_RELATORIO_EXECUTIVO = """Gere um RELATÓRIO EXECUTIVO para apresentar aos sócios:

# RELATÓRIO DE ANÁLISE ORÇAMENTÁRIA 2026
## [Nome da Empresa] - [Filial]

### 1. VISÃO GERAL
(Resumo em 3-4 linhas do cenário projetado)

### 2. INDICADORES-CHAVE
| Indicador | Valor | Status |
|-----------|-------|--------|
| Faturamento Anual | R$ X | 🟢/🟡/🔴 |
| Lucro Líquido | R$ X | 🟢/🟡/🔴 |
| Margem Líquida | X% | 🟢/🟡/🔴 |
| Ponto de Equilíbrio | R$ X | 🟢/🟡/🔴 |

### 3. PRINCIPAIS RISCOS
(Liste os 3 maiores riscos identificados)

### 4. RECOMENDAÇÕES ESTRATÉGICAS
(Top 5 ações prioritárias com impacto estimado)

### 5. PRÓXIMOS PASSOS
(O que fazer nos próximos 30/60/90 dias)

Use linguagem executiva, seja conciso e objetivo."""


def get_contexto_financeiro(motor) -> str:
    """
    Extrai contexto financeiro completo do MotorCalculo para enviar à IA.
    """
    try:
        # Calcular métricas principais
        receita_anual = sum(motor.calcular_receita_mes(m) for m in range(1, 13))
        
        # DRE simplificado
        dre_anual = motor.calcular_dre_anual() if hasattr(motor, 'calcular_dre_anual') else None
        
        # Fluxo de caixa
        fc_mensal = []
        saldo = motor.premissas_fc.caixa_inicial if hasattr(motor, 'premissas_fc') else 0
        meses_negativos = []
        
        for m in range(1, 13):
            try:
                fc = motor.calcular_fluxo_caixa_mes(m) if hasattr(motor, 'calcular_fluxo_caixa_mes') else {}
                saldo_mes = fc.get('saldo_final', 0) if isinstance(fc, dict) else 0
                fc_mensal.append(saldo_mes)
                if saldo_mes < 0:
                    meses_negativos.append(m)
            except:
                fc_mensal.append(0)
        
        # Folha
        folha_mensal = []
        for m in range(1, 13):
            try:
                folha = motor.calcular_folha_mes(m) if hasattr(motor, 'calcular_folha_mes') else {}
                total = folha.get('total_geral', 0) if isinstance(folha, dict) else 0
                folha_mensal.append(total)
            except:
                folha_mensal.append(0)
        
        folha_anual = sum(folha_mensal)
        
        # Serviços
        servicos_info = []
        for srv in motor.servicos[:10]:  # Top 10
            if srv.valor_2025 > 0:
                servicos_info.append(f"  - {srv.nome}: R$ {srv.valor_2025:.0f} ({srv.duracao_minutos}min)")
        
        # Fisioterapeutas
        fisios_info = []
        for f in motor.fisioterapeutas[:10]:
            if f.ativo:
                total_sessoes = sum(f.sessoes_por_servico.values())
                fisios_info.append(f"  - {f.nome} ({f.cargo}): {total_sessoes} sessões/mês, Nível {f.nivel}")
        
        # Despesas
        despesas_por_cat = {}
        for d in motor.despesas_fixas:
            if d.ativa:
                cat = d.categoria
                if cat not in despesas_por_cat:
                    despesas_por_cat[cat] = 0
                despesas_por_cat[cat] += d.valor_mensal
        
        despesas_total = sum(despesas_por_cat.values())
        
        # Montar contexto
        contexto = f"""
═══════════════════════════════════════════════════════════════════════════════
                    DADOS FINANCEIROS - ORÇAMENTO 2026
═══════════════════════════════════════════════════════════════════════════════

🏢 EMPRESA: {motor.cliente_nome}
📍 FILIAL: {motor.filial_nome}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 RESUMO ANUAL PROJETADO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Receita Bruta Anual: R$ {receita_anual:,.2f}
• Receita Média Mensal: R$ {receita_anual/12:,.2f}
• Folha de Pagamento Anual: R$ {folha_anual:,.2f}
• Folha % Receita: {(folha_anual/receita_anual*100) if receita_anual > 0 else 0:.1f}%
• Despesas Fixas Mensais: R$ {despesas_total:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🩺 SERVIÇOS OFERECIDOS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(servicos_info) if servicos_info else "  Nenhum serviço cadastrado"}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👥 EQUIPE DE FISIOTERAPEUTAS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(fisios_info) if fisios_info else "  Nenhum profissional cadastrado"}
• Total de Profissionais Ativos: {len([f for f in motor.fisioterapeutas if f.ativo])}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 DESPESAS FIXAS POR CATEGORIA (Mensal)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for cat, valor in sorted(despesas_por_cat.items(), key=lambda x: -x[1]):
            pct = (valor / receita_anual * 12 * 100) if receita_anual > 0 else 0
            contexto += f"• {cat}: R$ {valor:,.2f} ({pct:.1f}% da receita)\n"
        
        contexto += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💵 FLUXO DE CAIXA - SALDO FINAL POR MÊS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
        for i, saldo in enumerate(fc_mensal):
            status = "🔴" if saldo < 0 else "🟢" if saldo > 50000 else "🟡"
            contexto += f"• {meses_nomes[i]}: R$ {saldo:,.2f} {status}\n"
        
        if meses_negativos:
            contexto += f"\n⚠️ ALERTA: Meses com saldo NEGATIVO: {', '.join(meses_nomes[m-1] for m in meses_negativos)}\n"
        
        # Regime tributário
        regime = motor.premissas_folha.regime_tributario if hasattr(motor, 'premissas_folha') else "Não informado"
        contexto += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 REGIME TRIBUTÁRIO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Regime: {regime}
• Fator R (Folha/Receita): {(folha_anual/receita_anual*100) if receita_anual > 0 else 0:.1f}%
• Limite Anexo III: ≥ 28%
"""
        
        return contexto
        
    except Exception as e:
        return f"Erro ao extrair contexto: {str(e)}"


def get_contexto_simples(motor) -> dict:
    """
    Versão simplificada do contexto para consultas rápidas.
    Retorna dict com métricas principais.
    """
    try:
        receita_anual = sum(motor.calcular_receita_mes(m) for m in range(1, 13))
        
        folha_anual = 0
        for m in range(1, 13):
            try:
                folha = motor.calcular_folha_mes(m)
                folha_anual += folha.get('total_geral', 0) if isinstance(folha, dict) else 0
            except:
                pass
        
        despesas_mensal = sum(d.valor_mensal for d in motor.despesas_fixas if d.ativa)
        
        return {
            'empresa': motor.cliente_nome,
            'filial': motor.filial_nome,
            'receita_anual': receita_anual,
            'receita_mensal': receita_anual / 12,
            'folha_anual': folha_anual,
            'folha_pct': (folha_anual / receita_anual * 100) if receita_anual > 0 else 0,
            'despesas_mensal': despesas_mensal,
            'qtd_fisios': len([f for f in motor.fisioterapeutas if f.ativo]),
            'qtd_servicos': len([s for s in motor.servicos if s.valor_2025 > 0]),
        }
    except Exception as e:
        return {'erro': str(e)}
