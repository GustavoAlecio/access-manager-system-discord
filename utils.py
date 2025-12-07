# utils.py
import discord
import datetime
from datetime import timedelta
import re
import logging
from database import DB_DATETIME_FORMAT, DISPLAY_FORMAT, LEGACY_DATETIME_FORMAT, adicionar_assinatura
from config import CARGO_ASSINANTE_NOME, APOSTAS_CHANNEL_ID

logger = logging.getLogger(__name__)

def parse_db_datetime_to_display(raw: str) -> str:
    """
    Converte string de data/hora do banco (ISO ou legado) para dd/mm/YYYY.
    """
    if not raw:
        return "N/D"
    for fmt in (DB_DATETIME_FORMAT, LEGACY_DATETIME_FORMAT):
        try:
            dt = datetime.datetime.strptime(raw, fmt)
            return dt.strftime(DISPLAY_FORMAT)
        except ValueError:
            continue
    # tentativa final com só a parte da data no formato legado
    try:
        dt = datetime.datetime.strptime(raw[:10], "%d/%m/%Y")
        return dt.strftime(DISPLAY_FORMAT)
    except Exception:
        return raw  # devolve como veio, pra não perder informação


async def liberar_usuario(guild: discord.Guild, user: discord.User, dias: int) -> str:
    """Libera um usuário no servidor com assinatura"""
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
    if canal_assinantes:
        await canal_assinantes.set_permissions(cargo_assinante, view_channel=True, send_messages=True)
    
    adicionar_assinatura(member.id, member.name, data_expiracao, nome_plano)
    
    return f"✅ {member.mention} foi liberado no *{nome_plano}! Expira em *{data_formatada}."

async def atualizar_nickname(member: discord.Member, dias: int) -> None:
    """Atualiza o nickname com nova data de expiração"""
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

def criar_embed_assinaturas(resumo, author):
    """Cria embed para o comando !assinaturas"""
    embed = discord.Embed(
    title="📊 RELATÓRIO COMPLETO DE ASSINATURAS",
    color=discord.Color.blue(),
    timestamp=datetime.datetime.now()
)

    embed.add_field(
        name="📈 ESTATÍSTICAS GERAIS",
        value=(
            f"✅ **Ativas:** {resumo['total_ativas']}\n"
            f"⚠️ **A vencer (até 3 dias):** {resumo['total_pendentes']}\n"
            f"❌ **Expiradas:** {resumo['total_expiradas']}\n"
            f"📊 **Total:** {resumo['total_ativas'] + resumo['total_expiradas']}\n\n"
            f"🔔 *Lembretes automáticos para o usuário são enviados com **3 dias** de antecedência "
            f"e no dia da expiração.*"
        ),
        inline=False
    )
    
    # Assinaturas ativas
    if resumo['ativas']:
        ativas_text = ""
        for i, assinatura in enumerate(resumo['ativas'][:10], 1):
            username = assinatura[1]
            raw_data_exp = assinatura[2]
            plano = assinatura[3]
            
            data_exp_display = parse_db_datetime_to_display(raw_data_exp)
            
            try:
                dt_exp = None
                for fmt in (DB_DATETIME_FORMAT, LEGACY_DATETIME_FORMAT):
                    try:
                        dt_exp = datetime.datetime.strptime(raw_data_exp, fmt)
                        break
                    except ValueError:
                        continue
                if dt_exp:
                    data_expiracao = dt_exp.date()
                    hoje = datetime.datetime.now().date()
                    dias_restantes = (data_expiracao - hoje).days
                    
                    if dias_restantes > 0:
                        emoji = "🟢" if dias_restantes > 5 else "🟡"
                        status = f"{dias_restantes} dias"
                    else:
                        emoji = "🔴"
                        status = "VENCIDA"
            except:
                emoji = "⚪"
                status = "??"
            
            ativas_text += f"{emoji} `{username[:20]:20}` | {data_exp_display} | {plano} | {status}\n"
        
        if len(resumo['ativas']) > 10:
            ativas_text += f"\n... e mais {len(resumo['ativas']) - 10} assinaturas ativas"
        
        embed.add_field(
            name=f"✅ ASSINATURAS ATIVAS ({len(resumo['ativas'])})",
            value=ativas_text or "Nenhuma assinatura ativa",
            inline=False
        )
    
    # Assinaturas a vencer
    if resumo['pendentes']:
        pendentes_text = ""
        for assinatura in resumo['pendentes'][:5]:
            username = assinatura[1]
            raw_data_exp = assinatura[2]
            plano = assinatura[3]
            
            data_exp_display = parse_db_datetime_to_display(raw_data_exp)
            
            try:
                dt_exp = None
                for fmt in (DB_DATETIME_FORMAT, LEGACY_DATETIME_FORMAT):
                    try:
                        dt_exp = datetime.datetime.strptime(raw_data_exp, fmt)
                        break
                    except ValueError:
                        continue
                if dt_exp:
                    data_expiracao = datetime.datetime.strptime(dt_exp, "%d/%m/%Y").date()
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
                
            pendentes_text += f"🔴 `{username[:20]:20}` | {data_exp_display} | {plano} | Vence {status}\n"
        
        embed.add_field(
            name=f"⚠️ PRÓXIMAS A VENCER ({len(resumo['pendentes'])})",
            value=pendentes_text,
            inline=False
        )
    
    # Assinaturas expiradas
    if resumo['expiradas']:
        expiradas_text = ""
        for assinatura in resumo['expiradas'][:5]:
            username = assinatura[1]
            raw_data_exp = assinatura[2]
            plano = assinatura[3]
            data_exp_display = parse_db_datetime_to_display(raw_data_exp)
            expiradas_text += f"❌ `{username[:20]:20}` | {data_exp_display} | {plano}\n"
        
        
        
        embed.add_field(
            name=f"❌ EXPIRADAS RECENTES ({len(resumo['expiradas'])})",
            value=expiradas_text,
            inline=False
        )
    
    icon_url = author.avatar.url if author.avatar else None
    embed.set_footer(text=f"Solicitado por {author.name}", icon_url=icon_url)
    
    return embed

async def gerar_arquivo_assinaturas(resumo, filename='relatorio_assinaturas.txt'):
    """Gera arquivo TXT com relatório detalhado"""
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("RELATÓRIO COMPLETO DE ASSINATURAS\n")
        f.write("=" * 50 + "\n\n")
        
        f.write("ASSINATURAS ATIVAS:\n")
        f.write("-" * 50 + "\n")
        for assinatura in resumo['ativas']:
            data_exp_display = parse_db_datetime_to_display(assinatura[2])
            f.write(
                f"ID: {assinatura[0]} | Usuário: {assinatura[1]} | Expira: {data_exp_display} | Plano: {assinatura[3]}\n"
            )
        
        f.write("\nASSINATURAS EXPIRADAS:\n")
        f.write("-" * 50 + "\n")
        for assinatura in resumo['expiradas']:
            data_exp_display = parse_db_datetime_to_display(assinatura[2])
            f.write(
                f"ID: {assinatura[0]} | Usuário: {assinatura[1]} | Expirou: {data_exp_display} | Plano: {assinatura[3]}\n"
            )
    
    return discord.File(filename)