import disnake
from disnake.ext import commands
import re
import emoji as emoji_lib
import aiohttp

class EmojiAddView(disnake.ui.View):
    def __init__(self, bot, guild, emoji_name, emoji_url, is_animated, timeout=30):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.guild = guild
        self.emoji_name = emoji_name
        self.emoji_url = emoji_url
        self.is_animated = is_animated
        self.message = None

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if inter.author.id != self.guild.owner_id:
            if not inter.response.is_done():
                embed = disnake.Embed(
                    description=f"❌ | Эта кнопка доступна только создателю сервера.",
                    color=0x2B2D31
                )
                await inter.followup.send(embed=embed, ephemeral=True)
            return False
        return True

    @disnake.ui.button(label="Добавить эмодзи", emoji="➕", style=disnake.ButtonStyle.grey)
    async def add_emoji(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
        button.disabled = True
        await inter.response.edit_message(view=self)
        
        if self.is_animated:
            animated_count = len([e for e in self.guild.emojis if e.animated])
            if animated_count >= self.guild.emoji_limit:
                embed = disnake.Embed(
                    description=f"❌ | На сервере нет места для нового анимированного эмодзи. ({animated_count}/{self.guild.emoji_limit})",
                    color=0x2B2D31
                )
                await inter.followup.send(embed=embed, ephemeral=True)
                return
        else:
            static_count = len([e for e in self.guild.emojis if not e.animated])
            if static_count >= self.guild.emoji_limit:
                embed = disnake.Embed(
                    description=f"❌ | На сервере нет места для нового обычного эмодзи. ({static_count}/{self.guild.emoji_limit})",
                    color=0x2B2D31
                )
                await inter.followup.send(embed=embed, ephemeral=True)
                return

        async with aiohttp.ClientSession() as session:
            async with session.get(self.emoji_url) as resp:
                if resp.status != 200:
                    embed = disnake.Embed(
                        description=f"❌ | Ошибка загрузки изображения.",
                        color=0x2B2D31
                    )
                    await inter.followup.send(embed=embed, ephemeral=True)
                    return
                image_data = await resp.read()

        try:
            created_emoji = await self.guild.create_custom_emoji(name=self.emoji_name, image=image_data)
            embed = disnake.Embed(
                description=f"✅ | Эмодзи успешно добавлен: {created_emoji}",
                color=0x2B2D31
            )
            await inter.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            embed = disnake.Embed(
                description=f"❌ | Ошибка: ```{e}```",
                color=0x2B2D31
            )
            await inter.followup.send(embed=embed, ephemeral=True)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except disnake.NotFound:
                pass

class Emoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_views = []

    @commands.slash_command(description="🔍 | Информация об эмодзи", guild_only=True)
    async def emoji(self, inter: disnake.ApplicationCommandInteraction, emoji: str):
        
        try:
            match = re.match(r"<a?:(\w+):(\d+)>", emoji)
            if match:
                await inter.response.defer()
                emoji_name = match.group(1)
                emoji_id = match.group(2)
                is_animated = emoji.startswith("<a:")
                url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{'gif' if is_animated else 'png'}"

                embed = (
                    disnake.Embed(title="Эмодзи", color=0x2B2D31)
                    .set_image(url=url)
                    .add_field(name="ID", value=emoji_id)
                    .add_field(name="Анимация", value="✅" if is_animated else "❌")
                    .add_field(name="Ссылка", value=f"[Скачать]({url})")
                )

                if inter.author.id == inter.guild.owner_id:
                    view = EmojiAddView(self.bot, inter.guild, emoji_name, url, is_animated)
                    await inter.edit_original_response(embed=embed, view=view)
                    view.message = await inter.original_message()
                    self.active_views.append(view)
                else:
                    await inter.edit_original_response(embed=embed)
                return

            if len(emoji) <= 4 and emoji_lib.is_emoji(emoji):
                await inter.response.defer()
                embed = disnake.Embed(
                    title=f"Эмодзи {emoji}",
                    description="Стандартный Unicode-эмодзи",
                    color=0x2B2D31
                ).add_field(name="Код", value=repr(emoji))
                await inter.edit_original_response(embed=embed)
                return

            embed = disnake.Embed(
                description=f"❌ | Неверный формат эмодзи. Используйте Unicode эмодзи или Discord эмодзи в формате `<:name:id>`",
                color=0x2B2D31
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return


        except Exception as e:
            try:
                embed = disnake.Embed(
                    description=f"❌ | Ошибка: ```{e}```",
                    color=0x2B2D31
                )
                await inter.edit_original_response(embed=embed)
            except Exception:
                pass

    def cog_unload(self):
        for view in self.active_views:
            for child in view.children:
                child.disabled = True
            if view.message:
                self.bot.loop.create_task(view.message.edit(view=view))

def setup(bot):
    bot.add_cog(Emoji(bot))
