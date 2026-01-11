import os
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_alert(text="⚠️ Patient fall detected! Immediate attention required!"):
    if not BOT_TOKEN or not CHAT_ID:
        print("[alert] ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set in environment variables.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}

    try:
        response = requests.post(url, data=payload, timeout=8)
        print(f"[alert] HTTP {response.status_code} - {response.text}")
        if response.status_code == 200:
            print("[alert] Telegram alert sent successfully!")
            return True
        else:
            print("[alert] Telegram API returned error.")
            return False
    except Exception as e:
        print("[alert] Exception while sending Telegram alert:", e)
        return False
