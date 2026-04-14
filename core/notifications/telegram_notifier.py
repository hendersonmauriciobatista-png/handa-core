import requests


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def send(self, message: str):
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
            }
            requests.post(self.url, json=payload, timeout=5)
        except Exception as e:
            print(f"[TELEGRAM ERROR] {e}")