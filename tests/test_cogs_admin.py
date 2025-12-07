# tests/test_cogs_admin.py
import pytest
from types import SimpleNamespace

import discord
from discord.ext import commands

import database
from cogs.admin import AdminCog  # ajuste se o nome for diferente


class DummyAuthor:
    def __init__(self, user_id=1, name="Admin"):
        self.id = user_id
        self.name = name
        self.mention = f"<@{user_id}>"
        self.avatar = None


class DummyCtx:
    def __init__(self, author=None):
        self.author = author or DummyAuthor()
        self.sent_messages = []

    async def send(self, *args, **kwargs):
        self.sent_messages.append({"args": args, "kwargs": kwargs})


@pytest.fixture
def bot():
    intents = discord.Intents.none()
    return commands.Bot(command_prefix="!", intents=intents)


@pytest.mark.asyncio
async def test_assinaturas_resumo_basico(bot, monkeypatch, tmp_path):
    """
    Testa se o comando !assinaturas envia pelo menos um embed com
    as estatísticas gerais usando o resumo retornado do banco.
    """
    # monta um resumo fake
    resumo_fake = {
        "total_ativas": 2,
        "total_expiradas": 1,
        "total_pendentes": 1,
        "ativas": [
            # user_id, username, data_expiracao, plano, data_ativacao, status, ultimo_aviso
            (1, "UserAtivo1", "2025-12-31 10:00:00", "Plano 30 dias", "2025-11-30 10:00:00", "ATIVA", None),
            (2, "UserAtivo2", "2025-12-25 10:00:00", "Plano 90 dias", "2025-10-25 10:00:00", "ATIVA", None),
        ],
        "expiradas": [
            (3, "UserExpirado", "2025-11-01 10:00:00", "Plano 30 dias", "2025-10-01 10:00:00", "EXPIRADA", None)
        ],
        "pendentes": [
            (2, "UserAtivo2", "2025-12-25 10:00:00", "Plano 90 dias", "2025-10-25 10:00:00", "ATIVA", None)
        ],
    }

    monkeypatch.setattr(database, "obter_resumo_assinaturas", lambda: resumo_fake)

    ctx = DummyCtx()
    cog = AdminCog(bot)
    command = cog.ver_assinaturas
    await command.callback(cog, ctx)

    # Primeiro envio deve ser o embed
    assert len(ctx.sent_messages) >= 1
    first = ctx.sent_messages[0]
    kwargs = first["kwargs"]
    assert "embed" in kwargs
    embed = kwargs["embed"]
    assert isinstance(embed, discord.Embed)
    assert "RELATÓRIO COMPLETO" in (embed.title or "").upper()

    # Deve ter um campo com ESTATÍSTICAS GERAIS
    names = [f.name for f in embed.fields]
    assert any("ESTATÍSTICAS GERAIS" in n for n in names)
