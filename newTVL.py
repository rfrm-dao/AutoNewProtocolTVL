import requests
import json
import os

# === Config ===
TVL_THRESHOLD = 10_000_000
CATEGORY_FILTER = "Derivatives"
DEFI_LLAMA_URL = "https://api.llama.fi/protocols"
STATE_FILE = "notified_protocols.json"

# Telegram Config
USE_TELEGRAM = True
BOT_TOKEN = "8090344071:AAE_lHRB0FcLMgXQQ2uT91LlrbVIjFv_TKQ"
CHAT_IDS = ["861088602", "1203838173","5158958831"]  # Replace with real IDs


def send_telegram_message(text):
    for chat_id in CHAT_IDS:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        res = requests.post(url, data=payload)
        if res.status_code == 200:
            print(f"✅ Message sent to {chat_id}")
        else:
            print(f"❌ Error sending to {chat_id}: {res.text}")


def load_previous_alerts():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        return set(json.load(f))


def save_alerts(protocols):
    with open(STATE_FILE, "w") as f:
        json.dump(list(protocols), f)


def check_derivatives_tvl():
    try:
        res = requests.get(DEFI_LLAMA_URL)
        res.raise_for_status()
        protocols = res.json()

        alerted = load_previous_alerts()
        new_alerts = set()

        for protocol in protocols:
            tvl = protocol.get("tvl")
            if (
                protocol.get("category") == CATEGORY_FILTER and
                isinstance(tvl, (int, float)) and
                tvl >= TVL_THRESHOLD
            ):
                name = protocol["name"]
                if name not in alerted:
                    new_alerts.add(name)
                    message = f"🚨 {name} just crossed ${tvl:,.0f} TVL!"
                    print(message)
                    if USE_TELEGRAM:
                        send_telegram_message(message)

        # Save new alerts
        all_alerts = alerted.union(new_alerts)
        save_alerts(all_alerts)

        if not new_alerts:
            print("✅ No new protocols crossed the threshold.")

    except Exception as e:
        print("❌ Error:", e)


if __name__ == "__main__":
    check_derivatives_tvl()
