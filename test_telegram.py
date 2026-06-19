import requests
import os

token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

url = f"https://api.telegram.org/bot{token}/sendMessage"

response = requests.post(
    url,
    json={
        "chat_id": chat_id,
        "text": "🚀 Teste H&A Telegram OK"
    },
    timeout=10
)

print("STATUS:", response.status_code)
print("RESPOSTA:", response.text)
    
    
