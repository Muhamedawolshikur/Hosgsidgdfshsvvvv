#!/usr/bin/env python3
"""
MULTI-VPN DECRYPTOR (Slipnet & NetMod Combined with Flask for Render)
Maintained by: @Moos_Root
"""

import base64
import json
import re
import os
import telebot
import threading
from flask import Flask
from urllib.parse import urlparse, parse_qs, unquote
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

# ==================== FLASK WEB SERVER ====================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly 24/7!"

def run_flask():
    # Render automatically passes the PORT environment variable
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8706781362:AAFWsj1lfyk0PBinFfhli_497-XeAg8D1dA"
# ⚠️ YOUR ADMIN ID IS SET HERE
ADMIN_ID = 8700421304  

bot = telebot.TeleBot(BOT_TOKEN)
USER_DB = "users.txt"

# Crypto Keys
SLIPNET_KEY_HEX = "214f052025b2f949605a5429ec3d5fa80c2022c168ad946e68852d447214dbd3"
SLIPNET_KEY = bytes.fromhex(SLIPNET_KEY_HEX)
SLIPNET_FORMAT_VERSION = 0x01
SLIPNET_IV_LENGTH = 12
SLIPNET_TAG_LENGTH = 16

NETMOD_KEY = base64.b64decode("X25ldHN5bmFfbmV0bW9kXw==")
NETMOD_PREFIXES = [
    "nm-vmess://", "nm-vless://", "nm-dns://",
    "nm-trojan://", "nm-ssh://", "nm-ssr://",
    "nm-ss://", "nm-xray-json://"
]

# ==================== CORE UTILITIES ====================
def save_user(user_id):
    """Saves user ID to a text file for broadcasting."""
    if not os.path.exists(USER_DB):
        with open(USER_DB, "w") as f:
            f.write("")
            
    with open(USER_DB, "r") as f:
        users = f.read().splitlines()
        
    if str(user_id) not in users:
        with open(USER_DB, "a") as f:
            f.write(f"{user_id}\n")

# ==================== SLIPNET DECRYPTION ENGINE ====================
def decrypt_slipnet_data(raw_data: bytes) -> str:
    if len(raw_data) < 1 + SLIPNET_IV_LENGTH + SLIPNET_TAG_LENGTH:
        raise ValueError("Encrypted data too short")
    if raw_data[0] != SLIPNET_FORMAT_VERSION:
        raise ValueError("Unsupported encrypted format version")

    iv = raw_data[1:1 + SLIPNET_IV_LENGTH]
    ciphertext_with_tag = raw_data[1 + SLIPNET_IV_LENGTH:]
    ciphertext = ciphertext_with_tag[:-SLIPNET_TAG_LENGTH]
    tag = ciphertext_with_tag[-SLIPNET_TAG_LENGTH:]

    cipher = AES.new(SLIPNET_KEY, AES.MODE_GCM, nonce=iv)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext.decode("utf-8")

def parse_slipnet_profile(plaintext: str) -> dict:
    parts = plaintext.split("|")
    while len(parts) < 33:
        parts.append("")

    link_parts = parts[:]
    link_parts[31] = "0"
    link_parts[32] = ""
    clean_profile = "|".join(link_parts)

    return {
        "version": parts[0], "tunnel_type": parts[1], "name": parts[2],
        "domain": parts[3], "resolvers": parts[4], "authoritative_mode": parts[5],
        "keepalive": parts[6], "congestion": parts[7], "tcp_port": parts[8],
        "tcp_host": parts[9], "gso": parts[10], "dnstt_key": parts[11],
        "socks_user": parts[12], "socks_pass": parts[13], "ssh_enabled": parts[14],
        "ssh_user": parts[15], "ssh_pass": parts[16], "ssh_port": parts[17],
        "ssh_host": parts[19] if len(parts) > 19 else None,
        "dns_transport": parts[22] if len(parts) > 22 else None,
        "ssh_auth_type": parts[23] if len(parts) > 23 else None,
        "naive_port": parts[28] if len(parts) > 28 else None,
        "naive_user": parts[29] if len(parts) > 29 else None,
        "locked": parts[31] if len(parts) > 31 else None,
        "lock_hash": parts[32] if len(parts) > 32 else None,
        "slipnet_link": "slipnet://" + base64.b64encode(clean_profile.encode()).decode()
    }

