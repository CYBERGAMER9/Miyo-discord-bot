class GuildMenuPageSource(menus.ListPageSource):
    def __init__(self, data: list[Any], *, per_page: int = 5) -> None:
        super().__init__(data, per_page=per_page)
        
        self.embed = discord.Embed(
            color=discord.Color.random(),
            title="Server List",
            timestamp=discord.utils.utcnow(),
        )
    
    # Entries format: (guild.name, guild.invites)
    async def format_page(self, menu: PaginationView, entries: list[Any]) -> discord.Embed:
        entries_embed = []
        for entry in entries:
            entries_embed.append(inspect.cleandoc(f"{entry[0].name}: {entry[1].invite[0]}"))
        
        self.embed.description = "\n\n".join(entries) or "No guilds were found."
        return self.embed