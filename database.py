# database.py
import sqlite3
import datetime
from datetime import timedelta
import logging

DB_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
LEGACY_DATETIME_FORMAT = "%d/%m/%Y %H:%M:%S"
DISPLAY_FORMAT = "%d/%m/%Y"

logger = logging.getLogger(__name__)

def init_db():
    """Inicializa o banco de dados SQLite"""
    try: 
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
    
        # Tabela principal de assinaturas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assinaturas(
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                data_expiracao TEXT NOT NULL,
                plano TEXT NOT NULL,
                data_ativacao TEXT NOT NULL,
                status TEXT NOT NULL,
                ultimo_aviso TEXT
            )
        ''')
        
        # Tabela de histórico
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS historico(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                acao TEXT NOT NULL,
                detalhes TEXT,
                data_hora TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Banco de dados inicializado com sucesso!")
        return True
    except Exception as e:
        logger.error(f"Erro ao inicializar Banco de dados: {e}")
        return False

def adicionar_assinatura(user_id: int, username: str, data_expiracao: datetime.datetime, plano: str):
    """Adiciona ou atualiza uma assinatura no banco de dados"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        data_exp_str = data_expiracao.strftime(DB_DATETIME_FORMAT)
        data_ativacao = datetime.datetime.now().strftime(DB_DATETIME_FORMAT)
        
        # VERIFICAR se o usuário já existe
        cursor.execute('SELECT user_id FROM assinaturas WHERE user_id = ?', (user_id,))
        existe = cursor.fetchone()
        
        if existe:
            # ATUALIZAR
            cursor.execute('''
                UPDATE assinaturas 
                SET username = ?, data_expiracao = ?, plano = ?, data_ativacao = ?, status = ?, ultimo_aviso = NULL
                WHERE user_id = ?
            ''', (username, data_exp_str, plano, data_ativacao, "ATIVA", user_id))
        else:
            # INSERIR NOVO
            cursor.execute('''
                INSERT INTO assinaturas 
                (user_id, username, data_expiracao, plano, data_ativacao, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, data_exp_str, plano, data_ativacao, "ATIVA"))
        
        conn.commit()
        conn.close()
        logger.info(f"Assinatura adicionada/atualizada para {username} (ID: {user_id})")
        return True
    except Exception as e:
        logger.error(f"Error ao adicionar assinatura: {e}")
        return False

def atualizar_status_assinatura(user_id: int, status: str, motivo: str = ""):
    """Atualiza o status de uma assinatura"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE assinaturas SET status = ? WHERE user_id = ?
        ''', (status, user_id))

        # Registrar no histórico
        cursor.execute('''
            INSERT INTO historico (user_id, acao, detalhes)
            VALUES (?, ?, ?)
        ''', (user_id, f"STATUS_{status}", motivo))
        
        conn.commit()
        conn.close()
        logger.info(f"Status atualizado para usuário {user_id}: {status}")
        return True
    except Exception as e:
        logger.error(f"Erro ao atualizar status: {e}")
        return False

def registrar_aviso(user_id: int, tipo_aviso: str):
    """Registra quando um aviso foi enviado"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        data_aviso =  datetime.datetime.now().strftime(DB_DATETIME_FORMAT)
        cursor.execute('''
            UPDATE assinaturas SET ultimo_aviso = ? WHERE user_id = ?
        ''', (data_aviso, user_id))
        
        # Registrar no histórico
        cursor.execute('''
            INSERT INTO historico (user_id, acao, detalhes)
            VALUES (?, ?, ?)
        ''', (user_id, "AVISO", f"Tipo: {tipo_aviso}"))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Erro ao registrar aviso: {e}")
        return False

def obter_assinatura(user_id: int):
    """Obtém informações de uma assinatura específica"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM assinaturas WHERE user_id = ?', (user_id,))
        resultado = cursor.fetchone()
        conn.close()
        
        if resultado:
            return {
                'user_id': resultado[0],
                'username': resultado[1],
                'data_expiracao': resultado[2],
                'plano': resultado[3],
                'data_ativacao': resultado[4],
                'status': resultado[5],
                'ultimo_aviso': resultado[6]
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao obter assinatura: {e}")
        return None

def obter_todas_assinaturas():
    """Obtém todas as assinaturas do banco de dados"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM assinaturas ORDER BY data_expiracao')
        resultados = cursor.fetchall()
        conn.close()
        
        assinaturas = []
        for resultado in resultados:
            assinaturas.append({
                'user_id': resultado[0],
                'username': resultado[1],
                'data_expiracao': resultado[2],
                'plano': resultado[3],
                'data_ativacao': resultado[4],
                'status': resultado[5],
                'ultimo_aviso': resultado[6]
            })
        return assinaturas
    except Exception as e:
        logger.error(f"Erro ao obter assinaturas: {e}")
        return []

def obter_resumo_assinaturas():
    """Obtém um resumo completo das assinaturas"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        # Contagem por status
        cursor.execute('SELECT status, COUNT(*) FROM assinaturas GROUP BY status')
        status_counts = dict(cursor.fetchall())
        
        # Assinaturas ativas
        cursor.execute('SELECT * FROM assinaturas WHERE status = "ATIVA" ORDER BY data_expiracao')
        ativas = cursor.fetchall()
        
        # Assinaturas expiradas
        cursor.execute('SELECT * FROM assinaturas WHERE status = "EXPIRADA" ORDER BY data_expiracao')
        expiradas = cursor.fetchall()
        
        # Assinaturas pendentes (a expirar em até 5 dias)
        hoje = datetime.datetime.now().date()
        limite = (hoje + timedelta(days=5)).strftime("%Y-%m-%d")
        
        cursor.execute('''
            SELECT * FROM assinaturas 
            WHERE status = "ATIVA" 
            AND date(data_expiracao) <= ?
            ORDER BY data_expiracao
        ''', (limite,))
        pendentes = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_ativas': status_counts.get('ATIVA', 0),
            'total_expiradas': status_counts.get('EXPIRADA', 0),
            'total_pendentes': len(pendentes),
            'ativas': ativas,
            'expiradas': expiradas,
            'pendentes': pendentes
        }
    except Exception as e:
        logger.error(f"Erro ao obter resumo: {e}")
        return None