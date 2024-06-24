import discord
from discord.ext import commands
from discord.ext.commands import Context
import asyncio

class Paginator:
    def __init__(self, bot):
        self.bot = bot

    async def paginate(self, ctx: Context, pages: list, timeout=120):
        current_page = 0
        message = await ctx.send(embed=pages[current_page])
        
        await message.add_reaction("◀️")
        await message.add_reaction("▶️")
        await message.add_reaction("❌")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️", "❌"]

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=timeout, check=check)
                if str(reaction.emoji) == "▶️" and current_page < len(pages) - 1:
                    current_page += 1
                    await message.edit(embed=pages[current_page])
                elif str(reaction.emoji) == "◀️" and current_page > 0:
                    current_page -= 1
                    await message.edit(embed=pages[current_page])
                elif str(reaction.emoji) == "❌":
                    await message.delete()
                    break

                await message.remove_reaction(reaction, user)
            except:
                break

class Help(commands.Cog, name="help"):
    def __init__(self, bot) -> None:
        self.bot = bot

    @commands.command(name="help", description="List all commands.")
    async def help_command(self, context: Context) -> None:
        pages = []
        for cog_name in self.bot.cogs:
            cog = self.bot.get_cog(cog_name)
            commands_list = cog.get_commands()
            if not commands_list:
                continue
            embed = discord.Embed(
                title=f"{cog_name} Commands",
                description=f"List of available commands in {cog_name}:",
                color=0x00FF00,
            )
            for command in commands_list:
                if command.hidden:
                    continue
                embed.add_field(
                    name=f"`${command.name}`",
                    value=command.description or "No description",
                    inline=False,
                )
            pages.append(embed)

        paginator = Paginator(self.bot)
        await paginator.paginate(context, pages)

    @commands.command(name="clear", description="clears the chat")
    async def clear(self,ctx, *, n: int):
        try:
            if n < 10001:
                count = n//100
                rem = n % 100
                for i in range(count):
                    messages = []
                    async for message in ctx.channel.history(limit=100):
                        messages.append(message)
                    await ctx.channel.delete_messages(messages)
                    await asyncio.sleep(1.2)
                messages = []
                async for message in ctx.channel.history(limit=(rem+1)):
                    messages.append(message)
                await ctx.channel.delete_messages(messages)
                k = str(ctx.message.author)+' deleted '+str(n)+' messages.'
                async with ctx.typing():
                    embed = discord.Embed(
                        title="Clear", description=k, colour=discord.Color.green())
                m = await ctx.send(embed=embed)
                await asyncio.sleep(3)
                await ctx.channel.delete_messages([m])
            else:
                async with ctx.typing():
                    embed = discord.Embed(
                        title="Error", description='Cannot clear more than 10,000 msgs at once.', colour=discord.Color.red())
                await ctx.send(embed=embed)
        except:
            async with ctx.typing():
                embed = discord.Embed(
                    title="Error", description='Permission Error.', colour=discord.Color.red())
            await ctx.send(embed=embed)


async def setup(bot) -> None:
    await bot.add_cog(Help(bot))
