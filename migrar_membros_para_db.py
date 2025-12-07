# migrar_membros_para_banco.py

import asyncio
import datetime
import re
import logging

import discord

from config import TOKEN, SERVER_ID, CARGO_ASSINANTE_NOME
from database import adicionar_assinatura, registrar_aviso

logger = logging.getLogger("migracao")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)


INTENTS = discord.Intents.default()
INTENTS.members = True  # precisamos ver os membros


class MigracaoClient(discord.Client):
    async def on_ready(self):
        logger.info(f"Logado como {self.user} (ID: {self.user.id})")
        guild = self.get_guild(SERVER_ID)

        if not guild:
            logger.error(f"Servidor com ID {SERVER_ID} não encontrado.")
            await self.close()
            return

        hoje = datetime.date.today()
        total_processados = 0
        total_assinaturas_criadas = 0
        total_avisos_marcados = 0

        logger.info(f"Iniciando migração no servidor: {guild.name} ({guild.id})")

        for member in guild.members:
            # pula bots
            if member.bot:
                continue

            # precisa ter nick e estar no formato "Nome | dd/mm/aaaa"
            if not member.nick or " | " not in member.nick:
                continue

            partes = member.nick.split("|")
            if len(partes) < 2:
                continue

            data_str = partes[1].strip()
            if not re.match(r"\d{2}/\d{2}/\d{4}$", data_str):
                continue

            try:
                data_expiracao_date = datetime.datetime.strptime(data_str, "%d/%m/%Y").date()
            except ValueError:
                logger.warning(f"Nick com data inválida para {member.nick}, pulando...")
                continue

            dias_restantes = (data_expiracao_date - hoje).days

            # monta datetime para gravar no banco (meia-noite daquele dia)
            data_expiracao_dt = datetime.datetime.combine(
                data_expiracao_date, datetime.time(0, 0)
            )

            plano = "Importado (nickname)"

            # cria/atualiza assinatura no banco
            ok = adicionar_assinatura(
                user_id=member.id,
                username=member.name,
                data_expiracao=data_expiracao_dt,
                plano=plano,
            )

            total_processados += 1
            if ok:
                total_assinaturas_criadas += 1
                logger.info(
                    f"[ASSINATURA] {member.name} ({member.id}) -> expira em {data_str} "
                    f"({dias_restantes} dias restantes)"
                )
            else:
                logger.error(
                    f"[ERRO ASSINATURA] Falha ao adicionar/atualizar assinatura para {member.name} ({member.id})"
                )
                continue

            # ✅ Marcar que já foram avisados HOJE se estiverem em 5, 3 ou 1 dias
            if dias_restantes == 3:
                tipo = "AVISO_3_DIAS"

                ok_aviso = registrar_aviso(member.id, tipo)
                if ok_aviso:
                    total_avisos_marcados += 1
                    logger.info(
                        f"[AVISO MARCADO] {member.name} ({member.id}) marcado como {tipo} em {data_str}"
                    )
                else:
                    logger.error(
                        f"[ERRO AVISO] Falha ao registrar aviso {tipo} para {member.name} ({member.id})"
                    )
            elif dias_restantes == 0:
                tipo = "AVISO_EXPIRA_HOJE"
                ok_aviso = registrar_aviso(member.id, tipo)
                if ok_aviso:
                    total_avisos_marcados += 1
                    logger.info(
                        f"[AVISO MARCADO] {member.name} ({member.id}) marcado como {tipo} em {data_str}"
                    )
                else:
                    logger.error(
                        f"[ERRO AVISO] Falha ao registrar aviso {tipo} para {member.name} ({member.id})"
                    )

        logger.info("==== RESUMO MIGRAÇÃO ====")
        logger.info(f"Membros processados (com nick no formato esperado): {total_processados}")
        logger.info(f"Assinaturas criadas/atualizadas: {total_assinaturas_criadas}")
        logger.info(f"Avisos marcados hoje (3/0 dias): {total_avisos_marcados}")
        logger.info("Migração concluída. Fechando o client.")
        await self.close()


def main():
    client = MigracaoClient(intents=INTENTS)
    client.run(TOKEN)


if __name__ == "__main__":
    main()
