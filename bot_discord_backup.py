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
import sqlite3

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
CARGO_ASSINANTE_NOME = "ASSINANTE"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ============================ INICIALIZAÇÃO DO BANCO DE DADOS ==================

def init_db():
    """Inicializa o banco de dados SQLite"""
    try: 
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
    
        # Tabela principal de assinaturas (CORRIGIDA)
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
        
        # Tabela de histórico (ADICIONAR)
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
    except Exception as e:
        logger.error(f"Erro ao inicializar Banco de dados: {e}")

# ============================ FUNÇÕES DE BANCO DE DADOS ==================
def adicionar_assinatura(user_id: int, username: str, data_expiracao: datetime, plano: str):
    """Adiciona ou atualiza uma assinatura no banco de dados"""
    try:
        conn = sqlite3.connect('assinaturas.db')
        cursor = conn.cursor()
        
        data_exp_str = data_expiracao.strftime("%d/%m/%Y %H:%M:%S")
        data_ativacao = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
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
        
        data_aviso = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
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
        
        # Assinaturas pendentes (a expirar em até 7 dias)
        hoje = datetime.datetime.now().date()
        limite = (hoje + timedelta(days=7)).strftime("%d/%m/%Y")
        
        cursor.execute('''
            SELECT * FROM assinaturas 
            WHERE status = "ATIVA" 
            AND substr(data_expiracao, 1, 10) <= ?
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
    
# ==================== EVENTOS DO BOT ====================
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

# ==================== MENU DE SELEÇÃO PARA PLANOS ====================
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
            view = PlanoView("https://gustavocorrea.com.br/")
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

# ==================== CONFIRMAÇÃO DE PAGAMENTO ====================
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

# ==================== FUNÇÃO DE LIBERAÇÃO DO USUÁRIO ====================
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
    
    adicionar_assinatura(member.id, member.name, data_expiracao, nome_plano)
    
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

# ==================== FUNÇÃO AUXILIAR PARA ATUALIZAR NICKNAME ====================
async def atualizar_nickname(member: discord.Member, dias: int) -> None:
    try:
        nova_data = datetime.datetime.now() + timedelta(days=dias)
        novo_nick = re.sub(r"\s*\|\s*\d{2}/\d{2}/\d{4}$", "", member.display_name).strip() + " | " + nova_data.strftime("%d/%m/%Y")
        await member.edit(nick=novo_nick)
        
        logger.info(f"Nickname de {member.name} atualizado para {novo_nick}.")
        
        adicionar_assinatura(member.id, member.name, nova_data, f"Renovado {dias} dias")
    except discord.Forbidden:
        logger.error(f"Permissão negada para atualizar o nickname de {member.name}.")
    except Exception as e:
        logger.error(f"Erro ao atualizar o nickname de {member.name}: {e}")

# ==================== RENOVAÇÃO DE ASSINATURA ====================
class RenovarAssinaturaView(discord.ui.View):
    def __init__(self, user, timeout=172800):
        super().__init__(timeout=timeout)
        self.user = user
    
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

# ==================== CHECAGEM DE ASSINATURAS ====================
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

            dias_restantes = (data_expiracao - hoje).days
            assinatura_db = obter_assinatura(member.id)
            ultimo_aviso = None
            if assinatura_db and assinatura_db['ultimo_aviso']:
                try:
                    ultimo_aviso = datetime.datetime.strptime(assinatura_db['ultimo_aviso'], "%d/%m/%Y %H:%M:%S")
                except:
                    pass
                
            if dias_restantes > 0:
                if dias_restantes in [5, 3, 1]:
                    enviar_aviso = True
                    if ultimo_aviso:
                        horas_desde_ultimo = (datetime.datetime.now() - ultimo_aviso).total_seconds() / 3600
                        if horas_desde_ultimo < 12:
                            enviar_aviso = True
                    if enviar_aviso:
                        try:
                            dm_channel = await member.create_dm()
                            if dias_restantes == 1:
                                mensagem = f"🔔 Olá {member.name}, sua assinatura expira **AMANHÃ**!\nRenove seu plano clicando no botão abaixo:"
                                registrar_aviso(member.id, "AVISO_1_DIA")
                            elif dias_restantes == 3:
                                mensagem = f"🔔 Olá {member.name}, sua assinatura expira em **3 dias**!\nRenove seu plano clicando no botão abaixo:"
                                registrar_aviso(member.id, "AVISO_3_DIAS")
                            else:
                                mensagem = f"🔔 Olá {member.name}, sua assinatura expira em **5 dias**!\nRenove seu plano clicando no botão abaixo:"
                                registrar_aviso(member.id, "AVISO_5_DIAS")

                            await dm_channel.send(mensagem, view= RenovarAssinaturaView(member))
                            
                            logger.info(f"Enviado aviso para {member.name} ({dias_restantes} dias restantes)")
                        except Exception as e:
                            logger.error(f"Erro ao enviar DM para {member.name}: {e}")

            elif dias_restantes == 0:
                if not ultimo_aviso or (datetime.datetime.now() - ultimo_aviso).total_seconds() >= 43200:
                    try:
                        dm_channel = await member.create_dm()
                        await dm_channel.send(
                            f"⚠️ **ATENÇÃO** {member.name}, sua assinatura **VENCE HOJE**!\n"
                            "Você será removido do servidor AMANHÃ caso não renove.\n"
                            "Renove imediatamente clicando no botão abaixo:",
                            view=RenovarAssinaturaView(member)
                        )
                        registrar_aviso(member.id, "AVISO_EXPIRA_HOJE")
                        logger.info(f"Aviso final enviado para {member.name}")
                    except Exception as e:
                        logger.error(f"Erro ao enviar DM final para {member.name}: {e}")
            elif dias_restantes == -1:
                # 1 dia APÓS a expiração - REMOVER USUÁRIO
                try:
                    # Primeiro tentar enviar DM
                    try:
                        dm_channel = await member.create_dm()
                        await dm_channel.send(
                            f"🚨 **SUA ASSINATURA EXPIROU** {member.name}!\n"
                            "Você está sendo removido do servidor por falta de renovação.\n"
                            "Para retornar, renove seu plano clicando no botão abaixo:",
                            view=RenovarAssinaturaView(member)
                        )
                    except:
                        logger.warning(f"Não foi possível enviar DM para {member.name} antes da remoção")
                    
                    # Remover cargo e kick
                    await member.remove_roles(cargo, reason="Assinatura expirada há 1 dia")
                    await member.kick(reason="Assinatura expirada - Não renovada")
                    
                    # Atualizar status no banco
                    atualizar_status_assinatura(member.id, "EXPIRADA", "Removido do servidor após 1 dia sem renovação")
                    
                    logger.info(f"Usuário {member.name} removido do servidor (assinatura expirada há 1 dia)")
                    
                    # Notificar no canal de notificações
                    canal_notificacao = guild.get_channel(NOTIFICACAO_CHANNEL_ID)
                    if canal_notificacao:
                        await canal_notificacao.send(
                            f"📋 **RELATÓRIO DE EXPIRAÇÃO**\n"
                            f"👤 Usuário: {member.mention} ({member.name})\n"
                            f"📅 Data de expiração: {data_str}\n"
                            f"🚫 Status: REMOVIDO DO SERVIDOR\n"
                            f"⏰ Motivo: Assinatura não renovada após 1 dia da expiração"
                        )
                        
                except discord.Forbidden:
                    logger.error(f"Sem permissão para remover/kick {member.name}.")
                except Exception as e:
                    logger.error(f"Erro ao processar remoção de {member.name}: {e}")

    @checar_assinaturas.before_loop
    async def before_checar_assinaturas(self):
        logger.info("Aguardando o bot ficar pronto antes de começar a checagem...")
        await self.bot.wait_until_ready()
        
# ==================== COMANDO PARA VER ASSINATURAS ====================
@bot.command(name="assinaturas")
@commands.has_permissions(administrator=True)
async def ver_assinaturas(ctx):
    """Mostra um resumo completo das assinaturas"""
    try:
        # Obter resumo do banco de dados
        resumo = obter_resumo_assinaturas()
        
        if not resumo:
            await ctx.send("❌ Erro ao obter informações das assinaturas.")
            return
        
        # Criar embed principal
        embed = discord.Embed(
            title="📊 RELATÓRIO COMPLETO DE ASSINATURAS",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Estatísticas gerais
        embed.add_field(
            name="📈 ESTATÍSTICAS GERAIS",
            value=(
                f"✅ **Ativas:** {resumo['total_ativas']}\n"
                f"⚠️ **A vencer (7 dias):** {resumo['total_pendentes']}\n"
                f"❌ **Expiradas:** {resumo['total_expiradas']}\n"
                f"📊 **Total:** {resumo['total_ativas'] + resumo['total_expiradas']}"
            ),
            inline=False
        )
        
        # Assinaturas ativas (primeiras 10)
        if resumo['ativas']:
            ativas_text = ""
            for i, assinatura in enumerate(resumo['ativas'][:10], 1):
                user_id = assinatura[0]
                username = assinatura[1]
                data_exp = assinatura[2][:10]  # Pegar apenas a data
                plano = assinatura[3]
                
                # Calcular dias restantes
                try:
                    data_expiracao = datetime.datetime.strptime(data_exp, "%d/%m/%Y").date()
                    hoje = datetime.datetime.now().date()
                    dias_restantes = (data_expiracao - hoje).days
                    
                    if dias_restantes > 0:
                        emoji = "🟢" if dias_restantes > 7 else "🟡"
                        status = f"{dias_restantes} dias"
                    else:
                        emoji = "🔴"
                        status = "VENCIDA"
                except:
                    emoji = "⚪"
                    status = "??"
                
                ativas_text += f"{emoji} `{username[:20]:20}` | {data_exp} | {plano} | {status}\n"
            
            if len(resumo['ativas']) > 10:
                ativas_text += f"\n... e mais {len(resumo['ativas']) - 10} assinaturas ativas"
            
            embed.add_field(
                name=f"✅ ASSINATURAS ATIVAS ({len(resumo['ativas'])})",
                value=ativas_text or "Nenhuma assinatura ativa",
                inline=False
            )
        
        # Assinaturas a vencer (próximos 7 dias)
        if resumo['pendentes']:
            pendentes_text = ""
            for assinatura in resumo['pendentes'][:5]:
                username = assinatura[1]
                data_exp = assinatura[2][:10]
                plano = assinatura[3]
                
                try:
                    data_expiracao = datetime.datetime.strptime(data_exp, "%d/%m/%Y").date()
                    hoje = datetime.datetime.now().date()
                    dias_restantes = (data_expiracao - hoje).days
                    
                    if dias_restantes == 0:
                        status = "HOJE ⚠️"
                    elif dias_restantes == 1:
                        status = "AMANHÃ ⚠️"
                    else:
                        status = f"em {dias_restantes} dias"
                except:
                    status = "??"
                    
                pendentes_text += f"🔴 `{username[:20]:20}` | {data_exp} | {plano} | Vence {status}\n"
            
            embed.add_field(
                name=f"⚠️ PRÓXIMAS A VENCER ({len(resumo['pendentes'])})",
                value=pendentes_text,
                inline=False
            )
        # Assinaturas expiradas (últimas 5)
        if resumo['expiradas']:
            expiradas_text = ""
            for assinatura in resumo['expiradas'][:5]:
                username = assinatura[1]
                data_exp = assinatura[2][:10]
                plano = assinatura[3]
                expiradas_text += f"❌ `{username[:20]:20}` | {data_exp} | {plano}\n"
            
            embed.add_field(
                name=f"❌ EXPIRADAS RECENTES ({len(resumo['expiradas'])})",
                value=expiradas_text,
                inline=False
            )
        
        icon_url = ctx.author.avatar.url if ctx.author.avatar else None
        embed.set_footer(text=f"Solicitado por {ctx.author.name}", icon_url=icon_url)
        
        # Enviar embed
        await ctx.send(embed=embed)
        
        # Se houver muitas assinaturas, enviar arquivo detalhado
        if resumo['ativas'] or resumo['expiradas']:
            with open('relatorio_assinaturas.txt', 'w', encoding='utf-8') as f:
                f.write("RELATÓRIO COMPLETO DE ASSINATURAS\n")
                f.write("=" * 50 + "\n\n")
                
                f.write("ASSINATURAS ATIVAS:\n")
                f.write("-" * 50 + "\n")
                for assinatura in resumo['ativas']:
                    f.write(f"ID: {assinatura[0]} | Usuário: {assinatura[1]} | Expira: {assinatura[2]} | Plano: {assinatura[3]}\n")
                
                f.write("\nASSINATURAS EXPIRADAS:\n")
                f.write("-" * 50 + "\n")
                for assinatura in resumo['expiradas']:
                    f.write(f"ID: {assinatura[0]} | Usuário: {assinatura[1]} | Expirou: {assinatura[2]} | Plano: {assinatura[3]}\n")
            
            await ctx.send(file=discord.File('relatorio_assinaturas.txt'))
            
    except Exception as e:
        logger.error(f"Erro no comando assinaturas: {e}")
        await ctx.send("❌ Ocorreu um erro ao gerar o relatório de assinaturas.")
        
# ==================== COMANDO PARA VER ASSINATURA ESPECÍFICA ====================
@bot.command(name="minhaassinatura")
async def minha_assinatura(ctx):
    """Mostra informações da assinatura do usuário"""
    assinatura = obter_assinatura(ctx.author.id)
    
    if not assinatura:
        await ctx.send("❌ Você não possui uma assinatura ativa.")
        return
    
    embed = discord.Embed(
        title=f"📋 SUA ASSINATURA - {ctx.author.name}",
        color=discord.Color.green()
    )
    
    embed.add_field(name="👤 Usuário", value=ctx.author.mention, inline=True)
    embed.add_field(name="📅 Data de Ativação", value=assinatura['data_ativacao'][:10], inline=True)
    embed.add_field(name="📊 Plano", value=assinatura['plano'], inline=True)
    embed.add_field(name="⏰ Expira em", value=assinatura['data_expiracao'][:10], inline=True)
    embed.add_field(name="✅ Status", value=assinatura['status'], inline=True)
    
    # Calcular dias restantes
    try:
        data_exp = datetime.datetime.strptime(assinatura['data_expiracao'][:10], "%d/%m/%Y").date()
        hoje = datetime.datetime.now().date()
        dias_restantes = (data_exp - hoje).days
        
        if dias_restantes > 0:
            if dias_restantes > 30:
                cor = "🟢"
                status = "OK"
            elif dias_restantes > 7:
                cor = "🟡"
                status = "ATENÇÃO"
            else:
                cor = "🔴"
                status = "URGENTE"
            
            embed.add_field(
                name="⏳ Status da Renovação",
                value=f"{cor} **{dias_restantes} dias restantes**\n{status}",
                inline=False
            )
        else:
            embed.add_field(
                name="⚠️ STATUS CRÍTICO",
                value="🔴 **ASSINATURA EXPIRADA**\nRenove IMEDIATAMENTE!",
                inline=False
            )
            embed.color = discord.Color.red()
    except:
        pass
    
    embed.set_footer(text="Use !renovar para renovar sua assinatura")
    
    await ctx.send(embed=embed)
    


# ==================== EVENTOS ADICIONAIS ====================
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    cargo = discord.utils.get(after.guild.roles, name=CARGO_ASSINANTE_NOME)
    if cargo in before.roles and cargo not in after.roles:
        try:
            await after.edit(nick=None)
        except discord.Forbidden:
            logger.error(f"Não foi possível resetar o apelido de {after}")
        
        # Atualizar status no banco
        atualizar_status_assinatura(after.id, "REMOVIDA", "Cargo removido manualmente")
        logger.info(f"O cargo de {after} foi removido manualmente; apelido resetado.")

# ==================== EVENTO on_ready ====================
@bot.event
async def on_ready():
    logger.info(f"Bot conectado como {bot.user}")
    
    # Inicializar banco de dados
    init_db()
    
    # Carregar cogs
    await bot.add_cog(ChecagemAssinaturas(bot))
    await bot.add_cog(RenovarAssinatura(bot))
    logger.info("Sistema inicializado com sucesso!")

# ==================== INICIAR BOT ====================
if __name__ == "__main__":
    bot.run(TOKEN)
