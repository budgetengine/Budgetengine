"""
Gerenciador de Clientes e Filiais
Sistema multi-tenant para consultoria
COM SUPABASE - Salva dados no banco de dados
"""

import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
from datetime import datetime

# ============================================
# SUPABASE - Conexão com banco de dados
# ============================================
try:
    import streamlit as st
    from supabase import create_client
    SUPABASE_DISPONIVEL = True
except ImportError:
    SUPABASE_DISPONIVEL = False

# v1.99.74: Singleton para evitar "Too many open files"
_supabase_client = None

def _conectar_supabase():
    """Conecta ao Supabase se disponível - USA SINGLETON para evitar vazamento"""
    global _supabase_client

    if not SUPABASE_DISPONIVEL:
        print("[SUPABASE] Biblioteca não disponível")
        return None

    # Reutiliza conexão existente
    if _supabase_client is not None:
        return _supabase_client

    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        _supabase_client = create_client(url, key)
        print(f"[SUPABASE] ✅ Conectado (singleton)!")
        return _supabase_client
    except Exception as e:
        print(f"[SUPABASE] ❌ Erro ao conectar: {e}")
        return None

def _obter_supabase():
    """Obtém conexão Supabase - REUTILIZA singleton"""
    return _conectar_supabase()


def sincronizar_do_supabase(data_dir: str = "data/clientes") -> Dict:
    """
    SINCRONIZAÇÃO COMPLETA: Baixa todos os dados do Supabase para o local.
    Atualiza config.json e arquivos de filiais.

    Returns:
        Dict com estatísticas: {"clientes": n, "filiais": n, "erros": []}
    """
    stats = {"clientes": 0, "filiais": 0, "erros": [], "atualizados": []}

    supabase = _obter_supabase()
    if not supabase:
        stats["erros"].append("Supabase não disponível")
        return stats

    try:
        # Busca todas as companies
        resp_companies = supabase.table("companies").select("*").execute()

        for company in resp_companies.data:
            company_id = company["id"]
            company_name = company["name"].strip()

            # Gera slug do cliente
            import re
            cliente_id = company_name.lower()
            cliente_id = re.sub(r'[áàãâä]', 'a', cliente_id)
            cliente_id = re.sub(r'[éèêë]', 'e', cliente_id)
            cliente_id = re.sub(r'[íìîï]', 'i', cliente_id)
            cliente_id = re.sub(r'[óòõôö]', 'o', cliente_id)
            cliente_id = re.sub(r'[úùûü]', 'u', cliente_id)
            cliente_id = re.sub(r'[ç]', 'c', cliente_id)
            cliente_id = re.sub(r'[^a-z0-9]', '_', cliente_id)
            cliente_id = re.sub(r'_+', '_', cliente_id).strip('_')

            # Cria diretório do cliente
            cliente_path = os.path.join(data_dir, cliente_id)
            os.makedirs(cliente_path, exist_ok=True)

            # Busca filiais desta company
            resp_branches = supabase.table("branches").select("*").eq("company_id", company_id).execute()

            filiais_ids = []
            for branch in resp_branches.data:
                filial_id = branch["slug"]
                filiais_ids.append(filial_id)

                # Salva dados da filial localmente
                if branch.get("data"):
                    filial_path = os.path.join(cliente_path, f"{filial_id}.json")
                    with open(filial_path, 'w', encoding='utf-8') as f:
                        json.dump(branch["data"], f, ensure_ascii=False, indent=2)
                    stats["filiais"] += 1
                    stats["atualizados"].append(f"{cliente_id}/{filial_id}")
                    print(f"[SYNC] ✅ {cliente_id}/{filial_id} atualizado")

            # Atualiza config.json do cliente
            config_path = os.path.join(cliente_path, "config.json")
            config = {
                "id": cliente_id,
                "nome": company_name,
                "cnpj": company.get("cnpj", ""),
                "contato": "",
                "email": "",
                "telefone": "",
                "filiais": filiais_ids,
                "premissas_macro": {
                    "ipca": 0.045,
                    "igpm": 0.05,
                    "dissidio": 0.06,
                    "reajuste_tarifas": 0.08,
                    "reajuste_contratos": 0.05,
                    "taxa_credito": 0.0354,
                    "taxa_debito": 0.0211,
                    "taxa_antecipacao": 0.05
                },
                "data_criacao": company.get("created_at", datetime.now().isoformat()),
                "data_atualizacao": datetime.now().isoformat()
            }

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

            stats["clientes"] += 1
            print(f"[SYNC] ✅ Cliente {cliente_id} com {len(filiais_ids)} filiais")

    except Exception as e:
        stats["erros"].append(str(e))
        print(f"[SYNC] ❌ Erro: {e}")

    return stats


# Adiciona diretório pai ao path para imports do motor_calculo
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


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
    
    def __post_init__(self):
        if not self.data_criacao:
            self.data_criacao = datetime.now().isoformat()
        self.data_atualizacao = datetime.now().isoformat()


