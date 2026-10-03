"""A small progress window for downloads; falls back to no window at all."""

from __future__ import annotations

import queue
import threading


def run(task):
    """Run task(report) in a worker thread while a window shows report(text, fraction)."""
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception:  # noqa: BLE001 - no Tk: update silently
        return task(lambda _text, _fraction=None: None)
    events: queue.Queue = queue.Queue()
    outcome: dict = {}
    window = tk.Tk()
    window.title("LAIN")
    window.configure(bg="#07060a")
    window.resizable(False, False)
    window.geometry("440x130")
    window.protocol("WM_DELETE_WINDOW", lambda: None)  # downloads must not be cut halfway
    tk.Label(window, text="L A I N", fg="#e9e2ea", bg="#07060a", font=("Segoe UI", 16, "bold")).pack(pady=(14, 2))
    label = tk.Label(window, text="Buscando actualizaciones…", fg="#c9bfcc", bg="#07060a", font=("Segoe UI", 10))
    label.pack()
    bar = ttk.Progressbar(window, length=380, mode="determinate", maximum=1000)
    bar.pack(pady=10)

    def report(text, fraction=None):
        events.put((text, fraction))

    def worker():
        try:
            outcome["value"] = task(report)
        except BaseException as error:  # noqa: BLE001 - handed back to the caller
            outcome["error"] = error
        events.put(None)

    def pump():
        try:
            while True:
                event = events.get_nowait()
                if event is None:
                    window.destroy()
                    return
                text, fraction = event
                label.config(text=text)
                if fraction is not None:
                    bar.config(value=int(max(0.0, min(1.0, fraction)) * 1000))
        except queue.Empty:
            pass
        window.after(100, pump)

    threading.Thread(target=worker, daemon=True).start()
    window.after(100, pump)
    window.mainloop()
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("value")
