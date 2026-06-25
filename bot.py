import telebot
from telebot import apihelper, types
import yt_dlp
import os
import time
import re
import subprocess
import json
import threading
from concurrent.futures import ThreadPoolExecutor
import instaloader
import random
import shutil
import urllib.request
from colorama import Fore, Style, init
from PIL import Image

# Initialize Colorama
init(autoreset=True)

# --- 🚀 FORCED DIRECTORY & TEMP FIX ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Dedicated Downloads Directory
TEMP_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(TEMP_DIR, exist_ok=True)

# --- 🔑 YOUR TOKEN ---
BOT_TOKEN = '7798907457:AAHrDbNhK1CvPs9_K5-f_t9XTvl2A3VnPss'

# --- ⚙️ NETWORK CONFIGURATION ---
apihelper.ENABLE_MIDDLEWARE = True
apihelper.SESSION_TIME_TO_LIVE = 5 * 60 

# --- 📂 SETTINGS & TASK MANAGEMENT ---
SETTINGS_FILE = 'group_settings.json'
TASKS_FILE = 'pending_tasks.json'
DEFAULT_EMOJI = "🍉"

# --- 🔒 THREAD LOCKS & CONCURRENCY ---
tasks_lock = threading.Lock()
settings_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=5) # Prevent spam crashes

# --- 📸 INSTALOADER SETUP ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]

L = instaloader.Instaloader(
    download_pictures=True,
    download_videos=True,
    download_video_thumbnails=False,
    download_geotags=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False
)

# --- 🔄 SETTINGS LOGIC (THREAD SAFE) ---
def _read_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except: return {}
    return {}

def load_settings():
    with settings_lock:
        return _read_settings()

def save_setting(chat_id, emoji):
    with settings_lock:
        settings = _read_settings()
        settings[str(chat_id)] = emoji
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f)

def get_emoji(chat_id):
    return load_settings().get(str(chat_id), DEFAULT_EMOJI)

# --- 🔄 PERSISTENCE LOGIC (THREAD SAFE PENDING TASKS FIX) ---
def _read_tasks():
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, 'r') as f:
                return json.load(f)
        except: return {}
    return {}

def load_tasks():
    with tasks_lock:
        return _read_tasks()

def save_task(unique_id, chat_id, url, status_id):
    with tasks_lock:
        tasks = _read_tasks()
        tasks[unique_id] = {"chat_id": chat_id, "url": url, "status_id": status_id}
        with open(TASKS_FILE, 'w') as f:
            json.dump(tasks, f)

def remove_task(unique_id):
    with tasks_lock:
        tasks = _read_tasks()
        if unique_id in tasks:
            del tasks[unique_id]
            with open(TASKS_FILE, 'w') as f:
                json.dump(tasks, f)

def log(message, type="INFO"):
    timestamp = time.strftime("%H:%M:%S")
    color = Fore.GREEN
    if type == "ERROR": color = Fore.RED
    if type == "START": color = Fore.CYAN
    print(f"{color}[{timestamp}] [{type}] {message}")

log("Initializing Ultra-High-Quality GPU System (NVENC HEVC + Smart Attach)...", "START")
bot = telebot.TeleBot(BOT_TOKEN)

# --- 📋 SETUP BOT COMMANDS ---
def setup_bot_commands():
    commands = [
        types.BotCommand("start", "🚀 Start the bot"),
        types.BotCommand("setemoji", "⚙️ Change the hyperlink button style")
    ]
    bot.set_my_commands(commands)
    log("Bot commands updated for suggestions.", "INFO")

setup_bot_commands()
BOT_START_TIME = time.time() + 2

def auto_delete(chat_id, message_id, delay=5):
    time.sleep(delay)
    try: bot.delete_message(chat_id, message_id)
    except: pass

# --- 🛠️ COMMAND HANDLERS ---
@bot.message_handler(commands=['setemoji'])
def set_emoji_command(message):
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Reset to Default (🍉)", callback_data="emoji_reset"))
    markup.add(types.InlineKeyboardButton("Change Emoji", callback_data="emoji_change"))
    bot.send_message(message.chat.id, "⚙️ **Link Button Settings**\nChoose an option below:", 
                     reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("emoji_"))
