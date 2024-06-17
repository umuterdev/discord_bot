import asyncio
import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import os

# Define intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

# Initialize the bot
bot = commands.Bot(command_prefix="!", intents=intents)

# Specify FFmpeg executable path (replace with your actual path)
ffmpeg_path = r'C:\PATH_PROGRAMS\ffmpeg.exe'  # Example: r'C:\ffmpeg\bin\ffmpeg.exe'

# Configure yt_dlp to use specified FFmpeg path
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'ffmpeg_location': ffmpeg_path
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# Initialize yt_dlp with the specified options
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MusicPlayer:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.current = None
        self.volume = 0.5
        self.play_next_song = asyncio.Event()
        self.position = 0
        self.resuming = False

    async def audio_player_task(self, ctx):
        while True:
            self.play_next_song.clear()
            self.current = await self.queue.get()
            self.position = 0
            self.resuming = False
            self.play_song(ctx)
            await self.play_next_song.wait()

    def play_song(self, ctx):
        if self.resuming:
            ffmpeg_options['options'] = f'-vn -ss {self.position}'
        else:
            ffmpeg_options['options'] = '-vn'
        ctx.voice_client.play(discord.FFmpegPCMAudio(self.current.url, **ffmpeg_options), after=self.toggle_next)
        bot.loop.create_task(ctx.send(f'Now playing: {self.current.title}'))

    def toggle_next(self, error):
        if error:
            print(f'Player error: {error}')
        self.play_next_song.set()

    def add_to_queue(self, player):
        self.queue.put_nowait(player)

    def pause_song(self, ctx):
        if ctx.voice_client.is_playing():
            self.position = ctx.voice_client.source.position
            ctx.voice_client.pause()

    def resume_song(self, ctx):
        if ctx.voice_client.is_paused():
            self.resuming = True
            self.play_song(ctx)

music_player = MusicPlayer()

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.command()
async def join(ctx):
    """Joins a voice channel"""
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel.")
        return

    channel = ctx.message.author.voice.channel
    await channel.connect()

@bot.command()
async def leave(ctx):
    """Leaves the voice channel"""
    if ctx.voice_client:
        await ctx.guild.voice_client.disconnect()
    else:
        await ctx.send("I am not in a voice channel.")

@bot.command()
async def play(ctx, *, url):
    """Plays a file from a URL and queues it if another song is playing"""
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("You are not connected to a voice channel.")
            return

    async with ctx.typing():
        await ctx.send(f'Attempting to play: {url}')
        try:
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            music_player.add_to_queue(player)
            await ctx.send(f'Added to queue: {player.title}')
            if not ctx.voice_client.is_playing():
                bot.loop.create_task(music_player.audio_player_task(ctx))
        except youtube_dl.DownloadError as e:
            await ctx.send(f'Error: {e}')
        except Exception as e:
            await ctx.send(f'An error occurred: {e}')
            print(f'An error occurred: {e}')

@bot.command()
async def stop(ctx):
    """Stops the current song"""
    if ctx.voice_client:
        ctx.voice_client.stop()
    else:
        await ctx.send("I am not in a voice channel.")

@bot.command()
async def pause(ctx):
    """Pauses the current song"""
    music_player.pause_song(ctx)

@bot.command()
async def resume(ctx):
    """Resumes the current song"""
    music_player.resume_song(ctx)

@bot.command()
async def skip(ctx):
    """Skips the current song"""
    if ctx.voice_client:
        ctx.voice_client.stop()
    else:
        await ctx.send("I am not in a voice channel.")

@bot.command()
async def queue(ctx):
    """Displays the current song queue"""
    if music_player.queue.empty():
        await ctx.send("The queue is empty.")
    else:
        queue_list = list(music_player.queue._queue)
        queue_str = "\n".join(f"{idx + 1}. {song.title}" for idx, song in enumerate(queue_list))
        await ctx.send(f"Current queue:\n{queue_str}")

# Run the bot
bot.run('YOUR_BOT_TOKEN')
