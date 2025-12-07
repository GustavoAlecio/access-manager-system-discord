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

    @tasks.loop(hours=INTERVALO_CHECAGEM)
    async def checar_assinaturas(self):
        await self.bot.wait_until_ready()
        logger.info("Iniciando checagem de assinaturas...")
        
        guild = self.bot.get_guild(SERVER_ID)
        if not guild:
            logger.error("Servidor não encontrado!")
            return

        hoje = datetime.datetime.now().date()
        logger.debug(f"Data de hoje: {hoje}")
        
        cargo = discord.utils.get(guild.roles, name=CARGO_ASSINANTE_NOME)
        if not cargo:
            logger.error("Cargo 'Assinante' não encontrado!")
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
            
            try:
                data_expiracao = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError as e:
                logger.error(f"Erro ao converter data para {member.nick}: {e}")
                continue

            logger.debug(f"Data de expiração para {member.name}: {data_expiracao}")

            dias_restantes = (data_expiracao - hoje).days
            assinatura_db = obter_assinatura(member.id)
            ultimo_aviso = None
            
            if assinatura_db and assinatura_db.get('ultimo_aviso'):
                try:
                    ultimo_aviso = datetime.datetime.strptime(assinatura_db['ultimo_aviso'], "%d/%m/%Y %H:%M:%S")
                except:
                    pass
            
            # Lógica de avisos e expiração
            if dias_restantes > 0:
                if dias_restantes in [7, 3, 1]:  # Avisar 7, 3 e 1 dia antes
                    enviar_aviso = True
                    
                    if ultimo_aviso:
                        horas_desde_ultimo = (datetime.datetime.now() - ultimo_aviso).total_seconds() / 3600
                        if horas_desde_ultimo < 12:  # Não enviar se já avisou nas últimas 12h
                            enviar_aviso = False
                    
                    if enviar_aviso:
                        try:
                            dm_channel = await member.create_dm()
                            if dias_restantes == 1:
                                mensagem = f"🔔 Olá {member.name}, sua assinatura expira **AMANHÃ**!\nRenove seu plano clicando no botão abaixo:"
                                registrar_aviso(member.id, "AVISO_1_DIA")
                            elif dias_restantes == 3:
                                mensagem = f"🔔 Olá {member.name}, sua assinatura expira em **3 dias**!\nRenove seu plano clicando no botão abaixo:"
                                registrar_aviso(member.id, "AVISO_3_DIAS")
                            else:  # 7 dias
                                mensagem = f"🔔 Olá {member.name}, sua assinatura expira em **7 dias**!\nRenove seu plano clicando no botão abaixo:"
                                registrar_aviso(member.id, "AVISO_7_DIAS")

                            await dm_channel.send(mensagem, view=RenovarAssinaturaView(member))
                            logger.info(f"Enviado aviso para {member.name} ({dias_restantes} dias restantes)")
                        except Exception as e:
                            logger.error(f"Erro ao enviar DM para {member.name}: {e}")

            elif dias_restantes == 0:  # Dia da expiração
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
                
                atualizar_status_assinatura(member.id, "VENCENDO_HOJE", "Assinatura vence hoje")
            
            elif dias_restantes == -1:  # 1 dia após expiração - REMOVER
                try:
                    # Tentar enviar DM primeiro
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

async def setup(bot):
    await bot.add_cog(ChecagemAssinaturas(bot))