# utils.py
"""
Utilitários comuns para o projeto NEGOBOT-MOZ.
"""
import logging
import re
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Iterable, List, Optional, Tuple, Dict

def setup_logger(level: int = logging.INFO, name: str = "negobot"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger

logger = setup_logger()

def clean_number(raw: str) -> str:
    if not raw:
        return ""
    return re.sub(r'\D', '', str(raw))

def format_phone_mz(raw: str) -> str:
    n = clean_number(raw)
    if not n:
        return ""
    if n.startswith("258"):
        return n
    if len(n) == 9:
        return "258" + n
    return n

def is_group_jid(jid: str) -> bool:
    if not jid:
        return False
    return "@g.us" in jid or jid.endswith("@g.us")

def validate_phone_mz(raw: str) -> bool:
    n = clean_number(raw)
    return bool(re.match(r'^(258)(84|85)\d{7}$', n))

def safe_extract_numbers(text: str) -> List[str]:
    if not text:
        return []
    return re.findall(r'\d{2,}', text)

def chunk_text(text: str, max_len: int = 1000) -> List[str]:
    if not text:
        return []
    words = text.split()
    chunks = []
    cur = []
    cur_len = 0
    for w in words:
        if cur_len + len(w) + 1 > max_len and cur:
            chunks.append(" ".join(cur))
            cur = [w]
            cur_len = len(w) + 1
        else:
            cur.append(w)
            cur_len += len(w) + 1
    if cur:
        chunks.append(" ".join(cur))
    return chunks

def safe_get(d: Dict, key: str, default: Any = None) -> Any:
    try:
        return d.get(key, default)
    except Exception:
        return default

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def iso_utc(dt: Optional[datetime] = None) -> str:
    dt = dt or now_utc()
    return dt.astimezone(timezone.utc).isoformat()

def retry(times: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: Tuple = (Exception,)):
    def deco(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _times = times
            _delay = delay
            last_exc = None
            for attempt in range(_times):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    logger.warning("Retry %s/%s para %s devido a: %s", attempt + 1, _times, func.__name__, e)
                    time.sleep(_delay)
                    _delay *= backoff
            logger.error("Falha após %s tentativas em %s: %s", _times, func.__name__, last_exc)
            raise last_exc
        return wrapper
    return deco

def looks_like_mpesa(text: str) -> Optional[str]:
    if not text:
        return None
    m = re.search(r'(84|85)\d{7}', text)
    return m.group(0) if m else None

def join_lines(lines: Iterable[str]) -> str:
    return "\n".join([l for l in (lines or []) if l and l.strip()])

__all__ = [
    "setup_logger", "logger",
    "clean_number", "format_phone_mz", "validate_phone_mz", "is_group_jid",
    "safe_extract_numbers", "chunk_text", "safe_get",
    "now_utc", "iso_utc",
    "retry",
    "looks_like_mpesa", "join_lines"
]
