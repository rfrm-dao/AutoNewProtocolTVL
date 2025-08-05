import requests
import json
import os
from datetime import datetime

# === Config ===
TVL_THRESHOLD = 10_000_000
CATEGORY_FILTER = "Derivatives"
DEFI_LLAMA_URL = "https://api.llama.fi/protocols"
STATE_FILE = "notified_protocols.json"

# === Telegram Config ===
USE_TELEGRAM = True
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")

# === Validate Telegram Settings ===
if USE_TELEGRAM:
    if not BOT_TOKEN or not CHAT_IDS or CHAT_IDS == [""]:
        print("❌ Telegram configuration is missing.")
        USE_TELEGRAM = False


def send_telegram_message(text):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id.strip(), "text": text}
        try:
            res = requests.post(url, data=payload)
            if res.status_code == 200:
                print(f"✅ Message sent to {chat_id}")
            else:
                print(f"❌ Error sending to {chat_id}: {res.text}")
        except Exception as e:
            print(f"❌ Exception while sending to {chat_id}: {e}")


def load_previous_alerts():
    if not os.path.exists(STATE_FILE):
        print("ℹ️ No existing alert state found.")
        return set()
    with open(STATE_FILE, "r") as f:
        print("📁 Loaded previous alert state.")
        return set(json.load(f))


def save_alerts(protocols):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(list(protocols)), f, indent=2)
        print("💾 Updated alert state saved.")


def check_derivatives_tvl():
    try:
        print("🔍 Fetching DeFiLlama protocols...")
        res = requests.get(DEFI_LLAMA_URL)
        res.raise_for_status()
        protocols = res.json()

        alerted = load_previous_alerts()
        new_alerts = set()

        for protocol in protocols:
            tvl = protocol.get("tvl")
            name = protocol.get("name", "")
            if (
                protocol.get("category") == CATEGORY_FILTER
                and isinstance(tvl, (int, float))
                and tvl >= TVL_THRESHOLD
            ):
                if name not in alerted:
                    msg = f"🚨 {name} just crossed ${tvl:,.0f} TVL!"
                    print(msg)
                    if USE_TELEGRAM:
                        send_telegram_message(msg)
                    new_alerts.add(name)

        # Save updated alert state
        all_alerts = alerted.union(new_alerts)
        save_alerts(all_alerts)

        if not new_alerts:
            print("✅ No new protocols crossed the threshold.")

    except Exception as e:
        print("❌ Error:", e)


if __name__ == "__main__":
    check_derivatives_tvl()
