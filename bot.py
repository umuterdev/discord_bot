import asyncio
import discord
from discord.ext import commands
import yt_dlp as youtube_dl

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

    async def audio_player_task(self, ctx):
        while True:
            self.play_next_song.clear()
            self.current = await self.queue.get()
            ctx.voice_client.play(self.current, after=lambda e: self.play_next_song.set())
            await ctx.send(f'Now playing: {self.current.title}')
            await self.play_next_song.wait()

    def add_to_queue(self, player):
        self.queue.put_nowait(player)

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
    if ctx.voice_client:
        ctx.voice_client.pause()
    else:
        await ctx.send("I am not in a voice channel.")

@bot.command()
async def resume(ctx):
    """Resumes the current song"""
    if ctx.voice_client:
        ctx.voice_client.resume()
    else:
        await ctx.send("I am not in a voice channel.")

@bot.command()
async def skip(ctx):
    """Skips the current song"""
    if ctx.voice_client:
        ctx.voice_client.stop()
    else:
        await ctx.send("I am not in a voice channel.")

# Run the bot
bot.run('YOUR_BOT_TOKEN')
