"""
Página Streamlit - Consultor Financeiro IA
==========================================

Integração do Consultor IA com o Budget Engine.
"""

import streamlit as st
from typing import Optional
import sys
import os

# Adiciona path do projeto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from consultor_ia import (
        ConsultorFinanceiro,
        criar_consultor_local,
        verificar_instalacao,
        MODELOS_RECOMENDADOS
    )
    CONSULTOR_DISPONIVEL = True
except ImportError as e:
    CONSULTOR_DISPONIVEL = False
    ERRO_IMPORT = str(e)


def render_status_ollama():
    """Renderiza status da instalação Ollama."""
    
    status = verificar_instalacao()
    
    if status["pronto"]:
        st.success(f"✅ **Ollama Pronto** | Modelo: `{status['modelo_atual']}`")
        
        with st.expander("📋 Modelos Instalados"):
            for m in status["modelos_instalados"]:
                st.code(m)
    else:
        st.error("❌ **Ollama não está pronto**")
        
        for instrucao in status["instrucoes"]:
            st.warning(instrucao)
        
        st.markdown("""
        ### 📥 Como Instalar:
        
        **1. Baixe o Ollama:**
        ```bash
        # Windows/Mac: https://ollama.ai/download
        # Linux:
        curl -fsSL https://ollama.ai/install.sh | sh
        ```
        
        **2. Inicie o servidor:**
        ```bash
        ollama serve
        ```
        
        **3. Baixe um modelo:**
        ```bash
        ollama pull qwen2.5:7b
        ```
        
        **4. Recarregue esta página**
        """)
        
        st.markdown("### 🎯 Modelos Recomendados:")
        
        for modelo, info in MODELOS_RECOMENDADOS.items():
            st.markdown(f"""
            **{info['nome']}** (`{modelo}`)
            - RAM: {info['ram']} | Qualidade: {info['qualidade']} | Velocidade: {info['velocidade']}
            - {info.get('descricao', '')}
            """)
    
    return status["pronto"]


def render_chat(consultor: ConsultorFinanceiro):
    """Renderiza interface de chat."""
    
    st.markdown("### 💬 Chat com o Consultor")
    
    # Histórico de mensagens
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    
    # Container para mensagens
    chat_container = st.container()
    
    with chat_container:
        for msg in st.session_state.chat_messages:
            if msg["role"] == "user":
                st.markdown(f"**👤 Você:** {msg['content']}")
            else:
                st.markdown(f"**🤖 Consultor:** {msg['content']}")
            st.markdown("---")
    
    # Input
    col1, col2 = st.columns([5, 1])
    
    with col1:
        pergunta = st.text_input(
            "Faça uma pergunta:",
            placeholder="Ex: Por que meu fluxo de caixa fica negativo em março?",
            key="chat_input",
            label_visibility="collapsed"
        )
    
    with col2:
        enviar = st.button("📤 Enviar", use_container_width=True)
    
    if enviar and pergunta:
        with st.spinner("🤔 Analisando..."):
            try:
                resposta = consultor.perguntar(pergunta)
                
                st.session_state.chat_messages.append({"role": "user", "content": pergunta})
                st.session_state.chat_messages.append({"role": "assistant", "content": resposta})
                
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")
    
    # Botão limpar
    if st.session_state.chat_messages:
        if st.button("🗑️ Limpar Conversa"):
            st.session_state.chat_messages = []
            consultor.limpar_historico()
            st.rerun()


def render_analises_rapidas(consultor: ConsultorFinanceiro):
    """Renderiza botões de análises prontas."""
    
    st.markdown("### 📊 Análises Rápidas")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🩺 Diagnóstico Completo", use_container_width=True):
            with st.spinner("Gerando diagnóstico..."):
                resultado = consultor.diagnostico()
            st.session_state.ultima_analise = ("Diagnóstico", resultado)
    
    with col2:
        if st.button("⚠️ Alertas e Riscos", use_container_width=True):
            with st.spinner("Identificando alertas..."):
                resultado = consultor.alertas()
            st.session_state.ultima_analise = ("Alertas", resultado)
    
    with col3:
        if st.button("💵 Fluxo de Caixa", use_container_width=True):
            with st.spinner("Analisando fluxo de caixa..."):
                resultado = consultor.analisar_fluxo_caixa()
            st.session_state.ultima_analise = ("Fluxo de Caixa", resultado)
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        if st.button("📈 Análise DRE", use_container_width=True):
            with st.spinner("Analisando DRE..."):
                resultado = consultor.analisar_dre()
            st.session_state.ultima_analise = ("DRE", resultado)
    
    with col5:
        if st.button("⚖️ Ponto de Equilíbrio", use_container_width=True):
            with st.spinner("Analisando PE..."):
                resultado = consultor.analisar_ponto_equilibrio()
            st.session_state.ultima_analise = ("Ponto de Equilíbrio", resultado)
    
    with col6:
        if st.button("📋 Relatório Executivo", use_container_width=True):
            with st.spinner("Gerando relatório..."):
                resultado = consultor.relatorio_executivo()
            st.session_state.ultima_analise = ("Relatório Executivo", resultado)
    
    # Exibe última análise
    if "ultima_analise" in st.session_state:
        titulo, conteudo = st.session_state.ultima_analise
        
        st.markdown(f"---")
        st.markdown(f"## 📄 {titulo}")
        st.markdown(conteudo)
        
        # Botão copiar
        st.download_button(
            "📥 Baixar como TXT",
            conteudo,
            file_name=f"{titulo.lower().replace(' ', '_')}.txt",
            mime="text/plain"
        )


