import requests
import os
import csv
from datetime import datetime
import subprocess

# === Config ===
TVL_THRESHOLD = 10_000_000
CATEGORY_FILTER = "Derivatives"
DEFI_LLAMA_URL = "https://api.llama.fi/protocols"
STATE_FILE = "notified_protocols.csv"

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
    with open(STATE_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return {row[0] for row in reader if row}  # first column is protocol name

def save_alerts(protocols):
    with open(STATE_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for name in sorted(protocols):
            writer.writerow([name])
    print("💾 Updated alert state saved.")

    # Commit to GitHub if running in Actions
    if os.getenv("GITHUB_ACTIONS") == "true":
        subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
        subprocess.run(["git", "config", "user.email", "github-actions@github.com"], check=True)
        subprocess.run(["git", "add", STATE_FILE], check=True)
        subprocess.run(["git", "commit", "-m", f"Update alerts {datetime.utcnow().isoformat()}"], check=False)
        subprocess.run(["git", "push"], check=False)

def fetch_protocols():
    """Fetch protocols from DeFiLlama API"""
    try:
        print("🔍 Fetching DeFiLlama protocols...")
        res = requests.get(DEFI_LLAMA_URL)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Error fetching protocols: {e}")
        return []

def check_new_protocols():
    """Check for new protocols crossing the TVL threshold"""
    alerted = load_previous_alerts()
    protocols = fetch_protocols()
    new_alerts = set()
    
    if not protocols:
        print("⚠️ No protocols fetched, exiting")
        return
        
    for protocol in protocols:
        tvl = protocol.get("tvl")
        name = protocol.get("name", "")
        category = protocol.get("category", "")
        
        # Skip if not in our target category
        if category != CATEGORY_FILTER:
            continue
            
        # Skip if TVL is below threshold or not numeric
        if not isinstance(tvl, (int, float)) or tvl < TVL_THRESHOLD:
            continue
            
        # Check if we've already alerted for this protocol
        if name not in alerted:
            msg = f"🚨 New Derivative Protocol Alert!\n" \
                  f"Name: {name}\n" \
                  f"TVL: ${tvl:,.0f}\n" \
                  f"Chain: {protocol.get('chain', 'N/A')}\n" \
                  f"Category: {category}"
            print(msg)
            
            if USE_TELEGRAM:
                send_telegram_message(msg)
                
            new_alerts.add(name)
    
    if new_alerts:
        print(f"🎉 Found {len(new_alerts)} new protocols crossing the threshold!")
        save_alerts(alerted.union(new_alerts))
    else:
        print("✅ No new protocols crossed the threshold")
        
    # Count protocols above threshold
    above_threshold = sum(1 for p in protocols 
                         if p.get("category") == CATEGORY_FILTER 
                         and isinstance(p.get("tvl"), (int, float))
                         and p.get("tvl") >= TVL_THRESHOLD)
    print(f"📊 Total derivatives protocols above ${TVL_THRESHOLD:,}: {above_threshold}")

if __name__ == "__main__":
    check_new_protocols()
