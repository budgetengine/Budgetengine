"""
Módulo Realizado - Budget Engine
Gerenciamento de lançamentos realizados e comparativo Orçado x Realizado
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# v1.99.90: Import backup seguro
from modules.cliente_manager import _salvar_json_seguro


# ============================================
# ESTRUTURAS DE DADOS
# ============================================

@dataclass
class LancamentoMesRealizado:
    """Lançamento do realizado para um mês específico"""
    mes: int  # 0-11 (Jan-Dez)
    ano: int = 2026
    
    # Receitas realizadas por serviço
    sessoes_por_servico: Dict[str, int] = field(default_factory=dict)
    receita_por_servico: Dict[str, float] = field(default_factory=dict)
    
    # Sessões por profissional/serviço: {"Ana": {"Fisioterapia": 40, "Pilates": 20}}
    sessoes_por_profissional: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    # Despesas fixas realizadas: {"Aluguel": 5200.00}
    despesas_fixas: Dict[str, float] = field(default_factory=dict)
    
    # Folha de pagamento realizada
    folha_funcionarios: Dict[str, float] = field(default_factory=dict)
    folha_fisioterapeutas: Dict[str, float] = field(default_factory=dict)
    prolabore_socios: Dict[str, float] = field(default_factory=dict)
    
    # Impostos pagos
    imposto_simples: float = 0.0
    outros_impostos: float = 0.0
    
    # Taxas de cartão realizadas
    taxas_cartao: float = 0.0
    
    # Metadata
    data_lancamento: str = ""
    usuario_lancamento: str = ""
    observacoes: str = ""
    status: str = "rascunho"  # rascunho, confirmado, fechado
    
    def __post_init__(self):
        if not self.data_lancamento:
            self.data_lancamento = datetime.now().isoformat()
    
    @property
    def total_sessoes(self) -> int:
        return sum(self.sessoes_por_servico.values())
    
    @property
    def receita_bruta(self) -> float:
        return sum(self.receita_por_servico.values())
    
    @property
    def total_despesas_fixas(self) -> float:
        return sum(self.despesas_fixas.values())
    
    @property
    def total_folha(self) -> float:
        return (
            sum(self.folha_funcionarios.values()) +
            sum(self.folha_fisioterapeutas.values()) +
            sum(self.prolabore_socios.values())
        )
    
    @property
    def total_impostos(self) -> float:
        return self.imposto_simples + self.outros_impostos


@dataclass
class RealizadoAnual:
    """Consolidação do realizado anual (12 meses)"""
    ano: int = 2026
    meses: Dict[int, LancamentoMesRealizado] = field(default_factory=dict)
    
    def get_mes(self, mes: int) -> Optional[LancamentoMesRealizado]:
        """Retorna lançamento de um mês específico"""
        return self.meses.get(mes)
    
    def set_mes(self, mes: int, lancamento: LancamentoMesRealizado):
        """Define lançamento de um mês"""
        self.meses[mes] = lancamento
    
    def get_total_receita(self) -> float:
        """Total de receita do ano"""
        return sum(m.receita_bruta for m in self.meses.values())
    
    def get_total_sessoes(self) -> int:
        """Total de sessões do ano"""
        return sum(m.total_sessoes for m in self.meses.values())
    
    def get_receita_por_mes(self) -> List[float]:
        """Lista de receitas por mês (12 valores)"""
        return [self.meses.get(m, LancamentoMesRealizado(mes=m)).receita_bruta for m in range(12)]
    
    def get_sessoes_por_mes(self) -> List[int]:
        """Lista de sessões por mês (12 valores)"""
        return [self.meses.get(m, LancamentoMesRealizado(mes=m)).total_sessoes for m in range(12)]


@dataclass
class AnaliseVariacao:
    """Análise de variação Orçado x Realizado"""
    descricao: str
    orcado: float
    realizado: float
    
    @property
    def variacao_absoluta(self) -> float:
        return self.realizado - self.orcado
    
    @property
    def variacao_percentual(self) -> float:
        if self.orcado == 0:
            return 0.0 if self.realizado == 0 else 100.0
        return ((self.realizado - self.orcado) / self.orcado) * 100
    
    @property
    def status(self) -> str:
        """Retorna status semáforo"""
        pct = abs(self.variacao_percentual)
        if pct <= 5:
            return "verde"
        elif pct <= 15:
            return "amarelo"
        else:
            return "vermelho"
    
    @property
    def icone(self) -> str:
        """Retorna ícone baseado na variação"""
        status = self.status
        if status == "verde":
            return "🟢"
        elif status == "amarelo":
            return "🟡"
        else:
            return "🔴"


# ============================================
# GERENCIADOR DE REALIZADO
# ============================================

class RealizadoManager:
    """Gerencia lançamentos realizados por cliente/filial"""
    
    MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    def __init__(self, data_dir: str = "data/clientes"):
        self.data_dir = data_dir
    
    def _path_realizado(self, cliente_id: str, filial_id: str, ano: int) -> str:
        """Retorna caminho do arquivo de realizado"""
        return os.path.join(
            self.data_dir, 
            cliente_id, 
            f"realizado_{filial_id}_{ano}.json"
        )
    
    def carregar_realizado(self, cliente_id: str, filial_id: str, ano: int = 2026) -> RealizadoAnual:
        """Carrega dados realizados de uma filial/ano"""
        path = self._path_realizado(cliente_id, filial_id, ano)
        
        realizado = RealizadoAnual(ano=ano)
        
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    dados = json.load(f)
                    
                for mes_str, mes_data in dados.get("meses", {}).items():
                    mes = int(mes_str)
                    lancamento = LancamentoMesRealizado(
                        mes=mes,
                        ano=ano,
                        sessoes_por_servico=mes_data.get("sessoes_por_servico", {}),
                        receita_por_servico=mes_data.get("receita_por_servico", {}),
                        sessoes_por_profissional=mes_data.get("sessoes_por_profissional", {}),
                        despesas_fixas=mes_data.get("despesas_fixas", {}),
                        folha_funcionarios=mes_data.get("folha_funcionarios", {}),
                        folha_fisioterapeutas=mes_data.get("folha_fisioterapeutas", {}),
                        prolabore_socios=mes_data.get("prolabore_socios", {}),
                        imposto_simples=mes_data.get("imposto_simples", 0.0),
                        outros_impostos=mes_data.get("outros_impostos", 0.0),
                        taxas_cartao=mes_data.get("taxas_cartao", 0.0),
                        data_lancamento=mes_data.get("data_lancamento", ""),
                        usuario_lancamento=mes_data.get("usuario_lancamento", ""),
                        observacoes=mes_data.get("observacoes", ""),
                        status=mes_data.get("status", "rascunho"),
                    )
                    realizado.meses[mes] = lancamento
            except Exception as e:
                print(f"Erro ao carregar realizado: {e}")
        
        return realizado
    
    def salvar_realizado(self, cliente_id: str, filial_id: str, realizado: RealizadoAnual):
        """Salva dados realizados de uma filial/ano"""
        path = self._path_realizado(cliente_id, filial_id, realizado.ano)
        
        # Garantir diretório existe
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        # Converter para dict
        dados = {
            "ano": realizado.ano,
            "meses": {}
        }
        
        for mes, lancamento in realizado.meses.items():
            dados["meses"][str(mes)] = {
                "mes": lancamento.mes,
                "ano": lancamento.ano,
                "sessoes_por_servico": lancamento.sessoes_por_servico,
                "receita_por_servico": lancamento.receita_por_servico,
                "sessoes_por_profissional": lancamento.sessoes_por_profissional,
                "despesas_fixas": lancamento.despesas_fixas,
                "folha_funcionarios": lancamento.folha_funcionarios,
                "folha_fisioterapeutas": lancamento.folha_fisioterapeutas,
                "prolabore_socios": lancamento.prolabore_socios,
                "imposto_simples": lancamento.imposto_simples,
                "outros_impostos": lancamento.outros_impostos,
                "taxas_cartao": lancamento.taxas_cartao,
                "data_lancamento": lancamento.data_lancamento,
                "usuario_lancamento": lancamento.usuario_lancamento,
                "observacoes": lancamento.observacoes,
                "status": lancamento.status,
            }
        
        _salvar_json_seguro(path, dados)

    def salvar_lancamento_mes(self, cliente_id: str, filial_id: str, 
                              lancamento: LancamentoMesRealizado, ano: int = 2026):
        """Salva lançamento de um mês específico"""
        realizado = self.carregar_realizado(cliente_id, filial_id, ano)
        realizado.set_mes(lancamento.mes, lancamento)
        self.salvar_realizado(cliente_id, filial_id, realizado)
    
    def comparar_orcado_realizado(self, motor, realizado: RealizadoAnual, 
                                   mes: Optional[int] = None) -> Dict[str, AnaliseVariacao]:
        """
        Compara orçado x realizado
        
        Args:
            motor: MotorCalculo com dados orçados
            realizado: RealizadoAnual com dados realizados
            mes: Mês específico (0-11) ou None para ano todo
            
        Returns:
            Dict com análises de variação por categoria
        """
        analises = {}
        
        # Calcular DRE orçado se não calculado
        if not motor.receita_bruta:
            motor.calcular_receita_bruta_total()
        
        if mes is not None:
            # Análise de um mês específico
            lanc = realizado.get_mes(mes)
            if not lanc:
                lanc = LancamentoMesRealizado(mes=mes)
            
            # Receita
            receita_orcada = motor.receita_bruta.get("Total", [0]*12)[mes]
            analises["receita_bruta"] = AnaliseVariacao(
                descricao="Receita Bruta",
                orcado=receita_orcada,
                realizado=lanc.receita_bruta
            )
            
            # Sessões
            sessoes_orcadas = sum(
                motor.calcular_sessoes_mes(srv, mes) 
                for srv in motor.servicos.keys()
            )
            analises["sessoes"] = AnaliseVariacao(
                descricao="Total Sessões",
                orcado=sessoes_orcadas,
                realizado=lanc.total_sessoes
            )
            
            # Despesas Fixas
            despesas_orcadas = sum(
                desp.valor_mensal for desp in motor.despesas_fixas.values()
            )
            analises["despesas_fixas"] = AnaliseVariacao(
                descricao="Despesas Fixas",
                orcado=despesas_orcadas,
                realizado=lanc.total_despesas_fixas
            )
            
        else:
            # Análise anual
            receita_orcada_anual = sum(motor.receita_bruta.get("Total", [0]*12))
            receita_realizada_anual = realizado.get_total_receita()
            
            analises["receita_bruta"] = AnaliseVariacao(
                descricao="Receita Bruta Anual",
                orcado=receita_orcada_anual,
                realizado=receita_realizada_anual
            )
            
            sessoes_orcadas_anual = sum(
                sum(motor.calcular_sessoes_mes(srv, m) for srv in motor.servicos.keys())
                for m in range(12)
            )
            analises["sessoes"] = AnaliseVariacao(
                descricao="Total Sessões Anual",
                orcado=sessoes_orcadas_anual,
                realizado=realizado.get_total_sessoes()
            )
        
        return analises
    
    def gerar_template_excel(self, motor, mes: int) -> Dict:
        """
        Gera template com valores orçados para preenchimento
        
        Args:
            motor: MotorCalculo com dados orçados
            mes: Mês (0-11)
            
        Returns:
            Dict com estrutura do template
        """
        template = {
            "mes": mes,
            "mes_nome": self.MESES[mes],
            "servicos": {},
            "profissionais": {},
            "despesas_fixas": {},
            "folha": {
                "funcionarios": {},
                "fisioterapeutas": {},
                "socios": {}
            }
        }
        
        # Serviços com valores orçados
        for nome, srv in motor.servicos.items():
            sessoes_orcadas = motor.calcular_sessoes_mes(nome, mes)
            receita_orcada = motor.calcular_receita_servico_mes(nome, mes)
            template["servicos"][nome] = {
                "sessoes_orcadas": round(sessoes_orcadas),
                "receita_orcada": round(receita_orcada, 2),
                "sessoes_realizadas": 0,
                "receita_realizada": 0.0
            }
        
        # Profissionais
        for nome, fisio in motor.fisioterapeutas.items():
            if fisio.ativo:
                template["profissionais"][nome] = {
                    "sessoes_orcadas": sum(fisio.sessoes_por_servico.values()),
                    "sessoes_realizadas": 0
                }
        
        for nome, prop in motor.proprietarios.items():
            template["profissionais"][nome] = {
                "sessoes_orcadas": sum(prop.sessoes_por_servico.values()),
                "sessoes_realizadas": 0
            }
        
        for nome, prof in motor.profissionais.items():
            template["profissionais"][nome] = {
                "sessoes_orcadas": sum(prof.sessoes_por_servico.values()),
                "sessoes_realizadas": 0
            }
        
        # Despesas fixas
        for nome, desp in motor.despesas_fixas.items():
            template["despesas_fixas"][nome] = {
                "valor_orcado": desp.valor_mensal,
                "valor_realizado": 0.0
            }
        
        # Folha
        for nome, func in motor.funcionarios_clt.items():
            template["folha"]["funcionarios"][nome] = {
                "valor_orcado": func.salario_base,
                "valor_realizado": 0.0
            }
        
        for nome, socio in motor.socios_prolabore.items():
            template["folha"]["socios"][nome] = {
                "valor_orcado": socio.prolabore,
                "valor_realizado": 0.0
            }
        
        return template


# ============================================
# FUNÇÕES AUXILIARES PARA EXPORTAÇÃO
# ============================================

def criar_dre_comparativo(motor, realizado: RealizadoAnual, mes: Optional[int] = None) -> List[Dict]:
    """
    Cria DRE comparativo Orçado x Realizado
    
    Returns:
        Lista de dicts com linhas do DRE comparativo
    """
    linhas = []
    
    # Calcular totais orçados
    motor.calcular_receita_bruta_total()
    motor.calcular_deducoes_total()
    
    if mes is not None:
        # Mês específico
        lanc = realizado.get_mes(mes) or LancamentoMesRealizado(mes=mes)
        
        receita_orcada = motor.receita_bruta.get("Total", [0]*12)[mes]
        receita_realizada = lanc.receita_bruta
        
        linhas.append({
            "conta": "RECEITA BRUTA",
            "orcado": receita_orcada,
            "realizado": receita_realizada,
            "variacao": receita_realizada - receita_orcada,
            "variacao_pct": ((receita_realizada - receita_orcada) / receita_orcada * 100) if receita_orcada > 0 else 0
        })
        
        # Deduções
        deducoes_orcadas = motor.deducoes.get("Total Deduções", [0]*12)[mes]
        deducoes_realizadas = lanc.taxas_cartao + lanc.total_impostos
        
        linhas.append({
            "conta": "(-) Deduções",
            "orcado": deducoes_orcadas,
            "realizado": deducoes_realizadas,
            "variacao": deducoes_realizadas - deducoes_orcadas,
            "variacao_pct": ((deducoes_realizadas - deducoes_orcadas) / deducoes_orcadas * 100) if deducoes_orcadas > 0 else 0
        })
        
        # Receita Líquida
        rec_liq_orcada = receita_orcada - deducoes_orcadas
        rec_liq_realizada = receita_realizada - deducoes_realizadas
        
        linhas.append({
            "conta": "RECEITA LÍQUIDA",
            "orcado": rec_liq_orcada,
            "realizado": rec_liq_realizada,
            "variacao": rec_liq_realizada - rec_liq_orcada,
            "variacao_pct": ((rec_liq_realizada - rec_liq_orcada) / rec_liq_orcada * 100) if rec_liq_orcada > 0 else 0
        })
        
        # Despesas Fixas
        desp_orcadas = sum(d.valor_mensal for d in motor.despesas_fixas.values())
        desp_realizadas = lanc.total_despesas_fixas
        
        linhas.append({
            "conta": "(-) Despesas Fixas",
            "orcado": desp_orcadas,
            "realizado": desp_realizadas,
            "variacao": desp_realizadas - desp_orcadas,
            "variacao_pct": ((desp_realizadas - desp_orcadas) / desp_orcadas * 100) if desp_orcadas > 0 else 0
        })
        
        # Folha
        folha_orcada = motor.custo_pessoal_mensal
        folha_realizada = lanc.total_folha
        
        linhas.append({
            "conta": "(-) Folha de Pagamento",
            "orcado": folha_orcada,
            "realizado": folha_realizada,
            "variacao": folha_realizada - folha_orcada,
            "variacao_pct": ((folha_realizada - folha_orcada) / folha_orcada * 100) if folha_orcada > 0 else 0
        })
        
        # EBITDA
        ebitda_orcado = rec_liq_orcada - desp_orcadas - folha_orcada
        ebitda_realizado = rec_liq_realizada - desp_realizadas - folha_realizada
        
        linhas.append({
            "conta": "EBITDA",
            "orcado": ebitda_orcado,
            "realizado": ebitda_realizado,
            "variacao": ebitda_realizado - ebitda_orcado,
            "variacao_pct": ((ebitda_realizado - ebitda_orcado) / ebitda_orcado * 100) if ebitda_orcado > 0 else 0
        })
    
    return linhas


def formato_variacao(valor: float, percentual: float) -> str:
    """Formata variação para exibição"""
    sinal = "+" if valor >= 0 else ""
    return f"{sinal}R$ {valor:,.2f} ({sinal}{percentual:.1f}%)"
