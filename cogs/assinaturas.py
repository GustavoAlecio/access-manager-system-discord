# cogs/assinaturas.py
import discord
from discord.ext import commands
import datetime
import logging
from database import obter_assinatura, obter_resumo_assinaturas
from utils import criar_embed_assinaturas, gerar_arquivo_assinaturas
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
                    status_text = "OK"
                elif dias_restantes > 5:
                    cor = "🟡"
                    status_text = "ATENÇÃO"
                else:
                    cor = "🔴"
                    status_text = "URGENTE"
                
                embed.add_field(
                    name="⏳ Status da Renovação",
                    value=f"{cor} **{dias_restantes} dias restantes**\n{status_text}",
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

async def setup(bot):
    await bot.add_cog(AssinaturasCog(bot))