def process_slipnet(text: str) -> str:
    lines = re.split(r"\r?\n", text.strip())
    profiles = []
    for line in lines:
        line = line.strip()
        if line.lower().startswith("slipnet-enc://"):
            b64 = line[14:]
            try:
                raw = base64.b64decode(b64)
                plain = decrypt_slipnet_data(raw)
                profile = parse_slipnet_profile(plain)
                profiles.append(profile)
            except Exception:
                continue
    if not profiles:
        return None
    result_dict = {"success": True, "profiles": profiles}
    json_result = json.dumps(result_dict, indent=2, ensure_ascii=False)
    json_safe = json_result.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<pre><code class=\"language-json\">{json_safe}</code></pre>"

# ==================== NETMOD DECRYPTION ENGINE ====================
def decrypt_netmod_aes(ciphertext, key):
    cipher = AES.new(key, AES.MODE_ECB)
    decrypted_text = cipher.decrypt(ciphertext)
    return unpad(decrypted_text, AES.block_size)

def parse_netmod_proxy_string(raw_string):
    try:
        clean_str = raw_string.strip()
        if "://" not in clean_str:
            clean_str = "proxy://" + clean_str
        parsed = urlparse(clean_str)
        queries = parse_qs(parsed.query)
        remark = unquote(parsed.fragment) if parsed.fragment else ""
        user_info = parsed.username if parsed.username else ""
        host = parsed.hostname if parsed.hostname else ""
        port = parsed.port if parsed.port else ""
        
        formatted = ""
        if remark: formatted += f"📌 <b>Name:</b> {remark}\n"
        if parsed.scheme and parsed.scheme != "proxy": formatted += f"🔹 <b>Protocol:</b> {parsed.scheme.upper()}\n"
        if host: formatted += f"🌍 <b>Host/IP:</b> <code>{host}</code>\n"
        if port: formatted += f"🔌 <b>Port:</b> <code>{port}</code>\n"
        if user_info: formatted += f"🔑 <b>ID/User:</b> <code>{user_info}</code>\n"
        if queries:
            formatted += "⚙️ <b>Parameters:</b>\n"
            for k, v in queries.items():
                val = v[0] if v else ""
                formatted += f"   ├── <b>{k}:</b> <code>{unquote(val)}</code>\n"
        return formatted if formatted else f"📝 <b>Raw Config:</b>\n<code>{raw_string}</code>\n"
    except Exception:
        return f"📝 <b>Raw Config:</b>\n<code>{raw_string}</code>\n"

def format_netmod_string(decrypted_string):
    try:
        data = json.loads(decrypted_string)
        formatted_string = ""
        for key, value in data.items():
            if isinstance(value, dict):
                formatted_string += f"📦 <b>[{key}]:</b>\n"
                for inner_key, inner_value in value.items():
                    formatted_string += f"   ├── <b>{inner_key}:</b> <code>{inner_value}</code>\n"
            elif isinstance(value, list):
                for item in value:
                    formatted_string += f"📦 <b>[{key}]:</b>\n"
                    if isinstance(item, dict):
                        for inner_key, inner_value in item.items():
                            formatted_string += f"   ├── <b>{inner_key}:</b> <code>{inner_value}</code>\n"
                    else:
                        formatted_string += f"   ├── {item}\n"
            else:
                formatted_string += f"🔹 <b>{key}:</b> <code>{value}</code>\n"
        return formatted_string
    except json.JSONDecodeError:
        return parse_netmod_proxy_string(decrypted_string)

def process_netmod(text_content):
    lines = re.split(r"\r?\n", text_content.strip())
    results = ""
    success_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        for prefix in NETMOD_PREFIXES:
            if line.lower().startswith(prefix):
                line = line[len(prefix):]
                break
        try:
            decrypted_bytes = decrypt_netmod_aes(base64.b64decode(line), NETMOD_KEY)
            decrypted_string = decrypted_bytes.decode('utf-8', errors="replace")
            results += format_netmod_string(decrypted_string) + "\n" + "─" * 30 + "\n"
            success_count += 1
        except Exception:
            continue
    return results if success_count > 0 else None

