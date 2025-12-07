import sqlite3
import os
import datetime  # ADICIONAR ESTE IMPORT
import shutil

def corrigir_banco_dados():
    """Corrige a estrutura do banco de dados"""
    try:
        if os.path.exists('assinaturas.db'):
            # Fazer backup
            shutil.copy2('assinaturas.db', 'assinaturas_backup.db')
            print("✓ Backup criado: assinaturas_backup.db")
        
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        # 1. Criar nova tabela com estrutura correta
        cursor.execute('DROP TABLE IF EXISTS assinaturas_nova')
        
        cursor.execute('''
            CREATE TABLE assinaturas_nova(
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                data_expiracao TEXT NOT NULL,
                plano TEXT NOT NULL,
                data_ativacao TEXT NOT NULL,
                status TEXT NOT NULL,
                ultimo_aviso TEXT
            )
        ''')
        
        # 2. Tenta copiar dados existentes (se houver)
        try:
            cursor.execute('SELECT * FROM assinaturas')
            dados = cursor.fetchall()
            
            for linha in dados:
                if len(linha) >= 3:
                    cursor.execute('''
                        INSERT INTO assinaturas_nova (user_id, data_expiracao, plano, username, data_ativacao, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        linha[0], 
                        linha[1] if len(linha) > 1 else '', 
                        linha[2] if len(linha) > 2 else '',
                        f"Usuario_{linha[0]}", 
                        datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                        "ATIVA"))
        except Exception as e:
            print(f"⚠ Não foi possível migrar dados antigos: {e}")
        
        # 3. Substituir tabela antiga
        cursor.execute('DROP TABLE IF EXISTS assinaturas')
        cursor.execute('ALTER TABLE assinaturas_nova RENAME TO assinaturas')
        
        # 4. Criar tabela de histórico
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
        
        print("✅ Banco de dados corrigido com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao corrigir banco de dados: {e}")
        return False

if __name__ == "__main__":
    corrigir_banco_dados()