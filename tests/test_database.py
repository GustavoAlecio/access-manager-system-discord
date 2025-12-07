# tests/test_database.py
import datetime
from datetime import timedelta

import database


def test_init_db_cria_tabelas():
    """
    Garante que init_db cria as tabelas sem levantar exceção.
    (O schema já foi criado no conftest, mas chamamos de novo pra ver se não quebra.)
    """
    database.init_db()  # se der erro, o pytest já acusa
    # Se chegou aqui, está ok. Podemos opcionalmente tentar um SELECT simples:
    conn = database.sqlite3.connect("qualquer_coisa.db")  # será redirecionado pelo monkeypatch
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tabelas = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "assinaturas" in tabelas
    assert "historico" in tabelas


def test_adicionar_e_obter_assinatura():
    """
    Testa se adicionar_assinatura grava corretamente e se obter_assinatura retorna os dados.
    """
    user_id = 12345
    username = "TesteUser"
    plano = "Plano 30 dias"
    data_exp = datetime.datetime.now() + timedelta(days=30)

    ok = database.adicionar_assinatura(user_id, username, data_exp, plano)
    assert ok is True

    assinatura = database.obter_assinatura(user_id)
    assert assinatura is not None
    assert assinatura["user_id"] == user_id
    assert assinatura["username"] == username
    assert assinatura["plano"] == plano
    assert assinatura["status"] == "ATIVA"
    # data_expiracao deve estar em formato ISO
    assert len(assinatura["data_expiracao"]) >= 10
    assert "-" in assinatura["data_expiracao"]  # YYYY-MM-DD ...


def test_registrar_aviso_grava_ultimo_aviso():
    """
    Testa se registrar_aviso preenche o campo ultimo_aviso
    e cria um registro no histórico.
    """
    user_id = 999
    username = "AvisoUser"
    plano = "Plano 30 dias"
    data_exp = datetime.datetime.now() + timedelta(days=10)

    # cria assinatura
    database.adicionar_assinatura(user_id, username, data_exp, plano)

    # registra aviso
    ok = database.registrar_aviso(user_id, "AVISO_TESTE")
    assert ok is True

    assinatura = database.obter_assinatura(user_id)
    assert assinatura is not None
    assert assinatura["ultimo_aviso"] is not None
    # formato ISO: deve conter '-'
    assert "-" in assinatura["ultimo_aviso"]


def test_obter_resumo_assinaturas_pendentes_ate_5_dias():
    """
    Cria 3 assinaturas:
      - 10 dias à frente → não deve entrar em pendentes
      - 5 dias à frente  → deve entrar
      - 1 dia à frente   → deve entrar
    E valida se resumo['total_pendentes'] é 2.
    """
    # Assinatura A: 10 dias (não pendente)
    database.adicionar_assinatura(
        user_id=1,
        username="User10",
        data_expiracao=datetime.datetime.now() + timedelta(days=10),
        plano="Plano 30 dias",
    )

    # Assinatura B: 5 dias (pendente)
    database.adicionar_assinatura(
        user_id=2,
        username="User5",
        data_expiracao=datetime.datetime.now() + timedelta(days=5),
        plano="Plano 30 dias",
    )

    # Assinatura C: 1 dia (pendente)
    database.adicionar_assinatura(
        user_id=3,
        username="User1",
        data_expiracao=datetime.datetime.now() + timedelta(days=1),
        plano="Plano 30 dias",
    )

    resumo = database.obter_resumo_assinaturas()
    assert resumo is not None

    # total_ativas deve ser 3
    assert resumo["total_ativas"] == 3
    # pendentes (<= 5 dias) devem ser 2 (User5 e User1)
    assert resumo["total_pendentes"] == 2

    # podemos também garantir que 'User10' não está na lista de pendentes
    pendentes_nomes = {row[1] for row in resumo["pendentes"]}
    assert "User10" not in pendentes_nomes
    assert "User5" in pendentes_nomes
    assert "User1" in pendentes_nomes
