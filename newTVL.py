import requests
import os
import csv
from datetime import datetime
import subprocess
import sys

# === Config ===
TVL_THRESHOLD = 10_000_000
CATEGORY_FILTER = "Derivatives"
DEFI_LLAMA_URL = "https://api.llama.fi/protocols"
STATE_FILE = "notified_protocols.csv"
HISTORY_FILE = "protocol_history.csv"
REPO_BRANCH = "main"

# === Telegram Config ===
USE_TELEGRAM = True
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").split(",")

if USE_TELEGRAM and (not BOT_TOKEN or not CHAT_IDS or CHAT_IDS == [""]):
    print("❌ Telegram configuration is missing.")
    USE_TELEGRAM = False

def send_telegram_message(text):
    for chat_id in CHAT_IDS:
        try:
            res = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": chat_id.strip(), "text": text}
            )
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
    try:
        with open(STATE_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            return {row[0] for row in reader if row}
    except Exception as e:
        print(f"❌ Error loading state file: {e}")
        return set()

def load_protocol_history():
    history = {}
    if not os.path.exists(HISTORY_FILE):
        print("ℹ️ No protocol history file found.")
        return history
    try:
        with open(HISTORY_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                history[row["name"]] = {
                    "tvl": float(row["tvl"]),
                    "chain": row["chain"],
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"]
                }
        print(f"ℹ️ Loaded {len(history)} protocols from history")
    except Exception as e:
        print(f"❌ Error loading history file: {e}")
    return history

def save_protocol_history(history):
    try:
        with open(HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["name", "tvl", "chain", "first_seen", "last_seen"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for name, data in history.items():
                writer.writerow({
                    "name": name,
                    "tvl": data["tvl"],
                    "chain": data["chain"],
                    "first_seen": data["first_seen"],
                    "last_seen": data["last_seen"]
                })
        print(f"💾 Saved {len(history)} protocols to history")
        return True
    except Exception as e:
        print(f"❌ Error saving history file: {e}")
        return False

def save_alerts(protocols):
    try:
        with open(STATE_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for name in sorted(protocols):
                writer.writerow([name])
        print("💾 Updated alert state saved")
        return True
    except Exception as e:
        print(f"❌ Error saving state file: {e}")
        return False

def commit_to_github():
    if os.getenv("GITHUB_ACTIONS") != "true":
        print("ℹ️ Not in GitHub Actions - skipping commit")
        return False
    try:
        subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)
        subprocess.run(["git", "add", STATE_FILE, HISTORY_FILE], check=True)
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            print("ℹ️ No changes to commit")
            return False
        commit_message = f"Update protocol data {datetime.utcnow().isoformat()}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", f"HEAD:{REPO_BRANCH}"], check=True)
        print("🚀 Changes pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {e}\nCommand: {e.cmd}\nOutput: {e.stdout}\nError: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Error committing to GitHub: {e}")
        return False

def fetch_protocols():
    try:
        print("🔍 Fetching DeFiLlama protocols...")
        res = requests.get(DEFI_LLAMA_URL, timeout=30)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"❌ Error fetching protocols: {e}")
        return []

def check_new_protocols():
    alerted = load_previous_alerts()
    history = load_protocol_history()
    protocols = fetch_protocols()
    new_alerts = set()
    current_time = datetime.utcnow().isoformat()

    if not protocols:
        print("⚠️ No protocols fetched, exiting")
        return False

    for protocol in protocols:
        name = protocol.get("name", "").strip()
        if not name:
            continue
        tvl = protocol.get("tvl")
        chain = protocol.get("chain", "N/A")

        if name in history:
            history[name]["tvl"] = tvl
            history[name]["last_seen"] = current_time
        else:
            history[name] = {"tvl": tvl, "chain": chain, "first_seen": current_time, "last_seen": current_time}

        if name not in alerted:
            msg = (
                f"🚨 New Derivative Protocol Alert!\n"
                f"Name: {name}\nTVL: ${tvl:,.0f}\nChain: {chain}\n"
            )
            print(msg)
            if USE_TELEGRAM:
                send_telegram_message(msg)
            new_alerts.add(name)
            alerted.add(name)

    history_saved = save_protocol_history(history)
    alerts_saved = save_alerts(alerted)
    if new_alerts:
        print(f"🎉 Found {len(new_alerts)} new protocols crossing the threshold!")
    else:
        print("✅ No new protocols crossed the threshold")

    commit_success = commit_to_github()

    above_threshold = sum(
        1 for p in protocols
           print(f"📊 Total derivatives protocols above ${TVL_THRESHOLD:,}: {above_threshold}")

    return history_saved and alerts_saved and commit_success

if __name__ == "__main__":
    success = check_new_protocols()
    if not success:
        print("❌ Script completed with errors")
        sys.exit(1)
    print("✅ Script completed successfully")
