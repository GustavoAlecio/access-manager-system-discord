# views.py
import discord
from discord.ui import Button, View, Select
import asyncio
from config import *
from database import registrar_aviso, adicionar_assinatura
import re
import datetime

class PlanoSelect(View):
    def __init__(self, timeout=TEMPO_TIMEOUT_VIEW):
        super().__init__(timeout=timeout)
        self.add_item(PlanoDropdown())

class PlanoDropdown(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Comprar Plano", description="Planos mensal, trimestral, semestral e anual.", emoji="🟢"),
            discord.SelectOption(label="Suporte", description="Entre em contato com nosso suporte via Telegram", emoji="☎")
        ]
        super().__init__(placeholder="Escolha uma opção...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_option = self.values[0]
        
        if selected_option == "Comprar Plano":
            view = PlanoView(URL_COMPRA)
            suporte_view = PlanoView(URL_SUPORTE)
            
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
                view=PlanoView(URL_SUPORTE),
                ephemeral=True
            )

class PlanoView(View):
    def __init__(self, url, timeout=TEMPO_TIMEOUT_VIEW):
        super().__init__(timeout=timeout)
        button = Button(label="Acessar", url=url, style=discord.ButtonStyle.link)
        self.add_item(button)

class ConfirmarPagamentoView(View):
    def __init__(self, user, timeout=TEMPO_TIMEOUT_VIEW):
        super().__init__(timeout=timeout)
        self.user = user
        self.add_item(ConfirmarPagamentoButton(user, dias=30, label="Plano Mensal"))
        self.add_item(ConfirmarPagamentoButton(user, dias=90, label="Plano Trimestral"))
        self.add_item(ConfirmarPagamentoButton(user, dias=180, label="Plano Semestral"))
        self.add_item(ConfirmarPagamentoButton(user, dias=365, label="Plano Anual"))

