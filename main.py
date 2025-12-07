# main.py
import os
import discord
from discord.ext import commands
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from config import *
from database import init_db
from views import PlanoSelect

# Configuração de logging
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Handler para arquivo
    file_handler = RotatingFileHandler("bot.log", maxBytes=10*1024*1024, backupCount=5)
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Handler para console
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

# Carrega variáveis de ambiente
load_dotenv()

# Configuração do bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIXO, intents=intents)

@bot.event
async def on_ready():
    logger = logging.getLogger(__name__)
    logger.info(f"Bot conectado como {bot.user}")
    
    # Inicializar banco de dados
    init_db()
    
    # Carregar extensions (cogs)
    await load_extensions()
    
    logger.info("Sistema inicializado com sucesso!")

async def load_extensions():
    """Carrega todas as extensions (cogs)"""
    extensions = [
        'cogs.admin',
        'cogs.assinaturas',
        'cogs.tasks'
    ]
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            logging.info(f"Extension carregada: {extension}")
        except Exception as e:
            logging.error(f"Erro ao carregar {extension}: {e}")

@bot.event
async def on_member_join(member):
    """Evento quando um membro entra no servidor"""
    logger = logging.getLogger(__name__)
    
    try:
        import asyncio
        await asyncio.sleep(3)
        dm_channel = await member.create_dm()
        await dm_channel.send(
            f"👋 Olá {member.name}, bem-vindo ao nosso servidor! 🎉\n\n"
            "Escolha uma opção no menu abaixo:",
            view=PlanoSelect()
        )
        logger.info(f"Membro {member.name} entrou e recebeu mensagem de boas-vindas.")
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem para {member.name}: {e}")

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """Evento quando um membro é atualizado"""
    logger = logging.getLogger(__name__)
    from database import atualizar_status_assinatura
    
    cargo = discord.utils.get(after.guild.roles, name=CARGO_ASSINANTE_NOME)
    if cargo in before.roles and cargo not in after.roles:
        try:
            await after.edit(nick=None)
        except discord.Forbidden:
            logger.error(f"Não foi possível resetar o apelido de {after}")
        
        # Atualizar status no banco
        atualizar_status_assinatura(after.id, "REMOVIDA", "Cargo removido manualmente")
        logger.info(f"O cargo de {after} foi removido manualmente; apelido resetado.")

if __name__ == "__main__":
    logger = setup_logging()
    bot.run(TOKEN)