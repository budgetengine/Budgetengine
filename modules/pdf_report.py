"""
Módulo de Geração de Relatório PDF DIDÁTICO - v3.1
Budget Engine - Planejamento Orçamentário
Foco: Linguagem simples, muitos gráficos, explicações didáticas
Inclui: Custeio ABC, Ponto de Equilíbrio detalhado, Ocupação expandida
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, 
    PageBreak, Image, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.pdfgen import canvas
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional


# ============================================================================
# CORES DO TEMA
# ============================================================================

CORES = {
    'primaria': colors.HexColor('#1a365d'),
    'primaria_clara': colors.HexColor('#3182ce'),
    'secundaria': colors.HexColor('#276749'),
    'verde': colors.HexColor('#38a169'),
    'vermelho': colors.HexColor('#e53e3e'),
    'amarelo': colors.HexColor('#d69e2e'),
    'laranja': colors.HexColor('#dd6b20'),
    'roxo': colors.HexColor('#805ad5'),
    'texto': colors.HexColor('#2d3748'),
    'texto_claro': colors.HexColor('#718096'),
    'fundo_dica': colors.HexColor('#ebf8ff'),
    'fundo_alerta': colors.HexColor('#fffaf0'),
    'fundo_sucesso': colors.HexColor('#f0fff4'),
    'fundo_cinza': colors.HexColor('#f7fafc'),
    'linha': colors.HexColor('#e2e8f0'),
    'branco': colors.white,
}

MESES = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def criar_estilos():
    """Cria estilos personalizados"""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(
        name='TituloCapa', fontSize=32, textColor=CORES['primaria'],
        alignment=TA_CENTER, fontName='Helvetica-Bold', leading=38, spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name='SubtituloCapa', fontSize=16, textColor=CORES['texto_claro'],
        alignment=TA_CENTER, fontName='Helvetica', spaceAfter=20
    ))
    
    styles.add(ParagraphStyle(
        name='InfoCapa', fontSize=11, textColor=CORES['texto_claro'],
        alignment=TA_CENTER, fontName='Helvetica', leading=16
    ))
    
    styles.add(ParagraphStyle(
        name='TituloCapitulo', fontSize=22, textColor=CORES['primaria'],
        fontName='Helvetica-Bold', spaceBefore=0, spaceAfter=15, leading=26
    ))
    
    styles.add(ParagraphStyle(
        name='TituloSecao', fontSize=14, textColor=CORES['primaria'],
        fontName='Helvetica-Bold', spaceBefore=15, spaceAfter=8
    ))
    
    styles.add(ParagraphStyle(
        name='Subtitulo', fontSize=11, textColor=CORES['texto_claro'],
        fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name='Texto', fontSize=10, textColor=CORES['texto'],
        fontName='Helvetica', leading=14, spaceAfter=8, alignment=TA_JUSTIFY
    ))
    
    styles.add(ParagraphStyle(
        name='TextoPequeno', fontSize=9, textColor=CORES['texto_claro'],
        fontName='Helvetica', leading=12, spaceAfter=5
    ))
    
    styles.add(ParagraphStyle(
        name='KPINumero', fontSize=20, textColor=CORES['primaria'],
        alignment=TA_CENTER, fontName='Helvetica-Bold'
    ))
    
    styles.add(ParagraphStyle(
        name='KPILabel', fontSize=8, textColor=CORES['texto_claro'],
        alignment=TA_CENTER, fontName='Helvetica'
    ))
    
    styles.add(ParagraphStyle(
        name='Rodape', fontSize=8, textColor=CORES['texto_claro'],
        alignment=TA_CENTER, fontName='Helvetica'
    ))
    
    return styles


# ============================================================================
# FUNÇÕES AUXILIARES
# ============================================================================

def fmt_moeda(valor: float, resumido: bool = False) -> str:
    if valor is None:
        return "R$ 0"
    if resumido:
        if abs(valor) >= 1_000_000:
            return f"R$ {valor/1_000_000:.1f}M"
        elif abs(valor) >= 1_000:
            return f"R$ {valor/1_000:.0f}K"
    return f"R$ {valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_num(valor: float, decimais: int = 0) -> str:
    if decimais > 0:
        return f"{valor:,.{decimais}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{valor:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_pct(valor: float, decimais: int = 1) -> str:
    return f"{valor:.{decimais}f}%"


def linha_sep(cor=None, espessura=1):
    return HRFlowable(width="100%", thickness=espessura, color=cor or CORES['linha'],
                      spaceBefore=6, spaceAfter=6)


# ============================================================================
# COMPONENTES VISUAIS
# ============================================================================

def criar_box_explicativo(titulo: str, texto: str, tipo: str = "info") -> Table:
    """Box com explicação didática - tipo: 'info', 'alerta', 'sucesso'"""
    styles = criar_estilos()
    
    cores_tipo = {
        'info': (CORES['fundo_dica'], CORES['primaria_clara'], '?'),
        'alerta': (CORES['fundo_alerta'], CORES['laranja'], '!'),
        'sucesso': (CORES['fundo_sucesso'], CORES['verde'], 'V'),
    }
    
    cor_fundo, cor_texto, icone = cores_tipo.get(tipo, cores_tipo['info'])
    
    conteudo = f"<b>{titulo}</b><br/><br/>{texto}"
    
    dados = [[Paragraph(conteudo, ParagraphStyle(
        'BoxTexto', fontSize=9, textColor=cor_texto,
        fontName='Helvetica', leading=13, leftIndent=5, rightIndent=5
    ))]]
    
    tabela = Table(dados, colWidths=[16*cm])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo),
        ('BOX', (0, 0), (-1, -1), 1, cor_texto),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    return tabela


def criar_card_kpi_didatico(valor: str, label: str, explicacao: str, cor: str = "normal") -> Table:
    """Card de KPI com explicação"""
    styles = criar_estilos()
    
    cores_kpi = {
        'normal': CORES['fundo_cinza'],
        'bom': CORES['fundo_sucesso'],
        'ruim': colors.HexColor('#fff5f5'),
        'atencao': CORES['fundo_alerta'],
    }
    
    cor_fundo = cores_kpi.get(cor, cores_kpi['normal'])
    
    dados = [
        [Paragraph(valor, styles['KPINumero'])],
        [Paragraph(label, styles['KPILabel'])],
        [Paragraph(f"<i>{explicacao}</i>", ParagraphStyle(
            'KPIExp', fontSize=7, textColor=CORES['texto_claro'],
            alignment=TA_CENTER, fontName='Helvetica-Oblique', leading=9
        ))]
    ]
    
    tabela = Table(dados, colWidths=[4*cm])
    tabela.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo),
        ('BOX', (0, 0), (-1, -1), 1, CORES['linha']),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]))
    
    return tabela


def criar_linha_kpis_didaticos(kpis: List[Dict]) -> Table:
    cards = [criar_card_kpi_didatico(k['valor'], k['label'], k['explicacao'], k.get('cor', 'normal')) 
             for k in kpis]
    
    tabela = Table([cards], colWidths=[4.2*cm] * len(kpis))
    tabela.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return tabela


def criar_tabela_simples(dados: List[List], larguras: List[float], 
                          destaque_linhas: List[int] = None) -> Table:
    """Tabela formatada"""
    tabela = Table(dados, colWidths=larguras)
    
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), CORES['primaria']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, CORES['linha']),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, CORES['fundo_cinza']]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]
    
    if destaque_linhas:
        for idx in destaque_linhas:
            estilo.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor('#edf2f7')))
            estilo.append(('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold'))
    
    tabela.setStyle(TableStyle(estilo))
    return tabela


# ============================================================================
# GRÁFICOS
# ============================================================================

def criar_grafico_semaforo(indicadores: List[Dict]) -> BytesIO:
    """Gráfico de semáforo - barras horizontais com cores"""
    fig, ax = plt.subplots(figsize=(12, max(3, len(indicadores) * 0.8)))
    
    y_pos = np.arange(len(indicadores))
    
    for i, ind in enumerate(indicadores):
        if ind['status'] == 'verde':
            cor = '#38a169'
            status_txt = 'OK'
        elif ind['status'] == 'amarelo':
            cor = '#d69e2e'
            status_txt = 'ATENÇÃO'
        else:
            cor = '#e53e3e'
            status_txt = 'CRÍTICO'
        
        # Barra de status
        ax.barh(i, 0.3, color=cor, height=0.5, left=0)
        
        # Textos
        ax.text(0.35, i, f"{ind['nome']}", va='center', ha='left', fontsize=11, fontweight='bold')
        ax.text(0.75, i, ind['valor'], va='center', ha='center', fontsize=11, color='#2d3748')
        ax.text(0.9, i, status_txt, va='center', ha='left', fontsize=9, color=cor, fontweight='bold')
        
        # Explicação abaixo
        ax.text(0.35, i - 0.3, ind.get('explicacao', ''), va='center', ha='left', 
                fontsize=8, color='#718096', style='italic')
    
    ax.set_xlim(0, 1.1)
    ax.set_ylim(-0.6, len(indicadores) - 0.4)
    ax.invert_yaxis()
    ax.axis('off')
    ax.set_title('Painel de Indicadores - Visão Rápida\n', fontsize=13, fontweight='bold')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_pizza(valores: List[float], labels: List[str], titulo: str) -> BytesIO:
    """Gráfico de pizza didático"""
    fig, ax = plt.subplots(figsize=(7, 5))
    
    dados = [(v, l) for v, l in zip(valores, labels) if v > 0]
    if not dados:
        dados = [(1, 'Sem dados')]
    
    valores_f, labels_f = zip(*dados)
    cores = ['#3182ce', '#38a169', '#d69e2e', '#e53e3e', '#805ad5', '#dd6b20'][:len(dados)]
    
    wedges, texts, autotexts = ax.pie(
        valores_f, labels=None, colors=cores,
        autopct=lambda pct: f'{pct:.1f}%' if pct > 5 else '',
        startangle=90, pctdistance=0.75,
        textprops={'fontsize': 10, 'fontweight': 'bold', 'color': 'white'}
    )
    
    total = sum(valores_f)
    legend_labels = [f'{l}: {fmt_moeda(v, True)} ({v/total*100:.1f}%)' for l, v in zip(labels_f, valores_f)]
    ax.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1, 0.5), fontsize=9)
    
    ax.set_title(titulo, fontsize=12, fontweight='bold')
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_evolucao(meses, receitas, custos, resultado) -> BytesIO:
    """Gráfico de evolução mensal"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), height_ratios=[2, 1])
    
    x = range(len(meses))
    width = 0.35
    
    # Gráfico superior
    ax1.bar([i - width/2 for i in x], [r/1000 for r in receitas], 
            width, label='Receita', color='#3182ce', alpha=0.8)
    ax1.bar([i + width/2 for i in x], [c/1000 for c in custos], 
            width, label='Custos', color='#e53e3e', alpha=0.8)
    
    ax1.set_xticks(x)
    ax1.set_xticklabels(meses)
    ax1.set_ylabel('R$ mil', fontsize=10)
    ax1.set_title('Receitas vs Custos - Mês a Mês\n(Azul maior que vermelho = sobra dinheiro)', 
                  fontsize=12, fontweight='bold', pad=15)
    ax1.legend(loc='upper left', fontsize=9)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Gráfico inferior
    cores_res = ['#38a169' if r >= 0 else '#e53e3e' for r in resultado]
    ax2.bar(x, [r/1000 for r in resultado], color=cores_res, alpha=0.8)
    ax2.axhline(y=0, color='#2d3748', linestyle='-', linewidth=1)
    
    ax2.set_xticks(x)
    ax2.set_xticklabels(meses)
    ax2.set_ylabel('R$ mil', fontsize=10)
    ax2.set_title('Resultado Mensal (EBITDA)\n(Verde = lucro | Vermelho = prejuízo)', 
                  fontsize=11, fontweight='bold', pad=10)
    ax2.grid(True, alpha=0.3, axis='y')
    
    for i, r in enumerate(resultado):
        va = 'bottom' if r >= 0 else 'top'
        ax2.text(i, r/1000, f'{r/1000:.0f}K', ha='center', va=va, fontsize=8, fontweight='bold')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_fluxo_caixa(meses, saldos, saldo_minimo, aplicacoes=None) -> BytesIO:
    """Gráfico de fluxo de caixa"""
    fig, ax = plt.subplots(figsize=(14, 5))
    
    x = range(len(meses))
    saldos_k = [s/1000 for s in saldos]
    
    ax.fill_between(x, saldos_k, alpha=0.3, color='#3182ce')
    ax.plot(x, saldos_k, linewidth=2.5, marker='o', markersize=8, 
            color='#2c5282', label='Saldo em Caixa')
    
    if aplicacoes:
        app_k = [a/1000 for a in aplicacoes]
        ax.plot(x, app_k, linewidth=2, marker='s', markersize=6, 
                color='#38a169', linestyle='--', label='Aplicações')
    
    if saldo_minimo > 0:
        ax.axhline(y=saldo_minimo/1000, color='#e53e3e', linestyle='--', 
                   linewidth=2, label=f'Saldo Mínimo: R$ {saldo_minimo/1000:.0f}K')
    
    ax.axhline(y=0, color='#718096', linestyle='-', linewidth=0.5)
    
    ax.set_xticks(x)
    ax.set_xticklabels(meses)
    ax.set_ylabel('R$ mil', fontsize=10)
    ax.set_title('Evolução do Caixa\n(Linha azul deve ficar ACIMA da linha vermelha)', 
                 fontsize=12, fontweight='bold', pad=15)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)
    
    for i, s in enumerate(saldos_k):
        ax.text(i, s + 3, f'{s:.0f}K', ha='center', va='bottom', fontsize=8, color='#2c5282')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_barras_horizontal(dados: Dict[str, float], titulo: str, cor: str = '#3182ce') -> BytesIO:
    """Gráfico de barras horizontais"""
    fig, ax = plt.subplots(figsize=(10, max(4, len(dados) * 0.7)))
    
    dados_ord = sorted(dados.items(), key=lambda x: x[1], reverse=True)
    nomes = [d[0] for d in dados_ord]
    valores = [d[1]/1000 for d in dados_ord]
    total = sum(valores)
    
    cores_grad = plt.cm.Blues(np.linspace(0.4, 0.8, len(nomes)))
    
    bars = ax.barh(nomes, valores, color=cores_grad, height=0.6)
    
    for bar, valor in zip(bars, valores):
        pct = valor / total * 100 if total > 0 else 0
        ax.text(bar.get_width() + max(valores)*0.02, bar.get_y() + bar.get_height()/2,
                f'R$ {valor:.0f}K ({pct:.1f}%)', va='center', fontsize=9, fontweight='bold')
    
    ax.set_xlabel('R$ mil', fontsize=10)
    ax.set_title(titulo, fontsize=12, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, axis='x')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_ponto_equilibrio(receita, pe, margem_seguranca) -> BytesIO:
    """Gráfico visual do ponto de equilíbrio"""
    fig, ax = plt.subplots(figsize=(12, 5))
    
    max_val = receita * 1.2
    
    # Barra de fundo
    ax.barh(['Faturamento'], [max_val/1000], color='#e2e8f0', height=0.5)
    
    # Zona de prejuízo
    ax.barh(['Faturamento'], [pe/1000], color='#fed7d7', height=0.5)
    
    # Zona de lucro
    if receita > pe:
        ax.barh(['Faturamento'], [(receita - pe)/1000], left=pe/1000, color='#c6f6d5', height=0.5)
    
    # Linhas
    ax.axvline(x=pe/1000, color='#e53e3e', linestyle='-', linewidth=3)
    ax.text(pe/1000, 0.35, f'Ponto de Equilibrio\n{fmt_moeda(pe, True)}', 
            fontsize=10, color='#e53e3e', fontweight='bold', ha='center')
    
    ax.axvline(x=receita/1000, color='#38a169', linestyle='-', linewidth=3)
    ax.text(receita/1000, -0.35, f'Receita Projetada\n{fmt_moeda(receita, True)}', 
            fontsize=10, color='#38a169', fontweight='bold', ha='center')
    
    # Seta da margem
    mid = (pe + receita) / 2 / 1000
    ax.annotate('', xy=(receita/1000, 0), xytext=(pe/1000, 0),
                arrowprops=dict(arrowstyle='<->', color='#2c5282', lw=2))
    ax.text(mid, 0.15, f'Margem de Seguranca: {margem_seguranca:.1f}%', 
            ha='center', fontsize=11, color='#2c5282', fontweight='bold')
    
    ax.set_xlim(0, max_val/1000 * 1.1)
    ax.set_yticks([])
    ax.set_xlabel('Faturamento (R$ mil)', fontsize=10)
    ax.set_title('Ponto de Equilibrio - Quanto voce PRECISA faturar\n'
                 'VERMELHO = Prejuizo | VERDE = Lucro', 
                 fontsize=12, fontweight='bold', pad=15)
    
    for spine in ['top', 'right', 'left']:
        ax.spines[spine].set_visible(False)
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_pe_por_servico(servicos_pe: Dict) -> BytesIO:
    """Gráfico de PE por serviço"""
    fig, ax = plt.subplots(figsize=(10, max(4, len(servicos_pe) * 0.8)))
    
    nomes = list(servicos_pe.keys())
    pe_sessoes = [s['pe_sessoes'] for s in servicos_pe.values()]
    projetado = [s['sessoes_projetadas'] for s in servicos_pe.values()]
    
    y = np.arange(len(nomes))
    height = 0.35
    
    bars1 = ax.barh(y - height/2, pe_sessoes, height, label='PE (sessoes minimas)', color='#e53e3e', alpha=0.7)
    bars2 = ax.barh(y + height/2, projetado, height, label='Projetado', color='#38a169', alpha=0.7)
    
    ax.set_yticks(y)
    ax.set_yticklabels(nomes)
    ax.set_xlabel('Numero de Sessoes', fontsize=10)
    ax.set_title('Ponto de Equilibrio por Servico\n(Verde deve ser MAIOR que vermelho)', 
                 fontsize=12, fontweight='bold', pad=15)
    ax.legend(loc='lower right', fontsize=9)
    ax.grid(True, alpha=0.3, axis='x')
    
    # Valores nas barras
    for bar, val in zip(bars1, pe_sessoes):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                f'{val:.0f}', va='center', fontsize=8, color='#e53e3e')
    for bar, val in zip(bars2, projetado):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                f'{val:.0f}', va='center', fontsize=8, color='#38a169')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_ocupacao_barras(ocupacoes: Dict[str, float], titulo: str) -> BytesIO:
    """Gráfico de barras de ocupação"""
    fig, ax = plt.subplots(figsize=(10, max(4, len(ocupacoes) * 0.6)))
    
    nomes = list(ocupacoes.keys())
    valores = list(ocupacoes.values())
    
    cores = ['#38a169' if v >= 80 else '#d69e2e' if v >= 60 else '#e53e3e' for v in valores]
    
    bars = ax.barh(nomes, valores, color=cores, height=0.6)
    
    # Linha de meta
    ax.axvline(x=80, color='#2c5282', linestyle='--', linewidth=2, label='Meta: 80%')
    
    ax.set_xlim(0, 110)
    ax.set_xlabel('Taxa de Ocupacao (%)', fontsize=10)
    ax.set_title(f'{titulo}\n(Verde >= 80% | Amarelo 60-80% | Vermelho < 60%)', 
                 fontsize=12, fontweight='bold', pad=15)
    ax.legend(loc='lower right', fontsize=9)
    ax.grid(True, alpha=0.3, axis='x')
    
    for bar, val in zip(bars, valores):
        ax.text(bar.get_width() + 2, bar.get_y() + bar.get_height()/2,
                f'{val:.1f}%', va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_ocupacao_mensal(meses, ocupacao_prof, ocupacao_sala) -> BytesIO:
    """Gráfico de ocupação mensal"""
    fig, ax = plt.subplots(figsize=(12, 5))
    
    x = range(len(meses))
    
    ax.plot(x, ocupacao_prof, linewidth=2.5, marker='o', markersize=6, 
            color='#3182ce', label='Profissionais')
    ax.plot(x, ocupacao_sala, linewidth=2.5, marker='s', markersize=6, 
            color='#38a169', label='Salas')
    
    # Linha de meta
    ax.axhline(y=80, color='#d69e2e', linestyle='--', linewidth=2, label='Meta: 80%')
    ax.fill_between(x, 80, 100, alpha=0.1, color='green')
    ax.fill_between(x, 0, 60, alpha=0.1, color='red')
    
    ax.set_xticks(x)
    ax.set_xticklabels(meses)
    ax.set_ylabel('Taxa de Ocupacao (%)', fontsize=10)
    ax.set_ylim(0, 105)
    ax.set_title('Evolucao da Ocupacao ao Longo do Ano\n'
                 'Area verde = Otimo | Area vermelha = Critico', 
                 fontsize=12, fontweight='bold', pad=15)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_rentabilidade_servicos(servicos: Dict) -> BytesIO:
    """Gráfico de rentabilidade por serviço (Custeio ABC)"""
    fig, ax = plt.subplots(figsize=(12, max(5, len(servicos) * 0.9)))
    
    # Ordenar por margem
    dados_ord = sorted(servicos.items(), key=lambda x: x[1]['margem_pct'], reverse=True)
    
    nomes = [d[0] for d in dados_ord]
    margens = [d[1]['margem_pct'] for d in dados_ord]
    receitas = [d[1]['receita']/1000 for d in dados_ord]
    
    cores = ['#38a169' if m >= 30 else '#d69e2e' if m >= 15 else '#e53e3e' for m in margens]
    
    y = np.arange(len(nomes))
    
    # Barras de margem
    bars = ax.barh(y, margens, color=cores, height=0.6)
    
    ax.axvline(x=30, color='#38a169', linestyle='--', linewidth=1.5, alpha=0.5)
    ax.axvline(x=15, color='#d69e2e', linestyle='--', linewidth=1.5, alpha=0.5)
    
    ax.set_yticks(y)
    ax.set_yticklabels(nomes)
    ax.set_xlabel('Margem de Contribuicao (%)', fontsize=10)
    ax.set_title('Rentabilidade por Servico (Custeio ABC)\n'
                 'Verde >= 30% | Amarelo 15-30% | Vermelho < 15%', 
                 fontsize=12, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, axis='x')
    
    # Valores e receita
    for bar, margem, receita in zip(bars, margens, receitas):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height()/2,
                f'{margem:.1f}% (R$ {receita:.0f}K)', va='center', fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


def criar_grafico_custo_por_sessao(servicos: Dict) -> BytesIO:
    """Gráfico de custo vs receita por sessão"""
    fig, ax = plt.subplots(figsize=(12, max(5, len(servicos) * 0.9)))
    
    nomes = list(servicos.keys())
    precos = [s['preco'] for s in servicos.values()]
    custos = [s['custo_sessao'] for s in servicos.values()]
    lucros = [s['lucro_sessao'] for s in servicos.values()]
    
    y = np.arange(len(nomes))
    height = 0.25
    
    ax.barh(y - height, precos, height, label='Preco da Sessao', color='#3182ce', alpha=0.8)
    ax.barh(y, custos, height, label='Custo por Sessao', color='#e53e3e', alpha=0.8)
    ax.barh(y + height, lucros, height, label='Lucro por Sessao', color='#38a169', alpha=0.8)
    
    ax.set_yticks(y)
    ax.set_yticklabels(nomes)
    ax.set_xlabel('Valor (R$)', fontsize=10)
    ax.set_title('Analise de Custo por Sessao\n'
                 'Preco - Custo = Lucro (quanto maior o verde, melhor!)', 
                 fontsize=12, fontweight='bold', pad=15)
    ax.legend(loc='lower right', fontsize=9)
    ax.grid(True, alpha=0.3, axis='x')
    
    # Valores
    for i, (p, c, l) in enumerate(zip(precos, custos, lucros)):
        ax.text(p + 2, i - height, f'R$ {p:.0f}', va='center', fontsize=8)
        ax.text(c + 2, i, f'R$ {c:.0f}', va='center', fontsize=8)
        ax.text(l + 2, i + height, f'R$ {l:.0f}', va='center', fontsize=8, fontweight='bold')
    
    plt.tight_layout()
    
    buffer = BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor='white')
    buffer.seek(0)
    plt.close()
    
    return buffer