class ConfirmarPagamentoButton(Button):
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
            
        from utils import liberar_usuario
        msg = await liberar_usuario(guild, self.user, dias=self.dias)
        await interaction.followup.send(msg, ephemeral=True)
        
        try:
            await asyncio.sleep(3)
            dm_channel = await self.user.create_dm()
            await dm_channel.send(
                f"🎉 Olá {self.user.name}, seu pagamento foi confirmado! Seja bem-vindo ao servidor! 🚀"
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")

class RenovarAssinaturaView(View):
    def __init__(self, user, timeout=TEMPO_TIMEOUT_VIEW):
        super().__init__(timeout=timeout)
        self.user = user
    
    @discord.ui.button(label="Renovar Plano", style=discord.ButtonStyle.green)
    async def renovar_plano(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(
            "Para renovar sua assinatura, acesse o link abaixo:\n"
            f"🔗 [Renovar Assinatura]({URL_RENOVACAO})\n"
            f"🔴 [**Após o pagamento, envie o comprovante e seu nick do discord para o suporte:** ]({URL_SUPORTE})",
            ephemeral=True
        )
        
        canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
        if canal:
            await canal.send(
                f"📝 O usuário {self.user.mention} iniciou o processo de renovação. Aguardando confirmação de pagamento.",
                view=SuporteRenovacaoView(self.user)
            )

class SuporteRenovacaoView(View):
    def __init__(self, user, timeout=TEMPO_TIMEOUT_VIEW):
        super().__init__(timeout=timeout)
        self.user = user

    @discord.ui.button(label="Liberar Plano Mensal", style=discord.ButtonStyle.primary)
    async def liberar_plano_mensal(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            cargo = discord.utils.get(interaction.guild.roles, name=CARGO_ASSINANTE_NOME)
            if cargo and cargo not in self.user.roles:
                await self.user.add_roles(cargo, reason="Plano Mensal renovado pelo suporte.")
            
            from utils import atualizar_nickname
            member = interaction.guild.get_member(self.user.id)
            if member:
                await atualizar_nickname(member, 30)
            
            await interaction.response.send_message(
                f"✅ Plano Mensal ativado para {self.user.mention}.", ephemeral=True
            )
            
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Mensal ativado para {self.user.mention}.")
            
            try:
                dm_channel = await self.user.create_dm()
                await dm_channel.send("✅ Seu plano Mensal foi renovado! 🎉")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")
                
        except discord.errors.NotFound:
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Mensal ativado para {self.user.mention}.")
            
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Interação expirada. Mensagem enviada diretamente no canal.")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao liberar plano Mensal: {e}")

    @discord.ui.button(label="Liberar Plano Trimestral", style=discord.ButtonStyle.success)
    async def liberar_plano_trimestral(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            cargo = discord.utils.get(interaction.guild.roles, name=CARGO_ASSINANTE_NOME)
            if cargo and cargo not in self.user.roles:
                await self.user.add_roles(cargo, reason="Plano Trimestral renovado pelo suporte.")
            
            from utils import atualizar_nickname
            member = interaction.guild.get_member(self.user.id)
            if member:
                await atualizar_nickname(member, 90)
            
            await interaction.response.send_message(
                f"✅ Plano Trimestral ativado para {self.user.mention}.", ephemeral=True
            )
            
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Trimestral ativado para {self.user.mention}.")
            
            try:
                dm_channel = await self.user.create_dm()
                await dm_channel.send("✅ Seu plano Trimestral foi renovado! 🎉")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")
                
        except discord.errors.NotFound:
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Trimestral ativado para {self.user.mention}.")
            
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Interação expirada. Mensagem enviada diretamente no canal.")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao liberar plano Trimestral: {e}")
            
            
    @discord.ui.button(label="Liberar Plano Semestral", style=discord.ButtonStyle.success)
    async def liberar_plano_semestral(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            cargo = discord.utils.get(interaction.guild.roles, name=CARGO_ASSINANTE_NOME)
            if cargo and cargo not in self.user.roles:
                await self.user.add_roles(cargo, reason="Plano Semestral renovado pelo suporte.")
            
            from utils import atualizar_nickname
            member = interaction.guild.get_member(self.user.id)
            if member:
                await atualizar_nickname(member, 180)
            
            await interaction.response.send_message(
                f"✅ Plano Semestral ativado para {self.user.mention}.", ephemeral=True
            )
            
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Semestral ativado para {self.user.mention}.")
            
            try:
                dm_channel = await self.user.create_dm()
                await dm_channel.send("✅ Seu plano Semestral foi renovado! 🎉")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")
                
        except discord.errors.NotFound:
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Semestral ativado para {self.user.mention}.")
            
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Interação expirada. Mensagem enviada diretamente no canal.")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao liberar plano Semestral: {e}")
            
    @discord.ui.button(label="Liberar Plano Anual", style=discord.ButtonStyle.success)
    async def liberar_plano_anual(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            cargo = discord.utils.get(interaction.guild.roles, name=CARGO_ASSINANTE_NOME)
            if cargo and cargo not in self.user.roles:
                await self.user.add_roles(cargo, reason="Plano Anual renovado pelo suporte.")
            
            from utils import atualizar_nickname
            member = interaction.guild.get_member(self.user.id)
            if member:
                await atualizar_nickname(member, 365)
            
            await interaction.response.send_message(
                f"✅ Plano Anual ativado para {self.user.mention}.", ephemeral=True
            )
            
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Anual ativado para {self.user.mention}.")
            
            try:
                dm_channel = await self.user.create_dm()
                await dm_channel.send("✅ Seu plano Anual foi renovado! 🎉")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Erro ao enviar DM para {self.user.name}: {e}")
                
        except discord.errors.NotFound:
            canal = interaction.client.get_channel(SUPORTE_CHANNEL_ID)
            if canal:
                await canal.send(f"✅ Plano Anual ativado para {self.user.mention}.")
            
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("Interação expirada. Mensagem enviada diretamente no canal.")
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erro ao liberar plano Anual: {e}")