# cogs/assinaturas.py
import discord
from discord.ext import commands
import datetime
import logging
from database import DB_DATETIME_FORMAT, DISPLAY_FORMAT, LEGACY_DATETIME_FORMAT, obter_assinatura
from views import RenovarAssinaturaView

logger = logging.getLogger(__name__)

class AssinaturasCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="renovar")
    async def renovar(self, ctx):
        """Inicia processo de renovação de assinatura"""
        await ctx.send(
            "🔄 Escolha um plano para renovar sua assinatura:",
            view=RenovarAssinaturaView(ctx.author)
        )

    @commands.command(name="minhaassinatura")
    async def minha_assinatura(self, ctx):
        """Mostra informações da assinatura do usuário"""
        assinatura = obter_assinatura(ctx.author.id)
        
        if not assinatura:
            await ctx.send("❌ Você não possui uma assinatura ativa.")
            return
        
        embed = discord.Embed(
            title=f"📋 SUA ASSINATURA - {ctx.author.name}",
            color=discord.Color.green()
        )
        
        def parse_datetime_compat(raw: str) -> datetime.datetime:
            for fmt in (DB_DATETIME_FORMAT, LEGACY_DATETIME_FORMAT):
                try:
                    return datetime.datetime.strptime(raw, fmt)
                except ValueError:
                    continue
            try: 
                return datetime.datetime.strptime(raw[:10], "%d/%m/%Y")
            except Exception:
                return None
        
        dt_ativacao = parse_datetime_compat(assinatura['data_ativacao']) if assinatura['data_ativacao'] else None
        dt_expiracao = parse_datetime_compat(assinatura['data_expiracao']) if assinatura['data_expiracao'] else None
        
        data_ativacao_str = dt_ativacao.strftime(DISPLAY_FORMAT) if dt_ativacao else "N/D"
        data_expiracao_str = dt_expiracao.strftime(DISPLAY_FORMAT) if dt_expiracao else "N/D"
        
        embed.add_field(name="👤 Usuário", value=ctx.author.mention, inline=True)
        embed.add_field(name="📅 Data de Ativação", value=data_ativacao_str, inline=True)
        embed.add_field(name="📊 Plano", value=assinatura['plano'], inline=True)
        embed.add_field(name="⏰ Expira em", value=data_expiracao_str, inline=True)
        embed.add_field(name="✅ Status", value=assinatura['status'], inline=True)
        
        # Calcular dias restantes
        try:
            if dt_expiracao:
                data_exp = dt_expiracao.date()
                hoje = datetime.datetime.now().date()
                dias_restantes = (data_exp - hoje).days
            else:
                dias_restantes = None
            
            if dias_restantes > 0:
                if dias_restantes > 7:
                    cor = "🟢"
                    status = "Tranquilo"
                    detalhe = "Você ainda tem bastante tempo antes de vencer."
                elif dias_restantes > 3:
                    cor = "🟡"
                    status = "Planeje a renovação"
                    detalhe = "Faltam poucos dias, já comece a se organizar."
                else:
                    cor = "🔴"
                    status = "URGENTE"
                    detalhe = (
                        "Você começará (ou já começou) a receber lembretes automáticos.\n"
                        "Não deixe para a última hora!"
                    )
                
                embed.add_field(
                    name="⏳ Status da Renovação",
                    value=f"{cor} **{dias_restantes} dias restantes**\n{status}\n{detalhe}",
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
        
        embed.set_footer(
            text="Lembretes automáticos são enviados com 3 dias de antecedência e no dia da expiração. Use !renovar para renovar sua assinatura."
        )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AssinaturasCog(bot))