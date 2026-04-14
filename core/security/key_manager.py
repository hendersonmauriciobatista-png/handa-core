class KeyManager:
    """
    Gerenciador de chaves — H&A
    Controle lógico de conexão / desconexão
    """

    def __init__(self):
        self.api_key = None
        self.api_secret = None
        self.keys_loaded = False

    def connect_keys(self, api_key: str, api_secret: str) -> bool:
        if not api_key or not api_secret:
            return False

        # Validação mínima (LIVE real pode validar via API depois)
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.keys_loaded = True

        return True

    def disconnect_keys(self):
        self.api_key = None
        self.api_secret = None
        self.keys_loaded = False