class ClienteManager:
    """Gerencia clientes e seus dados"""
    
    def __init__(self, data_dir: str = "data/clientes"):
        self.data_dir = data_dir
        self.supabase = _conectar_supabase()
        self._garantir_diretorio()
    
    def _garantir_diretorio(self):
        """Cria diretório de dados se não existir"""
        os.makedirs(self.data_dir, exist_ok=True)
    
    def _path_cliente(self, cliente_id: str) -> str:
        """Retorna caminho da pasta do cliente"""
        return os.path.join(self.data_dir, cliente_id)
    
    def _path_config(self, cliente_id: str) -> str:
        """Retorna caminho do arquivo de configuração do cliente"""
        return os.path.join(self._path_cliente(cliente_id), "config.json")
    
    def _path_filial(self, cliente_id: str, filial_id: str) -> str:
        """Retorna caminho do arquivo de dados da filial"""
        return os.path.join(self._path_cliente(cliente_id), f"{filial_id}.json")
    
    def _gerar_id(self, nome: str) -> str:
        """Gera ID a partir do nome"""
        import re
        # Remove acentos e caracteres especiais
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
    
    def listar_clientes(self) -> List[Dict]:
        """Lista todos os clientes"""
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
    
    def criar_cliente(self, nome: str, cnpj: str = "", contato: str = "", 
                      email: str = "", telefone: str = "") -> Cliente:
        """Cria um novo cliente"""
        cliente_id = self._gerar_id(nome)
        
        # Verifica se já existe
        path = self._path_cliente(cliente_id)
        if os.path.exists(path):
            raise ValueError(f"Cliente '{nome}' já existe")
        
        # Cria diretório
        os.makedirs(path)
        
        # Cria cliente
        cliente = Cliente(
            id=cliente_id,
            nome=nome,
            cnpj=cnpj,
            contato=contato,
            email=email,
            telefone=telefone
        )
        
        # Salva configuração
        self._salvar_config_cliente(cliente)
        
        return cliente
    
    def carregar_cliente(self, cliente_id: str) -> Optional[Cliente]:
        """Carrega dados de um cliente"""
        path_config = self._path_config(cliente_id)
        
        if not os.path.exists(path_config):
            return None
        
        try:
            with open(path_config, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstrói premissas
            premissas_data = data.get("premissas_macro", {})
            premissas = PremissasMacroCliente(**premissas_data)
            
            cliente = Cliente(
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
            
            return cliente
        except Exception as e:
            print(f"Erro ao carregar cliente: {e}")
            return None
    
    def _salvar_config_cliente(self, cliente: Cliente):
        """Salva configuração do cliente"""
        cliente.data_atualizacao = datetime.now().isoformat()
        
        path_config = self._path_config(cliente.id)
        
        # Converte para dicionário
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
        self._salvar_config_cliente(cliente)
    
    def excluir_cliente(self, cliente_id: str):
        """Exclui um cliente e todos os seus dados"""
        import shutil
        path = self._path_cliente(cliente_id)
        if os.path.exists(path):
            shutil.rmtree(path)
    
    # ========== FILIAIS ==========
    
    def criar_filial(self, cliente_id: str, nome_filial: str) -> str:
        """Cria uma nova filial para o cliente"""
        cliente = self.carregar_cliente(cliente_id)
        if not cliente:
            raise ValueError(f"Cliente '{cliente_id}' não encontrado")
        
        filial_id = self._gerar_id(nome_filial)
        
        if filial_id in cliente.filiais:
            raise ValueError(f"Filial '{nome_filial}' já existe")
        
        # Adiciona à lista de filiais
        cliente.filiais.append(filial_id)
        self._salvar_config_cliente(cliente)
        
        # CORREÇÃO: Cria arquivo da filial com TODOS os campos necessários
        # incluindo macro, operacional, pagamento para garantir persistência
        dados_filial = {
            "id": filial_id,
            "nome": nome_filial,
            # Premissas Macro (NOVO!)
            "macro": {
                "ipca": 0.0,
                "igpm": 0.0,
                "dissidio": 0.0,
                "reajuste_tarifas": 0.0,
                "reajuste_contratos": 0.0,
                "taxa_cartao_credito": 0.0354,
                "taxa_cartao_debito": 0.0211,
                "taxa_antecipacao": 0.05
            },
            # Premissas Operacionais (NOVO!)
            "operacional": {
                "num_fisioterapeutas": 0,
                "num_salas": 0,
                "horas_atendimento_dia": 0,
                "dias_uteis_mes": 0,
                "modelo_tributario": "PJ - Simples Nacional",
                "modo_calculo_sessoes": "servico"
            },
            # Formas de Pagamento (NOVO!)
            "pagamento": {
                "dinheiro_pix": 0.0,
                "cartao_credito": 0.0,
                "cartao_debito": 0.0,
                "outros": 0.0,
                "pct_antecipacao": 0.0
            },
            # Dados de serviços e equipe
            "servicos": {},
            "valores_proprietario": {},
            "valores_profissional": {},
            "proprietarios": {},
            "profissionais": {},
            "despesas": {},
            "custo_pessoal_mensal": 0,
            "mes_dissidio": 5,
            "sazonalidade": [1.0] * 12,
            # Premissas de Folha (NOVO!)
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
                "horas_funcionamento_dia": 0,
                "dias_uteis_mes": 22
            }
        }
        
        path_filial = self._path_filial(cliente_id, filial_id)
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(path_filial), exist_ok=True)
        with open(path_filial, 'w', encoding='utf-8') as f:
            json.dump(dados_filial, f, ensure_ascii=False, indent=2)
        
        return filial_id
    
    def carregar_filial(self, cliente_id: str, filial_id: str) -> Optional[Dict]:
        """Carrega dados de uma filial (Supabase primeiro, depois JSON local)"""

        # ============================================
        # TENTA CARREGAR DO SUPABASE PRIMEIRO
        # ============================================
        # SEMPRE cria nova conexão para evitar timeout
        supabase = _obter_supabase()

        if supabase:
            try:
                # Busca company_id pelo nome do cliente
                print(f"[LOAD] Buscando company: {cliente_id}")
                resp_company = supabase.table("companies").select("id").ilike("name", f"%{cliente_id.replace('_', ' ')}%").execute()

                if resp_company.data:
                    company_id = resp_company.data[0]["id"]
                    print(f"[LOAD] Company encontrada: {company_id}")

                    # Busca filial
                    resp_branch = supabase.table("branches").select("data").eq("company_id", company_id).eq("slug", filial_id).execute()

                    if resp_branch.data and resp_branch.data[0].get("data"):
                        print(f"[LOAD] ✅ Dados carregados do Supabase para {filial_id}")
                        return resp_branch.data[0]["data"]
                    else:
                        print(f"[LOAD] ⚠️ Branch {filial_id} não encontrada no Supabase")
                else:
                    print(f"[LOAD] ⚠️ Company {cliente_id} não encontrada no Supabase")
            except Exception as e:
                print(f"[LOAD] ❌ Erro ao carregar do Supabase: {e}")
        else:
            print(f"[LOAD] ⚠️ Supabase não configurado")
        
        # ============================================
        # FALLBACK: JSON LOCAL
        # ============================================
        path_filial = self._path_filial(cliente_id, filial_id)
        print(f"[LOAD] Tentando JSON local: {path_filial}")
        
        if not os.path.exists(path_filial):
            print(f"[LOAD] ❌ Arquivo local não existe")
            return None
        
        try:
            with open(path_filial, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                print(f"[LOAD] ✅ Dados carregados do JSON local")
                return dados
        except Exception as e:
            print(f"[LOAD] ❌ Erro ao carregar JSON local: {e}")
            return None
    
    def salvar_filial(self, cliente_id: str, filial_id: str, dados: Dict) -> bool:
        """Salva dados de uma filial (JSON local + Supabase). Retorna True se sucesso."""
        path_filial = self._path_filial(cliente_id, filial_id)
        sucesso_local = False
        sucesso_supabase = False
        
        # CORREÇÃO: Garantir que o diretório existe antes de salvar
        os.makedirs(os.path.dirname(path_filial), exist_ok=True)
        
        # Salva JSON local (backup)
        try:
            with open(path_filial, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            sucesso_local = True
            print(f"[SAVE] JSON local salvo: {path_filial}")
        except Exception as e:
            print(f"[SAVE] Erro ao salvar localmente: {e}")
        
        # ============================================
        # SALVA NO SUPABASE
        # ============================================
        # SEMPRE cria nova conexão para evitar timeout
        supabase = _obter_supabase()

        if supabase:
            try:
                # Busca company_id pelo nome do cliente
                print(f"[SAVE] Buscando company: {cliente_id}")
                resp_company = supabase.table("companies").select("id").ilike("name", f"%{cliente_id.replace('_', ' ')}%").execute()

                if resp_company.data:
                    company_id = resp_company.data[0]["id"]
                    print(f"[SAVE] Company encontrada: {company_id}")

                    # Verifica se filial já existe
                    resp_branch = supabase.table("branches").select("id").eq("company_id", company_id).eq("slug", filial_id).execute()

                    if resp_branch.data:
                        # UPDATE
                        print(f"[SAVE] Atualizando branch: {resp_branch.data[0]['id']}")
                        supabase.table("branches").update({
                            "data": dados,
                            "updated_at": datetime.now().isoformat()
                        }).eq("id", resp_branch.data[0]["id"]).execute()
                        sucesso_supabase = True
                        print(f"[SAVE] ✅ Branch atualizada!")
                    else:
                        # INSERT
                        print(f"[SAVE] Inserindo nova branch: {filial_id}")
                        supabase.table("branches").insert({
                            "company_id": company_id,
                            "name": filial_id.replace("_", " ").title(),
                            "slug": filial_id,
                            "is_active": True,
                            "data": dados
                        }).execute()
                        sucesso_supabase = True
                        print(f"[SAVE] ✅ Branch inserida!")
                else:
                    print(f"[SAVE] ⚠️ Cliente '{cliente_id}' NÃO encontrado no Supabase!")
            except Exception as e:
                print(f"[SAVE] ❌ Erro ao salvar no Supabase: {e}")
        else:
            print(f"[SAVE] ⚠️ Supabase não configurado")
            # Sem Supabase, considera sucesso se salvou localmente
            sucesso_supabase = sucesso_local
        
        resultado = sucesso_local or sucesso_supabase
        print(f"[SAVE] Resultado final: local={sucesso_local}, supabase={sucesso_supabase}, final={resultado}")
        return resultado
    
    def excluir_filial(self, cliente_id: str, filial_id: str):
        """Exclui uma filial"""
        cliente = self.carregar_cliente(cliente_id)
        if not cliente:
            return
        
        if filial_id in cliente.filiais:
            cliente.filiais.remove(filial_id)
            self._salvar_config_cliente(cliente)
        
        path_filial = self._path_filial(cliente_id, filial_id)
        if os.path.exists(path_filial):
            os.remove(path_filial)
    
    def listar_filiais(self, cliente_id: str) -> List[Dict]:
        """Lista filiais de um cliente"""
        cliente = self.carregar_cliente(cliente_id)
        if not cliente:
            return []
        
        filiais = []
        for filial_id in cliente.filiais:
            dados = self.carregar_filial(cliente_id, filial_id)
            if dados:
                filiais.append({
                    "id": filial_id,
                    "nome": dados.get("nome", filial_id)
                })
        
        return filiais


def motor_para_dict(motor) -> Dict:
    """Converte MotorCalculo para dicionário (para salvar)"""
    from dataclasses import asdict
    
    dados = {
        "servicos": {},
        "valores_proprietario": motor.valores_proprietario,
        "valores_profissional": motor.valores_profissional,
        "proprietarios": {},
        "profissionais": {},
        "despesas": {},
        "custo_pessoal_mensal": motor.custo_pessoal_mensal,
        "mes_dissidio": motor.mes_dissidio,
        "sazonalidade": motor.sazonalidade.fatores
    }
    
    # NOVO: Premissas Operacionais
    dados["operacional"] = {
        "num_fisioterapeutas": motor.operacional.num_fisioterapeutas,
        "num_salas": motor.operacional.num_salas,
        "horas_atendimento_dia": motor.operacional.horas_atendimento_dia,
        "dias_uteis_mes": motor.operacional.dias_uteis_mes,
        "modelo_tributario": getattr(motor.operacional, 'modelo_tributario', 'PJ - Simples Nacional'),
        "modo_calculo_sessoes": getattr(motor.operacional, 'modo_calculo_sessoes', 'servico')
    }
    
    # NOVO v1.79.0: Cadastro de Salas (TDABC)
    dados["cadastro_salas"] = motor.cadastro_salas.to_dict()
    
    # NOVO: Premissas Macro
    dados["macro"] = {
        "ipca": motor.macro.ipca,
        "igpm": motor.macro.igpm,
        "dissidio": motor.macro.dissidio,
        "reajuste_tarifas": motor.macro.reajuste_tarifas,
        "reajuste_contratos": motor.macro.reajuste_contratos,
        "taxa_cartao_credito": motor.macro.taxa_cartao_credito,
        "taxa_cartao_debito": motor.macro.taxa_cartao_debito,
        "taxa_antecipacao": motor.macro.taxa_antecipacao
    }
    
    # NOVO: Formas de Pagamento
    dados["pagamento"] = {
        "dinheiro_pix": motor.pagamento.dinheiro_pix,
        "cartao_credito": motor.pagamento.cartao_credito,
        "cartao_debito": motor.pagamento.cartao_debito,
        "outros": motor.pagamento.outros,
        "pct_antecipacao": motor.pagamento.pct_antecipacao
    }
    
    # Serviços
    for nome, srv in motor.servicos.items():
        dados["servicos"][nome] = {
            "nome": srv.nome,
            "duracao_minutos": srv.duracao_minutos,
            "valor_2026": srv.valor_2026,
            "sessoes_mes_base": srv.sessoes_mes_base,
            "pct_reajuste": srv.pct_reajuste,
            "mes_reajuste": srv.mes_reajuste,
            "pct_crescimento": srv.pct_crescimento,
            "usa_sala": srv.usa_sala
        }
    
    # Proprietários
    for nome, prop in motor.proprietarios.items():
        dados["proprietarios"][nome] = {
            "nome": prop.nome,
            "tipo": prop.tipo,
            "ativo": prop.ativo,
            "sessoes_por_servico": prop.sessoes_por_servico,
            "pct_crescimento_por_servico": prop.pct_crescimento_por_servico
        }
    
    # Profissionais
    for nome, prof in motor.profissionais.items():
        dados["profissionais"][nome] = {
            "nome": prof.nome,
            "tipo": prof.tipo,
            "ativo": prof.ativo,
            "sessoes_por_servico": prof.sessoes_por_servico,
            "pct_crescimento_por_servico": prof.pct_crescimento_por_servico
        }
    
    # Despesas (é um dicionário, não lista)
    for nome, desp in motor.despesas_fixas.items():
        dados["despesas"][nome] = {
            "nome": desp.nome,
            "categoria": desp.categoria,
            "valor_mensal": desp.valor_mensal,
            "tipo_reajuste": desp.tipo_reajuste,
            "mes_reajuste": desp.mes_reajuste,
            "pct_adicional": desp.pct_adicional,
            "aplicar_reajuste": desp.aplicar_reajuste,
            "tipo_sazonalidade": desp.tipo_sazonalidade,
            "valores_2025": desp.valores_2025,
            "ativa": desp.ativa,
            # Campos de despesas variáveis
            "tipo_despesa": getattr(desp, 'tipo_despesa', 'fixa'),
            "base_variavel": getattr(desp, 'base_variavel', 'receita'),
            "pct_receita": getattr(desp, 'pct_receita', 0.0),
            "valor_por_sessao": getattr(desp, 'valor_por_sessao', 0.0)
        }
    
    # Premissas Folha
    pf = motor.premissas_folha
    dados["premissas_folha"] = {
        "regime_tributario": pf.regime_tributario,
        "deducao_dependente_ir": pf.deducao_dependente_ir,
        "aliquota_fgts": pf.aliquota_fgts,
        "desconto_vt_pct": pf.desconto_vt_pct,
        "dias_uteis_mes": pf.dias_uteis_mes,
        "mes_dissidio": pf.mes_dissidio,
        "pct_dissidio": pf.pct_dissidio
    }
    
    # Funcionários CLT
    dados["funcionarios_clt"] = {}
    for nome, func in motor.funcionarios_clt.items():
        dados["funcionarios_clt"][nome] = {
            "nome": func.nome,
            "cargo": func.cargo,
            "salario_base": func.salario_base,
            "tipo_vinculo": func.tipo_vinculo,
            "dependentes_ir": func.dependentes_ir,
            "vt_dia": func.vt_dia,
            "vr_dia": func.vr_dia,
            "plano_saude": func.plano_saude,
            "plano_odonto": func.plano_odonto,
            "mes_admissao": func.mes_admissao,
            "mes_aumento": func.mes_aumento,
            "pct_reajuste": func.pct_reajuste,
            "ativo": func.ativo
        }
    
    # Sócios Pró-Labore
    dados["socios_prolabore"] = {}
    for nome, socio in motor.socios_prolabore.items():
        dados["socios_prolabore"][nome] = {
            "nome": socio.nome,
            "prolabore": socio.prolabore,
            "dependentes_ir": socio.dependentes_ir,
            "mes_reajuste": socio.mes_reajuste,
            "pct_aumento": socio.pct_aumento,
            "ativo": socio.ativo
        }
    
    # Fisioterapeutas
    dados["fisioterapeutas"] = {}
    for nome, fisio in motor.fisioterapeutas.items():
        dados["fisioterapeutas"][nome] = {
            "nome": fisio.nome,
            "cargo": fisio.cargo,
            "nivel": fisio.nivel,
            "filial": fisio.filial,
            "ativo": fisio.ativo,
            "sessoes_por_servico": fisio.sessoes_por_servico,
            "pct_crescimento_por_servico": fisio.pct_crescimento_por_servico,
            "tipo_remuneracao": fisio.tipo_remuneracao,
            "valores_fixos_por_servico": fisio.valores_fixos_por_servico,
            "pct_customizado": getattr(fisio, 'pct_customizado', 0.0),
            # v1.79.0: Escala semanal para taxa de ocupação
            "escala_semanal": fisio.escala_semanal
        }
    
    # Premissas Fisioterapeutas
    pf = motor.premissas_fisio
    dados["premissas_fisio"] = {
        "niveis_remuneracao": pf.niveis_remuneracao,
        "pct_producao_propria": pf.pct_producao_propria,
        "pct_faturamento_total": pf.pct_faturamento_total,
        "pct_base_remuneracao_prop": pf.pct_base_remuneracao_prop,
        "pct_gerencia_equipe": pf.pct_gerencia_equipe,
        "pct_base_remuneracao_ger": pf.pct_base_remuneracao_ger
    }
    
    # NOVO: Premissas Simples Nacional / Carnê Leão
    ps = motor.premissas_simples
    dados["premissas_simples"] = {
        "faturamento_pf_anual": ps.faturamento_pf_anual,
        "aliquota_inss_pf": ps.aliquota_inss_pf,
        "teto_inss_pf": ps.teto_inss_pf,
        "limite_fator_r": ps.limite_fator_r
    }
    
    # NOVO: Premissas Dividendos
    pd = motor.premissas_dividendos
    dados["premissas_dividendos"] = {
        "distribuir": pd.distribuir,
        "pct_reserva_legal": pd.pct_reserva_legal,
        "pct_reserva_investimento": pd.pct_reserva_investimento,
        "frequencia": pd.frequencia,
        "pct_distribuir": pd.pct_distribuir,
        "mostrar_no_dre": pd.mostrar_no_dre
    }
    
    # Premissas FC
    pfc = motor.premissas_fc
    dados["premissas_fc"] = {
        "caixa_inicial": pfc.caixa_inicial,
        "cp_impostos": pfc.cp_impostos,
        "cp_folha_colaboradores": pfc.cp_folha_colaboradores,
        "cp_folha_fisioterapeutas": pfc.cp_folha_fisioterapeutas,
        "cp_retirada_proprietarios": pfc.cp_retirada_proprietarios,
        "cp_encargos_clt": pfc.cp_encargos_clt,
        "cp_fornecedores": pfc.cp_fornecedores,
        "usar_cp_folha_auto": pfc.usar_cp_folha_auto,
        "receita_out_ano_anterior": pfc.receita_out_ano_anterior,
        "receita_nov_ano_anterior": pfc.receita_nov_ano_anterior,
        "receita_dez_ano_anterior": pfc.receita_dez_ano_anterior,
        "usar_receita_auto": pfc.usar_receita_auto,
        "recebimento_avista_no_mes": pfc.recebimento_avista_no_mes,
        "saldo_minimo": pfc.saldo_minimo,
        "pct_cartao_1x": pfc.pct_cartao_1x,
        "pct_cartao_2x": pfc.pct_cartao_2x,
        "pct_cartao_3x": pfc.pct_cartao_3x,
        "pct_cartao_4x": pfc.pct_cartao_4x,
        "pct_cartao_5x": pfc.pct_cartao_5x,
        "pct_cartao_6x": pfc.pct_cartao_6x,
    }
    
    # Aplicações Financeiras
    aplic = motor.premissas_financeiras.aplicacoes
    dados["aplicacoes"] = {
        "saldo_inicial": aplic.saldo_inicial,
        "taxa_selic_anual": aplic.taxa_selic_anual,
        "pct_cdi": aplic.pct_cdi,
    }
    
    # Investimentos (CAPEX)
    dados["investimentos"] = []
    for inv in motor.premissas_financeiras.investimentos:
        dados["investimentos"].append({
            "descricao": inv.descricao,
            "categoria": inv.categoria,
            "valor_total": inv.valor_total,
            "mes_aquisicao": inv.mes_aquisicao,
            "entrada": inv.entrada,
            "taxa_mensal": inv.taxa_mensal,
            "parcelas": inv.parcelas,
            "beneficio_mensal": inv.beneficio_mensal,
            "ativo": inv.ativo,
        })
    
    # Financiamentos Existentes
    dados["financiamentos"] = []
    for fin in motor.premissas_financeiras.financiamentos:
        dados["financiamentos"].append({
            "descricao": fin.descricao,
            "saldo_devedor": fin.saldo_devedor,
            "taxa_mensal": fin.taxa_mensal,
            "parcelas_total": fin.parcelas_total,
            "parcelas_pagas": fin.parcelas_pagas,
            "mes_inicio_2026": fin.mes_inicio_2026,
            "valor_parcela": fin.valor_parcela,
            "ativo": fin.ativo,
        })
    
    # NOVO: Cenários e Faturamento Anterior
    dados["usar_cenarios"] = getattr(motor, 'usar_cenarios', True)
    dados["cenario_oficial"] = getattr(motor, 'cenario_oficial', 'Conservador')
    dados["ajustes_cenarios"] = getattr(motor, 'ajustes_cenarios', {})
    dados["usar_comparativo_anterior"] = getattr(motor, 'usar_comparativo_anterior', False)
    dados["faturamento_anterior"] = getattr(motor, 'faturamento_anterior', [0.0] * 12)
    dados["ano_anterior"] = getattr(motor, 'ano_anterior', 2025)
    
    return dados


def dict_para_motor(dados: Dict, motor):
    """Carrega dados de dicionário para MotorCalculo"""
    try:
        from .motor_calculo import Servico, Profissional, DespesaFixa, Sazonalidade, Fisioterapeuta, PremissasFisioterapeutas
    except ImportError:
        from motor_calculo import Servico, Profissional, DespesaFixa, Sazonalidade, Fisioterapeuta, PremissasFisioterapeutas
    
    # Limpa dados existentes
    motor.servicos.clear()
    motor.proprietarios.clear()
    motor.profissionais.clear()
    motor.despesas_fixas.clear()
    motor.valores_proprietario.clear()
    motor.valores_profissional.clear()
    
    # NOVO: Carrega Premissas Operacionais
    if "operacional" in dados:
        op = dados["operacional"]
        motor.operacional.num_fisioterapeutas = op.get("num_fisioterapeutas", 0)
        motor.operacional.num_salas = op.get("num_salas", 0)
        motor.operacional.horas_atendimento_dia = op.get("horas_atendimento_dia", 0)
        motor.operacional.dias_uteis_mes = op.get("dias_uteis_mes", 0)
        motor.operacional.modelo_tributario = op.get("modelo_tributario", "PJ - Simples Nacional")
        motor.operacional.modo_calculo_sessoes = op.get("modo_calculo_sessoes", "servico")
        
        # IMPORTANTE: Sincroniza regime tributário imediatamente
        motor.premissas_folha.regime_tributario = motor.operacional.modelo_tributario
    
    # NOVO v1.79.0: Carrega Cadastro de Salas (TDABC)
    if "cadastro_salas" in dados:
        try:
            from .motor_calculo import CadastroSalas
        except ImportError:
            from motor_calculo import CadastroSalas
        motor.cadastro_salas = CadastroSalas.from_dict(dados["cadastro_salas"])
        # IMPORTANTE: Sincronizar com operacional após carregar
        motor.cadastro_salas.sincronizar_num_salas(motor.operacional.num_salas)
        motor.cadastro_salas.horas_funcionamento_dia = motor.operacional.horas_atendimento_dia
        motor.cadastro_salas.dias_uteis_mes = motor.operacional.dias_uteis_mes
    else:
        # Dados antigos: sincronizar com operacional
        motor.cadastro_salas.sincronizar_num_salas(motor.operacional.num_salas)
        motor.cadastro_salas.horas_funcionamento_dia = motor.operacional.horas_atendimento_dia
        motor.cadastro_salas.dias_uteis_mes = motor.operacional.dias_uteis_mes
    
    # NOVO: Carrega Premissas Macro
    if "macro" in dados:
        mc = dados["macro"]
        motor.macro.ipca = mc.get("ipca", 0.0)
        motor.macro.igpm = mc.get("igpm", 0.0)
        motor.macro.dissidio = mc.get("dissidio", 0.0)
        motor.macro.reajuste_tarifas = mc.get("reajuste_tarifas", 0.0)
        motor.macro.reajuste_contratos = mc.get("reajuste_contratos", 0.0)
        motor.macro.taxa_cartao_credito = mc.get("taxa_cartao_credito", 0.0354)
        motor.macro.taxa_cartao_debito = mc.get("taxa_cartao_debito", 0.0211)
        motor.macro.taxa_antecipacao = mc.get("taxa_antecipacao", 0.05)
    
    # NOVO: Carrega Formas de Pagamento
    if "pagamento" in dados:
        pg = dados["pagamento"]
        motor.pagamento.dinheiro_pix = pg.get("dinheiro_pix", 0.0)
        motor.pagamento.cartao_credito = pg.get("cartao_credito", 0.0)
        motor.pagamento.cartao_debito = pg.get("cartao_debito", 0.0)
        motor.pagamento.outros = pg.get("outros", 0.0)
        motor.pagamento.pct_antecipacao = pg.get("pct_antecipacao", 0.0)
    
    # Serviços
    for nome, srv_data in dados.get("servicos", {}).items():
        motor.servicos[nome] = Servico(
            nome=srv_data["nome"],
            duracao_minutos=srv_data.get("duracao_minutos", 50),
            valor_2026=srv_data.get("valor_2026", 0),
            sessoes_mes_base=srv_data.get("sessoes_mes_base", 0),
            pct_reajuste=srv_data.get("pct_reajuste", 0.05),
            mes_reajuste=srv_data.get("mes_reajuste", 3),
            pct_crescimento=srv_data.get("pct_crescimento", 0.0),
            usa_sala=srv_data.get("usa_sala", True)
        )
    
    # Valores - IMPORTANTE: usar deepcopy para evitar referências compartilhadas
    import copy
    motor.valores_proprietario = copy.deepcopy(dados.get("valores_proprietario", {}))
    motor.valores_profissional = copy.deepcopy(dados.get("valores_profissional", {}))
    
    # Proprietários
    for nome, prop_data in dados.get("proprietarios", {}).items():
        motor.proprietarios[nome] = Profissional(
            nome=prop_data["nome"],
            tipo="proprietario",
            ativo=prop_data.get("ativo", True),
            sessoes_por_servico=copy.deepcopy(prop_data.get("sessoes_por_servico", {})),
            pct_crescimento_por_servico=copy.deepcopy(prop_data.get("pct_crescimento_por_servico", {}))
        )
    
    # Profissionais
    for nome, prof_data in dados.get("profissionais", {}).items():
        motor.profissionais[nome] = Profissional(
            nome=prof_data["nome"],
            tipo="profissional",
            ativo=prof_data.get("ativo", True),
            sessoes_por_servico=copy.deepcopy(prof_data.get("sessoes_por_servico", {})),
            pct_crescimento_por_servico=copy.deepcopy(prof_data.get("pct_crescimento_por_servico", {}))
        )
    
    # Despesas (é um dicionário)
    for nome, desp_data in dados.get("despesas", {}).items():
        motor.despesas_fixas[nome] = DespesaFixa(
            nome=desp_data["nome"],
            categoria=desp_data.get("categoria", "Outros"),
            valor_mensal=desp_data.get("valor_mensal", 0),
            tipo_reajuste=desp_data.get("tipo_reajuste", "ipca"),
            mes_reajuste=desp_data.get("mes_reajuste", 1),
            pct_adicional=desp_data.get("pct_adicional", 0),
            aplicar_reajuste=desp_data.get("aplicar_reajuste", True),
            tipo_sazonalidade=desp_data.get("tipo_sazonalidade", "uniforme"),
            valores_2025=copy.deepcopy(desp_data.get("valores_2025", [0.0] * 12)),
            ativa=desp_data.get("ativa", True),
            # Campos de despesas variáveis
            tipo_despesa=desp_data.get("tipo_despesa", "fixa"),
            base_variavel=desp_data.get("base_variavel", "receita"),
            pct_receita=desp_data.get("pct_receita", 0.0),
            valor_por_sessao=desp_data.get("valor_por_sessao", 0.0)
        )
    
    # Custo pessoal
    motor.custo_pessoal_mensal = dados.get("custo_pessoal_mensal", 0)
    motor.mes_dissidio = dados.get("mes_dissidio", 5)
    
    # Sazonalidade - usar deepcopy para evitar referências compartilhadas
    fatores = copy.deepcopy(dados.get("sazonalidade", [1.0] * 12))
    motor.sazonalidade = Sazonalidade(fatores=fatores)
    
    # Premissas Folha
    try:
        from .motor_calculo import PremissasFolha, FuncionarioCLT, SocioProLabore
    except ImportError:
        from motor_calculo import PremissasFolha, FuncionarioCLT, SocioProLabore
    
    if "premissas_folha" in dados:
        pf_data = dados["premissas_folha"]
        motor.premissas_folha = PremissasFolha(
            regime_tributario=pf_data.get("regime_tributario", "PJ - Simples Nacional"),
            deducao_dependente_ir=pf_data.get("deducao_dependente_ir", 189.59),
            aliquota_fgts=pf_data.get("aliquota_fgts", 0.08),
            desconto_vt_pct=pf_data.get("desconto_vt_pct", 0.06),
            dias_uteis_mes=pf_data.get("dias_uteis_mes", 22),
            mes_dissidio=pf_data.get("mes_dissidio", 5),
            pct_dissidio=pf_data.get("pct_dissidio", 0.06)
        )
        # IMPORTANTE: Sincroniza operacional.modelo_tributario com premissas_folha.regime_tributario
        motor.operacional.modelo_tributario = motor.premissas_folha.regime_tributario
    
    # Funcionários CLT
    if "funcionarios_clt" in dados:
        motor.funcionarios_clt.clear()
        for nome, func_data in dados["funcionarios_clt"].items():
            motor.funcionarios_clt[nome] = FuncionarioCLT(
                nome=func_data["nome"],
                cargo=func_data.get("cargo", ""),
                salario_base=func_data.get("salario_base", 0),
                tipo_vinculo=func_data.get("tipo_vinculo", "informal"),
                dependentes_ir=func_data.get("dependentes_ir", 0),
                vt_dia=func_data.get("vt_dia", 0),
                vr_dia=func_data.get("vr_dia", 0),
                plano_saude=func_data.get("plano_saude", 0),
                plano_odonto=func_data.get("plano_odonto", 0),
                mes_admissao=func_data.get("mes_admissao", 1),
                mes_aumento=func_data.get("mes_aumento", 13),
                pct_reajuste=func_data.get("pct_reajuste", 0),
                ativo=func_data.get("ativo", True)
            )
    
    # Sócios Pró-Labore
    if "socios_prolabore" in dados:
        motor.socios_prolabore.clear()
        for nome, socio_data in dados["socios_prolabore"].items():
            motor.socios_prolabore[nome] = SocioProLabore(
                nome=socio_data["nome"],
                prolabore=socio_data.get("prolabore", 0),
                dependentes_ir=socio_data.get("dependentes_ir", 0),
                mes_reajuste=socio_data.get("mes_reajuste", 5),
                pct_aumento=socio_data.get("pct_aumento", 0),
                ativo=socio_data.get("ativo", True)
            )
    
    # Fisioterapeutas
    if "fisioterapeutas" in dados:
        motor.fisioterapeutas.clear()
        for nome, fisio_data in dados["fisioterapeutas"].items():
            # v1.79.0: Escala semanal zerada como padrão (forçar preenchimento)
            escala_padrao = {
                "segunda": 0.0, "terca": 0.0, "quarta": 0.0,
                "quinta": 0.0, "sexta": 0.0, "sabado": 0.0
            }
            escala_salva = fisio_data.get("escala_semanal", escala_padrao)
            
            motor.fisioterapeutas[nome] = Fisioterapeuta(
                nome=fisio_data["nome"],
                cargo=fisio_data.get("cargo", "Fisioterapeuta"),
                nivel=fisio_data.get("nivel", 2),
                filial=fisio_data.get("filial", "Copacabana"),
                ativo=fisio_data.get("ativo", True),
                sessoes_por_servico=copy.deepcopy(fisio_data.get("sessoes_por_servico", {})),
                pct_crescimento_por_servico=copy.deepcopy(fisio_data.get("pct_crescimento_por_servico", {})),
                tipo_remuneracao=fisio_data.get("tipo_remuneracao", "percentual"),
                valores_fixos_por_servico=copy.deepcopy(fisio_data.get("valores_fixos_por_servico", {})),
                pct_customizado=fisio_data.get("pct_customizado", 0.0),
                escala_semanal=copy.deepcopy(escala_salva)
            )
    
    # Premissas Fisioterapeutas
    if "premissas_fisio" in dados:
        pf_data = dados["premissas_fisio"]
        motor.premissas_fisio = PremissasFisioterapeutas(
            niveis_remuneracao=copy.deepcopy(pf_data.get("niveis_remuneracao", {1: 0.35, 2: 0.30, 3: 0.25, 4: 0.20})),
            pct_producao_propria=pf_data.get("pct_producao_propria", 0.60),
            pct_faturamento_total=pf_data.get("pct_faturamento_total", 0.20),
            pct_base_remuneracao_prop=pf_data.get("pct_base_remuneracao_prop", 0.75),
            pct_gerencia_equipe=pf_data.get("pct_gerencia_equipe", 0.01),
            pct_base_remuneracao_ger=pf_data.get("pct_base_remuneracao_ger", 0.75)
        )
    
    # NOVO: Premissas Simples Nacional / Carnê Leão
    if "premissas_simples" in dados:
        ps_data = dados["premissas_simples"]
        motor.premissas_simples.faturamento_pf_anual = ps_data.get("faturamento_pf_anual", 0.0)
        motor.premissas_simples.aliquota_inss_pf = ps_data.get("aliquota_inss_pf", 0.11)
        motor.premissas_simples.teto_inss_pf = ps_data.get("teto_inss_pf", 908.86)
        motor.premissas_simples.limite_fator_r = ps_data.get("limite_fator_r", 0.28)
    
    # NOVO: Premissas Dividendos
    if "premissas_dividendos" in dados:
        pd_data = dados["premissas_dividendos"]
        motor.premissas_dividendos.distribuir = pd_data.get("distribuir", True)
        motor.premissas_dividendos.pct_reserva_legal = pd_data.get("pct_reserva_legal", 0.05)
        motor.premissas_dividendos.pct_reserva_investimento = pd_data.get("pct_reserva_investimento", 0.20)
        motor.premissas_dividendos.frequencia = pd_data.get("frequencia", "Trimestral")
        motor.premissas_dividendos.pct_distribuir = pd_data.get("pct_distribuir", 0.30)
        motor.premissas_dividendos.mostrar_no_dre = pd_data.get("mostrar_no_dre", True)
    
    # NOVO: Premissas FC (Fluxo de Caixa)
    if "premissas_fc" in dados:
        pfc_data = dados["premissas_fc"]
        pfc = motor.premissas_fc
        pfc.caixa_inicial = pfc_data.get("caixa_inicial", 0.0)
        pfc.cp_impostos = pfc_data.get("cp_impostos", 0.0)
        pfc.cp_folha_colaboradores = pfc_data.get("cp_folha_colaboradores", 0.0)
        pfc.cp_folha_fisioterapeutas = pfc_data.get("cp_folha_fisioterapeutas", 0.0)
        pfc.cp_retirada_proprietarios = pfc_data.get("cp_retirada_proprietarios", 0.0)
        pfc.cp_encargos_clt = pfc_data.get("cp_encargos_clt", 0.0)
        pfc.cp_fornecedores = pfc_data.get("cp_fornecedores", 0.0)
        pfc.usar_cp_folha_auto = pfc_data.get("usar_cp_folha_auto", True)
        pfc.receita_out_ano_anterior = pfc_data.get("receita_out_ano_anterior", 0.0)
        pfc.receita_nov_ano_anterior = pfc_data.get("receita_nov_ano_anterior", 0.0)
        pfc.receita_dez_ano_anterior = pfc_data.get("receita_dez_ano_anterior", 0.0)
        pfc.usar_receita_auto = pfc_data.get("usar_receita_auto", True)
        pfc.recebimento_avista_no_mes = pfc_data.get("recebimento_avista_no_mes", True)
        pfc.saldo_minimo = pfc_data.get("saldo_minimo", 0.0)
        pfc.pct_cartao_1x = pfc_data.get("pct_cartao_1x", 0.3333)
        pfc.pct_cartao_2x = pfc_data.get("pct_cartao_2x", 0.3333)
        pfc.pct_cartao_3x = pfc_data.get("pct_cartao_3x", 0.3334)
        pfc.pct_cartao_4x = pfc_data.get("pct_cartao_4x", 0.0)
        pfc.pct_cartao_5x = pfc_data.get("pct_cartao_5x", 0.0)
        pfc.pct_cartao_6x = pfc_data.get("pct_cartao_6x", 0.0)
    
    # Aplicações Financeiras
    if "aplicacoes" in dados:
        aplic_data = dados["aplicacoes"]
        aplic = motor.premissas_financeiras.aplicacoes
        aplic.saldo_inicial = aplic_data.get("saldo_inicial", 0.0)
        aplic.taxa_selic_anual = aplic_data.get("taxa_selic_anual", 0.1225)
        aplic.pct_cdi = aplic_data.get("pct_cdi", 1.0)
    
    # Investimentos (CAPEX)
    if "investimentos" in dados:
        try:
            from .motor_calculo import Investimento
        except ImportError:
            from motor_calculo import Investimento
        motor.premissas_financeiras.investimentos.clear()
        for inv_data in dados["investimentos"]:
            inv = Investimento(
                descricao=inv_data.get("descricao", ""),
                categoria=inv_data.get("categoria", "Equipamentos"),
                valor_total=inv_data.get("valor_total", 0.0),
                mes_aquisicao=inv_data.get("mes_aquisicao", 1),
                entrada=inv_data.get("entrada", 0.0),
                taxa_mensal=inv_data.get("taxa_mensal", 0.05),
                parcelas=inv_data.get("parcelas", 12),
                beneficio_mensal=inv_data.get("beneficio_mensal", 0.0),
                ativo=inv_data.get("ativo", True),
            )
            motor.premissas_financeiras.investimentos.append(inv)
    
    # Financiamentos Existentes
    if "financiamentos" in dados:
        try:
            from .motor_calculo import FinanciamentoExistente
        except ImportError:
            from motor_calculo import FinanciamentoExistente
        motor.premissas_financeiras.financiamentos.clear()
        for fin_data in dados["financiamentos"]:
            fin = FinanciamentoExistente(
                descricao=fin_data.get("descricao", ""),
                saldo_devedor=fin_data.get("saldo_devedor", 0.0),
                taxa_mensal=fin_data.get("taxa_mensal", 0.03),
                parcelas_total=fin_data.get("parcelas_total", 12),
                parcelas_pagas=fin_data.get("parcelas_pagas", 0),
                mes_inicio_2026=fin_data.get("mes_inicio_2026", 1),
                valor_parcela=fin_data.get("valor_parcela", 0.0),
                ativo=fin_data.get("ativo", True),
            )
            motor.premissas_financeiras.financiamentos.append(fin)
    
    # IMPORTANTE: Sincroniza proprietários -> sócios pró-labore
    # Isso garante que fisioterapeutas com cargo="Proprietário" apareçam na folha
    try:
        motor.sincronizar_proprietarios()
    except Exception as e:
        pass  # Ignora erro se função não existir ou falhar
    
    # NOVO: Carrega Cenários e Faturamento Anterior
    if "usar_cenarios" in dados:
        motor.usar_cenarios = dados["usar_cenarios"]
    if "cenario_oficial" in dados:
        motor.cenario_oficial = dados["cenario_oficial"]
    if "ajustes_cenarios" in dados:
        motor.ajustes_cenarios = copy.deepcopy(dados["ajustes_cenarios"])
    if "usar_comparativo_anterior" in dados:
        motor.usar_comparativo_anterior = dados["usar_comparativo_anterior"]
    if "faturamento_anterior" in dados:
        motor.faturamento_anterior = copy.deepcopy(dados["faturamento_anterior"])
    if "ano_anterior" in dados:
        motor.ano_anterior = dados["ano_anterior"]
    
    return motor


def consolidar_filiais(manager: ClienteManager, cliente_id: str, cliente_nome: str = "Cliente") -> 'MotorCalculo':
    """
    Consolida os dados de todas as filiais de um cliente em um único motor.
    
    Args:
        manager: Instância do ClienteManager
        cliente_id: ID do cliente
        cliente_nome: Nome do cliente para exibição
        
    Returns:
        MotorCalculo com dados consolidados de todas as filiais
    """
    from motor_calculo import criar_motor_vazio, Servico, Fisioterapeuta, FuncionarioCLT, DespesaFixa
    
    # Criar motor consolidado
    motor_consolidado = criar_motor_vazio(
        cliente_nome=cliente_nome,
        filial_nome="Consolidado",
        tipo_relatorio="Consolidado"
    )
    
    # Listar filiais
    filiais = manager.listar_filiais(cliente_id)
    
    if not filiais:
        return motor_consolidado
    
    # Contadores para consolidação
    servicos_consolidados = {}
    fisioterapeutas_consolidados = {}
    funcionarios_consolidados = {}
    despesas_consolidadas = {}
    
    # Iterar sobre cada filial
    for filial_info in filiais:
        filial_id = filial_info["id"]
        filial_nome = filial_info["nome"]
        
        # Carregar dados da filial
        dados_filial = manager.carregar_filial(cliente_id, filial_id)
        
        if not dados_filial:
            continue
        
        # Criar motor temporário para esta filial
        motor_filial = criar_motor_vazio()
        dict_para_motor(dados_filial, motor_filial)
        
        # ===== CONSOLIDAR SERVIÇOS =====
        for nome_srv, srv in motor_filial.servicos.items():
            if nome_srv not in servicos_consolidados:
                servicos_consolidados[nome_srv] = {
                    'nome': nome_srv,
                    'duracao_minutos': srv.duracao_minutos,
                    'pacientes_por_sessao': srv.pacientes_por_sessao,
                    'valor_2025': srv.valor_2025,
                    'valor_2026': srv.valor_2026,
                    'usa_sala': srv.usa_sala,
                }
        
        # ===== CONSOLIDAR FISIOTERAPEUTAS =====
        for nome_fisio, fisio in motor_filial.fisioterapeutas.items():
            # Prefixar com nome da filial para evitar colisão
            nome_unico = f"{nome_fisio} ({filial_nome})"
            
            if nome_unico not in fisioterapeutas_consolidados:
                fisioterapeutas_consolidados[nome_unico] = {
                    'nome': nome_unico,
                    'tipo': fisio.tipo,
                    'regime': fisio.regime,
                    'horas_mes': fisio.horas_mes,
                    'salario': fisio.salario,
                    'prolabore': fisio.prolabore,
                    'ativo': fisio.ativo,
                    'sessoes_por_servico': dict(fisio.sessoes_por_servico) if fisio.sessoes_por_servico else {},
                    'pct_crescimento_por_servico': dict(fisio.pct_crescimento_por_servico) if fisio.pct_crescimento_por_servico else {},
                    'escala_semanal': list(fisio.escala_semanal) if fisio.escala_semanal else [0]*7,
                }
        
        # ===== CONSOLIDAR FUNCIONÁRIOS =====
        for nome_func, func in motor_filial.funcionarios.items():
            nome_unico = f"{nome_func} ({filial_nome})"
            
            if nome_unico not in funcionarios_consolidados:
                funcionarios_consolidados[nome_unico] = {
                    'nome': nome_unico,
                    'cargo': getattr(func, 'cargo', ''),
                    'salario_base': getattr(func, 'salario_base', 0),
                    'tipo_vinculo': getattr(func, 'tipo_vinculo', 'informal'),
                    'vt_dia': getattr(func, 'vt_dia', 0),
                    'vr_dia': getattr(func, 'vr_dia', 0),
                    'plano_saude': getattr(func, 'plano_saude', 0),
                    'plano_odonto': getattr(func, 'plano_odonto', 0),
                    'mes_admissao': getattr(func, 'mes_admissao', 1),
                    'ativo': getattr(func, 'ativo', True),
                }
        
        # ===== CONSOLIDAR DESPESAS FIXAS =====
        for nome_desp, desp in motor_filial.despesas_fixas.items():
            if nome_desp in despesas_consolidadas:
                # Somar valores se despesa já existe
                despesas_consolidadas[nome_desp]['valor_mensal'] += getattr(desp, 'valor_mensal', 0)
            else:
                despesas_consolidadas[nome_desp] = {
                    'nome': nome_desp,
                    'valor_mensal': getattr(desp, 'valor_mensal', 0),
                    'categoria': getattr(desp, 'categoria', 'Administrativa'),
                    'tipo_reajuste': getattr(desp, 'tipo_reajuste', 'ipca'),
                    'ativa': getattr(desp, 'ativa', True),
                    # Campos de despesas variáveis
                    'tipo_despesa': getattr(desp, 'tipo_despesa', 'fixa'),
                    'base_variavel': getattr(desp, 'base_variavel', 'receita'),
                    'pct_receita': getattr(desp, 'pct_receita', 0.0),
                    'valor_por_sessao': getattr(desp, 'valor_por_sessao', 0.0),
                }
        
        # ===== COPIAR PREMISSAS (usa da primeira filial) =====
        if not motor_consolidado.servicos:
            motor_consolidado.premissas_macro = motor_filial.premissas_macro
            motor_consolidado.forma_pagamento = motor_filial.forma_pagamento
            motor_consolidado.premissas_operacionais = motor_filial.premissas_operacionais
            motor_consolidado.simples_nacional = motor_filial.simples_nacional
            motor_consolidado.premissas_financeiras = motor_filial.premissas_financeiras
    
    # ===== APLICAR DADOS CONSOLIDADOS AO MOTOR =====
    
    # Serviços
    for nome, dados in servicos_consolidados.items():
        motor_consolidado.servicos[nome] = Servico(
            nome=dados['nome'],
            duracao_minutos=dados['duracao_minutos'],
            pacientes_por_sessao=dados['pacientes_por_sessao'],
            valor_2025=dados['valor_2025'],
            valor_2026=dados['valor_2026'],
            usa_sala=dados['usa_sala'],
        )
    
    # Fisioterapeutas
    for nome, dados in fisioterapeutas_consolidados.items():
        motor_consolidado.fisioterapeutas[nome] = Fisioterapeuta(
            nome=dados['nome'],
            tipo=dados['tipo'],
            regime=dados['regime'],
            horas_mes=dados['horas_mes'],
            salario=dados['salario'],
            prolabore=dados['prolabore'],
            ativo=dados['ativo'],
            sessoes_por_servico=dados['sessoes_por_servico'],
            pct_crescimento_por_servico=dados['pct_crescimento_por_servico'],
            escala_semanal=dados['escala_semanal'],
        )
    
    # Funcionários
    for nome, dados in funcionarios_consolidados.items():
        motor_consolidado.funcionarios[nome] = FuncionarioCLT(
            nome=dados['nome'],
            cargo=dados['cargo'],
            salario_base=dados['salario_base'],
            tipo_vinculo=dados['tipo_vinculo'],
            vt_dia=dados['vt_dia'],
            vr_dia=dados['vr_dia'],
            plano_saude=dados['plano_saude'],
            plano_odonto=dados['plano_odonto'],
            mes_admissao=dados['mes_admissao'],
            ativo=dados['ativo'],
        )
    
    # Despesas Fixas
    for nome, dados in despesas_consolidadas.items():
        motor_consolidado.despesas_fixas[nome] = DespesaFixa(
            nome=dados['nome'],
            valor_mensal=dados['valor_mensal'],
            categoria=dados['categoria'],
            tipo_reajuste=dados['tipo_reajuste'],
            ativa=dados['ativa'],
            # Campos de despesas variáveis
            tipo_despesa=dados.get('tipo_despesa', 'fixa'),
            base_variavel=dados.get('base_variavel', 'receita'),
            pct_receita=dados.get('pct_receita', 0.0),
            valor_por_sessao=dados.get('valor_por_sessao', 0.0),
        )
    
    # Atualizar premissas operacionais com totais
    total_salas = sum(
        manager.carregar_filial(cliente_id, f["id"]).get("premissas_operacionais", {}).get("num_salas", 4)
        for f in filiais
        if manager.carregar_filial(cliente_id, f["id"])
    )
    motor_consolidado.premissas_operacionais.num_salas = max(total_salas, 1)
    motor_consolidado.premissas_operacionais.num_fisioterapeutas = len(fisioterapeutas_consolidados)
    
    return motor_consolidado


# ============================================
# SISTEMA DE 3 MOTORES POR CENÁRIO
# ============================================

def criar_estrutura_cenarios(motor_base) -> Dict:
    """
    Cria estrutura com 3 motores (um para cada cenário).
    Usado na migração de dados antigos e criação de novas filiais.
    
    Args:
        motor_base: Motor existente que será usado como base (Conservador)
    
    Returns:
        Dict com estrutura de 3 cenários
    """
    import copy
    
    # Serializa o motor base
    dados_base = motor_para_dict(motor_base)
    
    # Cria cópias para cada cenário
    return {
        "_version": "2.0",
        "_format": "multi_cenario",
        "cenario_ativo": "Conservador",
        "cenario_aprovado": None,  # None = não aprovado, ou "Pessimista"/"Conservador"/"Otimista"
        "usar_cenarios": getattr(motor_base, 'usar_cenarios', True),
        "cenarios": {
            "Conservador": copy.deepcopy(dados_base),
            "Pessimista": copy.deepcopy(dados_base),
            "Otimista": copy.deepcopy(dados_base)
        }
    }


def migrar_formato_antigo(dados_antigos: Dict) -> Dict:
    """
    Migra dados do formato antigo (1 motor) para novo (3 motores).
    
    Args:
        dados_antigos: Dict no formato antigo
    
    Returns:
        Dict no formato novo com 3 cenários
    """
    import copy
    
    # Se já está no formato novo, retorna como está
    if dados_antigos.get("_version") == "2.0" and "cenarios" in dados_antigos:
        return dados_antigos
    
    # Migra para formato novo
    return {
        "_version": "2.0",
        "_format": "multi_cenario",
        "cenario_ativo": dados_antigos.get("cenario_oficial", "Conservador"),
        "cenario_aprovado": dados_antigos.get("cenario_aprovado", None),
        "usar_cenarios": dados_antigos.get("usar_cenarios", True),
        "cenarios": {
            "Conservador": copy.deepcopy(dados_antigos),
            "Pessimista": copy.deepcopy(dados_antigos),
            "Otimista": copy.deepcopy(dados_antigos)
        }
    }


def carregar_motores_cenarios(manager: ClienteManager, cliente_id: str, filial_id: str) -> Dict:
    """
    Carrega os 3 motores de uma filial.
    Faz migração automática se dados estiverem no formato antigo.
    
    Args:
        manager: ClienteManager
        cliente_id: ID do cliente
        filial_id: ID da filial
    
    Returns:
        Dict com estrutura: {
            "cenario_ativo": str,
            "usar_cenarios": bool,
            "motores": {
                "Conservador": MotorCalculo,
                "Pessimista": MotorCalculo,
                "Otimista": MotorCalculo
            }
        }
    """
    try:
        from motor_calculo import criar_motor_padrao
    except ImportError:
        from .motor_calculo import criar_motor_padrao
    
    # Carrega dados brutos da filial
    dados_brutos = manager.carregar_filial(cliente_id, filial_id)
    
    if not dados_brutos:
        # Filial não existe, cria estrutura padrão
        # v1.99.49: CORREÇÃO CRÍTICA - Definir cenario_origem para evitar bloqueio
        motor_cons = criar_motor_padrao()
        motor_cons.cenario_origem = "Conservador"

        motor_pess = criar_motor_padrao()
        motor_pess.cenario_origem = "Pessimista"

        motor_otim = criar_motor_padrao()
        motor_otim.cenario_origem = "Otimista"

        return {
            "cenario_ativo": "Conservador",
            "cenario_aprovado": None,
            "usar_cenarios": True,
            "modelo_eficiencia": "profissional",
            "motores": {
                "Conservador": motor_cons,
                "Pessimista": motor_pess,
                "Otimista": motor_otim
            },
            "_migrado": True
        }
    
    # Verifica se é formato novo ou antigo
    if dados_brutos.get("_version") == "2.0" and "cenarios" in dados_brutos:
        # Formato novo - carrega os 3 motores
        motores = {}
        print(f"[LOAD-CENARIOS] Carregando formato 2.0 para {filial_id}")
        for cenario_nome in ["Conservador", "Pessimista", "Otimista"]:
            motor = criar_motor_padrao()
            dados_cenario = dados_brutos["cenarios"].get(cenario_nome, {})
            if dados_cenario:
                dict_para_motor(dados_cenario, motor)
                # LOG: Contagem de sessões
                total_sessoes = sum(
                    sum(f.get("sessoes_por_servico", {}).values())
                    for f in dados_cenario.get("fisioterapeutas", {}).values()
                )
                ipca = dados_cenario.get("macro", {}).get("ipca", 0)
                print(f"[LOAD-CENARIOS] {cenario_nome}: sessões={total_sessoes:.0f}, IPCA={ipca*100:.1f}%")
            # v1.99.49: CORREÇÃO CRÍTICA - Definir cenario_origem
            motor.cenario_origem = cenario_nome
            # v1.99.73: CORREÇÃO - Aplicar fatores do cenário (fator_receita, etc)
            motor.aplicar_cenario(cenario_nome)
            motores[cenario_nome] = motor

        return {
            "cenario_ativo": dados_brutos.get("cenario_ativo", "Conservador"),
            "cenario_aprovado": dados_brutos.get("cenario_aprovado", None),
            "usar_cenarios": dados_brutos.get("usar_cenarios", True),
            "modelo_eficiencia": dados_brutos.get("modelo_eficiencia", "profissional"),
            "motores": motores,
            "_migrado": False
        }
    else:
        # Formato antigo - migra para novo
        motor_base = criar_motor_padrao()
        dict_para_motor(dados_brutos, motor_base)
        motor_base.cenario_origem = "Conservador"  # v1.99.49: CORREÇÃO

        # Cria cópias para os outros cenários
        motor_pess = criar_motor_padrao()
        dict_para_motor(dados_brutos, motor_pess)
        motor_pess.cenario_origem = "Pessimista"  # v1.99.49: CORREÇÃO

        motor_otim = criar_motor_padrao()
        dict_para_motor(dados_brutos, motor_otim)
        motor_otim.cenario_origem = "Otimista"  # v1.99.49: CORREÇÃO

        return {
            "cenario_ativo": dados_brutos.get("cenario_oficial", "Conservador"),
            "cenario_aprovado": dados_brutos.get("cenario_aprovado", None),
            "usar_cenarios": dados_brutos.get("usar_cenarios", True),
            "modelo_eficiencia": dados_brutos.get("modelo_eficiencia", "profissional"),
            "motores": {
                "Conservador": motor_base,
                "Pessimista": motor_pess,
                "Otimista": motor_otim
            },
            "_migrado": True
        }


def salvar_motores_cenarios(manager: ClienteManager, cliente_id: str, filial_id: str, 
                            motores: Dict, cenario_ativo: str = "Conservador", 
                            usar_cenarios: bool = True, cenario_aprovado: str = None,
                            modelo_eficiencia: str = "profissional"):
    """
    Salva os 3 motores de uma filial no novo formato.
    
    Args:
        manager: ClienteManager
        cliente_id: ID do cliente
        filial_id: ID da filial
        motores: Dict com {"Conservador": motor, "Pessimista": motor, "Otimista": motor}
        cenario_ativo: Qual cenário estava ativo
        usar_cenarios: Se o módulo de cenários está habilitado
        cenario_aprovado: Qual cenário foi aprovado (None se nenhum)
        modelo_eficiencia: Modelo de eficiência selecionado (profissional/infraestrutura)
    """
    dados = {
        "_version": "2.0",
        "_format": "multi_cenario",
        "cenario_ativo": cenario_ativo,
        "cenario_aprovado": cenario_aprovado,
        "usar_cenarios": usar_cenarios,
        "modelo_eficiencia": modelo_eficiencia,
        "cenarios": {}
    }
    
    print(f"[SAVE-CENARIOS] Salvando {filial_id} com cenario_ativo={cenario_ativo}")
    for cenario_nome, motor in motores.items():
        dados["cenarios"][cenario_nome] = motor_para_dict(motor)
        # LOG: Contagem de sessões ao salvar
        total_sessoes = sum(
            sum(f.sessoes_por_servico.values())
            for f in motor.fisioterapeutas.values()
        )
        ipca = motor.macro.ipca if hasattr(motor, 'macro') else 0
        print(f"[SAVE-CENARIOS] {cenario_nome}: sessões={total_sessoes:.0f}, IPCA={ipca*100:.1f}%")
    
    return manager.salvar_filial(cliente_id, filial_id, dados)


def copiar_cenario(motor_origem, motor_destino):
    """
    Copia todas as premissas de um motor para outro.
    
    Args:
        motor_origem: Motor de onde copiar
        motor_destino: Motor para onde copiar
    """
    dados = motor_para_dict(motor_origem)
    dict_para_motor(dados, motor_destino)

