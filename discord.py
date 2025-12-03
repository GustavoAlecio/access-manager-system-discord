import os
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import datetime
from datetime import timedelta
import asyncio
import re
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração de logging para produção com rotação de arquivos
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("bot.log", maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%d/%m/%Y %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)

# Variáveis de ambiente
TOKEN = os.getenv("DISCORD_TOKEN")
SERVER_ID = int(os.getenv("SERVER_ID"))
SUPORTE_CHANNEL_ID = int(os.getenv("SUPORTE_CHANNEL_ID"))
APOSTAS_CHANNEL_ID = int(os.getenv("APOSTAS_CHANNEL_ID"))
NOTIFICACAO_CHANNEL_ID = int(os.getenv("NOTIFICACAO_CHANNEL_ID"))
BOAS_VINDAS_CHANNEL_ID = int(os.getenv("BOAS_VINDAS_CHANNEL_ID"))
CARGO_ASSINANTE_NOME = "ASSINANTE"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dicionário para armazenar informações de assinaturas
assinaturas_ativas = {}

@bot.event
async def on_member_join(member):
    try:
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

# MENU DE SELEÇÃO PARA PLANOS
class PlanoSelect(discord.ui.View):
    def __init__(self, timeout=172800):  # 48 horas
        super().__init__(timeout=timeout)
        self.add_item(PlanoDropdown())

class PlanoDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Comprar Plano", description="Planos de 30 ou 90 dias", emoji="🟢"),
            discord.SelectOption(label="Suporte", description="Entre em contato com nosso suporte via Telegram", emoji="☎")
        ]
        super().__init__(placeholder="Escolha uma opção...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_option = self.values[0]
        if selected_option == "Comprar Plano":
            view = PlanoView("https://gustavotipster.vip/compreagora")
            suporte_view = PlanoView("https://t.me/suportegstv")
            await asyncio.sleep(3)
            await interaction.followup.send(
                content=(
                    "* 🔴 Passos para acessar o nosso servidor |SUPER IMPORTANTE| 🔴*\n"
                    "1️⃣ Acesse o site no botão abaixo.\n"
                    "2️⃣ Escolha o plano que melhor atende às suas necessidades.\n"
                    "3️⃣ Finalize o pagamento.\n"
                    "4️⃣ Envie o comprovante  **e o seu nick do discord** para o suporte no Telegram para ativação.\n\n"
                    "Clique no botão abaixo para comprar seu plano:"
                ),
                view=view,
                ephemeral=True
            )
            await asyncio.sleep(3)
            await interaction.followup.send(
                content="📞 Suporte no Telegram: Caso precise enviar comprovante ou tirar dúvidas, clique no botão abaixo:",
                view=suporte_view,
                ephemeral=True
            )
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await asyncio.sleep(3)
                await canal.send(
                    f"📢 Aviso: O usuário {interaction.user.mention} está tentando adquirir um plano.\n"
                    "O pagamento foi confirmado?",
                    view=ConfirmarPagamentoView(interaction.user)
                )
        elif selected_option == "Suporte":
            await asyncio.sleep(3)
            await interaction.followup.send(
                "📞 Precisa de ajuda? Entre em contato com o suporte pelo Telegram:",
                view=PlanoView("https://t.me/suportegstv"),
                ephemeral=True
            )

class PlanoView(discord.ui.View):
    def __init__(self, url, timeout=172800):
        super().__init__(timeout=timeout)
        button = discord.ui.Button(label="Acessar", url=url, style=discord.ButtonStyle.link)
        self.add_item(button)

# CONFIRMAÇÃO DE PAGAMENTO
class ConfirmarPagamentoView(discord.ui.View):
    def __init__(self, user, timeout=172800):
        super().__init__(timeout=timeout)
        self.user = user
        self.add_item(ConfirmarPagamentoButton(user, dias=30, label="Plano 30 dias"))
        self.add_item(ConfirmarPagamentoButton(user, dias=90, label="Plano 90 dias"))

class ConfirmarPagamentoButton(discord.ui.Button):
    def __init__(self, user, dias: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.success)
        self.user = user
        self.dias = dias

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("Você não tem permissões para confirmar pagamentos", ephemeral=True)
            return
        await interaction.response.send_message(f"Pagamento do usuário {self.user.mention} confirmado!", ephemeral=True)
        guild = interaction.guild
        if guild is None:
            return
        msg = await liberar_usuario(guild, self.user, dias=self.dias)
        await interaction.followup.send(msg, ephemeral=True)
        try:
            await asyncio.sleep(3)
            dm_channel = await self.user.create_dm()
            await dm_channel.send(
                f"🎉 Olá {self.user.name}, seu pagamento foi confirmado! Seja bem-vindo ao servidor! 🚀"
            )
        except Exception as e:
            logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")

@bot.command()
async def confirmar(ctx, user: discord.User):
    view = ConfirmarPagamentoView(user)
    await ctx.send(f"Selecione o plano para liberar {user.mention}:", view=view)

# FUNÇÃO DE LIBERAÇÃO DO USUÁRIO (atualiza o nick com a data de expiração)
async def liberar_usuario(guild: discord.Guild, user: discord.User, dias: int) -> str:
    data_expiracao = datetime.datetime.now() + timedelta(days=dias)
    data_formatada = data_expiracao.strftime("%d/%m/%Y")
    if dias == 30:
        nome_plano = "Plano 30 dias"
    elif dias == 90:
        nome_plano = "Plano 90 dias"
    else:
        nome_plano = "ASSINANTE"
    member = guild.get_member(user.id)
    if member is None:
        return "⚠ O usuário não está no servidor ou não foi encontrado."
    nickname_atual = member.display_name
    nickname_limpo = re.sub(r"\s*\|\s*\d{2}/\d{2}/\d{4}$", "", nickname_atual).strip()
    novo_apelido = f"{nickname_limpo} | {data_formatada}"
    try:
        await member.edit(nick=novo_apelido)
        logger.info(f"Nickname de {member.name} atualizado para {novo_apelido}.")
    except discord.Forbidden:
        return "⚠ Não tenho permissão para mudar o apelido desse usuário."
    except Exception as e:
        return f"⚠ Erro ao editar apelido: {e}"
    cargo_assinante = discord.utils.get(guild.roles, name=CARGO_ASSINANTE_NOME)
    if cargo_assinante is None:
        cargo_assinante = await guild.create_role(
            name=CARGO_ASSINANTE_NOME,
            color=discord.Color.green(),
            reason="Criando cargo para assinantes."
        )
        logger.info(f"Criado cargo '{CARGO_ASSINANTE_NOME}' no servidor.")
    await member.add_roles(cargo_assinante, reason=f"Usuário liberado ({nome_plano})")
    canal_assinantes = guild.get_channel(APOSTAS_CHANNEL_ID)
    await canal_assinantes.set_permissions(cargo_assinante, view_channel=True, send_messages=True)
    
    assinaturas_ativas[member.id] = {
        "data_exp": data_expiracao,
        "avisado": False,
        "last_warning": datetime.datetime.now(),
        "plano": nome_plano
    }
    return f"✅ {member.mention} foi liberado no *{nome_plano}! Expira em *{data_formatada}."

@bot.command()
@commands.has_permissions(administrator=True)
async def liberar30(ctx, member: discord.Member):
    msg = await liberar_usuario(ctx.guild, member, dias=30)
    await ctx.send(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def liberar90(ctx, member: discord.Member):
    msg = await liberar_usuario(ctx.guild, member, dias=90)
    await ctx.send(msg)

# Função auxiliar para atualizar o nickname durante a renovação
async def atualizar_nickname(member: discord.Member, dias: int) -> None:
    try:
        nova_data = datetime.datetime.now() + timedelta(days=dias)
        novo_nick = re.sub(r"\s*\|\s*\d{2}/\d{2}/\d{4}$", "", member.display_name).strip() + " | " + nova_data.strftime("%d/%m/%Y")
        await member.edit(nick=novo_nick)
        logger.info(f"Nickname de {member.name} atualizado para {novo_nick}.")
    except discord.Forbidden:
        logger.error(f"Permissão negada para atualizar o nickname de {member.name}.")
    except Exception as e:
        logger.error(f"Erro ao atualizar o nickname de {member.name}: {e}")

# RENOVAÇÃO DE ASSINATURA
class RenovarAssinaturaView(discord.ui.View):
    def __init__(self, user, timeout=172800):
        super().__init__(timeout=timeout)
        self.user = user
        # Botão definido via decorator, evitando duplicação.
    
    @discord.ui.button(label="Renovar Plano", style=discord.ButtonStyle.green)
    async def renovar_plano(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Para renovar sua assinatura, acesse o link abaixo:\n"
            "🔗 [Renovar Assinatura](https://gustavotipster.vip/compreagora)\n"
            "🔴 [**Após o pagamento, envie o comprovante e seu nick do discord para o suporte:** ](https://t.me/suportegstv)",
            ephemeral=True
        )
        canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
        if canal:
            await canal.send(
                f"📝 O usuário {self.user.mention} iniciou o processo de renovação. Aguardando confirmação de pagamento.",
                view=SuporteRenovacaoView(self.user)
            )

class RenovarAssinaturaButton(discord.ui.Button):
    def __init__(self, user):
        super().__init__(label="Renovar Plano", style=discord.ButtonStyle.green)
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Para renovar sua assinatura, acesse o link abaixo:\n"
            "🔗 [Renovar Assinatura](https://gustavotipster.vip/compreagora)\n"
            "🔴 [**Após o pagamento, envie o comprovante e seu nick do discord para o suporte:** ](https://t.me/suportegstv)",
            ephemeral=True
        )
        canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
        if canal:
            await canal.send(
                f"📝 O usuário {self.user.mention} iniciou o processo de renovação. Aguardando confirmação de pagamento.",
                view=SuporteRenovacaoView(self.user)
            )

class SuporteRenovacaoView(discord.ui.View):
    def __init__(self, user, timeout=172800):
        super().__init__(timeout=timeout)
        self.user = user

    @discord.ui.button(label="Liberar Plano (30 dias)", style=discord.ButtonStyle.primary)
    async def liberar_plano(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            cargo = discord.utils.get(interaction.guild.roles, name=CARGO_ASSINANTE_NOME)
            if cargo and cargo not in self.user.roles:
                await self.user.add_roles(cargo, reason="Plano de 30 dias renovado pelo suporte.")
            member = interaction.guild.get_member(self.user.id)
            if member:
                await atualizar_nickname(member, 30)
            await interaction.response.send_message(
                f"✅ Plano de 30 dias ativado para {self.user.mention}.", ephemeral=True
            )
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano de 30 dias ativado para {self.user.mention}.")
            try:
                dm_channel = await self.user.create_dm()
                await dm_channel.send("✅ Seu plano de 30 dias foi renovado! 🎉")
            except Exception as e:
                logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")
        except discord.errors.NotFound:
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano de 30 dias ativado para {self.user.mention}.")
            logger.warning("Interação expirada. Mensagem enviada diretamente no canal.")
        except Exception as e:
            logger.error(f"Erro ao liberar plano de 30 dias: {e}")

    @discord.ui.button(label="Liberar Plano (90 dias)", style=discord.ButtonStyle.success)
    async def liberar_plano_y(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            cargo = discord.utils.get(interaction.guild.roles, name=CARGO_ASSINANTE_NOME)
            if cargo and cargo not in self.user.roles:
                await self.user.add_roles(cargo, reason="Plano de 90 dias renovado pelo suporte.")
            member = interaction.guild.get_member(self.user.id)
            if member:
                await atualizar_nickname(member, 90)
            await interaction.response.send_message(
                f"✅ Plano de 90 dias ativado para {self.user.mention}.", ephemeral=True
            )
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano de 90 dias ativado para {self.user.mention}.")
            try:
                dm_channel = await self.user.create_dm()
                await dm_channel.send("✅ Seu plano de 90 dias foi renovado! 🎉")
            except Exception as e:
                logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")
        except discord.errors.NotFound:
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano de 90 dias ativado para {self.user.mention}.")
            logger.warning("Interação expirada. Mensagem enviada diretamente no canal.")
        except Exception as e:
            logger.error(f"Erro ao liberar plano de 90 dias: {e}")

class RenovarAssinatura(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="renovar")
    async def renovar(self, ctx):
        await ctx.send(
            "🔄 Escolha um plano para renovar sua assinatura:",
            view=RenovarAssinaturaView(ctx.author)
        )

# CHECAGEM DE ASSINATURAS (UMA ÚNICA DEFINIÇÃO)
class ChecagemAssinaturas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Inicializando checagem de assinaturas...")
        self.checar_assinaturas.start()

    def cog_unload(self):
        logger.info("Cancelando checagem de assinaturas...")
        self.checar_assinaturas.cancel()

    @tasks.loop(hours=12)  # Intervalo de 12 horas
    async def checar_assinaturas(self):
        await self.bot.wait_until_ready()
        logger.info("Iniciando checagem de assinaturas...")
        guild = self.bot.get_guild(SERVER_ID)
        if not guild:
            logger.error("Servidor não encontrado!")
            return

        hoje = datetime.datetime.now().date()
        logger.debug(f"Data de hoje: {hoje}")
        cargo = discord.utils.get(guild.roles, name="ASSINANTE")
        if not cargo:
            logger.error("Cargo 'Assinante' não encontrado!")
            return


        for member in guild.members:
            if not member.nick or " | " not in member.nick:
                continue # se não tem " | " ignora e continua

            partes = member.nick.split("|")
            if len(partes) < 2:
                logger.warning(f"Formato de nick inesperado para {member.nick}")
                continue

            data_str = partes[1].strip()
            if not re.match(r"\d{2}/\d{2}/\d{4}$", data_str):
                continue # se a data não segue o formato correto, ignora
            
            logger.debug(f"Extraindo data do nick de {member.name}: {data_str}")
            try:
                data_expiracao = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError as e:
                logger.error(f"Erro ao converter data para {member.nick}: {e}")
                continue

            logger.debug(f"Data de expiração para {member.name}: {data_expiracao}")

            if data_expiracao == hoje:
                info = assinaturas_ativas.get(member.id)
                send_warning = False
                if info is None or "last_warning" not in info:
                    send_warning = True
                else:
                    last_warning = info["last_warning"]
                    if (datetime.datetime.now() - last_warning).total_seconds() >= 43200:
                        send_warning = True

                if send_warning:
                    try:
                        await asyncio.sleep(3)
                        dm_channel = await member.create_dm()
                        await dm_channel.send(
                            f"🔔 Olá {member.name}, sua assinatura expira hoje!\n"
                            "Renove seu plano clicando no botão abaixo:",
                            view=RenovarAssinaturaView(member)
                        )
                        logger.info(f"Enviado aviso para {member.name} sobre expiração.")
                        current_info = assinaturas_ativas.get(member.id, {})
                        current_info["last_warning"] = datetime.datetime.now()
                        assinaturas_ativas[member.id] = current_info
                    except Exception as e:
                        logger.error(f"Erro ao enviar DM para {member.name}: {e}")
            elif data_expiracao < hoje:
                try:
                    await member.remove_roles(cargo, reason="Assinatura expirada e não renovada.")
                    logger.info(f"Cargo de assinante removido para: {member.name}")
                    await asyncio.sleep(3)
                    dm_channel = await member.create_dm()
                    await dm_channel.send(
                        f"🚨 Olá {member.name}, sua assinatura expirou!\n"
                        "Renove seu plano clicando no botão abaixo:",
                        view=RenovarAssinaturaView(member)
                    )
                except discord.Forbidden:
                    logger.error(f"Sem permissão para remover o cargo de {member.name}.")
                except Exception as e:
                    logger.error(f"Erro ao processar {member.name}: {e}")

    @checar_assinaturas.before_loop
    async def before_checar_assinaturas(self):
        logger.info("Aguardando o bot ficar pronto antes de começar a checagem...")
        await self.bot.wait_until_ready()

# EVENTOS ADICIONAIS
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    cargo = discord.utils.get(after.guild.roles, name=CARGO_ASSINANTE_NOME)
    if cargo in before.roles and cargo not in after.roles:
        try:
            await after.edit(nick=None)
        except discord.Forbidden:
            logger.error(f"Não foi possível resetar o apelido de {after}")
        if after.id in assinaturas_ativas:
            del assinaturas_ativas[after.id]
        logger.info(f"O cargo de {after} foi removido manualmente; apelido resetado e removido do dicionário.")

# EVENTO on_ready – adição dos cogs
@bot.event
async def on_ready():
    logger.info(f"Bot conectado como {bot.user}")
    await bot.add_cog(ChecagemAssinaturas(bot))
    await bot.add_cog(RenovarAssinatura(bot))
    logger.info("Cogs carregadas com sucesso!")

bot.run(TOKEN)