# ==================== MASTER ROUTER ====================
def auto_decrypt_handler(text_content):
    """Detects config type and routes to the correct decryption engine."""
    text_lower = text_content.lower()
    
    # 1. Route to Slipnet
    if "slipnet-enc://" in text_lower:
        return process_slipnet(text_content), "slipnet"
        
    # 2. Route to NetMod
    for prefix in NETMOD_PREFIXES:
        if prefix in text_lower or any(line.strip().startswith(prefix) for line in text_content.splitlines()):
            return process_netmod(text_content), "netmod"
            
    # 3. Fallback try (In case prefixes are stripped but content is valid)
    netmod_try = process_netmod(text_content)
    if netmod_try:
        return netmod_try, "netmod"
        
    return None, None

# ==================== TELEGRAM HANDLERS ====================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    save_user(message.chat.id)
    welcome_text = (
        "<b>👋 Welcome to Universal VPN Decryptor Bot!</b>\n\n"
        "Supported formats:\n"
        "🔹 <code>slipnet-enc://</code>\n"
        "🔹 <code>nm-vmess://</code>, <code>nm-vless://</code>, <code>nm-trojan://</code> etc.\n\n"
        "Send your link directly or upload a <code>.txt</code> file."
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="HTML")


@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.chat.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ <b>Unauthorized:</b> Restricted to administrator.", parse_mode="HTML")
        return
    command_text = message.text.replace("/broadcast", "").strip()
    if not command_text:
        bot.send_message(message.chat.id, "⚠️ <b>Usage:</b> <code>/broadcast Your message here</code>", parse_mode="HTML")
        return
    if not os.path.exists(USER_DB):
        bot.send_message(message.chat.id, "❌ No users found.", parse_mode="HTML")
        return
    with open(USER_DB, "r") as f:
        users = f.read().splitlines()
    bot.send_message(message.chat.id, f"📢 Broadcasting to {len(users)} users...", parse_mode="HTML")
    success_count = 0
    for user in users:
        try:
            bot.send_message(user, command_text)
            success_count += 1
        except Exception: pass  
    bot.send_message(message.chat.id, f"✅ <b>Completed:</b> Sent to {success_count}/{len(users)} users.", parse_mode="HTML")


@bot.message_handler(content_types=['document'])
def handle_docs(message):
    save_user(message.chat.id)
    try:
        if message.document.file_name.endswith('.txt'):
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            content = downloaded_file.decode('utf-8')
            
            output, engine = auto_decrypt_handler(content)
            
            if not output:
                bot.send_message(message.chat.id, "❌ No valid Slipnet or NetMod configuration detected in this file.", parse_mode="HTML")
                return

            caption_text = "✅ <b>Decryption Successful!</b>\n\n<b>&lt;/Dec&gt; BY:</b> @Moos_Root"
            
            if len(output) > 4000:
                filename = "Decrypted_Output.txt" if engine == "netmod" else "Decrypted_Result.json"
                clean_file_content = output.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<pre>", "").replace("</pre>", "").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(clean_file_content)
                with open(filename, "rb") as f:
                    bot.send_document(message.chat.id, f, caption=caption_text, parse_mode="HTML")
                os.remove(filename)
            else:
                bot.send_message(message.chat.id, f"{output}\n{caption_text}", parse_mode="HTML")
        else:
            bot.send_message(message.chat.id, "❌ Please upload a valid <code>.txt</code> file.", parse_mode="HTML")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ An error occurred: <code>{str(e)}</code>", parse_mode="HTML")


@bot.message_handler(func=lambda message: True)
def handle_text(message):
    save_user(message.chat.id)
    text = message.text.strip()
    
    output, engine = auto_decrypt_handler(text)
    
    if output:
        caption_text = "✅ <b>Decryption Successful!</b>\n\n<b>&lt;/Dec&gt; BY:</b> @Moos_Root"
        
        if len(output) > 4000:
            filename = "Decrypted_Output.txt" if engine == "netmod" else "Decrypted_Result.json"
            clean_file_content = output.replace("<b>", "").replace("</b>", "").replace("<code>", "").replace("</code>", "").replace("<pre>", "").replace("</pre>", "").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(clean_file_content)
            with open(filename, "rb") as f:
                bot.send_document(message.chat.id, f, caption=caption_text, parse_mode="HTML")
            os.remove(filename)
        else:
            bot.send_message(message.chat.id, f"{output}\n{caption_text}", parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, "❌ Invalid Config. Please send a valid Slipnet or NetMod link.", parse_mode="HTML")


if __name__ == "__main__":
    # Start Flask Web Server in a background thread
    print("🚀 Starting Flask Web Server...")
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # Start Telegram Bot Polling
    print("✨ Universal VPN Bot is securely running and listening...")
    bot.infinity_polling()
