# tests/test_cog_checagem_assinaturas.py
import datetime
from datetime import timedelta

import pytest

import cogs.tasks as tasks_module  # ajuste o caminho se sua ChecagemAssinaturas estiver em outro arquivo
from cogs.tasks import ChecagemAssinaturas


# ---------- Dummies de Discord ----------

class DummyDM:
    def __init__(self):
        self.sent_messages = []

    async def send(self, content=None, **kwargs):
        self.sent_messages.append({"content": content, "kwargs": kwargs})


class DummyMember:
    def __init__(self, user_id, name, nick):
        self.id = user_id
        self.name = name
        self.nick = nick
        self.display_name = nick
        self._dm = DummyDM()
        self.roles_removed = []
        self.kicked = False
        self.mention = f"<@{user_id}>"

    async def create_dm(self):
        return self._dm

    async def remove_roles(self, role, **kwargs):
        self.roles_removed.append((role, kwargs))

    async def kick(self, **kwargs):
        self.kicked = True


class DummyRole:
    def __init__(self, name):
        self.name = name


class DummyChannel:
    def __init__(self):
        self.sent_messages = []

    async def send(self, content=None, **kwargs):
        self.sent_messages.append({"content": content, "kwargs": kwargs})


class DummyGuild:
    def __init__(self, members, roles, notification_channel=None):
        self.members = members
        self._roles = roles
        self._notification_channel = notification_channel

    @property
    def roles(self):
        return self._roles

    def get_channel(self, channel_id):
        return self._notification_channel


class DummyBot:
    def __init__(self, guild):
        self._guild = guild

    def get_guild(self, server_id):
        # para os testes, qualquer SERVER_ID devolve o guild fake
        return self._guild


# ---------- Testes ----------

@pytest.mark.asyncio
async def test_checagem_envia_aviso_5_dias(monkeypatch):
    """
    Usuário com nick 'User5 | <data em 5 dias>' deve receber DM de aviso
    e registrar aviso de 5 dias.
    """
    hoje = datetime.date.today()
    data_5 = (hoje + timedelta(days=5)).strftime("%d/%m/%Y")
    nick = f"User5 | {data_5}"

    member = DummyMember(user_id=1, name="User5", nick=nick)
    role_assinante = DummyRole(name=tasks_module.CARGO_ASSINANTE_NOME)
    guild = DummyGuild(members=[member], roles=[role_assinante])

    bot = DummyBot(guild)

    # monkeypatch SERVER_ID para qualquer valor
    monkeypatch.setattr(tasks_module, "SERVER_ID", 123, raising=False)

    # obter_assinatura -> sem ultimo_aviso (primeiro aviso)
    def fake_obter_assinatura(user_id):
        return {
            "user_id": user_id,
            "username": "User5",
            "data_expiracao": "",  # não usado aqui
            "plano": "Plano 30 dias",
            "data_ativacao": "",
            "status": "ATIVA",
            "ultimo_aviso": None,
        }

    avisos_registrados = []

    def fake_registrar_aviso(user_id, tipo_aviso):
        avisos_registrados.append((user_id, tipo_aviso))
        return True

    monkeypatch.setattr(tasks_module, "obter_assinatura", fake_obter_assinatura)
    monkeypatch.setattr(tasks_module, "registrar_aviso", fake_registrar_aviso)

    cog = ChecagemAssinaturas(bot)

    # em teste, chamamos só a versão "uma vez"
    await cog._rodar_checar_assinaturas_uma_vez()

    # Deve ter mandado 1 DM
    assert len(member._dm.sent_messages) == 1
    conteudo = member._dm.sent_messages[0]["content"]
    assert "5 dias" in conteudo
    assert "sua assinatura expira" in conteudo

    # Deve ter registrado aviso de 5 dias
    assert avisos_registrados == [(1, "AVISO_5_DIAS")]


@pytest.mark.asyncio
async def test_checagem_remove_usuario_expirado_1_dia(monkeypatch):
    """
    Usuário com nick 'User | <data de ontem>' deve:
    - receber DM de expiração
    - ter o cargo removido
    - ser kickado
    - ter status atualizado para EXPIRADA
    - gerar mensagem no canal de notificação
    """
    hoje = datetime.date.today()
    data_ontem = (hoje - timedelta(days=1)).strftime("%d/%m/%Y")
    nick = f"UserExp | {data_ontem}"

    member = DummyMember(user_id=2, name="UserExp", nick=nick)
    role_assinante = DummyRole(name=tasks_module.CARGO_ASSINANTE_NOME)
    canal_notificacao = DummyChannel()
    guild = DummyGuild(members=[member], roles=[role_assinante], notification_channel=canal_notificacao)

    bot = DummyBot(guild)

    monkeypatch.setattr(tasks_module, "SERVER_ID", 123, raising=False)
    monkeypatch.setattr(tasks_module, "NOTIFICACAO_CHANNEL_ID", 999, raising=False)

    def fake_obter_assinatura(user_id):
        return {
            "user_id": user_id,
            "username": "UserExp",
            "data_expiracao": "",
            "plano": "Plano 30 dias",
            "data_ativacao": "",
            "status": "ATIVA",
            "ultimo_aviso": None,
        }

    status_atualizados = []

    def fake_atualizar_status(user_id, status, motivo=""):
        status_atualizados.append((user_id, status, motivo))
        return True

    monkeypatch.setattr(tasks_module, "obter_assinatura", fake_obter_assinatura)
    monkeypatch.setattr(tasks_module, "atualizar_status_assinatura", fake_atualizar_status)

    cog = ChecagemAssinaturas(bot)
    await cog._rodar_checar_assinaturas_uma_vez()

    # Deve ter tentado enviar DM de expiração
    assert len(member._dm.sent_messages) == 1
    assert "SUA ASSINATURA EXPIROU" in member._dm.sent_messages[0]["content"]

    # Deve ter removido o cargo e dado kick
    assert len(member.roles_removed) == 1
    role_removido, _ = member.roles_removed[0]
    assert role_removido.name == tasks_module.CARGO_ASSINANTE_NOME
    assert member.kicked is True

    # Status atualizado para EXPIRADA
    assert len(status_atualizados) == 1
    user_id, status, motivo = status_atualizados[0]
    assert user_id == 2
    assert status == "EXPIRADA"
    assert "Removido do servidor após 1 dia" in motivo

    # Notificação enviada no canal certo
    assert len(canal_notificacao.sent_messages) == 1
    texto = canal_notificacao.sent_messages[0]["content"]
    assert "RELATÓRIO DE EXPIRAÇÃO" in texto
    assert "UserExp" in texto
