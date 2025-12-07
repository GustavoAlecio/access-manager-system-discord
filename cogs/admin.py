# cogs/admin.py
import discord
from discord.ext import commands
import logging
from database import obter_resumo_assinaturas
from utils import criar_embed_assinaturas, gerar_arquivo_assinaturas

logger = logging.getLogger(__name__)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="assinaturas")
    @commands.has_permissions(administrator=True)
    async def ver_assinaturas(self, ctx):
        """Mostra um resumo completo das assinaturas (apenas admin)"""
        try:
            resumo = obter_resumo_assinaturas()
            
            if not resumo:
                await ctx.send("❌ Erro ao obter informações das assinaturas.")
                return
            
            embed = criar_embed_assinaturas(resumo, ctx.author)
            await ctx.send(embed=embed)
            
            # Arquivo detalhado
            if resumo['ativas'] or resumo['expiradas']:
                arquivo = await gerar_arquivo_assinaturas(resumo)
                await ctx.send(file=arquivo)
                
        except Exception as e:
            logger.error(f"Erro no comando assinaturas: {e}")
            await ctx.send("❌ Ocorreu um erro ao gerar o relatório de assinaturas.")

async def setup(bot):
    await bot.add_cog(AdminCog(bot))