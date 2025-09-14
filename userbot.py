import re
import os
import asyncio
import requests
import subprocess
from pyrogram import Client, filters
from pyrogram.types import Message



API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
SESSION_STRING = os.getenv('SESSION_STRING')


DOWNLOADS_DIR = "downloads"
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# Prefer 480p quality for m3u8 by default
PREFERRED_QUALITY = "480p"

app = Client(
    session_string=SESSION_STRING,
    api_id=API_ID,
    api_hash=API_HASH,
    name="userbot"
)

async def download_file(url, filename):
    # Simple direct download (pdf/mp4)
    filepath = os.path.join(DOWNLOADS_DIR, filename)
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return filepath
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None

async def download_m3u8(url, filename):
    # Fetch master playlist, parse, select preferred quality and download
    try:
        r = requests.get(url)
        r.raise_for_status()
        base_url = url.rsplit('/', 1)[0] + '/'
        content = r.text

        # Find all stream URLs and qualities
        matches = re.findall(r'#EXT-X-STREAM-INF:.*\\n(.*)', content)
        selected_url = url  # fallback: full master playlist

        # Select preferred quality stream
        for stream_url in matches:
            if PREFERRED_QUALITY in stream_url:
                selected_url = base_url + stream_url
                break
        
        # Download with ffmpeg
        filepath = os.path.join(DOWNLOADS_DIR, filename)
        cmd = [
            'ffmpeg', '-y',
            '-i', selected_url,
            '-c', 'copy',
            '-bsf:a', 'aac_adtstoasc',
            filepath
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode == 0:
            return filepath
        else:
            print(f"FFmpeg error: {proc.stderr}")
            return None
    except Exception as e:
        print(f"Error downloading m3u8: {e}")
        return None

@app.on_message(filters.command("dl") & filters.group & filters.me)
async def on_dl_command(client: Client, message: Message):
    # Expected format: /dl [URL] FILENAME
    text = message.text or ""
    match = re.match(r'/dl\\s+\\[(.*?)\\]\\s+(.*)', text, re.IGNORECASE)
    if not match:
        await message.reply_text("Usage: /dl [URL] FILENAME")
        return

    url = match.group(1)
    filename = match.group(2).strip()

    await message.reply_text(f"Downloading: {url} as {filename} ...")

    # Decide by extension if m3u8 or direct file
    if url.endswith('.m3u8'):
        local_file = await download_m3u8(url, filename)
    elif any(url.lower().endswith(ext) for ext in ['.mp4', '.pdf']):
        local_file = await download_file(url, filename)
    else:
        await message.reply_text("Unsupported file type or URL")
        return

    if not local_file or not os.path.exists(local_file):
        await message.reply_text("Download failed.")
        return

    # Upload with caption = filename
    try:
        if local_file.endswith(".mp4"):
            await client.send_video(message.chat.id, local_file, caption=filename)
        elif local_file.endswith(".pdf"):
            await client.send_document(message.chat.id, local_file, caption=filename)
        else:
            await client.send_document(message.chat.id, local_file, caption=filename)
        await message.reply_text("Upload complete.")
    except Exception as e:
        await message.reply_text(f"Upload failed: {e}")
    finally:
        # Cleanup local file
        try:
            os.remove(local_file)
        except:
            pass

app.run()
