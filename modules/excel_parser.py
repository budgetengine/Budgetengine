"""
Parser do Excel - Importação do Modelo de Budget
"""

import pandas as pd
import numpy as np
from pathlib import Path
from config import EXCEL_SHEETS_MAP, MESES_ABREV

class BudgetExcelParser:
    """Parser para o modelo de Budget Excel"""
    
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.excel_file = None
        self.dados = {}
        
    def carregar(self):
        """Carrega o arquivo Excel"""
        self.excel_file = pd.ExcelFile(self.filepath)
        return self.excel_file.sheet_names
    
    def get_sheet_names(self):
        """Retorna nomes das abas"""
        if self.excel_file is None:
            self.carregar()
        return self.excel_file.sheet_names
    
    def _limpar_valor(self, valor):
        """Limpa e converte valor para float"""
        if pd.isna(valor) or valor is None:
            return None
        if isinstance(valor, (int, float)):
            return float(valor) if not np.isnan(valor) else None
        return None
    
    def extrair_dre(self):
        """Extrai dados do DRE"""
        try:
            df = pd.read_excel(self.excel_file, sheet_name=EXCEL_SHEETS_MAP['dre'], header=None)
            
            # Encontra a linha de cabeçalho (CONTA, Jan, Fev...)
            header_row = None
            for i, row in df.iterrows():
                if 'CONTA' in str(row.values):
                    header_row = i
                    break
            
            if header_row is None:
                return None
            
            # Define cabeçalho
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            
            # Processa dados
            dados_dre = []
            tipo_atual = "receita"
            
            for _, row in df.iterrows():
                conta = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                
                if not conta or conta == "nan":
                    continue
                
                # Identifica tipo de conta
                if "Deduções" in conta or "(-)" in conta:
                    tipo_atual = "deducao"
                elif "Custo" in conta or "CPV" in conta:
                    tipo_atual = "custo"
                elif "Despesa" in conta:
                    tipo_atual = "despesa"
                elif "Resultado" in conta:
                    tipo_atual = "resultado"
                
                # Extrai valores mensais
                registro = {
                    'conta': conta,
                    'tipo': tipo_atual,
                }
                
                # Mapeia colunas para meses
                colunas = df.columns.tolist()
                for i, mes in enumerate(MESES_ABREV):
                    for j, col in enumerate(colunas):
                        if str(col).strip().lower().startswith(mes.lower()):
                            registro[mes.lower()] = self._limpar_valor(row.iloc[j])
                            break
                
                # Total
                for j, col in enumerate(colunas):
                    if 'TOTAL' in str(col).upper():
                        registro['total'] = self._limpar_valor(row.iloc[j])
                        break
                
                dados_dre.append(registro)
            
            self.dados['dre'] = dados_dre
            return dados_dre
            
        except Exception as e:
            print(f"Erro ao extrair DRE: {e}")
            return None
    
    def extrair_fluxo_caixa(self):
        """Extrai dados do Fluxo de Caixa"""
        try:
            df = pd.read_excel(self.excel_file, sheet_name=EXCEL_SHEETS_MAP['fluxo_caixa'], header=None)
            
            # Encontra linha de cabeçalho
            header_row = None
            for i, row in df.iterrows():
                row_str = ' '.join([str(v) for v in row.values])
                if 'Jan' in row_str and 'Fev' in row_str:
                    header_row = i
                    break
            
            if header_row is None:
                return None
            
            df.columns = df.iloc[header_row]
            df = df.iloc[header_row + 1:].reset_index(drop=True)
            
            dados_fc = []
            categoria_atual = "entrada"
            
            for _, row in df.iterrows():
                descricao = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                
                if not descricao or descricao == "nan":
                    continue
                
                # Identifica categoria
                if "Entrada" in descricao.upper():
                    categoria_atual = "entrada"
                    continue
                elif "Saída" in descricao.upper() or "SAIDA" in descricao.upper():
                    categoria_atual = "saida"
                    continue
                elif "SALDO" in descricao.upper():
                    categoria_atual = "saldo"
                
                registro = {
                    'categoria': categoria_atual,
                    'descricao': descricao,
                    'tipo': 'entrada' if categoria_atual == 'entrada' else 'saida',
                }
                
                # Extrai valores mensais
                colunas = df.columns.tolist()
                for i, mes in enumerate(MESES_ABREV):
                    for j, col in enumerate(colunas):
                        if str(col).strip().lower().startswith(mes.lower()):
                            registro[mes.lower()] = self._limpar_valor(row.iloc[j])
                            break
                
                # Total
                for j, col in enumerate(colunas):
                    if 'TOTAL' in str(col).upper():
                        registro['total'] = self._limpar_valor(row.iloc[j])
                        break
                
                dados_fc.append(registro)
            
            self.dados['fluxo_caixa'] = dados_fc
            return dados_fc
            
        except Exception as e:
            print(f"Erro ao extrair Fluxo de Caixa: {e}")
            return None
    
    def extrair_resumo_receitas(self):
        """Extrai resumo de receitas por tipo de serviço"""
        try:
            df = pd.read_excel(self.excel_file, sheet_name=EXCEL_SHEETS_MAP['dre'], header=None)
            
            # Procura por tipos de serviço conhecidos
            servicos = ['Oestopatia', 'Osteopatia', 'Individual', 'Consultório', 
                       'Domiciliar', 'Ginasio', 'Ginásio', 'Personalizado']
            
            receitas = []
            
            for _, row in df.iterrows():
                conta = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                
                for servico in servicos:
                    if servico.lower() in conta.lower():
                        registro = {'servico': conta}
                        
                        # Pega valores numéricos
                        for j in range(1, min(14, len(row))):
                            valor = self._limpar_valor(row.iloc[j])
                            if valor is not None and valor > 0:
                                if j <= 12:
                                    registro[MESES_ABREV[j-1].lower()] = valor
                                elif j == 13:
                                    registro['total'] = valor
                        
                        if 'total' in registro or any(m in registro for m in [m.lower() for m in MESES_ABREV]):
                            receitas.append(registro)
                        break
            
            self.dados['receitas_servicos'] = receitas
            return receitas
            
        except Exception as e:
            print(f"Erro ao extrair receitas: {e}")
            return None
    
    def extrair_indicadores(self):
        """Extrai indicadores principais"""
        indicadores = []
        
        try:
            # Do DRE
            if 'dre' in self.dados:
                for item in self.dados['dre']:
                    conta = item['conta'].lower().strip()
                    total = item.get('total')
                    
                    if total is None:
                        continue
                    
                    # Receita Bruta Total
                    if 'total da receita bruta' in conta or 'total receita bruta' in conta:
                        indicadores.append({
                            'indicador': 'Receita Bruta Total',
                            'valor': total,
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Receita Líquida
                    elif conta == 'receita liquida' or conta == 'receita líquida':
                        indicadores.append({
                            'indicador': 'Receita Líquida',
                            'valor': total,
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Margem de Contribuição
                    elif 'margem de contribuição' in conta or 'margem de contribuicao' in conta:
                        indicadores.append({
                            'indicador': 'Margem de Contribuição',
                            'valor': total,
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # EBITDA / Resultado Operacional
                    elif 'ebitda' in conta or 'resultado operacional' in conta:
                        indicadores.append({
                            'indicador': 'EBITDA',
                            'valor': total,
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Resultado Líquido
                    elif conta == 'resultado liquido' or conta == 'resultado líquido':
                        indicadores.append({
                            'indicador': 'Resultado Líquido',
                            'valor': total,
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Lucro no Período
                    elif 'lucro no periodo' in conta or 'lucro no período' in conta:
                        indicadores.append({
                            'indicador': 'Lucro no Período',
                            'valor': total,
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Total Deduções
                    elif 'total deduções' in conta or 'total deducoes' in conta:
                        indicadores.append({
                            'indicador': 'Deduções',
                            'valor': abs(total),
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Total Custos Fixos
                    elif 'total custos fixos' in conta:
                        indicadores.append({
                            'indicador': 'Custos Fixos',
                            'valor': abs(total),
                            'categoria': 'financeiro',
                            'unidade': 'R$'
                        })
                    
                    # Subtotal Pessoal
                    elif 'subtotal pessoal' in conta:
                        indicadores.append({
                            'indicador': 'Custo Pessoal',
                            'valor': abs(total),
                            'categoria': 'operacional',
                            'unidade': 'R$'
                        })
            
            # Calcula margens
            receita_bruta = next((i['valor'] for i in indicadores if i['indicador'] == 'Receita Bruta Total'), None)
            receita_liq = next((i['valor'] for i in indicadores if i['indicador'] == 'Receita Líquida'), None)
            ebitda = next((i['valor'] for i in indicadores if i['indicador'] == 'EBITDA'), None)
            resultado_liq = next((i['valor'] for i in indicadores if i['indicador'] == 'Resultado Líquido'), None)
            margem_contrib = next((i['valor'] for i in indicadores if i['indicador'] == 'Margem de Contribuição'), None)
            
            if receita_bruta and ebitda:
                indicadores.append({
                    'indicador': 'Margem EBITDA',
                    'valor': ebitda / receita_bruta,
                    'categoria': 'financeiro',
                    'unidade': '%'
                })
            
            if receita_bruta and resultado_liq:
                indicadores.append({
                    'indicador': 'Margem Líquida',
                    'valor': resultado_liq / receita_bruta,
                    'categoria': 'financeiro',
                    'unidade': '%'
                })
            
            if receita_liq and margem_contrib:
                indicadores.append({
                    'indicador': '% Margem Contribuição',
                    'valor': margem_contrib / receita_liq,
                    'categoria': 'financeiro',
                    'unidade': '%'
                })
            
            self.dados['indicadores'] = indicadores
            return indicadores
            
        except Exception as e:
            print(f"Erro ao extrair indicadores: {e}")
            return []
    
    def extrair_tudo(self):
        """Extrai todos os dados do arquivo"""
        self.carregar()
        self.extrair_dre()
        self.extrair_fluxo_caixa()
        self.extrair_resumo_receitas()
        self.extrair_indicadores()
        return self.dados
    
    def get_resumo(self):
        """Retorna um resumo dos dados extraídos"""
        resumo = {
            'arquivo': self.filepath.name,
            'abas_encontradas': len(self.get_sheet_names()),
            'dre_linhas': len(self.dados.get('dre', [])),
            'fluxo_caixa_linhas': len(self.dados.get('fluxo_caixa', [])),
            'servicos': len(self.dados.get('receitas_servicos', [])),
            'indicadores': len(self.dados.get('indicadores', [])),
        }
        return resumo


def importar_budget(filepath):
    """Função helper para importar um arquivo de budget"""
    parser = BudgetExcelParser(filepath)
    dados = parser.extrair_tudo()
    resumo = parser.get_resumo()
    return dados, resumo
