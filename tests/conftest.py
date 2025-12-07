# tests/conftest.py
import os
import sys
import sqlite3
import pytest

# --- Garantir que a raiz do projeto esteja no sys.path ---

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import database  # agora deve funcionar, porque a raiz está no sys.path


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """
    Usa um arquivo de banco de dados temporário para todos os testes,
    sem encostar no 'assinaturas.db' real.
    """
    db_file = tmp_path / "assinaturas_test.db"

    # Guarda a função original ANTES de fazer o monkeypatch
    original_connect = sqlite3.connect

    def fake_connect(_path, *args, **kwargs):
        # Sempre aponta para o arquivo temporário,
        # mas usa a função original do sqlite3 para evitar recursão
        return original_connect(db_file, *args, **kwargs)

    # Monkeypatch só o connect usado dentro do módulo database
    monkeypatch.setattr(database.sqlite3, "connect", fake_connect)

    # Inicializa o schema no banco de teste
    database.init_db()

    yield
