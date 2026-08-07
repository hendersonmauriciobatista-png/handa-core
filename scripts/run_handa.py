# ============================================================
# run_handa.py
# Launcher oficial do sistema H&A (compatível com EXE)
# ============================================================

import os
import sys


# 🔥 GARANTE PATH CORRETO NO EXE
if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

sys.path.append(base_path)


from main import main


def run():
    print("[H&A] Iniciando via launcher oficial...")
    main()


if __name__ == "__main__":
    run()
