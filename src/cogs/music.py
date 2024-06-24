import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord.utils import get
import yt_dlp
import random
import asyncio
from collections import deque
import aiohttp

def create_embed(title: str, description: str, color=discord.Color.green(), image=None, thumbnail=None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if image:
        embed.set_image(url=image)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return embed

async def ytbettersearch(query):
    url = f"https://www.youtube.com/results?search_query={query}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            html = await resp.text()
    index = html.find('watch?v')
    url = ""
    while True:
        char = html[index]
        if char == '"':
            break
        url += char
        index += 1
    url = f"https://www.youtube.com/{url}"
    return url



class Music(commands.Cog, name="music"):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.queue = deque()
        self.is_playing = False
        self.player = None
        self.current_song = None
        self.on_loop = False

    @commands.command(name="join", description="Join the voice channel.")
    async def join(self, context: Context) -> None:
        if not context.author.voice:
            await context.send(embed=create_embed("Error", "You are not connected to a voice channel"))
            return
        await context.author.voice.channel.connect()

    @commands.command(name="play", description="Play a song from YouTube.")
    async def play(self, context: Context, *, url: str) -> None:
        voice = get(self.bot.voice_clients, guild=context.guild)
        try:
            await context.author.voice.channel.connect()
        except:
            pass
        
        url = await ytbettersearch(url)
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            self.current_song = info
            song = {
                'url': info['url'],
                'title': info['title'],
                'thumbnail': info['thumbnail']
            }
        
        voice = context.voice_client
        if voice.is_playing() or voice.is_paused():
            self.queue.appendleft(song)
            embed = discord.Embed(title="Added to Queue", description=f"Added {song['title']} to the queue.", color=discord.Color.green())
            await context.send(embed=embed)
        else:
            await self.play_audio(context, voice, song)

    async def play_audio(self, context: Context, voice, song) -> None:
        self.current_song = song
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        self.player = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song['url'], **ffmpeg_options))
        voice.play(self.player, after=lambda e: asyncio.run_coroutine_threadsafe(self._on_song_end(context), self.bot.loop))
        
        await context.send(embed=create_embed("Now Playing", f"Playing {song['title']}", thumbnail=song['thumbnail']))

    async def _on_song_end(self,context):
        if self.on_loop:
            await self.play_audio(context, self.current_song)
        else:
            await self.next(context)

    @commands.command(name="next", description="Play the next song in the queue.")
    async def next(self, context: Context) -> None:
        voice = get(self.bot.voice_clients, guild=context.guild)
        if self.queue:
            next_song = self.queue.popleft()
            await self.play_audio(context, voice, next_song)
        else:
            self.current_song = None
            embed = discord.Embed(title="Queue Empty", description="There are no more songs in the queue.", color=discord.Color.red())
            await context.send(embed=embed)

    @commands.command(name="pause", description="Pause the currently playing song.")
    async def pause(self, context: Context) -> None:
        voice = get(self.bot.voice_clients, guild=context.guild)
        if voice and voice.is_playing():
            voice.pause()
            await context.send(embed=create_embed("Voice", "Music Paused!"))
        else:
            await context.send(embed=create_embed("Error", "No music Playing or some error occurred."))

    @commands.command(name="resume", description="Resume the currently paused song.")
    async def resume(self, context: Context) -> None:
        voice = get(self.bot.voice_clients, guild=context.guild)
        if voice and voice.is_paused():
            voice.resume()
            await context.send(embed=create_embed("Voice", "Music Resumed!"))
        else:
            await context.send(embed=create_embed("Error", "No music Paused or some error occurred."))

    @commands.command(name="stop", description="Stop the currently playing song.")
    async def stop(self, context: Context) -> None:
        voice = get(self.bot.voice_clients, guild=context.guild)
        if (voice and voice.is_paused()) or (voice and voice.is_playing()):
            voice.stop()
        else:
            await context.send(embed=create_embed("Error", "No music Paused or Playing or some error occurred."))

    @commands.command(name="volume", description="Set the volume of the music.")
    async def volume(self, context: Context, vol: float) -> None:
        voice = context.voice_client
        voice.source.volume = (vol / 100)
        await context.send(embed=create_embed("Volume", f"Changed volume to {voice.source.volume * 100}%"))

    @commands.command(name="now_playing", description="Show the currently playing song.")
    async def now_playing(self, context: Context) -> None:
        if (not self.player) or (not self.current_song):
            embed = discord.Embed(title="Error", description="There is no music playing right now.", color=discord.Color.red())
            return await context.send(embed=embed)
        title = self.current_song["title"]
        embed = discord.Embed(title=f"Now Playing: {title}", color=discord.Color.green())
        embed.set_thumbnail(url=self.current_song["thumbnail"])
        await context.send(embed=embed)

    @commands.command(name="leave", description="Leave the voice channel.")
    async def leave(self, context: Context) -> None:
        voice_client = context.message.guild.voice_client
        await voice_client.disconnect()

    @commands.command(name="queue", description="Show the current queue.")
    async def queue(self, context: Context) -> None:
        if not self.queue:
            embed = discord.Embed(title="Queue", description="There are no songs in the queue.", color=discord.Color.red())
            return await context.send(embed=embed)
        embed = discord.Embed(title="Queue", description="```" + "\n".join([song["title"] for song in self.queue]) + "```", color=discord.Color.green())
        await context.send(embed=embed)

    @commands.command(name="clear", description="Clear the queue.")
    async def clear(self, context: Context) -> None:
        self.queue.clear()
        embed = discord.Embed(title="Queue Cleared", description="The queue has been cleared.", color=discord.Color.green())
        await context.send(embed=embed)
    
    @commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, context: Context) -> None:
        random.shuffle(self.queue)
        embed = discord.Embed(title="Queue Shuffled", description="The queue has been shuffled.", color=discord.Color.green())
        await context.send(embed=embed)
    
    @commands.command(name="remove", description="Remove a song from the queue.")
    async def remove(self, context: Context, index: int) -> None:
        if index < 1 or index > len(self.queue):
            embed = discord.Embed(title="Error", description="Invalid index.", color=discord.Color.red())
            return await context.send(embed=embed)
        song = self.queue[index - 1]
        self.queue.remove(song)
        embed = discord.Embed(title="Song Removed", description=f"Removed {song['title']} from the queue.", color=discord.Color.green())
        await context.send(embed=embed)

    @commands.command(name="loop", description="Loop the current song.")
    async def loop(self, context: Context) -> None:
        if not self.current_song:
            embed = discord.Embed(title="Error", description="There is no song playing right now.", color=discord.Color.red())
            return await context.send(embed=embed)
        self.on_loop = not self.on_loop
        if self.on_loop:
            embed = discord.Embed(title="Loop", description="Looping the current song.", color=discord.Color.green())
        else:
            embed = discord.Embed(title="Loop", description="Stopped looping the current song.", color=discord.Color.red())
        await context.send(embed=embed)
async def setup(bot) -> None:
    await bot.add_cog(Music(bot))
