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
REPO_BRANCH = "main"  # Change to your default branch if different

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
    """Load previously alerted protocols from state file"""
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
    """Load historical protocol data from CSV"""
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
                    "category": row["category"],
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"]
                }
        print(f"ℹ️ Loaded {len(history)} protocols from history")
        return history
    except Exception as e:
        print(f"❌ Error loading history file: {e}")
        return {}

def save_protocol_history(history):
    """Save protocol history to CSV"""
    try:
        with open(HISTORY_FILE, "w", newline="", encoding="utf-8") as f:
            fieldnames = ["name", "tvl", "chain", "category", "first_seen", "last_seen"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for name, data in history.items():
                writer.writerow({
                    "name": name,
                    "tvl": data["tvl"],
                    "chain": data["chain"],
                    "category": data["category"],
                    "first_seen": data["first_seen"],
                    "last_seen": data["last_seen"]
                })
        print(f"💾 Saved {len(history)} protocols to history")
        return True
    except Exception as e:
        print(f"❌ Error saving history file: {e}")
        return False

def save_alerts(protocols):
    """Save alerted protocols to state file"""
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
    """Commit changes to GitHub if running in Actions"""
    if os.getenv("GITHUB_ACTIONS") != "true":
        print("ℹ️ Not in GitHub Actions - skipping commit")
        return False
        
    try:
        # Configure git
        subprocess.run(["git", "config", "--global", "user.name", "github-actions"], check=True)
        subprocess.run(["git", "config", "--global", "user.email", "github-actions@github.com"], check=True)
        
        # Add files
        subprocess.run(["git", "add", STATE_FILE, HISTORY_FILE], check=True)
        
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not status.stdout.strip():
            print("ℹ️ No changes to commit")
            return False
            
        # Commit and push
        commit_message = f"Update protocol data {datetime.utcnow().isoformat()}"
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", f"HEAD:{REPO_BRANCH}"], check=True)
        print("🚀 Changes pushed to GitHub")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {e}")
        print(f"Command: {e.cmd}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False
    except Exception as e:
        print(f"❌ Error committing to GitHub: {e}")
        return False

def fetch_protocols():
    """Fetch protocols from DeFiLlama API"""
    try:
        print("🔍 Fetching DeFiLlama protocols...")
        res = requests.get(DEFI_LLAMA_URL, timeout=30)
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error fetching protocols: {e}")
    except Exception as e:
        print(f"❌ Error fetching protocols: {e}")
    return []

def check_new_protocols():
    """Check for new protocols crossing the TVL threshold"""
    alerted = load_previous_alerts()  # already-called protocols
    history = load_protocol_history()
    protocols = fetch_protocols()
    new_alerts = set()
    current_time = datetime.utcnow().isoformat()

    if not protocols:
        print("⚠️ No protocols fetched, exiting")
        return False

    # Update history with current data
    for protocol in protocols:
        name = protocol.get("name", "").strip()
        if not name:
            continue

        tvl = protocol.get("tvl")
        category = protocol.get("category", "")
        chain = protocol.get("chain", "N/A")

        if category != CATEGORY_FILTER:
            continue
        if not isinstance(tvl, (int, float)) or tvl < TVL_THRESHOLD:
            continue

        # Update existing history record or add new
        if name in history:
            history[name]["tvl"] = tvl
            history[name]["last_seen"] = current_time
        else:
            history[name] = {
                "tvl": tvl,
                "chain": chain,
                "category": category,
                "first_seen": current_time,
                "last_seen": current_time
            }

        # Alert only if this protocol hasn't been called before
        if name not in alerted:
            msg = f"🚨 New Derivative Protocol Alert!\n" \
                  f"Name: {name}\n" \
                  f"TVL: ${tvl:,.0f}\n" \
                  f"Chain: {chain}\n" \
                  f"Category: {category}"
            print(msg)

            if USE_TELEGRAM:
                send_telegram_message(msg)

            new_alerts.add(name)
            alerted.add(name)  # add to alerted list immediately

    # Save updated history and alert state
    history_saved = save_protocol_history(history)
    alerts_saved = save_alerts(alerted)

    if new_alerts:
        print(f"🎉 Found {len(new_alerts)} new protocols crossing the threshold!")
    else:
        print("✅ No new protocols crossed the threshold")

    # Commit to GitHub
    commit_success = commit_to_github()

    # Stats
    above_threshold = sum(1 for p in protocols
                          if p.get("category") == CATEGORY_FILTER
                          and isinstance(p.get("tvl"), (int, float))
                          and p.get("tvl") >= TVL_THRESHOLD)
    print(f"📊 Total derivatives protocols above ${TVL_THRESHOLD:,}: {above_threshold}")

    return history_saved and alerts_saved and commit_success
        
    # Update history with current data
    for protocol in protocols:
        name = protocol.get("name", "")
        if not name:
            continue
            
        tvl = protocol.get("tvl")
        category = protocol.get("category", "")
        chain = protocol.get("chain", "N/A")
        
        # Skip if not in our target category
        if category != CATEGORY_FILTER:
            continue
            
        # Skip if TVL is below threshold or not numeric
        if not isinstance(tvl, (int, float)) or tvl < TVL_THRESHOLD:
            continue
            
        # Update protocol history
        if name in history:
            # Update existing entry
            history[name]["tvl"] = tvl
            history[name]["last_seen"] = current_time
        else:
            # Add new entry
            history[name] = {
                "tvl": tvl,
                "chain": chain,
                "category": category,
                "first_seen": current_time,
                "last_seen": current_time
            }
            
            # Check if we need to alert
            if name not in alerted:
                msg = f"🚨 New Derivative Protocol Alert!\n" \
                      f"Name: {name}\n" \
                      f"TVL: ${tvl:,.0f}\n" \
                      f"Chain: {chain}\n" \
                      f"Category: {category}"
                print(msg)
                
                if USE_TELEGRAM:
                    send_telegram_message(msg)
                    
                new_alerts.add(name)
    
    # Save data
    history_saved = save_protocol_history(history)
    alerts_saved = True
    
    if new_alerts:
        print(f"🎉 Found {len(new_alerts)} new protocols crossing the threshold!")
        alerts_saved = save_alerts(alerted.union(new_alerts))
    else:
        print("✅ No new protocols crossed the threshold")
        
    # Commit changes to GitHub
    commit_success = commit_to_github()
    
    # Generate summary statistics
    above_threshold = sum(1 for p in protocols 
                         if p.get("category") == CATEGORY_FILTER 
                         and isinstance(p.get("tvl"), (int, float))
                         and p.get("tvl") >= TVL_THRESHOLD)
    print(f"📊 Total derivatives protocols above ${TVL_THRESHOLD:,}: {above_threshold}")
    
    return history_saved and alerts_saved and commit_success

if __name__ == "__main__":
    success = check_new_protocols()
    if not success:
        print("❌ Script completed with errors")
        sys.exit(1)
    print("✅ Script completed successfully")
