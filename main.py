from dotenv import load_dotenv
import os
from threading import Thread
import discord
from discord.ext import commands, menus
from flask import Flask, render_template
import traceback
from typing import Optional, Any
import inspect  # Import inspect module

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Enable necessary intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

# Initialize Discord bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask app setup
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/commands')
def commands_page():
    return render_template('commands.html')

# Pagination classes
class PaginationView(discord.ui.View):
    def __init__(self, source: menus.PageSource, *, interaction: commands.Context | discord.Interaction, check_embeds: bool = True, compact: bool = False):
        super().__init__()
        self.source: menus.PageSource = source
        self.check_embeds: bool = check_embeds
        self.interaction = interaction
        self.message: Optional[discord.Message] = None
        self.current_page: int = 0
        self.compact: bool = compact
        self.clear_items()
        self.fill_items()

    def fill_items(self) -> None:
        if self.source.is_paginating():
            if not self.compact:
                self.add_item(self.go_to_first_page)
            self.add_item(self.go_to_previous_page)
            self.add_item(self.stop_pages)
            self.add_item(self.go_to_next_page)
            if not self.compact:
                self.add_item(self.go_to_last_page)

    async def _get_kwargs_from_page(self, page: int) -> dict[str, Any]:
        value = await discord.utils.maybe_coroutine(self.source.format_page, self, page)
        if isinstance(value, dict):
            return value
        elif isinstance(value, str):
            return {'content': value, 'embed': None}
        elif isinstance(value, discord.Embed):
            return {'embed': value, 'content': None}
        else:
            return {}

    async def show_page(self, interaction: discord.Interaction, page_number: int) -> None:
        page = await self.source.get_page(page_number)
        self.current_page = page_number
        kwargs = await self._get_kwargs_from_page(page)
        self._update_labels(page_number)
        if kwargs:
            if interaction.response.is_done():
                if self.message:
                    await self.message.edit(**kwargs, view=self)
            else:
                await interaction.response.edit_message(**kwargs, view=self)

    def _update_labels(self, page_number: int) -> None:
        self.go_to_first_page.disabled = page_number == 0
        max_pages = self.source.get_max_pages()
        self.go_to_next_page.disabled = max_pages is not None and (page_number + 1) >= max_pages
        self.go_to_previous_page.disabled = page_number == 0
        if not self.compact:
            self.go_to_last_page.disabled = (page_number + 1) >= max_pages

    async def show_checked_page(self, interaction: discord.Interaction, page_number: int) -> None:
        max_pages = self.source.get_max_pages()
        try:
            if max_pages is None:
                await self.show_page(interaction, page_number)
            elif max_pages > page_number >= 0:
                await self.show_page(interaction, page_number)
        except IndexError:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if isinstance(self.interaction, commands.Context):
            predicate = self.interaction.author.id
        else:
            predicate = self.interaction.user.id

        if interaction.user and interaction.user.id == predicate:
            return True

        await interaction.response.send_message('This menu is not for you.', ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        if self.message is not None:
            for child in self.children:
                child.disabled = True

            await self.message.edit(view=self)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if interaction.response.is_done():
            await interaction.followup.send('An unknown error occurred, sorry', ephemeral=True)
        else:
            await interaction.response.send_message(' An unknown error occurred, sorry', ephemeral=True)

        try:
            exc = ''.join(traceback.format_exception(type(error), error, error.__traceback__, chain=False))
            embed = discord.Embed(
                title=f'{self.source.__class__.__name__} Error',
                description=f'``` py\n{exc}\n```',
                timestamp=interaction.created_at,
                colour=0xCC3366,
            )
            embed.add_field(name='User', value=f'{interaction.user} ({interaction.user.id})')
            embed.add_field(name='Guild', value=f'{interaction.guild} ({interaction.guild_id})')
            embed.add_field(name='Channel', value=f'{interaction.channel} ({interaction.channel_id})')

            if isinstance(self.interaction, discord.Interaction):
                await self.interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await self.interaction.send(embed=embed, ephemeral=True)

        except discord.HTTPException:
            pass

    async def start(self, *, content: Optional[str] = None, ephemeral: bool = False) -> None:
        if self.check_embeds and not self.interaction.channel.permissions_for(self.interaction.guild.me).embed_links:  # type: ignore
            if isinstance(self.interaction, discord.Interaction):
                await self.interaction.response.send_message('Missing embed permissions.', ephemeral=True)
                return

            else:
                await self.interaction.send('Missing embed permissions.', ephemeral=True)

        await self.source._prepare_once()
        page = await self.source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)

        if content:
            kwargs.setdefault('content', content)

        self._update_labels(0)

        if isinstance(self.interaction, discord.Interaction):
            if not self.interaction.response.is_done():
                await self.interaction.response.send_message(**kwargs, view=self, ephemeral=ephemeral)
                self.message = await self.interaction.original_response()

            else:
                self.message = await self.interaction.followup.send(wait=True, ephemeral=ephemeral, **kwargs)

        else:
            self.message = await self.interaction.send(**kwargs, view=self, ephemeral=ephemeral)

    @discord.ui.button(emoji="<:TWD_FIRST:1209075732676874340>", l'Channel'style=discord.ButtonStyle.blurple)
    async def go_to_first_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the first page"""
        await self.show_page(interaction, 0)

    @discord.ui.button(emoji="<:TWD_PREVIOUS:1298504437823967323>", label='', style=discord.ButtonStyle.blurple)
    async def go_to_previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the previous page"""
        await self.show_checked_page(interaction, self.current_page - 1)

    @discord.ui.button(emoji="<a:TWD_CROSS:1183023325992202274>", label='', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """stops the pagination session."""
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    @discord.ui.button(emoji="<:TWD_NEXT:1298504381452517417>", label="", style=discord.ButtonStyle.blurple)
    async def go_to_next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the next page"""
        await self.show_checked_page(interaction, self.current_page + 1)

    @discord.ui.button(emoji="<:TWD_LAST:1209075810879799339>", label="", style=discord.ButtonStyle.blurple)
    async def go_to_last_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """go to the last page"""
        await self.show_page(interaction, self.source.get_max_pages() - 1)

class GuildMenuPageSource(menus.ListPageSource):
    def __init__(self, data: list[Any], *, per_page: int = 5) -> None:
        super().__init__(data, per_page=per_page)

        self.embed = discord.Embed(
            color=discord.Color.random(),
            title="Server List",
            timestamp=discord.utils.utcnow(),
        )

    async def format_page(self, menu: PaginationView, entries: list[Any]) -> discord.Embed:
        entries_embed = []
        for entry in entries:
            entries_embed.append(f"{entry[0].name}: {entry[1]}")

        self.embed.description = "\n\n".join(entries_embed) or "No guilds were found."
        return self.embed

@bot.command(name='servers')
async def servers_command(ctx):
    if ctx .author.id != 1169487822344962060:  # Check if the user is the owner
        return  # Ignore the command without response

    guilds_data = []

    # Iterate through all guilds the bot is a member of
    for guild in bot.guilds:
        # Attempt to get an invite link for the guild
        invites = await guild.invites()
        invite_link = invites[0].url if invites else "No invite available"
        guilds_data.append((guild, invite_link))  # Store guild and its invite link

    # Create a page source with the gathered guild data
    source = GuildMenuPageSource(guilds_data, per_page=5)  # Adjust per_page as needed

    # Create a pagination view and start it
    view = PaginationView(source, interaction=ctx)
    await view.start(content="Here are the servers I'm in:", ephemeral=True)

# Run Flask app in a separate thread
def run_app():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_app).start()

# Run Discord bot
bot.run(TOKEN)