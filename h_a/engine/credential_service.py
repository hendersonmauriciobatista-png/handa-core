class CredentialService:

    """Compatibilidade estrutural; não é fonte autorizada de credenciais."""

    def save(self, api_key: str, api_secret: str):
        raise RuntimeError(
            "CredentialService não é uma fonte autorizada de credenciais governadas."
        )

    def load(self):
        return None, None
