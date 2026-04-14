import tkinter as tk
import json
from pathlib import Path
from datetime import datetime


LOG_FILE = Path("storage") / "history.jsonl"


class HistoryArea(tk.Frame):
    """
    Histórico de Trades — H&A
    Formato linear, estilo log
    Scroll vertical à direita
    Layout CONGELADO
    """

    REFRESH_MS = 800  # intervalo de atualização

    def __init__(self, master):
        super().__init__(master, bg="#f2f2f2")
        self._last_size = 0
        self._build_ui()
        self._refresh_loop()

    # =================================================
    # UI (CONGELADA)
    # =================================================
    def _build_ui(self):
        container = tk.Frame(
            self,
            bg="#f2f2f2",
            highlightbackground="#c0c0c0",
            highlightthickness=1
        )
        container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        tk.Label(
            container,
            text="Histórico de Trades",
            bg="#f2f2f2",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w", padx=6, pady=(4, 2))

        header_text = (
            "Hora     "
            "Slot  "
            "Par        "
            "Ação        "
            "Preço      "
            "Resultado  "
            "Var%"
        )

        tk.Label(
            container,
            text=header_text,
            bg="#f2f2f2",
            fg="#555555",
            font=("Consolas", 9, "bold")
        ).pack(anchor="w", padx=8, pady=(0, 4))

        body = tk.Frame(container, bg="#f2f2f2")
        body.pack(fill="both", expand=True, padx=6, pady=4)

        scrollbar = tk.Scrollbar(body)
        scrollbar.pack(side="right", fill="y")

        self.listbox = tk.Listbox(
            body,
            yscrollcommand=scrollbar.set,
            font=("Consolas", 9),
            width=110,
            activestyle="none",
            highlightthickness=0,
            relief="flat"
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        scrollbar.config(command=self.listbox.yview)

    # =================================================
    # LOOP DE LEITURA DO HISTÓRICO REAL
    # =================================================
    def _refresh_loop(self):
        if LOG_FILE.exists():
            size = LOG_FILE.stat().st_size

            if size != self._last_size:
                with LOG_FILE.open("r", encoding="utf-8") as f:
                    f.seek(self._last_size)
                    for line in f:
                        self._append_event(line.strip())

                self._last_size = size

        self.after(self.REFRESH_MS, self._refresh_loop)

    # =================================================
    # FORMATADOR
    # =================================================
    def _append_event(self, raw_line: str):
        try:
            event = json.loads(raw_line)
        except Exception:
            return

        # Hora
        ts = event.get("ts", "")
        try:
            hora = datetime.fromisoformat(ts.replace("Z", "")).strftime("%H:%M:%S")
        except Exception:
            hora = "--:--:--"

        # Campos (fallback seguro)
        slot = event.get("slot", "--")
        par = event.get("pair", "----")
        acao = event.get("type", "EVENTO").upper()
        preco = event.get("price", "--")
        resultado = event.get("status", "--")
        variacao = event.get("var", "--")

        line = (
            hora.ljust(9) +
            f"S{slot}".ljust(6) +
            str(par).ljust(11) +
            str(acao).ljust(12) +
            str(preco).rjust(11) + "  " +
            str(resultado).ljust(10) +
            str(variacao).rjust(6)
        )

        self.listbox.insert("end", line)
        self.listbox.yview_moveto(1.0)