def handle_emoji_settings(call):
    bot.answer_callback_query(call.id) 
    chat_id = call.message.chat.id
    
    if call.data == "emoji_reset":
        save_setting(chat_id, DEFAULT_EMOJI)
        msg = bot.edit_message_text(f"✅ Emoji reset to {DEFAULT_EMOJI}", chat_id, call.message.message_id)
        threading.Thread(target=auto_delete, args=(chat_id, msg.message_id, 5)).start()
    elif call.data == "emoji_change":
        try: bot.delete_message(chat_id, call.message.message_id)
        except: pass
        msg = bot.send_message(chat_id, "Please send the single emoji or text you want to use for the hyperlink:")
        bot.register_next_step_handler(msg, process_emoji_input, msg.message_id)

def process_emoji_input(message, instruction_msg_id):
    chat_id = message.chat.id
    new_emoji = message.text.strip()
    save_setting(chat_id, new_emoji)
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    try: bot.delete_message(chat_id, instruction_msg_id)
    except: pass
    done_msg = bot.send_message(chat_id, f"✅ Hyperlink button updated to: {new_emoji}")
    threading.Thread(target=auto_delete, args=(chat_id, done_msg.message_id, 5)).start()

# --- 📥 DOWNLOAD & LOSSLESS ENCODING (REELS) ---
def download_video(url, unique_id):
    filename = os.path.join(TEMP_DIR, f"reel_{unique_id}.mp4")
    log(f"📥 Fetching LOSSLESS SOURCE (GPU) for ID: {unique_id}")
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': filename,
        'merge_output_format': 'mp4',
        'postprocessor_args': [
            '-c:v', 'hevc_nvenc', '-rc', 'vbr', '-cq', '22', 
            '-preset', 'p7', '-pix_fmt', 'yuv420p', '-tag:v', 'hvc1', # hvc1 tag strictly required for iOS natively
            '-c:a', 'aac', '-b:a', '192k', '-ar', '48000'            
        ],
        'quiet': True, 'no_warnings': True,
    }

    def attempt_download(options):
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            final_filename = ydl.prepare_filename(info)
            if not final_filename.endswith('.mp4'):
                new_name = os.path.splitext(final_filename)[0] + '.mp4'
                if os.path.exists(final_filename): os.rename(final_filename, new_name)
                final_filename = new_name
            size_mb = os.path.getsize(final_filename) / (1024 * 1024)
            return {'path': final_filename, 'width': info.get('width'), 'height': info.get('height'), 'duration': info.get('duration'), 'size_mb': size_mb, 'url': url}

    try:
        return attempt_download(ydl_opts)
    except Exception as e:
        log(f"⚠️ Initial download failed (Auth Required?): {e}", "ERROR")
        if os.path.exists('cookies.txt'):
            log(f"🍪 Retrying with cookies.txt...", "INFO")
            try:
                ydl_opts['cookiefile'] = 'cookies.txt'
                return attempt_download(ydl_opts)
            except Exception as e2:
                log(f"❌ HQ Error (Even with cookies): {e2}", "ERROR")
                return None
        else:
            log("❌ No cookies.txt found. Cannot fallback.", "ERROR")
            return None

