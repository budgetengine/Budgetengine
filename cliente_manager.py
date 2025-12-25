"""
Gerenciador de Clientes e Filiais
Sistema multi-tenant para consultoria
VERSÃO SUPABASE - Salva dados no banco de dados
"""

import json
import os
import sys
import streamlit as st
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime

# Tenta importar Supabase
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

# Adiciona diretório pai ao path para imports do motor_calculo
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


# ============================================
# CONEXÃO SUPABASE
# ============================================

def get_supabase_client() -> Optional['Client']:
    """Retorna cliente Supabase"""
    if not SUPABASE_AVAILABLE:
        return None
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        print(f"Erro ao conectar Supabase: {e}")
        return None


@dataclass
class PremissasMacroCliente:
    """Premissas macroeconômicas compartilhadas pelo cliente"""
    ipca: float = 0.045
    igpm: float = 0.05
    dissidio: float = 0.06
    reajuste_tarifas: float = 0.08
    reajuste_contratos: float = 0.05
    taxa_credito: float = 0.0354
    taxa_debito: float = 0.0211
    taxa_antecipacao: float = 0.05


@dataclass
class Cliente:
    """Representa um cliente da consultoria"""
    id: str
    nome: str
    cnpj: str = ""
    contato: str = ""
    email: str = ""
    telefone: str = ""
    filiais: List[str] = field(default_factory=list)
    premissas_macro: PremissasMacroCliente = field(default_factory=PremissasMacroCliente)
    data_criacao: str = ""
    data_atualizacao: str = ""
    # Campo para ID do Supabase
    supabase_id: str = ""
    
    def __post_init__(self):
        if not self.data_criacao:
            self.data_criacao = datetime.now().isoformat()
        self.data_atualizacao = datetime.now().isoformat()