# ============================================================================
# CANVAS COM NUMERAÇÃO
# ============================================================================

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, nome_cliente="", tipo_relatorio="", **kwargs):
        self.nome_cliente = nome_cliente
        self.tipo_relatorio = tipo_relatorio
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_elements(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_elements(self, page_count):
        page_num = self._pageNumber
        if page_num == 1:
            return
        
        self.setFont("Helvetica", 8)
        self.setFillColor(CORES['texto_claro'])
        
        # Cabeçalho com tipo de relatório
        tipo_txt = f" ({self.tipo_relatorio})" if self.tipo_relatorio else ""
        self.drawString(2*cm, A4[1] - 1.2*cm, f"Planejamento Orcamentario 2026 - {self.nome_cliente}{tipo_txt}")
        self.setStrokeColor(CORES['linha'])
        self.line(2*cm, A4[1] - 1.4*cm, A4[0] - 2*cm, A4[1] - 1.4*cm)
        
        self.drawString(2*cm, 1.2*cm, "Budget Engine 2026")
        self.drawCentredString(A4[0]/2, 1.2*cm, datetime.now().strftime("%d/%m/%Y"))
        self.drawRightString(A4[0] - 2*cm, 1.2*cm, f"Pagina {page_num - 1} de {page_count - 1}")
        self.line(2*cm, 1.5*cm, A4[0] - 2*cm, 1.5*cm)


# ============================================================================
# GERAÇÃO DO RELATÓRIO COMPLETO
# ============================================================================

def gerar_relatorio_completo(motor, nome_cliente: str = "Cliente", observacoes: str = "", tipo_relatorio: str = "") -> BytesIO:
    """Gera relatório PDF completo e didático
    
    Args:
        motor: MotorCalculo com os dados
        nome_cliente: Nome do cliente/empresa
        observacoes: Observações adicionais
        tipo_relatorio: "Consolidado", "Filial" ou "" (detecta automaticamente)
    """
    buffer = BytesIO()
    
    # Detectar tipo de relatório automaticamente se não informado
    if not tipo_relatorio:
        tipo_relatorio = getattr(motor, 'tipo_relatorio', '')
        if not tipo_relatorio:
            # Tenta detectar pelo nome da filial
            filial_nome = getattr(motor, 'filial_nome', '')
            if filial_nome and 'consolidado' in filial_nome.lower():
                tipo_relatorio = "Consolidado"
            elif filial_nome:
                tipo_relatorio = "Filial"
    
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    
    styles = criar_estilos()
    story = []
    
    # Calcular DRE
    if not motor.dre:
        motor.calcular_dre()
    
    dre = motor.dre
    
    # Extrair totais
    receita_bruta = sum(dre.get('Receita Bruta Total', [0]*12))
    deducoes = abs(sum(dre.get('Total Deduções', [0]*12)))
    receita_liquida = sum(dre.get('Receita Líquida', [0]*12))
    custos_variaveis = abs(sum(dre.get('Total Custos Variáveis', [0]*12)))
    margem_contribuicao = sum(dre.get('Margem de Contribuição', [0]*12))
    custos_fixos = abs(sum(dre.get('Total Custos Fixos', [0]*12)))
    custos_pessoal = abs(sum(dre.get('Subtotal Pessoal', [0]*12)))
    despesas_fixas_total = abs(sum(dre.get('Total Despesas Fixas', [0]*12)))
    ebitda = sum(dre.get('EBITDA', [0]*12))
    resultado_liquido = sum(dre.get('Resultado Líquido', [0]*12))
    
    margem_ebitda = (ebitda / receita_bruta * 100) if receita_bruta > 0 else 0
    margem_liquida = (resultado_liquido / receita_bruta * 100) if receita_bruta > 0 else 0
    
    # Calcular sessões totais
    total_sessoes_ano = 0
    sessoes_por_servico = {}
    for nome_srv in motor.servicos.keys():
        sessoes_srv = 0
        for fisio in motor.fisioterapeutas.values():
            sessoes_srv += fisio.sessoes_por_servico.get(nome_srv, 0) * 12
        sessoes_por_servico[nome_srv] = sessoes_srv
        total_sessoes_ano += sessoes_srv
    
    # FC e PE
    try:
        fc = motor.calcular_fluxo_caixa()
        saldos_fc = fc.get('Saldo Final', [0]*12)
        aplicacoes_fc = fc.get('Saldo Aplicações', [0]*12) if 'Saldo Aplicações' in fc else None
        liquidez = saldos_fc[-1] + (aplicacoes_fc[-1] if aplicacoes_fc else 0)
    except:
        fc = {}
        saldos_fc = [0]*12
        aplicacoes_fc = None
        liquidez = 0
    
    try:
        pe_anual = motor.calcular_ponto_equilibrio_anual()
        margem_seguranca = pe_anual.margem_seguranca
        pe_contabil = pe_anual.pe_contabil
    except:
        margem_seguranca = 0
        pe_contabil = 0
    
    try:
        ocupacao = motor.calcular_ocupacao_anual()
        taxa_ocup_prof = sum(ocupacao.meses[m].taxa_ocupacao_profissional for m in range(12)) / 12
        taxa_ocup_sala = sum(ocupacao.meses[m].taxa_ocupacao_sala for m in range(12)) / 12
        ocup_prof_mensal = [ocupacao.meses[m].taxa_ocupacao_profissional for m in range(12)]
        ocup_sala_mensal = [ocupacao.meses[m].taxa_ocupacao_sala for m in range(12)]
    except:
        taxa_ocup_prof = 0
        taxa_ocup_sala = 0
        ocup_prof_mensal = [0]*12
        ocup_sala_mensal = [0]*12
    
    # ========================================================================
    # CAPA
    # ========================================================================
    story.append(Spacer(1, 3*cm))
    story.append(Paragraph("PLANEJAMENTO", styles['TituloCapa']))
    story.append(Paragraph("ORCAMENTARIO 2026", styles['TituloCapa']))
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="30%", thickness=3, color=CORES['primaria'], hAlign='CENTER'))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(nome_cliente, styles['SubtituloCapa']))
    
    # Badge do tipo de relatório
    if tipo_relatorio:
        badge_cor = CORES['primaria_clara'] if tipo_relatorio == "Consolidado" else CORES['verde']
        story.append(Paragraph(
            f"<font color='#{badge_cor.hexval()[2:]}'><b>[ {tipo_relatorio.upper()} ]</b></font>",
            ParagraphStyle('Badge', fontSize=12, alignment=TA_CENTER, spaceAfter=10)
        ))
    story.append(Spacer(1, 2*cm))
    
    story.append(criar_box_explicativo(
        "O que e este documento?",
        "Este relatorio apresenta a <b>projecao financeira</b> da sua empresa para 2026. "
        "Mostra quanto voce deve faturar, quais serao seus custos, se tera lucro ou prejuizo, "
        "e informacoes importantes para tomar decisoes sobre precos, investimentos e gastos.",
        "info"
    ))
    
    story.append(Spacer(1, 2*cm))
    info = f"<b>Data:</b> {datetime.now().strftime('%d/%m/%Y')}<br/><b>Periodo:</b> Janeiro a Dezembro de 2026"
    story.append(Paragraph(info, styles['InfoCapa']))
    story.append(PageBreak())
    
    # ========================================================================
    # SUMÁRIO
    # ========================================================================
    story.append(Paragraph("SUMARIO", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    sumario = [
        ("1.", "Visao Geral", "Os numeros mais importantes"),
        ("2.", "Receitas", "Quanto voce vai faturar"),
        ("3.", "Custos", "Para onde vai o dinheiro"),
        ("4.", "Custeio ABC", "Custo e lucro por sessao de cada servico"),
        ("5.", "Resultado Mensal", "Lucro ou prejuizo mes a mes"),
        ("6.", "Ponto de Equilibrio", "Quanto precisa faturar para nao ter prejuizo"),
        ("7.", "Taxa de Ocupacao", "Uso da capacidade da clinica"),
        ("8.", "Fluxo de Caixa", "Dinheiro entrando e saindo"),
        ("9.", "Indicadores", "Termometro de saude do negocio"),
        ("10.", "Conclusoes", "Resumo e recomendacoes"),
    ]
    
    for num, titulo, desc in sumario:
        story.append(Paragraph(f"<b>{num} {titulo}</b> - <i>{desc}</i>", styles['Texto']))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 1. VISÃO GERAL
    # ========================================================================
    story.append(Paragraph("1. VISAO GERAL", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "Como ler esta secao",
        "Aqui estao os <b>4 numeros mais importantes</b> do seu planejamento. "
        "Se voce so tiver 1 minuto, olhe apenas esta pagina!",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    cor_ebitda = 'bom' if ebitda > 0 else 'ruim'
    cor_margem = 'bom' if margem_seguranca > 20 else 'atencao' if margem_seguranca > 0 else 'ruim'
    
    kpis = [
        {'valor': fmt_moeda(receita_bruta, True), 'label': 'Receita Total',
         'explicacao': 'Tudo que voce vai faturar no ano', 'cor': 'normal'},
        {'valor': fmt_moeda(ebitda, True), 'label': 'Lucro Operacional',
         'explicacao': 'O que sobra apos pagar tudo', 'cor': cor_ebitda},
        {'valor': fmt_pct(margem_ebitda), 'label': 'Margem de Lucro',
         'explicacao': '% do faturamento que e lucro', 'cor': cor_ebitda},
        {'valor': fmt_pct(margem_seguranca), 'label': 'Margem de Seguranca',
         'explicacao': 'Folga antes do prejuizo', 'cor': cor_margem},
    ]
    
    story.append(criar_linha_kpis_didaticos(kpis))
    story.append(Spacer(1, 0.5*cm))
    
    if ebitda > 0:
        analise = f"""
        <b>Boa noticia!</b> Sua empresa esta projetada para ter <b>lucro</b> em 2026.<br/><br/>
        Voce deve faturar <b>{fmt_moeda(receita_bruta)}</b> no ano. Desse valor, 
        <b>{fmt_moeda(ebitda)}</b> vai sobrar como lucro ({margem_ebitda:.1f}%).<br/><br/>
        Voce tem uma "folga" de <b>{margem_seguranca:.1f}%</b> - pode faturar ate esse percentual 
        a menos do planejado e ainda assim nao ter prejuizo.
        """
        story.append(criar_box_explicativo("Analise do Resultado", analise, "sucesso"))
    else:
        analise = f"""
        <b>Atencao!</b> O planejamento atual mostra <b>prejuizo</b> de <b>{fmt_moeda(abs(ebitda))}</b>.<br/><br/>
        Os custos estao maiores que as receitas. E preciso:<br/>
        - Aumentar o faturamento (mais clientes ou precos maiores), OU<br/>
        - Reduzir custos (renegociar contratos, cortar despesas)
        """
        story.append(criar_box_explicativo("Analise do Resultado", analise, "alerta"))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 2. RECEITAS
    # ========================================================================
    story.append(Paragraph("2. RECEITAS", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "O que e Receita?",
        "<b>Receita</b> e todo o dinheiro que entra na empresa atraves da venda de servicos. "
        "E o seu <b>faturamento bruto</b>, antes de descontar qualquer custo ou imposto.",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    # Receita por serviço
    receita_por_servico = {}
    for nome, srv in motor.servicos.items():
        receita_srv = sum(dre.get(nome, [0]*12))
        if receita_srv > 0:
            receita_por_servico[nome] = receita_srv
    
    if receita_por_servico:
        grafico_srv = criar_grafico_barras_horizontal(receita_por_servico, 'Receita por Servico')
        story.append(Image(grafico_srv, width=15*cm, height=7*cm))
    
    story.append(Spacer(1, 0.3*cm))
    
    # Tabela de serviços
    dados_srv = [['Servico', 'Preco', 'Sessoes/Mes', 'Receita Anual', '%']]
    total_receita = sum(receita_por_servico.values())
    
    for nome, srv in motor.servicos.items():
        receita_srv = receita_por_servico.get(nome, 0)
        sessoes = sessoes_por_servico.get(nome, 0) / 12
        pct = receita_srv / total_receita * 100 if total_receita > 0 else 0
        dados_srv.append([nome, fmt_moeda(srv.valor_2026), fmt_num(sessoes), 
                          fmt_moeda(receita_srv), fmt_pct(pct)])
    
    dados_srv.append(['TOTAL', '', '', fmt_moeda(total_receita), '100%'])
    
    story.append(criar_tabela_simples(dados_srv, [4*cm, 2.5*cm, 2.5*cm, 3.5*cm, 2*cm], 
                                       destaque_linhas=[len(dados_srv)-1]))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 3. CUSTOS
    # ========================================================================
    story.append(Paragraph("3. CUSTOS", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "Tipos de Custos",
        "<b>Custos Fixos:</b> Voce paga todo mes, independente de quantos clientes atende "
        "(aluguel, salarios, sistema).<br/><br/>"
        "<b>Custos Variaveis:</b> Aumentam conforme voce atende mais clientes "
        "(materiais, comissoes).<br/><br/>"
        "<b>Impostos e Taxas:</b> Cobrados sobre o faturamento (taxas de cartao, impostos).",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    grafico_custos = criar_grafico_pizza(
        [custos_pessoal, despesas_fixas_total, custos_variaveis, deducoes],
        ['Pessoal', 'Despesas Fixas', 'Custos Variaveis', 'Impostos/Taxas'],
        'Composicao dos Custos'
    )
    story.append(Image(grafico_custos, width=12*cm, height=8*cm))
    
    story.append(Spacer(1, 0.3*cm))
    
    total_custos = custos_pessoal + despesas_fixas_total + custos_variaveis + deducoes
    
    dados_custos = [
        ['Categoria', 'Valor Anual', '% Receita', 'O que inclui'],
        ['Pessoal', fmt_moeda(custos_pessoal), fmt_pct(custos_pessoal/receita_bruta*100), 'Salarios, pro-labore'],
        ['Despesas Fixas', fmt_moeda(despesas_fixas_total), fmt_pct(despesas_fixas_total/receita_bruta*100), 'Aluguel, energia, sistema'],
        ['Custos Variaveis', fmt_moeda(custos_variaveis), fmt_pct(custos_variaveis/receita_bruta*100), 'Materiais, comissoes'],
        ['Impostos/Taxas', fmt_moeda(deducoes), fmt_pct(deducoes/receita_bruta*100), 'Taxas cartao, impostos'],
        ['TOTAL', fmt_moeda(total_custos), fmt_pct(total_custos/receita_bruta*100), ''],
    ]
    
    story.append(criar_tabela_simples(dados_custos, [3.5*cm, 3*cm, 2.5*cm, 6*cm], destaque_linhas=[5]))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 4. CUSTEIO ABC
    # ========================================================================
    story.append(Paragraph("4. CUSTEIO ABC - Analise por Servico", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "O que e Custeio ABC?",
        "E uma forma de calcular o <b>custo real de cada sessao</b> de cada servico. "
        "Assim voce sabe exatamente quanto <b>lucra por sessao</b> e quais servicos sao mais rentaveis.<br/><br/>"
        "<b>Custo por Sessao</b> = (Todos os custos) / (Total de sessoes)<br/>"
        "<b>Lucro por Sessao</b> = Preco - Custo<br/>"
        "<b>Margem</b> = Lucro / Preco x 100",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    # Calcular custeio ABC
    custo_total_sem_deducao = custos_pessoal + despesas_fixas_total + custos_variaveis
    custo_por_sessao_medio = custo_total_sem_deducao / total_sessoes_ano if total_sessoes_ano > 0 else 0
    
    servicos_abc = {}
    for nome, srv in motor.servicos.items():
        preco = srv.valor_2026
        receita_srv = receita_por_servico.get(nome, 0)
        sessoes_srv = sessoes_por_servico.get(nome, 0)
        
        if sessoes_srv > 0:
            # Custo proporcional ao número de sessões
            custo_srv = (sessoes_srv / total_sessoes_ano) * custo_total_sem_deducao if total_sessoes_ano > 0 else 0
            custo_sessao = custo_srv / sessoes_srv
            lucro_sessao = preco - custo_sessao
            margem_pct = (lucro_sessao / preco * 100) if preco > 0 else 0
            
            servicos_abc[nome] = {
                'preco': preco,
                'custo_sessao': custo_sessao,
                'lucro_sessao': lucro_sessao,
                'margem_pct': margem_pct,
                'receita': receita_srv,
                'sessoes': sessoes_srv
            }
    
    # Gráfico de custo por sessão
    if servicos_abc:
        grafico_custo_sessao = criar_grafico_custo_por_sessao(servicos_abc)
        story.append(Image(grafico_custo_sessao, width=15*cm, height=7*cm))
        story.append(Spacer(1, 0.3*cm))
    
    # Tabela de Custeio ABC
    story.append(Paragraph("<b>Detalhamento por Servico:</b>", styles['Subtitulo']))
    
    dados_abc = [['Servico', 'Preco', 'Custo/Sessao', 'Lucro/Sessao', 'Margem', 'Sessoes/Ano']]
    
    for nome, abc in sorted(servicos_abc.items(), key=lambda x: x[1]['margem_pct'], reverse=True):
        cor_margem = ''
        dados_abc.append([
            nome, 
            fmt_moeda(abc['preco']), 
            fmt_moeda(abc['custo_sessao']),
            fmt_moeda(abc['lucro_sessao']),
            fmt_pct(abc['margem_pct']),
            fmt_num(abc['sessoes'])
        ])
    
    story.append(criar_tabela_simples(dados_abc, [3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm, 2*cm]))
    story.append(Spacer(1, 0.3*cm))
    
    # Gráfico de rentabilidade
    story.append(Paragraph("<b>Ranking de Rentabilidade:</b>", styles['Subtitulo']))
    grafico_rent = criar_grafico_rentabilidade_servicos(servicos_abc)
    story.append(Image(grafico_rent, width=15*cm, height=6*cm))
    
    # Análise
    melhor_servico = max(servicos_abc.items(), key=lambda x: x[1]['margem_pct']) if servicos_abc else None
    pior_servico = min(servicos_abc.items(), key=lambda x: x[1]['margem_pct']) if servicos_abc else None
    
    if melhor_servico and pior_servico:
        analise_abc = f"""
        <b>Servico mais rentavel:</b> {melhor_servico[0]} com margem de {melhor_servico[1]['margem_pct']:.1f}%<br/>
        Cada sessao gera R$ {melhor_servico[1]['lucro_sessao']:.2f} de lucro.<br/><br/>
        <b>Servico menos rentavel:</b> {pior_servico[0]} com margem de {pior_servico[1]['margem_pct']:.1f}%<br/>
        Considere revisar o preco ou reduzir custos deste servico.
        """
        story.append(criar_box_explicativo("Analise de Rentabilidade", analise_abc, "info"))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 5. RESULTADO MENSAL
    # ========================================================================
    story.append(Paragraph("5. RESULTADO MES A MES", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "Como ler este grafico",
        "O grafico mostra <b>mes a mes</b> quanto voce vai faturar (barras azuis), "
        "quanto vai gastar (barras vermelhas) e o resultado (barras embaixo).<br/><br/>"
        "<b>Dica:</b> Se a barra azul for maior que a vermelha, sobra dinheiro!",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    receitas_mes = dre.get('Receita Bruta Total', [0]*12)
    custos_mes = [abs(dre.get('Total Deduções', [0]*12)[m]) + 
                  abs(dre.get('Total Custos Variáveis', [0]*12)[m]) + 
                  abs(dre.get('Total Custos Fixos', [0]*12)[m]) 
                  for m in range(12)]
    resultado_mes = dre.get('EBITDA', [0]*12)
    
    grafico_evol = criar_grafico_evolucao(MESES, receitas_mes, custos_mes, resultado_mes)
    story.append(Image(grafico_evol, width=17*cm, height=10*cm))
    
    meses_negativos = [MESES[i] for i, r in enumerate(resultado_mes) if r < 0]
    if meses_negativos:
        story.append(criar_box_explicativo(
            "Atencao aos meses criticos",
            f"Os meses <b>{', '.join(meses_negativos)}</b> estao projetados com prejuizo. "
            f"Planeje-se para ter reserva de caixa.",
            "alerta"
        ))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 6. PONTO DE EQUILÍBRIO (EXPANDIDO)
    # ========================================================================
    story.append(Paragraph("6. PONTO DE EQUILIBRIO", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "O que e Ponto de Equilibrio (PE)?",
        "E o <b>faturamento minimo</b> que voce precisa ter para pagar todas as contas, "
        "sem lucro e sem prejuizo.<br/><br/>"
        "<b>Se faturar MENOS que o PE:</b> Tera prejuizo<br/>"
        "<b>Se faturar MAIS que o PE:</b> Tera lucro<br/><br/>"
        "<b>Margem de Seguranca:</b> E a 'folga' que voce tem - quanto pode faturar a menos "
        "antes de comecar a ter prejuizo.",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    # Gráfico visual do PE
    grafico_pe = criar_grafico_ponto_equilibrio(receita_bruta, pe_contabil, margem_seguranca)
    story.append(Image(grafico_pe, width=16*cm, height=6*cm))
    story.append(Spacer(1, 0.3*cm))
    
    # KPIs do PE
    pe_sessoes = (pe_contabil / receita_bruta * total_sessoes_ano) if receita_bruta > 0 else 0
    pe_mensal = pe_contabil / 12
    
    kpis_pe = [
        {'valor': fmt_moeda(pe_contabil, True), 'label': 'PE Anual',
         'explicacao': 'Faturamento minimo no ano', 'cor': 'normal'},
        {'valor': fmt_moeda(pe_mensal, True), 'label': 'PE Mensal',
         'explicacao': 'Faturamento minimo por mes', 'cor': 'normal'},
        {'valor': fmt_num(pe_sessoes), 'label': 'PE em Sessoes',
         'explicacao': 'Sessoes minimas no ano', 'cor': 'normal'},
        {'valor': fmt_pct(margem_seguranca), 'label': 'Margem Seguranca',
         'explicacao': 'Sua folga antes do prejuizo', 
         'cor': 'bom' if margem_seguranca > 20 else 'atencao' if margem_seguranca > 0 else 'ruim'},
    ]
    
    story.append(criar_linha_kpis_didaticos(kpis_pe))
    story.append(Spacer(1, 0.5*cm))
    
    # PE por Serviço
    story.append(Paragraph("<b>Ponto de Equilibrio por Servico:</b>", styles['Subtitulo']))
    story.append(Paragraph(
        "Cada servico precisa atingir um numero minimo de sessoes para cobrir sua parte dos custos:",
        styles['Texto']
    ))
    
    servicos_pe = {}
    for nome, abc in servicos_abc.items():
        if abc['lucro_sessao'] > 0:
            custo_fixo_srv = (abc['sessoes'] / total_sessoes_ano) * (custos_fixos) if total_sessoes_ano > 0 else 0
            pe_sessoes_srv = custo_fixo_srv / abc['lucro_sessao'] if abc['lucro_sessao'] > 0 else 0
            servicos_pe[nome] = {
                'pe_sessoes': pe_sessoes_srv,
                'sessoes_projetadas': abc['sessoes'],
                'margem_srv': ((abc['sessoes'] - pe_sessoes_srv) / abc['sessoes'] * 100) if abc['sessoes'] > 0 else 0
            }
    
    if servicos_pe:
        grafico_pe_srv = criar_grafico_pe_por_servico(servicos_pe)
        story.append(Image(grafico_pe_srv, width=14*cm, height=6*cm))
    
    # Análise do PE
    if margem_seguranca > 30:
        msg_pe = f"Excelente! Margem de seguranca de <b>{margem_seguranca:.0f}%</b>. Voce pode perder ate esse percentual do faturamento sem ter prejuizo."
        tipo_pe = "sucesso"
    elif margem_seguranca > 15:
        msg_pe = f"Margem de seguranca <b>moderada</b> ({margem_seguranca:.1f}%). Monitore o faturamento mensalmente."
        tipo_pe = "info"
    else:
        msg_pe = f"Margem de seguranca <b>baixa</b> ({margem_seguranca:.1f}%). Qualquer queda no faturamento pode causar prejuizo. Revise seus custos!"
        tipo_pe = "alerta"
    
    story.append(criar_box_explicativo("O que isso significa", msg_pe, tipo_pe))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 7. TAXA DE OCUPAÇÃO (EXPANDIDO)
    # ========================================================================
    story.append(Paragraph("7. TAXA DE OCUPACAO", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "O que e Taxa de Ocupacao?",
        "Mede o <b>quanto da sua capacidade esta sendo usada</b>.<br/><br/>"
        "<b>Ocupacao dos Profissionais:</b> Quanto do tempo disponivel dos profissionais esta preenchido com atendimentos.<br/><br/>"
        "<b>Ocupacao das Salas:</b> Quanto do tempo das salas esta sendo utilizado.<br/><br/>"
        "<b>Meta ideal:</b> Entre 75% e 85%. Abaixo disso, ha capacidade ociosa. Acima, pode faltar horario para novos clientes.",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    # Ocupação por profissional
    story.append(Paragraph("<b>Ocupacao Media Anual:</b>", styles['Subtitulo']))
    
    ocupacoes = {
        'Profissionais': taxa_ocup_prof,
        'Salas': taxa_ocup_sala
    }
    
    # Ocupação por profissional individual
    ocup_por_prof = {}
    for nome, fisio in motor.fisioterapeutas.items():
        sessoes_prof = sum(fisio.sessoes_por_servico.values())
        horas_disponiveis = motor.operacional.horas_atendimento_dia * motor.operacional.dias_uteis_mes
        sessoes_possiveis = horas_disponiveis  # 1 sessão por hora
        taxa = (sessoes_prof / sessoes_possiveis * 100) if sessoes_possiveis > 0 else 0
        ocup_por_prof[nome] = min(taxa, 100)
    
    if ocup_por_prof:
        grafico_ocup_prof = criar_grafico_ocupacao_barras(ocup_por_prof, 'Ocupacao por Profissional')
        story.append(Image(grafico_ocup_prof, width=14*cm, height=6*cm))
    
    story.append(Spacer(1, 0.3*cm))
    
    # Evolução mensal da ocupação
    story.append(Paragraph("<b>Evolucao da Ocupacao ao Longo do Ano:</b>", styles['Subtitulo']))
    
    grafico_ocup_mensal = criar_grafico_ocupacao_mensal(MESES, ocup_prof_mensal, ocup_sala_mensal)
    story.append(Image(grafico_ocup_mensal, width=15*cm, height=6*cm))
    story.append(Spacer(1, 0.3*cm))
    
    # Análise de ocupação
    if taxa_ocup_prof >= 85:
        msg_ocup = f"Ocupacao <b>muito alta</b> ({taxa_ocup_prof:.1f}%). Considere contratar mais profissionais ou abrir mais horarios."
        tipo_ocup = "alerta"
    elif taxa_ocup_prof >= 70:
        msg_ocup = f"Ocupacao <b>saudavel</b> ({taxa_ocup_prof:.1f}%). Boa utilizacao da capacidade com espaco para crescer."
        tipo_ocup = "sucesso"
    else:
        msg_ocup = f"Ocupacao <b>baixa</b> ({taxa_ocup_prof:.1f}%). Ha muita capacidade ociosa. Invista em captacao de clientes."
        tipo_ocup = "alerta"
    
    story.append(criar_box_explicativo("Analise de Ocupacao", msg_ocup, tipo_ocup))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 8. FLUXO DE CAIXA
    # ========================================================================
    story.append(Paragraph("8. FLUXO DE CAIXA", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "O que e Fluxo de Caixa?",
        "E o <b>dinheiro que entra e sai</b> da sua conta bancaria. "
        "Mesmo tendo lucro no papel, voce pode ficar sem dinheiro se os clientes "
        "pagarem depois que voce precisa pagar as contas!<br/><br/>"
        "<b>Saldo Minimo:</b> Valor que voce deve sempre manter em caixa para emergencias.",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    saldo_minimo = motor.premissas_fc.saldo_minimo
    grafico_fc = criar_grafico_fluxo_caixa(MESES, saldos_fc, saldo_minimo, aplicacoes_fc)
    story.append(Image(grafico_fc, width=17*cm, height=6*cm))
    story.append(Spacer(1, 0.3*cm))
    
    total_entradas = sum(fc.get('Total Entradas', [0]*12))
    total_saidas = abs(sum(fc.get('Total Saídas', [0]*12)))
    
    kpis_fc = [
        {'valor': fmt_moeda(total_entradas, True), 'label': 'Total Entradas',
         'explicacao': 'Dinheiro que vai entrar', 'cor': 'bom'},
        {'valor': fmt_moeda(total_saidas, True), 'label': 'Total Saidas',
         'explicacao': 'Dinheiro que vai sair', 'cor': 'normal'},
        {'valor': fmt_moeda(saldos_fc[-1], True), 'label': 'Saldo Final',
         'explicacao': 'Quanto tera em Dez', 
         'cor': 'bom' if saldos_fc[-1] > saldo_minimo else 'ruim'},
        {'valor': fmt_moeda(liquidez, True), 'label': 'Liquidez Total',
         'explicacao': 'Caixa + Aplicacoes', 'cor': 'bom'},
    ]
    
    story.append(criar_linha_kpis_didaticos(kpis_fc))
    
    meses_criticos = [MESES[i] for i, s in enumerate(saldos_fc) if s < saldo_minimo]
    if meses_criticos:
        story.append(Spacer(1, 0.3*cm))
        story.append(criar_box_explicativo(
            "Meses com caixa abaixo do minimo",
            f"Nos meses <b>{', '.join(meses_criticos)}</b>, o saldo ficara abaixo de {fmt_moeda(saldo_minimo)}. "
            f"Planeje-se com antecedencia!",
            "alerta"
        ))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 9. INDICADORES
    # ========================================================================
    story.append(Paragraph("9. INDICADORES DE SAUDE", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    story.append(criar_box_explicativo(
        "Como ler os indicadores",
        "Cada indicador funciona como um <b>semaforo</b>:<br/><br/>"
        "<b>VERDE</b> = Esta tudo bem, continue assim!<br/>"
        "<b>AMARELO</b> = Atencao, pode melhorar<br/>"
        "<b>VERMELHO</b> = Precisa de acao urgente",
        "info"
    ))
    story.append(Spacer(1, 0.3*cm))
    
    indicadores = [
        {
            'nome': 'Resultado Operacional (EBITDA)',
            'valor': fmt_moeda(ebitda),
            'status': 'verde' if ebitda > 0 else 'vermelho',
            'explicacao': 'Lucro ou prejuizo das operacoes'
        },
        {
            'nome': 'Margem de Seguranca',
            'valor': fmt_pct(margem_seguranca),
            'status': 'verde' if margem_seguranca > 20 else 'amarelo' if margem_seguranca > 0 else 'vermelho',
            'explicacao': 'Folga antes do prejuizo'
        },
        {
            'nome': 'Taxa de Ocupacao',
            'valor': fmt_pct(taxa_ocup_prof),
            'status': 'verde' if 70 <= taxa_ocup_prof <= 85 else 'amarelo' if taxa_ocup_prof >= 60 else 'vermelho',
            'explicacao': 'Uso da capacidade da clinica'
        },
        {
            'nome': 'Liquidez Final',
            'valor': fmt_moeda(liquidez, True),
            'status': 'verde' if liquidez > saldo_minimo * 2 else 'amarelo' if liquidez > saldo_minimo else 'vermelho',
            'explicacao': 'Dinheiro disponivel ao final'
        },
        {
            'nome': 'Margem de Lucro',
            'valor': fmt_pct(margem_ebitda),
            'status': 'verde' if margem_ebitda > 20 else 'amarelo' if margem_ebitda > 10 else 'vermelho',
            'explicacao': 'Percentual que sobra do faturamento'
        },
    ]
    
    grafico_semaforo = criar_grafico_semaforo(indicadores)
    story.append(Image(grafico_semaforo, width=16*cm, height=7*cm))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 10. CONCLUSÕES
    # ========================================================================
    story.append(Paragraph("10. CONCLUSOES E RECOMENDACOES", styles['TituloCapitulo']))
    story.append(linha_sep(CORES['primaria'], 2))
    
    # Resumo
    story.append(Paragraph("<b>Resumo do Planejamento:</b>", styles['Subtitulo']))
    resumo = f"""
    <b>Receita Anual:</b> {fmt_moeda(receita_bruta)}<br/>
    <b>Custos Totais:</b> {fmt_moeda(total_custos)}<br/>
    <b>Resultado:</b> {fmt_moeda(ebitda)} ({fmt_pct(margem_ebitda)})<br/>
    <b>Ponto de Equilibrio:</b> {fmt_moeda(pe_contabil)} ({fmt_num(pe_sessoes)} sessoes)<br/>
    <b>Margem de Seguranca:</b> {fmt_pct(margem_seguranca)}
    """
    story.append(Paragraph(resumo, styles['Texto']))
    story.append(Spacer(1, 0.3*cm))
    
    # Análise automática
    pontos_fortes = []
    pontos_atencao = []
    recomendacoes = []
    
    if ebitda > 0:
        pontos_fortes.append("Resultado operacional positivo")
    else:
        pontos_atencao.append("Resultado operacional negativo")
        recomendacoes.append("Revisar estrutura de custos ou aumentar precos/volume")
    
    if margem_seguranca > 20:
        pontos_fortes.append("Boa margem de seguranca")
    elif margem_seguranca > 0:
        pontos_atencao.append("Margem de seguranca baixa")
        recomendacoes.append("Monitorar faturamento semanalmente")
    
    if 70 <= taxa_ocup_prof <= 85:
        pontos_fortes.append("Taxa de ocupacao saudavel")
    elif taxa_ocup_prof > 85:
        pontos_atencao.append("Ocupacao muito alta")
        recomendacoes.append("Avaliar contratacao de novos profissionais")
    else:
        pontos_atencao.append("Ocupacao baixa")
        recomendacoes.append("Investir em captacao de novos clientes")
    
    if liquidez > saldo_minimo * 2:
        pontos_fortes.append("Boa reserva de caixa")
    elif liquidez < saldo_minimo:
        pontos_atencao.append("Caixa abaixo do minimo")
        recomendacoes.append("Planejar linha de credito emergencial")
    
    if pontos_fortes:
        story.append(criar_box_explicativo("Pontos Fortes", "<br/>".join([f"- {p}" for p in pontos_fortes]), "sucesso"))
        story.append(Spacer(1, 0.3*cm))
    
    if pontos_atencao:
        story.append(criar_box_explicativo("Pontos de Atencao", "<br/>".join([f"- {p}" for p in pontos_atencao]), "alerta"))
        story.append(Spacer(1, 0.3*cm))
    
    story.append(Paragraph("<b>Recomendacoes:</b>", styles['Subtitulo']))
    if recomendacoes:
        for i, rec in enumerate(recomendacoes, 1):
            story.append(Paragraph(f"{i}. {rec}", styles['Texto']))
    else:
        story.append(Paragraph("Continue com o planejamento atual e monitore os indicadores mensalmente.", styles['Texto']))
    
    if observacoes:
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph("<b>Observacoes Adicionais:</b>", styles['Subtitulo']))
        story.append(Paragraph(observacoes, styles['Texto']))
    
    # Disclaimer
    story.append(Spacer(1, 1*cm))
    story.append(linha_sep())
    disclaimer = """<font size='8' color='#718096'><i>
    Este relatorio apresenta projecoes baseadas nas premissas informadas. 
    Os resultados reais podem variar. Recomenda-se revisao mensal.
    </i></font>"""
    story.append(Paragraph(disclaimer, styles['Rodape']))
    
    # Build
    def make_canvas(filename, **kwargs):
        return NumberedCanvas(filename, nome_cliente=nome_cliente, tipo_relatorio=tipo_relatorio, **kwargs)
    
    doc.build(story, canvasmaker=make_canvas)
    
    buffer.seek(0)
    return buffer


# Alias
def gerar_relatorio_do_motor(motor, nome_cliente: str = "Cliente", observacoes: str = "", tipo_relatorio: str = "") -> BytesIO:
    return gerar_relatorio_completo(motor, nome_cliente, observacoes, tipo_relatorio)