def compress_video_gpu(input_path, start_cq=22):
    output_path = input_path.replace(".mp4", "_compressed.mp4")
    current_cq = start_cq
    while current_cq <= 45:
        log(f"📉 Attempting GPU CQ {current_cq}...")
        cmd = [
            'ffmpeg', '-y', '-vsync', '0', '-hwaccel', 'cuda', '-i', input_path,
            '-c:v', 'hevc_nvenc', '-rc', 'vbr', '-cq', str(current_cq), 
            '-preset', 'p7', '-pix_fmt', 'yuv420p', '-tag:v', 'hvc1', 
            '-c:a', 'copy', output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(output_path):
            size = os.path.getsize(output_path) / (1024 * 1024)
            if size < 49.5: return output_path
        current_cq += 2
    return output_path

def extract_clean_link(text):
    pattern = r'(https?://(?:www\.)?instagram\.com/(?:reel|p|tv)/[a-zA-Z0-9_-]+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None

def extract_pinterest_link(text):
    pattern = r'(https?://(?:www\.)?pinterest\.[a-zA-Z0-9]+/(?:pin/)?\d+/?|https?://pin\.it/[a-zA-Z0-9]+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None

# --- 📸 POST DOWNLOADER (INSTALOADER) ---
def download_post_instaloader(url, unique_id):
    try:
        L.context.user_agent = random.choice(USER_AGENTS)
        shortcode = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
        target_dir = os.path.join(TEMP_DIR, f"post_{unique_id}")
        
        time.sleep(random.uniform(2, 4))
        
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        L.download_post(post, target=target_dir)
        
        media_files = []
        for file in sorted(os.listdir(target_dir)):
            if file.lower().endswith((".jpg", ".jpeg", ".png", ".mp4", ".webp")):
                file_path = os.path.join(target_dir, file)
                
                # Ignore 0-byte files
                if os.path.getsize(file_path) == 0:
                    log(f"Skipping empty file (likely 403 block): {file}", "ERROR")
                    os.remove(file_path)
                    continue
                
                # Convert WebP to JPG on the fly
                if file.lower().endswith(".webp"):
                    try:
                        im = Image.open(file_path).convert("RGB")
                        new_path = file_path.rsplit('.', 1)[0] + ".jpg"
                        im.save(new_path, "jpeg", quality=95, optimize=True)
                        os.remove(file_path) # Clean up the original webp
                        file_path = new_path
                    except Exception as e:
                        log(f"WebP Conversion Error: {e}", "ERROR")
                        continue 
                        
                if file_path.endswith(".mp4"):
                    size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    if size_mb >= 50:
                        file_path = compress_video_gpu(file_path)
                
                # Double check size after potential conversion/compression
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    media_files.append(file_path)
        
        return media_files, target_dir
    except Exception as e:
        log(f"Instaloader Error: {e}", "ERROR")
        return None, None

# --- ⚙️ CORE PROCESSING ENGINE (INSTAGRAM) ---
def process_reel(chat_id, unique_id, clean_url, is_resume=False, old_status_id=None):
    try:
        if is_resume and old_status_id:
            try: bot.delete_message(chat_id, old_status_id)
            except: pass
            
        status_text = "⚡" if not is_resume else "🔄 Resuming..."
        status_msg = bot.send_message(chat_id, status_text)
        save_task(unique_id, chat_id, clean_url, status_msg.message_id)

        if "/p/" in clean_url:
            media_files, folder = download_post_instaloader(clean_url, unique_id)
            if media_files:
                custom_emoji = get_emoji(chat_id)
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(custom_emoji, url=clean_url))
                
                # ATTACH HYPERLINK LOGIC
                if len(media_files) == 1:
                    path = media_files[0]
                    with open(path, 'rb') as f:
                        success = False
                        while not success:
                            try:
                                f.seek(0)
                                if path.endswith(".mp4"):
                                    bot.send_video(chat_id, f, reply_markup=markup)
                                else:
                                    bot.send_photo(chat_id, f, reply_markup=markup)
                                success = True
                            except Exception as e:
                                if "Too Many Requests" in str(e):
                                    match = re.search(r'after (\d+)', str(e))
                                    wait_time = int(match.group(1)) + 1 if match else 5
                                    log(f"Rate limited (Single Send). Waiting {wait_time}s...", "INFO")
                                    time.sleep(wait_time)
                                else:
                                    raise e
                else:
                    media_group = []
                    opened_files = []
                    for i, path in enumerate(media_files):
                        f = open(path, 'rb')
                        opened_files.append(f)
                        caption = f"[{custom_emoji}]({clean_url})" if i == 0 else None
                        if path.endswith(".mp4"):
                            media_group.append(types.InputMediaVideo(f, caption=caption, parse_mode="Markdown"))
                        else:
                            media_group.append(types.InputMediaPhoto(f, caption=caption, parse_mode="Markdown"))
                    
                    chunk_size = 10
                    for i in range(0, len(media_group), chunk_size):
                        chunk = media_group[i:i + chunk_size]
                        success = False
                        while not success:
                            try:
                                for media in chunk:
                                    if hasattr(media.media, 'seek'):
                                        media.media.seek(0)
                                        
                                bot.send_media_group(chat_id, chunk)
                                success = True
                            except Exception as e:
                                if "Too Many Requests" in str(e):
                                    match = re.search(r'after (\d+)', str(e))
                                    wait_time = int(match.group(1)) + 1 if match else 5
                                    log(f"Rate limited (Album Chunk). Waiting {wait_time}s...", "INFO")
                                    time.sleep(wait_time)
                                else:
                                    log(f"Media group send error: {e}", "ERROR")
                                    break 
                        time.sleep(1) 
                    
                    for f in opened_files: f.close()

                try: bot.delete_message(chat_id, status_msg.message_id)
                except: pass
                
                if folder and os.path.exists(folder):
                    shutil.rmtree(folder)
            else:
                raise Exception("Post download failed or files were 0 bytes due to Instagram block.")
        else:
            video_data = download_video(clean_url, unique_id)
            if video_data and os.path.exists(video_data['path']):
                if video_data['size_mb'] >= 50:
                    bot.edit_message_text("⚙️ NVIDIA NVENC: Optimizing...", chat_id, status_msg.message_id)
                    compressed_path = compress_video_gpu(video_data['path'])
                    old_path = video_data['path']
                    video_data['path'] = compressed_path
                    upload_video_to_telegram(chat_id, video_data, status_msg.message_id)
                    if os.path.exists(old_path): os.remove(old_path)
                else:
                    upload_video_to_telegram(chat_id, video_data, status_msg.message_id)
            else:
                raise Exception("Download failed")

        remove_task(unique_id)
            
    except Exception as e:
        log(f"Process Error: {e}", "ERROR")
        try: bot.delete_message(chat_id, status_msg.message_id)
        except: pass
        
        success = False
        while not success:
            try:
                bot.send_message(chat_id, f"🌵\nError: Failed to process.\n{clean_url}")
                success = True
            except Exception as e_msg:
                if "Too Many Requests" in str(e_msg):
                    match = re.search(r'after (\d+)', str(e_msg))
                    time.sleep(int(match.group(1)) + 1 if match else 5)
                else:
                    success = True 
                    
        remove_task(unique_id)

