import tkinter as tk


def attach_context_menu(widget):

    menu = tk.Menu(widget, tearoff=0)

    def cut():
        try:
            widget.delete("sel.first", "sel.last")
        except:
            pass

    def copy():
        try:
            selected = widget.get()[widget.index("sel.first"):widget.index("sel.last")]
            widget.clipboard_clear()
            widget.clipboard_append(selected)
        except:
            pass

    def paste():
        try:
            text = widget.clipboard_get()
            widget.insert("insert", text)
        except:
            pass

    menu.add_command(label="Recortar", command=cut)
    menu.add_command(label="Copiar", command=copy)
    menu.add_command(label="Colar", command=paste)

    def show_menu(event):
        widget.focus_set()
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    widget.bind("<Button-3>", show_menu)
