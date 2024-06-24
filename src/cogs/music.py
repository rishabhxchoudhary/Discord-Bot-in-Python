import discord
from discord.ext import commands
from discord.ext.commands import Context
from discord.utils import get
import yt_dlp
import random
import asyncio
from collections import deque
import aiohttp
from dotenv import load_dotenv
import os
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import re

from cogs.help import Paginator

load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)


def get_playlist_id(url):
    pattern = r"playlist/([a-zA-Z0-9]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    else:
        return None

def get_playlist_songs(playlist_id):
    tracks_response = sp.playlist_tracks(playlist_id)
    tracks = tracks_response["items"]
    while tracks_response["next"]:
        tracks_response = sp.next(tracks_response)
        tracks.extend(tracks_response["items"])
    songs = []
    for i in tracks:
        output_str = f"{i['track']['name']} by {i['track']['artists'][0]['name']}"
        songs.append(output_str)
    return songs

def create_embed(title: str, description: str, color=discord.Color.green(), image=None, thumbnail=None) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    if image:
        embed.set_image(url=image)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    return embed

def get_spotify_songs(url):
    playlist_id = get_playlist_id(url)
    if playlist_id:
        songs = get_playlist_songs(playlist_id)
        return songs
    else:
        return False

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
        self.song_queue = deque()
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
        voice = context.voice_client
        if "spotify" in url:
            songs = get_spotify_songs(url)
            if not songs:
                embed = discord.Embed(title="Error", description="Invalid Spotify Playlist URL.", color=discord.Color.red())
                return await context.send(embed=embed)
            for song in songs:
                self.song_queue.append(song)
            if voice.is_playing() or voice.is_paused():
                embed = discord.Embed(title="Added to Queue", description=f"Added {len(songs)} songs to the queue.", color=discord.Color.green())
                await context.send(embed=embed)
            else:
                await self.next(context)
            return
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
        
        if voice.is_playing() or voice.is_paused():
            self.song_queue.appendleft(song)
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
            voice = get(self.bot.voice_clients, guild=context.guild)
            await self.play_audio(context,voice,self.current_song)
        else:
            await self.next(context)

    @commands.command(name="next", description="Play the next song in the queue.")
    async def next(self, context: Context) -> None:
        voice = get(self.bot.voice_clients, guild=context.guild)
        if voice.is_playing() or voice.is_paused():
            self.on_loop = False
            voice.stop()
        if self.song_queue:
            next_song = self.song_queue.popleft()
            if isinstance(next_song, str):
                next_song = await ytbettersearch(next_song)
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
                    info = ydl.extract_info(next_song, download=False)
                    next_song = {
                        'url': info['url'],
                        'title': info['title'],
                        'thumbnail': info['thumbnail']
                }
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

    @commands.command(name="stop", description="Stop the currently playing song and clears the queue.")
    async def stop(self, context: Context) -> None:
        self.song_queue.clear()
        self.current_song = None
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
        embed = discord.Embed(title=f"Now Playing",description=f"{title}", color=discord.Color.green())
        embed.set_thumbnail(url=self.current_song["thumbnail"])
        await context.send(embed=embed)

    @commands.command(name="leave", description="Leave the voice channel.")
    async def leave(self, context: Context) -> None:
        voice_client = context.message.guild.voice_client
        if voice_client:
            self.song_queue.clear()
            self.is_playing = False
            self.current_song = None
            self.on_loop = False
        await voice_client.disconnect()

    @commands.command(name="queue", description="Show the current queue.")
    async def queue(self, context: Context) -> None:
        if not self.song_queue:
            embed = discord.Embed(title="Queue", description="There are no songs in the queue.", color=discord.Color.red())
            return await context.send(embed=embed)
        pages = []
        for i in range(0, len(self.song_queue), 5):
            embed = discord.Embed(title="Queue", description="List of songs in the queue:", color=discord.Color.green())
            for j in range(i, i + 5):
                if j >= len(self.song_queue):
                    break
                song = self.song_queue[j]
                if isinstance(song, dict):
                    embed.add_field(name=f"{j + 1}. {song['title']}", value="",inline=False)
                else:
                    embed.add_field(name=f"{j + 1}. {song}", value="",inline=False)
            pages.append(embed)
        paginator = Paginator(self.bot)
        await paginator.paginate(context, pages)
    
    @commands.command(name="shuffle", description="Shuffle the queue.")
    async def shuffle(self, context: Context) -> None:
        random.shuffle(self.song_queue)
        embed = discord.Embed(title="Queue Shuffled", description="The queue has been shuffled.", color=discord.Color.green())
        await context.send(embed=embed)
    
    @commands.command(name="remove", description="Remove a song from the queue.")
    async def remove(self, context: Context, index: int) -> None:
        if index < 1 or index > len(self.song_queue):
            embed = discord.Embed(title="Error", description="Invalid index.", color=discord.Color.red())
            return await context.send(embed=embed)
        song = self.song_queue[index - 1]
        self.song_queue.remove(song)
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
