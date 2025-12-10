# cogs/admin.py
import discord
from discord.ext import commands
import logging
from cogs.tasks import ChecagemAssinaturas
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
            if resumo.get("ativas") or resumo.get("expiradas"):
                arquivo = await gerar_arquivo_assinaturas(resumo)
                await ctx.send(file=arquivo)
                
        except Exception as e:
            logger.error(f"Erro no comando assinaturas: {e}")
            await ctx.send("❌ Ocorreu um erro ao gerar o relatório de assinaturas.")
            
    # =====================================================
    # FORÇAR CHECAGEM DE ASSINATURAS (RODAR TAREFA MANUAL)
    # =====================================================
    @commands.command(name="check_assinaturas")
    @commands.has_permissions(administrator=True)
    async def check_assinaturas(self, ctx):
        """
        Roda manualmente a rotina de checagem de assinaturas.
        Usa o método _rodar_checar_assinaturas_uma_vez da cog ChecagemAssinaturas
        """
        
        cog: ChecagemAssinaturas = self.bot.get_cog("ChecagemAssinaturas")
        
        if cog is None:
            await ctx.send(
                "A cog de checagem de assinaturas não está carregada.\n"
                "Verifique se 'cogs.tasks' foi adicionada no setup do bot."
            )
            return

        msg = await ctx.send("Rodando checagem de assinaturas, aguarde...")
        
        try: 
            await cog._rodar_checar_assinaturas_uma_vez()
        except Exception as e:
            logger.error(f"Erro ao rodar checagem manual de assinaturas: {e}")
            await msg.edit(content="Ocorreu um erro ao rodar a checagem de assinaturas.")
            return
        
        await msg.edit(content="Checagem de assinaturas executada com sucesso.")
        
    # =====================================================
    # HEALTH CHECK DO BOT / SISTEMA DE ASSINATURAS
    # =====================================================
    @commands.command(name='health')
    @commands.has_permissions(administrator=True)
    async def health(self, ctx):
        """
        Mostra o status básico do bot e do sistema de assinaturas.
        Verifica:
        - Latência do bot
        - Acesso básico ao banco via obter_resumo_assinaturas
        """
        ping_ms = round(self.bot.latency *1000)
        
        db_status = "OK"
        db_detail = ""
        
        try:
            resumo = obter_resumo_assinaturas()
            if not resumo:
                db_status = "Sem dados"
                db_detail = "obter_resumo_assinaturas() não retornou informações."
        except Exception as e:
            logger.error(f"Erro ao verificar banco no health: {e}")
            db_status = "Erro"
            db_detail = f"{e.__class__.__name__}: {e}"
        
        embed = discord.Embed(
            title = "Health Check",
            description="Status do bot e do sistema de assinaturas."
        )
        embed.add_field(
            name="Bot",
            value="Online",
            inline=True
        )
        embed.add_field(
            name="Latência",
            value=f"{ping_ms} ms",
            inline=True
        )
        embed.add_field(
            name="Banco / Assinaturas",
            value=f"{db_status}\n{db_detail}" if db_detail else db_status,
            inline=False,
        )
        embed.set_footer(text= f"Conectado em {len(self.bot.guilds)} servidores.")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))