class ClienteManager:
    """
    Gerencia clientes e seus dados
    VERSÃO SUPABASE - Salva no banco de dados
    """
    
    def __init__(self, data_dir: str = "data/clientes"):
        self.data_dir = data_dir
        self.supabase = get_supabase_client()
        self._garantir_diretorio()
    
    def _garantir_diretorio(self):
        """Cria diretório de dados se não existir (fallback)"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _gerar_id(self, nome: str) -> str:
        """Gera ID a partir do nome"""
        import re
        id_base = nome.lower()
        id_base = re.sub(r'[áàãâä]', 'a', id_base)
        id_base = re.sub(r'[éèêë]', 'e', id_base)
        id_base = re.sub(r'[íìîï]', 'i', id_base)
        id_base = re.sub(r'[óòõôö]', 'o', id_base)
        id_base = re.sub(r'[úùûü]', 'u', id_base)
        id_base = re.sub(r'[ç]', 'c', id_base)
        id_base = re.sub(r'[^a-z0-9]', '_', id_base)
        id_base = re.sub(r'_+', '_', id_base).strip('_')
        return id_base
    
    # ============================================
    # MÉTODOS DE CLIENTE
    # ============================================
    
    def listar_clientes(self) -> List[Dict]:
        """Lista todos os clientes do Supabase"""
        if not self.supabase:
            return self._listar_clientes_local()
        
        try:
            response = self.supabase.table("companies").select("*").eq("is_active", True).execute()
            
            clientes = []
            for company in response.data or []:
                # Buscar filiais
                filiais_resp = self.supabase.table("branches").select("slug").eq(
                    "company_id", company["id"]
                ).eq("is_active", True).execute()
                
                filiais = [f["slug"] for f in filiais_resp.data or []]
                
                clientes.append({
                    "id": company["name"].lower().replace(" ", "_"),
                    "nome": company["name"],
                    "filiais": filiais,
                    "supabase_id": company["id"]
                })
            
            return sorted(clientes, key=lambda x: x["nome"])
        except Exception as e:
            print(f"Erro ao listar clientes Supabase: {e}")
            return self._listar_clientes_local()
    
    def _listar_clientes_local(self) -> List[Dict]:
        """Fallback: Lista clientes do JSON local"""
        clientes = []
        if not os.path.exists(self.data_dir):
            return clientes
        
        for item in os.listdir(self.data_dir):
            path_config = os.path.join(self.data_dir, item, "config.json")
            if os.path.isfile(path_config):
                try:
                    with open(path_config, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        clientes.append({
                            "id": config.get("id", item),
                            "nome": config.get("nome", item),
                            "filiais": config.get("filiais", [])
                        })
                except:
                    pass
        
        return sorted(clientes, key=lambda x: x["nome"])
    
    def carregar_cliente(self, cliente_id: str) -> Optional[Cliente]:
        """Carrega dados de um cliente"""
        if not self.supabase:
            return self._carregar_cliente_local(cliente_id)
        
        try:
            # Busca por nome (id é derivado do nome)
            response = self.supabase.table("companies").select("*").eq("is_active", True).execute()
            
            company = None
            for c in response.data or []:
                if self._gerar_id(c["name"]) == cliente_id or c["name"].lower().replace(" ", "_") == cliente_id:
                    company = c
                    break
            
            if not company:
                return self._carregar_cliente_local(cliente_id)
            
            # Buscar filiais
            filiais_resp = self.supabase.table("branches").select("slug").eq(
                "company_id", company["id"]
            ).eq("is_active", True).execute()
            
            filiais = [f["slug"] for f in filiais_resp.data or []]
            
            # Premissas macro
            premissas_data = company.get("premissas_macro", {}) or {}
            premissas = PremissasMacroCliente(
                ipca=premissas_data.get("ipca", 0.045),
                igpm=premissas_data.get("igpm", 0.05),
                dissidio=premissas_data.get("dissidio", 0.06),
                reajuste_tarifas=premissas_data.get("reajuste_tarifas", 0.08),
                reajuste_contratos=premissas_data.get("reajuste_contratos", 0.05),
                taxa_credito=premissas_data.get("taxa_credito", 0.0354),
                taxa_debito=premissas_data.get("taxa_debito", 0.0211),
                taxa_antecipacao=premissas_data.get("taxa_antecipacao", 0.05)
            )
            
            cliente = Cliente(
                id=self._gerar_id(company["name"]),
                nome=company["name"],
                cnpj=company.get("cnpj", ""),
                contato=company.get("contato", ""),
                email=company.get("email", ""),
                telefone=company.get("telefone", ""),
                filiais=filiais,
                premissas_macro=premissas,
                data_criacao=company.get("created_at", ""),
                data_atualizacao=company.get("updated_at", ""),
                supabase_id=company["id"]
            )
            
            return cliente
        except Exception as e:
            print(f"Erro ao carregar cliente Supabase: {e}")
            return self._carregar_cliente_local(cliente_id)
    
    def _carregar_cliente_local(self, cliente_id: str) -> Optional[Cliente]:
        """Fallback: Carrega cliente do JSON local"""
        path_config = os.path.join(self.data_dir, cliente_id, "config.json")
        
        if not os.path.exists(path_config):
            return None
        
        try:
            with open(path_config, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            premissas_data = data.get("premissas_macro", {})
            premissas = PremissasMacroCliente(**premissas_data)
            
            return Cliente(
                id=data.get("id", cliente_id),
                nome=data.get("nome", ""),
                cnpj=data.get("cnpj", ""),
                contato=data.get("contato", ""),
                email=data.get("email", ""),
                telefone=data.get("telefone", ""),
                filiais=data.get("filiais", []),
                premissas_macro=premissas,
                data_criacao=data.get("data_criacao", ""),
                data_atualizacao=data.get("data_atualizacao", "")
            )
        except Exception as e:
            print(f"Erro ao carregar cliente local: {e}")
            return None
    
    # ============================================
    # MÉTODOS DE FILIAL
    # ============================================
    
    def carregar_dados_filial(self, cliente_id: str, filial_id: str) -> Dict:
        """Carrega dados completos de uma filial"""
        if not self.supabase:
            return self._carregar_dados_filial_local(cliente_id, filial_id)
        
        try:
            # Primeiro encontra o company_id
            cliente = self.carregar_cliente(cliente_id)
            if not cliente or not cliente.supabase_id:
                return self._carregar_dados_filial_local(cliente_id, filial_id)
            
            # Busca filial
            response = self.supabase.table("branches").select("*").eq(
                "company_id", cliente.supabase_id
            ).eq("slug", filial_id).execute()
            
            if response.data and len(response.data) > 0:
                branch = response.data[0]
                dados = branch.get("data", {})
                if dados:
                    return dados
            
            # Fallback para local se não encontrar no Supabase
            return self._carregar_dados_filial_local(cliente_id, filial_id)
            
        except Exception as e:
            print(f"Erro ao carregar filial Supabase: {e}")
            return self._carregar_dados_filial_local(cliente_id, filial_id)
    
    def _carregar_dados_filial_local(self, cliente_id: str, filial_id: str) -> Dict:
        """Fallback: Carrega filial do JSON local"""
        path_filial = os.path.join(self.data_dir, cliente_id, f"{filial_id}.json")
        
        if not os.path.exists(path_filial):
            return {}
        
        try:
            with open(path_filial, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def salvar_dados_filial(self, cliente_id: str, filial_id: str, dados: Dict):
        """Salva dados completos de uma filial no Supabase"""
        if not self.supabase:
            return self._salvar_dados_filial_local(cliente_id, filial_id, dados)
        
        try:
            # Primeiro encontra o company_id
            cliente = self.carregar_cliente(cliente_id)
            if not cliente or not cliente.supabase_id:
                return self._salvar_dados_filial_local(cliente_id, filial_id, dados)
            
            # Verifica se filial existe
            response = self.supabase.table("branches").select("id").eq(
                "company_id", cliente.supabase_id
            ).eq("slug", filial_id).execute()
            
            if response.data and len(response.data) > 0:
                # UPDATE
                branch_id = response.data[0]["id"]
                self.supabase.table("branches").update({
                    "data": dados,
                    "updated_at": datetime.now().isoformat()
                }).eq("id", branch_id).execute()
            else:
                # INSERT
                self.supabase.table("branches").insert({
                    "company_id": cliente.supabase_id,
                    "name": filial_id.replace("_", " ").title(),
                    "slug": filial_id,
                    "is_active": True,
                    "data": dados
                }).execute()
                
                # Atualiza lista de filiais do cliente
                if filial_id not in cliente.filiais:
                    cliente.filiais.append(filial_id)
            
            # Também salva localmente como backup
            self._salvar_dados_filial_local(cliente_id, filial_id, dados)
            
            return True
            
        except Exception as e:
            print(f"Erro ao salvar filial Supabase: {e}")
            import traceback
            traceback.print_exc()
            return self._salvar_dados_filial_local(cliente_id, filial_id, dados)
    
    def _salvar_dados_filial_local(self, cliente_id: str, filial_id: str, dados: Dict):
        """Fallback: Salva filial no JSON local"""
        try:
            path_cliente = os.path.join(self.data_dir, cliente_id)
            os.makedirs(path_cliente, exist_ok=True)
            
            path_filial = os.path.join(path_cliente, f"{filial_id}.json")
            
            with open(path_filial, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Erro ao salvar local: {e}")
            return False
    
    # ============================================
    # OUTROS MÉTODOS (mantidos para compatibilidade)
    # ============================================
    
    def criar_cliente(self, nome: str, cnpj: str = "", contato: str = "", 
                      email: str = "", telefone: str = "") -> Cliente:
        """Cria um novo cliente"""
        cliente_id = self._gerar_id(nome)
        
        if self.supabase:
            try:
                # Cria no Supabase
                response = self.supabase.table("companies").insert({
                    "name": nome,
                    "cnpj": cnpj,
                    "email": email,
                    "telefone": telefone,
                    "contato": contato,
                    "is_active": True
                }).execute()
                
                if response.data:
                    return Cliente(
                        id=cliente_id,
                        nome=nome,
                        cnpj=cnpj,
                        contato=contato,
                        email=email,
                        telefone=telefone,
                        supabase_id=response.data[0]["id"]
                    )
            except Exception as e:
                print(f"Erro ao criar cliente Supabase: {e}")
        
        # Fallback local
        path = os.path.join(self.data_dir, cliente_id)
        if os.path.exists(path):
            raise ValueError(f"Cliente '{nome}' já existe")
        
        os.makedirs(path)
        
        cliente = Cliente(
            id=cliente_id,
            nome=nome,
            cnpj=cnpj,
            contato=contato,
            email=email,
            telefone=telefone
        )
        
        self._salvar_config_cliente(cliente)
        return cliente
    
    def _salvar_config_cliente(self, cliente: Cliente):
        """Salva configuração do cliente"""
        cliente.data_atualizacao = datetime.now().isoformat()
        
        path_config = os.path.join(self.data_dir, cliente.id, "config.json")
        os.makedirs(os.path.dirname(path_config), exist_ok=True)
        
        data = {
            "id": cliente.id,
            "nome": cliente.nome,
            "cnpj": cliente.cnpj,
            "contato": cliente.contato,
            "email": cliente.email,
            "telefone": cliente.telefone,
            "filiais": cliente.filiais,
            "premissas_macro": asdict(cliente.premissas_macro),
            "data_criacao": cliente.data_criacao,
            "data_atualizacao": cliente.data_atualizacao
        }
        
        with open(path_config, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def atualizar_cliente(self, cliente: Cliente):
        """Atualiza dados do cliente"""
        if self.supabase and cliente.supabase_id:
            try:
                self.supabase.table("companies").update({
                    "name": cliente.nome,
                    "cnpj": cliente.cnpj,
                    "email": cliente.email,
                    "telefone": cliente.telefone,
                    "contato": cliente.contato,
                    "premissas_macro": asdict(cliente.premissas_macro)
                }).eq("id", cliente.supabase_id).execute()
            except Exception as e:
                print(f"Erro ao atualizar cliente Supabase: {e}")
        
        self._salvar_config_cliente(cliente)
    
    def criar_filial(self, cliente_id: str, nome_filial: str) -> str:
        """Cria uma nova filial para o cliente"""
        cliente = self.carregar_cliente(cliente_id)
        if not cliente:
            raise ValueError(f"Cliente '{cliente_id}' não encontrado")
        
        filial_id = self._gerar_id(nome_filial)
        
        if filial_id in cliente.filiais:
            raise ValueError(f"Filial '{nome_filial}' já existe")
        
        # Dados iniciais da filial
        dados_filial = {
            "id": filial_id,
            "nome": nome_filial,
            "macro": {
                "ipca": 0.045,
                "igpm": 0.05,
                "dissidio": 0.06,
                "reajuste_tarifas": 0.08,
                "reajuste_contratos": 0.05,
                "taxa_cartao_credito": 0.0354,
                "taxa_cartao_debito": 0.0211,
                "taxa_antecipacao": 0.05
            },
            "operacional": {
                "num_fisioterapeutas": 0,
                "num_salas": 0,
                "horas_atendimento_dia": 0,
                "dias_uteis_mes": 22,
                "modelo_tributario": "PJ - Simples Nacional",
                "modo_calculo_sessoes": "servico"
            },
            "pagamento": {
                "dinheiro_pix": 0.0,
                "cartao_credito": 0.0,
                "cartao_debito": 0.0,
                "outros": 0.0,
                "pct_antecipacao": 0.0
            },
            "servicos": {},
            "valores_proprietario": {},
            "valores_profissional": {},
            "proprietarios": {},
            "profissionais": {},
            "despesas": {},
            "custo_pessoal_mensal": 0,
            "mes_dissidio": 5,
            "sazonalidade": [1.0] * 12,
            "premissas_folha": {
                "regime_tributario": "PJ - Simples Nacional",
                "deducao_dependente_ir": 189.59,
                "aliquota_fgts": 0.08,
                "desconto_vt_pct": 0.06,
                "dias_uteis_mes": 22,
                "mes_dissidio": 5,
                "pct_dissidio": 0.05
            },
            "funcionarios_clt": {},
            "socios_prolabore": {},
            "fisioterapeutas": {},
            "premissas_fisioterapeutas": {
                "percentual_padrao": 0.35,
                "modelo_remuneracao": "percentual",
                "usa_niveis": True,
                "percentuais_nivel": {1: 0.30, 2: 0.35, 3: 0.40, 4: 0.45, 5: 0.50}
            },
            "cadastro_salas": {
                "salas": {},
                "horas_funcionamento_dia": 8,
                "dias_uteis_mes": 22
            }
        }
        
        # Salva no Supabase (ou local)
        self.salvar_dados_filial(cliente_id, filial_id, dados_filial)
        
        # Atualiza lista de filiais
        cliente.filiais.append(filial_id)
        self.atualizar_cliente(cliente)
        
        return filial_id
    
    def excluir_filial(self, cliente_id: str, filial_id: str):
        """Exclui uma filial"""
        cliente = self.carregar_cliente(cliente_id)
        if not cliente:
            return
        
        if self.supabase and cliente.supabase_id:
            try:
                self.supabase.table("branches").update({
                    "is_active": False
                }).eq("company_id", cliente.supabase_id).eq("slug", filial_id).execute()
            except Exception as e:
                print(f"Erro ao excluir filial Supabase: {e}")
        
        # Remove da lista
        if filial_id in cliente.filiais:
            cliente.filiais.remove(filial_id)
            self.atualizar_cliente(cliente)
        
        # Remove arquivo local
        path_filial = os.path.join(self.data_dir, cliente_id, f"{filial_id}.json")
        if os.path.exists(path_filial):
            os.remove(path_filial)
    
    def excluir_cliente(self, cliente_id: str):
        """Exclui um cliente e todos os seus dados"""
        cliente = self.carregar_cliente(cliente_id)
        
        if self.supabase and cliente and cliente.supabase_id:
            try:
                # Soft delete no Supabase
                self.supabase.table("companies").update({
                    "is_active": False
                }).eq("id", cliente.supabase_id).execute()
            except Exception as e:
                print(f"Erro ao excluir cliente Supabase: {e}")
        
        # Remove local
        import shutil
        path = os.path.join(self.data_dir, cliente_id)
        if os.path.exists(path):
            shutil.rmtree(path)


# ============================================
# FUNÇÕES DE CONVERSÃO MOTOR ↔ DICT
# ============================================

def motor_para_dict(motor) -> Dict:
    """Converte MotorCalculo para dicionário serializável"""
    try:
        from motor_calculo import MotorCalculo
        
        dados = {
            # Serviços
            "servicos": {},
            "valores_proprietario": getattr(motor, 'valores_proprietario', {}),
            "valores_profissional": getattr(motor, 'valores_profissional', {}),
            
            # Equipe
            "proprietarios": {},
            "profissionais": {},
            
            # Despesas
            "despesas": {},
            
            # Premissas operacionais
            "operacional": {
                "num_fisioterapeutas": motor.num_fisioterapeutas,
                "num_salas": motor.num_salas,
                "horas_atendimento_dia": motor.horas_atendimento_dia,
                "dias_uteis_mes": motor.dias_uteis_mes,
                "modelo_tributario": motor.modelo_tributario,
                "modo_calculo_sessoes": getattr(motor, 'modo_calculo_sessoes', 'servico')
            },
            
            # Premissas macro
            "macro": {
                "ipca": motor.ipca,
                "igpm": motor.igpm,
                "dissidio": motor.dissidio,
                "reajuste_tarifas": motor.reajuste_tarifas,
                "reajuste_contratos": motor.reajuste_contratos,
                "taxa_cartao_credito": motor.taxa_cartao_credito,
                "taxa_cartao_debito": motor.taxa_cartao_debito,
                "taxa_antecipacao": motor.taxa_antecipacao
            },
            
            # Pagamento
            "pagamento": {
                "dinheiro_pix": motor.dinheiro_pix,
                "cartao_credito": motor.cartao_credito,
                "cartao_debito": motor.cartao_debito,
                "outros": motor.outros,
                "pct_antecipacao": motor.pct_antecipacao
            },
            
            # Outros
            "custo_pessoal_mensal": motor.custo_pessoal_mensal,
            "mes_dissidio": motor.mes_dissidio,
            "sazonalidade": motor.sazonalidade,
            
            # Folha
            "premissas_folha": getattr(motor, 'premissas_folha', {}),
            "funcionarios_clt": {},
            "socios_prolabore": {},
            "fisioterapeutas": {},
            "premissas_fisio": getattr(motor, 'premissas_fisio', {}),
            
            # Salas
            "cadastro_salas": getattr(motor, 'cadastro_salas', {}),
            
            # Simples
            "premissas_simples": getattr(motor, 'premissas_simples', {}),
            
            # Dividendos
            "premissas_dividendos": getattr(motor, 'premissas_dividendos', {}),
            
            # FC
            "premissas_fc": getattr(motor, 'premissas_fc', {}),
            
            # Aplicações
            "aplicacoes": getattr(motor, 'aplicacoes', {}),
            
            # Investimentos
            "investimentos": [],
            
            # Financiamentos
            "financiamentos": []
        }
        
        # Serializa serviços
        for nome, servico in motor.servicos.items():
            dados["servicos"][nome] = {
                "nome": servico.nome,
                "duracao_minutos": servico.duracao_minutos,
                "valor_2026": servico.valor_2026,
                "sessoes_mes_base": servico.sessoes_mes_base,
                "pct_reajuste": getattr(servico, 'pct_reajuste', 0),
                "mes_reajuste": getattr(servico, 'mes_reajuste', 1),
                "pct_crescimento": getattr(servico, 'pct_crescimento', 0),
                "usa_sala": getattr(servico, 'usa_sala', True)
            }
        
        # Serializa proprietários
        for nome, prop in getattr(motor, 'proprietarios', {}).items():
            dados["proprietarios"][nome] = {
                "nome": prop.nome,
                "tipo": "proprietario",
                "ativo": getattr(prop, 'ativo', True),
                "sessoes_por_servico": getattr(prop, 'sessoes_por_servico', {}),
                "pct_crescimento_por_servico": getattr(prop, 'pct_crescimento_por_servico', {})
            }
        
        # Serializa profissionais
        for nome, prof in getattr(motor, 'profissionais', {}).items():
            dados["profissionais"][nome] = {
                "nome": prof.nome,
                "tipo": "profissional",
                "ativo": getattr(prof, 'ativo', True),
                "sessoes_por_servico": getattr(prof, 'sessoes_por_servico', {}),
                "pct_crescimento_por_servico": getattr(prof, 'pct_crescimento_por_servico', {})
            }
        
        # Serializa despesas
        for nome, desp in motor.despesas_fixas.items():
            dados["despesas"][nome] = {
                "nome": desp.nome,
                "categoria": desp.categoria,
                "valor_mensal": desp.valor_mensal,
                "tipo_reajuste": desp.tipo_reajuste,
                "mes_reajuste": desp.mes_reajuste,
                "pct_adicional": getattr(desp, 'pct_adicional', 0),
                "aplicar_reajuste": getattr(desp, 'aplicar_reajuste', True),
                "tipo_sazonalidade": getattr(desp, 'tipo_sazonalidade', 'uniforme'),
                "valores_2025": getattr(desp, 'valores_2025', [desp.valor_mensal] * 12),
                "ativa": getattr(desp, 'ativa', True),
                "tipo_despesa": getattr(desp, 'tipo_despesa', 'fixa'),
                "base_variavel": getattr(desp, 'base_variavel', 'receita'),
                "pct_receita": getattr(desp, 'pct_receita', 0),
                "valor_por_sessao": getattr(desp, 'valor_por_sessao', 0)
            }
        
        # Serializa funcionários CLT
        for nome, func in getattr(motor, 'funcionarios_clt', {}).items():
            dados["funcionarios_clt"][nome] = {
                "nome": func.nome,
                "cargo": func.cargo,
                "salario_base": func.salario_base,
                "vale_transporte": getattr(func, 'vale_transporte', 0),
                "vale_refeicao": getattr(func, 'vale_refeicao', 0),
                "plano_saude": getattr(func, 'plano_saude', 0),
                "outros_beneficios": getattr(func, 'outros_beneficios', 0),
                "dependentes_ir": getattr(func, 'dependentes_ir', 0),
                "data_admissao": getattr(func, 'data_admissao', ''),
                "mes_reajuste": getattr(func, 'mes_reajuste', 5),
                "pct_aumento": getattr(func, 'pct_aumento', 0),
                "ativo": getattr(func, 'ativo', True)
            }
        
        # Serializa sócios
        for nome, socio in getattr(motor, 'socios_prolabore', {}).items():
            dados["socios_prolabore"][nome] = {
                "nome": socio.nome,
                "prolabore": socio.prolabore,
                "dependentes_ir": getattr(socio, 'dependentes_ir', 0),
                "mes_reajuste": getattr(socio, 'mes_reajuste', 5),
                "pct_aumento": getattr(socio, 'pct_aumento', 0),
                "ativo": getattr(socio, 'ativo', True)
            }
        
        # Serializa fisioterapeutas
        for nome, fisio in getattr(motor, 'fisioterapeutas', {}).items():
            dados["fisioterapeutas"][nome] = {
                "nome": fisio.nome,
                "cargo": getattr(fisio, 'cargo', 'Fisioterapeuta'),
                "nivel": getattr(fisio, 'nivel', 1),
                "filial": getattr(fisio, 'filial', ''),
                "ativo": getattr(fisio, 'ativo', True),
                "sessoes_por_servico": getattr(fisio, 'sessoes_por_servico', {}),
                "pct_crescimento_por_servico": getattr(fisio, 'pct_crescimento_por_servico', {}),
                "tipo_remuneracao": getattr(fisio, 'tipo_remuneracao', 'percentual'),
                "valores_fixos_por_servico": getattr(fisio, 'valores_fixos_por_servico', {}),
                "pct_customizado": getattr(fisio, 'pct_customizado', 0),
                "escala_semanal": getattr(fisio, 'escala_semanal', {})
            }
        
        # Serializa investimentos
        for inv in getattr(motor, 'investimentos', []):
            dados["investimentos"].append({
                "descricao": inv.descricao,
                "valor": inv.valor,
                "mes": inv.mes,
                "tipo": getattr(inv, 'tipo', 'equipamento'),
                "forma_pagamento": getattr(inv, 'forma_pagamento', 'avista'),
                "num_parcelas": getattr(inv, 'num_parcelas', 1)
            })
        
        # Serializa financiamentos
        for fin in getattr(motor, 'financiamentos', []):
            dados["financiamentos"].append({
                "descricao": fin.descricao,
                "saldo_devedor": fin.saldo_devedor,
                "taxa_mensal": fin.taxa_mensal,
                "parcelas_total": fin.parcelas_total,
                "parcelas_pagas": fin.parcelas_pagas,
                "mes_inicio_2026": getattr(fin, 'mes_inicio_2026', 1),
                "valor_parcela": getattr(fin, 'valor_parcela', 0),
                "ativo": getattr(fin, 'ativo', True)
            })
        
        return dados
        
    except Exception as e:
        print(f"Erro ao converter motor para dict: {e}")
        import traceback
        traceback.print_exc()
        return {}


def dict_para_motor(dados: Dict):
    """Converte dicionário para MotorCalculo"""
    try:
        from motor_calculo import (
            MotorCalculo, criar_motor_vazio, Servico, 
            DespesaFixa, FuncionarioCLT, Fisioterapeuta,
            Investimento, FinanciamentoExistente, Profissional
        )
        
        motor = criar_motor_vazio()
        
        # Premissas operacionais
        op = dados.get("operacional", {})
        motor.num_fisioterapeutas = op.get("num_fisioterapeutas", 0)
        motor.num_salas = op.get("num_salas", 0)
        motor.horas_atendimento_dia = op.get("horas_atendimento_dia", 0)
        motor.dias_uteis_mes = op.get("dias_uteis_mes", 22)
        motor.modelo_tributario = op.get("modelo_tributario", "PJ - Simples Nacional")
        motor.modo_calculo_sessoes = op.get("modo_calculo_sessoes", "servico")
        
        # Premissas macro
        macro = dados.get("macro", {})
        motor.ipca = macro.get("ipca", 0.045)
        motor.igpm = macro.get("igpm", 0.05)
        motor.dissidio = macro.get("dissidio", 0.06)
        motor.reajuste_tarifas = macro.get("reajuste_tarifas", 0.08)
        motor.reajuste_contratos = macro.get("reajuste_contratos", 0.05)
        motor.taxa_cartao_credito = macro.get("taxa_cartao_credito", 0.0354)
        motor.taxa_cartao_debito = macro.get("taxa_cartao_debito", 0.0211)
        motor.taxa_antecipacao = macro.get("taxa_antecipacao", 0.05)
        
        # Pagamento
        pag = dados.get("pagamento", {})
        motor.dinheiro_pix = pag.get("dinheiro_pix", 0)
        motor.cartao_credito = pag.get("cartao_credito", 0)
        motor.cartao_debito = pag.get("cartao_debito", 0)
        motor.outros = pag.get("outros", 0)
        motor.pct_antecipacao = pag.get("pct_antecipacao", 0)
        
        # Outros
        motor.custo_pessoal_mensal = dados.get("custo_pessoal_mensal", 0)
        motor.mes_dissidio = dados.get("mes_dissidio", 5)
        motor.sazonalidade = dados.get("sazonalidade", [1.0] * 12)
        
        # Premissas específicas
        motor.premissas_folha = dados.get("premissas_folha", {})
        motor.premissas_fisio = dados.get("premissas_fisio", {})
        motor.cadastro_salas = dados.get("cadastro_salas", {})
        motor.premissas_simples = dados.get("premissas_simples", {})
        motor.premissas_dividendos = dados.get("premissas_dividendos", {})
        motor.premissas_fc = dados.get("premissas_fc", {})
        motor.aplicacoes = dados.get("aplicacoes", {})
        
        # Valores por tipo de profissional
        motor.valores_proprietario = dados.get("valores_proprietario", {})
        motor.valores_profissional = dados.get("valores_profissional", {})
        
        # Serviços
        motor.servicos = {}
        for nome, srv_data in dados.get("servicos", {}).items():
            motor.servicos[nome] = Servico(
                nome=srv_data.get("nome", nome),
                duracao_minutos=srv_data.get("duracao_minutos", 60),
                valor_2026=srv_data.get("valor_2026", 0),
                sessoes_mes_base=srv_data.get("sessoes_mes_base", 0),
                pct_reajuste=srv_data.get("pct_reajuste", 0),
                mes_reajuste=srv_data.get("mes_reajuste", 1),
                pct_crescimento=srv_data.get("pct_crescimento", 0),
                usa_sala=srv_data.get("usa_sala", True)
            )
        
        # Proprietários
        motor.proprietarios = {}
        for nome, prop_data in dados.get("proprietarios", {}).items():
            motor.proprietarios[nome] = Profissional(
                nome=prop_data.get("nome", nome),
                tipo="proprietario",
                ativo=prop_data.get("ativo", True),
                sessoes_por_servico=prop_data.get("sessoes_por_servico", {}),
                pct_crescimento_por_servico=prop_data.get("pct_crescimento_por_servico", {})
            )
        
        # Profissionais
        motor.profissionais = {}
        for nome, prof_data in dados.get("profissionais", {}).items():
            motor.profissionais[nome] = Profissional(
                nome=prof_data.get("nome", nome),
                tipo="profissional",
                ativo=prof_data.get("ativo", True),
                sessoes_por_servico=prof_data.get("sessoes_por_servico", {}),
                pct_crescimento_por_servico=prof_data.get("pct_crescimento_por_servico", {})
            )
        
        # Despesas
        motor.despesas_fixas = {}
        for nome, desp_data in dados.get("despesas", {}).items():
            motor.despesas_fixas[nome] = DespesaFixa(
                nome=desp_data.get("nome", nome),
                categoria=desp_data.get("categoria", "Outros"),
                valor_mensal=desp_data.get("valor_mensal", 0),
                tipo_reajuste=desp_data.get("tipo_reajuste", "nenhum"),
                mes_reajuste=desp_data.get("mes_reajuste", 1),
                pct_adicional=desp_data.get("pct_adicional", 0),
                aplicar_reajuste=desp_data.get("aplicar_reajuste", True),
                tipo_sazonalidade=desp_data.get("tipo_sazonalidade", "uniforme"),
                valores_2025=desp_data.get("valores_2025", []),
                ativa=desp_data.get("ativa", True),
                tipo_despesa=desp_data.get("tipo_despesa", "fixa"),
                base_variavel=desp_data.get("base_variavel", "receita"),
                pct_receita=desp_data.get("pct_receita", 0),
                valor_por_sessao=desp_data.get("valor_por_sessao", 0)
            )
        
        # Funcionários CLT
        motor.funcionarios_clt = {}
        for nome, func_data in dados.get("funcionarios_clt", {}).items():
            motor.funcionarios_clt[nome] = FuncionarioCLT(
                nome=func_data.get("nome", nome),
                cargo=func_data.get("cargo", ""),
                salario_base=func_data.get("salario_base", 0),
                vale_transporte=func_data.get("vale_transporte", 0),
                vale_refeicao=func_data.get("vale_refeicao", 0),
                plano_saude=func_data.get("plano_saude", 0),
                outros_beneficios=func_data.get("outros_beneficios", 0),
                dependentes_ir=func_data.get("dependentes_ir", 0),
                data_admissao=func_data.get("data_admissao", ""),
                mes_reajuste=func_data.get("mes_reajuste", 5),
                pct_aumento=func_data.get("pct_aumento", 0),
                ativo=func_data.get("ativo", True)
            )
        
        # Sócios pró-labore
        motor.socios_prolabore = {}
        for nome, socio_data in dados.get("socios_prolabore", {}).items():
            from dataclasses import dataclass
            @dataclass
            class SocioProlabore:
                nome: str
                prolabore: float
                dependentes_ir: int = 0
                mes_reajuste: int = 5
                pct_aumento: float = 0
                ativo: bool = True
            
            motor.socios_prolabore[nome] = SocioProlabore(
                nome=socio_data.get("nome", nome),
                prolabore=socio_data.get("prolabore", 0),
                dependentes_ir=socio_data.get("dependentes_ir", 0),
                mes_reajuste=socio_data.get("mes_reajuste", 5),
                pct_aumento=socio_data.get("pct_aumento", 0),
                ativo=socio_data.get("ativo", True)
            )
        
        # Fisioterapeutas
        motor.fisioterapeutas = {}
        for nome, fisio_data in dados.get("fisioterapeutas", {}).items():
            motor.fisioterapeutas[nome] = Fisioterapeuta(
                nome=fisio_data.get("nome", nome),
                cargo=fisio_data.get("cargo", "Fisioterapeuta"),
                nivel=fisio_data.get("nivel", 1),
                filial=fisio_data.get("filial", ""),
                ativo=fisio_data.get("ativo", True),
                sessoes_por_servico=fisio_data.get("sessoes_por_servico", {}),
                pct_crescimento_por_servico=fisio_data.get("pct_crescimento_por_servico", {}),
                tipo_remuneracao=fisio_data.get("tipo_remuneracao", "percentual"),
                valores_fixos_por_servico=fisio_data.get("valores_fixos_por_servico", {}),
                pct_customizado=fisio_data.get("pct_customizado", 0),
                escala_semanal=fisio_data.get("escala_semanal", {})
            )
        
        # Investimentos
        motor.investimentos = []
        for inv_data in dados.get("investimentos", []):
            motor.investimentos.append(Investimento(
                descricao=inv_data.get("descricao", ""),
                valor=inv_data.get("valor", 0),
                mes=inv_data.get("mes", 1),
                tipo=inv_data.get("tipo", "equipamento"),
                forma_pagamento=inv_data.get("forma_pagamento", "avista"),
                num_parcelas=inv_data.get("num_parcelas", 1)
            ))
        
        # Financiamentos
        motor.financiamentos = []
        for fin_data in dados.get("financiamentos", []):
            motor.financiamentos.append(FinanciamentoExistente(
                descricao=fin_data.get("descricao", ""),
                saldo_devedor=fin_data.get("saldo_devedor", 0),
                taxa_mensal=fin_data.get("taxa_mensal", 0),
                parcelas_total=fin_data.get("parcelas_total", 0),
                parcelas_pagas=fin_data.get("parcelas_pagas", 0),
                mes_inicio_2026=fin_data.get("mes_inicio_2026", 1),
                valor_parcela=fin_data.get("valor_parcela", 0),
                ativo=fin_data.get("ativo", True)
            ))
        
        return motor
        
    except Exception as e:
        print(f"Erro ao converter dict para motor: {e}")
        import traceback
        traceback.print_exc()
        from motor_calculo import criar_motor_vazio
        return criar_motor_vazio()