# --- 📌 CORE PROCESSING ENGINE (PINTEREST) ---
def process_pinterest(chat_id, unique_id, clean_url, is_resume=False, old_status_id=None):
    try:
        if is_resume and old_status_id:
            try: bot.delete_message(chat_id, old_status_id)
            except: pass
            
        status_text = "⚡" if not is_resume else "🔄 Resuming..."
        status_msg = bot.send_message(chat_id, status_text)
        save_task(unique_id, chat_id, clean_url, status_msg.message_id)

        log(f"📥 Fetching PINTEREST SOURCE for ID: {unique_id}")
        
        media_path = None
        media_type = None

        # 1. Try yt-dlp to natively extract the media
        ydl_opts = {
            'outtmpl': os.path.join(TEMP_DIR, f"pin_{unique_id}.%(ext)s"),
            'quiet': True, 'no_warnings': True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(clean_url, download=True)
                media_path = ydl.prepare_filename(info)
        except Exception as e:
            log(f"yt-dlp Pinterest fallback triggered: {e}", "INFO")

        # 2. Fallback to direct page scraping for image Pins if yt-dlp didn't catch it
        if not media_path or not os.path.exists(media_path):
            req = urllib.request.Request(clean_url, headers={'User-Agent': random.choice(USER_AGENTS)})
            html = urllib.request.urlopen(req).read().decode('utf-8')
            match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if match:
                img_url = match.group(1)
                img_url = img_url.replace('236x', 'originals').replace('736x', 'originals')
                media_path = os.path.join(TEMP_DIR, f"pin_{unique_id}.jpg")
                urllib.request.urlretrieve(img_url, media_path)

        if media_path and os.path.exists(media_path):
            # 3. Universal Format Standardization
            ext = media_path.split('.')[-1].lower()
            video_extensions = ['mp4', 'webm', 'mov', 'mkv', 'flv', 'avi', 'wmv', 'm4v']
            
            if ext in video_extensions:
                media_type = 'video'
                if ext != 'mp4': # Force to MP4 for perfect Telegram support
                    log(f"🔄 Converting {ext.upper()} to MP4 for universal support...")
                    new_path = media_path.rsplit('.', 1)[0] + ".mp4"
                    subprocess.run([
                        'ffmpeg', '-y', '-i', media_path, 
                        '-c:v', 'hevc_nvenc', '-preset', 'p4', '-cq', '22',
                        '-pix_fmt', 'yuv420p', '-tag:v', 'hvc1',
                        '-c:a', 'aac', '-b:a', '192k', new_path
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(new_path):
                        os.remove(media_path)
                        media_path = new_path
            else:
                media_type = 'image'
                if ext not in ['jpg', 'jpeg', 'png']: # Normalize weird image formats
                    try:
                        im = Image.open(media_path).convert("RGB")
                        new_path = media_path.rsplit('.', 1)[0] + ".jpg"
                        im.save(new_path, "jpeg", quality=95, optimize=True)
                        os.remove(media_path)
                        media_path = new_path
                    except: pass

            # 4. Upload to Telegram
            custom_emoji = get_emoji(chat_id)
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(custom_emoji, url=clean_url))

            with open(media_path, 'rb') as f:
                success = False
                while not success:
                    try:
                        f.seek(0)
                        if media_type == 'video':
                            bot.send_video(chat_id, f, reply_markup=markup, timeout=600)
                        else:
                            bot.send_photo(chat_id, f, reply_markup=markup, timeout=60)
                        success = True
                    except Exception as e:
                        if "Too Many Requests" in str(e):
                            match = re.search(r'after (\d+)', str(e))
                            wait_time = int(match.group(1)) + 1 if match else 5
                            log(f"Rate limited (Pinterest Upload). Waiting {wait_time}s...", "INFO")
                            time.sleep(wait_time)
                        else:
                            try: # Last resort document sending for ungodly formats
                                f.seek(0)
                                bot.send_document(chat_id, f, reply_markup=markup, timeout=600)
                                success = True
                            except: raise e

            try: bot.delete_message(chat_id, status_msg.message_id)
            except: pass
            os.remove(media_path)
        else:
            raise Exception("Failed to locate or download Pinterest media.")

        remove_task(unique_id)
            
    except Exception as e:
        log(f"Pinterest Process Error: {e}", "ERROR")
        try: bot.delete_message(chat_id, status_msg.message_id)
        except: pass
        
        success = False
        while not success:
            try:
                bot.send_message(chat_id, f"🌵\nError: Failed to process Pinterest link.\n{clean_url}")
                success = True
            except Exception as e_msg:
                if "Too Many Requests" in str(e_msg):
                    match = re.search(r'after (\d+)', str(e_msg))
                    time.sleep(int(match.group(1)) + 1 if match else 5)
                else:
                    success = True 
                    
        remove_task(unique_id)

# --- 📩 MESSAGE HANDLING ---
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.date < BOT_START_TIME: return
    text, chat_id = message.text, message.chat.id
    unique_id = f"{chat_id}_{message.message_id}"

    insta_url = extract_clean_link(text)
    pin_url = extract_pinterest_link(text)

    if insta_url:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass
        executor.submit(process_reel, chat_id, unique_id, insta_url)
    
    elif pin_url:
        try: bot.delete_message(chat_id, message.message_id)
        except: pass
        executor.submit(process_pinterest, chat_id, unique_id, pin_url)

def upload_video_to_telegram(chat_id, video_data, status_id):
    try:
        custom_emoji = get_emoji(chat_id)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(custom_emoji, url=video_data['url']))
        with open(video_data['path'], 'rb') as video:
            success = False
            while not success:
                try:
                    video.seek(0)
                    bot.send_video(
                        chat_id, video, 
                        width=video_data.get('width'), height=video_data.get('height'),
                        duration=video_data.get('duration'), supports_streaming=True,
                        reply_markup=markup, timeout=600
                    )
                    success = True
                except Exception as e:
                    if "Too Many Requests" in str(e):
                         match = re.search(r'after (\d+)', str(e))
                         wait_time = int(match.group(1)) + 1 if match else 5
                         log(f"Rate limited (Reel Upload). Waiting {wait_time}s...", "INFO")
                         time.sleep(wait_time)
                    else:
                         raise e
                         
        try: bot.delete_message(chat_id, status_id)
        except: pass
    except Exception as e:
        log(f"Upload failed: {e}", "ERROR")
    
    if os.path.exists(video_data['path']):
        try: os.remove(video_data['path'])
        except: pass

# --- 🛠️ RECOVERY SYSTEM ---
def resume_interrupted_tasks():
    tasks = load_tasks()
    if not tasks: return
    log(f"Found {len(tasks)} unfinished tasks. Resuming...", "START")
    for uid, data in list(tasks.items()):
        url = data['url']
        if "instagram" in url:
            executor.submit(process_reel, data['chat_id'], uid, url, True, data.get('status_id'))
        elif "pinterest" in url or "pin.it" in url:
            executor.submit(process_pinterest, data['chat_id'], uid, url, True, data.get('status_id'))

if __name__ == "__main__":
    # Safe dedicated temp folder clean up
    for item in os.listdir(TEMP_DIR):
        item_path = os.path.join(TEMP_DIR, item)
        try:
            if os.path.isfile(item_path): os.remove(item_path)
            else: shutil.rmtree(item_path)
        except: pass
            
    resume_interrupted_tasks()
    log("Bot Status: LIVE (HEVC + POOL + PINTEREST + ISOLATED FILES) ⚡", "START")
    bot.infinity_polling(timeout=20, long_polling_timeout=10, skip_pending=True)