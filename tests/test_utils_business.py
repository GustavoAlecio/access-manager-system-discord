# tests/test_utils_business.py
import pytest
import datetime
from types import SimpleNamespace

import discord

import utils
import database


class DummyRole:
    def __init__(self, name="ASSINANTE"):
        self.name = name
        self.color = None


class DummyChannel:
    def __init__(self):
        self.permissions_set = []
        self.sent_messages = []

    async def set_permissions(self, role, **perms):
        self.permissions_set.append((role, perms))

    async def send(self, *args, **kwargs):
        self.sent_messages.append({"args": args, "kwargs": kwargs})


class DummyMember:
    def __init__(self, user_id=10, name="UserTeste", display_name="UserTeste"):
        self.id = user_id
        self.name = name
        self.display_name = display_name
        self.nick = display_name
        self.roles_added = []
        self.mention = f"<@{user_id}>"

    async def edit(self, **kwargs):
        if "nick" in kwargs:
            self.nick = kwargs["nick"]
            self.display_name = kwargs["nick"]

    async def add_roles(self, role, **kwargs):
        self.roles_added.append((role, kwargs))


class DummyGuild:
    def __init__(self, member, channel, existing_roles=None):
        self._member = member
        self._channel = channel
        self._roles = existing_roles or []

    def get_member(self, user_id):
        if self._member.id == user_id:
            return self._member
        return None

    def get_channel(self, channel_id):
        return self._channel

    @property
    def roles(self):
        return self._roles

    async def create_role(self, name, color, reason=None):
        role = DummyRole(name=name)
        self._roles.append(role)
        return role


@pytest.mark.asyncio
async def test_liberar_usuario_cria_cargo_e_atualiza_nick(monkeypatch):
    """
    Testa se liberar_usuario:
      - atualiza o nickname com a data
      - cria o cargo ASSINANTE se não existir
      - adiciona o cargo ao membro
      - chama adicionar_assinatura
    """
    member = DummyMember()
    channel = DummyChannel()
    guild = DummyGuild(member, channel, existing_roles=[])

    # monkeypatch do ID de canal e nome do cargo
    monkeypatch.setattr("utils.APOSTAS_CHANNEL_ID", 999, raising=False)
    monkeypatch.setattr("utils.CARGO_ASSINANTE_NOME", "ASSINANTE", raising=False)

    # interceptar chamadas ao adicionar_assinatura
    called = {}

    def fake_adicionar_assinatura(user_id, username, data_expiracao, plano):
        called["user_id"] = user_id
        called["username"] = username
        called["plano"] = plano
        called["data_expiracao"] = data_expiracao
        return True

    monkeypatch.setattr(utils, "adicionar_assinatura", fake_adicionar_assinatura)

    # executa
    msg = await utils.liberar_usuario(guild, member, dias=30)

    # nickname deve ter data no final
    assert " | " in member.nick
    # deve ter adicionado pelo menos um cargo
    assert len(member.roles_added) == 1
    role_adicionado, _ = member.roles_added[0]
    assert isinstance(role_adicionado, DummyRole)
    assert role_adicionado.name == "ASSINANTE"

    # adicionar_assinatura foi chamado?
    assert called["user_id"] == member.id
    assert called["username"] == member.name
    assert "Plano 30 dias" in called["plano"]

    # mensagem de retorno deve mencionar o usuário
    assert member.mention in msg
    assert "Plano 30 dias" in msg


@pytest.mark.asyncio
async def test_atualizar_nickname_renova_data(monkeypatch):
    """
    Testa se atualizar_nickname atualiza apenas a data no final do nick
    e chama adicionar_assinatura com plano 'Renovado X dias'.
    """
    # nick inicial com data antiga
    member = DummyMember(display_name="UserTeste | 01/01/2024")

    called = {}

    def fake_adicionar_assinatura(user_id, username, data_expiracao, plano):
        called["user_id"] = user_id
        called["username"] = username
        called["plano"] = plano
        called["data_expiracao"] = data_expiracao
        return True

    monkeypatch.setattr(utils, "adicionar_assinatura", fake_adicionar_assinatura)

    await utils.atualizar_nickname(member, dias=30)

    # novo nick ainda deve começar com o mesmo nome
    assert member.nick.startswith("UserTeste | ")
    # plano deve conter "Renovado 30 dias"
    assert "Renovado 30 dias" in called["plano"]
