# tests/test_cogs_assinaturas.py
import pytest
import datetime
from types import SimpleNamespace

import discord
from discord.ext import commands

import database
from database import DB_DATETIME_FORMAT
import cogs.assinaturas as assinaturas_module


class DummyAuthor:
    def __init__(self, user_id=123, name="UserTeste"):
        self.id = user_id
        self.name = name
        self.mention = f"<@{user_id}>"
        self.avatar = None  # pra não precisar de URL


class DummyCtx:
    def __init__(self, author=None):
        self.author = author or DummyAuthor()
        self.sent_messages = []

    async def send(self, *args, **kwargs):
        # salva tudo que foi "enviado" pra gente inspecionar
        self.sent_messages.append({"args": args, "kwargs": kwargs})


@pytest.fixture
def bot():
    intents = discord.Intents.none()
    bot = commands.Bot(command_prefix="!", intents=intents)
    return bot


@pytest.mark.asyncio
async def test_minha_assinatura_sem_registro(bot, monkeypatch):
    """
    Se o usuário não tiver assinatura no banco,
    o comando deve avisar isso claramente.
    """
    # monkeypatch: nenhuma assinatura encontrada
    monkeypatch.setattr(assinaturas_module, "obter_assinatura", lambda _id: None)

    cog = assinaturas_module.AssinaturasCog(bot)
    ctx = DummyCtx()
    command = cog.minha_assinatura
    await command.callback(cog, ctx)

    assert len(ctx.sent_messages) == 1
    args = ctx.sent_messages[0]["args"]
    # mensagem simples (sem embed)
    assert isinstance(args[0], str)
    assert "não possui uma assinatura ativa" in args[0]


@pytest.mark.asyncio
async def test_minha_assinatura_com_registro(bot, monkeypatch):
    """
    Se o usuário tiver assinatura registrada,
    deve receber um embed com as informações básicas.
    """
    author = DummyAuthor(user_id=42, name="Assinante")
    ctx = DummyCtx(author=author)

    # monta uma assinatura fake no formato esperado
    now = datetime.datetime.now()
    assinatura_fake = {
        "user_id": author.id,
        "username": author.name,
        "data_expiracao": (now + datetime.timedelta(days=10)).strftime(DB_DATETIME_FORMAT),
        "plano": "Plano 30 dias",
        "data_ativacao": now.strftime(DB_DATETIME_FORMAT),
        "status": "ATIVA",
        "ultimo_aviso": None,
    }

    monkeypatch.setattr(assinaturas_module, "obter_assinatura", lambda _id: assinatura_fake)

    cog = assinaturas_module.AssinaturasCog(bot)
    command = cog.minha_assinatura
    await command.callback(cog, ctx)

    assert len(ctx.sent_messages) == 1
    kwargs = ctx.sent_messages[0]["kwargs"]
    assert "embed" in kwargs

    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert "SUA ASSINATURA" in (embed.title or "").upper()

    # confere se o plano está em algum campo do embed
    planos = [f.value for f in embed.fields if "Plano" in f.name]
    assert any("Plano 30 dias" in v for v in planos)
