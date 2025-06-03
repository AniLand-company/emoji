import discord
from discord.ext import commands
from discord import app_commands
import re
import emoji as emoji_lib
import aiohttp

class EmojiAddView(discord.ui.View):
    def __init__(self, bot, guild, emoji_name, emoji_url, is_animated, timeout=30):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild = guild
        self.emoji_name = emoji_name
        self.emoji_url = emoji_url
        self.is_animated = is_animated
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.guild.owner_id:
            embed = discord.Embed(
                description=f"❌ | Эта кнопка доступна только создателю сервера.",
                color=0x2B2D31
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Добавить эмодзи", emoji="➕", style=discord.ButtonStyle.grey)
    async def add_emoji(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        if self.is_animated:
            animated_count = len([e for e in self.guild.emojis if e.animated])
            if animated_count >= self.guild.emoji_limit:
                embed = discord.Embed(
                    description=f"❌ | На сервере нет места для нового анимированного эмодзи. ({animated_count}/{self.guild.emoji_limit})",
                    color=0x2B2D31
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
        else:
            static_count = len([e for e in self.guild.emojis if not e.animated])
            if static_count >= self.guild.emoji_limit:
                embed = discord.Embed(
                    description=f"❌ | На сервере нет места для нового обычного эмодзи. ({static_count}/{self.guild.emoji_limit})",
                    color=0x2B2D31
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

        async with aiohttp.ClientSession() as session:
            async with session.get(self.emoji_url) as resp:
                if resp.status != 200:
                    embed = discord.Embed(
                        description=f"❌ | Ошибка загрузки изображения.",
                        color=0x2B2D31
                    )
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                image_data = await resp.read()

        try:
            created_emoji = await self.guild.create_custom_emoji(name=self.emoji_name, image=image_data)
            embed = discord.Embed(
                description=f"✅ | Эмодзи успешно добавлен: {created_emoji}",
                color=0x2B2D31
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ | Ошибка: ```{e}```",
                color=0x2B2D31
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

class Emoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_views = []

    @app_commands.command(name="emoji", description="🔍 | Информация об эмодзи")
    @app_commands.describe(emoji="Эмодзи для анализа")
    async def emoji(self, interaction: discord.Interaction, emoji: str):
        
        try:
            match = re.match(r"<a?:(\w+):(\d+)>", emoji)
            if match:
                await interaction.response.defer()
                emoji_name = match.group(1)
                emoji_id = match.group(2)
                is_animated = emoji.startswith("<a:")
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if is_animated else 'png'}"

                embed = (
                    discord.Embed(title="Эмодзи", color=0x2B2D31)
                    .set_image(url=url)
                    .add_field(name="ID", value=emoji_id)
                    .add_field(name="Анимация", value="✅" if is_animated else "❌")
                    .add_field(name="Ссылка", value=f"[Скачать]({url})")
                )

                if interaction.user.id == interaction.guild.owner_id:
                    view = EmojiAddView(self.bot, interaction.guild, emoji_name, url, is_animated)
                    await interaction.followup.send(embed=embed, view=view)
                    view.message = await interaction.original_response()
                    self.active_views.append(view)
                else:
                    await interaction.followup.send(embed=embed)
                return

            if len(emoji) <= 4 and emoji_lib.is_emoji(emoji):
                await interaction.response.defer()
                embed = discord.Embed(
                    title=f"Эмодзи {emoji}",
                    description="Стандартный Unicode-эмодзи",
                    color=0x2B2D31
                ).add_field(name="Код", value=repr(emoji))
                await interaction.followup.send(embed=embed)
                return

            embed = discord.Embed(
                description=f"❌ | Неверный формат эмодзи. Используйте Unicode эмодзи или Discord эмодзи в формате `<:name:id>`",
                color=0x2B2D31
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        except Exception as e:
            try:
                embed = discord.Embed(
                    description=f"❌ | Ошибка: ```{e}```",
                    color=0x2B2D31
                )
                await interaction.followup.send(embed=embed)
            except Exception:
                pass

    def cog_unload(self):
        for view in self.active_views:
            for child in view.children:
                child.disabled = True
            if view.message:
                self.bot.loop.create_task(view.message.edit(view=view))

async def setup(bot):
    await bot.add_cog(Emoji(bot))