def render_simulador(consultor: ConsultorFinanceiro):
    """Renderiza simulador de cenários."""
    
    st.markdown("### 🎮 Simulador 'E se?'")
    
    st.markdown("""
    Teste cenários hipotéticos e veja o impacto no orçamento.
    
    **Exemplos:**
    - "E se eu aumentar os preços em 10%?"
    - "E se eu contratar mais 2 fisioterapeutas?"
    - "E se eu reduzir o aluguel em R$ 2.000?"
    - "E se eu perder 20% das sessões de Pilates?"
    """)
    
    cenario = st.text_area(
        "Descreva o cenário que quer simular:",
        height=100,
        placeholder="Ex: E se eu demitir 1 recepcionista e aumentar o marketing em R$ 1.000/mês?"
    )
    
    if st.button("🚀 Simular Cenário", disabled=not cenario):
        with st.spinner("Simulando cenário..."):
            try:
                resultado = consultor.simular(cenario)
                
                st.markdown("---")
                st.markdown("## 📊 Resultado da Simulação")
                st.markdown(resultado)
                
            except Exception as e:
                st.error(f"❌ Erro: {str(e)}")


def render_pagina_consultor(motor=None):
    """
    Renderiza página completa do consultor.
    
    Args:
        motor: Instância do MotorCalculo (se não passar, usa st.session_state.motor)
    """
    
    st.title("🤖 Consultor Financeiro IA")
    st.markdown("*Especialista em Controladoria para Clínicas de Fisioterapia*")
    
    # Verifica se módulo está disponível
    if not CONSULTOR_DISPONIVEL:
        st.error(f"❌ Módulo consultor_ia não disponível: {ERRO_IMPORT}")
        return
    
    # Verifica motor
    if motor is None:
        motor = st.session_state.get("motor", None)
    
    if motor is None:
        st.warning("⚠️ **Nenhum orçamento carregado.**")
        st.info("Carregue um cliente primeiro para usar o consultor.")
        
        # Ainda mostra status do Ollama
        st.markdown("---")
        st.markdown("### ⚙️ Status do Sistema")
        render_status_ollama()
        return
    
    # Verifica Ollama
    st.markdown("### ⚙️ Status do Sistema")
    ollama_ok = render_status_ollama()
    
    if not ollama_ok:
        return
    
    # Inicializa consultor
    if "consultor_ia" not in st.session_state:
        st.session_state.consultor_ia = criar_consultor_local(motor=motor)
    else:
        # Atualiza motor se necessário
        st.session_state.consultor_ia.carregar_motor(motor)
    
    consultor = st.session_state.consultor_ia
    
    # Exibe métricas resumidas
    metricas = consultor.get_metricas_resumo()
    
    if metricas and "erro" not in metricas:
        st.markdown("---")
        st.markdown(f"### 📊 {metricas.get('empresa', '')} - {metricas.get('filial', '')}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("💰 Receita Mensal", f"R$ {metricas.get('receita_mensal', 0):,.0f}")
        
        with col2:
            st.metric("👥 Folha % Receita", f"{metricas.get('folha_pct', 0):.1f}%")
        
        with col3:
            st.metric("🩺 Profissionais", metricas.get('qtd_fisios', 0))
        
        with col4:
            st.metric("📋 Serviços", metricas.get('qtd_servicos', 0))
    
    # Tabs principais
    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["💬 Chat", "📊 Análises Rápidas", "🎮 Simulador"])
    
    with tab1:
        render_chat(consultor)
    
    with tab2:
        render_analises_rapidas(consultor)
    
    with tab3:
        render_simulador(consultor)


# Para rodar standalone (teste)
if __name__ == "__main__":
    st.set_page_config(
        page_title="Consultor Financeiro IA",
        page_icon="🤖",
        layout="wide"
    )
    
    render_pagina_consultor()
