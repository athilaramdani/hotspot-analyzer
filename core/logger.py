# backend/log.py

_log_callback = None

def set_log_callback(cb):
    global _log_callback
    _log_callback = cb

def _log(msg: str):
    print("[LOG]", msg)
    if _log_callback:
        _log_callback(msg)
