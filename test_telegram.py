import requests

token = "8696491310:AAFtyPpdmE7qJX2c61rPJeDI7gjAlnonazA"
chat_id = "7975792456"

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
    
    
