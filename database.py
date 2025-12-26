"""
Módulo de conexão com banco de dados Supabase (PostgreSQL)
Sistema multi-tenant para Budget Engine
"""
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any

class Database:
    """Gerenciador de conexão com PostgreSQL do Supabase"""
    
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self) -> bool:
        """Conecta ao PostgreSQL do Supabase"""
        try:
            self.conn = psycopg2.connect(
                st.secrets["database"]["connection_string"]
            )
            return True
        except Exception as e:
            st.error(f"❌ Erro ao conectar ao banco: {e}")
            return False
    
    def get_cursor(self):
        """Retorna cursor para queries"""
        if not self.conn or self.conn.closed:
            self.connect()
        return self.conn.cursor(cursor_factory=RealDictCursor)
    
    def execute_query(self, query: str, params: tuple = None) -> Optional[List[Dict]]:
        """Executa query e retorna resultados"""
        try:
            cursor = self.get_cursor()
            cursor.execute(query, params)
            
            # Se for SELECT, retorna resultados
            if query.strip().upper().startswith('SELECT'):
                return cursor.fetchall()
            
            # Se for INSERT/UPDATE/DELETE, commita
            self.conn.commit()
            return None
            
        except Exception as e:
            self.conn.rollback()
            st.error(f"❌ Erro na query: {e}")
            return None
    
    def commit(self):
        """Commit das transações"""
        if self.conn:
            self.conn.commit()
    
    def rollback(self):
        """Rollback das transações"""
        if self.conn:
            self.conn.rollback()
    
    def close(self):
        """Fecha conexão"""
        if self.conn and not self.conn.closed:
            self.conn.close()


# Singleton da conexão
@st.cache_resource
def get_database():
    """Retorna instância única do banco de dados"""
    return Database()
