import json
import os


CREDENTIAL_PATH = "h_a/storage/credentials.json"


class CredentialService:

    def save(self, api_key: str, api_secret: str):

        os.makedirs("h_a/storage", exist_ok=True)

        data = {
            "api_key": api_key,
            "api_secret": api_secret
        }

        with open(CREDENTIAL_PATH, "w") as f:
            json.dump(data, f)

    def load(self):

        if not os.path.exists(CREDENTIAL_PATH):
            return None, None

        with open(CREDENTIAL_PATH, "r") as f:
            data = json.load(f)

        return data.get("api_key"), data.get("api_secret")
