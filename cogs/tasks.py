# cogs/tasks.py
import discord
from discord.ext import commands, tasks
import datetime
import re
import asyncio
import logging
from config import *
from database import *
from views import RenovarAssinaturaView

logger = logging.getLogger(__name__)

class ChecagemAssinaturas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("Inicializando checagem de assinaturas...")
        self.checar_assinaturas.start()

    def cog_unload(self):
        logger.info("Cancelando checagem de assinaturas...")
        self.checar_assinaturas.cancel()
        
    async def _rodar_checar_assinaturas_uma_vez(self):
        """
        Versão 'unit test' da checagem:
        mesma lógica do loop, mas sem o decorator @tasks.loop
        e sem wait_until_ready. Usada nos testes.
        """
        logger.info("Iniciando checagem de assinaturas (uma vez)...")
        guild = self.bot.get_guild(SERVER_ID)
        if not guild:
            logger.error("Servidor não encontrado!")
            return
        
        resumo = {
            "processados": 0,
            "avisos_3": 0,
            "avisos_hoje": 0,
            "removidos": 0,
            "erros_dm": 0,
            "erros_permissao": 0,
        }
        
        canal_notificacao = guild.get_channel(NOTIFICACAO_CHANNEL_ID)

        hoje = datetime.datetime.now().date()
        logger.debug(f"Data de hoje: {hoje}")
        cargo = discord.utils.get(guild.roles, name=CARGO_ASSINANTE_NOME)
        if not cargo:
            logger.error(f"Cargo '{CARGO_ASSINANTE_NOME}' não encontrado!")
            return

        for member in guild.members:
            if not member.nick or " | " not in member.nick:
                continue

            partes = member.nick.split("|")
            if len(partes) < 2:
                logger.warning(f"Formato de nick inesperado para {member.nick}")
                continue

            data_str = partes[1].strip()
            if not re.match(r"\d{2}/\d{2}/\d{4}$", data_str):
                continue

            logger.debug(f"Extraindo data do nick de {member.name}: {data_str}")
            try:
                data_expiracao = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError as e:
                logger.error(f"Erro ao converter data para {member.nick}: {e}")
                continue

            logger.debug(f"Data de expiração para {member.name}: {data_expiracao}")
            
            resumo["processados"] += 1

            dias_restantes = (data_expiracao - hoje).days
            assinatura_db = obter_assinatura(member.id)
            
            if not assinatura_db:
                data_exp_datetime = datetime.datetime.combine(data_expiracao, datetime.time(0,0))
                adicionar_assinatura(
                    user_id=member.id,
                    username=member.name,
                    data_expiracao = data_exp_datetime,
                    plano="Imprtado (nickname)"
                )
                assinatura_db = obter_assinatura(member.id)
            ultimo_aviso = None
            if assinatura_db and assinatura_db['ultimo_aviso']:
                raw_aviso = assinatura_db['ultimo_aviso']
                for fmt in (DB_DATETIME_FORMAT, LEGACY_DATETIME_FORMAT):
                    try:
                        ultimo_aviso = datetime.datetime.strptime(raw_aviso, fmt)
                        break
                    except ValueError:
                        continue

            # --- a partir daqui é o mesmo código que você já tem ---
            if dias_restantes > 0:
                if dias_restantes == 3:
                    enviar_aviso = True

                    if ultimo_aviso:
                        horas_desde_ultimo = (datetime.datetime.now() - ultimo_aviso).total_seconds() / 3600
                        if horas_desde_ultimo < 12:
                            enviar_aviso = False

                    if enviar_aviso:
                        try:
                            dm_channel = await member.create_dm()
                            
                            mensagem = (
                                    f"🔔 Olá {member.name}, sua assinatura expira em **3 dias**!\n"
                                    "Renove seu plano clicando no botão abaixo:"
                                )
                            registrar_aviso(member.id, "AVISO_3_DIAS")
                            resumo["avisos_3"] += 1

                            await dm_channel.send(mensagem, view=RenovarAssinaturaView(member))
                            logger.info(f"Enviado aviso para {member.name} ({dias_restantes} dias restantes)")
                        except Exception as e:
                            resumo["erros_dm"] += 1
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
                        resumo["avisos_hoje"] += 1
                        logger.info(f"Aviso final enviado para {member.name}")
                    except Exception as e:
                        resumo["erros_dm"] += 1
                        logger.error(f"Erro ao enviar DM final para {member.name}: {e}")

            elif dias_restantes < 0:
                dias_atras = abs(dias_restantes)
                if member == guild.owner:
                    logger.warning(f"Tentativa de remover o dono do servidor ({member}). Ignorando.")
                    continue
                try:
                    try:
                        dm_channel = await member.create_dm()
                        if dias_restantes == 1:
                            texto_qtd = "há **1 dia**"
                        else:
                            texto_qtd = f"há **{dias_atras} dias**"
                            
                        await dm_channel.send(
                            f"🚨 **SUA ASSINATURA EXPIROU** {member.name}!\n"
                            f"Sua assinatura está vencida {texto_qtd} e você será removido do servidor.\n"
                            "Para retornar, renove seu plano clicando no botão abaixo:",
                            view=RenovarAssinaturaView(member)
                        )
                    except Exception:
                        logger.warning(f"Não foi possível enviar DM para {member.name} antes da remoção")

                    await member.remove_roles(cargo, reason="Assinatura expirada há 1 dia")
                    await member.kick(reason="Assinatura expirada - Não renovada")

                    atualizar_status_assinatura(
                        member.id, 
                        "EXPIRADA",
                        f"Removido do servidor com {dias_atras} dias de atraso após a expiração"
)
                    resumo["removidos"] += 1
                    logger.info(f"Usuário {member.name} removido do servidor (assinatura expirada há 1 dia)")
                    
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
                    resumo["erros_permissao"] += 1
                    logger.error(f"Sem permissão para remover/kick {member.name}.")
                except Exception as e:
                    logger.error(f"Erro ao processar remoção de {member.name}: {e}")

        if canal_notificacao:
            try:
                msg_resumo = (
                    "📋 **RESUMO DA CHECAGEM DE ASSINATURAS**\n"
                    f"👥 Membros com assinatura processados: **{resumo['processados']}**\n"
                    f"🔔 Avisos enviados: "
                    f"3d: **{resumo['avisos_3']}**, "
                    f"hoje: **{resumo['avisos_hoje']}**\n"
                    f"🚫 Removidos por expiração (1 dia após vencer): **{resumo['removidos']}**\n"
                    f"⚠️ Falhas de DM: **{resumo['erros_dm']}** | "
                    f"Falhas de permissão (kick/remover cargo): **{resumo['erros_permissao']}**"
                )
                await canal_notificacao.send(msg_resumo)
            except Exception as e:
                logger.error(f"Erro ao enviar resumo da checagem no canal de notificações: {e}")

        logger.info("Checagem de assinaturas concluída.")
        
    @tasks.loop(hours=INTERVALO_CHECAGEM)
    async def checar_assinaturas(self):
        await self.bot.wait_until_ready()
        await self._rodar_checar_assinaturas_uma_vez()

async def setup(bot):
    await bot.add_cog(ChecagemAssinaturas(bot))