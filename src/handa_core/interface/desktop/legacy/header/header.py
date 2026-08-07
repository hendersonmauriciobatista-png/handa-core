import tkinter as tk
import threading


class HeaderArea(tk.Frame):
    """
    Header H&A — UI PURA + CONTROLE
    Painel de controle da UI (não executa trade, não decide lógica)
    """

    BG = "#1e1e1e"
    FG = "#dddddd"
    GREEN = "#2ecc71"
    RED = "#e53935"
    YELLOW = "#f1c40f"
    BLUE = "#1565C0"
    GRAY = "#777777"

    STATES = ["DISCONNECTED", "CONNECTING", "CONNECTED", "ERROR"]

    def __init__(self, master, auto_loop, slot_controller, core=None):
        super().__init__(master, bg=self.BG, height=48)
        self.pack_propagate(False)

        # dependências (injeção)
        self.auto_loop = auto_loop
        self.slot_controller = slot_controller
        self.core = core  # core do H&A (injeção, não import direto)

        # estados
        self.mode = "MOCK"
        self.auto_running = False
        self.connection_state = "DISCONNECTED"

        # variáveis
        self.api_key_var = tk.StringVar()
        self.secret_key_var = tk.StringVar()

        self._build_ui()
        self._set_state("DISCONNECTED")

    # =====================================================
    # UI
    # =====================================================

    def _build_ui(self):
        container = tk.Frame(self, bg=self.BG)
        container.pack(fill="both", expand=True, padx=10)

        # MODE
        self.mock_btn = tk.Button(
            container, text="MOCK",
            bg=self.BLUE, fg="white",
            font=("Segoe UI", 9, "bold"),
            width=6, command=lambda: self._set_mode("MOCK")
        )
        self.mock_btn.pack(side="left")

        self.live_btn = tk.Button(
            container, text="LIVE",
            bg="#2a2a2a", fg="#aaaaaa",
            font=("Segoe UI", 9, "bold"),
            width=6, command=lambda: self._set_mode("LIVE")
        )
        self.live_btn.pack(side="left", padx=(4, 14))

        # API KEY
        tk.Label(container, text="API KEY", bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))

        self.api_entry = tk.Entry(
            container,
            width=22,
            font=("Consolas", 8),
            textvariable=self.api_key_var
        )
        self.api_entry.pack(side="left", padx=(0, 10))
        self._bind_context_menu(self.api_entry)

        # SECRET KEY
        tk.Label(container, text="SECRET KEY", bg=self.BG, fg=self.FG,
                 font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 4))

        self.secret_entry = tk.Entry(
            container,
            width=22,
            font=("Consolas", 8),
            show="•",
            textvariable=self.secret_key_var
        )
        self.secret_entry.pack(side="left", padx=(0, 10))
        self._bind_context_menu(self.secret_entry)

        # CONECTAR
        self.connect_btn = tk.Button(
            container, text="Conectar",
            font=("Segoe UI", 8),
            command=self._handle_connect
        )
        self.connect_btn.pack(side="left", padx=(0, 6))

        self.conn_status = tk.Label(
            container, text="Desconectado",
            bg=self.BG, fg=self.RED,
            font=("Segoe UI", 8, "bold")
        )
        self.conn_status.pack(side="left", padx=(0, 16))

        # AUTO
        self.auto_btn = tk.Button(
            container, text="AUTO OFF",
            font=("Segoe UI", 8, "bold"),
            bg="#2a2a2a", fg="#cccccc",
            command=self._toggle_auto
        )
        self.auto_btn.pack(side="right")

    # =====================================================
    # MODE
    # =====================================================

    def _set_mode(self, mode):
        self.mode = mode
        if mode == "MOCK":
            self.mock_btn.config(bg=self.BLUE, fg="white")
            self.live_btn.config(bg="#2a2a2a", fg="#aaaaaa")
        else:
            self.live_btn.config(bg="#C62828", fg="white")
            self.mock_btn.config(bg="#2a2a2a", fg="#aaaaaa")

    # =====================================================
    # CONNECTION
    # =====================================================

    def _handle_connect(self):
        if self.connection_state == "CONNECTED":
            self._set_state("DISCONNECTED")
            return

        self._set_state("CONNECTING")

        api = self.api_key_var.get().strip()
        secret = self.secret_key_var.get().strip()

        threading.Thread(
            target=self._validate_connection,
            args=(api, secret),
            daemon=True
        ).start()

    def _validate_connection(self, api, secret):
        try:
            if not api or not secret:
                raise Exception("Chaves vazias")

            # validação isolada no core
            if self.core:
                ok = self.core.validate_keys(api, secret)
            else:
                ok = True  # MOCK / fallback

            if ok:
                self.after(0, lambda: self._set_state("CONNECTED"))
            else:
                self.after(0, lambda: self._set_state("ERROR"))

        except Exception:
            self.after(0, lambda: self._set_state("ERROR"))

    def _set_state(self, state):
        self.connection_state = state

        if state == "DISCONNECTED":
            self.connect_btn.config(text="Conectar")
            self.conn_status.config(text="Desconectado", fg=self.RED)

        elif state == "CONNECTING":
            self.connect_btn.config(text="Conectando...")
            self.conn_status.config(text="Conectando...", fg=self.YELLOW)

        elif state == "CONNECTED":
            self.connect_btn.config(text="Desconectar")
            self.conn_status.config(text="Conectado", fg=self.GREEN)

        elif state == "ERROR":
            self.connect_btn.config(text="Conectar")
            self.conn_status.config(text="Erro", fg=self.RED)

    # =====================================================
    # AUTO
    # =====================================================

    def _toggle_auto(self):
        self.auto_running = not self.auto_running

        if self.auto_running:
            self.auto_btn.config(text="AUTO ON", bg="#2E7D32", fg="white")
            self.auto_loop.start()
            self.slot_controller.start_all()
        else:
            self.auto_btn.config(text="AUTO OFF", bg="#2a2a2a", fg="#cccccc")
            self.auto_loop.stop()
            self.slot_controller.stop_all()

    # =====================================================
    # CONTEXT MENU
    # =====================================================

    def _bind_context_menu(self, widget):
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="Colar", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Copiar", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="Limpar", command=lambda: widget.delete(0, tk.END))

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu)
