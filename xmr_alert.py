import requests
import time

WALLET_ADDRESS = "4B3WoA2P3fQNancXvdPVvnVcWZfeyC97dRj56pbq6RJdNGS39V4ME4WKHxn7e9KAFeJ87dNxgAdrP8dF5r8bFVxhPDS49gU"
BOT_TOKEN = "your_bot_token_here"
CHAT_ID = "your_chat_id_here"
THRESHOLD = 0.005  # Send alert when balance >= 0.005 XMR

def get_balance():
    url = f"https://supportxmr.com/api/wallet/{WALLET_ADDRESS}"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        balance = data["stats"]["balance"] / 1e12  # convert from atomic units
        return balance
    except Exception as e:
        print("Error checking balance:", e)
        return 0

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=data)

# Run check every 10 minutes
print("🚀 Starting XMR balance watcher...")
while True:
    balance = get_balance()
    print(f"🔍 Current balance: {balance:.12f} XMR")

    if balance >= THRESHOLD:
        send_telegram(f"🔔 Sudip, you reached {balance:.6f} XMR! 🎉 You can withdraw now.")
        break

    time.sleep(600)  # wait 10 mins
