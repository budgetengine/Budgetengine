"""
Motor de Cálculo - Budget Engine
Núcleo de simulação que replica a lógica das planilhas Excel
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import json

# ============================================
# ESTRUTURAS DE DADOS
# ============================================

@dataclass
class PremissasMacro:
    """Premissas macroeconômicas"""
    ipca: float = 0.045  # Inflação anual
    igpm: float = 0.05   # Reajuste aluguel
    dissidio: float = 0.06  # Reajuste salarial
    reajuste_tarifas: float = 0.04  # Água, energia, telefone
    reajuste_contratos: float = 0.08
    taxa_cartao_credito: float = 0.0354
    taxa_cartao_debito: float = 0.0211
    taxa_antecipacao: float = 0.05

@dataclass
class FormaPagamento:
    """Distribuição de formas de pagamento"""
    dinheiro_pix: float = 0.30
    cartao_credito: float = 0.65
    cartao_debito: float = 0.05
    outros: float = 0.0
    pct_antecipacao: float = 0.30  # % sobre cartões que antecipa

@dataclass  
class PremissasOperacionais:
    """Premissas operacionais da clínica"""
    num_fisioterapeutas: int = 13
    horas_atendimento_dia: int = 10
    dias_uteis_mes: int = 20
    num_salas: int = 4
    modelo_tributario: str = "PJ - Simples Nacional"
    modo_calculo_sessoes: str = "servico"  # "servico" ou "profissional"

@dataclass
class Servico:
    """Configuração de um serviço"""
    nome: str
    duracao_minutos: int = 50
    pacientes_por_sessao: int = 1
    valor_2025: float = 0.0
    valor_2026: float = 0.0
    pct_reajuste: float = 0.0
    mes_reajuste: int = 3  # Março = 3
    sessoes_mes_base: int = 0
    pct_crescimento: float = 0.0
    usa_sala: bool = True  # False para Domiciliar (não consome sala física)
    
    @property
    def duracao_horas(self) -> float:
        """Duração em horas"""
        return self.duracao_minutos / 60.0

@dataclass
class Profissional:
    """Dados de um profissional"""
    nome: str
    tipo: str = "profissional"  # "proprietario" ou "profissional"
    ativo: bool = True
    sessoes_por_servico: Dict[str, int] = field(default_factory=dict)  # {servico: qtd_mes}
    pct_crescimento_por_servico: Dict[str, float] = field(default_factory=dict)  # {servico: %}


@dataclass
class ConfiguracaoFilial:
    """Configuração de uma filial/unidade"""
    nome: str
    ativa: bool = True


# ============================================
# ESTRUTURAS DE INFRAESTRUTURA (TDABC)
# ============================================

@dataclass
class Sala:
    """Configuração de uma sala física para TDABC"""
    numero: int
    metros_quadrados: float = 0.0
    tipo: str = "Individual"  # "Individual", "Compartilhado", "Reserva"
    servicos_atendidos: List[str] = field(default_factory=list)
    ativa: bool = True
    
    @property
    def qtd_servicos(self) -> int:
        """Quantidade de serviços atendidos na sala"""
        return len(self.servicos_atendidos) if self.ativa else 0
    
    @property
    def m2_por_servico(self) -> float:
        """m² alocado por serviço (dividido igualmente)"""
        if not self.ativa or self.qtd_servicos == 0:
            return 0.0
        return self.metros_quadrados / self.qtd_servicos
    
    def atende_servico(self, servico: str) -> bool:
        """Verifica se a sala atende um serviço específico"""
        return self.ativa and servico in self.servicos_atendidos


@dataclass
class CadastroSalas:
    """Gerenciador de cadastro de salas (TDABC)"""
    salas: List[Sala] = field(default_factory=list)
    horas_funcionamento_dia: int = 10
    dias_uteis_mes: int = 20
    
    def __post_init__(self):
        """Inicializa salas padrão se não houver"""
        if self.salas is None:
            self.salas = []
        if not self.salas:
            self._criar_salas_padrao()
    
    def _criar_salas_padrao(self):
        """Cria estrutura de 15 salas VAZIAS (sem valores pré-preenchidos)"""
        # Todas as salas começam em branco para o usuário preencher
        for i in range(1, 16):
            self.salas.append(Sala(
                numero=i,
                metros_quadrados=0.0,  # Em branco
                tipo="Individual",      # Tipo padrão (pode ser alterado)
                servicos_atendidos=[],  # Sem serviços pré-selecionados
                ativa=(i <= 4)          # Primeiras 4 ativas por padrão
            ))
    
    @property
    def salas_ativas(self) -> List[Sala]:
        """Lista de salas ativas"""
        return [s for s in self.salas if s.ativa]
    
    @property
    def num_salas_ativas(self) -> int:
        """Número de salas ativas"""
        return len(self.salas_ativas)
    
    def sincronizar_num_salas(self, num_salas: int):
        """
        Sincroniza o número de salas ativas com o valor das premissas.
        Ativa/desativa salas conforme necessário.
        Novas salas são ativadas sem valores pré-preenchidos.
        """
        if num_salas < 1:
            num_salas = 1
        if num_salas > len(self.salas):
            num_salas = len(self.salas)
        
        # Ativar as primeiras N salas, desativar o resto
        for i, sala in enumerate(self.salas):
            if i < num_salas:
                sala.ativa = True
            else:
                sala.ativa = False
    
    @property
    def m2_total(self) -> float:
        """Total de m² (todas as salas)"""
        return sum(s.metros_quadrados for s in self.salas)
    
    @property
    def m2_ativo(self) -> float:
        """Total de m² ativo"""
        return sum(s.metros_quadrados for s in self.salas_ativas)
    
    @property
    def horas_disponiveis_mes(self) -> float:
        """Horas disponíveis por sala por mês"""
        return self.horas_funcionamento_dia * self.dias_uteis_mes
    
    @property
    def capacidade_total_horas(self) -> float:
        """Capacidade total em horas (todas salas ativas)"""
        return self.num_salas_ativas * self.horas_disponiveis_mes
    
    def get_sala(self, numero: int) -> Optional[Sala]:
        """Obtém sala por número"""
        for sala in self.salas:
            if sala.numero == numero:
                return sala
        return None
    
    def get_m2_por_servico(self, servico: str) -> float:
        """Calcula m² alocado para um serviço específico"""
        m2_total = 0.0
        for sala in self.salas_ativas:
            if sala.atende_servico(servico):
                m2_total += sala.m2_por_servico
        return m2_total
    
    def get_pct_espaco_servico(self, servico: str) -> float:
        """Calcula % do espaço total alocado para um serviço"""
        if self.m2_ativo <= 0:
            return 0.0
        return self.get_m2_por_servico(servico) / self.m2_ativo
    
    def get_salas_por_servico(self, servico: str) -> List[Sala]:
        """Lista salas que atendem um serviço"""
        return [s for s in self.salas_ativas if s.atende_servico(servico)]
    
    def get_mix_servicos(self) -> Dict[str, Dict]:
        """Retorna mix de serviços com alocações"""
        mix = {}
        servicos_unicos = set()
        
        for sala in self.salas_ativas:
            for srv in sala.servicos_atendidos:
                servicos_unicos.add(srv)
        
        for srv in servicos_unicos:
            salas_srv = self.get_salas_por_servico(srv)
            mix[srv] = {
                "m2_alocado": self.get_m2_por_servico(srv),
                "pct_espaco": self.get_pct_espaco_servico(srv),
                "num_salas": len(salas_srv),
                "salas": [s.numero for s in salas_srv]
            }
        
        return mix
    
    def to_dict(self) -> Dict:
        """Serializa para dicionário"""
        return {
            "horas_funcionamento_dia": self.horas_funcionamento_dia,
            "dias_uteis_mes": self.dias_uteis_mes,
            "salas": [
                {
                    "numero": s.numero,
                    "metros_quadrados": s.metros_quadrados,
                    "tipo": s.tipo,
                    "servicos_atendidos": s.servicos_atendidos,
                    "ativa": s.ativa
                }
                for s in self.salas
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CadastroSalas':
        """Deserializa de dicionário"""
        # IMPORTANTE: Criar as salas ANTES de instanciar o objeto
        # para evitar que __post_init__ crie salas padrão
        salas_carregadas = []
        for s_data in data.get("salas", []):
            salas_carregadas.append(Sala(
                numero=s_data["numero"],
                metros_quadrados=s_data.get("metros_quadrados", 0.0),
                tipo=s_data.get("tipo", "Reserva"),
                servicos_atendidos=s_data.get("servicos_atendidos", []),
                ativa=s_data.get("ativa", False)
            ))
        
        cadastro = cls(
            salas=salas_carregadas if salas_carregadas else None,  # None permite criar padrão se vazio
            horas_funcionamento_dia=data.get("horas_funcionamento_dia", 10),
            dias_uteis_mes=data.get("dias_uteis_mes", 20)
        )
        
        return cadastro
# ESTRUTURAS DE FOLHA DE PAGAMENTO
# ============================================

@dataclass
class PremissasFolha:
    """Premissas para cálculo de folha de pagamento"""
    regime_tributario: str = "PJ - Simples Nacional"
    deducao_dependente_ir: float = 189.59
    aliquota_fgts: float = 0.08
    desconto_vt_pct: float = 0.06
    dias_uteis_mes: int = 22
    mes_dissidio: int = 5  # Maio
    pct_dissidio: float = 0.06
    
    # Tabela INSS - Lista de tuplas (limite_faixa, aliquota, deducao)
    # Valores da planilha Budget_FVS_22
    tabela_inss: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (1631.00, 0.075, 0.0),      # Faixa 1: até R$ 1.631,00 - 7,5%
        (3002.73, 0.09, 24.47),     # Faixa 2: até R$ 3.002,73 - 9%
        (4503.14, 0.12, 114.55),    # Faixa 3: até R$ 4.503,14 - 12%
        (8769.22, 0.14, 204.61),    # Faixa 4: até R$ 8.769,22 - 14%
    ])
    
    # Tabela IR 2026 - Lista de tuplas (limite_faixa, aliquota, deducao)
    # Nova legislação com isenção até R$ 5.000 na base de cálculo
    tabela_ir: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (5000.00, 0.0, 0.0),           # Isento até R$ 5.000
        (7500.00, 0.075, 375.00),      # 7,5%
        (10000.00, 0.15, 937.50),      # 15%
        (12500.00, 0.225, 1687.50),    # 22,5%
        (9999999.99, 0.275, 2312.50),  # 27,5%
    ])


@dataclass
class PremissasSimplesNacional:
    """Premissas para cálculo do Simples Nacional e Carnê Leão"""
    
    # Tabela Anexo III (Fator r >= 28%) - Mais favorável
    tabela_anexo_iii: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (180000, 0.06, 0),
        (360000, 0.112, 9360),
        (720000, 0.132, 17640),
        (1800000, 0.16, 35640),
        (3600000, 0.21, 125640),
        (4800000, 0.33, 648000),
    ])
    
    # Tabela Anexo V (Fator r < 28%) - Menos favorável
    tabela_anexo_v: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (180000, 0.155, 0),
        (360000, 0.18, 4500),
        (720000, 0.195, 9900),
        (1800000, 0.205, 17100),
        (3600000, 0.23, 62100),
        (4800000, 0.305, 540000),
    ])
    
    # Limite Fator R para definir anexo
    limite_fator_r: float = 0.28
    
    # Carnê Leão - Pessoa Física
    faturamento_pf_anual: float = 66000.0  # Faturamento médio PF
    aliquota_inss_pf: float = 0.0  # 0%, 11% ou 20%
    teto_inss_pf: float = 1023.08
    
    # IR 2026 - Lei 15.270/2025
    limite_isencao_ir: float = 5000.0
    teto_redutor_ir: float = 7350.0
    deducao_fixa_ir: float = 528.0
    
    # Tabela IR Progressiva (para Carnê Leão)
    tabela_ir_pf: List[Tuple[float, float, float]] = field(default_factory=lambda: [
        (2428.80, 0.0, 0.0),
        (2826.65, 0.075, 182.16),
        (3751.05, 0.15, 394.16),
        (4664.68, 0.225, 675.49),
        (9999999.99, 0.275, 908.73),
    ])


@dataclass
class FuncionarioCLT:
    """Dados de um funcionário (CLT ou Informal)"""
    nome: str
    cargo: str = ""
    salario_base: float = 0.0
    tipo_vinculo: str = "informal"  # "clt" ou "informal"
    dependentes_ir: int = 0
    vt_dia: float = 0.0
    vr_dia: float = 0.0
    plano_saude: float = 0.0
    plano_odonto: float = 0.0
    mes_admissao: int = 1  # Janeiro
    mes_aumento: int = 13  # 13 = não tem aumento no ano
    pct_reajuste: float = 0.0
    ativo: bool = True


@dataclass
class SocioProLabore:
    """Dados de um sócio com pró-labore e participação societária"""
    nome: str
    prolabore: float = 0.0
    dependentes_ir: int = 0
    mes_reajuste: int = 5  # Maio
    pct_aumento: float = 0.0
    ativo: bool = True
    # Campos para Dividendos
    participacao: float = 1.0  # % de participação (0 a 1) - padrão 100%
    capital: float = 10000.0   # Capital investido (R$)


# ============================================
# ESTRUTURAS DE FISIOTERAPEUTAS
# ============================================

@dataclass
class PremissasFisioterapeutas:
    """Premissas para cálculo de remuneração de fisioterapeutas"""
    # Níveis de remuneração (% sobre faturamento próprio)
    niveis_remuneracao: Dict[int, float] = field(default_factory=lambda: {
        1: 0.35,  # 35%
        2: 0.30,  # 30%
        3: 0.25,  # 25%
        4: 0.20,  # 20%
    })
    # Proprietário
    pct_producao_propria: float = 0.60  # 60% sobre produção própria
    pct_faturamento_total: float = 0.20  # 20% sobre faturamento total
    pct_base_remuneracao_prop: float = 0.75  # 75%
    # Gerência
    pct_gerencia_equipe: float = 0.01  # 1% sobre faturamento da equipe
    pct_base_remuneracao_ger: float = 0.75  # 75%


@dataclass
class Fisioterapeuta:
    """Dados de um fisioterapeuta"""
    nome: str
    cargo: str = "Fisioterapeuta"  # "Fisioterapeuta", "Gerente", "Proprietário"
    nivel: int = 2  # 1, 2, 3 ou 4 (usado quando tipo_remuneracao="percentual" ou "misto")
    filial: str = "Copacabana"
    ativo: bool = True
    # Sessões por serviço (quantidade mensal base)
    sessoes_por_servico: Dict[str, int] = field(default_factory=dict)
    # % crescimento mensal por serviço
    pct_crescimento_por_servico: Dict[str, float] = field(default_factory=dict)
    
    # Tipo de remuneração:
    # - "percentual": usa nível (% sobre faturamento)
    # - "valor_fixo": usa valores_fixos_por_servico (R$ por sessão)
    # - "misto": percentual sobre faturamento + valor fixo adicional por sessão
    tipo_remuneracao: str = "percentual"  # "percentual", "valor_fixo" ou "misto"
    
    # Valores fixos por sessão (usado quando tipo_remuneracao="valor_fixo" ou "misto")
    valores_fixos_por_servico: Dict[str, float] = field(default_factory=dict)
    
    # Percentual customizado (usado em "misto" se diferente do nível)
    pct_customizado: float = 0.0  # Se > 0, usa este em vez do nível
    
    # Escala semanal (horas por dia da semana)
    # v1.79.0: Começa zerada para forçar preenchimento pelo usuário
    escala_semanal: Dict[str, float] = field(default_factory=lambda: {
        "segunda": 0.0, "terca": 0.0, "quarta": 0.0,
        "quinta": 0.0, "sexta": 0.0, "sabado": 0.0
    })
    
    @property
    def horas_semana(self) -> float:
        """Total de horas por semana"""
        return sum(self.escala_semanal.values())
    
    @property
    def horas_mes(self) -> float:
        """Total de horas por mês (4 semanas)"""
        return self.horas_semana * 4
    
    @property
    def media_horas_dia(self) -> float:
        """Média de horas por dia útil"""
        dias_trabalhados = sum(1 for h in self.escala_semanal.values() if h > 0)
        if dias_trabalhados == 0:
            return 0
        return self.horas_semana / dias_trabalhados


@dataclass
class AnaliseOcupacaoMes:
    """Análise de ocupação para um mês específico"""
    mes: int
    ano: int = 2026
    
    # Capacidades (em horas)
    capacidade_profissional: float = 0.0
    capacidade_sala: float = 0.0
    
    # Demandas (em horas)
    demanda_profissional: float = 0.0  # Todas as sessões
    demanda_sala: float = 0.0  # Apenas sessões que usam sala
    
    # Sessões
    total_sessoes: float = 0.0
    sessoes_por_servico: Dict[str, float] = field(default_factory=dict)
    
    # Detalhamento por profissional
    demanda_por_profissional: Dict[str, float] = field(default_factory=dict)
    
    @property
    def taxa_ocupacao_profissional(self) -> float:
        """Taxa de ocupação dos profissionais (0-1)"""
        if self.capacidade_profissional <= 0:
            return 0.0
        return min(1.0, self.demanda_profissional / self.capacidade_profissional)
    
    @property
    def taxa_ocupacao_sala(self) -> float:
        """Taxa de ocupação das salas (0-1)"""
        if self.capacidade_sala <= 0:
            return 0.0
        return min(1.0, self.demanda_sala / self.capacidade_sala)
    
    @property
    def gargalo(self) -> str:
        """Identifica o gargalo operacional"""
        if self.taxa_ocupacao_profissional > self.taxa_ocupacao_sala:
            return "Profissional"
        return "Sala"
    
    @property
    def taxa_ocupacao_efetiva(self) -> float:
        """Taxa de ocupação do recurso mais limitante"""
        return max(self.taxa_ocupacao_profissional, self.taxa_ocupacao_sala)
    
    @property
    def status(self) -> str:
        """Status qualitativo da ocupação"""
        taxa = self.taxa_ocupacao_efetiva
        if taxa < 0.5:
            return "ociosidade"
        elif taxa < 0.7:
            return "saudavel"
        elif taxa < 0.9:
            return "atencao"
        else:
            return "critico"
    
    @property
    def status_emoji(self) -> str:
        """Emoji do status"""
        status_map = {
            "ociosidade": "🟢",
            "saudavel": "🟢",
            "atencao": "🟡",
            "critico": "🔴"
        }
        return status_map.get(self.status, "⚪")
    
    @property
    def status_texto(self) -> str:
        """Texto descritivo do status"""
        status_map = {
            "ociosidade": "Ociosidade Alta - Oportunidade de Crescimento",
            "saudavel": "Saudável - Margem para Variações",
            "atencao": "Atenção - Monitorar de Perto",
            "critico": "Crítico - Risco de Sobrecarga"
        }
        return status_map.get(self.status, "Indefinido")
    
    @property
    def recomendacao(self) -> str:
        """Recomendação baseada no gargalo e status"""
        if self.status == "ociosidade":
            return "Foco em aumentar volume de atendimentos e captação de novos pacientes."
        elif self.status == "saudavel":
            return "Operação equilibrada. Manter monitoramento regular."
        elif self.gargalo == "Sala":
            return "Considere ampliar número de salas ou estender horário de funcionamento."
        else:
            return "Considere contratar mais profissionais ou aumentar carga horária."
    
    # Capacidade ociosa
    @property
    def horas_ociosas_profissional(self) -> float:
        return max(0, self.capacidade_profissional - self.demanda_profissional)
    
    @property
    def horas_ociosas_sala(self) -> float:
        return max(0, self.capacidade_sala - self.demanda_sala)


@dataclass
class AnaliseOcupacaoAnual:
    """Análise consolidada de ocupação para o ano"""
    ano: int = 2026
    meses: List[AnaliseOcupacaoMes] = field(default_factory=list)
    
    # Parâmetros usados
    num_salas: int = 4
    horas_funcionamento_dia: int = 12
    dias_uteis_mes: int = 20
    
    @property
    def capacidade_sala_mes(self) -> float:
        """Capacidade total de salas por mês"""
        return self.num_salas * self.horas_funcionamento_dia * self.dias_uteis_mes
    
    @property
    def media_taxa_profissional(self) -> float:
        """Média anual da taxa de ocupação de profissionais"""
        if not self.meses:
            return 0.0
        return sum(m.taxa_ocupacao_profissional for m in self.meses) / len(self.meses)
    
    @property
    def media_taxa_sala(self) -> float:
        """Média anual da taxa de ocupação de salas"""
        if not self.meses:
            return 0.0
        return sum(m.taxa_ocupacao_sala for m in self.meses) / len(self.meses)
    
    @property
    def gargalo_predominante(self) -> str:
        """Gargalo que aparece mais vezes no ano"""
        if not self.meses:
            return "Indefinido"
        gargalos = [m.gargalo for m in self.meses]
        return max(set(gargalos), key=gargalos.count)
    
    @property
    def total_sessoes_ano(self) -> float:
        """Total de sessões no ano"""
        return sum(m.total_sessoes for m in self.meses)
    
    @property
    def total_horas_demanda_profissional(self) -> float:
        """Total de horas demandadas dos profissionais"""
        return sum(m.demanda_profissional for m in self.meses)
    
    @property
    def total_horas_demanda_sala(self) -> float:
        """Total de horas demandadas das salas"""
        return sum(m.demanda_sala for m in self.meses)


# ============================================
# ESTRUTURAS DE TDABC - RATEIO DE CUSTOS
# ============================================

@dataclass
class CustoIndireto:
    """Custo indireto com direcionador para rateio ABC"""
    nome: str
    valor_mensal: float = 0.0
    direcionador: str = "Receita"  # "m²", "Sessões", "Receita"
    
    def get_valor_mes(self, mes: int, valores_mensais: List[float] = None) -> float:
        """Retorna valor do mês (usa lista de 12 meses se disponível)"""
        if valores_mensais and len(valores_mensais) > mes:
            return valores_mensais[mes]
        return self.valor_mensal


@dataclass
class RateioTDABC:
    """Estrutura de rateio ABC por serviço para um mês"""
    mes: int
    servico: str
    
    # Bases de rateio
    sessoes: float = 0.0
    receita: float = 0.0
    m2_alocado: float = 0.0
    horas_sala: float = 0.0
    
    # Totais para cálculo de %
    total_sessoes: float = 0.0
    total_receita: float = 0.0
    total_m2: float = 0.0
    total_horas_sala: float = 0.0
    
    # Custos rateados
    rateio_m2: float = 0.0
    rateio_sessoes: float = 0.0
    rateio_receita: float = 0.0
    
    @property
    def pct_sessoes(self) -> float:
        """% de sessões do serviço sobre total"""
        if self.total_sessoes <= 0:
            return 0.0
        return self.sessoes / self.total_sessoes
    
    @property
    def pct_receita(self) -> float:
        """% de receita do serviço sobre total"""
        if self.total_receita <= 0:
            return 0.0
        return self.receita / self.total_receita
    
    @property
    def pct_m2(self) -> float:
        """% de m² alocado do serviço sobre total"""
        if self.total_m2 <= 0:
            return 0.0
        return self.m2_alocado / self.total_m2
    
    @property
    def pct_horas(self) -> float:
        """% de horas de sala do serviço sobre total"""
        if self.total_horas_sala <= 0:
            return 0.0
        return self.horas_sala / self.total_horas_sala
    
    @property
    def overhead_total(self) -> float:
        """Total de overhead rateado para este serviço"""
        return self.rateio_m2 + self.rateio_sessoes + self.rateio_receita


@dataclass
class LucroABCServico:
    """Lucro ABC calculado para um serviço"""
    mes: int
    servico: str
    
    # Componentes
    receita: float = 0.0
    custos_variaveis_rateados: float = 0.0
    overhead_rateado: float = 0.0
    
    @property
    def lucro_abc(self) -> float:
        """Lucro ABC = Receita - CV rateado - Overhead"""
        return self.receita - self.custos_variaveis_rateados - self.overhead_rateado
    
    @property
    def margem_abc(self) -> float:
        """Margem ABC em %"""
        if self.receita <= 0:
            return 0.0
        return self.lucro_abc / self.receita
    
    @property
    def margem_contribuicao(self) -> float:
        """Margem de Contribuição = Receita - CV"""
        return self.receita - self.custos_variaveis_rateados
    
    @property
    def pct_mc(self) -> float:
        """% Margem de Contribuição"""
        if self.receita <= 0:
            return 0.0
        return self.margem_contribuicao / self.receita


@dataclass
class AnaliseTDABCMes:
    """Análise TDABC completa para um mês"""
    mes: int
    ano: int = 2026
    
    # Subtotais por direcionador
    subtotal_m2: float = 0.0
    subtotal_sessoes: float = 0.0
    subtotal_receita: float = 0.0
    
    # Rateios por serviço
    rateios: Dict[str, RateioTDABC] = field(default_factory=dict)
    
    # Lucros ABC por serviço
    lucros: Dict[str, LucroABCServico] = field(default_factory=dict)
    
    @property
    def overhead_total(self) -> float:
        """Total de overhead do mês"""
        return self.subtotal_m2 + self.subtotal_sessoes + self.subtotal_receita
    
    @property
    def lucro_total(self) -> float:
        """Lucro ABC total do mês"""
        return sum(l.lucro_abc for l in self.lucros.values())
    
    def get_ranking_lucro(self) -> List[Tuple[str, float, float]]:
        """Ranking de serviços por lucro (nome, lucro, margem)"""
        ranking = [(s, l.lucro_abc, l.margem_abc) for s, l in self.lucros.items()]
        return sorted(ranking, key=lambda x: x[1], reverse=True)


@dataclass
class AnaliseTDABCAnual:
    """Análise TDABC consolidada para o ano"""
    ano: int = 2026
    meses: List[AnaliseTDABCMes] = field(default_factory=list)
    
    @property
    def overhead_total(self) -> float:
        """Overhead total do ano"""
        return sum(m.overhead_total for m in self.meses)
    
    @property
    def lucro_total(self) -> float:
        """Lucro ABC total do ano"""
        return sum(m.lucro_total for m in self.meses)
    
    def get_lucro_servico(self, servico: str) -> float:
        """Lucro ABC total de um serviço no ano"""
        return sum(m.lucros.get(servico, LucroABCServico(0, servico)).lucro_abc for m in self.meses)
    
    def get_receita_servico(self, servico: str) -> float:
        """Receita total de um serviço no ano"""
        return sum(m.lucros.get(servico, LucroABCServico(0, servico)).receita for m in self.meses)
    
    def get_margem_servico(self, servico: str) -> float:
        """Margem ABC média de um serviço"""
        receita = self.get_receita_servico(servico)
        if receita <= 0:
            return 0.0
        return self.get_lucro_servico(servico) / receita
    
    def get_ranking_anual(self) -> List[Dict]:
        """Ranking anual de serviços por lucro ABC"""
        servicos = set()
        for m in self.meses:
            servicos.update(m.lucros.keys())
        
        ranking = []
        for srv in servicos:
            lucro = self.get_lucro_servico(srv)
            receita = self.get_receita_servico(srv)
            margem = self.get_margem_servico(srv)
            ranking.append({
                "servico": srv,
                "receita": receita,
                "lucro_abc": lucro,
                "margem_abc": margem
            })
        
        return sorted(ranking, key=lambda x: x['lucro_abc'], reverse=True)


# ============================================
# ESTRUTURAS DE PONTO DE EQUILÍBRIO
# ============================================

@dataclass
class AnalisePontoEquilibrioMes:
    """Análise de Ponto de Equilíbrio para um mês específico"""
    mes: int
    ano: int = 2026
    
    # Dados base (do DRE)
    receita_liquida: float = 0.0
    custos_variaveis: float = 0.0
    margem_contribuicao: float = 0.0
    custos_fixos: float = 0.0
    ebitda: float = 0.0
    
    # Dados de ocupação
    total_sessoes: float = 0.0
    capacidade_horas: float = 0.0
    demanda_horas: float = 0.0
    horas_ociosas: float = 0.0
    
    # Custo de ociosidade (TDABC)
    custo_infraestrutura: float = 0.0  # Custos de m² (aluguel, energia, etc)
    custo_ociosidade: float = 0.0
    
    @property
    def pct_margem_contribuicao(self) -> float:
        """% da Margem de Contribuição sobre Receita Líquida"""
        if self.receita_liquida <= 0:
            return 0.0
        return self.margem_contribuicao / self.receita_liquida
    
    @property
    def pe_contabil(self) -> float:
        """Ponto de Equilíbrio Contábil = Custos Fixos / % MC"""
        if self.pct_margem_contribuicao <= 0:
            return 0.0
        return self.custos_fixos / self.pct_margem_contribuicao
    
    @property
    def pe_com_ociosidade(self) -> float:
        """PE considerando custo de ociosidade = (CF + Custo Ociosidade) / % MC"""
        if self.pct_margem_contribuicao <= 0:
            return 0.0
        return (self.custos_fixos + self.custo_ociosidade) / self.pct_margem_contribuicao
    
    @property
    def pe_sessoes(self) -> float:
        """PE em número de sessões"""
        if self.receita_liquida <= 0:
            return 0.0
        return (self.pe_contabil / self.receita_liquida) * self.total_sessoes
    
    @property
    def pe_horas(self) -> float:
        """PE em horas de sala"""
        if self.receita_liquida <= 0:
            return 0.0
        return (self.pe_contabil / self.receita_liquida) * self.demanda_horas
    
    @property
    def pe_taxa_ocupacao(self) -> float:
        """PE em taxa de ocupação (0-1)"""
        if self.capacidade_horas <= 0:
            return 0.0
        return self.pe_horas / self.capacidade_horas
    
    @property
    def margem_seguranca_valor(self) -> float:
        """Margem de Segurança em R$"""
        return self.receita_liquida - self.pe_contabil
    
    @property
    def margem_seguranca_pct(self) -> float:
        """Margem de Segurança em % (quanto a receita pode cair)"""
        if self.receita_liquida <= 0:
            return 0.0
        return (self.receita_liquida - self.pe_contabil) / self.receita_liquida
    
    @property
    def gao(self) -> float:
        """Grau de Alavancagem Operacional = MC / EBITDA"""
        if self.ebitda <= 0:
            return 0.0
        return self.margem_contribuicao / self.ebitda
    
    @property
    def lucro_por_sessao(self) -> float:
        """Lucro médio por sessão = EBITDA / Sessões"""
        if self.total_sessoes <= 0:
            return 0.0
        return self.ebitda / self.total_sessoes
    
    @property
    def custo_hora_sala(self) -> float:
        """Custo por hora de sala = Custo Infra / Capacidade"""
        if self.capacidade_horas <= 0:
            return 0.0
        return self.custo_infraestrutura / self.capacidade_horas
    
    @property
    def pct_ociosidade(self) -> float:
        """% de custo ocioso sobre infraestrutura"""
        if self.custo_infraestrutura <= 0:
            return 0.0
        return self.custo_ociosidade / self.custo_infraestrutura
    
    @property
    def status_risco(self) -> str:
        """Status de risco baseado na margem de segurança"""
        ms = self.margem_seguranca_pct
        if ms >= 0.30:
            return "baixo"
        elif ms >= 0.15:
            return "moderado"
        elif ms >= 0.05:
            return "elevado"
        else:
            return "critico"
    
    @property
    def status_emoji(self) -> str:
        """Emoji do status de risco"""
        status_map = {
            "baixo": "🟢",
            "moderado": "🟡",
            "elevado": "🟠",
            "critico": "🔴"
        }
        return status_map.get(self.status_risco, "⚪")
    
    @property
    def status_texto(self) -> str:
        """Texto descritivo do status"""
        status_map = {
            "baixo": "Risco Baixo - Operação Sólida",
            "moderado": "Risco Moderado - Monitorar",
            "elevado": "Risco Elevado - Atenção",
            "critico": "Risco Crítico - Ação Urgente"
        }
        return status_map.get(self.status_risco, "Indefinido")
    
    @property
    def recomendacao(self) -> str:
        """Recomendação baseada no status"""
        if self.status_risco == "baixo":
            return "Margem confortável. Considere investir em crescimento."
        elif self.status_risco == "moderado":
            return "Manter monitoramento regular. Foco em manter/aumentar receita."
        elif self.status_risco == "elevado":
            return "Revisar estrutura de custos. Buscar aumento de receita urgente."
        else:
            return "ALERTA: Risco de prejuízo. Reduzir custos e/ou aumentar preços."


@dataclass
class AnalisePontoEquilibrioAnual:
    """Análise consolidada de Ponto de Equilíbrio para o ano"""
    ano: int = 2026
    meses: List[AnalisePontoEquilibrioMes] = field(default_factory=list)
    
    @property
    def receita_total(self) -> float:
        """Receita líquida total do ano"""
        return sum(m.receita_liquida for m in self.meses)
    
    @property
    def ebitda_total(self) -> float:
        """EBITDA total do ano"""
        return sum(m.ebitda for m in self.meses)
    
    @property
    def custos_fixos_total(self) -> float:
        """Custos fixos totais do ano"""
        return sum(m.custos_fixos for m in self.meses)
    
    @property
    def custo_ociosidade_total(self) -> float:
        """Custo de ociosidade total do ano"""
        return sum(m.custo_ociosidade for m in self.meses)
    
    @property
    def pe_contabil_total(self) -> float:
        """PE contábil total do ano"""
        return sum(m.pe_contabil for m in self.meses)
    
    @property
    def pe_contabil_medio(self) -> float:
        """PE contábil médio mensal"""
        if not self.meses:
            return 0.0
        return self.pe_contabil_total / len(self.meses)
    
    @property
    def margem_seguranca_total(self) -> float:
        """Margem de segurança total do ano"""
        return self.receita_total - self.pe_contabil_total
    
    @property
    def margem_seguranca_media_pct(self) -> float:
        """Margem de segurança média em %"""
        if not self.meses:
            return 0.0
        return sum(m.margem_seguranca_pct for m in self.meses) / len(self.meses)
    
    @property
    def gao_medio(self) -> float:
        """GAO médio do ano"""
        if not self.meses:
            return 0.0
        gaos = [m.gao for m in self.meses if m.gao > 0]
        if not gaos:
            return 0.0
        return sum(gaos) / len(gaos)
    
    @property
    def lucro_por_sessao_medio(self) -> float:
        """Lucro por sessão médio"""
        total_sessoes = sum(m.total_sessoes for m in self.meses)
        if total_sessoes <= 0:
            return 0.0
        return self.ebitda_total / total_sessoes
    
    @property
    def total_sessoes(self) -> float:
        """Total de sessões no ano"""
        return sum(m.total_sessoes for m in self.meses)
    
    @property
    def status_risco_predominante(self) -> str:
        """Status de risco que aparece mais vezes"""
        if not self.meses:
            return "indefinido"
        status_list = [m.status_risco for m in self.meses]
        return max(set(status_list), key=status_list.count)
    
    @property
    def meses_criticos(self) -> int:
        """Quantidade de meses com risco crítico ou elevado"""
        return sum(1 for m in self.meses if m.status_risco in ["critico", "elevado"])


@dataclass
class PEPorServico:
    """Análise de Ponto de Equilíbrio por Serviço (integração TDABC)"""
    servico: str
    
    # Dados de volume e receita
    receita_anual: float = 0.0
    sessoes_ano: float = 0.0
    ticket_medio: float = 0.0
    
    # Dados TDABC
    lucro_abc: float = 0.0
    margem_abc: float = 0.0
    pct_mix: float = 0.0  # Participação na receita total
    
    # Custos rateados
    custos_variaveis_rateados: float = 0.0
    custos_fixos_rateados: float = 0.0
    overhead_abc: float = 0.0
    
    # MC Global (da empresa)
    pct_mc_global: float = 0.95  # Margem de Contribuição % global
    
    @property
    def custo_total_rateado(self) -> float:
        """Custo total alocado ao serviço"""
        return self.custos_variaveis_rateados + self.custos_fixos_rateados
    
    @property
    def pe_receita(self) -> float:
        """
        Ponto de Equilíbrio em R$ para este serviço.
        Fórmula Excel: PE = CF Rateado / %MC Global
        
        Usa a MC global da empresa (não a margem ABC individual).
        """
        if self.pct_mc_global <= 0:
            return 0.0
        return self.custos_fixos_rateados / self.pct_mc_global
    
    @property
    def pe_sessoes(self) -> float:
        """Ponto de Equilíbrio em sessões para este serviço"""
        if self.ticket_medio <= 0:
            return 0.0
        return self.pe_receita / self.ticket_medio
    
    @property
    def margem_seguranca_valor(self) -> float:
        """Margem de segurança em R$"""
        return self.receita_anual - self.pe_receita
    
    @property
    def margem_seguranca_pct(self) -> float:
        """Margem de segurança em %"""
        if self.receita_anual <= 0:
            return 0.0
        return self.margem_seguranca_valor / self.receita_anual
    
    @property
    def status(self) -> str:
        """Status do serviço em relação ao PE"""
        if self.receita_anual >= self.pe_receita:
            return "✅ Acima PE"
        else:
            return "❌ Abaixo PE"
    
    @property
    def folga_sessoes(self) -> float:
        """Sessões acima do PE"""
        return self.sessoes_ano - self.pe_sessoes


# Tabela INSS 2026 (valores default - pode ser sobrescrito por PremissasFolha)
TABELA_INSS_2026 = [
    (1631.00, 0.075, 0.0),
    (3002.73, 0.09, 24.47),
    (4503.14, 0.12, 114.55),
    (8769.22, 0.14, 204.61),
]

# Tabela IR 2026 (nova legislação - isenção R$ 5.000)
TABELA_IR_2026 = [
    (5000.00, 0.0, 0.0),
    (7500.00, 0.075, 375.00),
    (10000.00, 0.15, 937.50),
    (12500.00, 0.225, 1687.50),
    (9999999.99, 0.275, 2312.50),
]


def calcular_inss(salario_bruto: float, tabela_inss: List[Tuple[float, float, float]] = None) -> float:
    """
    Calcula INSS com método de dedução (igual planilha).
    INSS = (Salário × Alíquota) - Dedução
    """
    tabela = tabela_inss if tabela_inss else TABELA_INSS_2026
    
    for limite, aliquota, deducao in tabela:
        if salario_bruto <= limite:
            inss = (salario_bruto * aliquota) - deducao
            return max(0, inss)
    
    # Se passou do teto, usa a última faixa
    _, aliquota, deducao = tabela[-1]
    return max(0, (salario_bruto * aliquota) - deducao)


def calcular_ir(salario_bruto: float, inss: float, dependentes: int, deducao_dep: float = 189.59, tabela_ir: List[Tuple[float, float, float]] = None) -> float:
    """Calcula IR retido na fonte"""
    tabela = tabela_ir if tabela_ir else TABELA_IR_2026
    base_ir = salario_bruto - inss - (dependentes * deducao_dep)
    
    if base_ir <= 0:
        return 0.0
    
    for limite, aliquota, deducao in tabela:
        if base_ir <= limite:
            ir = (base_ir * aliquota) - deducao
            return max(0, ir)
    
    return 0.0


@dataclass
class DespesaFixa:
    """Configuração de uma despesa - modelo completo com suporte a fixa/variável"""
    nome: str
    categoria: str = "Administrativa"  # Administrativa, Ocupação, Operacional, Marketing, Utilidades, Desenvolvimento
    valor_mensal: float = 0.0  # Média 2025 (base) - para despesas fixas
    tipo_reajuste: str = "ipca"  # ipca, igpm, tarifas, contratos, dissidio, nenhum
    mes_reajuste: int = 1  # Janeiro = 1
    pct_adicional: float = 0.0  # % adicional sobre o reajuste
    aplicar_reajuste: bool = True  # Se False, não aplica reajuste em 2026
    tipo_sazonalidade: str = "uniforme"  # "uniforme" ou "sazonal"
    valores_2025: List[float] = field(default_factory=lambda: [0.0] * 12)  # 12 valores mensais
    ativa: bool = True
    
    # ===== NOVOS CAMPOS: TIPO FIXA/VARIÁVEL =====
    tipo_despesa: str = "fixa"  # "fixa" ou "variavel"
    # Para despesas variáveis:
    pct_receita: float = 0.0  # % sobre receita bruta (ex: 0.02 = 2%)
    valor_por_sessao: float = 0.0  # R$ por sessão realizada
    base_variavel: str = "receita"  # "receita" ou "sessao"
    
    def calcular_valor_mes(self, mes: int, indices: Dict[str, float], 
                          receita_mes: float = 0.0, sessoes_mes: float = 0.0) -> float:
        """
        Calcula valor da despesa para um mês específico.
        mes: 0-11 (Janeiro=0, Dezembro=11)
        indices: dicionário com valores dos índices {ipca: 0.045, igpm: 0.05, ...}
        receita_mes: receita bruta do mês (para despesas variáveis)
        sessoes_mes: total de sessões do mês (para despesas variáveis)
        """
        # ===== DESPESA VARIÁVEL =====
        if self.tipo_despesa == "variavel":
            if self.base_variavel == "receita":
                return receita_mes * self.pct_receita
            else:  # sessao
                return sessoes_mes * self.valor_por_sessao
        
        # ===== DESPESA FIXA (comportamento original) =====
        # Pega valor base
        if self.tipo_sazonalidade == "sazonal" and self.valores_2025:
            valor_base = self.valores_2025[mes]
            
            # FALLBACK ROBUSTO: Se valores_2025 estiver zerado OU com valores residuais
            # (muito menores que valor_mensal), usa valor_mensal como base
            # Isso cobre casos onde valores_2025 tem dados inválidos/residuais
            soma_valores_2025 = sum(self.valores_2025)
            valor_esperado_anual = self.valor_mensal * 12
            
            # Se soma de valores_2025 é menor que 10% do esperado, considerar inválido
            if valor_esperado_anual > 0 and soma_valores_2025 < valor_esperado_anual * 0.1:
                valor_base = self.valor_mensal
            
            # Para sazonal, aplica reajuste em todos os meses se habilitado
            if self.aplicar_reajuste:
                indice = indices.get(self.tipo_reajuste, 0)
                valor_base = valor_base * (1 + indice + self.pct_adicional)
        else:
            valor_base = self.valor_mensal
            # Para uniforme, aplica reajuste somente a partir do mês de reajuste
            if self.aplicar_reajuste:
                mes_humano = mes + 1  # Converte para 1-12
                if mes_humano >= self.mes_reajuste:
                    indice = indices.get(self.tipo_reajuste, 0)
                    valor_base = valor_base * (1 + indice + self.pct_adicional)
        
        return valor_base


# Despesas tipicamente FIXAS (para aviso ao usuário)
DESPESAS_TIPICAMENTE_FIXAS = [
    "aluguel", "iptu", "condomínio", "condominio", "seguro", "contabilidade",
    "software", "sistema", "internet", "telefone", "energia", "água", "agua",
    "limpeza", "vigilância", "vigilancia", "manutenção", "manutencao",
    "honorários", "honorarios", "assessoria", "consultoria", "licença", "licenca"
]

# Despesas tipicamente VARIÁVEIS (para aviso ao usuário)
DESPESAS_TIPICAMENTE_VARIAVEIS = [
    "material", "consumo", "descartável", "descartavel", "insumo",
    "comissão", "comissao", "bonificação", "bonificacao", "gratificação", "gratificacao",
    "frete", "entrega", "embalagem", "taxa", "imposto variável"
]

def verificar_tipo_despesa(nome_despesa: str, tipo_selecionado: str) -> str:
    """
    Verifica se o tipo selecionado é compatível com o nome da despesa.
    Retorna mensagem de aviso se houver inconsistência, ou string vazia se OK.
    """
    nome_lower = nome_despesa.lower()
    
    if tipo_selecionado == "variavel":
        for termo in DESPESAS_TIPICAMENTE_FIXAS:
            if termo in nome_lower:
                return f"⚠️ '{nome_despesa}' geralmente é uma despesa FIXA. Tem certeza que deseja classificar como variável?"
    
    elif tipo_selecionado == "fixa":
        for termo in DESPESAS_TIPICAMENTE_VARIAVEIS:
            if termo in nome_lower:
                return f"⚠️ '{nome_despesa}' geralmente é uma despesa VARIÁVEL. Tem certeza que deseja classificar como fixa?"
    
    return ""

@dataclass
class Sazonalidade:
    """Fatores de sazonalidade mensal"""
    fatores: List[float] = field(default_factory=lambda: [
        0.85,  # Janeiro - Férias/Verão
        0.90,  # Fevereiro - Retomada gradual
        1.05,  # Março - Volta às aulas
        1.00,  # Abril - Normal
        1.00,  # Maio - Normal
        0.95,  # Junho - Meio do ano
        0.90,  # Julho - Férias escolares
        1.05,  # Agosto - Retomada
        1.10,  # Setembro - Pico
        1.10,  # Outubro - Pico
        1.05,  # Novembro - Forte
        0.85,  # Dezembro - Férias/Verão
    ])

# ============================================
# CENÁRIOS DE ORÇAMENTO
# ============================================

@dataclass
class Cenario:
    """Configuração de cenário orçamentário"""
    nome: str = "Base"
    descricao: str = "Cenário base sem ajustes"
    
    # Multiplicadores (1.0 = sem alteração)
    fator_receita: float = 1.0      # Impacta sessões e valores
    fator_despesas: float = 1.0     # Impacta despesas fixas e variáveis
    fator_crescimento: float = 1.0  # Impacta crescimento de sessões
    fator_inflacao: float = 1.0     # Impacta reajustes
    
    # Cenários pré-definidos
    @classmethod
    def pessimista(cls) -> 'Cenario':
        return cls(
            nome="Pessimista",
            descricao="Cenário de crise: queda na demanda",
            fator_receita=0.75,
            fator_despesas=1.0,  # Inflação já aplicada via Premissas Macro
            fator_crescimento=0.50,
            fator_inflacao=1.20  # Crise = inflação alta = reajuste maior
        )

    @classmethod
    def conservador(cls) -> 'Cenario':
        return cls(
            nome="Conservador",
            descricao="Cenário cauteloso: leve redução na demanda",
            fator_receita=0.90,
            fator_despesas=1.0,  # Inflação já aplicada via Premissas Macro
            fator_crescimento=0.75,
            fator_inflacao=1.08
        )

    @classmethod
    def base(cls) -> 'Cenario':
        return cls(
            nome="Base",
            descricao="Cenário base: projeção realista",
            fator_receita=1.0,
            fator_despesas=1.0,
            fator_crescimento=1.0,
            fator_inflacao=1.0
        )

    @classmethod
    def otimista(cls) -> 'Cenario':
        return cls(
            nome="Otimista",
            descricao="Cenário favorável: crescimento acelerado",
            fator_receita=1.15,
            fator_despesas=1.0,  # Inflação já aplicada via Premissas Macro
            fator_crescimento=1.30,
            fator_inflacao=0.95  # Favorável = inflação baixa = reajuste menor
        )
    
    @classmethod
    def get_cenarios(cls) -> Dict[str, 'Cenario']:
        """Retorna dicionário com todos os cenários pré-definidos"""
        return {
            "Pessimista": cls.pessimista(),
            "Conservador": cls.conservador(),
            "Base": cls.base(),
            "Otimista": cls.otimista()
        }

# ============================================
# ESTRUTURAS DO MÓDULO FINANCEIRO
# ============================================

@dataclass
class Investimento:
    """Investimento (CAPEX) planejado para o ano"""
    descricao: str = ""
    categoria: str = "Equipamentos"  # Equipamentos, Mobiliário, Tecnologia, Reforma, Veículo, Outros
    valor_total: float = 0.0
    mes_aquisicao: int = 1  # 1-12
    entrada: float = 0.0  # Valor pago à vista
    taxa_mensal: float = 0.05  # Taxa de juros a.m.
    parcelas: int = 12
    beneficio_mensal: float = 0.0  # Economia/receita esperada
    ativo: bool = True
    
    @property
    def valor_financiado(self) -> float:
        return self.valor_total - self.entrada
    
    def calcular_pmt(self) -> float:
        """Calcula valor da parcela (sistema Price)"""
        if self.valor_financiado <= 0 or self.parcelas <= 0:
            return 0.0
        if self.taxa_mensal <= 0:
            return self.valor_financiado / self.parcelas
        
        i = self.taxa_mensal
        n = self.parcelas
        pv = self.valor_financiado
        # PMT = PV × [i(1+i)^n] / [(1+i)^n - 1]
        pmt = pv * (i * (1 + i)**n) / ((1 + i)**n - 1)
        return pmt
    
    def calcular_custo_total(self) -> float:
        """Custo total incluindo juros"""
        return self.entrada + (self.calcular_pmt() * self.parcelas)
    
    def calcular_juros_total(self) -> float:
        """Total de juros pagos"""
        return self.calcular_custo_total() - self.valor_total
    
    def calcular_payback(self) -> float:
        """Meses para retorno do investimento"""
        if self.beneficio_mensal <= 0:
            return 0.0
        return self.valor_total / self.beneficio_mensal
    
    def calcular_juros_mes(self, mes: int) -> float:
        """
        Calcula juros do mês (sistema SAC - amortização constante)
        mes: 1-12
        """
        if mes < self.mes_aquisicao:
            return 0.0
        
        if self.valor_financiado <= 0:
            return 0.0
        
        # Meses desde a aquisição
        meses_decorridos = mes - self.mes_aquisicao
        
        # Sistema SAC: amortização constante
        amortizacao = self.valor_financiado / self.parcelas
        saldo_devedor = self.valor_financiado - (amortizacao * meses_decorridos)
        
        if saldo_devedor <= 0:
            return 0.0
        
        return saldo_devedor * self.taxa_mensal
    
    def calcular_amortizacao_mes(self, mes: int) -> float:
        """Calcula amortização do mês (sistema SAC)"""
        if mes < self.mes_aquisicao:
            return 0.0
        if self.valor_financiado <= 0 or self.parcelas <= 0:
            return 0.0
        
        # Verifica se ainda há parcelas no período
        meses_decorridos = mes - self.mes_aquisicao
        if meses_decorridos >= self.parcelas:
            return 0.0
        
        return self.valor_financiado / self.parcelas
    
    def calcular_parcela_mes(self, mes: int) -> float:
        """
        Calcula PARCELA completa do mês (Juros + Amortização)
        Para o Fluxo de Caixa - saída real de dinheiro
        """
        return self.calcular_juros_mes(mes) + self.calcular_amortizacao_mes(mes)
    
    def calcular_entrada_mes(self, mes: int) -> float:
        """Retorna a entrada (pagamento à vista) no mês da aquisição"""
        if mes == self.mes_aquisicao:
            return self.entrada
        return 0.0


@dataclass
class FinanciamentoExistente:
    """Financiamento/empréstimo já existente"""
    descricao: str = ""
    saldo_devedor: float = 0.0  # Saldo atual da dívida
    taxa_mensal: float = 0.03  # Taxa de juros a.m.
    parcelas_total: int = 100
    parcelas_pagas: int = 0
    mes_inicio_2026: int = 1  # Mês que começa a pagar em 2026 (1-12)
    valor_parcela: float = 0.0  # Valor fixo da parcela
    ativo: bool = True
    
    @property
    def parcelas_restantes(self) -> int:
        return max(0, self.parcelas_total - self.parcelas_pagas)
    
    def calcular_juros_mes(self, mes: int) -> float:
        """
        Calcula juros do mês (sistema SAC)
        mes: 1-12
        """
        if mes < self.mes_inicio_2026:
            return 0.0
        
        if self.saldo_devedor <= 0 or self.parcelas_restantes <= 0:
            return 0.0
        
        # Meses desde início 2026
        meses_pagos_2026 = mes - self.mes_inicio_2026
        
        # Calcula saldo devedor atual
        amortizacao = self.saldo_devedor / self.parcelas_restantes
        saldo_atual = self.saldo_devedor - (amortizacao * meses_pagos_2026)
        
        if saldo_atual <= 0:
            return 0.0
        
        return saldo_atual * self.taxa_mensal
    
    def calcular_amortizacao_mes(self, mes: int) -> float:
        """Calcula amortização do mês (sistema SAC)"""
        if mes < self.mes_inicio_2026:
            return 0.0
        if self.saldo_devedor <= 0 or self.parcelas_restantes <= 0:
            return 0.0
        
        # Verifica se ainda há parcelas
        meses_pagos_2026 = mes - self.mes_inicio_2026
        if meses_pagos_2026 >= self.parcelas_restantes:
            return 0.0
        
        return self.saldo_devedor / self.parcelas_restantes
    
    def calcular_parcela_mes(self, mes: int) -> float:
        """
        Calcula PARCELA completa do mês (Juros + Amortização)
        Para o Fluxo de Caixa - saída real de dinheiro
        """
        return self.calcular_juros_mes(mes) + self.calcular_amortizacao_mes(mes)


@dataclass
class PremissasChequeEspecial:
    """Premissas do cheque especial"""
    taxa_mensal: float = 0.08  # 8% a.m. (taxa padrão cheque especial)
    # Valores utilizados por mês (1-12)
    valores_utilizados: List[float] = field(default_factory=lambda: [0.0] * 12)
    dias_uso: List[int] = field(default_factory=lambda: [0] * 12)
    
    def calcular_juros_mes(self, mes: int) -> float:
        """
        Calcula juros do cheque especial no mês
        mes: 1-12
        Fórmula: Valor × Taxa × (Dias/30)
        """
        idx = mes - 1
        if idx < 0 or idx >= 12:
            return 0.0
        
        valor = self.valores_utilizados[idx]
        dias = self.dias_uso[idx]
        
        if valor <= 0 or dias <= 0:
            return 0.0
        
        return valor * self.taxa_mensal * (dias / 30)


@dataclass
class PremissasAplicacoes:
    """Premissas de aplicações financeiras"""
    saldo_inicial: float = 0.0  # Saldo em Dez/ano anterior
    taxa_selic_anual: float = 0.1225  # 12,25% a.a.
    pct_cdi: float = 1.0  # 100% do CDI
    # Aportes e resgates mensais (1-12)
    aportes: List[float] = field(default_factory=lambda: [0.0] * 12)
    resgates: List[float] = field(default_factory=lambda: [0.0] * 12)
    
    @property
    def taxa_mensal(self) -> float:
        """Taxa mensal equivalente"""
        # Taxa mensal = (1 + Selic)^(1/12) - 1
        return ((1 + self.taxa_selic_anual) ** (1/12) - 1) * self.pct_cdi
    
    def calcular_evolucao_anual(self) -> List[dict]:
        """
        Calcula evolução das aplicações mês a mês
        Retorna lista de dicts com saldo_inicial, aportes, resgates, rendimento, saldo_final
        """
        resultado = []
        saldo = self.saldo_inicial
        
        for mes in range(12):
            aporte = self.aportes[mes] if mes < len(self.aportes) else 0
            resgate = self.resgates[mes] if mes < len(self.resgates) else 0
            rendimento = saldo * self.taxa_mensal
            saldo_final = saldo + aporte - resgate + rendimento
            
            resultado.append({
                "mes": mes + 1,
                "saldo_inicial": saldo,
                "aportes": aporte,
                "resgates": resgate,
                "rendimento": rendimento,
                "saldo_final": saldo_final
            })
            
            saldo = saldo_final
        
        return resultado


@dataclass
class PremissasFinanceiras:
    """Consolidação das premissas financeiras"""
    investimentos: List[Investimento] = field(default_factory=list)
    financiamentos: List[FinanciamentoExistente] = field(default_factory=list)
    cheque_especial: PremissasChequeEspecial = field(default_factory=PremissasChequeEspecial)
    aplicacoes: PremissasAplicacoes = field(default_factory=PremissasAplicacoes)


@dataclass
class PremissasDividendos:
    """Premissas para distribuição de dividendos"""
    # Flag de ativação
    distribuir: bool = True  # Se False, não calcula/distribui dividendos
    
    # Reservas
    pct_reserva_legal: float = 0.05  # 5% (obrigatório S.A., opcional LTDA)
    pct_reserva_investimento: float = 0.20  # 20% (configurável)
    
    # Política de Distribuição
    frequencia: str = "Trimestral"  # "Mensal", "Trimestral", "Semestral", "Anual"
    pct_distribuir: float = 0.30  # 30% do lucro distribuível
    
    # Flag para DRE
    mostrar_no_dre: bool = True  # Se True, mostra dividendos no DRE; Se False, não mostra
    
    def get_periodos(self) -> List[tuple]:
        """Retorna os períodos de acumulação baseado na frequência"""
        if self.frequencia == "Mensal":
            return [(i+1, i+1) for i in range(12)]
        elif self.frequencia == "Trimestral":
            return [(1, 3), (4, 6), (7, 9), (10, 12)]
        elif self.frequencia == "Semestral":
            return [(1, 6), (7, 12)]
        else:  # Anual
            return [(1, 12)]
    
    def get_meses_pagamento(self) -> List[int]:
        """Retorna os meses de pagamento baseado na frequência"""
        if self.frequencia == "Mensal":
            return list(range(1, 13))
        elif self.frequencia == "Trimestral":
            return [3, 6, 9, 12]
        elif self.frequencia == "Semestral":
            return [6, 12]
        else:  # Anual
            return [12]
    
    def get_nome_periodo(self, inicio: int, fim: int) -> str:
        """Retorna nome legível do período"""
        meses_nome = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                      "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        if inicio == fim:
            return meses_nome[inicio - 1]
        elif self.frequencia == "Trimestral":
            trim = {3: "1T", 6: "2T", 9: "3T", 12: "4T"}
            return trim.get(fim, f"{meses_nome[inicio-1]}-{meses_nome[fim-1]}")
        elif self.frequencia == "Semestral":
            return "1º Sem" if fim == 6 else "2º Sem"
        else:
            return "Anual"


# ============================================
# PREMISSAS DO FLUXO DE CAIXA
# ============================================

@dataclass
class ContaReceber:
    """Configuração de conta a receber por serviço"""
    servico: str = ""
    saldo_inicial: float = 0.0  # Saldo de CR do ano anterior
    pmr_dias: int = 30  # Prazo Médio de Recebimento em dias
    
    @property
    def pct_mes_1(self) -> float:
        """% recebido no mês seguinte à venda"""
        if self.pmr_dias <= 30:
            return 1.0
        elif self.pmr_dias >= 60:
            return 0.0
        else:
            return (60 - self.pmr_dias) / 30
    
    @property
    def pct_mes_2(self) -> float:
        """% recebido 2 meses após a venda"""
        return 1.0 - self.pct_mes_1


@dataclass
class PremissasFluxoCaixa:
    """Premissas para o Fluxo de Caixa"""
    
    # Saldos Iniciais (01/Janeiro)
    # Se usar_cp_auto = True, esses valores são calculados baseado na folha de Dezembro
    caixa_inicial: float = 0.0
    cp_fornecedores: float = 0.0  # Contas a Pagar - Fornecedores
    cp_impostos: float = 0.0  # Contas a Pagar - Impostos (DAS/Carnê Dez)
    cp_retirada_proprietarios: float = 0.0  # Comissão proprietários (Dez)
    cp_folha_colaboradores: float = 0.0  # Salários CLT (Dez)
    cp_folha_fisioterapeutas: float = 0.0  # Comissão fisioterapeutas (Dez)
    cp_encargos_clt: float = 0.0  # INSS+FGTS de Dezembro
    usar_cp_folha_auto: bool = True  # Se True, calcula CP baseado na folha de Dezembro
    
    # Contas a Receber por Serviço
    contas_receber: Dict[str, ContaReceber] = field(default_factory=dict)
    
    # Receita estimada dos últimos meses do ano anterior (para cálculo de recebimentos)
    # Isso representa a receita de Out, Nov, Dez do ano anterior que será recebida em Jan, Fev, Mar
    # Se = 0, será calculado automaticamente baseado na receita projetada
    receita_dez_ano_anterior: float = 0.0  # Receita Dezembro ano anterior
    receita_nov_ano_anterior: float = 0.0  # Receita Novembro ano anterior
    receita_out_ano_anterior: float = 0.0  # Receita Outubro ano anterior
    usar_receita_auto: bool = True  # Se True, calcula automaticamente baseado na receita projetada
    
    # Parcelamento em Cartão (% das vendas em cartão)
    # Estrutura de Parcelamento em Cartão de Crédito (% das vendas em cartão)
    # Suporta até 12x - a soma deve ser 100%
    pct_cartao_1x: float = 0.3333   # 33,33% em 1x
    pct_cartao_2x: float = 0.3333   # 33,33% em 2x
    pct_cartao_3x: float = 0.3334   # 33,34% em 3x
    pct_cartao_4x: float = 0.0      # % em 4x
    pct_cartao_5x: float = 0.0      # % em 5x
    pct_cartao_6x: float = 0.0      # % em 6x
    pct_cartao_7x: float = 0.0      # % em 7x
    pct_cartao_8x: float = 0.0      # % em 8x
    pct_cartao_9x: float = 0.0      # % em 9x
    pct_cartao_10x: float = 0.0     # % em 10x
    pct_cartao_11x: float = 0.0     # % em 11x
    pct_cartao_12x: float = 0.0     # % em 12x
    
    # Antecipação de Cartão de Crédito
    # % do valor em cartão crédito que será antecipado (recebido no mesmo mês)
    # A taxa de antecipação é definida em PremissasMacro.taxa_antecipacao
    pct_antecipacao_cartao: float = 0.30  # 30% padrão conforme planilha
    
    def get_parcelamento_list(self) -> list:
        """Retorna lista com % de cada parcela [1x, 2x, ..., 12x]"""
        return [
            self.pct_cartao_1x, self.pct_cartao_2x, self.pct_cartao_3x,
            self.pct_cartao_4x, self.pct_cartao_5x, self.pct_cartao_6x,
            self.pct_cartao_7x, self.pct_cartao_8x, self.pct_cartao_9x,
            self.pct_cartao_10x, self.pct_cartao_11x, self.pct_cartao_12x
        ]
    
    def get_coeficientes_recebimento(self) -> list:
        """
        Calcula coeficientes de recebimento por mês após a venda.
        Retorna lista com % que será recebido em M+1, M+2, ..., M+12.
        
        Exemplo: Se 50% em 2x e 50% em 4x:
        - M+1: 50%×(1/2) + 50%×(1/4) = 25% + 12.5% = 37.5%
        - M+2: 50%×(1/2) + 50%×(1/4) = 25% + 12.5% = 37.5%
        - M+3: 50%×(1/4) = 12.5%
        - M+4: 50%×(1/4) = 12.5%
        """
        parcelamento = self.get_parcelamento_list()
        coeficientes = [0.0] * 12  # M+1 até M+12
        
        for num_parcelas, pct in enumerate(parcelamento, start=1):
            if pct > 0:
                valor_parcela = pct / num_parcelas
                for i in range(num_parcelas):
                    coeficientes[i] += valor_parcela
        
        return coeficientes
    
    # Configuração de timing de recebimentos
    # Se True: Dinheiro/PIX/Débito é recebido NO MESMO MÊS
    # Se False: TODA receita segue o PMR (recebe em M+1 ou M+2) - compatível com planilha
    recebimento_avista_no_mes: bool = True  # Padrão: modo realista (formas de pagamento + antecipação)
    
    # Política de Caixa
    saldo_minimo: float = 0.0  # Saldo mínimo desejado
    
    def __post_init__(self):
        if not self.contas_receber:
            self.contas_receber = {
                "Osteopatia": ContaReceber("Osteopatia", 6000, 60),
                "Individual": ContaReceber("Individual", 7000, 30),
                "Consultório": ContaReceber("Consultório", 10000, 30),
                "Domiciliar": ContaReceber("Domiciliar", 3000, 30),
                "Ginásio": ContaReceber("Ginásio", 1100, 40),
                "Personalizado": ContaReceber("Personalizado", 1000, 55),
            }
    
    def get_saldo_inicial_cr(self, servico: str) -> float:
        """Retorna saldo inicial de CR para um serviço"""
        if servico in self.contas_receber:
            return self.contas_receber[servico].saldo_inicial
        return 0.0
    
    def get_pmr(self, servico: str) -> int:
        """Retorna PMR em dias para um serviço"""
        if servico in self.contas_receber:
            return self.contas_receber[servico].pmr_dias
        return 30  # Padrão
    
    def get_distribuicao_pmr(self, servico: str) -> Tuple[float, float]:
        """Retorna (% mês 1, % mês 2) para um serviço"""
        if servico in self.contas_receber:
            cr = self.contas_receber[servico]
            return (cr.pct_mes_1, cr.pct_mes_2)
        return (1.0, 0.0)  # Padrão: tudo no mês seguinte
    
    def get_total_cp_inicial(self) -> float:
        """Total de Contas a Pagar inicial"""
        return (self.cp_fornecedores + self.cp_impostos + 
                self.cp_retirada_proprietarios + self.cp_folha_colaboradores + 
                self.cp_folha_fisioterapeutas)
    
    def get_total_cr_inicial(self) -> float:
        """Total de Contas a Receber inicial"""
        return sum(cr.saldo_inicial for cr in self.contas_receber.values())


# ============================================
# MOTOR DE CÁLCULO PRINCIPAL
# ============================================

class MotorCalculo:
    """Motor de cálculo do Budget"""
    
    MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
             "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    
    SERVICOS_PADRAO = [
        "Osteopatia", "Individual", "Consultório", 
        "Domiciliar", "Ginásio", "Personalizado"
    ]
    
    def __init__(self):
        # Identificação do cliente
        self.cliente_nome: str = "Cliente"
        self.filial_nome: str = "Filial"
        self.tipo_relatorio: str = "Filial"  # "Filial" ou "Consolidado"
        
        # Premissas
        self.macro = PremissasMacro()
        self.pagamento = FormaPagamento()
        self.operacional = PremissasOperacionais()
        self.sazonalidade = Sazonalidade()
        self.cenario = Cenario.base()  # Cenário padrão
        
        # Configuração dos cenários
        # CONSERVADOR = Base (premissas cadastradas)
        # PESSIMISTA = Ajustes negativos sobre a base
        # OTIMISTA = Ajustes positivos sobre a base
        self.usar_cenarios = True  # Flag para habilitar/desabilitar módulo de cenários
        self.cenario_oficial = "Conservador"  # Cenário padrão para relatórios
        
        # Comparativo com exercício anterior
        self.usar_comparativo_anterior = False  # Habilita/desabilita por cliente
        self.faturamento_anterior = [0.0] * 12  # Faturamento mensal do ano anterior
        self.ano_anterior = 2025  # Ano de referência
        
        # Ajustes por cenário (valores que SOMAM às premissas base)
        # Formato: {servico/despesa: valor_ajuste}
        self.ajustes_cenarios = {
            "Pessimista": {
                "sessoes": {},      # {servico: ajuste_qtd}
                "valores": {},      # {servico: ajuste_valor}
                "despesas": {},     # {despesa: ajuste_valor}
                "descricao": "Cenário de crise: redução de demanda, aumento de custos"
            },
            "Otimista": {
                "sessoes": {},
                "valores": {},
                "despesas": {},
                "descricao": "Cenário favorável: crescimento acelerado, otimização de custos"
            }
        }
        
        # Serviços (valores diferenciados para proprietários e profissionais)
        self.servicos: Dict[str, Servico] = {}
        self.valores_proprietario: Dict[str, float] = {}  # {servico: valor}
        self.valores_profissional: Dict[str, float] = {}  # {servico: valor}
        self._inicializar_servicos_padrao()
        
        # Proprietários e Profissionais
        self.proprietarios: Dict[str, Profissional] = {}
        self.profissionais: Dict[str, Profissional] = {}
        self._inicializar_equipe_padrao()
        
        # Despesas Fixas
        self.despesas_fixas: Dict[str, DespesaFixa] = {}
        self._inicializar_despesas_padrao()
        
        # Custo de Pessoal
        self.custo_pessoal_mensal: float = 63955.31  # Valor base planilha FVS (jan): Fisios + Props + Pró-Labore + CLT
        self.mes_dissidio: int = 5  # Maio
        
        # Folha de Pagamento e Pró-Labore
        self.premissas_folha = PremissasFolha()
        self.funcionarios_clt: Dict[str, FuncionarioCLT] = {}
        self.socios_prolabore: Dict[str, SocioProLabore] = {}
        self._inicializar_folha_padrao()
        
        # Fisioterapeutas
        self.premissas_fisio = PremissasFisioterapeutas()
        self.fisioterapeutas: Dict[str, Fisioterapeuta] = {}
        self._inicializar_fisioterapeutas_padrao()
        
        # Simples Nacional / Carnê Leão
        self.premissas_simples = PremissasSimplesNacional()
        
        # Módulo Financeiro
        self.premissas_financeiras = PremissasFinanceiras()
        self._inicializar_financeiro_padrao()
        
        # Módulo Dividendos
        self.premissas_dividendos = PremissasDividendos()
        
        # Módulo Fluxo de Caixa
        self.premissas_fc = PremissasFluxoCaixa()
        
        # Módulo TDABC - Cadastro de Salas
        self.cadastro_salas = CadastroSalas(
            horas_funcionamento_dia=self.operacional.horas_atendimento_dia,
            dias_uteis_mes=self.operacional.dias_uteis_mes
        )
        
        # Resultados calculados
        self.receita_bruta = {}
        self.deducoes = {}
        self.custos = {}
        self.despesas = {}
        self.dre = {}
        self.fluxo_caixa = {}  # Novo: armazena resultado do FC
        self.fluxo_caixa = {}
    
    def _inicializar_servicos_padrao(self):
        """Inicializa serviços com valores padrão"""
        # Formato: valor_2025 (antes reajuste), valor_2026 (após reajuste), pct_reajuste, mes_reajuste
        # usa_sala: True para todos exceto Domiciliar
        configs = {
            # Proprietários usam valor de Osteopatia
            "Osteopatia": {"duracao": 60, "valor_2025_prop": 322, "valor_2026_prop": 335, "valor_prof": 0, "mes_reajuste": 3, "usa_sala": True},
            # Profissionais
            "Individual": {"duracao": 90, "valor_2025_prop": 0, "valor_2026_prop": 0, "valor_2025_prof": 182.09, "valor_2026_prof": 192, "mes_reajuste": 3, "usa_sala": True},
            "Consultório": {"duracao": 50, "valor_2025_prop": 0, "valor_2026_prop": 0, "valor_2025_prof": 223.27, "valor_2026_prof": 235, "mes_reajuste": 3, "usa_sala": True},
            "Domiciliar": {"duracao": 50, "valor_2025_prop": 0, "valor_2026_prop": 0, "valor_2025_prof": 262.82, "valor_2026_prof": 275, "mes_reajuste": 3, "usa_sala": False},  # NÃO USA SALA!
            "Ginásio": {"duracao": 50, "valor_2025_prop": 0, "valor_2026_prop": 0, "valor_2025_prof": 143.64, "valor_2026_prof": 151, "mes_reajuste": 3, "usa_sala": True},
            "Personalizado": {"duracao": 50, "valor_2025_prop": 0, "valor_2026_prop": 0, "valor_2025_prof": 199, "valor_2026_prof": 209, "mes_reajuste": 3, "usa_sala": True},
        }
        
        for nome, cfg in configs.items():
            # Calcula % de reajuste
            if "valor_2025_prof" in cfg and cfg.get("valor_2025_prof", 0) > 0:
                pct_reajuste = (cfg["valor_2026_prof"] - cfg["valor_2025_prof"]) / cfg["valor_2025_prof"]
                valor_base = cfg["valor_2026_prof"]
            elif cfg.get("valor_2025_prop", 0) > 0:
                pct_reajuste = (cfg["valor_2026_prop"] - cfg["valor_2025_prop"]) / cfg["valor_2025_prop"]
                valor_base = cfg["valor_2026_prop"]
            else:
                pct_reajuste = 0.05
                valor_base = 0
            
            self.servicos[nome] = Servico(
                nome=nome,
                duracao_minutos=cfg["duracao"],
                valor_2026=valor_base,
                sessoes_mes_base=0,  # Agora usa dos profissionais
                pct_reajuste=pct_reajuste,
                mes_reajuste=cfg.get("mes_reajuste", 3),
                usa_sala=cfg.get("usa_sala", True)  # Default True
            )
            
            # Valores separados para antes e depois do reajuste
            self.valores_proprietario[nome] = {
                "antes": cfg.get("valor_2025_prop", 0),
                "depois": cfg.get("valor_2026_prop", 0)
            }
            self.valores_profissional[nome] = {
                "antes": cfg.get("valor_2025_prof", 0),
                "depois": cfg.get("valor_2026_prof", 0)
            }
    
    def _inicializar_equipe_padrao(self):
        """Inicializa equipe padrão baseada no arquivo FVS - usando BASE 2025"""
        # Proprietário - BASE 2025: 19 sessões (não 21 que é a meta)
        self.proprietarios["Felipe Vidal"] = Profissional(
            nome="Felipe Vidal",
            tipo="proprietario",
            sessoes_por_servico={"Osteopatia": 19},  # BASE 2025
            pct_crescimento_por_servico={"Osteopatia": 0.105263}  # 10.53%
        )
        
        # Profissionais com sessões BASE 2025 e % crescimento individual
        profissionais_config = {
            "Claudia": {
                "sessoes": {"Consultório": 75, "Domiciliar": 1},  # Removido Ginásio(1) e Personalizado(4) - não estão na planilha real
                "crescimento": {"Consultório": 0.0667, "Domiciliar": 1.0}
            },
            "Elane": {"sessoes": {}, "crescimento": {}},
            "Felipe Barros": {
                "sessoes": {"Individual": 77, "Domiciliar": 2, "Ginásio": 3},
                "crescimento": {"Individual": 0.0519, "Domiciliar": 0.5, "Ginásio": 1.0}
            },
            "Fernando Zacca": {"sessoes": {}, "crescimento": {}},
            "Igor": {"sessoes": {}, "crescimento": {}},
            "Igor Melgaço": {
                "sessoes": {"Domiciliar": 7},
                "crescimento": {"Domiciliar": 0.1429}
            },
            "Isabelle": {
                "sessoes": {"Consultório": 1, "Personalizado": 58},
                "crescimento": {"Consultório": 1.0, "Personalizado": 0.0517}
            },
            "Juliana": {
                "sessoes": {"Individual": 1, "Consultório": 14, "Ginásio": 155},
                "crescimento": {"Individual": 1.0, "Consultório": 0.1429, "Ginásio": 0.0645}
            },
            "Pablo": {
                "sessoes": {"Domiciliar": 4, "Personalizado": 82},
                "crescimento": {"Domiciliar": 0.25, "Personalizado": 0.0488}
            },
            "Paty": {
                "sessoes": {"Individual": 66, "Domiciliar": 3, "Ginásio": 9, "Personalizado": 3},
                "crescimento": {"Individual": 0.0606, "Domiciliar": 0.3333, "Ginásio": 0.4444, "Personalizado": 0.3333}
            },
            "Pedro": {"sessoes": {}, "crescimento": {}},
            "Yuri": {
                "sessoes": {"Individual": 1, "Consultório": 2, "Domiciliar": 11, "Ginásio": 224},
                "crescimento": {"Individual": 1.0, "Consultório": 0.5, "Domiciliar": 0.0909, "Ginásio": 0.0491}
            },
        }
        
        for nome, config in profissionais_config.items():
            self.profissionais[nome] = Profissional(
                nome=nome,
                tipo="profissional",
                sessoes_por_servico=config["sessoes"],
                pct_crescimento_por_servico=config["crescimento"]
            )
    
    def _inicializar_despesas_padrao(self):
        """Inicializa despesas fixas padrão baseadas na planilha FVS Budget_22"""
        # Dados completos extraídos das abas 'Diretrizes Despesas' e 'Projeção Despesas'
        # Campo 'aplicar_reajuste' baseado na coluna VAR% da planilha
        despesas_config = [
            {
                "nome": "Aluguel",
                "categoria": "Ocupação",
                "indice": "igpm",
                "mes_reajuste": 6,
                "pct_adicional": 0,
                "aplicar_reajuste": False,  # VAR% = 0 na planilha
                "media_2025": 8408.55,
                "sazonalidade": "uniforme",
                "valores_2025": [7427.0, 8173.0, 8124.22, 8182.09, 8739.69, 8678.92, 9249.04, 8424.28, 8644.49, 8425.66, 8425.66, 8408.55],
            },
            {
                "nome": "IPTU",
                "categoria": "Ocupação",
                "indice": "ipca",
                "mes_reajuste": 2,
                "pct_adicional": 0,
                "aplicar_reajuste": False,
                "media_2025": 0.00,
                "sazonalidade": "uniforme",
                "valores_2025": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            },
            {
                "nome": "Condomínio",
                "categoria": "Ocupação",
                "indice": "tarifas",
                "mes_reajuste": 1,
                "pct_adicional": 0,
                "aplicar_reajuste": False,
                "media_2025": 0.00,
                "sazonalidade": "uniforme",
                "valores_2025": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            },
            {
                "nome": "Energia",
                "categoria": "Utilidades",
                "indice": "tarifas",
                "mes_reajuste": 7,
                "pct_adicional": 0,
                "aplicar_reajuste": True,  # VAR% = 4%
                "media_2025": 1577.45,
                "sazonalidade": "sazonal",
                "valores_2025": [1983.11, 2396.64, 2630.79, 2108.41, 1116.22, 1174.24, 1143.95, 981.48, 1229.12, 1227.97, 1360.0, 1577.45],
            },
            {
                "nome": "TV/Telefone/Internet",
                "categoria": "Utilidades",
                "indice": "tarifas",
                "mes_reajuste": 5,
                "pct_adicional": 0,
                "aplicar_reajuste": False,  # VAR% = 0
                "media_2025": 360.20,
                "sazonalidade": "sazonal",
                "valores_2025": [340.29, 340.29, 340.28, 342.22, 357.11, 356.51, 372.01, 372.01, 372.01, 372.02, 397.5, 360.20],
            },
            {
                "nome": "Limpeza",
                "categoria": "Operacional",
                "indice": "dissidio",
                "mes_reajuste": 5,
                "pct_adicional": 0,
                "aplicar_reajuste": False,  # VAR% = 0
                "media_2025": 767.13,
                "sazonalidade": "uniforme",
                "valores_2025": [0.0, 511.91, 626.45, 1139.85, 679.4, 972.72, 597.5, 1029.17, 1345.65, 762.35, 773.4, 767.13],
            },
            {
                "nome": "Manutenção",
                "categoria": "Operacional",
                "indice": "igpm",
                "mes_reajuste": 1,
                "pct_adicional": 0,
                "aplicar_reajuste": True,  # VAR% = 5%
                "media_2025": 474.89,
                "sazonalidade": "sazonal",
                "valores_2025": [582.1, 651.7, 0.0, 2100.0, 0.0, 0.0, 200.0, 1690.0, 0.0, 0.0, 0.0, 474.89],
            },
            {
                "nome": "Seguros",
                "categoria": "Administrativa",
                "indice": "igpm",
                "mes_reajuste": 4,
                "pct_adicional": 0,
                "aplicar_reajuste": False,  # VAR% ≈ 0
                "media_2025": 60.15,
                "sazonalidade": "sazonal",  # Usa valores históricos
                "valores_2025": [36.14, 408.67, 36.14, 36.14, 36.14, 36.14, 36.14, 0.0, 36.14, 0.0, 0.0, 60.15],
            },
            {
                "nome": "Sistema",
                "categoria": "Administrativa",
                "indice": "igpm",
                "mes_reajuste": 1,
                "pct_adicional": 0,
                "aplicar_reajuste": True,  # VAR% = 5%
                "media_2025": 595.76,
                "sazonalidade": "uniforme",
                "valores_2025": [508.7, 514.94, 514.94, 513.26, 517.7, 1383.35, 523.1, 521.9, 514.94, 515.54, 525.0, 595.76],
            },
            {
                "nome": "Compras",
                "categoria": "Operacional",
                "indice": "igpm",
                "mes_reajuste": 1,
                "pct_adicional": 0,
                "aplicar_reajuste": True,  # VAR% = 5%
                "media_2025": 5873.46,
                "sazonalidade": "sazonal",
                "valores_2025": [7837.34, 4439.28, 4725.35, 3705.0, 5139.82, 5836.66, 6052.03, 7620.27, 6173.32, 6353.91, 6725.06, 5873.46],
            },
            {
                "nome": "Contabilidade",
                "categoria": "Administrativa",
                "indice": "igpm",
                "mes_reajuste": 1,
                "pct_adicional": 0,
                "aplicar_reajuste": True,  # VAR% = 5%
                "media_2025": 1026.55,
                "sazonalidade": "uniforme",
                "valores_2025": [666.0, 759.0, 759.0, 759.0, 759.0, 759.0, 759.0, 1518.0, 1518.0, 1518.0, 1518.0, 1026.55],
            },
            {
                "nome": "Marketing",
                "categoria": "Marketing",
                "indice": "nenhum",
                "mes_reajuste": 1,
                "pct_adicional": 0.10,  # 10% adicional conforme planilha
                "aplicar_reajuste": True,  # VAR% = 10%
                "media_2025": 2343.57,
                "sazonalidade": "sazonal",
                "valores_2025": [3992.21, 2100.0, 2250.0, 2250.0, 1737.02, 2300.0, 2150.0, 2250.0, 2250.0, 2250.0, 2250.0, 2343.57],
            },
            {
                "nome": "Serviços Terceiros",
                "categoria": "Operacional",
                "indice": "dissidio",
                "mes_reajuste": 5,
                "pct_adicional": 0,
                "aplicar_reajuste": False,  # VAR% = 0
                "media_2025": 588.54,
                "sazonalidade": "uniforme",
                "valores_2025": [0.0, 0.0, 0.0, 0.0, 149.4, 749.4, 1652.8, 1325.64, 759.64, 725.64, 1111.44, 588.54],
            },
            {
                "nome": "Cursos",
                "categoria": "Desenvolvimento",
                "indice": "igpm",
                "mes_reajuste": 1,
                "pct_adicional": 0,
                "aplicar_reajuste": True,  # VAR% = 5%
                "media_2025": 1722.73,
                "sazonalidade": "sazonal",
                "valores_2025": [925.0, 925.0, 925.0, 3850.0, 3850.0, 3850.0, 925.0, 925.0, 925.0, 925.0, 925.0, 1722.73],
            },
        ]
        
        for cfg in despesas_config:
            self.despesas_fixas[cfg["nome"]] = DespesaFixa(
                nome=cfg["nome"],
                categoria=cfg["categoria"],
                valor_mensal=cfg["media_2025"],
                tipo_reajuste=cfg["indice"],
                mes_reajuste=cfg["mes_reajuste"],
                pct_adicional=cfg["pct_adicional"],
                aplicar_reajuste=cfg.get("aplicar_reajuste", True),
                tipo_sazonalidade=cfg["sazonalidade"],
                valores_2025=cfg["valores_2025"]
            )
    
    def _inicializar_folha_padrao(self):
        """Inicializa dados de folha de pagamento baseados na planilha FVS Budget_22"""
        
        # Premissas de folha
        self.premissas_folha = PremissasFolha(
            regime_tributario="PJ - Simples Nacional",
            deducao_dependente_ir=189.59,
            aliquota_fgts=0.08,
            desconto_vt_pct=0.06,
            dias_uteis_mes=22,
            mes_dissidio=5,  # Maio
            pct_dissidio=0.06
        )
        
        # Funcionários (da planilha - com tipo de vínculo)
        # CLT = com carteira, tem FGTS, INSS
        # Informal = sem carteira, não tem FGTS
        funcionarios = [
            {"nome": "Lucia", "cargo": "Administrativo", "salario": 1030.0, "vinculo": "informal"},
            {"nome": "Flávio", "cargo": "Administrativo", "salario": 1000.0, "vinculo": "informal"},
            {"nome": "Fabiana", "cargo": "Administrativo", "salario": 1500.0, "vinculo": "informal"},
            {"nome": "Rafa", "cargo": "Administrativo", "salario": 1200.0, "vinculo": "informal"},
            {"nome": "Rubia", "cargo": "Administrativo", "salario": 500.0, "vinculo": "informal"},
            {"nome": "Karine", "cargo": "Administrativo", "salario": 1800.0, "vinculo": "clt"},  # CLT
            {"nome": "Sirley", "cargo": "Administrativo", "salario": 1800.0, "vinculo": "clt"},  # CLT
            {"nome": "Guilherme", "cargo": "Estagiário", "salario": 400.0, "vinculo": "informal"},
            {"nome": "João", "cargo": "Estagiário", "salario": 500.0, "vinculo": "informal"},
            {"nome": "Karine E.", "cargo": "Estagiário", "salario": 500.0, "vinculo": "informal"},
            {"nome": "Mariana", "cargo": "Estagiário", "salario": 500.0, "vinculo": "informal"},
        ]
        
        for func in funcionarios:
            self.funcionarios_clt[func["nome"]] = FuncionarioCLT(
                nome=func["nome"],
                cargo=func["cargo"],
                salario_base=func["salario"],
                tipo_vinculo=func["vinculo"],
                mes_admissao=1,
                mes_aumento=13
            )
        
        # Sócios Pró-Labore (da planilha)
        self.socios_prolabore["Felipe Vidal"] = SocioProLabore(
            nome="Felipe Vidal",
            prolabore=1631.0,
            dependentes_ir=0,
            mes_reajuste=5,  # Maio
            pct_aumento=0.0,
            participacao=1.0,  # 100%
            capital=10000.0    # R$ 10.000
        )
    
    def _inicializar_fisioterapeutas_padrao(self):
        """Inicializa fisioterapeutas baseados na planilha FVS Budget_22"""
        
        # Premissas
        self.premissas_fisio = PremissasFisioterapeutas(
            niveis_remuneracao={1: 0.35, 2: 0.30, 3: 0.25, 4: 0.20},
            pct_producao_propria=0.60,
            pct_faturamento_total=0.20,
            pct_base_remuneracao_prop=0.75,
            pct_gerencia_equipe=0.01,
            pct_base_remuneracao_ger=0.75
        )
        
        # Escalas semanais padrão (baseadas na planilha Taxa de Ocupação)
        escala_integral = {"segunda": 8.0, "terca": 8.0, "quarta": 8.0, "quinta": 8.0, "sexta": 8.0, "sabado": 0.0}  # 40h/sem
        escala_parcial_3h = {"segunda": 3.0, "terca": 3.0, "quarta": 3.0, "quinta": 3.0, "sexta": 3.0, "sabado": 0.0}  # 15h/sem
        escala_parcial_alt = {"segunda": 3.0, "terca": 0.0, "quarta": 3.0, "quinta": 0.0, "sexta": 3.0, "sabado": 0.0}  # 9h/sem
        escala_juliana = {"segunda": 8.0, "terca": 10.0, "quarta": 8.0, "quinta": 10.0, "sexta": 8.0, "sabado": 0.0}  # 44h/sem
        escala_inativa = {"segunda": 0.0, "terca": 0.0, "quarta": 0.0, "quinta": 0.0, "sexta": 0.0, "sabado": 0.0}  # 0h/sem
        
        # Proprietário - Felipe Vidal (Osteopatia) - não entra aqui, usa cálculo próprio
        self.fisioterapeutas["Felipe Vidal"] = Fisioterapeuta(
            nome="Felipe Vidal",
            cargo="Proprietário",
            nivel=0,
            filial="Copacabana",
            sessoes_por_servico={},  # Calculado separadamente
            pct_crescimento_por_servico={},
            escala_semanal=escala_parcial_3h.copy()  # 15h/sem = 60h/mês
        )
        
        # Sessões BASE 2025 por fisioterapeuta (da planilha Diretrizes Clinica)
        # Escalas da planilha Taxa de Ocupação
        # Total 2025: Individual=145, Consultório=92, Domiciliar=28, Ginásio=392, Personalizado=147
        fisios_config = [
            {"nome": "Claudia", "cargo": "Gerente", "nivel": 2, 
             "sessoes": {"Consultório": 75, "Domiciliar": 1, "Ginásio": 1, "Personalizado": 4},
             "escala": escala_integral},  # 40h/sem = 160h/mês
            {"nome": "Elane", "cargo": "Fisioterapeuta", "nivel": 2, "sessoes": {},
             "escala": escala_inativa},  # Inativo
            {"nome": "Felipe Barros", "cargo": "Fisioterapeuta", "nivel": 3, 
             "sessoes": {"Individual": 77, "Domiciliar": 2, "Ginásio": 3},
             "escala": escala_integral},  # 40h/sem = 160h/mês
            {"nome": "Fernando Zacca", "cargo": "Fisioterapeuta", "nivel": 2, "sessoes": {},
             "escala": escala_inativa},  # Inativo
            {"nome": "Igor", "cargo": "Fisioterapeuta", "nivel": 2, "sessoes": {},
             "escala": escala_inativa},  # Inativo
            {"nome": "Igor Melgaço", "cargo": "Fisioterapeuta", "nivel": 2, 
             "sessoes": {"Domiciliar": 7},
             "escala": escala_parcial_alt},  # 9h/sem = 60h/mês (3x por semana)
            {"nome": "Isabelle", "cargo": "Fisioterapeuta", "nivel": 3, 
             "sessoes": {"Consultório": 1, "Personalizado": 58},
             "escala": escala_integral},  # 40h/sem = 160h/mês
            {"nome": "Juliana", "cargo": "Fisioterapeuta", "nivel": 2, 
             "sessoes": {"Individual": 1, "Consultório": 14, "Ginásio": 155},
             "escala": escala_juliana},  # 44h/sem = 176h/mês
            {"nome": "Pablo", "cargo": "Fisioterapeuta", "nivel": 3, 
             "sessoes": {"Domiciliar": 4, "Personalizado": 82},
             "escala": escala_integral},  # 40h/sem = 160h/mês
            {"nome": "Paty", "cargo": "Fisioterapeuta", "nivel": 3, 
             "sessoes": {"Individual": 66, "Domiciliar": 3, "Ginásio": 9, "Personalizado": 3},
             "escala": escala_parcial_3h},  # 15h/sem = 60h/mês
            {"nome": "Pedro", "cargo": "Fisioterapeuta", "nivel": 2, "sessoes": {},
             "escala": escala_inativa},  # Inativo
            {"nome": "Yuri", "cargo": "Fisioterapeuta", "nivel": 3, 
             "sessoes": {"Individual": 1, "Consultório": 2, "Domiciliar": 11, "Ginásio": 224},
             "escala": escala_integral},  # 40h/sem = 160h/mês
        ]
        
        for cfg in fisios_config:
            self.fisioterapeutas[cfg["nome"]] = Fisioterapeuta(
                nome=cfg["nome"],
                cargo=cfg["cargo"],
                nivel=cfg["nivel"],
                filial="Copacabana",
                sessoes_por_servico=cfg["sessoes"],
                pct_crescimento_por_servico={},
                escala_semanal=cfg["escala"].copy()
            )
    
    def _inicializar_financeiro_padrao(self):
        """Inicializa módulo financeiro com valores da planilha"""
        
        # Investimento exemplo da planilha (pode ser removido pelo usuário)
        investimento_exemplo = Investimento(
            descricao="Equipamentos",
            categoria="Equipamentos",
            valor_total=1000000.0,
            mes_aquisicao=3,  # Março
            entrada=500000.0,
            taxa_mensal=0.05,  # 5% a.m.
            parcelas=60,
            beneficio_mensal=0.0,
            ativo=False  # Desativado por padrão
        )
        
        # Financiamento existente exemplo
        financiamento_exemplo = FinanciamentoExistente(
            descricao="Empréstimo Bancário",
            saldo_devedor=5000000.0,
            taxa_mensal=0.03,  # 3% a.m.
            parcelas_total=100,
            parcelas_pagas=0,
            mes_inicio_2026=6,  # Junho
            valor_parcela=175000.0,
            ativo=False  # Desativado por padrão
        )
        
        self.premissas_financeiras = PremissasFinanceiras(
            investimentos=[investimento_exemplo],
            financiamentos=[financiamento_exemplo],
            cheque_especial=PremissasChequeEspecial(
                taxa_mensal=0.08,  # 8% a.m.
                valores_utilizados=[0.0] * 12,
                dias_uso=[0] * 12
            ),
            aplicacoes=PremissasAplicacoes(
                saldo_inicial=0.0,
                taxa_selic_anual=0.1225,  # 12,25% a.a.
                pct_cdi=1.0,
                aportes=[0.0] * 12,
                resgates=[0.0] * 12
            )
        )
    
    def get_valor_servico(self, servico: str, mes: int, tipo: str = "profissional") -> float:
        """
        Retorna o valor do serviço para o mês, considerando reajuste.
        tipo: "proprietario" ou "profissional"
        
        Args:
            servico: Nome do serviço
            mes: Índice do mês (0-11, onde 0=Janeiro)
            tipo: Tipo de profissional
        
        VERSÃO DINÂMICA: Usa valores cadastrados em self.servicos
        valor_2026 = valor BASE (antes do reajuste)
        Após mês de reajuste: valor_base * (1 + pct_reajuste)
        """
        # Verifica se o serviço existe
        if servico not in self.servicos:
            return 0.0
        
        srv = self.servicos[servico]
        valor_base = srv.valor_2026  # Valor BASE (antes do reajuste)
        pct_reajuste = srv.pct_reajuste
        mes_reajuste = srv.mes_reajuste  # 1-12 (ex: Março=3)
        
        # Converte mes_reajuste para índice 0-11 para comparação
        # Se reajuste é em Março (3), então a partir de mes=2 (Março, índice 0-based) usa valor novo
        mes_reajuste_idx = mes_reajuste - 1
        
        # A partir do mês de reajuste, aplica o percentual
        if mes >= mes_reajuste_idx and pct_reajuste > 0:
            # Valor após reajuste = valor_base * (1 + pct_reajuste)
            return valor_base * (1 + pct_reajuste)
        
        # Antes do reajuste: valor base cadastrado
        return valor_base
    
    def get_sessoes_servico_mes(self, servico: str, mes: int) -> float:
        """
        Retorna quantidade de sessões do serviço para o mês.
        
        Args:
            servico: Nome do serviço
            mes: Índice do mês (0-11, onde 0=Janeiro)
        
        Modo "servico": Usa sessoes_mes_base e pct_crescimento do serviço
        Modo "profissional": Soma sessões de todos os fisioterapeutas
        """
        if mes < 0 or mes > 11:
            return 0.0
        
        sessoes_base = 0.0
        pct_crescimento = 0.0
        
        # ========================================
        # MODO SERVIÇO: Usa dados direto do serviço
        # ========================================
        if self.operacional.modo_calculo_sessoes == "servico":
            if servico in self.servicos:
                srv = self.servicos[servico]
                sessoes_base = srv.sessoes_mes_base
                pct_crescimento = srv.pct_crescimento
            else:
                return 0.0
        
        # ========================================
        # MODO PROFISSIONAL: Soma dos fisioterapeutas
        # ========================================
        else:
            qtd_com_crescimento = 0
            
            # Soma sessões de todos os fisioterapeutas para este serviço
            for fisio in self.fisioterapeutas.values():
                if not fisio.ativo:
                    continue
                sessoes_srv = fisio.sessoes_por_servico.get(servico, 0)
                if sessoes_srv > 0:
                    sessoes_base += sessoes_srv
                    # Pega crescimento individual se existir
                    cresc = fisio.pct_crescimento_por_servico.get(servico, 0)
                    if cresc > 0:
                        pct_crescimento += cresc
                        qtd_com_crescimento += 1
            
            # Se não encontrou fisioterapeutas, tenta nos proprietários (estrutura antiga)
            if sessoes_base == 0:
                for prop in self.proprietarios.values():
                    if not prop.ativo:
                        continue
                    sessoes_srv = prop.sessoes_por_servico.get(servico, 0)
                    if sessoes_srv > 0:
                        sessoes_base += sessoes_srv
                        cresc = prop.pct_crescimento_por_servico.get(servico, 0)
                        if cresc > 0:
                            pct_crescimento += cresc
                            qtd_com_crescimento += 1
            
            # FALLBACK: Se ainda não tem dados, usa do serviço
            if sessoes_base == 0 and servico in self.servicos:
                sessoes_base = self.servicos[servico].sessoes_mes_base
                pct_crescimento = self.servicos[servico].pct_crescimento
            elif qtd_com_crescimento > 0:
                pct_crescimento = pct_crescimento / qtd_com_crescimento
        
        # ========================================
        # APLICA CRESCIMENTO (fórmula igual calcular_sessoes_mes)
        # ========================================
        
        if sessoes_base == 0:
            return 0.0
        
        # Aplica crescimento linear igual à planilha
        if pct_crescimento > 0:
            crescimento_qtd = sessoes_base * pct_crescimento
            cresc_mensal = crescimento_qtd / 13.1
            sessoes = sessoes_base + cresc_mensal * (mes + 0.944)
        else:
            sessoes = sessoes_base
        
        # APLICA SAZONALIDADE
        fator_sazonalidade = self.sazonalidade.fatores[mes] if hasattr(self, 'sazonalidade') else 1.0
        return sessoes * fator_sazonalidade

    def validar_sessoes(self) -> dict:
        """
        Valida consistência das sessões entre serviços e profissionais.
        
        Retorna dict com:
        - alertas: lista de strings com avisos
        - erros: lista de strings com erros críticos
        - detalhes: dict com números comparativos
        - ok: bool se tudo está consistente
        """
        alertas = []
        erros = []
        detalhes = {
            "modo": getattr(self.operacional, 'modo_calculo_sessoes', 'servico'),
            "por_servico": {},
            "totais": {
                "servicos": 0,
                "fisioterapeutas": 0,
                "capacidade_salas": 0
            }
        }
        
        # ========================================
        # 1. CALCULAR SESSÕES POR SERVIÇO (do cadastro)
        # ========================================
        total_servicos = 0
        for srv_nome, srv in self.servicos.items():
            sessoes = srv.sessoes_mes_base
            total_servicos += sessoes
            detalhes["por_servico"][srv_nome] = {
                "servico": sessoes,
                "fisios": 0,
                "crescimento_servico": srv.pct_crescimento
            }
        detalhes["totais"]["servicos"] = total_servicos
        
        # ========================================
        # 2. CALCULAR SESSÕES POR FISIOTERAPEUTA
        # ========================================
        total_fisios = 0
        fisios_sem_sessoes = []
        servicos_fisios = set()
        
        for fisio in self.fisioterapeutas.values():
            if not fisio.ativo:
                continue
            
            fisio_tem_sessoes = False
            for srv_nome, qtd in fisio.sessoes_por_servico.items():
                if qtd > 0:
                    fisio_tem_sessoes = True
                    total_fisios += qtd
                    servicos_fisios.add(srv_nome)
                    if srv_nome in detalhes["por_servico"]:
                        detalhes["por_servico"][srv_nome]["fisios"] += qtd
                    else:
                        # Fisio tem serviço que não existe no cadastro
                        erros.append(f"Fisio '{fisio.nome}' tem sessões em '{srv_nome}' que não está cadastrado")
            
            if not fisio_tem_sessoes:
                fisios_sem_sessoes.append(fisio.nome)
        
        detalhes["totais"]["fisioterapeutas"] = total_fisios
        
        # ========================================
        # 3. CALCULAR CAPACIDADE DAS SALAS
        # ========================================
        if hasattr(self, 'cadastro_salas') and self.cadastro_salas:
            capacidade_horas = self.cadastro_salas.capacidade_total_horas
            # Estimar sessões (assumindo 50min = 0.83h por sessão)
            capacidade_sessoes = int(capacidade_horas / 0.83) if capacidade_horas > 0 else 0
        else:
            capacidade_horas = self.operacional.num_salas * self.operacional.horas_atendimento_dia * self.operacional.dias_uteis_mes
            capacidade_sessoes = int(capacidade_horas / 0.83) if capacidade_horas > 0 else 0
        
        detalhes["totais"]["capacidade_salas"] = capacidade_sessoes
        
        # ========================================
        # 4. VALIDAÇÃO: Num Fisios Configurado vs Cadastrados
        # ========================================
        fisios_cadastrados = len([f for f in self.fisioterapeutas.values() if f.ativo])
        fisios_configurados = self.operacional.num_fisioterapeutas
        
        if fisios_configurados > 0 and fisios_cadastrados != fisios_configurados:
            alertas.append(f"Fisioterapeutas configurados ({fisios_configurados}) ≠ cadastrados ({fisios_cadastrados})")
        
        # ========================================
        # 5. VALIDAÇÕES POR MODO
        # ========================================
        modo = detalhes["modo"]
        
        if modo == "servico":
            # Modo Serviço: verificar se serviços têm sessões
            servicos_sem_sessoes = [s for s, srv in self.servicos.items() if srv.sessoes_mes_base == 0]
            if servicos_sem_sessoes:
                alertas.append(f"Serviços sem sessões: {', '.join(servicos_sem_sessoes)}")
            
            # Se tem fisios cadastrados com sessões, avisar divergência
            if total_fisios > 0 and total_servicos > 0 and abs(total_fisios - total_servicos) > 5:
                alertas.append(f"Sessões serviços ({total_servicos}) ≠ soma fisios ({total_fisios}). Modo atual: SERVIÇO")
        
        else:  # modo == "profissional"
            # Modo Profissional: verificar se fisios têm sessões
            if fisios_sem_sessoes:
                alertas.append(f"Fisioterapeutas sem sessões: {', '.join(fisios_sem_sessoes[:3])}" + 
                              (f" (+{len(fisios_sem_sessoes)-3})" if len(fisios_sem_sessoes) > 3 else ""))
            
            if total_fisios == 0:
                erros.append("Modo PROFISSIONAL mas nenhum fisioterapeuta tem sessões cadastradas!")
            
            # Se tem serviços com sessões, avisar divergência
            if total_servicos > 0 and total_fisios > 0 and abs(total_fisios - total_servicos) > 5:
                alertas.append(f"Sessões serviços ({total_servicos}) ≠ soma fisios ({total_fisios}). Modo atual: PROFISSIONAL")
        
        # ========================================
        # 6. VALIDAÇÃO: Capacidade vs Sessões
        # ========================================
        sessoes_usadas = total_servicos if modo == "servico" else total_fisios
        
        if capacidade_sessoes > 0 and sessoes_usadas > capacidade_sessoes:
            alertas.append(f"Sessões ({sessoes_usadas}) > capacidade das salas ({capacidade_sessoes})")
        
        # ========================================
        # 7. VALIDAÇÃO: Crescimento Inconsistente
        # ========================================
        for srv_nome, info in detalhes["por_servico"].items():
            if info["servico"] > 0 and info["fisios"] > 0:
                # Ambos têm dados - verificar se crescimento é consistente
                cresc_srv = info["crescimento_servico"]
                # Calcular média de crescimento dos fisios para este serviço
                cresc_fisios = []
                for fisio in self.fisioterapeutas.values():
                    if fisio.ativo and srv_nome in fisio.pct_crescimento_por_servico:
                        cresc_fisios.append(fisio.pct_crescimento_por_servico[srv_nome])
                
                if cresc_fisios:
                    media_fisios = sum(cresc_fisios) / len(cresc_fisios)
                    if abs(cresc_srv - media_fisios) > 0.02:  # Diferença > 2%
                        alertas.append(f"Crescimento '{srv_nome}': serviço={cresc_srv*100:.0f}% vs fisios={media_fisios*100:.0f}%")
        
        # ========================================
        # RESULTADO FINAL
        # ========================================
        return {
            "ok": len(erros) == 0 and len(alertas) == 0,
            "erros": erros,
            "alertas": alertas,
            "detalhes": detalhes
        }
    
    def calcular_folha_fisioterapeutas_mes(self, mes: int) -> dict:
        """
        Calcula folha de fisioterapeutas para um mês específico.
        mes: 1-12 (Janeiro=1, Dezembro=12)
        """
        pf = self.premissas_fisio
        
        # Converte de 1-12 para 0-11 para funções internas
        mes_idx = mes - 1
        
        resultado = {
            "fisioterapeutas": [],
            "proprietarios": [],
            "total_fisioterapeutas": 0,
            "total_proprietarios": 0,
            "producao_bruta": 0,
            "margem_clinica": 0
        }
        
        # ===== VERIFICAÇÃO: Se não há fisioterapeutas cadastrados, retorna tudo zerado =====
        if not self.fisioterapeutas:
            return resultado
        
        # Verifica se há pelo menos um fisioterapeuta ativo
        tem_fisio_ativo = any(f.ativo for f in self.fisioterapeutas.values())
        if not tem_fisio_ativo:
            return resultado
        
        # Calcula faturamento total por serviço - USA SERVIÇOS CADASTRADOS
        servicos = list(self.servicos.keys())  # Dinâmico
        faturamento_por_servico = {}
        
        for srv in servicos:
            sessoes = self.get_sessoes_servico_mes(srv, mes_idx)
            # Determina tipo baseado no serviço (proprietário geralmente tem serviço específico)
            tipo = "profissional"
            for fisio in self.fisioterapeutas.values():
                if fisio.cargo == "Proprietário" and srv in fisio.sessoes_por_servico:
                    tipo = "proprietario"
                    break
            valor = self.get_valor_servico(srv, mes_idx, tipo)
            faturamento_por_servico[srv] = sessoes * valor
        
        # Produção total da clínica
        producao_total = sum(faturamento_por_servico.values())
        
        # Produção própria do proprietário - CALCULA DINAMICAMENTE
        # Soma faturamento dos serviços que proprietários atendem
        # BUG #7 CORRIGIDO: Primeiro coleta serviços, depois soma (evita contagem dupla)
        servicos_proprietario = set()
        for fisio in self.fisioterapeutas.values():
            if fisio.cargo == "Proprietário" and fisio.ativo:
                for srv in fisio.sessoes_por_servico.keys():
                    servicos_proprietario.add(srv)
        # Calcula producao_propria UMA vez só (após coletar todos os serviços)
        producao_propria = sum(faturamento_por_servico.get(srv, 0) for srv in servicos_proprietario)

        # Faturamento da equipe (sem serviços do proprietário)
        faturamento_equipe = producao_total - producao_propria
        
        # === PROPRIETÁRIO ===
        # Dois modelos:
        # 1. COM EQUIPE: Folha = faturamento equipe × 20% × 75% (como na planilha FVS)
        # 2. SOLO (PF/autônomo): Folha = produção própria × pct_producao_propria (retirada do profissional)
        
        # Fator de sazonalidade do mês
        fator_sazonalidade = self.sazonalidade.fatores[mes_idx] if hasattr(self, 'sazonalidade') else 1.0
        
        for nome, fisio in self.fisioterapeutas.items():
            if fisio.cargo != "Proprietário":
                continue
            if not fisio.ativo:
                continue
            
            # CORRIGIDO v1.87: Calcula sessões COM crescimento individual do proprietário
            sessoes_prop = 0
            faturamento_prop = 0
            
            for srv, qtd_base in fisio.sessoes_por_servico.items():
                if qtd_base > 0:
                    # APLICA CRESCIMENTO INDIVIDUAL do proprietário
                    pct_crescimento = fisio.pct_crescimento_por_servico.get(srv, 0.0)
                    
                    if pct_crescimento > 0:
                        crescimento_qtd = qtd_base * pct_crescimento
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes_com_crescimento = qtd_base + cresc_mensal * (mes_idx + 0.944)
                    else:
                        sessoes_com_crescimento = qtd_base
                    
                    # APLICA SAZONALIDADE
                    sessoes_srv = sessoes_com_crescimento * fator_sazonalidade
                    sessoes_prop += sessoes_srv
                    
                    # Calcula faturamento do proprietário
                    valor = self.get_valor_servico(srv, mes_idx, "proprietario")
                    faturamento_prop += sessoes_srv * valor
            
            # Recalcula produção própria com crescimento
            producao_propria = faturamento_prop
            
            rem_producao = producao_propria * pf.pct_producao_propria  # 60% da produção própria
            rem_faturamento = faturamento_equipe * pf.pct_faturamento_total * pf.pct_base_remuneracao_prop
            
            # Determina modelo de remuneração
            if faturamento_equipe > 0:
                # COM EQUIPE: usa participação no faturamento da equipe (modelo planilha)
                remuneracao = rem_faturamento
            else:
                # SOLO/AUTÔNOMO: usa produção própria (o profissional é a própria clínica)
                remuneracao = rem_producao
            
            resultado["proprietarios"].append({
                "nome": nome,
                "sessoes": sessoes_prop,
                "producao_propria": producao_propria,
                "rem_producao_propria": rem_producao,
                "rem_faturamento_total": rem_faturamento,
                "remuneracao": remuneracao
            })
        
        resultado["total_proprietarios"] = sum(p["remuneracao"] for p in resultado["proprietarios"])
        
        # === FISIOTERAPEUTAS ===
        # Fórmula: Remuneração = Faturamento × % Nível × 75%
        # CORRIGIDO v1.87: Calcula sessões COM crescimento individual de cada fisioterapeuta
        
        # Fator de sazonalidade do mês
        fator_sazonalidade = self.sazonalidade.fatores[mes_idx] if hasattr(self, 'sazonalidade') else 1.0
        
        faturamento_outros = 0  # Para cálculo de bônus de gerência
        
        for nome, fisio in self.fisioterapeutas.items():
            if not fisio.ativo or fisio.cargo == "Proprietário":
                continue
            
            # Calcula faturamento do profissional COM CRESCIMENTO INDIVIDUAL
            faturamento_prof = 0
            sessoes_prof = 0
            sessoes_por_servico_mes = {}  # Para cálculo de valor fixo
            
            for srv, qtd_base in fisio.sessoes_por_servico.items():
                if qtd_base > 0:
                    # APLICA CRESCIMENTO INDIVIDUAL do fisioterapeuta
                    pct_crescimento = fisio.pct_crescimento_por_servico.get(srv, 0.0)
                    
                    if pct_crescimento > 0:
                        # Fórmula: sessoes = base + (base × pct_cresc / 13.1) × (mes + 0.944)
                        crescimento_qtd = qtd_base * pct_crescimento
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes_com_crescimento = qtd_base + cresc_mensal * (mes_idx + 0.944)
                    else:
                        sessoes_com_crescimento = qtd_base
                    
                    # APLICA SAZONALIDADE
                    sessoes_srv = sessoes_com_crescimento * fator_sazonalidade
                    sessoes_por_servico_mes[srv] = sessoes_srv
                    
                    # Valor do serviço
                    valor = self.get_valor_servico(srv, mes_idx, "profissional")
                    
                    # Faturamento
                    faturamento_prof += sessoes_srv * valor
                    sessoes_prof += sessoes_srv
            
            # Remuneração baseada no tipo (PERCENTUAL, VALOR FIXO ou MISTO)
            if fisio.tipo_remuneracao == "valor_fixo":
                # VALOR FIXO: soma dos (sessões × valor fixo) por serviço
                # Se não tem valores configurados, resultado será R$ 0
                remuneracao = 0
                for srv, sessoes_srv in sessoes_por_servico_mes.items():
                    valor_fixo = fisio.valores_fixos_por_servico.get(srv, 0)
                    remuneracao += sessoes_srv * valor_fixo
                pct_nivel = 0  # Não usa nível
                tipo_calc = "valor_fixo"
            
            elif fisio.tipo_remuneracao == "misto":
                # MISTO: percentual sobre faturamento + valor fixo adicional por sessão
                # Parte percentual
                if fisio.pct_customizado > 0:
                    pct_nivel = fisio.pct_customizado
                else:
                    pct_nivel = pf.niveis_remuneracao.get(fisio.nivel, 0.25)
                remuneracao_pct = faturamento_prof * pct_nivel * 0.75
                
                # Parte valor fixo (adicional)
                remuneracao_fixo = 0
                for srv, sessoes_srv in sessoes_por_servico_mes.items():
                    valor_fixo = fisio.valores_fixos_por_servico.get(srv, 0)
                    remuneracao_fixo += sessoes_srv * valor_fixo
                
                remuneracao = remuneracao_pct + remuneracao_fixo
                tipo_calc = "misto"
            
            else:
                # PERCENTUAL: faturamento × % nível × 0.75
                pct_nivel = pf.niveis_remuneracao.get(fisio.nivel, 0.25)
                remuneracao = faturamento_prof * pct_nivel * 0.75
                tipo_calc = "percentual"
            
            # Acumula faturamento para gerência
            if fisio.cargo != "Gerente":
                faturamento_outros += faturamento_prof
            
            resultado["fisioterapeutas"].append({
                "nome": nome,
                "cargo": fisio.cargo,
                "nivel": fisio.nivel,
                "tipo_remuneracao": fisio.tipo_remuneracao,
                "sessoes": sessoes_prof,
                "faturamento": faturamento_prof,
                "pct_nivel": pct_nivel,
                "bonus_gerencia": 0,
                "remuneracao": remuneracao
            })
        
        # Adiciona bônus de gerência
        for item in resultado["fisioterapeutas"]:
            if item["cargo"] == "Gerente":
                # Bônus = 1% sobre faturamento de outros × 75%
                bonus = faturamento_outros * pf.pct_gerencia_equipe * 0.75
                item["bonus_gerencia"] = bonus
                item["remuneracao"] += bonus
        
        resultado["total_fisioterapeutas"] = sum(f["remuneracao"] for f in resultado["fisioterapeutas"])
        
        # Totais
        resultado["producao_bruta"] = producao_total
        resultado["margem_clinica"] = producao_total - resultado["total_fisioterapeutas"] - resultado["total_proprietarios"]
        
        # Detalhes por nome (para facilitar acesso na UI)
        resultado["detalhes_fisioterapeutas"] = {
            f["nome"]: {"total": f["remuneracao"], "sessoes": f["sessoes"], "faturamento": f["faturamento"]}
            for f in resultado["fisioterapeutas"]
        }
        resultado["detalhes_proprietarios"] = {
            p["nome"]: {"total": p["remuneracao"], "producao": p["producao_propria"]}
            for p in resultado["proprietarios"]
        }
        
        return resultado
    
    def projetar_folha_fisioterapeutas_anual(self) -> list:
        """Projeta folha de fisioterapeutas para todos os meses do ano"""
        return [self.calcular_folha_fisioterapeutas_mes(mes) for mes in range(1, 13)]
    
    # ============================================
    # SIMULADOR DE METAS (CÁLCULO REVERSO)
    # ============================================
    
    def simular_meta_faturamento(self, pct_crescimento_meta: float, mes_referencia: int = 1, 
                                  modo_distribuicao: str = "proporcional",
                                  usar_faturamento_anterior: bool = True) -> dict:
        """
        Simula quantas sessões adicionais cada fisioterapeuta precisa fazer
        para atingir uma meta de crescimento no faturamento.
        
        MODO SOMENTE LEITURA - não altera dados do motor.
        
        Args:
            pct_crescimento_meta: % de crescimento desejado (ex: 0.12 para 12%)
            mes_referencia: Mês base para cálculo (1-12), default=1 (Janeiro)
            modo_distribuicao: Como distribuir o gap entre fisios
                - "proporcional": Distribui proporcionalmente ao faturamento atual
                - "igual": Distribui igualmente entre todos
                - "capacidade": Distribui por capacidade disponível
            usar_faturamento_anterior: Se True, usa faturamento_anterior (2025) como base
                                       Se False, usa faturamento calculado atual
        
        Returns:
            dict com:
                - faturamento_base: Faturamento base (2025 ou calculado)
                - faturamento_meta: Faturamento alvo
                - gap_faturamento: Diferença a ser coberta
                - fisioterapeutas: Lista com detalhes de cada fisio
                - resumo: Resumo executivo
                - viavel: Se a meta é viável com a equipe atual
        """
        pf = self.premissas_fisio
        
        # 1. Calcula situação atual usando função existente
        folha_atual = self.calcular_folha_fisioterapeutas_mes(mes_referencia)
        
        # 2. Extrai dados atuais dos fisioterapeutas E proprietários (v1.99.56)
        faturamento_fisios_atual = sum(f["faturamento"] for f in folha_atual["fisioterapeutas"])
        faturamento_fisios_atual += sum(p.get("faturamento", 0) for p in folha_atual.get("proprietarios", []))
        sessoes_atual = sum(f["sessoes"] for f in folha_atual["fisioterapeutas"])
        sessoes_atual += sum(p.get("sessoes", 0) for p in folha_atual.get("proprietarios", []))
        remuneracao_atual = folha_atual["total_fisioterapeutas"]
        
        # 3. Define faturamento base para cálculo da meta
        if usar_faturamento_anterior and hasattr(self, 'faturamento_anterior'):
            # Usa faturamento total de 2025 (ano anterior)
            faturamento_base = sum(self.faturamento_anterior) / 12  # Média mensal
            faturamento_base_anual = sum(self.faturamento_anterior)
            fonte_base = "Faturamento 2025 (média mensal)"
        else:
            # Usa faturamento calculado atual
            faturamento_base = faturamento_fisios_atual
            faturamento_base_anual = faturamento_fisios_atual * 12
            fonte_base = "Faturamento calculado (fisioterapeutas)"
        
        # 4. Calcula metas
        faturamento_meta = faturamento_base * (1 + pct_crescimento_meta)
        gap_faturamento = faturamento_meta - faturamento_fisios_atual  # Gap real a cobrir
        
        # Se usando faturamento anterior, o gap é a diferença entre meta e atual dos fisios
        # Isso porque queremos que os fisios cubram a diferença
        
        # 5. Calcula valor médio por sessão (para estimar sessões necessárias)
        valor_medio_sessao = faturamento_fisios_atual / sessoes_atual if sessoes_atual > 0 else 0
        sessoes_adicionais_total = gap_faturamento / valor_medio_sessao if valor_medio_sessao > 0 else 0
        
        # 6. Distribui entre fisios
        resultado_fisios = []
        total_sessoes_novas = 0
        total_remuneracao_nova = 0
        
        for fisio_atual in folha_atual["fisioterapeutas"]:
            nome = fisio_atual["nome"]
            fisio_obj = self.fisioterapeutas.get(nome)
            
            if not fisio_obj or not fisio_obj.ativo:
                continue
            
            # Dados atuais do fisio
            sessoes_fisio = fisio_atual["sessoes"]
            faturamento_fisio = fisio_atual["faturamento"]
            remuneracao_fisio = fisio_atual["remuneracao"]
            nivel = fisio_atual["nivel"]
            pct_nivel = fisio_atual["pct_nivel"]
            
            # Calcula participação no faturamento total dos fisios
            participacao = faturamento_fisio / faturamento_fisios_atual if faturamento_fisios_atual > 0 else 0
            
            # Distribui gap conforme modo
            if modo_distribuicao == "proporcional":
                gap_fisio = gap_faturamento * participacao
            elif modo_distribuicao == "igual":
                qtd_fisios = len([f for f in folha_atual["fisioterapeutas"] if f["sessoes"] > 0])
                gap_fisio = gap_faturamento / qtd_fisios if qtd_fisios > 0 else 0
            else:  # capacidade
                gap_fisio = gap_faturamento * participacao  # Por enquanto igual a proporcional
            
            # Calcula sessões adicionais para este fisio
            valor_sessao_fisio = faturamento_fisio / sessoes_fisio if sessoes_fisio > 0 else valor_medio_sessao
            sessoes_adicionais = gap_fisio / valor_sessao_fisio if valor_sessao_fisio > 0 else 0
            
            # Novos valores
            sessoes_nova = sessoes_fisio + sessoes_adicionais
            faturamento_novo = faturamento_fisio + gap_fisio
            
            # Calcula nova remuneração usando mesma lógica do motor
            tipo_rem = fisio_obj.tipo_remuneracao if fisio_obj else "percentual"
            
            if tipo_rem == "valor_fixo":
                # Valor fixo por sessão
                valor_fixo_medio = remuneracao_fisio / sessoes_fisio if sessoes_fisio > 0 else 0
                remuneracao_nova = sessoes_nova * valor_fixo_medio
            elif tipo_rem == "misto":
                # Parte percentual + parte fixa
                remuneracao_nova = faturamento_novo * pct_nivel * 0.75
                # Adiciona parte fixa proporcional
                parte_fixa = remuneracao_fisio - (faturamento_fisio * pct_nivel * 0.75)
                if parte_fixa > 0 and sessoes_fisio > 0:
                    remuneracao_nova += (sessoes_nova / sessoes_fisio) * parte_fixa
            else:
                # Percentual padrão
                remuneracao_nova = faturamento_novo * pct_nivel * 0.75
            
            # Delta
            delta_sessoes = sessoes_nova - sessoes_fisio
            delta_faturamento = faturamento_novo - faturamento_fisio
            delta_remuneracao = remuneracao_nova - remuneracao_fisio
            
            resultado_fisios.append({
                "nome": nome,
                "cargo": fisio_atual["cargo"],
                "nivel": nivel,
                "tipo_remuneracao": tipo_rem,
                # Atual
                "sessoes_atual": sessoes_fisio,
                "faturamento_atual": faturamento_fisio,
                "remuneracao_atual": remuneracao_fisio,
                # Meta
                "sessoes_meta": sessoes_nova,
                "faturamento_meta": faturamento_novo,
                "remuneracao_meta": remuneracao_nova,
                # Deltas
                "delta_sessoes": delta_sessoes,
                "delta_faturamento": delta_faturamento,
                "delta_remuneracao": delta_remuneracao,
                # Percentuais
                "pct_crescimento_sessoes": (delta_sessoes / sessoes_fisio * 100) if sessoes_fisio > 0 else 0,
                "pct_crescimento_faturamento": (delta_faturamento / faturamento_fisio * 100) if faturamento_fisio > 0 else 0,
                "pct_crescimento_remuneracao": (delta_remuneracao / remuneracao_fisio * 100) if remuneracao_fisio > 0 else 0,
            })
            
            total_sessoes_novas += sessoes_nova
            total_remuneracao_nova += remuneracao_nova
        
        # 7. Análise de viabilidade
        # Verifica se sessões adicionais são razoáveis (< 50% de aumento por fisio)
        viavel = True
        alertas = []
        
        for f in resultado_fisios:
            if f["pct_crescimento_sessoes"] > 50:
                viavel = False
                alertas.append(f"{f['nome']}: +{f['pct_crescimento_sessoes']:.0f}% sessões é muito alto")
            elif f["pct_crescimento_sessoes"] > 30:
                alertas.append(f"{f['nome']}: +{f['pct_crescimento_sessoes']:.0f}% sessões pode ser desafiador")
        
        # Alerta se faturamento anterior não está preenchido
        if usar_faturamento_anterior:
            if not hasattr(self, 'faturamento_anterior') or sum(self.faturamento_anterior) == 0:
                alertas.insert(0, "⚠️ Faturamento 2025 não preenchido! Vá em Premissas → Cenários para preencher.")
        
        # 8. Resumo
        faturamento_meta_total = sum(f["faturamento_meta"] for f in resultado_fisios)
        
        resumo = {
            "fonte_base": fonte_base,
            "faturamento_base": faturamento_base,
            "faturamento_base_anual": faturamento_base_anual,
            "faturamento_atual_fisios": faturamento_fisios_atual,
            "faturamento_meta": faturamento_meta,
            "faturamento_meta_total": faturamento_meta_total,
            "gap_faturamento": gap_faturamento,
            "sessoes_atual": sessoes_atual,
            "sessoes_meta": total_sessoes_novas,
            "sessoes_adicionais": total_sessoes_novas - sessoes_atual,
            "remuneracao_atual": remuneracao_atual,
            "remuneracao_meta": total_remuneracao_nova,
            "delta_remuneracao": total_remuneracao_nova - remuneracao_atual,
            "margem_atual": faturamento_fisios_atual - remuneracao_atual,
            "margem_meta": faturamento_meta_total - total_remuneracao_nova,
            "qtd_fisios": len(resultado_fisios),
            "viavel": viavel,
            "alertas": alertas,
        }
        
        return {
            "meta_input": {
                "pct_crescimento": pct_crescimento_meta,
                "mes_referencia": mes_referencia,
                "modo_distribuicao": modo_distribuicao,
                "usar_faturamento_anterior": usar_faturamento_anterior,
            },
            "fisioterapeutas": resultado_fisios,
            "resumo": resumo,
            "viavel": viavel,
            "alertas": alertas,
        }
    
    def simular_meta_faturamento_anual(self, pct_crescimento_meta: float,
                                        modo_distribuicao: str = "proporcional",
                                        usar_faturamento_anterior: bool = True) -> dict:
        """
        Simula metas de crescimento considerando o ANO INTEIRO.
        USA A SAZONALIDADE DO FATURAMENTO 2025 para distribuir metas mensais.
        
        MODO SOMENTE LEITURA - não altera dados do motor.
        
        Args:
            pct_crescimento_meta: % de crescimento desejado (ex: 0.12 para 12%)
            modo_distribuicao: Como distribuir o gap entre fisios
            usar_faturamento_anterior: Se True, usa faturamento 2025 como base
        
        Returns:
            dict com dados anuais e mensais detalhados
        """
        pf = self.premissas_fisio
        
        # 1. Pega faturamento 2025 e calcula proporção de cada mês
        fat_2025 = getattr(self, 'faturamento_anterior', [0.0] * 12)
        fat_2025_total = sum(fat_2025)
        
        # Proporção de cada mês no faturamento 2025 (sazonalidade real)
        prop_mes_2025 = []
        for i in range(12):
            if fat_2025_total > 0:
                prop_mes_2025.append(fat_2025[i] / fat_2025_total)
            else:
                prop_mes_2025.append(1/12)  # Distribuição uniforme se não tem dados
        
        # 2. Calcula totais anuais ATUAIS dos fisioterapeutas
        totais_anuais = {
            "faturamento_fisios": 0,
            "sessoes": 0,
            "remuneracao": 0,
        }
        
        # Dados mensais para cada fisio
        dados_mensais_fisios = {}  # {nome: {mes: dados}}
        
        for mes in range(1, 13):
            folha_mes = self.calcular_folha_fisioterapeutas_mes(mes)
            
            for fisio in folha_mes["fisioterapeutas"]:
                nome = fisio["nome"]
                if nome not in dados_mensais_fisios:
                    dados_mensais_fisios[nome] = {
                        "meses": {},
                        "total_sessoes": 0,
                        "total_faturamento": 0,
                        "total_remuneracao": 0,
                        "cargo": fisio["cargo"],
                        "nivel": fisio["nivel"],
                        "tipo_remuneracao": fisio.get("tipo_remuneracao", "percentual"),
                        "pct_nivel": fisio.get("pct_nivel", 0.25),
                    }
                
                dados_mensais_fisios[nome]["meses"][mes] = {
                    "sessoes": fisio["sessoes"],
                    "faturamento": fisio["faturamento"],
                    "remuneracao": fisio["remuneracao"],
                }
                dados_mensais_fisios[nome]["total_sessoes"] += fisio["sessoes"]
                dados_mensais_fisios[nome]["total_faturamento"] += fisio["faturamento"]
                dados_mensais_fisios[nome]["total_remuneracao"] += fisio["remuneracao"]
            
            totais_anuais["faturamento_fisios"] += sum(f["faturamento"] for f in folha_mes["fisioterapeutas"])
            totais_anuais["faturamento_fisios"] += sum(p.get("faturamento", 0) for p in folha_mes.get("proprietarios", []))
            totais_anuais["sessoes"] += sum(f["sessoes"] for f in folha_mes["fisioterapeutas"])
            totais_anuais["sessoes"] += sum(p.get("sessoes", 0) for p in folha_mes.get("proprietarios", []))
            totais_anuais["remuneracao"] += folha_mes["total_fisioterapeutas"]
        
        # 3. Define base para cálculo da meta
        if usar_faturamento_anterior and fat_2025_total > 0:
            faturamento_base_anual = fat_2025_total
            fonte_base = "Faturamento 2025 (anual)"
        else:
            faturamento_base_anual = totais_anuais["faturamento_fisios"]
            fonte_base = "Faturamento calculado (anual)"
        
        # 4. Calcula metas anuais
        faturamento_meta_anual = faturamento_base_anual * (1 + pct_crescimento_meta)
        gap_anual = faturamento_meta_anual - totais_anuais["faturamento_fisios"]
        
        # 5. Calcula META MENSAL usando proporção do faturamento 2025
        # Cada mês terá exatamente +X% sobre o faturamento de 2025 daquele mês
        metas_mensais_2026 = []
        for i in range(12):
            meta_mes = fat_2025[i] * (1 + pct_crescimento_meta)
            metas_mensais_2026.append(meta_mes)
        
        # 6. Valor médio por sessão (anual)
        valor_medio_sessao = totais_anuais["faturamento_fisios"] / totais_anuais["sessoes"] if totais_anuais["sessoes"] > 0 else 0
        sessoes_adicionais_total = gap_anual / valor_medio_sessao if valor_medio_sessao > 0 else 0
        
        # 7. Distribui gap entre fisios (anual)
        resultado_fisios = []
        total_sessoes_meta = 0
        total_remuneracao_meta = 0
        
        for nome, dados in dados_mensais_fisios.items():
            fisio_obj = self.fisioterapeutas.get(nome)
            if not fisio_obj or not fisio_obj.ativo:
                continue
            
            # Participação proporcional no faturamento total dos fisios
            participacao = dados["total_faturamento"] / totais_anuais["faturamento_fisios"] if totais_anuais["faturamento_fisios"] > 0 else 0
            
            # Distribui gap anual
            if modo_distribuicao == "proporcional":
                gap_fisio = gap_anual * participacao
            else:  # igual
                qtd_fisios = len(dados_mensais_fisios)
                gap_fisio = gap_anual / qtd_fisios if qtd_fisios > 0 else 0
            
            # Sessões adicionais anuais
            valor_sessao_fisio = dados["total_faturamento"] / dados["total_sessoes"] if dados["total_sessoes"] > 0 else valor_medio_sessao
            sessoes_adicionais = gap_fisio / valor_sessao_fisio if valor_sessao_fisio > 0 else 0
            
            # Novos totais anuais
            sessoes_meta = dados["total_sessoes"] + sessoes_adicionais
            faturamento_meta = dados["total_faturamento"] + gap_fisio
            
            # Calcula nova remuneração
            tipo_rem = dados["tipo_remuneracao"]
            pct_nivel = dados["pct_nivel"]
            
            if tipo_rem == "valor_fixo":
                valor_fixo_medio = dados["total_remuneracao"] / dados["total_sessoes"] if dados["total_sessoes"] > 0 else 0
                remuneracao_meta = sessoes_meta * valor_fixo_medio
            elif tipo_rem == "misto":
                remuneracao_meta = faturamento_meta * pct_nivel * 0.75
                parte_fixa = dados["total_remuneracao"] - (dados["total_faturamento"] * pct_nivel * 0.75)
                if parte_fixa > 0 and dados["total_sessoes"] > 0:
                    remuneracao_meta += (sessoes_meta / dados["total_sessoes"]) * parte_fixa
            else:
                remuneracao_meta = faturamento_meta * pct_nivel * 0.75
            
            # Deltas anuais
            delta_sessoes = sessoes_adicionais
            delta_faturamento = gap_fisio
            delta_remuneracao = remuneracao_meta - dados["total_remuneracao"]
            
            # 8. Calcula dados mensais META - CRESCIMENTO UNIFORME sobre 2025
            # Para cada mês: meta = fat_2025_mes * (1 + pct_meta)
            # E depois distribui o gap daquele mês específico entre os fisios
            meses_meta = {}
            for mes in range(1, 13):
                dados_mes = dados["meses"].get(mes, {"sessoes": 0, "faturamento": 0, "remuneracao": 0})
                
                # Meta deste mês específico: 2025_mes * (1 + pct_meta)
                fat_2025_mes = fat_2025[mes - 1]
                meta_fat_mes = fat_2025_mes * (1 + pct_crescimento_meta)
                
                # Quanto o fisio produz atualmente neste mês
                fat_atual_mes = dados_mes["faturamento"]
                
                # Participação do fisio no total dos fisios neste mês
                folha_mes = self.calcular_folha_fisioterapeutas_mes(mes)
                fat_total_fisios_mes = sum(f["faturamento"] for f in folha_mes["fisioterapeutas"])
                fat_total_fisios_mes += sum(p.get("faturamento", 0) for p in folha_mes.get("proprietarios", []))
                participacao_mes = fat_atual_mes / fat_total_fisios_mes if fat_total_fisios_mes > 0 else 0
                
                # Gap deste mês que todos os fisios precisam cobrir
                gap_mes_total = meta_fat_mes - fat_total_fisios_mes
                
                # Gap deste fisio neste mês (proporcional à sua participação)
                if modo_distribuicao == "proporcional":
                    gap_fisio_mes = gap_mes_total * participacao_mes
                else:
                    qtd_fisios = len(dados_mensais_fisios)
                    gap_fisio_mes = gap_mes_total / qtd_fisios if qtd_fisios > 0 else 0
                
                # Meta de faturamento do fisio neste mês
                fat_meta_fisio_mes = fat_atual_mes + gap_fisio_mes
                
                # Sessões adicionais para este mês (calculadas após verificar faturamento)
                valor_sessao_fisio = fat_atual_mes / dados_mes["sessoes"] if dados_mes["sessoes"] > 0 else valor_medio_sessao
                
                # Faturamento meta nunca pode ser menor que atual
                if fat_meta_fisio_mes < fat_atual_mes:
                    fat_meta_fisio_mes = fat_atual_mes
                
                # Agora calcula gap REAL de faturamento (após proteção)
                gap_fisio_mes_real = fat_meta_fisio_mes - fat_atual_mes
                
                # Sessões adicionais baseadas no gap REAL
                sessoes_add_mes = gap_fisio_mes_real / valor_sessao_fisio if valor_sessao_fisio > 0 else 0
                
                # Sessões meta
                sessoes_meta_mes = dados_mes["sessoes"] + sessoes_add_mes
                
                # IMPORTANTE: Sessões meta nunca pode ser menor que atual
                if sessoes_meta_mes < dados_mes["sessoes"]:
                    sessoes_meta_mes = dados_mes["sessoes"]
                
                # Remuneração proporcional às NOVAS sessões
                if tipo_rem == "valor_fixo":
                    rem_meta_mes = sessoes_meta_mes * (dados_mes["remuneracao"] / dados_mes["sessoes"]) if dados_mes["sessoes"] > 0 else 0
                else:
                    rem_meta_mes = fat_meta_fisio_mes * pct_nivel * 0.75
                
                # IMPORTANTE: Remuneração nunca pode cair
                if rem_meta_mes < dados_mes["remuneracao"]:
                    rem_meta_mes = dados_mes["remuneracao"]
                
                meses_meta[mes] = {
                    "sessoes_atual": dados_mes["sessoes"],
                    "sessoes_meta": sessoes_meta_mes,
                    "faturamento_atual": dados_mes["faturamento"],
                    "faturamento_meta": fat_meta_fisio_mes,
                    "remuneracao_atual": dados_mes["remuneracao"],
                    "remuneracao_meta": rem_meta_mes,
                }
            
            # Recalcula totais anuais baseado nos dados mensais
            sessoes_meta = sum(m["sessoes_meta"] for m in meses_meta.values())
            faturamento_meta = sum(m["faturamento_meta"] for m in meses_meta.values())
            remuneracao_meta = sum(m["remuneracao_meta"] for m in meses_meta.values())
            
            delta_sessoes = sessoes_meta - dados["total_sessoes"]
            delta_faturamento = faturamento_meta - dados["total_faturamento"]
            delta_remuneracao = remuneracao_meta - dados["total_remuneracao"]
            
            resultado_fisios.append({
                "nome": nome,
                "cargo": dados["cargo"],
                "nivel": dados["nivel"],
                "tipo_remuneracao": tipo_rem,
                # Totais anuais - Atual
                "sessoes_atual": dados["total_sessoes"],
                "faturamento_atual": dados["total_faturamento"],
                "remuneracao_atual": dados["total_remuneracao"],
                # Totais anuais - Meta (recalculados dos mensais)
                "sessoes_meta": sessoes_meta,
                "faturamento_meta": faturamento_meta,
                "remuneracao_meta": remuneracao_meta,
                # Deltas anuais
                "delta_sessoes": delta_sessoes,
                "delta_faturamento": delta_faturamento,
                "delta_remuneracao": delta_remuneracao,
                # Percentuais
                "pct_crescimento_sessoes": (delta_sessoes / dados["total_sessoes"] * 100) if dados["total_sessoes"] > 0 else 0,
                "pct_crescimento_faturamento": (delta_faturamento / dados["total_faturamento"] * 100) if dados["total_faturamento"] > 0 else 0,
                "pct_crescimento_remuneracao": (delta_remuneracao / dados["total_remuneracao"] * 100) if dados["total_remuneracao"] > 0 else 0,
                # Dados mensais
                "meses": meses_meta,
            })
            
            total_sessoes_meta += sessoes_meta
            total_remuneracao_meta += remuneracao_meta
        
        # 8.5. Adiciona bônus de gerência à remuneração meta dos gerentes
        # O bônus = 1% × faturamento_outros_meta × 0.75
        # pf já foi definido no início como self.premissas_fisio
        
        for f in resultado_fisios:
            if f["cargo"] == "Gerente":
                # Calcula faturamento meta de outros (não-gerentes) para cada mês
                for mes in range(1, 13):
                    fat_outros_meta_mes = sum(
                        fisio["meses"][mes]["faturamento_meta"] 
                        for fisio in resultado_fisios 
                        if fisio["cargo"] != "Gerente"
                    )
                    
                    # Bônus de gerência meta
                    bonus_gerencia_meta = fat_outros_meta_mes * pf.pct_gerencia_equipe * 0.75
                    
                    # Adiciona ao remuneração meta do mês
                    f["meses"][mes]["remuneracao_meta"] += bonus_gerencia_meta
                
                # Recalcula totais anuais do gerente
                f["remuneracao_meta"] = sum(m["remuneracao_meta"] for m in f["meses"].values())
                f["delta_remuneracao"] = f["remuneracao_meta"] - f["remuneracao_atual"]
                f["pct_crescimento_remuneracao"] = (f["delta_remuneracao"] / f["remuneracao_atual"] * 100) if f["remuneracao_atual"] > 0 else 0
        
        # 9. Análise de viabilidade
        viavel = True
        alertas = []
        
        for f in resultado_fisios:
            if f["pct_crescimento_sessoes"] > 50:
                viavel = False
                alertas.append(f"{f['nome']}: +{f['pct_crescimento_sessoes']:.0f}% sessões/ano é muito alto")
            elif f["pct_crescimento_sessoes"] > 30:
                alertas.append(f"{f['nome']}: +{f['pct_crescimento_sessoes']:.0f}% sessões/ano pode ser desafiador")
        
        if usar_faturamento_anterior:
            if not hasattr(self, 'faturamento_anterior') or sum(self.faturamento_anterior) == 0:
                alertas.insert(0, "⚠️ Faturamento 2025 não preenchido! Vá em Premissas → Cenários para preencher.")
        
        # 10. Dados mensais consolidados (com meta baseada em 2025)
        dados_mensais = []
        for mes in range(1, 13):
            fat_2025_mes = fat_2025[mes-1]
            fat_meta_2025 = fat_2025_mes * (1 + pct_crescimento_meta)  # Meta direta sobre 2025
            
            sessoes_atual_mes = sum(f["meses"][mes]["sessoes_atual"] for f in resultado_fisios)
            sessoes_meta_mes = sum(f["meses"][mes]["sessoes_meta"] for f in resultado_fisios)
            fat_atual_mes = sum(f["meses"][mes]["faturamento_atual"] for f in resultado_fisios)
            fat_meta_mes = sum(f["meses"][mes]["faturamento_meta"] for f in resultado_fisios)
            rem_atual_mes = sum(f["meses"][mes]["remuneracao_atual"] for f in resultado_fisios)
            rem_meta_mes = sum(f["meses"][mes]["remuneracao_meta"] for f in resultado_fisios)
            
            # Crescimento % real vs 2025
            crescimento_vs_2025 = ((fat_meta_mes - fat_2025_mes) / fat_2025_mes * 100) if fat_2025_mes > 0 else 0
            
            dados_mensais.append({
                "mes": mes,
                "faturamento_2025": fat_2025_mes,
                "faturamento_meta_2025": fat_meta_2025,  # Meta ideal (+X% exato sobre 2025)
                "faturamento_2026_atual": fat_atual_mes,
                "faturamento_2026_meta": fat_meta_mes,
                "crescimento_vs_2025": crescimento_vs_2025,
                "sessoes_atual": sessoes_atual_mes,
                "sessoes_meta": sessoes_meta_mes,
                "remuneracao_atual": rem_atual_mes,
                "remuneracao_meta": rem_meta_mes,
            })
        
        # 11. Resumo
        resumo = {
            "fonte_base": fonte_base,
            "modo_calculo": "anual",
            "faturamento_base_anual": faturamento_base_anual,
            "faturamento_base": faturamento_base_anual / 12,  # média mensal para compatibilidade
            "faturamento_atual_fisios": totais_anuais["faturamento_fisios"],
            "faturamento_meta_anual": faturamento_meta_anual,
            "faturamento_meta": faturamento_meta_anual / 12,  # média mensal
            "faturamento_meta_total": sum(f["faturamento_meta"] for f in resultado_fisios),
            "gap_faturamento_anual": gap_anual,
            "gap_faturamento": gap_anual / 12,  # média mensal
            "sessoes_atual": totais_anuais["sessoes"],
            "sessoes_meta": total_sessoes_meta,
            "sessoes_adicionais": total_sessoes_meta - totais_anuais["sessoes"],
            "remuneracao_atual": totais_anuais["remuneracao"],
            "remuneracao_meta": total_remuneracao_meta,
            "delta_remuneracao": total_remuneracao_meta - totais_anuais["remuneracao"],
            "margem_atual": totais_anuais["faturamento_fisios"] - totais_anuais["remuneracao"],
            "margem_meta": sum(f["faturamento_meta"] for f in resultado_fisios) - total_remuneracao_meta,
            "qtd_fisios": len(resultado_fisios),
            "viavel": viavel,
            "alertas": alertas,
        }
        
        return {
            "meta_input": {
                "pct_crescimento": pct_crescimento_meta,
                "mes_referencia": None,  # Indica cálculo anual
                "modo_distribuicao": modo_distribuicao,
                "usar_faturamento_anterior": usar_faturamento_anterior,
                "modo_calculo": "anual",
            },
            "fisioterapeutas": resultado_fisios,
            "dados_mensais": dados_mensais,
            "resumo": resumo,
            "viavel": viavel,
            "alertas": alertas,
        }
    
    def aplicar_simulacao_metas(self, resultado_simulacao: dict) -> dict:
        """
        Aplica os resultados de uma simulação de metas ao motor.
        
        LÓGICA:
        1. Calcula faturamento meta: Fat_2025 × (1 + pct_meta)
        2. Calcula faturamento atual do motor
        3. Calcula fator de ajuste
        4. Ajusta sessoes_mes_base de cada serviço proporcionalmente
        5. Resultado: Motor produz EXATAMENTE o valor da meta
        
        Args:
            resultado_simulacao: Dict retornado por simular_meta_faturamento()
        
        Returns:
            dict com:
                - sucesso: bool
                - alteracoes: Lista de alterações feitas
                - snapshot_anterior: Dados antes da alteração (para desfazer)
        """
        if not resultado_simulacao:
            return {"sucesso": False, "erro": "Simulação inválida"}

        # v1.99.93: Proteção completa contra valores None
        pct_meta = resultado_simulacao.get("meta_input", {}).get("pct_crescimento", 0) or 0

        # 1. Calcula faturamento 2025 e meta
        fat_anterior = getattr(self, 'faturamento_anterior', None) or [0.0] * 12
        fat_2025 = sum((v or 0) for v in fat_anterior)
        if fat_2025 == 0:
            return {"sucesso": False, "erro": "Faturamento 2025 não preenchido"}

        fat_meta = fat_2025 * (1 + pct_meta)

        # 2. Calcula faturamento BASE (sem crescimento) para determinar o fator
        # CORREÇÃO v1.99.7: A meta é relativa a Fat_2025, então:
        #   Fat_meta = Fat_2025 × (1 + pct_meta)
        #   Como zeramos crescimento, sessões_novas × valor × 12 = Fat_meta
        #   Então fator = Fat_meta / Fat_base = (1 + pct_meta) se Fat_base ≈ Fat_2025

        # Primeiro, tenta calcular Fat_base (sessões atuais × valor × 12, sem crescimento)
        fat_base = 0

        for srv_nome, srv in self.servicos.items():
            sessoes_base_total = 0
            valor = 0

            # ===== CALCULA SESSÕES BASE =====
            modo = getattr(self.operacional, 'modo_calculo_sessoes', 'servico')

            if modo == "servico":
                sessoes_base_total = srv.sessoes_mes_base or 0
            else:
                # Modo profissional - soma sessões de fisioterapeutas
                for fisio in self.fisioterapeutas.values():
                    if fisio.ativo:
                        sessoes_base_total += (fisio.sessoes_por_servico.get(srv_nome, 0) or 0)

                # Fallback: proprietarios + profissionais
                if sessoes_base_total == 0:
                    for prop in self.proprietarios.values():
                        if getattr(prop, 'ativo', True):
                            sessoes_base_total += (prop.sessoes_por_servico.get(srv_nome, 0) or 0)
                    for prof in self.profissionais.values():
                        if getattr(prof, 'ativo', True):
                            sessoes_base_total += (prof.sessoes_por_servico.get(srv_nome, 0) or 0)

            # ===== CALCULA VALOR DO SERVIÇO =====
            # v1.99.93: valores_proprietario/profissional têm estrutura {'antes': X, 'depois': Y}
            def _extrair_valor(v):
                if v is None:
                    return 0
                if isinstance(v, dict):
                    return float(v.get('depois', v.get('antes', 0)) or 0)
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return 0

            valor = getattr(srv, 'valor_2025', 0) or 0
            if valor == 0:
                valor = _extrair_valor(self.valores_proprietario.get(srv_nome, 0))
            if valor == 0:
                valor = _extrair_valor(self.valores_profissional.get(srv_nome, 0))
            if valor == 0:
                valor = getattr(srv, 'valor_2026', 0) or 0

            try:
                sessoes_num = float(sessoes_base_total) if sessoes_base_total else 0
                valor_num = float(valor) if valor else 0
                fat_base += sessoes_num * valor_num * 12
            except (TypeError, ValueError):
                pass

        # v1.99.99: CORREÇÃO DEFINITIVA - Crescimento de SESSÕES baseado em 2025
        #
        # LÓGICA DO USUÁRIO:
        # "Quero crescer 20% em relação a 2025" significa:
        # - SESSÕES devem ser 20% maiores que as sessões de 2025
        # - Preço de 2026 é SEPARADO - reajuste não conta como crescimento
        # - Crescimento = MAIS ATIVIDADE (sessões), não valor monetário
        #
        # CÁLCULO:
        # 1. sessoes_2025 = fat_2025 / valor_medio_2025
        # 2. sessoes_meta = sessoes_2025 × (1 + pct_meta)
        # 3. fator = sessoes_meta / sessoes_atuais
        #
        # Como não temos valor_2025 diretamente, usamos:
        # - Se sessões atuais ≈ sessões de 2025 (não mudaram), fator = 1 + pct_meta
        # - Esta é a interpretação correta: sessões crescem pelo % especificado

        if fat_2025 == 0:
            fator_ajuste = 1.0
            print(f"[METAS-CALC] ⚠️ fat_2025=0, usando fator=1.0")
        else:
            # CORREÇÃO SIMPLES E DIRETA:
            # Se usuário quer +20% de crescimento, sessões aumentam 20%
            # Independente de preços, inflação, ou estado atual
            fator_ajuste = 1 + pct_meta

            print(f"[METAS-CALC] fat_2025={fat_2025:,.0f} (base do exercício anterior)")
            print(f"[METAS-CALC] fat_base={fat_base:,.0f} (projeção atual - apenas referência)")
            print(f"[METAS-CALC] pct_meta={pct_meta*100:+.1f}%")
            print(f"[METAS-CALC] fator_ajuste={fator_ajuste:.4f} ({(fator_ajuste-1)*100:+.1f}%)")
            print(f"[METAS-CALC] Sessões aumentam {pct_meta*100:+.1f}% → crescimento REAL de atividade")
        
        # 3. Guarda snapshot para possível rollback
        snapshot = {
            "fisioterapeutas": {},
            "servicos": {},
            "proprietarios": {},
            "profissionais": {}
        }
        
        for nome, fisio in self.fisioterapeutas.items():
            snapshot["fisioterapeutas"][nome] = {
                "sessoes_por_servico": dict(fisio.sessoes_por_servico),
                "pct_crescimento_por_servico": dict(fisio.pct_crescimento_por_servico),
            }
        
        for nome, srv in self.servicos.items():
            snapshot["servicos"][nome] = {
                "sessoes_mes_base": srv.sessoes_mes_base,
                "pct_crescimento": srv.pct_crescimento,
            }
        
        for nome, prop in self.proprietarios.items():
            snapshot["proprietarios"][nome] = {
                "sessoes_por_servico": dict(prop.sessoes_por_servico),
                "pct_crescimento_por_servico": dict(prop.pct_crescimento_por_servico),
            }
        
        for nome, prof in self.profissionais.items():
            snapshot["profissionais"][nome] = {
                "sessoes_por_servico": dict(prof.sessoes_por_servico),
                "pct_crescimento_por_servico": dict(prof.pct_crescimento_por_servico),
            }
        
        # 5. Aplica ajustes
        alteracoes = []
        
        # 5a. Ajusta SERVIÇOS - sessoes_mes_base
        for nome_srv, srv in self.servicos.items():
            sessoes_anterior = srv.sessoes_mes_base or 0
            srv.sessoes_mes_base = round((srv.sessoes_mes_base or 0) * fator_ajuste, 1)

            # Zera crescimento (já está embutido nas sessões)
            cresc_anterior = srv.pct_crescimento or 0
            srv.pct_crescimento = 0.0
            
            alteracoes.append({
                "tipo": "SERVIÇO",
                "nome": nome_srv,
                "campo": "sessoes_mes_base",
                "anterior": sessoes_anterior,
                "novo": srv.sessoes_mes_base,
            })
            alteracoes.append({
                "tipo": "SERVIÇO",
                "nome": nome_srv,
                "campo": "pct_crescimento",
                "anterior": cresc_anterior,
                "novo": 0.0,
            })
        
        # 5b. Ajusta FISIOTERAPEUTAS - sessoes_por_servico
        for nome, fisio in self.fisioterapeutas.items():
            for servico in list(fisio.sessoes_por_servico.keys()):
                sessoes_anterior = fisio.sessoes_por_servico.get(servico, 0) or 0
                fisio.sessoes_por_servico[servico] = round(sessoes_anterior * fator_ajuste, 1)

                # Zera crescimento
                fisio.pct_crescimento_por_servico[servico] = 0.0
                
                alteracoes.append({
                    "tipo": "FISIO",
                    "nome": nome,
                    "servico": servico,
                    "campo": "sessoes",
                    "anterior": sessoes_anterior,
                    "novo": fisio.sessoes_por_servico[servico],
                })
        
        # 5c. Ajusta PROPRIETÁRIOS - sessoes_por_servico
        for nome, prop in self.proprietarios.items():
            for servico in list(prop.sessoes_por_servico.keys()):
                sessoes_anterior = prop.sessoes_por_servico.get(servico, 0) or 0
                prop.sessoes_por_servico[servico] = round(sessoes_anterior * fator_ajuste, 1)
                prop.pct_crescimento_por_servico[servico] = 0.0
                
                alteracoes.append({
                    "tipo": "PROPRIETÁRIO",
                    "nome": nome,
                    "servico": servico,
                    "campo": "sessoes",
                    "anterior": sessoes_anterior,
                    "novo": prop.sessoes_por_servico[servico],
                })
        
        # 5d. Ajusta PROFISSIONAIS - sessoes_por_servico
        for nome, prof in self.profissionais.items():
            for servico in list(prof.sessoes_por_servico.keys()):
                sessoes_anterior = prof.sessoes_por_servico.get(servico, 0) or 0
                prof.sessoes_por_servico[servico] = round(sessoes_anterior * fator_ajuste, 1)
                prof.pct_crescimento_por_servico[servico] = 0.0
                
                alteracoes.append({
                    "tipo": "PROFISSIONAL",
                    "nome": nome,
                    "servico": servico,
                    "campo": "sessoes",
                    "anterior": sessoes_anterior,
                    "novo": prof.sessoes_por_servico[servico],
                })
        
        # 6. Sincroniza estruturas
        self.sincronizar_proprietarios()
        
        # 7. Verifica resultado
        fat_novo = 0
        for srv in self.servicos:
            for mes in range(12):
                fat_novo += self.calcular_receita_servico_mes(srv, mes)
        
        return {
            "sucesso": True,
            "alteracoes": alteracoes,
            "snapshot_anterior": snapshot,
            "qtd_alteracoes": len(alteracoes),
            "fat_2025": fat_2025,
            "fat_meta": fat_meta,
            "fat_anterior": fat_atual,
            "fat_novo": fat_novo,
            "fator_ajuste": fator_ajuste,
        }
    
    def desfazer_simulacao_metas(self, snapshot: dict) -> bool:
        """
        Desfaz uma simulação de metas aplicada, restaurando estado anterior.
        
        Args:
            snapshot: Dict de snapshot retornado por aplicar_simulacao_metas()
        
        Returns:
            bool: True se desfez com sucesso
        """
        if not snapshot:
            return False
        
        try:
            # Restaura fisioterapeutas
            fisios_data = snapshot.get("fisioterapeutas", {})
            for nome, dados in fisios_data.items():
                if nome in self.fisioterapeutas and isinstance(dados, dict):
                    fisio = self.fisioterapeutas[nome]
                    if "sessoes_por_servico" in dados:
                        fisio.sessoes_por_servico = dict(dados["sessoes_por_servico"])
                    if "pct_crescimento_por_servico" in dados:
                        fisio.pct_crescimento_por_servico = dict(dados["pct_crescimento_por_servico"])
            
            # Restaura serviços (incluindo sessoes_mes_base)
            servicos_data = snapshot.get("servicos", {})
            for nome, dados in servicos_data.items():
                if nome in self.servicos and isinstance(dados, dict):
                    if "sessoes_mes_base" in dados:
                        self.servicos[nome].sessoes_mes_base = dados["sessoes_mes_base"]
                    if "pct_crescimento" in dados:
                        self.servicos[nome].pct_crescimento = dados["pct_crescimento"]
            
            # Restaura proprietários
            props_data = snapshot.get("proprietarios", {})
            for nome, dados in props_data.items():
                if nome in self.proprietarios and isinstance(dados, dict):
                    prop = self.proprietarios[nome]
                    if "sessoes_por_servico" in dados:
                        prop.sessoes_por_servico = dict(dados["sessoes_por_servico"])
                    if "pct_crescimento_por_servico" in dados:
                        prop.pct_crescimento_por_servico = dict(dados["pct_crescimento_por_servico"])
            
            # Restaura profissionais
            profs_data = snapshot.get("profissionais", {})
            for nome, dados in profs_data.items():
                if nome in self.profissionais and isinstance(dados, dict):
                    prof = self.profissionais[nome]
                    if "sessoes_por_servico" in dados:
                        prof.sessoes_por_servico = dict(dados["sessoes_por_servico"])
                    if "pct_crescimento_por_servico" in dados:
                        prof.pct_crescimento_por_servico = dict(dados["pct_crescimento_por_servico"])
            
            self.sincronizar_proprietarios()
            return True
        except Exception:
            return False
    
    # ============================================
    # CÁLCULO SIMPLES NACIONAL / CARNÊ LEÃO
    # ============================================
    
    def calcular_simples_nacional_mes(self, mes: int, receita_mensal: float, folha_mensal: float, 
                                       rbt12: float, folha_12m: float) -> dict:
        """
        Calcula DAS do Simples Nacional para um mês.
        
        Args:
            mes: Número do mês (1-12)
            receita_mensal: Receita bruta do mês
            folha_mensal: Folha de pagamento do mês
            rbt12: Receita Bruta acumulada 12 meses
            folha_12m: Folha acumulada 12 meses
        
        Returns:
            dict com fator_r, anexo, aliquota_efetiva, das
        """
        ps = self.premissas_simples
        
        # Fator R
        fator_r = folha_12m / rbt12 if rbt12 > 0 else 0
        
        # Determina anexo
        if fator_r >= ps.limite_fator_r:
            anexo = "III"
            tabela = ps.tabela_anexo_iii
        else:
            anexo = "V"
            tabela = ps.tabela_anexo_v
        
        # Encontra faixa
        aliq_nominal = 0
        deducao = 0
        for limite, aliq, ded in tabela:
            if rbt12 <= limite:
                aliq_nominal = aliq
                deducao = ded
                break
        
        # Alíquota efetiva
        aliq_efetiva = (rbt12 * aliq_nominal - deducao) / rbt12 if rbt12 > 0 else 0
        
        # DAS
        das = receita_mensal * aliq_efetiva
        
        return {
            "mes": mes,
            "receita_mensal": receita_mensal,
            "folha_mensal": folha_mensal,
            "rbt12": rbt12,
            "folha_12m": folha_12m,
            "fator_r": fator_r,
            "anexo": anexo,
            "aliquota_nominal": aliq_nominal,
            "deducao": deducao,
            "aliquota_efetiva": aliq_efetiva,
            "das": das
        }
    
    def calcular_ir_carne_leao(self, base_ir: float) -> tuple:
        """
        Calcula IR do Carnê Leão com redutor (Lei 15.270/2025).
        
        Returns:
            (ir_devido, status)
        """
        ps = self.premissas_simples
        
        # Isento
        if base_ir <= ps.limite_isencao_ir:
            return 0, "ISENTO"
        
        # Calcula IR pela tabela progressiva
        ir_tabela = 0
        for limite, aliq, ded in ps.tabela_ir_pf:
            if base_ir <= limite:
                ir_tabela = max(0, base_ir * aliq - ded)
                break
        
        # Sem redutor (acima do teto)
        if base_ir >= ps.teto_redutor_ir:
            return ir_tabela, "SEM_REDUTOR"
        
        # Com redutor proporcional
        redutor = ps.deducao_fixa_ir * (ps.teto_redutor_ir - base_ir) / (ps.teto_redutor_ir - ps.limite_isencao_ir)
        ir_final = max(0, ir_tabela - redutor)
        
        return ir_final, f"REDUTOR_{redutor:.2f}"
    
    def calcular_carne_leao_mes(self, mes: int, receita_mensal: float) -> dict:
        """
        Calcula tributos do Carnê Leão (PF) para um mês.
        
        Args:
            mes: Número do mês (1-12)
            receita_mensal: Receita do mês (para PF)
        
        Returns:
            dict com inss, base_ir, ir, total
        """
        ps = self.premissas_simples
        
        # INSS Contribuinte Individual
        inss = min(receita_mensal * ps.aliquota_inss_pf, ps.teto_inss_pf)
        
        # Base IR = Receita - INSS
        base_ir = receita_mensal - inss
        
        # IR
        ir, status = self.calcular_ir_carne_leao(base_ir)
        
        # Total tributação
        total = inss + ir
        
        # Alíquota efetiva
        aliq_efetiva = total / receita_mensal if receita_mensal > 0 else 0
        
        return {
            "mes": mes,
            "receita_mensal": receita_mensal,
            "inss": inss,
            "base_ir": base_ir,
            "ir": ir,
            "status": status,
            "total": total,
            "aliquota_efetiva": aliq_efetiva
        }
    
    def calcular_simples_nacional_anual(self) -> dict:
        """
        Calcula Simples Nacional e Carnê Leão para o ano inteiro.
        
        IMPORTANTE: O Fator R considera apenas folha CLT + Pró-Labore.
        Fisioterapeutas autônomos (RPA) não entram no cálculo do Fator R.
        
        Returns:
            dict com projecao_pj, projecao_pf, total_pj, total_pf, comparativo
        """
        ps = self.premissas_simples
        
        # Calcula receita bruta mensal (proprietários + profissionais)
        receita_bruta = self.calcular_receita_bruta_total()
        receitas_mensais = receita_bruta.get("Total", [0] * 12)
        
        # Se receita de proprietários/profissionais é zero, tenta usar fisioterapeutas
        if sum(receitas_mensais) == 0:
            projecao_folha_fisio = self.projetar_folha_fisioterapeutas_anual()
            receitas_mensais = [p["producao_bruta"] for p in projecao_folha_fisio]
        
        # Calcular folha para Fator R (apenas CLT + Pró-Labore, sem FGTS e informais)
        projecao_folha_fator_r = []
        for mes in range(1, 13):
            folha = self.calcular_folha_mes(mes)
            # Fator R = salários CLT (brutos, sem FGTS) + Pró-Labore
            # NÃO inclui: FGTS, informais, fisioterapeutas autônomos
            folha_fator_r = (folha['clt']['salarios_brutos'] + 
                           folha['prolabore']['bruto'])
            projecao_folha_fator_r.append(folha_fator_r)
        
        # === SIMPLES NACIONAL (PJ) ===
        projecao_pj = []
        rbt12_acum = 0
        folha_12m_acum = 0
        
        for mes in range(12):
            # Receita vem da receita bruta total (proprietários + profissionais)
            receita_mes = receitas_mensais[mes]
            
            # Folha para Fator R (apenas CLT + Pró-Labore)
            folha_mes = projecao_folha_fator_r[mes]
            
            # Acumula RBT12 e Folha 12m
            rbt12_acum += receita_mes
            folha_12m_acum += folha_mes
            
            # Calcula Simples
            calc_pj = self.calcular_simples_nacional_mes(
                mes + 1, receita_mes, folha_mes, rbt12_acum, folha_12m_acum
            )
            projecao_pj.append(calc_pj)
        
        # === CARNÊ LEÃO (PF) ===
        # Usa a MESMA receita do Simples Nacional (para comparação justa)
        # Se faturamento_pf_anual > 0, usa ele; senão usa receita real
        total_receita_anual = sum(p["receita_mensal"] for p in projecao_pj)
        projecao_pf = []
        
        # Usa receita real se faturamento_pf_anual não foi preenchido
        receita_pf_anual = ps.faturamento_pf_anual if ps.faturamento_pf_anual > 0 else total_receita_anual
        
        for mes in range(12):
            # Distribui proporcionalmente à receita mensal
            proporcao = projecao_pj[mes]["receita_mensal"] / total_receita_anual if total_receita_anual > 0 else 1/12
            receita_pf_mes = receita_pf_anual * proporcao
            
            calc_pf = self.calcular_carne_leao_mes(mes + 1, receita_pf_mes)
            projecao_pf.append(calc_pf)
        
        # Totais
        total_pj = sum(p["das"] for p in projecao_pj)
        total_pf = sum(p["total"] for p in projecao_pf)
        
        # Comparativo
        diferenca = total_pj - total_pf
        mais_vantajoso = "PF" if diferenca > 0 else "PJ"
        
        return {
            "projecao_pj": projecao_pj,
            "projecao_pf": projecao_pf,
            "total_pj": total_pj,
            "total_pf": total_pf,
            "diferenca": diferenca,
            "mais_vantajoso": mais_vantajoso,
            "receita_total": total_receita_anual
        }
    
    def get_imposto_para_dre(self, mes: int) -> float:
        """
        Retorna o imposto do mês baseado no regime tributário selecionado.
        
        Args:
            mes: Número do mês (1-12)
        
        Returns:
            Valor do imposto do mês
        """
        regime = self.premissas_folha.regime_tributario
        
        calc = self.calcular_simples_nacional_anual()
        
        if "Simples" in regime or "PJ" in regime:
            return calc["projecao_pj"][mes - 1]["das"]
        elif "Carnê" in regime or "PF" in regime:
            return calc["projecao_pf"][mes - 1]["total"]
        else:
            # Default: Simples Nacional
            return calc["projecao_pj"][mes - 1]["das"]
    
    def get_impostos_para_dre_anual(self) -> list:
        """
        Retorna lista de impostos mensais baseado no regime tributário.
        
        Returns:
            Lista com 12 valores de imposto
        """
        return [self.get_imposto_para_dre(mes) for mes in range(1, 13)]
    
    def sincronizar_proprietarios(self):
        """
        Sincroniza TODA a equipe entre todas as estruturas:
        - motor.proprietarios (Atendimentos - sessões proprietários)
        - motor.profissionais (Atendimentos - sessões profissionais)
        - motor.fisioterapeutas (Folha Fisioterapeutas)
        - motor.socios_prolabore (Folha e Pró-Labore)
        """
        # Classes já definidas neste arquivo, não precisa importar
        
        # ========== PROPRIETÁRIOS ==========
        # 1. Sincroniza de fisioterapeutas -> socios_prolabore
        for nome, fisio in self.fisioterapeutas.items():
            if fisio.cargo == "Proprietário":
                if nome not in self.socios_prolabore:
                    self.socios_prolabore[nome] = SocioProLabore(
                        nome=nome,
                        prolabore=1631.0,
                        dependentes_ir=0,
                        mes_reajuste=5,
                        pct_aumento=0.0,
                        participacao=1.0,  # 100% padrão
                        capital=10000.0    # R$ 10.000 padrão
                    )
        
        # 2. Sincroniza de proprietarios (Atendimentos) -> socios_prolabore e fisioterapeutas
        for nome, prop in self.proprietarios.items():
            if nome not in self.socios_prolabore:
                self.socios_prolabore[nome] = SocioProLabore(
                    nome=nome,
                    prolabore=1631.0,
                    dependentes_ir=0,
                    mes_reajuste=5,
                    pct_aumento=0.0,
                    participacao=1.0,  # 100% padrão
                    capital=10000.0    # R$ 10.000 padrão
                )
            
            # Sincroniza para fisioterapeutas
            if nome not in self.fisioterapeutas:
                self.fisioterapeutas[nome] = Fisioterapeuta(
                    nome=nome,
                    cargo="Proprietário",
                    nivel=0,
                    filial="Copacabana",
                    sessoes_por_servico=dict(prop.sessoes_por_servico) if prop.sessoes_por_servico else {},
                    pct_crescimento_por_servico=dict(prop.pct_crescimento_por_servico) if prop.pct_crescimento_por_servico else {}
                )
            else:
                # v1.99.56: SUBSTITUI sessões (não mescla) para evitar duplicação
                if prop.sessoes_por_servico:
                    self.fisioterapeutas[nome].sessoes_por_servico = dict(prop.sessoes_por_servico)
                if prop.pct_crescimento_por_servico:
                    self.fisioterapeutas[nome].pct_crescimento_por_servico = dict(prop.pct_crescimento_por_servico)
        
        # ========== PROFISSIONAIS ==========
        # 3. Sincroniza de profissionais (Atendimentos) -> fisioterapeutas
        for nome, prof in self.profissionais.items():
            if nome not in self.fisioterapeutas:
                # Novo profissional - adiciona com nível padrão 2 (30%)
                self.fisioterapeutas[nome] = Fisioterapeuta(
                    nome=nome,
                    cargo="Fisioterapeuta",
                    nivel=2,  # Nível padrão
                    filial="Copacabana",
                    sessoes_por_servico=dict(prof.sessoes_por_servico) if prof.sessoes_por_servico else {},
                    pct_crescimento_por_servico=dict(prof.pct_crescimento_por_servico) if prof.pct_crescimento_por_servico else {}
                )
            else:
                # v1.99.56: SUBSTITUI sessões (não mescla) para evitar duplicação
                if prof.sessoes_por_servico:
                    self.fisioterapeutas[nome].sessoes_por_servico = dict(prof.sessoes_por_servico)
                if prof.pct_crescimento_por_servico:
                    self.fisioterapeutas[nome].pct_crescimento_por_servico = dict(prof.pct_crescimento_por_servico)

        # 4. Sincroniza de fisioterapeutas -> profissionais (sessões e crescimento)
        for nome, fisio in self.fisioterapeutas.items():
            if fisio.cargo in ["Fisioterapeuta", "Gerente"]:
                if nome not in self.profissionais:
                    from modules.motor_calculo import Profissional
                    self.profissionais[nome] = Profissional(
                        nome=nome,
                        tipo="profissional",
                        sessoes_por_servico=dict(fisio.sessoes_por_servico) if fisio.sessoes_por_servico else {},
                        pct_crescimento_por_servico=dict(fisio.pct_crescimento_por_servico) if fisio.pct_crescimento_por_servico else {}
                    )
                else:
                    # Atualiza sessões e crescimento
                    if fisio.sessoes_por_servico:
                        self.profissionais[nome].sessoes_por_servico.update(fisio.sessoes_por_servico)
                    if fisio.pct_crescimento_por_servico:
                        self.profissionais[nome].pct_crescimento_por_servico.update(fisio.pct_crescimento_por_servico)
    
    def get_proprietarios(self) -> list:
        """Retorna lista de nomes dos proprietários cadastrados (de todas as fontes)"""
        nomes = set()
        # De fisioterapeutas
        for nome, fisio in self.fisioterapeutas.items():
            if fisio.cargo == "Proprietário":
                nomes.add(nome)
        # De proprietarios (Atendimentos)
        for nome in self.proprietarios.keys():
            nomes.add(nome)
        return list(nomes)
    
    def get_gerentes(self) -> list:
        """Retorna lista de nomes dos gerentes cadastrados"""
        return [nome for nome, fisio in self.fisioterapeutas.items() if fisio.cargo == "Gerente"]

    def calcular_folha_mes(self, mes: int) -> dict:
        """
        Calcula folha de pagamento para um mês específico.
        mes: 1-12 (Janeiro=1, Dezembro=12)
        Retorna dicionário com todos os valores calculados
        """
        pf = self.premissas_folha
        resultado = {
            "clt": {"salarios_brutos": 0, "inss": 0, "irrf": 0, "fgts": 0, "vt": 0, "vr": 0, 
                    "plano_saude": 0, "liquido": 0, "provisao_13": 0, "provisao_ferias": 0,
                    "custo_total": 0, "detalhes": []},
            "informal": {"salarios_brutos": 0, "liquido": 0, "custo_total": 0, "detalhes": []},
            "prolabore": {"bruto": 0, "inss": 0, "irrf": 0, "liquido": 0, "detalhes": []},
            "total": {"salarios": 0, "inss": 0, "irrf": 0, "fgts": 0, "provisao_13": 0, 
                      "provisao_ferias": 0, "custo_total": 0}
        }
        
        # === FUNCIONÁRIOS ===
        for nome, func in self.funcionarios_clt.items():
            if not func.ativo:
                continue
            
            # Verifica se já foi admitido (mes é 1-12, mes_admissao é 1-12)
            if mes < func.mes_admissao:
                continue
            
            # Salário com dissídio
            salario = func.salario_base
            if mes >= pf.mes_dissidio:
                salario = salario * (1 + pf.pct_dissidio)
            
            if func.tipo_vinculo == "clt":
                # === CLT: tem INSS, FGTS, VT, VR ===
                inss = calcular_inss(salario, pf.tabela_inss)
                irrf = calcular_ir(salario, inss, func.dependentes_ir, pf.deducao_dependente_ir, pf.tabela_ir)
                fgts = salario * pf.aliquota_fgts
                vt = func.vt_dia * pf.dias_uteis_mes
                vr = func.vr_dia * pf.dias_uteis_mes
                liquido = salario - inss - irrf
                
                # Provisões mensais (só CLT)
                provisao_13 = salario / 12  # 1/12 avos do salário
                provisao_ferias = (salario / 12) * (4/3)  # 1/12 + 1/3 de férias
                
                custo = salario + fgts + vt + vr + func.plano_saude + func.plano_odonto + provisao_13 + provisao_ferias
                
                resultado["clt"]["salarios_brutos"] += salario
                resultado["clt"]["inss"] += inss
                resultado["clt"]["irrf"] += irrf
                resultado["clt"]["fgts"] += fgts
                resultado["clt"]["vt"] += vt
                resultado["clt"]["vr"] += vr
                resultado["clt"]["plano_saude"] += func.plano_saude
                resultado["clt"]["liquido"] += liquido
                resultado["clt"]["provisao_13"] += provisao_13
                resultado["clt"]["provisao_ferias"] += provisao_ferias
                resultado["clt"]["custo_total"] += custo
                
                resultado["clt"]["detalhes"].append({
                    "nome": nome, "vinculo": "CLT", "salario": salario, "inss": inss, 
                    "irrf": irrf, "fgts": fgts, "liquido": liquido
                })
            else:
                # === INFORMAL: só salário, sem encargos ===
                liquido = salario
                custo = salario
                
                resultado["informal"]["salarios_brutos"] += salario
                resultado["informal"]["liquido"] += liquido
                resultado["informal"]["custo_total"] += custo
                
                resultado["informal"]["detalhes"].append({
                    "nome": nome, "vinculo": "Informal", "salario": salario, "liquido": liquido
                })
        
        # === SÓCIOS PRÓ-LABORE ===
        for nome, socio in self.socios_prolabore.items():
            if not socio.ativo:
                continue
            
            # Pró-labore com reajuste
            prolabore = socio.prolabore
            if mes >= socio.mes_reajuste:
                prolabore = prolabore * (1 + pf.pct_dissidio)
            
            # Cálculos (11% INSS para pró-labore)
            inss = prolabore * 0.11
            irrf = calcular_ir(prolabore, inss, socio.dependentes_ir, pf.deducao_dependente_ir, pf.tabela_ir)
            liquido = prolabore - inss - irrf
            
            resultado["prolabore"]["bruto"] += prolabore
            resultado["prolabore"]["inss"] += inss
            resultado["prolabore"]["irrf"] += irrf
            resultado["prolabore"]["liquido"] += liquido
            
            resultado["prolabore"]["detalhes"].append({
                "nome": nome, "prolabore": prolabore, "inss": inss, 
                "irrf": irrf, "liquido": liquido
            })
        
        # === TOTAIS ===
        resultado["total"]["salarios"] = (
            resultado["clt"]["salarios_brutos"] + 
            resultado["informal"]["salarios_brutos"] + 
            resultado["prolabore"]["bruto"]
        )
        resultado["total"]["inss"] = resultado["clt"]["inss"] + resultado["prolabore"]["inss"]
        resultado["total"]["irrf"] = resultado["clt"]["irrf"] + resultado["prolabore"]["irrf"]
        resultado["total"]["fgts"] = resultado["clt"]["fgts"]
        resultado["total"]["provisao_13"] = resultado["clt"]["provisao_13"]
        resultado["total"]["provisao_ferias"] = resultado["clt"]["provisao_ferias"]
        resultado["total"]["custo_total"] = (
            resultado["clt"]["custo_total"] + 
            resultado["informal"]["custo_total"] + 
            resultado["prolabore"]["bruto"]
        )
        
        return resultado
    
    def projetar_folha_anual(self) -> list:
        """Projeta folha de pagamento para todos os meses do ano"""
        return [self.calcular_folha_mes(mes) for mes in range(1, 13)]
    
    def calcular_custo_pessoal_dre(self) -> Dict[str, List[float]]:
        """
        Calcula custo de pessoal DINÂMICO para o DRE.
        Retorna dicionário com cada componente e total mensal.
        
        IMPORTANTE: Para PF (Pessoa Física / Carnê Leão):
        - TEM "Folha Proprietários" - é a remuneração por produção (60%)
        - NÃO tem "Pró-Labore" separado - já está na Folha Proprietário
        - Pode ter funcionários (CLT/informal) se o PF contratar alguém
        
        Componentes:
        - Folha Fisioterapeutas: comissão baseada em atendimentos
        - Folha Proprietários: comissão baseada em produção
        - Folha CLT: salários + encargos (INSS, FGTS, 13º, férias)
        - Folha Informal: pagamentos sem vínculo
        - Pró-Labore: retirada dos sócios (SOMENTE PJ)
        """
        # Projetar folhas anuais
        folha_fisio = self.projetar_folha_fisioterapeutas_anual()
        folha_geral = self.projetar_folha_anual()
        
        # Verifica regime tributário
        regime = self.premissas_folha.regime_tributario
        is_pf = "Carnê" in regime or "PF" in regime
        
        resultado = {
            "Folha Fisioterapeutas": [],
            "Folha Proprietários": [],
            "Pró-Labore": [],
            "Folha CLT + Encargos": [],
            "Total Custo Pessoal": []
        }
        
        for m in range(12):
            # Folha baseada em atendimentos (fisioterapeutas)
            fisio = folha_fisio[m]["total_fisioterapeutas"]
            
            # Folha Proprietários: tanto PJ quanto PF (é a remuneração por produção)
            prop = folha_fisio[m]["total_proprietarios"]
            
            # Pró-Labore: SOMENTE para PJ (para PF já está na Folha Proprietário)
            if is_pf:
                prolabore = 0  # PF não tem pró-labore separado
            else:
                prolabore = folha_geral[m]["prolabore"]["bruto"]
            
            # Folha CLT/Informal: existe tanto para PJ quanto PF (se tiver funcionários)
            clt = folha_geral[m]["clt"]["custo_total"]
            informal = folha_geral[m]["informal"]["custo_total"]
            
            # Agrupar CLT + Informal como "Folha CLT + Encargos"
            folha_clt_total = clt + informal
            
            # Total do mês
            total = fisio + prop + prolabore + folha_clt_total
            
            resultado["Folha Fisioterapeutas"].append(fisio)
            resultado["Folha Proprietários"].append(prop)
            resultado["Pró-Labore"].append(prolabore)
            resultado["Folha CLT + Encargos"].append(folha_clt_total)
            resultado["Total Custo Pessoal"].append(total)
        
        return resultado
    
    # ============================================
    # CÁLCULOS DE RECEITA
    # ============================================
    
    def get_total_sessoes_servico(self, servico: str) -> int:
        """
        Retorna total de sessões de um serviço.
        RESPEITA modo_calculo_sessoes.
        """
        modo = getattr(self.operacional, 'modo_calculo_sessoes', 'servico')
        
        if modo == "servico":
            # Retorna do cadastro do serviço
            if servico in self.servicos:
                return self.servicos[servico].sessoes_mes_base
            return 0
        
        # Modo profissional: soma dos cadastros
        total = 0
        
        # Sessões dos proprietários (estrutura antiga)
        for prop in self.proprietarios.values():
            total += prop.sessoes_por_servico.get(servico, 0)
        
        # Sessões dos profissionais (estrutura antiga)
        for prof in self.profissionais.values():
            total += prof.sessoes_por_servico.get(servico, 0)
        
        # FALLBACK: Sessões dos fisioterapeutas (estrutura nova)
        if total == 0:
            for fisio in self.fisioterapeutas.values():
                if fisio.ativo:
                    total += fisio.sessoes_por_servico.get(servico, 0)
        
        return total
    
    def calcular_sessoes_mes(self, servico: str, mes: int) -> float:
        """
        Calcula quantidade de sessões no mês usando CRESCIMENTO LINEAR.
        Fórmula: base + (meta - base) / 13.1 * (mes + 0.944)

        RESPEITA modo_calculo_sessoes:
        - "servico": Usa sessoes_mes_base e pct_crescimento do serviço
        - "profissional": Soma dos fisios com seus crescimentos individuais
        """
        modo = getattr(self.operacional, 'modo_calculo_sessoes', 'servico')

        # ========================================
        # MODO SERVIÇO: Usa dados do cadastro de serviços
        # ========================================
        if modo == "servico":
            if servico not in self.servicos:
                return 0

            srv = self.servicos[servico]
            sessoes_base = srv.sessoes_mes_base
            pct_crescimento = srv.pct_crescimento

            if sessoes_base == 0:
                return 0

            if pct_crescimento > 0:
                crescimento_qtd = sessoes_base * pct_crescimento
                cresc_mensal = crescimento_qtd / 13.1
                sessoes = sessoes_base + cresc_mensal * (mes + 0.944)
            else:
                sessoes = sessoes_base

            # APLICA SAZONALIDADE
            fator_sazon = self.sazonalidade.fatores[mes] if hasattr(self, 'sazonalidade') else 1.0
            return sessoes * fator_sazon

        # ========================================
        # MODO PROFISSIONAL: Soma dos cadastros com crescimento individual
        # ========================================
        total = 0

        # Primeiro tenta fisioterapeutas (estrutura principal)
        for fisio in self.fisioterapeutas.values():
            if not fisio.ativo:
                continue
            sessoes_base = fisio.sessoes_por_servico.get(servico, 0)
            if sessoes_base > 0:
                pct_crescimento = fisio.pct_crescimento_por_servico.get(servico, 0.0)
                if pct_crescimento > 0:
                    crescimento_qtd = sessoes_base * pct_crescimento
                    cresc_mensal = crescimento_qtd / 13.1
                    total += sessoes_base + cresc_mensal * (mes + 0.944)
                else:
                    total += sessoes_base

        # FALLBACK: Se não encontrou em fisioterapeutas, tenta estruturas antigas
        if total == 0:
            # Proprietários (estrutura antiga)
            for prop in self.proprietarios.values():
                sessoes_base = prop.sessoes_por_servico.get(servico, 0)
                if sessoes_base > 0:
                    pct_crescimento = prop.pct_crescimento_por_servico.get(servico, 0.0)
                    crescimento_qtd = sessoes_base * pct_crescimento
                    cresc_mensal = crescimento_qtd / 13.1
                    total += sessoes_base + cresc_mensal * (mes + 0.944)

            # Profissionais (estrutura antiga)
            for prof in self.profissionais.values():
                sessoes_base = prof.sessoes_por_servico.get(servico, 0)
                if sessoes_base > 0:
                    pct_crescimento = prof.pct_crescimento_por_servico.get(servico, 0.0)
                    crescimento_qtd = sessoes_base * pct_crescimento
                    cresc_mensal = crescimento_qtd / 13.1
                    total += sessoes_base + cresc_mensal * (mes + 0.944)

        # APLICA SAZONALIDADE
        fator_sazon = self.sazonalidade.fatores[mes] if hasattr(self, 'sazonalidade') else 1.0
        return total * fator_sazon

    def calcular_sessoes_mes_por_tipo(self, servico: str, mes: int, tipo: str = "todos") -> float:
        """
        Calcula sessões por tipo (proprietario, profissional ou todos) com crescimento.
        
        RESPEITA modo_calculo_sessoes:
        - "servico": Usa sessões do serviço, distribui proporcionalmente entre tipos
        - "profissional": Soma diretamente dos fisios/proprietarios/profissionais
        """
        modo = getattr(self.operacional, 'modo_calculo_sessoes', 'servico')
        
        # ========================================
        # MODO SERVIÇO: Total vem do serviço, distribui por proporção
        # ========================================
        if modo == "servico":
            # Pega total de sessões do serviço para o mês
            total_servico = self.get_sessoes_servico_mes(servico, mes)
            
            if total_servico == 0:
                return 0
            
            # Calcula proporção de cada tipo baseado nos cadastros
            sessoes_prop_base = 0
            sessoes_prof_base = 0
            
            # Proprietários
            for prop in self.proprietarios.values():
                sessoes_prop_base += prop.sessoes_por_servico.get(servico, 0)
            
            # Profissionais
            for prof in self.profissionais.values():
                sessoes_prof_base += prof.sessoes_por_servico.get(servico, 0)
            
            # Fisioterapeutas (fallback)
            if sessoes_prop_base == 0 and sessoes_prof_base == 0:
                for fisio in self.fisioterapeutas.values():
                    if not fisio.ativo:
                        continue
                    sessoes_base = fisio.sessoes_por_servico.get(servico, 0)
                    if fisio.cargo == "Proprietário":
                        sessoes_prop_base += sessoes_base
                    else:
                        sessoes_prof_base += sessoes_base
            
            total_base = sessoes_prop_base + sessoes_prof_base
            
            # Se não há cadastro de nenhum tipo, assume tudo como profissional
            if total_base == 0:
                if tipo == "todos":
                    return total_servico
                elif tipo == "profissional":
                    return total_servico
                else:
                    return 0
            
            # Calcula proporção
            pct_prop = sessoes_prop_base / total_base if total_base > 0 else 0
            pct_prof = sessoes_prof_base / total_base if total_base > 0 else 0
            
            if tipo == "proprietario":
                return total_servico * pct_prop
            elif tipo == "profissional":
                return total_servico * pct_prof
            else:  # todos
                return total_servico
        
        # ========================================
        # MODO PROFISSIONAL: Soma direto dos cadastros (comportamento original)
        # ========================================
        total = 0
        
        if tipo in ["proprietario", "todos"]:
            for prop in self.proprietarios.values():
                sessoes_base = prop.sessoes_por_servico.get(servico, 0)
                if sessoes_base > 0:
                    pct_crescimento = prop.pct_crescimento_por_servico.get(servico, 0.0)
                    crescimento_qtd = sessoes_base * pct_crescimento
                    cresc_mensal = crescimento_qtd / 13.1
                    total += sessoes_base + cresc_mensal * (mes + 0.944)
        
        if tipo in ["profissional", "todos"]:
            for prof in self.profissionais.values():
                sessoes_base = prof.sessoes_por_servico.get(servico, 0)
                if sessoes_base > 0:
                    pct_crescimento = prof.pct_crescimento_por_servico.get(servico, 0.0)
                    crescimento_qtd = sessoes_base * pct_crescimento
                    cresc_mensal = crescimento_qtd / 13.1
                    total += sessoes_base + cresc_mensal * (mes + 0.944)
        
        # FALLBACK: Fisioterapeutas (estrutura nova)
        if total == 0:
            for fisio in self.fisioterapeutas.values():
                if not fisio.ativo:
                    continue
                # Filtra por tipo se necessário
                if tipo == "proprietario" and fisio.cargo != "Proprietário":
                    continue
                if tipo == "profissional" and fisio.cargo == "Proprietário":
                    continue
                    
                sessoes_base = fisio.sessoes_por_servico.get(servico, 0)
                if sessoes_base > 0:
                    pct_crescimento = fisio.pct_crescimento_por_servico.get(servico, 0.0)
                    if pct_crescimento > 0:
                        crescimento_qtd = sessoes_base * pct_crescimento
                        cresc_mensal = crescimento_qtd / 13.1
                        total += sessoes_base + cresc_mensal * (mes + 0.944)
                    else:
                        total += sessoes_base
        
        # APLICA SAZONALIDADE
        fator_sazon = self.sazonalidade.fatores[mes] if hasattr(self, 'sazonalidade') else 1.0
        return total * fator_sazon

    def calcular_valor_servico_mes(self, servico: str, mes: int, tipo: str = "profissional") -> float:
        """
        Calcula valor do serviço no mês.
        Usa valor_2025 antes do mês de reajuste e valor_2026 após.
        Se não houver valor específico por tipo, usa o valor do serviço.
        """
        srv = self.servicos.get(servico)
        if not srv:
            return 0

        # Pega valores antes/depois conforme tipo
        if tipo == "proprietario":
            valores = self.valores_proprietario.get(servico, {})
        else:
            valores = self.valores_profissional.get(servico, {})

        # Se é dicionário com antes/depois
        if isinstance(valores, dict) and valores:
            valor_antes = valores.get("antes", 0)
            valor_depois = valores.get("depois", 0)

            # Se não tem valor antes, usa valor depois
            if valor_antes == 0:
                valor_antes = valor_depois

            # Retorna valor conforme mês (mes 0=jan, 1=fev, 2=mar)
            # Reajuste em março = mes_reajuste 3, então mes >= 2 usa valor_depois
            if mes >= srv.mes_reajuste - 1:
                return valor_depois
            else:
                return valor_antes
        elif isinstance(valores, (int, float)) and valores > 0:
            # Compatibilidade com formato antigo (valor único)
            return valores
        else:
            # FALLBACK: Usa valor do próprio serviço quando não há valor específico
            # valor_2026 = valor BASE (antes do reajuste)
            # após reajuste = valor_2026 * (1 + pct_reajuste)
            if mes >= srv.mes_reajuste - 1:
                # Após mês de reajuste: aplica o percentual
                if srv.pct_reajuste > 0:
                    return srv.valor_2026 * (1 + srv.pct_reajuste)
                return srv.valor_2026
            else:
                # Antes do reajuste: valor base cadastrado
                return srv.valor_2026
    
    def calcular_receita_servico_mes(self, servico: str, mes: int) -> float:
        """
        Calcula receita de um serviço em um mês específico.
        v1.99.57: fator_receita já aplicado em calcular_sessoes_mes_por_tipo (não duplicar!)
        """
        receita = 0

        # Receita de proprietários (sessões já incluem fator_receita do cenário)
        sessoes_prop = self.calcular_sessoes_mes_por_tipo(servico, mes, "proprietario")
        valor_prop = self.calcular_valor_servico_mes(servico, mes, "proprietario")
        receita += sessoes_prop * valor_prop

        # Receita de profissionais (sessões já incluem fator_receita do cenário)
        sessoes_prof = self.calcular_sessoes_mes_por_tipo(servico, mes, "profissional")
        valor_prof = self.calcular_valor_servico_mes(servico, mes, "profissional")
        receita += sessoes_prof * valor_prof

        # Aplicar ajustes MANUAIS do cenário (Pessimista/Otimista)
        cenario_nome = self.cenario.nome if hasattr(self, 'cenario') else "Conservador"

        if cenario_nome != "Conservador" and hasattr(self, 'ajustes_cenarios'):
            # Ajuste de sessões (soma às sessões base)
            ajuste_sessoes = self.get_ajuste_sessoes(cenario_nome, servico)
            # Ajuste de valor (soma ao valor base)
            ajuste_valor = self.get_ajuste_valor(cenario_nome, servico)

            if ajuste_sessoes != 0:
                # Calcular valor médio ponderado para as sessões adicionais
                total_sessoes = sessoes_prop + sessoes_prof
                if total_sessoes > 0:
                    valor_medio = receita / total_sessoes
                else:
                    valor_medio = (valor_prop + valor_prof) / 2 if (valor_prop + valor_prof) > 0 else 0
                # Adicionar receita das sessões extras
                receita += ajuste_sessoes * valor_medio

            if ajuste_valor != 0:
                # Aplicar ajuste de valor em todas as sessões
                total_sessoes = sessoes_prop + sessoes_prof + ajuste_sessoes
                receita += ajuste_valor * total_sessoes

        return receita
    
    def calcular_receita_bruta_total(self) -> Dict[str, List[float]]:
        """Calcula receita bruta total por serviço e mês"""
        resultado = {}
        
        for servico in self.servicos:
            resultado[servico] = []
            for mes in range(12):
                receita = self.calcular_receita_servico_mes(servico, mes)
                resultado[servico].append(receita)
        
        # Total geral
        resultado["Total"] = []
        for mes in range(12):
            total_mes = sum(resultado[srv][mes] for srv in self.servicos)
            resultado["Total"].append(total_mes)
        
        self.receita_bruta = resultado
        return resultado
    
    # ============================================
    # CÁLCULOS DE TAXA DE OCUPAÇÃO
    # ============================================
    
    def calcular_capacidade_profissional_mes(self) -> float:
        """Calcula capacidade total de horas dos profissionais por mês"""
        total_horas = 0.0
        for fisio in self.fisioterapeutas.values():
            if fisio.ativo:
                total_horas += fisio.horas_mes
        return total_horas
    
    def calcular_capacidade_sala_mes(self) -> float:
        """Calcula capacidade total de horas das salas por mês"""
        return (self.operacional.num_salas * 
                self.operacional.horas_atendimento_dia * 
                self.operacional.dias_uteis_mes)
    
    def calcular_demanda_profissional_mes(self, mes: int) -> float:
        """Calcula demanda de horas dos profissionais (todas as sessões)"""
        demanda_total = 0.0
        
        for servico_nome, servico in self.servicos.items():
            sessoes = self.calcular_sessoes_mes(servico_nome, mes)
            horas = sessoes * servico.duracao_horas
            demanda_total += horas
        
        return demanda_total
    
    def calcular_demanda_sala_mes(self, mes: int) -> float:
        """Calcula demanda de horas das salas (apenas serviços que usam sala)"""
        demanda_total = 0.0
        
        for servico_nome, servico in self.servicos.items():
            if servico.usa_sala:  # Exclui Domiciliar
                sessoes = self.calcular_sessoes_mes(servico_nome, mes)
                horas = sessoes * servico.duracao_horas
                demanda_total += horas
        
        return demanda_total
    
    def calcular_demanda_por_profissional_mes(self, mes: int) -> Dict[str, float]:
        """Calcula demanda de horas por profissional no mês"""
        demanda = {}
        
        for nome, fisio in self.fisioterapeutas.items():
            if not fisio.ativo:
                demanda[nome] = 0.0
                continue
            
            horas_fisio = 0.0
            for servico_nome, qtd_base in fisio.sessoes_por_servico.items():
                if servico_nome in self.servicos:
                    servico = self.servicos[servico_nome]
                    # Aplicar crescimento LINEAR (mesma fórmula de calcular_sessoes_mes)
                    crescimento = fisio.pct_crescimento_por_servico.get(servico_nome, 0)
                    if crescimento > 0:
                        crescimento_qtd = qtd_base * crescimento
                        cresc_mensal = crescimento_qtd / 13.1
                        sessoes = qtd_base + cresc_mensal * (mes + 0.944)
                    else:
                        sessoes = qtd_base
                    horas_fisio += sessoes * servico.duracao_horas
            
            demanda[nome] = horas_fisio
        
        return demanda
    
    def calcular_sessoes_por_servico_mes(self, mes: int) -> Dict[str, float]:
        """Calcula sessões por serviço no mês"""
        sessoes = {}
        for servico_nome in self.servicos:
            sessoes[servico_nome] = self.calcular_sessoes_mes(servico_nome, mes)
        return sessoes
    
    def calcular_ocupacao_mes(self, mes: int) -> AnaliseOcupacaoMes:
        """Calcula análise de ocupação completa para um mês"""
        analise = AnaliseOcupacaoMes(
            mes=mes,
            ano=2026,
            capacidade_profissional=self.calcular_capacidade_profissional_mes(),
            capacidade_sala=self.calcular_capacidade_sala_mes(),
            demanda_profissional=self.calcular_demanda_profissional_mes(mes),
            demanda_sala=self.calcular_demanda_sala_mes(mes),
            total_sessoes=sum(self.calcular_sessoes_mes(srv, mes) for srv in self.servicos),
            sessoes_por_servico=self.calcular_sessoes_por_servico_mes(mes),
            demanda_por_profissional=self.calcular_demanda_por_profissional_mes(mes)
        )
        return analise
    
    def calcular_ocupacao_anual(self) -> AnaliseOcupacaoAnual:
        """Calcula análise de ocupação para o ano inteiro"""
        analise = AnaliseOcupacaoAnual(
            ano=2026,
            num_salas=self.operacional.num_salas,
            horas_funcionamento_dia=self.operacional.horas_atendimento_dia,
            dias_uteis_mes=self.operacional.dias_uteis_mes
        )
        
        for mes in range(12):
            analise.meses.append(self.calcular_ocupacao_mes(mes))
        
        return analise
    
    def get_resumo_ocupacao(self) -> Dict:
        """Retorna resumo da ocupação para exibição"""
        analise = self.calcular_ocupacao_anual()
        
        return {
            "capacidade_profissional_mes": analise.meses[0].capacidade_profissional if analise.meses else 0,
            "capacidade_sala_mes": analise.capacidade_sala_mes,
            "media_taxa_profissional": analise.media_taxa_profissional,
            "media_taxa_sala": analise.media_taxa_sala,
            "gargalo": analise.gargalo_predominante,
            "total_sessoes_ano": analise.total_sessoes_ano,
            "meses": [
                {
                    "mes": m.mes + 1,
                    "taxa_profissional": m.taxa_ocupacao_profissional,
                    "taxa_sala": m.taxa_ocupacao_sala,
                    "gargalo": m.gargalo,
                    "status": m.status,
                    "status_emoji": m.status_emoji
                }
                for m in analise.meses
            ]
        }
    
    # ============================================
    # CÁLCULOS DE PONTO DE EQUILÍBRIO
    # ============================================
    
    def calcular_custo_infraestrutura_mes(self) -> float:
        """
        Calcula custo de infraestrutura mensal (custos rateados por m²).
        Inclui: Aluguel, Energia, Limpeza, Manutenção, Seguros.
        Fonte: TDABC linhas 62-66 + Depreciação + Amortização.
        """
        # Custos base de infraestrutura (aproximação)
        # Esses valores deveriam vir das despesas configuradas
        self.calcular_despesas_fixas()
        
        custo_infra = 0.0
        despesas_infra = ['Aluguel', 'Energia', 'Limpeza', 'Manutencao', 'Seguros']
        
        for desp in despesas_infra:
            if desp in self.despesas:
                # Média mensal
                custo_infra += sum(self.despesas[desp]) / 12
        
        # Se não encontrou despesas específicas, usa estimativa baseada em custos fixos
        if custo_infra == 0:
            # Aproximação: 15% dos custos fixos são infraestrutura
            dre = self.calcular_dre()
            if "Total Custos Fixos" in dre:
                custo_infra = abs(sum(dre["Total Custos Fixos"]) / 12 * 0.15)
        
        return custo_infra
    
    def calcular_custo_ociosidade_mes(self, mes: int) -> float:
        """
        Calcula custo de ociosidade = Custo/Hora × Horas Ociosas.
        Fórmula do TDABC linha 188.
        Usa capacidade de PROFISSIONAIS (como Excel) para cálculo correto.
        """
        ocupacao = self.calcular_ocupacao_mes(mes)
        custo_infra = self.calcular_custo_infraestrutura_mes()
        
        # Usar capacidade de profissionais (como Excel)
        if ocupacao.capacidade_profissional <= 0:
            return 0.0
        
        custo_hora = custo_infra / ocupacao.capacidade_profissional
        horas_ociosas = ocupacao.horas_ociosas_profissional
        
        return custo_hora * horas_ociosas
    
    # ============================================
    # CÁLCULOS TDABC - RATEIO ABC
    # ============================================
    
    def calcular_subtotais_direcionadores(self, mes: int) -> Dict[str, float]:
        """
        Calcula subtotais de custos por direcionador.
        Fonte: TDABC linhas 75-77
        """
        self.calcular_despesas_fixas()
        
        # Categorização de despesas por direcionador
        despesas_m2 = ['Aluguel', 'Energia', 'Limpeza', 'Manutencao', 'Seguros']
        despesas_sessoes = ['Sistema', 'TV/Telefone/Internet', 'Servicos Terceiros', 'Cursos']
        despesas_receita = ['Contabilidade', 'Marketing']
        
        subtotal_m2 = 0.0
        subtotal_sessoes = 0.0
        subtotal_receita = 0.0
        
        for desp, valores in self.despesas.items():
            if "Total" in desp:
                continue
            valor_mes = valores[mes] if mes < len(valores) else valores[0]
            
            # Classificar por direcionador
            desp_lower = desp.lower()
            if any(d.lower() in desp_lower for d in despesas_m2):
                subtotal_m2 += valor_mes
            elif any(d.lower() in desp_lower for d in despesas_sessoes):
                subtotal_sessoes += valor_mes
            elif any(d.lower() in desp_lower for d in despesas_receita):
                subtotal_receita += valor_mes
            else:
                # Default: rateia por receita
                subtotal_receita += valor_mes
        
        # Se não encontrou despesas categorizadas, usa estimativa
        if subtotal_m2 + subtotal_sessoes + subtotal_receita == 0:
            custo_infra = self.calcular_custo_infraestrutura_mes()
            subtotal_m2 = custo_infra * 0.6  # 60% infraestrutura
            subtotal_sessoes = custo_infra * 0.15  # 15% sessões
            subtotal_receita = custo_infra * 0.25  # 25% receita
        
        return {
            "m2": subtotal_m2,
            "sessoes": subtotal_sessoes,
            "receita": subtotal_receita,
            "total": subtotal_m2 + subtotal_sessoes + subtotal_receita
        }
    
    def calcular_rateio_servico_mes(self, servico: str, mes: int) -> RateioTDABC:
        """
        Calcula rateio ABC para um serviço em um mês.
        Fórmula TDABC linhas 103-108
        """
        # Dados do serviço
        sessoes = self.calcular_sessoes_mes(servico, mes)
        receita = self.calcular_receita_servico_mes(servico, mes)
        m2_alocado = self.cadastro_salas.get_m2_por_servico(servico)
        
        # Horas de sala consumidas
        srv = self.servicos.get(servico)
        if srv and srv.usa_sala:
            horas_sala = sessoes * srv.duracao_horas
        else:
            horas_sala = 0.0
        
        # Totais
        total_sessoes = sum(self.calcular_sessoes_mes(s, mes) for s in self.servicos)
        total_receita = sum(self.calcular_receita_servico_mes(s, mes) for s in self.servicos)
        total_m2 = self.cadastro_salas.m2_ativo
        total_horas_sala = self.calcular_demanda_sala_mes(mes)
        
        # Subtotais por direcionador
        subtotais = self.calcular_subtotais_direcionadores(mes)
        
        # Cálculo de pesos para rateio de m² (ponderado por sessões × m²)
        soma_ponderada = 0.0
        for s in self.servicos:
            sess = self.calcular_sessoes_mes(s, mes)
            m2_s = self.cadastro_salas.get_m2_por_servico(s)
            soma_ponderada += sess * m2_s
        
        # Rateio por m² (ponderado)
        if soma_ponderada > 0:
            rateio_m2 = (sessoes * m2_alocado / soma_ponderada) * subtotais["m2"]
        else:
            rateio_m2 = 0.0
        
        # Rateio por sessões
        if total_sessoes > 0:
            rateio_sessoes = (sessoes / total_sessoes) * subtotais["sessoes"]
        else:
            rateio_sessoes = 0.0
        
        # Rateio por receita
        if total_receita > 0:
            rateio_receita = (receita / total_receita) * subtotais["receita"]
        else:
            rateio_receita = 0.0
        
        return RateioTDABC(
            mes=mes,
            servico=servico,
            sessoes=sessoes,
            receita=receita,
            m2_alocado=m2_alocado,
            horas_sala=horas_sala,
            total_sessoes=total_sessoes,
            total_receita=total_receita,
            total_m2=total_m2,
            total_horas_sala=total_horas_sala,
            rateio_m2=rateio_m2,
            rateio_sessoes=rateio_sessoes,
            rateio_receita=rateio_receita
        )
    
    def calcular_cv_total_tdabc(self, mes: int) -> float:
        """
        Calcula o CV Total para o TDABC.
        
        IMPORTANTE: O TDABC do Excel usa uma definição diferente de CV
        que inclui TODOS os custos operacionais que variam com volume:
        - Folha Fisioterapeutas
        - Folha Proprietários (Pró-labore)  
        - Folha CLT + Encargos
        - Simples Nacional
        - Taxa Cartão
        - Materiais/Compras
        
        Isso é diferente do CV tradicional do DRE!
        Fonte: Planilha TDABC linhas 114-122
        """
        dre = self.calcular_dre()
        
        # Componentes do CV TDABC (todos os custos operacionais)
        cv_tdabc = 0.0
        
        # Folha de pagamento (tratada como CV no TDABC)
        cv_tdabc += abs(dre.get("(-) Folha Fisioterapeutas", [0]*12)[mes])
        cv_tdabc += abs(dre.get("(-) Folha Proprietários", [0]*12)[mes])
        cv_tdabc += abs(dre.get("(-) Folha CLT + Encargos", [0]*12)[mes])
        
        # Impostos e taxas
        cv_tdabc += abs(dre.get("(-) Simples Nacional", [0]*12)[mes])
        cv_tdabc += abs(dre.get("(-) Taxa Cartão", [0]*12)[mes])
        
        # Custos Variáveis (Materiais e outras despesas variáveis cadastradas)
        cv_tdabc += abs(dre.get("Total Custos Variáveis", [0]*12)[mes])
        
        return cv_tdabc
    
    def calcular_lucro_abc_servico_mes(self, servico: str, mes: int) -> LucroABCServico:
        """
        Calcula lucro ABC de um serviço em um mês.
        Fórmula TDABC linhas 136-141:
        
        Lucro ABC = Receita - CV Rateado - Overhead ABC
        
        Onde CV inclui: Folha + Impostos + Materiais (definição TDABC)
        """
        # Receita do serviço
        receita = self.calcular_receita_servico_mes(servico, mes)
        
        # Receita total
        total_receita = sum(self.calcular_receita_servico_mes(s, mes) for s in self.servicos)
        
        # Custos variáveis TDABC (inclui folha + impostos + materiais)
        cv_total_tdabc = self.calcular_cv_total_tdabc(mes)
        
        if total_receita > 0:
            cv_rateado = (receita / total_receita) * cv_total_tdabc
        else:
            cv_rateado = 0.0
        
        # Overhead rateado (TDABC - custos indiretos)
        rateio = self.calcular_rateio_servico_mes(servico, mes)
        overhead = rateio.overhead_total
        
        return LucroABCServico(
            mes=mes,
            servico=servico,
            receita=receita,
            custos_variaveis_rateados=cv_rateado,
            overhead_rateado=overhead
        )
    
    def calcular_tdabc_mes(self, mes: int) -> AnaliseTDABCMes:
        """Calcula análise TDABC completa para um mês"""
        subtotais = self.calcular_subtotais_direcionadores(mes)
        
        analise = AnaliseTDABCMes(
            mes=mes,
            ano=2026,
            subtotal_m2=subtotais["m2"],
            subtotal_sessoes=subtotais["sessoes"],
            subtotal_receita=subtotais["receita"]
        )
        
        # Calcular para cada serviço
        for servico in self.servicos:
            analise.rateios[servico] = self.calcular_rateio_servico_mes(servico, mes)
            analise.lucros[servico] = self.calcular_lucro_abc_servico_mes(servico, mes)
        
        return analise
    
    def calcular_tdabc_anual(self) -> AnaliseTDABCAnual:
        """Calcula análise TDABC para o ano inteiro"""
        analise = AnaliseTDABCAnual(ano=2026)
        
        for mes in range(12):
            analise.meses.append(self.calcular_tdabc_mes(mes))
        
        return analise
    
    def get_resumo_tdabc(self) -> Dict:
        """Retorna resumo do TDABC para exibição"""
        analise = self.calcular_tdabc_anual()
        
        # Ranking anual
        ranking = analise.get_ranking_anual()
        
        return {
            "overhead_total": analise.overhead_total,
            "lucro_total": analise.lucro_total,
            "ranking": ranking,
            "meses": [
                {
                    "mes": m.mes + 1,
                    "nome_mes": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"][m.mes],
                    "overhead": m.overhead_total,
                    "lucro": m.lucro_total,
                    "subtotal_m2": m.subtotal_m2,
                    "subtotal_sessoes": m.subtotal_sessoes,
                    "subtotal_receita": m.subtotal_receita,
                    "servicos": {
                        s: {
                            "receita": l.receita,
                            "cv_rateado": l.custos_variaveis_rateados,
                            "overhead": l.overhead_rateado,
                            "lucro_abc": l.lucro_abc,
                            "margem_abc": l.margem_abc
                        }
                        for s, l in m.lucros.items()
                    }
                }
                for m in analise.meses
            ]
        }
    
    def calcular_pe_mes(self, mes: int) -> AnalisePontoEquilibrioMes:
        """
        Calcula análise de Ponto de Equilíbrio para um mês específico.
        Integra dados do DRE e Taxa de Ocupação.
        """
        # Calcula DRE para obter dados financeiros
        dre = self.calcular_dre()
        
        # Dados do DRE
        receita_liquida = dre["Receita Líquida"][mes]
        custos_variaveis = abs(dre["Total Custos Variáveis"][mes])
        margem_contribuicao = dre["Margem de Contribuição"][mes]
        custos_fixos = abs(dre["Total Custos Fixos"][mes])
        ebitda = dre["EBITDA"][mes]
        
        # Dados de ocupação
        ocupacao = self.calcular_ocupacao_mes(mes)
        
        # Custo de ociosidade
        custo_infra = self.calcular_custo_infraestrutura_mes()
        custo_ociosidade = self.calcular_custo_ociosidade_mes(mes)
        
        analise = AnalisePontoEquilibrioMes(
            mes=mes,
            ano=2026,
            receita_liquida=receita_liquida,
            custos_variaveis=custos_variaveis,
            margem_contribuicao=margem_contribuicao,
            custos_fixos=custos_fixos,
            ebitda=ebitda,
            total_sessoes=ocupacao.total_sessoes,
            # Usar capacidade de PROFISSIONAIS (como Excel) ao invés de salas
            capacidade_horas=ocupacao.capacidade_profissional,
            demanda_horas=ocupacao.demanda_profissional,
            horas_ociosas=ocupacao.horas_ociosas_profissional,
            custo_infraestrutura=custo_infra,
            custo_ociosidade=custo_ociosidade
        )
        
        return analise
    
    def calcular_pe_anual(self) -> AnalisePontoEquilibrioAnual:
        """Calcula análise de Ponto de Equilíbrio para o ano inteiro"""
        analise = AnalisePontoEquilibrioAnual(ano=2026)
        
        for mes in range(12):
            analise.meses.append(self.calcular_pe_mes(mes))
        
        return analise
    
    def get_resumo_pe(self) -> Dict:
        """Retorna resumo do Ponto de Equilíbrio para exibição"""
        analise = self.calcular_pe_anual()
        
        # Calcular TDABC para overhead
        tdabc = self.calcular_tdabc_anual()
        
        # Calcular overhead por mês
        overheads = []
        for mes in range(12):
            tdabc_mes = self.calcular_tdabc_mes(mes)
            overheads.append(tdabc_mes.subtotal_m2 + tdabc_mes.subtotal_sessoes + tdabc_mes.subtotal_receita)
        
        return {
            "receita_total": analise.receita_total,
            "ebitda_total": analise.ebitda_total,
            "pe_contabil_total": analise.pe_contabil_total,
            "pe_contabil_medio": analise.pe_contabil_medio,
            "margem_seguranca_total": analise.margem_seguranca_total,
            "margem_seguranca_media_pct": analise.margem_seguranca_media_pct,
            "gao_medio": analise.gao_medio,
            "lucro_por_sessao_medio": analise.lucro_por_sessao_medio,
            "total_sessoes": analise.total_sessoes,
            "custo_ociosidade_total": analise.custo_ociosidade_total,
            "overhead_abc_total": sum(overheads),
            "custos_fixos_total": analise.custos_fixos_total,
            "status_predominante": analise.status_risco_predominante,
            "meses_criticos": analise.meses_criticos,
            "meses": [
                {
                    "mes": m.mes + 1,
                    "nome_mes": ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", 
                                 "Jul", "Ago", "Set", "Out", "Nov", "Dez"][m.mes],
                    "receita_liquida": m.receita_liquida,
                    "custos_variaveis": m.custos_variaveis,
                    "margem_contribuicao": m.margem_contribuicao,
                    "pct_mc": m.pct_margem_contribuicao,
                    "custos_fixos": m.custos_fixos,
                    "overhead_abc": overheads[m.mes],
                    "ebitda": m.ebitda,
                    "total_sessoes": m.total_sessoes,
                    "capacidade_horas": m.capacidade_horas,
                    "demanda_horas": m.demanda_horas,
                    "horas_ociosas": m.horas_ociosas,
                    "taxa_ocupacao": m.demanda_horas / m.capacidade_horas if m.capacidade_horas > 0 else 0,
                    "custo_ociosidade": m.custo_ociosidade,
                    "pe_contabil": m.pe_contabil,
                    "pe_com_ociosidade": m.pe_com_ociosidade,
                    "pe_sessoes": m.pe_sessoes,
                    "pe_horas": m.pe_horas,
                    "pe_taxa_ocupacao": m.pe_taxa_ocupacao,
                    "margem_seguranca_valor": m.margem_seguranca_valor,
                    "margem_seguranca_pct": m.margem_seguranca_pct,
                    "gao": m.gao,
                    "lucro_por_sessao": m.lucro_por_sessao,
                    "status": m.status_risco,
                    "status_emoji": m.status_emoji,
                    "status_texto": m.status_texto
                }
                for m in analise.meses
            ]
        }
    
    def calcular_pe_por_servico(self) -> List[PEPorServico]:
        """
        Calcula Ponto de Equilíbrio por serviço (integração TDABC).
        Fonte: Planilha 'Ponto de Equilibrio' linhas 39-47.
        
        Fórmula: PE por Serviço = CF Rateado / %MC Global
        """
        # Calcular TDABC anual
        tdabc = self.calcular_tdabc_anual()
        
        # DRE para calcular MC Global
        dre = self.calcular_dre()
        
        # MC Global (média anual)
        # MC = Receita Líquida - CV
        # %MC = MC / Receita Líquida
        receita_liquida_total = sum(dre["Receita Líquida"])
        cv_total_dre = abs(sum(dre["Total Custos Variáveis"]))
        mc_total = receita_liquida_total - cv_total_dre
        pct_mc_global = mc_total / receita_liquida_total if receita_liquida_total > 0 else 0.95
        
        # Receita total para calcular mix (usando TDABC)
        receita_total = sum(
            tdabc.get_receita_servico(srv) 
            for srv in self.servicos
        )
        
        # Custos fixos totais para ratear
        custos_fixos_total = abs(sum(dre["Total Custos Fixos"]))
        
        resultados = []
        
        for servico in self.servicos:
            # Dados de receita e volume (usando TDABC)
            receita_anual = tdabc.get_receita_servico(servico)
            sessoes_ano = sum(self.calcular_sessoes_mes(servico, m) for m in range(12))
            ticket_medio = receita_anual / sessoes_ano if sessoes_ano > 0 else 0
            
            # Mix de participação
            pct_mix = receita_anual / receita_total if receita_total > 0 else 0
            
            # Dados do TDABC
            lucro_abc = tdabc.get_lucro_servico(servico)
            margem_abc = tdabc.get_margem_servico(servico)
            
            # Custos rateados proporcionalmente à receita
            cv_rateado = pct_mix * cv_total_dre
            cf_rateado = pct_mix * custos_fixos_total
            
            # Overhead ABC (do TDABC) - soma dos rateios mensais
            overhead = 0.0
            for mes_tdabc in tdabc.meses:
                rateio = mes_tdabc.rateios.get(servico)
                if rateio:
                    overhead += rateio.overhead_total
            
            pe_servico = PEPorServico(
                servico=servico,
                receita_anual=receita_anual,
                sessoes_ano=sessoes_ano,
                ticket_medio=ticket_medio,
                lucro_abc=lucro_abc,
                margem_abc=margem_abc,
                pct_mix=pct_mix,
                custos_variaveis_rateados=cv_rateado,
                custos_fixos_rateados=cf_rateado,
                overhead_abc=overhead,
                pct_mc_global=pct_mc_global
            )
            
            resultados.append(pe_servico)
        
        # Ordenar por receita (maior primeiro)
        resultados.sort(key=lambda x: x.receita_anual, reverse=True)
        
        return resultados
    
    def get_resumo_pe_por_servico(self) -> Dict:
        """Retorna resumo do PE por serviço para UI"""
        pe_servicos = self.calcular_pe_por_servico()
        
        # Totais
        receita_total = sum(p.receita_anual for p in pe_servicos)
        sessoes_total = sum(p.sessoes_ano for p in pe_servicos)
        lucro_total = sum(p.lucro_abc for p in pe_servicos)
        cf_total = sum(p.custos_fixos_rateados for p in pe_servicos)
        pe_total = sum(p.pe_receita for p in pe_servicos)
        
        return {
            "receita_total": receita_total,
            "sessoes_total": sessoes_total,
            "lucro_total": lucro_total,
            "cf_total": cf_total,
            "pe_total": pe_total,
            "servicos_acima_pe": sum(1 for p in pe_servicos if p.receita_anual >= p.pe_receita),
            "servicos_abaixo_pe": sum(1 for p in pe_servicos if p.receita_anual < p.pe_receita),
            "servicos": [
                {
                    "servico": p.servico,
                    "receita_anual": p.receita_anual,
                    "sessoes_ano": p.sessoes_ano,
                    "ticket_medio": p.ticket_medio,
                    "lucro_abc": p.lucro_abc,
                    "margem_abc": p.margem_abc,
                    "pct_mix": p.pct_mix,
                    "cf_rateado": p.custos_fixos_rateados,
                    "pe_receita": p.pe_receita,
                    "pe_sessoes": p.pe_sessoes,
                    "margem_seguranca_pct": p.margem_seguranca_pct,
                    "folga_sessoes": p.folga_sessoes,
                    "status": p.status
                }
                for p in pe_servicos
            ]
        }
    
    # ============================================
    # CÁLCULOS DE DEDUÇÕES
    # ============================================
    
    def calcular_taxa_cartao_mes(self, receita_mes: float) -> float:
        """Calcula taxa de cartão sobre a receita"""
        # Receita por forma de pagamento
        receita_credito = receita_mes * self.pagamento.cartao_credito
        receita_debito = receita_mes * self.pagamento.cartao_debito
        
        # Taxa sobre cada forma
        taxa_credito = receita_credito * self.macro.taxa_cartao_credito
        taxa_debito = receita_debito * self.macro.taxa_cartao_debito
        
        # Taxa de antecipação
        valor_antecipado = receita_credito * self.pagamento.pct_antecipacao
        taxa_antecipacao = valor_antecipado * self.macro.taxa_antecipacao
        
        return taxa_credito + taxa_debito + taxa_antecipacao
    
    def calcular_simples_nacional(self, receita_12_meses: float, receita_mes: float) -> float:
        """Calcula imposto Simples Nacional (anexo III - serviços)"""
        # Se não tem receita, não tem imposto
        if receita_12_meses <= 0 or receita_mes <= 0:
            return 0.0
        
        # Tabela Simples Nacional Anexo III (simplificada)
        if receita_12_meses <= 180000:
            aliquota = 0.06
            deducao = 0
        elif receita_12_meses <= 360000:
            aliquota = 0.112
            deducao = 9360
        elif receita_12_meses <= 720000:
            aliquota = 0.135
            deducao = 17640
        elif receita_12_meses <= 1800000:
            aliquota = 0.16
            deducao = 35640
        elif receita_12_meses <= 3600000:
            aliquota = 0.21
            deducao = 125640
        else:
            aliquota = 0.33
            deducao = 648000
        
        # Alíquota efetiva
        aliquota_efetiva = (receita_12_meses * aliquota - deducao) / receita_12_meses
        
        return receita_mes * aliquota_efetiva
    
    def calcular_deducoes_total(self) -> Dict[str, List[float]]:
        """Calcula todas as deduções sobre receita (respeita regime tributário)"""
        if not self.receita_bruta:
            self.calcular_receita_bruta_total()
        
        receitas_mensais = self.receita_bruta.get("Total", [0]*12)
        
        # Pega impostos baseado no regime tributário selecionado
        impostos_regime = self.get_impostos_para_dre_anual()
        
        resultado = {
            "Simples Nacional": [],  # Mantém nome para compatibilidade (mas pode ser PF também)
            "Taxa Cartão": [],
            "Total Deduções": []
        }
        
        for mes in range(12):
            receita_mes = receitas_mensais[mes]
            
            # Imposto conforme regime tributário (PJ ou PF)
            imposto = impostos_regime[mes]
            resultado["Simples Nacional"].append(imposto)
            
            # Taxa cartão
            taxa_cartao = self.calcular_taxa_cartao_mes(receita_mes)
            resultado["Taxa Cartão"].append(taxa_cartao)
            
            # Total
            resultado["Total Deduções"].append(imposto + taxa_cartao)
        
        self.deducoes = resultado
        return resultado
    
    # ============================================
    # CÁLCULOS DE CUSTOS E DESPESAS
    # ============================================
    
    def calcular_custos_variaveis(self) -> Dict[str, List[float]]:
        """
        Calcula custos variáveis baseado nas despesas cadastradas pelo usuário.
        Inclui apenas despesas com tipo_despesa = "variavel".
        """
        if not self.receita_bruta:
            self.calcular_receita_bruta_total()
        
        receitas = self.receita_bruta.get("Total", [0]*12)
        
        # Calcula sessões por mês
        sessoes_por_mes = []
        for mes in range(12):
            sessoes = sum(self.calcular_sessoes_mes(srv, mes) for srv in self.servicos)
            sessoes_por_mes.append(sessoes)
        
        resultado = {}
        
        # Índices para cálculo de despesas
        indices = {
            "ipca": self.macro.ipca,
            "igpm": self.macro.igpm,
            "tarifas": self.macro.reajuste_tarifas,
            "contratos": self.macro.reajuste_contratos,
            "dissidio": self.macro.dissidio,
            "nenhum": 0
        }
        
        # Despesas variáveis cadastradas pelo usuário
        for nome, desp in self.despesas_fixas.items():
            if not desp.ativa:
                continue
            if desp.tipo_despesa != "variavel":
                continue
            
            valores_mes = []
            for mes in range(12):
                valor = desp.calcular_valor_mes(
                    mes=mes,
                    indices=indices,
                    receita_mes=receitas[mes],
                    sessoes_mes=sessoes_por_mes[mes]
                )
                valores_mes.append(valor)
            
            resultado[nome] = valores_mes
        
        # Total Custos Variáveis
        resultado["Total Custos Variáveis"] = [0.0] * 12
        for mes in range(12):
            total = sum(resultado[key][mes] for key in resultado if key != "Total Custos Variáveis")
            resultado["Total Custos Variáveis"][mes] = total
        
        self.custos = resultado
        return resultado
    
    def calcular_despesas_fixas(self, despesas_base: Dict[str, float] = None) -> Dict[str, List[float]]:
        """
        Calcula despesas fixas com reajustes usando a estrutura de DespesaFixa.
        EXCLUI despesas variáveis (que são calculadas em calcular_custos_variaveis).
        """
        resultado = {}
        
        # Nome do cenário atual
        cenario_nome = self.cenario.nome if hasattr(self, 'cenario') else "Conservador"
        
        # Índices para cálculo
        indices = {
            "ipca": self.macro.ipca,
            "igpm": self.macro.igpm,
            "tarifas": self.macro.reajuste_tarifas,
            "contratos": self.macro.reajuste_contratos,
            "dissidio": self.macro.dissidio,
            "nenhum": 0
        }
        
        for nome, desp in self.despesas_fixas.items():
            if not desp.ativa:
                continue
            
            # IGNORA despesas variáveis (são calculadas em calcular_custos_variaveis)
            if desp.tipo_despesa == "variavel":
                continue
                
            valores_mes = []
            
            # Ajuste do cenário para esta despesa (valor absoluto configurado pelo usuário)
            ajuste_despesa = self.get_ajuste_despesa(cenario_nome, nome) if hasattr(self, 'get_ajuste_despesa') else 0
            
            # Fator global do cenário (multiplicador: 1.15 para Pessimista, 0.95 para Otimista)
            fator_cenario = self.cenario.fator_despesas if hasattr(self, 'cenario') else 1.0
            
            for mes in range(12):
                # Usa o método calcular_valor_mes que já trata sazonalidade e reajustes
                valor = desp.calcular_valor_mes(
                    mes=mes,
                    indices=indices,
                    receita_mes=0,  # Não usado para despesas fixas
                    sessoes_mes=0   # Não usado para despesas fixas
                )
                # Aplica fator do cenário (multiplicador) + ajuste individual (absoluto)
                valor_ajustado = (valor * fator_cenario) + ajuste_despesa
                valores_mes.append(valor_ajustado)
            
            resultado[nome] = valores_mes
        
        # Total - apenas despesas fixas ativas
        resultado["Total Despesas Fixas"] = []
        for mes in range(12):
            total = sum(
                resultado[d][mes] 
                for d in resultado.keys() 
                if d != "Total Despesas Fixas"
            )
            resultado["Total Despesas Fixas"].append(total)
        
        self.despesas = resultado
        return resultado
    
    # ============================================
    # DRE COMPLETO
    # ============================================
    
    def calcular_dre(self, despesas_base: Dict[str, float] = None, 
                     custo_pessoal_mensal: float = None) -> Dict[str, List[float]]:
        """
        Calcula DRE completo
        """
        # Usa custo de pessoal do motor se não informado
        if custo_pessoal_mensal is None:
            custo_pessoal_mensal = self.custo_pessoal_mensal
        
        # Calcula componentes
        self.calcular_receita_bruta_total()
        self.calcular_deducoes_total()
        self.calcular_custos_variaveis()
        self.calcular_despesas_fixas()
        
        dre = {}
        
        # Receita Bruta por serviço
        for servico in self.servicos:
            dre[servico] = self.receita_bruta[servico]
        
        dre["Receita Bruta Total"] = self.receita_bruta["Total"]
        
        # Deduções - Nome do imposto conforme regime tributário
        regime = self.premissas_folha.regime_tributario
        if "Simples" in regime or "PJ" in regime:
            nome_imposto = "(-) Simples Nacional"
        else:
            nome_imposto = "(-) Carnê Leão (PF)"
        
        dre[nome_imposto] = [-v for v in self.deducoes["Simples Nacional"]]
        dre["(-) Taxa Cartão"] = [-v for v in self.deducoes["Taxa Cartão"]]
        dre["Total Deduções"] = [-v for v in self.deducoes["Total Deduções"]]
        
        # Receita Líquida
        dre["Receita Líquida"] = [
            dre["Receita Bruta Total"][m] - self.deducoes["Total Deduções"][m]
            for m in range(12)
        ]
        
        # Custos Variáveis - Detalhamento
        # Adiciona TODAS as despesas variáveis cadastradas pelo usuário
        for nome, valores in self.custos.items():
            if nome != "Total Custos Variáveis":
                dre[f"(-) {nome}"] = [-v for v in valores]
        
        dre["Total Custos Variáveis"] = [-v for v in self.custos["Total Custos Variáveis"]]
        
        # Margem de Contribuição
        dre["Margem de Contribuição"] = [
            dre["Receita Líquida"][m] + dre["Total Custos Variáveis"][m]
            for m in range(12)
        ]
        
        # ========== CUSTO DE PESSOAL (CÁLCULO DINÂMICO) ==========
        # Calcula baseado em atendimentos, comissões e folha real
        custo_pessoal = self.calcular_custo_pessoal_dre()
        
        # Detalhamento por componente (para visualização)
        dre["(-) Folha Fisioterapeutas"] = [-v for v in custo_pessoal["Folha Fisioterapeutas"]]
        dre["(-) Folha Proprietários"] = [-v for v in custo_pessoal["Folha Proprietários"]]
        dre["(-) Pró-Labore"] = [-v for v in custo_pessoal["Pró-Labore"]]
        dre["(-) Folha CLT + Encargos"] = [-v for v in custo_pessoal["Folha CLT + Encargos"]]
        
        # Subtotal Pessoal (para compatibilidade e totalização)
        dre["Subtotal Pessoal"] = [-v for v in custo_pessoal["Total Custo Pessoal"]]
        
        # Despesas Fixas (excluindo Compras que já está em Custos Variáveis como Materiais)
        for despesa, valores in self.despesas.items():
            if "Total" not in despesa and despesa != "Compras":
                dre[f"(-) {despesa}"] = [-v for v in valores]
        
        # Recalcular Total Despesas Fixas sem Compras
        total_desp_fixas = [0.0] * 12
        for despesa, valores in self.despesas.items():
            if "Total" not in despesa and despesa != "Compras":
                for m in range(12):
                    total_desp_fixas[m] += valores[m]
        dre["Total Despesas Fixas"] = [-v for v in total_desp_fixas]
        
        # Total Custos Fixos (Pessoal + Despesas Operacionais)
        dre["Total Custos Fixos"] = [
            dre["Subtotal Pessoal"][m] + dre["Total Despesas Fixas"][m]
            for m in range(12)
        ]
        
        # EBITDA
        dre["EBITDA"] = [
            dre["Margem de Contribuição"][m] + dre["Total Custos Fixos"][m]
            for m in range(12)
        ]
        
        # ========== RESULTADO FINANCEIRO ==========
        # Calcula despesas e receitas financeiras
        resultado_financeiro = self.calcular_resultado_financeiro()
        
        # Despesas Financeiras
        dre["(-) Juros Novos Investimentos"] = [-v for v in resultado_financeiro["juros_investimentos"]]
        dre["(-) Juros Financ. Existentes"] = [-v for v in resultado_financeiro["juros_financiamentos"]]
        dre["(-) Juros Cheque Especial"] = [-v for v in resultado_financeiro["juros_cheque"]]
        dre["Total Despesas Financeiras"] = [-v for v in resultado_financeiro["total_despesas"]]
        
        # Receitas Financeiras
        dre["(+) Rendimentos Aplicações"] = resultado_financeiro["rendimentos_aplicacoes"]
        dre["Total Receitas Financeiras"] = resultado_financeiro["total_receitas"]
        
        # Resultado Financeiro Líquido
        dre["Resultado Financeiro Líquido"] = resultado_financeiro["resultado_liquido"]
        
        # Resultado Antes do IR
        dre["Resultado Antes IR"] = [
            dre["EBITDA"][m] + dre["Resultado Financeiro Líquido"][m]
            for m in range(12)
        ]
        
        # Resultado Líquido (igual ao Resultado Antes IR para Simples Nacional)
        dre["Resultado Líquido"] = dre["Resultado Antes IR"].copy()
        
        # ========== DESTINAÇÃO DOS RESULTADOS (somente PJ e se flag ativo) ==========
        regime = self.premissas_folha.regime_tributario
        is_pj = "Simples" in regime or "PJ" in regime
        
        pd = self.premissas_dividendos
        # Só calcula dividendos se: é PJ, flag distribuir=True e mostrar_no_dre=True
        if is_pj and pd.distribuir and pd.mostrar_no_dre:
            resultado_liquido = dre["Resultado Líquido"]
            
            # Reserva Legal (5% do resultado positivo)
            reserva_legal = [max(0, rl * pd.pct_reserva_legal) if rl > 0 else 0 for rl in resultado_liquido]
            dre["(-) Reserva Legal"] = [-v for v in reserva_legal]
            
            # Reserva para Investimentos
            reserva_investimento = [max(0, rl * pd.pct_reserva_investimento) if rl > 0 else 0 for rl in resultado_liquido]
            dre["(-) Reserva Investimentos"] = [-v for v in reserva_investimento]
            
            # Lucro Distribuível mensal
            lucro_distribuivel = []
            for m in range(12):
                if resultado_liquido[m] > 0:
                    lucro = resultado_liquido[m] - reserva_legal[m] - reserva_investimento[m]
                else:
                    lucro = 0
                lucro_distribuivel.append(max(0, lucro))
            
            # Calcular dividendos por período e cronograma de pagamento
            periodos = pd.get_periodos()
            cronograma = [0.0] * 12
            
            for inicio, fim in periodos:
                lucro_periodo = sum(lucro_distribuivel[inicio-1:fim])
                dividendo = lucro_periodo * pd.pct_distribuir
                mes_pgto = fim - 1  # índice 0-based
                cronograma[mes_pgto] = dividendo
            
            # Dividendos Distribuídos (cronograma de pagamento)
            dre["(-) Dividendos Distribuídos"] = [-v for v in cronograma]
            
            # Lucro no Período (Retido)
            dre["Lucro no Período"] = [
                dre["Resultado Líquido"][m] + dre["(-) Reserva Legal"][m] + 
                dre["(-) Reserva Investimentos"][m] + dre["(-) Dividendos Distribuídos"][m]
                for m in range(12)
            ]
        
        self.dre = dre
        return dre
    
    # ============================================
    # MÓDULO FINANCEIRO - CÁLCULOS
    # ============================================
    
    def calcular_resultado_financeiro(self) -> Dict[str, List[float]]:
        """
        Calcula resultado financeiro mensal consolidando todas as fontes.
        
        IMPORTANTE: Os rendimentos de aplicações são calculados de forma independente
        usando a mesma lógica do Fluxo de Caixa, mas sem criar dependência circular.
        
        Returns:
            Dict com juros_investimentos, juros_financiamentos, juros_cheque,
            rendimentos_aplicacoes, total_despesas, total_receitas, resultado_liquido
        """
        pf = self.premissas_financeiras
        
        # Inicializa listas
        juros_investimentos = [0.0] * 12
        juros_financiamentos = [0.0] * 12
        juros_cheque = [0.0] * 12
        rendimentos_aplicacoes = [0.0] * 12
        
        # 1. Juros de Novos Investimentos
        for inv in pf.investimentos:
            if inv.ativo:
                for mes in range(1, 13):
                    juros_investimentos[mes - 1] += inv.calcular_juros_mes(mes)
        
        # 2. Juros de Financiamentos Existentes
        for fin in pf.financiamentos:
            if fin.ativo:
                for mes in range(1, 13):
                    juros_financiamentos[mes - 1] += fin.calcular_juros_mes(mes)
        
        # 3. Juros de Cheque Especial
        for mes in range(1, 13):
            juros_cheque[mes - 1] = pf.cheque_especial.calcular_juros_mes(mes)
        
        # 4. Rendimentos de Aplicações
        # Se o FC já foi calculado, usa os valores dele (mais precisos)
        # Caso contrário, calcula de forma simplificada
        if hasattr(self, 'fluxo_caixa') and self.fluxo_caixa and "(+) Rendimentos Aplicações" in self.fluxo_caixa:
            rendimentos_aplicacoes = self.fluxo_caixa.get("(+) Rendimentos Aplicações", [0.0] * 12).copy()
        else:
            # Cálculo simplificado: rendimentos baseados no saldo com aportes estimados do excesso de caixa
            # Essa lógica espelha o que o FC faz, mas sem precisar do FC completo
            taxa_mensal = pf.aplicacoes.taxa_mensal
            saldo_aplicacoes = pf.aplicacoes.saldo_inicial
            saldo_minimo = self.premissas_fc.saldo_minimo
            caixa_inicial = self.premissas_fc.caixa_inicial
            
            # Calcula recebimentos e pagamentos para estimar o fluxo
            try:
                recebimentos = self.calcular_recebimentos_totais()
                total_recebimentos = recebimentos.get("Total Recebimentos", [0.0] * 12)
            except:
                total_recebimentos = [0.0] * 12
            
            try:
                # Estima saídas totais (sem dividendos para evitar recursão)
                saidas_estimadas = [0.0] * 12
                folha = self.calcular_pagamentos_folha_fc()
                impostos = self.calcular_pagamentos_impostos_fc()
                despesas = self.calcular_pagamentos_despesas_fc()
                financeiros = self.calcular_pagamentos_financeiros_fc()
                
                for m in range(12):
                    for valores in folha.values():
                        saidas_estimadas[m] += valores[m]
                    for valores in impostos.values():
                        saidas_estimadas[m] += valores[m]
                    for valores in despesas.values():
                        saidas_estimadas[m] += valores[m]
                    for valores in financeiros.values():
                        saidas_estimadas[m] += valores[m]
            except:
                saidas_estimadas = [0.0] * 12
            
            saldo_caixa = caixa_inicial
            
            for mes in range(12):
                # Rendimento do mês sobre saldo de aplicações do início do mês
                rendimentos_aplicacoes[mes] = saldo_aplicacoes * taxa_mensal
                
                # Estima variação do caixa
                variacao = total_recebimentos[mes] - saidas_estimadas[mes] + rendimentos_aplicacoes[mes]
                saldo_projetado = saldo_caixa + variacao
                
                # Se saldo_minimo > 0, simula aportes/resgates
                if saldo_minimo > 0:
                    excesso = saldo_projetado - saldo_minimo
                    if excesso > 0:
                        # Aporte do excesso em aplicações
                        saldo_aplicacoes += excesso
                        saldo_caixa = saldo_minimo
                    elif excesso < 0 and saldo_aplicacoes > 0:
                        # Resgate de aplicações
                        resgate = min(abs(excesso), saldo_aplicacoes)
                        saldo_aplicacoes -= resgate
                        saldo_caixa = saldo_projetado + resgate
                    else:
                        saldo_caixa = saldo_projetado
                else:
                    saldo_caixa = saldo_projetado
                    # Sem política de saldo mínimo, rendimento é só sobre saldo inicial
                    saldo_aplicacoes = saldo_aplicacoes * (1 + taxa_mensal)
        
        # Totais
        total_despesas = [
            juros_investimentos[m] + juros_financiamentos[m] + juros_cheque[m]
            for m in range(12)
        ]
        
        total_receitas = rendimentos_aplicacoes.copy()
        
        # Resultado líquido = Receitas - Despesas
        resultado_liquido = [
            total_receitas[m] - total_despesas[m]
            for m in range(12)
        ]
        
        return {
            "juros_investimentos": juros_investimentos,
            "juros_financiamentos": juros_financiamentos,
            "juros_cheque": juros_cheque,
            "rendimentos_aplicacoes": rendimentos_aplicacoes,
            "total_despesas": total_despesas,
            "total_receitas": total_receitas,
            "resultado_liquido": resultado_liquido
        }
    
    def get_resumo_financeiro(self) -> Dict:
        """
        Retorna resumo do módulo financeiro para exibição.
        """
        pf = self.premissas_financeiras
        resultado = self.calcular_resultado_financeiro()
        
        # Totais anuais
        total_juros_inv = sum(resultado["juros_investimentos"])
        total_juros_fin = sum(resultado["juros_financiamentos"])
        total_juros_cheque = sum(resultado["juros_cheque"])
        total_rendimentos = sum(resultado["rendimentos_aplicacoes"])
        total_despesas = sum(resultado["total_despesas"])
        total_receitas = sum(resultado["total_receitas"])
        resultado_liq = sum(resultado["resultado_liquido"])
        
        # Resumo de investimentos
        investimentos_ativos = [inv for inv in pf.investimentos if inv.ativo]
        total_investimentos = sum(inv.valor_total for inv in investimentos_ativos)
        total_entradas = sum(inv.entrada for inv in investimentos_ativos)
        total_financiado = sum(inv.valor_financiado for inv in investimentos_ativos)
        
        # Resumo de financiamentos
        financiamentos_ativos = [fin for fin in pf.financiamentos if fin.ativo]
        total_saldo_devedor = sum(fin.saldo_devedor for fin in financiamentos_ativos)
        
        # Aplicações
        evolucao = pf.aplicacoes.calcular_evolucao_anual()
        saldo_final_aplicacoes = evolucao[-1]["saldo_final"] if evolucao else 0
        
        return {
            "investimentos": {
                "quantidade": len(investimentos_ativos),
                "valor_total": total_investimentos,
                "entrada": total_entradas,
                "financiado": total_financiado,
                "juros_ano": total_juros_inv
            },
            "financiamentos": {
                "quantidade": len(financiamentos_ativos),
                "saldo_devedor": total_saldo_devedor,
                "juros_ano": total_juros_fin
            },
            "cheque_especial": {
                "juros_ano": total_juros_cheque
            },
            "aplicacoes": {
                "saldo_inicial": pf.aplicacoes.saldo_inicial,
                "saldo_final": saldo_final_aplicacoes,
                "rendimentos_ano": total_rendimentos,
                "taxa_mensal": pf.aplicacoes.taxa_mensal
            },
            "resumo": {
                "total_despesas_financeiras": total_despesas,
                "total_receitas_financeiras": total_receitas,
                "resultado_financeiro_liquido": resultado_liq
            },
            "mensal": resultado
        }
    
    # ============================================
    # MÓDULO DIVIDENDOS
    # ============================================
    
    def calcular_dividendos(self) -> Dict:
        """
        Calcula distribuição de dividendos baseado no resultado líquido do DRE.
        
        Retorna:
            - resultado_liquido_mensal: [12 meses] do DRE
            - reserva_legal: [12 meses] (5% do resultado)
            - reserva_investimento: [12 meses] (% configurável)
            - lucro_distribuivel: [12 meses] (resultado - reservas)
            - dividendos_periodo: [(periodo, lucro_acum, dividendo, mes_pgto)]
            - dividendos_por_socio: {nome: {periodo: valor}}
            - cronograma: [12 meses] valores pagos
            - indicadores: {payout, div_capital, lucro_retido}
        """
        # Garante DRE calculado
        if not self.dre:
            self.calcular_dre()
        
        pd = self.premissas_dividendos
        
        # Se distribuir=False, retorna tudo zerado
        if not pd.distribuir:
            return {
                "resultado_liquido": self.dre.get("Resultado Líquido", [0.0] * 12),
                "reserva_legal": [0.0] * 12,
                "reserva_investimento": [0.0] * 12,
                "lucro_distribuivel": [0.0] * 12,
                "dividendos_periodo": [],
                "dividendos_por_socio": {},
                "cronograma": [0.0] * 12,
                "indicadores": {
                    "payout": 0,
                    "dividendo_por_capital": 0,
                    "lucro_retido": sum(self.dre.get("Resultado Líquido", [0.0] * 12)),
                    "total_reserva_legal": 0,
                    "total_reserva_investimento": 0,
                    "total_lucro_distribuivel": 0,
                    "total_dividendos": 0,
                    "total_resultado_liquido": sum(self.dre.get("Resultado Líquido", [0.0] * 12))
                },
                "premissas": {
                    "pct_reserva_legal": pd.pct_reserva_legal,
                    "pct_reserva_investimento": pd.pct_reserva_investimento,
                    "frequencia": pd.frequencia,
                    "pct_distribuir": pd.pct_distribuir,
                    "distribuir": pd.distribuir
                }
            }
        
        # 1. Resultado Líquido mensal do DRE
        resultado_liquido = self.dre.get("Resultado Líquido", [0.0] * 12)
        
        # 2. Reservas mensais
        reserva_legal = [max(0, rl * pd.pct_reserva_legal) for rl in resultado_liquido]
        reserva_investimento = [max(0, rl * pd.pct_reserva_investimento) for rl in resultado_liquido]
        
        # 3. Lucro Distribuível mensal (só se resultado positivo)
        lucro_distribuivel = []
        for m in range(12):
            if resultado_liquido[m] > 0:
                lucro = resultado_liquido[m] - reserva_legal[m] - reserva_investimento[m]
            else:
                lucro = 0  # Prejuízo não gera dividendos
            lucro_distribuivel.append(max(0, lucro))
        
        # 4. Dividendos por período
        periodos = pd.get_periodos()
        dividendos_periodo = []
        
        for inicio, fim in periodos:
            # Acumula lucro do período
            lucro_acum = sum(lucro_distribuivel[inicio-1:fim])
            
            # Calcula dividendo do período
            dividendo = lucro_acum * pd.pct_distribuir
            
            # Nome do período
            nome_periodo = pd.get_nome_periodo(inicio, fim)
            
            dividendos_periodo.append({
                "periodo": nome_periodo,
                "inicio": inicio,
                "fim": fim,
                "lucro_acumulado": lucro_acum,
                "dividendo": dividendo,
                "mes_pagamento": fim
            })
        
        # 5. Dividendos por sócio
        socios_ativos = {k: v for k, v in self.socios_prolabore.items() if v.ativo}
        
        # Validar soma de participações
        total_participacao = sum(s.participacao for s in socios_ativos.values())
        
        dividendos_por_socio = {}
        for nome, socio in socios_ativos.items():
            participacao_ajustada = socio.participacao / total_participacao if total_participacao > 0 else 0
            
            dividendos_por_socio[nome] = {
                "participacao": socio.participacao,
                "participacao_ajustada": participacao_ajustada,
                "capital": socio.capital,
                "por_periodo": {}
            }
            
            total_socio = 0
            for dp in dividendos_periodo:
                valor_socio = dp["dividendo"] * participacao_ajustada
                dividendos_por_socio[nome]["por_periodo"][dp["periodo"]] = valor_socio
                total_socio += valor_socio
            
            dividendos_por_socio[nome]["total_anual"] = total_socio
        
        # 6. Cronograma de pagamentos (para Fluxo de Caixa)
        cronograma = [0.0] * 12
        for dp in dividendos_periodo:
            mes_pgto = dp["mes_pagamento"] - 1  # índice 0-based
            cronograma[mes_pgto] = dp["dividendo"]
        
        # 7. Indicadores
        total_resultado = sum(resultado_liquido)
        total_dividendos = sum(cronograma)
        capital_total = sum(s.capital for s in socios_ativos.values())
        
        indicadores = {
            "payout": total_dividendos / total_resultado if total_resultado > 0 else 0,
            "dividendo_por_capital": total_dividendos / capital_total if capital_total > 0 else 0,
            "lucro_retido": total_resultado - total_dividendos,
            "total_reserva_legal": sum(reserva_legal),
            "total_reserva_investimento": sum(reserva_investimento),
            "total_lucro_distribuivel": sum(lucro_distribuivel),
            "total_dividendos": total_dividendos,
            "total_resultado_liquido": total_resultado
        }
        
        return {
            "resultado_liquido": resultado_liquido,
            "reserva_legal": reserva_legal,
            "reserva_investimento": reserva_investimento,
            "lucro_distribuivel": lucro_distribuivel,
            "dividendos_periodo": dividendos_periodo,
            "dividendos_por_socio": dividendos_por_socio,
            "cronograma": cronograma,
            "indicadores": indicadores,
            "premissas": {
                "pct_reserva_legal": pd.pct_reserva_legal,
                "pct_reserva_investimento": pd.pct_reserva_investimento,
                "frequencia": pd.frequencia,
                "pct_distribuir": pd.pct_distribuir
            }
        }
    
    def get_cronograma_dividendos(self) -> List[float]:
        """
        Retorna cronograma de pagamento de dividendos para uso no Fluxo de Caixa.
        
        Returns:
            Lista com 12 valores (um por mês)
        """
        resultado = self.calcular_dividendos()
        return resultado["cronograma"]
    
    # ============================================
    # FLUXO DE CAIXA
    # ============================================
    
    def calcular_recebimentos_servico(self, servico: str) -> List[float]:
        """
        Calcula cronograma de recebimentos de um serviço.
        Suporta parcelamento de até 12x no cartão de crédito.
        
        DOIS MODOS:
        
        1. MODO PLANILHA (recebimento_avista_no_mes = False):
           - TODA receita segue PMR + parcelamento de cartão
           - Mesmo dinheiro/PIX só entra em M+1
           - Compatível com a planilha Excel
        
        2. MODO REALISTA (recebimento_avista_no_mes = True):
           - Dinheiro/PIX: recebe NO MESMO MÊS
           - Cartão Débito: recebe NO MESMO MÊS
           - Cartão Crédito: segue parcelamento (1x até 12x)
           - Mais preciso para gestão de caixa real
        """
        if not self.dre:
            self.calcular_dre()
        
        # Normaliza nome do serviço (remove espaços extras)
        servico_norm = servico.strip()
        
        # Busca receita no DRE (tenta com e sem strip)
        receita_mensal = self.dre.get(servico_norm, self.dre.get(servico, [0.0] * 12))
        pfc = self.premissas_fc
        fp = self.pagamento  # Formas de pagamento
        
        # Coeficientes de recebimento do cartão crédito (suporta até 12x)
        coefs = pfc.get_coeficientes_recebimento()  # [coef_m1, coef_m2, ..., coef_m12]
        
        # PMR do serviço (distribuição entre M+1 e M+2)
        pct_m1, pct_m2 = pfc.get_distribuicao_pmr(servico_norm)
        
        # Saldo inicial de CR
        saldo_inicial = pfc.get_saldo_inicial_cr(servico_norm)
        
        # Proporção deste serviço no faturamento (para rateio da receita ano anterior)
        receita_jan = receita_mensal[0]
        # USA SERVIÇOS CADASTRADOS (dinâmico) - com strip
        total_receita_jan = sum(
            self.dre.get(s.strip(), self.dre.get(s, [0]*12))[0] 
            for s in self.servicos.keys()
        )
        pct_servico = receita_jan / total_receita_jan if total_receita_jan > 0 else 0
        
        # Receita do ano anterior - AUTO ou MANUAL
        # Se usar_receita_auto = True, usa a receita média projetada do ano atual
        if pfc.usar_receita_auto:
            # Calcula média da receita projetada do ano atual
            receita_media_projetada = sum(receita_mensal) / 12 if sum(receita_mensal) > 0 else 0
            # Usa essa média para Out, Nov, Dez do ano anterior (rateio já aplicado)
            rec_out = receita_media_projetada
            rec_nov = receita_media_projetada
            rec_dez = receita_media_projetada
        else:
            # Usa valores manuais configurados (rateio por pct_servico)
            rec_out = pfc.receita_out_ano_anterior * pct_servico
            rec_nov = pfc.receita_nov_ano_anterior * pct_servico
            rec_dez = pfc.receita_dez_ano_anterior * pct_servico
        
        # Receita dos últimos 12 meses do ano anterior (para parcelamentos longos)
        rec_media_ant = (rec_out + rec_nov + rec_dez) / 3
        receita_ano_ant = [rec_media_ant] * 12  # índice 0 = mês -12, índice 11 = mês -1 (dez)
        receita_ano_ant[11] = rec_dez  # Dezembro
        receita_ano_ant[10] = rec_nov  # Novembro
        receita_ano_ant[9] = rec_out   # Outubro
        
        recebimentos = [0.0] * 12
        
        # =====================================================
        # MODO REALISTA: Considera formas de pagamento + antecipação
        # =====================================================
        if pfc.recebimento_avista_no_mes:
            pct_avista = fp.dinheiro_pix + fp.cartao_debito  # Recebe no mês
            pct_credito = fp.cartao_credito  # Parcelado
            pct_antecipacao = fp.pct_antecipacao  # % do crédito antecipado (de Premissas)
            taxa_antecipacao = self.macro.taxa_antecipacao  # Taxa cobrada (5%)
            
            for mes in range(12):
                # 1. SALDO CR INICIAL (Jan e Fev)
                if mes == 0:
                    recebimentos[mes] += saldo_inicial * pct_m1
                elif mes == 1:
                    recebimentos[mes] += saldo_inicial * pct_m2
                
                # 2. RECEITA DO MÊS - parte à vista (Dinheiro/PIX + Débito)
                recebimentos[mes] += receita_mensal[mes] * pct_avista
                
                # 3. RECEITA EM CARTÃO CRÉDITO DO MÊS - parte antecipada
                # Antecipação: recebe no mesmo mês, deduzindo a taxa
                credito_mes = receita_mensal[mes] * pct_credito
                valor_antecipado = credito_mes * pct_antecipacao
                valor_liquido_antecipado = valor_antecipado * (1 - taxa_antecipacao)
                recebimentos[mes] += valor_liquido_antecipado
                
                # 4. RECEITA EM CARTÃO CRÉDITO - parcelada de meses anteriores
                # Apenas a parte NÃO antecipada (1 - pct_antecipacao)
                pct_nao_antecipado = 1 - pct_antecipacao
                
                for lag in range(1, 13):  # lag = 1 (M-1) até 12 (M-12)
                    if coefs[lag - 1] > 0:  # Só processa se há coeficiente
                        mes_origem = mes - lag
                        if mes_origem >= 0:
                            # Receita do ano atual (parte não antecipada)
                            credito = receita_mensal[mes_origem] * pct_credito * pct_nao_antecipado
                            recebimentos[mes] += credito * coefs[lag - 1]
                        else:
                            # Receita do ano anterior
                            idx_ant = 12 + mes_origem
                            if idx_ant >= 0:
                                credito = receita_ano_ant[idx_ant] * pct_credito * pct_nao_antecipado
                                recebimentos[mes] += credito * coefs[lag - 1]
        
        # =====================================================
        # MODO PLANILHA: Toda receita segue PMR + parcelamento
        # =====================================================
        else:
            for mes in range(12):
                # Saldo CR inicial (Jan e Fev)
                if mes == 0:
                    recebimentos[mes] += saldo_inicial * pct_m1
                elif mes == 1:
                    recebimentos[mes] += saldo_inicial * pct_m2
                
                # Receita de meses anteriores com PMR + parcelamento
                # PMR distribui entre M+1 e M+2, depois parcelamento distribui
                for lag_pmr in range(1, 3):  # PMR M+1 e M+2
                    pct_pmr = pct_m1 if lag_pmr == 1 else pct_m2
                    
                    for lag_parc in range(1, 13):  # Parcelamento até 12x
                        if coefs[lag_parc - 1] > 0:
                            lag_total = lag_pmr + lag_parc - 1  # Lag total desde a venda
                            mes_origem = mes - lag_total
                            
                            if mes_origem >= 0:
                                rec = receita_mensal[mes_origem] * pct_pmr * coefs[lag_parc - 1]
                                recebimentos[mes] += rec
                            elif mes_origem >= -12:
                                idx_ant = 12 + mes_origem
                                if idx_ant >= 0:
                                    rec = receita_ano_ant[idx_ant] * pct_pmr * coefs[lag_parc - 1]
                                    recebimentos[mes] += rec
        
        return recebimentos


    def calcular_recebimentos_totais(self) -> Dict[str, List[float]]:
        """
        Calcula todos os recebimentos por serviço e total.
        Retorna dicionário com cronograma por serviço + total.
        """
        # USA SERVIÇOS CADASTRADOS (dinâmico)
        servicos = list(self.servicos.keys())
        
        resultado = {}
        total = [0.0] * 12
        
        for servico in servicos:
            receb = self.calcular_recebimentos_servico(servico)
            # Usa nome normalizado (sem espaços extras) como chave
            servico_norm = servico.strip()
            resultado[servico_norm] = receb
            for m in range(12):
                total[m] += receb[m]
        
        resultado["Total Recebimentos"] = total
        return resultado
    
    def calcular_pagamentos_folha_fc(self) -> Dict[str, List[float]]:
        """
        Calcula pagamentos de folha para o Fluxo de Caixa.
        Regime de CAIXA: pagamento no mês seguinte à competência.
        
        IMPORTANTE: 
        - No Simples Nacional, o INSS Patronal (CPP) está INCLUÍDO no DAS
        - Para PF (Carnê Leão), não há Pró-labore separado
        
        Inclui:
        - Folha CLT Líquida (salário líquido CLT + pagamentos informais)
        - INSS + FGTS (encargos CLT - só FGTS no Simples)
        - Folha Proprietários e Fisioterapeutas (comissões)
        - Pró-labore + INSS (sócios) - SOMENTE PARA PJ
        """
        # Obter folha por competência
        custo_pessoal = self.calcular_custo_pessoal_dre()
        folha_fisio_anual = self.projetar_folha_fisioterapeutas_anual()
        folha_geral_anual = self.projetar_folha_anual()
        
        # Verificar regime tributário
        regime = self.premissas_folha.regime_tributario
        is_pf = "Carnê" in regime or "PF" in regime
        is_simples = "Simples" in regime
        pfc = self.premissas_fc
        
        resultado = {
            "Folha Proprietários": [0.0] * 12,
            "Folha Fisioterapeutas": [0.0] * 12,
            "Folha CLT Líquida": [0.0] * 12,
            "INSS + FGTS": [0.0] * 12,
            "Pró-labore + INSS": [0.0] * 12,
        }
        
        # Saldos iniciais (pagos em Janeiro) - AUTO ou MANUAL
        if pfc.usar_cp_folha_auto:
            # Calcula baseado na folha de Dezembro (mês 11)
            dez_prop = folha_fisio_anual[11]["total_proprietarios"]
            dez_fisio = folha_fisio_anual[11]["total_fisioterapeutas"]
            dez_clt_bruto = folha_geral_anual[11]["clt"]["salarios_brutos"]
            dez_clt_inss = folha_geral_anual[11]["clt"]["inss"]
            dez_clt_fgts = folha_geral_anual[11]["clt"]["fgts"]
            dez_clt_liquido = dez_clt_bruto - dez_clt_inss
            dez_informal = folha_geral_anual[11]["informal"]["liquido"]
            
            # Saldos iniciais calculados
            cp_prop = dez_prop
            cp_fisio = dez_fisio
            cp_clt = dez_clt_liquido + dez_informal
            cp_encargos = dez_clt_fgts if (is_simples or is_pf) else (dez_clt_fgts + dez_clt_bruto * 0.20)
        else:
            # Usa valores manuais configurados
            cp_prop = pfc.cp_retirada_proprietarios
            cp_fisio = pfc.cp_folha_fisioterapeutas
            cp_clt = pfc.cp_folha_colaboradores
            cp_encargos = pfc.cp_encargos_clt
        
        # Aplica saldos iniciais (Janeiro)
        # Para PF, só inclui saldo inicial de proprietários (se houver)
        resultado["Folha Proprietários"][0] = cp_prop
        
        if not is_pf:
            # PJ tem mais saldos iniciais
            resultado["Folha Fisioterapeutas"][0] = cp_fisio
            resultado["Folha CLT Líquida"][0] = cp_clt
            resultado["INSS + FGTS"][0] = cp_encargos
        
        # Pagamentos mensais (mês M+1 paga competência M)
        for mes in range(12):
            # Competência do mês
            prop_competencia = folha_fisio_anual[mes]["total_proprietarios"]
            fisio_competencia = folha_fisio_anual[mes]["total_fisioterapeutas"]
            
            # CLT: salário líquido (bruto - INSS funcionário - IRRF)
            clt_bruto = folha_geral_anual[mes]["clt"]["salarios_brutos"]
            clt_inss_func = folha_geral_anual[mes]["clt"]["inss"]
            clt_fgts = folha_geral_anual[mes]["clt"]["fgts"]
            clt_liquido = clt_bruto - clt_inss_func
            
            # Encargos: No Simples só FGTS, em outros regimes INSS Patronal + FGTS
            if is_simples or is_pf:
                # Simples/PF: INSS Patronal está no DAS/Carnê
                encargos_clt = clt_fgts
            else:
                # Lucro Presumido/Real: INSS Patronal 20% + FGTS 8%
                clt_inss_patronal = clt_bruto * 0.20
                encargos_clt = clt_inss_patronal + clt_fgts
            
            # Informal: pagamento direto (sem encargos)
            informal_liquido = folha_geral_anual[mes]["informal"]["liquido"]
            
            # Total pagamento "CLT + Informal" - saída de caixa real
            total_folha_liquida = clt_liquido + informal_liquido
            
            # Pró-labore (SOMENTE PJ)
            if is_pf:
                prolabore_total = 0  # PF não tem pró-labore separado
            else:
                prolabore_bruto = folha_geral_anual[mes]["prolabore"]["bruto"]
                prolabore_inss = folha_geral_anual[mes]["prolabore"]["inss"]
                prolabore_total = prolabore_bruto + prolabore_inss
            
            # Pagamento no mês seguinte
            if mes < 11:  # Até novembro, paga no mês seguinte
                resultado["Folha Proprietários"][mes + 1] = prop_competencia
                resultado["Folha Fisioterapeutas"][mes + 1] = fisio_competencia
                resultado["Folha CLT Líquida"][mes + 1] = total_folha_liquida
                resultado["INSS + FGTS"][mes + 1] = encargos_clt
                resultado["Pró-labore + INSS"][mes + 1] = prolabore_total
            # Dezembro fica para Janeiro do próximo ano (não entra neste FC)
        
        return resultado
    
    def calcular_pagamentos_impostos_fc(self) -> Dict[str, List[float]]:
        """
        Calcula pagamentos de impostos para o Fluxo de Caixa.
        
        - PJ (Simples Nacional): DAS pago no mês seguinte
        - PF (Carnê Leão): INSS + IR pago no mês seguinte
        """
        if not self.dre:
            self.calcular_dre()
        
        # Verifica regime tributário
        regime = self.premissas_folha.regime_tributario
        is_pf = "Carnê" in regime or "PF" in regime
        pfc = self.premissas_fc
        
        # Busca o imposto correto do DRE
        if is_pf:
            # PF - Carnê Leão
            imposto_competencia = [abs(v) for v in self.dre.get("(-) Carnê Leão (PF)", [0.0] * 12)]
            nome_conta = "Carnê Leão (INSS+IR)"
        else:
            # PJ - Simples Nacional (ou outro regime)
            imposto_competencia = [abs(v) for v in self.dre.get("(-) Simples Nacional", [0.0] * 12)]
            nome_conta = "DAS Simples Nacional"
        
        resultado = {
            nome_conta: [0.0] * 12
        }
        
        # Janeiro: paga saldo inicial (imposto de Dezembro do ano anterior)
        # AUTO ou MANUAL
        if pfc.usar_cp_folha_auto:
            # Usa imposto de Dezembro projetado como proxy
            cp_imposto = imposto_competencia[11]  # Dezembro
        else:
            cp_imposto = pfc.cp_impostos
        
        resultado[nome_conta][0] = cp_imposto
        
        # Meses seguintes: paga competência do mês anterior
        for mes in range(1, 12):
            resultado[nome_conta][mes] = imposto_competencia[mes - 1]
        
        return resultado
    
    def calcular_pagamentos_despesas_fc(self) -> Dict[str, List[float]]:
        """
        Calcula pagamentos de despesas operacionais para o Fluxo de Caixa.
        Despesas operacionais: pagas no próprio mês.
        
        IMPORTANTE: No FC incluímos:
        - Despesas Fixas (Compras, Aluguel, Energia, etc.)
        - Custos Variáveis (despesas cadastradas como variáveis)
        """
        if not self.despesas:
            self.calcular_despesas_fixas()
        
        if not self.dre:
            self.calcular_dre()
        
        pfc = self.premissas_fc
        
        # Total despesas fixas (INCLUINDO Compras para o FC)
        total_despesas = [0.0] * 12
        for despesa, valores in self.despesas.items():
            if "Total" not in despesa:  # Inclui tudo, inclusive Compras
                for m in range(12):
                    total_despesas[m] += valores[m]
        
        # Adicionar Custos Variáveis (todas as despesas variáveis cadastradas) - saída de caixa!
        custos_variaveis = [abs(v) for v in self.dre.get("Total Custos Variáveis", [0.0] * 12)]
        for m in range(12):
            total_despesas[m] += custos_variaveis[m]
        
        # CP Fornecedores - AUTO ou MANUAL
        if pfc.usar_cp_folha_auto:
            # v1.99.94: Usa valores_2025[11] (Dez do ano anterior) em vez de projeção
            cp_fornecedores = 0.0
            for desp in self.despesas_fixas.values():
                if hasattr(desp, 'valores_2025') and desp.valores_2025:
                    cp_fornecedores += (desp.valores_2025[11] or 0) if len(desp.valores_2025) > 11 else 0
        else:
            cp_fornecedores = pfc.cp_fornecedores
        
        # Saldo inicial de fornecedores pago em Janeiro
        resultado = {
            "Despesas Operacionais": total_despesas.copy()
        }
        resultado["Despesas Operacionais"][0] += cp_fornecedores
        
        return resultado
    
    def calcular_pagamentos_financeiros_fc(self) -> Dict[str, List[float]]:
        """
        Calcula pagamentos financeiros para o Fluxo de Caixa.
        Inclui taxa cartão, parcelas de financiamentos, CAPEX.
        """
        if not self.dre:
            self.calcular_dre()
        
        resultado = {
            "Custos Financeiros Cartão": [0.0] * 12,
            "Parcelas Financiamentos": [0.0] * 12,
            "Parcelas Novos Invest.": [0.0] * 12,
            "Entrada CAPEX": [0.0] * 12,
            "Juros Cheque Especial": [0.0] * 12,
        }
        
        # Taxa de cartão (paga no mês do recebimento)
        taxa_cartao = [abs(v) for v in self.dre.get("(-) Taxa Cartão", [0.0] * 12)]
        resultado["Custos Financeiros Cartão"] = taxa_cartao
        
        # Financiamentos existentes - PARCELAS (não só juros!)
        for fin in self.premissas_financeiras.financiamentos:
            if fin.ativo:
                for mes in range(1, 13):
                    parcela = fin.calcular_parcela_mes(mes)
                    resultado["Parcelas Financiamentos"][mes - 1] += parcela
        
        # Novos investimentos - PARCELAS + ENTRADA
        for inv in self.premissas_financeiras.investimentos:
            if inv.ativo:
                for mes in range(1, 13):
                    # Entrada à vista
                    entrada = inv.calcular_entrada_mes(mes)
                    resultado["Entrada CAPEX"][mes - 1] += entrada
                    
                    # Parcelas do financiamento (começam no mês seguinte à aquisição)
                    if mes > inv.mes_aquisicao:
                        parcela = inv.calcular_parcela_mes(mes)
                        resultado["Parcelas Novos Invest."][mes - 1] += parcela
        
        # Juros cheque especial (calculado após saldo - circular, tratado depois)
        # Por ora deixa zerado
        
        return resultado
    
    def calcular_pagamentos_dividendos_fc(self) -> List[float]:
        """
        Calcula pagamentos de dividendos para o Fluxo de Caixa.
        Dividendos: pagos no final de cada trimestre.
        """
        regime = self.premissas_folha.regime_tributario
        is_pj = "Simples" in regime or "PJ" in regime
        
        if not is_pj:
            return [0.0] * 12
        
        return self.get_cronograma_dividendos()
    
    def calcular_fluxo_caixa(self) -> Dict[str, List[float]]:
        """
        Calcula o Fluxo de Caixa completo.
        
        Estrutura:
        - ENTRADAS: Recebimentos por serviço + Rendimentos aplicações
        - SAÍDAS: Folha + Impostos + Despesas + Financeiros + Dividendos
        - MOVIMENTAÇÃO: Aportes/Resgates de aplicações
        - SALDO: Inicial, Variação, Final
        - INDICADORES: Saldo Mínimo, Excesso/Necessidade, Status
        """
        fc = {}
        
        # ========== ENTRADAS ==========
        recebimentos = self.calcular_recebimentos_totais()
        for servico, valores in recebimentos.items():
            if servico != "Total Recebimentos":
                fc[f"(+) {servico}"] = valores
        
        # Rendimentos de aplicações (por ora zerado - depende do saldo)
        fc["(+) Rendimentos Aplicações"] = [0.0] * 12
        
        # Total Entradas
        fc["Total Entradas"] = recebimentos["Total Recebimentos"].copy()
        
        # ========== SAÍDAS ==========
        # Folha
        folha = self.calcular_pagamentos_folha_fc()
        for conta, valores in folha.items():
            fc[f"(-) {conta}"] = [-v for v in valores]
        
        # Impostos
        impostos = self.calcular_pagamentos_impostos_fc()
        for conta, valores in impostos.items():
            fc[f"(-) {conta}"] = [-v for v in valores]
        
        # Benefícios (por ora zerado)
        fc["(-) Benefícios (VT, VR, Planos)"] = [0.0] * 12
        
        # Despesas
        despesas = self.calcular_pagamentos_despesas_fc()
        for conta, valores in despesas.items():
            fc[f"(-) {conta}"] = [-v for v in valores]
        
        # Financeiros
        financeiros = self.calcular_pagamentos_financeiros_fc()
        for conta, valores in financeiros.items():
            fc[f"(-) {conta}"] = [-v for v in valores]
        
        # Dividendos
        dividendos = self.calcular_pagamentos_dividendos_fc()
        fc["(-) Distribuição Dividendos"] = [-v for v in dividendos]
        
        # Total Saídas
        total_saidas = [0.0] * 12
        for conta, valores in fc.items():
            if conta.startswith("(-)"):
                for m in range(12):
                    total_saidas[m] += valores[m]
        fc["Total Saídas"] = total_saidas
        
        # ========== MOVIMENTAÇÃO APLICAÇÕES ==========
        fc["(-) Aportes Aplicações"] = [0.0] * 12
        fc["(+) Resgates Aplicações"] = [0.0] * 12
        
        # ========== FLUXO DE CAIXA COM POLÍTICA DE SALDO MÍNIMO ==========
        # Lógica: 
        # 1. Calcular variação operacional (sem movimentação de aplicações)
        # 2. Se saldo > saldo_minimo: aporte do excesso em aplicações
        # 3. Se saldo < saldo_minimo: resgate de aplicações (se houver)
        # 4. Rendimentos sobre saldo de aplicações do mês anterior
        
        saldo_inicial = [0.0] * 12
        variacao_operacional = [0.0] * 12  # Antes de movimentações de aplicações
        variacao = [0.0] * 12  # Total incluindo aplicações
        saldo_final = [0.0] * 12
        
        # Aplicações
        aportes_aplicacoes = [0.0] * 12
        resgates_aplicacoes = [0.0] * 12
        rendimentos = [0.0] * 12
        saldo_aplicacoes = [0.0] * 12
        
        # Premissas
        taxa_mensal = self.premissas_financeiras.aplicacoes.taxa_mensal
        saldo_aplicacoes_inicial = self.premissas_financeiras.aplicacoes.saldo_inicial
        saldo_minimo = self.premissas_fc.saldo_minimo
        
        # Janeiro: saldo inicial é o caixa inicial
        saldo_inicial[0] = self.premissas_fc.caixa_inicial
        
        for mes in range(12):
            # 1. Saldo de aplicações no início do mês
            if mes == 0:
                saldo_aplic_inicio = saldo_aplicacoes_inicial
            else:
                saldo_aplic_inicio = saldo_aplicacoes[mes - 1]
            
            # 2. Rendimento do mês (sobre saldo do início do mês)
            rendimentos[mes] = saldo_aplic_inicio * taxa_mensal
            
            # 3. Adiciona rendimento às entradas
            fc["(+) Rendimentos Aplicações"][mes] = rendimentos[mes]
            fc["Total Entradas"][mes] += rendimentos[mes]
            
            # 4. Variação operacional (entradas + saídas, sem movimentação de aplicações)
            variacao_operacional[mes] = fc["Total Entradas"][mes] + fc["Total Saídas"][mes]
            
            # 5. Saldo projetado ANTES de movimentar aplicações
            saldo_projetado = saldo_inicial[mes] + variacao_operacional[mes]
            
            # 6. Política de Saldo Mínimo
            if saldo_minimo > 0:
                excesso = saldo_projetado - saldo_minimo
                
                if excesso > 0:
                    # Sobra dinheiro: APLICA o excesso
                    aportes_aplicacoes[mes] = excesso
                    resgates_aplicacoes[mes] = 0
                elif excesso < 0:
                    # Falta dinheiro: RESGATA das aplicações (se houver)
                    necessidade = abs(excesso)
                    # Limita resgate ao saldo disponível em aplicações
                    resgate_possivel = min(necessidade, saldo_aplic_inicio + rendimentos[mes])
                    resgates_aplicacoes[mes] = resgate_possivel
                    aportes_aplicacoes[mes] = 0
                else:
                    aportes_aplicacoes[mes] = 0
                    resgates_aplicacoes[mes] = 0
            else:
                # Sem política de saldo mínimo: não movimenta aplicações automaticamente
                aportes_aplicacoes[mes] = 0
                resgates_aplicacoes[mes] = 0
            
            # 7. Atualiza FC com movimentações de aplicações
            fc["(-) Aportes Aplicações"][mes] = -aportes_aplicacoes[mes]  # Saída de caixa
            fc["(+) Resgates Aplicações"][mes] = resgates_aplicacoes[mes]  # Entrada de caixa
            
            # 8. Variação total = operacional + resgates - aportes
            variacao[mes] = variacao_operacional[mes] + resgates_aplicacoes[mes] - aportes_aplicacoes[mes]
            
            # 9. Saldo Final de Caixa
            saldo_final[mes] = saldo_inicial[mes] + variacao[mes]
            
            # 10. Saldo Final de Aplicações
            saldo_aplicacoes[mes] = saldo_aplic_inicio + aportes_aplicacoes[mes] - resgates_aplicacoes[mes] + rendimentos[mes]
            
            # 11. Próximo mês: Saldo Inicial = Saldo Final do mês anterior
            if mes < 11:
                saldo_inicial[mes + 1] = saldo_final[mes]
        
        # Armazena resultados
        fc["Saldo Inicial"] = saldo_inicial
        fc["(+/-) Variação"] = variacao
        fc["Saldo Final"] = saldo_final
        
        # Armazena evolução das aplicações para consulta
        fc["_Saldo Aplicações"] = saldo_aplicacoes  # Prefixo _ para não exibir na tabela principal
        fc["_Rendimentos Aplicações"] = rendimentos
        fc["_Aportes Aplicações"] = aportes_aplicacoes
        fc["_Resgates Aplicações"] = resgates_aplicacoes
        
        # Atualiza arrays em premissas_financeiras.aplicacoes para consistência
        self.premissas_financeiras.aplicacoes.aportes = aportes_aplicacoes
        self.premissas_financeiras.aplicacoes.resgates = resgates_aplicacoes
        
        # ========== INDICADORES ==========
        fc["Saldo Mínimo"] = [saldo_minimo] * 12
        
        # Com política ativa, o saldo deve ficar próximo ao mínimo
        fc["Excesso/(Necessidade)"] = [saldo_final[m] - saldo_minimo for m in range(12)]
        fc["Status"] = ["OK" if saldo_final[m] >= saldo_minimo * 0.95 else "ATENÇÃO" for m in range(12)]
        
        # Indicadores de Aplicações (para exibição)
        fc["Saldo Aplicações"] = saldo_aplicacoes
        
        # Armazenar resultado
        self.fluxo_caixa = fc
        
        return fc
    
    def get_resumo_fluxo_caixa(self) -> Dict:
        """Retorna resumo do Fluxo de Caixa"""
        if not self.fluxo_caixa:
            self.calcular_fluxo_caixa()
        
        fc = self.fluxo_caixa
        
        return {
            "total_entradas": sum(fc["Total Entradas"]),
            "total_saidas": sum(fc["Total Saídas"]),
            "variacao_ano": sum(fc["(+/-) Variação"]),
            "saldo_inicial": fc["Saldo Inicial"][0],
            "saldo_final": fc["Saldo Final"][11],
            "meses_atencao": sum(1 for s in fc["Status"] if s == "ATENÇÃO"),
            "necessidade_maxima": min(fc["Excesso/(Necessidade)"]),
            # Informações de Aplicações
            "saldo_aplicacoes_inicial": self.premissas_financeiras.aplicacoes.saldo_inicial,
            "saldo_aplicacoes_final": fc.get("Saldo Aplicações", [0]*12)[11],
            "total_aportes": sum(fc.get("_Aportes Aplicações", [0]*12)),
            "total_resgates": sum(fc.get("_Resgates Aplicações", [0]*12)),
            "total_rendimentos": sum(fc.get("(+) Rendimentos Aplicações", [0]*12)),
        }
    
    # ============================================
    # INDICADORES
    # ============================================
    
    def calcular_indicadores(self) -> Dict[str, float]:
        """Calcula indicadores principais"""
        if not self.dre:
            self.calcular_dre()
        
        receita_total = sum(self.dre.get("Receita Bruta Total", [0]))
        receita_liquida = sum(self.dre.get("Receita Líquida", [0]))
        margem_contrib = sum(self.dre.get("Margem de Contribuição", [0]))
        ebitda = sum(self.dre.get("EBITDA", [0]))
        resultado_liq = sum(self.dre.get("Resultado Líquido", [0]))
        
        # Lucro no Período (para PJ) ou Resultado Líquido (para PF)
        lucro_periodo = sum(self.dre.get("Lucro no Período", [0])) if "Lucro no Período" in self.dre else resultado_liq
        
        indicadores = {
            "Receita Bruta Total": receita_total,
            "Receita Líquida": receita_liquida,
            "Margem de Contribuição": margem_contrib,
            "EBITDA": ebitda,
            "Resultado Líquido": resultado_liq,
            "Lucro no Período": lucro_periodo,
            "Margem EBITDA": ebitda / receita_total if receita_total else 0,
            "Margem Líquida": resultado_liq / receita_total if receita_total else 0,
            "% Margem Contribuição": margem_contrib / receita_liquida if receita_liquida else 0,
        }
        
        # Sessões totais
        total_sessoes = 0
        for servico in self.servicos:
            for mes in range(12):
                total_sessoes += self.calcular_sessoes_mes(servico, mes)
        indicadores["Total Sessões Ano"] = total_sessoes
        
        # Ticket médio
        if total_sessoes > 0:
            indicadores["Ticket Médio"] = receita_total / total_sessoes
        
        return indicadores
    
    # ============================================
    # CONFIGURAÇÃO DE CENÁRIOS
    # ============================================
    
    def aplicar_cenario(self, nome_cenario: str):
        """Aplica um cenário - usa os fatores pré-definidos da classe Cenario"""
        cenarios_map = {
            "Pessimista": Cenario.pessimista,
            "Conservador": Cenario.base,  # Conservador usa base (sem alteração)
            "Otimista": Cenario.otimista,
            "Base": Cenario.base
        }
        
        if nome_cenario in cenarios_map:
            self.cenario = cenarios_map[nome_cenario]()
        else:
            # Fallback para cenário Base
            self.cenario = Cenario.base()
        
        # CRÍTICO: Limpar caches de cálculo para forçar recálculo com novo fator
        # Sem isso, DRE/FC usam valores do cenário anterior!
        self.despesas = {}
        self.dre = {}
        self.receita_bruta = {}
        self.deducoes = {}
        self.custos = {}
        self.fluxo_caixa = {}  # CRÍTICO: Sem isso get_resumo_fluxo_caixa retorna valores antigos!
    
    def restaurar_ajustes_padrao(self):
        """Restaura ajustes padrão dos cenários"""
        self.ajustes_cenarios = {
            "Pessimista": {
                "sessoes": {},
                "valores": {},
                "despesas": {},
                "descricao": "Cenário de crise: redução de demanda, aumento de custos"
            },
            "Otimista": {
                "sessoes": {},
                "valores": {},
                "despesas": {},
                "descricao": "Cenário favorável: crescimento acelerado, otimização de custos"
            }
        }
        self.cenario_oficial = "Conservador"
    
    def get_ajuste_sessoes(self, cenario: str, servico: str) -> float:
        """Retorna o ajuste de sessões para um serviço em um cenário"""
        if cenario == "Conservador":
            return 0  # Base não tem ajuste
        if cenario in self.ajustes_cenarios:
            return self.ajustes_cenarios[cenario].get("sessoes", {}).get(servico, 0)
        return 0
    
    def get_ajuste_valor(self, cenario: str, servico: str) -> float:
        """Retorna o ajuste de valor para um serviço em um cenário"""
        if cenario == "Conservador":
            return 0
        if cenario in self.ajustes_cenarios:
            return self.ajustes_cenarios[cenario].get("valores", {}).get(servico, 0)
        return 0
    
    def get_ajuste_despesa(self, cenario: str, despesa: str) -> float:
        """Retorna o ajuste de despesa em um cenário"""
        if cenario == "Conservador":
            return 0
        if cenario in self.ajustes_cenarios:
            return self.ajustes_cenarios[cenario].get("despesas", {}).get(despesa, 0)
        return 0
    
    # ============================================
    # SERIALIZAÇÃO (salvar/carregar)
    # ============================================
    
    def to_dict(self) -> dict:
        """Exporta configuração para dicionário"""
        return {
            "macro": self.macro.__dict__,
            "pagamento": self.pagamento.__dict__,
            "operacional": self.operacional.__dict__,
            "sazonalidade": self.sazonalidade.fatores,
            "cenario": {
                "nome": self.cenario.nome,
                "fator_receita": self.cenario.fator_receita,
                "fator_despesas": self.cenario.fator_despesas,
                "fator_crescimento": self.cenario.fator_crescimento,
                "fator_inflacao": self.cenario.fator_inflacao
            },
            "usar_cenarios": getattr(self, 'usar_cenarios', True),
            "cenario_oficial": getattr(self, 'cenario_oficial', 'Conservador'),
            "ajustes_cenarios": getattr(self, 'ajustes_cenarios', {}),
            "usar_comparativo_anterior": getattr(self, 'usar_comparativo_anterior', False),
            "faturamento_anterior": getattr(self, 'faturamento_anterior', [0.0] * 12),
            "ano_anterior": getattr(self, 'ano_anterior', 2025),
            "servicos": {k: v.__dict__ for k, v in self.servicos.items()},
        }
    
    def from_dict(self, data: dict):
        """Importa configuração de dicionário"""
        if "macro" in data:
            self.macro = PremissasMacro(**data["macro"])
        if "pagamento" in data:
            self.pagamento = FormaPagamento(**data["pagamento"])
        if "operacional" in data:
            self.operacional = PremissasOperacionais(**data["operacional"])
        if "sazonalidade" in data:
            self.sazonalidade = Sazonalidade(fatores=data["sazonalidade"])
        if "cenario" in data:
            cenario_data = data["cenario"]
            self.cenario = Cenario(
                nome=cenario_data.get("nome", "Conservador"),
                fator_receita=cenario_data.get("fator_receita", 1.0),
                fator_despesas=cenario_data.get("fator_despesas", 1.0),
                fator_crescimento=cenario_data.get("fator_crescimento", 1.0),
                fator_inflacao=cenario_data.get("fator_inflacao", 1.0)
            )
        if "usar_cenarios" in data:
            self.usar_cenarios = data["usar_cenarios"]
        if "cenario_oficial" in data:
            self.cenario_oficial = data["cenario_oficial"]
        if "ajustes_cenarios" in data:
            self.ajustes_cenarios = data["ajustes_cenarios"]
        if "usar_comparativo_anterior" in data:
            self.usar_comparativo_anterior = data["usar_comparativo_anterior"]
        if "faturamento_anterior" in data:
            self.faturamento_anterior = data["faturamento_anterior"]
        if "ano_anterior" in data:
            self.ano_anterior = data["ano_anterior"]
        if "servicos" in data:
            for nome, srv_data in data["servicos"].items():
                self.servicos[nome] = Servico(**srv_data)


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def criar_motor_padrao(cliente_nome: str = "FVS Fisioterapia", 
                       filial_nome: str = "Unidade Copacabana",
                       tipo_relatorio: str = "Filial") -> MotorCalculo:
    """Cria motor com configurações padrão baseadas no arquivo FVS"""
    motor = MotorCalculo()
    
    # Identificação do cliente
    motor.cliente_nome = cliente_nome
    motor.filial_nome = filial_nome
    motor.tipo_relatorio = tipo_relatorio
    
    # Configurações específicas do cliente FVS
    motor.operacional.num_fisioterapeutas = 13
    motor.operacional.num_salas = 4
    motor.operacional.horas_atendimento_dia = 10
    motor.operacional.dias_uteis_mes = 20
    
    # Serviços com valores do arquivo
    motor.servicos["Osteopatia"].valor_2026 = 335
    motor.servicos["Osteopatia"].sessoes_mes_base = 21
    motor.servicos["Osteopatia"].pct_reajuste = 0.04
    
    motor.servicos["Individual"].valor_2026 = 192
    motor.servicos["Individual"].sessoes_mes_base = 155
    motor.servicos["Individual"].pct_reajuste = 0.054
    
    motor.servicos["Consultório"].valor_2026 = 235
    motor.servicos["Consultório"].sessoes_mes_base = 101
    motor.servicos["Consultório"].pct_reajuste = 0.052
    
    motor.servicos["Domiciliar"].valor_2026 = 275
    motor.servicos["Domiciliar"].sessoes_mes_base = 34
    motor.servicos["Domiciliar"].pct_reajuste = 0.046
    
    motor.servicos["Ginásio"].valor_2026 = 151
    motor.servicos["Ginásio"].sessoes_mes_base = 421
    motor.servicos["Ginásio"].pct_reajuste = 0.051
    
    motor.servicos["Personalizado"].valor_2026 = 209
    motor.servicos["Personalizado"].sessoes_mes_base = 156
    motor.servicos["Personalizado"].pct_reajuste = 0.05
    
    return motor


def criar_motor_vazio(cliente_nome: str = "Novo Cliente", 
                      filial_nome: str = "Matriz",
                      tipo_relatorio: str = "Filial") -> MotorCalculo:
    """
    Cria motor COMPLETAMENTE ZERADO - sem nenhum dado pré-preenchido.
    Ideal para cadastrar novos clientes sem risco de dados equivocados.
    """
    motor = MotorCalculo()
    
    # Identificação do cliente
    motor.cliente_nome = cliente_nome
    motor.filial_nome = filial_nome
    motor.tipo_relatorio = tipo_relatorio
    
    # Zera premissas macro (usar float para evitar erros de tipo)
    motor.macro.ipca = 0.0
    motor.macro.igpm = 0.0
    motor.macro.dissidio = 0.0
    motor.macro.reajuste_tarifas = 0.0
    motor.macro.reajuste_contratos = 0.0
    # Mantém taxas de cartão com valores padrão (não zera)
    motor.macro.taxa_cartao_credito = 0.0354  # 3.54%
    motor.macro.taxa_cartao_debito = 0.0211   # 2.11%
    motor.macro.taxa_antecipacao = 0.05       # 5%
    
    # Zera formas de pagamento (usar float para evitar erros de tipo)
    motor.pagamento.dinheiro_pix = 0.0
    motor.pagamento.cartao_credito = 0.0
    motor.pagamento.cartao_debito = 0.0
    motor.pagamento.outros = 0.0
    motor.pagamento.pct_antecipacao = 0.30  # 30% padrão (não zera)
    
    # Zera operacional
    motor.operacional.num_fisioterapeutas = 0
    motor.operacional.num_salas = 0
    motor.operacional.horas_atendimento_dia = 0
    motor.operacional.dias_uteis_mes = 0
    
    # Zera sazonalidade (LISTA com 12 elementos, índice 0-11)
    motor.sazonalidade.fatores = [1.0] * 12  # 1.0 = neutro (sem variação)
    
    # Limpa todos os serviços
    motor.servicos.clear()
    motor.valores_proprietario.clear()
    motor.valores_profissional.clear()
    
    # Remove todos os proprietários e profissionais
    motor.proprietarios.clear()
    motor.profissionais.clear()
    
    # Remove todos os funcionários CLT e sócios pró-labore
    motor.funcionarios_clt.clear()
    motor.socios_prolabore.clear()
    
    # Zera premissas folha (usar float para evitar erros de tipo)
    motor.premissas_folha.piso_salarial = 0.0
    motor.premissas_folha.vale_transporte_dia = 0.0
    motor.premissas_folha.vale_refeicao_dia = 0.0
    motor.premissas_folha.plano_saude = 0.0
    motor.premissas_folha.plano_odonto = 0.0
    motor.premissas_folha.pct_fgts = 0.0
    motor.premissas_folha.pct_inss_patronal = 0.0
    motor.premissas_folha.pct_provisao_ferias = 0.0
    motor.premissas_folha.pct_provisao_13o = 0.0
    motor.premissas_folha.pct_desconto_vt = 0.0
    motor.premissas_folha.deducao_dependente_ir = 0.0
    motor.premissas_folha.regime_tributario = "PJ - Simples Nacional"  # Default: PJ
    
    # Remove todos os fisioterapeutas
    motor.fisioterapeutas.clear()
    
    # Zera premissas fisioterapeutas para profissionais (níveis)
    # MAS mantém valores padrão para proprietário (60% produção + 20% fat. total)
    motor.premissas_fisio.niveis_remuneracao = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
    # IMPORTANTE: Manter valores padrão para proprietário autônomo
    motor.premissas_fisio.pct_producao_propria = 0.60  # 60% da produção própria
    motor.premissas_fisio.pct_faturamento_total = 0.20  # 20% do faturamento total
    motor.premissas_fisio.pct_base_remuneracao = 0.75
    motor.premissas_fisio.pct_bonus_gerencia = 0.0
    
    # Limpa despesas
    motor.despesas_fixas.clear()
    
    # Zera custo de pessoal
    motor.custo_pessoal_mensal = 0.0
    motor.mes_dissidio = 0
    
    # Configura premissas Simples Nacional com valores sensatos para cálculos
    motor.premissas_simples.faturamento_pf_anual = 0.0  # Se zerado, usa receita real
    motor.premissas_simples.aliquota_inss_pf = 0.11  # 11% contribuinte individual (padrão)
    motor.premissas_simples.teto_inss_pf = 908.86  # Teto INSS 2025 (7.786,02 * 0.1167)
    motor.premissas_simples.limite_fator_r = 0.28  # Mantém default
    
    # Zera premissas financeiras (usar float para evitar erros de tipo)
    motor.premissas_financeiras.investimentos.clear()
    motor.premissas_financeiras.financiamentos.clear()
    motor.premissas_financeiras.cheque_especial_taxa = 0.0
    motor.premissas_financeiras.aplicacao_saldo_inicial = 0.0
    motor.premissas_financeiras.aplicacao_taxa_mensal = 0.0
    
    # Dividendos - mantém defaults sensatos para PJ
    motor.premissas_dividendos.distribuir = True  # PJ distribui dividendos por padrão
    motor.premissas_dividendos.pct_distribuir = 0.30  # 30% do lucro distribuível
    motor.premissas_dividendos.frequencia = "Trimestral"
    motor.premissas_dividendos.pct_reserva_legal = 0.05  # 5%
    motor.premissas_dividendos.pct_reserva_investimento = 0.20  # 20%
    
    # Zera fluxo de caixa (usar float para evitar erros de tipo)
    motor.premissas_fc.caixa_inicial = 0.0
    motor.premissas_fc.saldo_minimo_caixa = 0.0
    motor.premissas_fc.cp_fornecedores = 0
    motor.premissas_fc.cp_impostos = 0
    motor.premissas_fc.cp_folha_clt = 0
    motor.premissas_fc.cp_folha_fisioterapeutas = 0
    motor.premissas_fc.cp_prolabore_socios = 0
    
    # Zera salas
    motor.cadastro_salas.salas.clear()
    motor.cadastro_salas.horas_funcionamento_dia = 0
    motor.cadastro_salas.dias_uteis_mes = 0
    
    return motor


if __name__ == "__main__":
    # Teste do motor
    motor = criar_motor_padrao()
    
    dre = motor.calcular_dre()
    indicadores = motor.calcular_indicadores()
    
    print("="*60)
    print("TESTE DO MOTOR DE CÁLCULO")
    print("="*60)
    
    print("\n📊 INDICADORES:")
    for k, v in indicadores.items():
        if "%" in k or "Margem" in k:
            print(f"  {k}: {v*100:.1f}%")
        elif "Sessões" in k:
            print(f"  {k}: {v:,.0f}")
        else:
            print(f"  {k}: R$ {v:,.2f}")
