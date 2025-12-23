import requests
import time
from datetime import datetime
import urllib3
import os

# Disable warnings for verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8532475060:AAHqNAMopq_3YCG8poKJJJ0u8_mvaYjMVNI"
CHAT_ID = "6086541776"

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Default settings
sleep_duration = 60       # Default duration in seconds
only_show_found = False   # False = Mode All, True = Mode Found Only
running = False
last_update_id = None
last_check_time = 0       # Timestamp of the last check

# --- VFS LOGIC ---
def checkForTCF(idAntenne):
    url = "https://forms.vfsglobal.com.dz/IFAL/api/allowedDate/"
    headers = {
        "Accept": "*/*",
        "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": "https://forms.vfsglobal.com.dz",
        "Referer": "https://forms.vfsglobal.com.dz/IFAL/dash",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    }
    
    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "session_id": "1117342",
                "session_token": "c4e88ffb566bfd4094373ea0ffae0185",
                "vac_id": idAntenne,
                "category_id": "1"
            },
            verify=False,
            timeout=15
        )
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def format_telegram_message(response, place):
    """
    Returns a tuple: (message_string, found_boolean)
    found_boolean is True if a date is found, False otherwise.
    """
    message = f"📍 Location: {place}\n"
    found_slots = False

    if not isinstance(response, dict) or "error" in response:
        return f"📍 Location: {place}\n⚠️ Error connecting to server", False

    # Check valid status and data existence
    if response.get("status") != 1 or not response.get("datas"):
        message += "❌ No appointment slots available."
        return message, False

    # Loop through datas
    for item in response["datas"]:
        slot_date = item.get("slot_date")
        if slot_date:
            try:
                formatted_date = datetime.strptime(slot_date, "%Y-%m-%d").strftime("%d %b %Y")
                message += f"✅ Available date: {formatted_date}\n"
                found_slots = True
            except ValueError:
                message += f"⚠️ Invalid date format: {slot_date}\n"
        else:
            message += "⚠️ Date missing in response\n"

    return message, found_slots

# --- TELEGRAM LOGIC ---

def send_message(text):
    try:
        requests.post(
            f"{API_URL}/sendMessage",
            data={"chat_id": CHAT_ID, "text": text},
            timeout=10
        )
    except Exception as e:
        print(f"Failed to send message: {e}")

def get_updates():
    global last_update_id
    params = {"timeout": 10} # Long polling
    if last_update_id:
        params["offset"] = last_update_id + 1

    try:
        r = requests.get(f"{API_URL}/getUpdates", params=params, timeout=20).json()
        return r.get("result", [])
    except Exception:
        return []

# --- MAIN LOOP ---

print("Bot is running...")

while True:
    # 1. Process Telegram Commands
    updates = get_updates()

    for update in updates:
        last_update_id = update["update_id"]

        if "message" in update:
            text = update["message"].get("text", "").strip()
            
            # Start / Stop
            if text == "/start":
                running = True
                send_message(f"✅ STARTED\nRate: {sleep_duration}s\nMode: {'Found Only' if only_show_found else 'All Info'}")
            
            elif text == "/stop":
                running = False
                send_message("⛔ STOPPED")

            # Set Sleep Duration (e.g., /sleep 30)
            elif text.startswith("/sleep"):
                try:
                    parts = text.split()
                    if len(parts) > 1:
                        new_time = int(parts[1])
                        if new_time > 0:
                            sleep_duration = new_time
                            send_message(f"⏱ Sleep duration set to {sleep_duration} seconds.")
                        else:
                            send_message("⚠️ Time must be greater than 0.")
                    else:
                        send_message("⚠️ Usage: /sleep 60")
                except ValueError:
                    send_message("⚠️ Please provide a valid number.")

            # Set Mode (e.g., /mode all or /mode found)
            elif text.startswith("/mode"):
                parts = text.split()
                if len(parts) > 1:
                    mode = parts[1].lower()
                    if mode == "found":
                        only_show_found = True
                        send_message("🔕 Mode set to: FOUND ONLY (Silent if empty)")
                    elif mode == "all":
                        only_show_found = False
                        send_message("🔔 Mode set to: ALL (Verbose)")
                    else:
                        send_message("⚠️ Usage: /mode all OR /mode found")

    # 2. Check for Appointments (Non-blocking timer)
    if running:
        current_time = time.time()
        # Only check if enough time has passed since the last check
        if current_time - last_check_time > sleep_duration:
            
            # Check Alger
            msg_alg, found_alg = format_telegram_message(checkForTCF("1"), "Alger")
            
            # Check Oran
            msg_oran, found_oran = format_telegram_message(checkForTCF("2"), "Oran")

            # Combine messages into one string
            # We send if:
            # 1. Mode is 'All' (not only_show_found)
            # 2. OR if ANY date was found in either city (found_alg or found_oran)
            if not only_show_found or (found_alg or found_oran):
                combined_msg = f"{msg_alg}\n------------------\n{msg_oran}"
                send_message(combined_msg)

            # Update the last check time
            last_check_time = time.time()

    # Small sleep to prevent high CPU usage, but keep bot responsive to commands
    time.sleep(1)
