# Tema visual central do H&A Desktop
# Modo DEV — simples, estável, legível

# =====================================================
# FUNDOS
# =====================================================

# Fundo geral da aplicação
BG_MAIN = "white"

# Fundo de painéis (slots, telemetria, histórico)
BG_PANEL = "#f2f2f2"

# Slots usam o mesmo fundo de painel
BG_SLOT = BG_PANEL

# Slot ativo (ligeiramente mais escuro para destaque)
BG_SLOT_ACTIVE = "#e6e6e6"


# =====================================================
# TEXTO
# =====================================================

# Texto principal
FG_MAIN = "black"

# Texto secundário / discreto
FG_MUTED = "#333333"

# Alias de compatibilidade
FG_TEXT = FG_MAIN


# =====================================================
# BORDAS / DIVISÕES
# =====================================================

# Bordas sutis (visíveis em fundo claro)
BORDER = "#c0c0c0"


# =====================================================
# ACENTOS (STATUS / TELEMETRIA)
# =====================================================

# Verde — atividade, ok, progresso positivo
ACCENT_OK = "#2e7d32"

# Amarelo — latência, alerta, atenção
ACCENT_WARN = "#f9a825"

# Vermelho — erro, crítico
ACCENT_ERROR = "#c62828"


# =====================================================
# FONTES (PADRÃO)
# =====================================================

FONT_SMALL = ("Segoe UI", 8)
FONT_NORMAL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI", 9, "bold")

def apply_theme(root):
    """
    Aplica o tema base do H&A Desktop.
    Versão DEV — simples e estável.
    """
    root.configure(bg=BG_MAIN)
