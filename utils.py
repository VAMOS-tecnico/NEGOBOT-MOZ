# utils.py
"""
Utilitários comuns para o projeto NEGOBOT-MOZ.

Inclui:
- setup_logger: configuração global de logging
- funções de normalização/validação de números (Moçambique)
- parsing simples de mensagens e extração de números
- helpers de tempo (UTC)
- retry decorator para chamadas externas
- pequenas funções utilitárias (chunk, safe_get)
"""

import logging
import re
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Iterable, List, Optional, Tuple, Dict

# -------------------------
# Logging
# -------------------------
def setup_logger(level: int = logging.INFO, name: str = "negobot"):
    """
    Configura logger global. Chamar no arranque da app.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger

logger = setup_logger()

# -------------------------
# Números e telefones
# -------------------------
def clean_number(raw: str) -> str:
    """
    Remove tudo que não for dígito e retorna string limpa.
    Ex: '+258 84 123 4567' -> '258841234567'
    """
    if not raw:
        return ""
    return re.sub(r'\D', '', str(raw))

def format_phone_mz(raw: str) -> str:
    """
    Normaliza para formato internacional moçambicano sem separadores.
    Se o número já tiver código de país (começa por 258) mantém.
    Caso contrário, tenta assumir 258 quando o número tiver 9 dígitos (84xxxxxxx / 85xxxxxxx).
    """
    n = clean_number(raw)
    if not n:
        return ""
    if n.startswith("258"):
        return n
    # números locais com 9 dígitos (84/85 prefix)
    if len(n) == 9:
        return "258" + n
    # se tiver 10 ou 11 dígitos, devolve tal como está (fallback)
    return n

def is_group_jid(jid: str) -> bool:
    """
    Detecta se o JID é de grupo (contém '@g.us' ou similar).
    """
    if not jid:
        return False
    return "@g.us" in jid or jid.endswith("@g.us")

def validate_phone_mz(raw: str) -> bool:
    """
    Validação simples para números de Moçambique: começa por 25884 ou 25885 e tem 12 dígitos no total.
    Ajusta conforme as regras locais.
    """
    n = clean_number(raw)
    return bool(re.match(r'^(258)(84|85)\d{7}$', n))

# -------------------------
# Extração e parsing de texto
# -------------------------
def safe_extract_numbers(text: str) -> List[str]:
    """
    Extrai sequências numéricas com 2+ dígitos (útil para detectar preços, códigos).
    Retorna lista de strings.
    """
    if not text:
        return []
    return re.findall(r'\d{2,}', text)

def chunk_text(text: str, max_len: int = 1000) -> List[str]:
    """
    Divide texto em pedaços com no máximo max_len caracteres, preservando palavras.
    """
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
    """
    Acesso seguro a dicionários.
    """
    try:
        return d.get(key, default)
    except Exception:
        return default

# -------------------------
# Tempo / timestamps
# -------------------------
def now_utc() -> datetime:
    """
    Timestamp UTC timezone-aware.
    """
    return datetime.now(timezone.utc)

def iso_utc(dt: Optional[datetime] = None) -> str:
    """
    Retorna ISO string em UTC.
    """
    dt = dt or now_utc()
    return dt.astimezone(timezone.utc).isoformat()

# -------------------------
# Retry decorator
# -------------------------
def retry(times: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: Tuple = (Exception,)):
    """
    Decorator simples para re-tentar chamadas externas.
    Uso:
        @retry(times=3, delay=1)
        def call_api(...):
            ...
    """
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
            # último raise para visibilidade
            logger.error("Falha após %s tentativas em %s: %s", _times, func.__name__, last_exc)
            raise last_exc
        return wrapper
    return deco

# -------------------------
# Pequenas validações e utilitários
# -------------------------
def looks_like_mpesa(text: str) -> Optional[str]:
    """
    Detecta um número M-Pesa moçambicano no texto (ex.: 84xxxxxxx ou 85xxxxxxx).
    Retorna o primeiro match limpo ou None.
    """
    if not text:
        return None
    m = re.search(r'(84|85)\d{7}', text)
    return m.group(0) if m else None

def join_lines(lines: Iterable[str]) -> str:
    """
    Junta linhas ignorando vazios.
    """
    return "\n".join([l for l in (lines or []) if l and l.strip()])

# -------------------------
# Export helpers (para import simples)
# -------------------------
__all__ = [
    "setup_logger", "logger",
    "clean_number", "format_phone_mz", "validate_phone_mz", "is_group_jid",
    "safe_extract_numbers", "chunk_text", "safe_get",
    "now_utc", "iso_utc",
    "retry",
    "looks_like_mpesa", "join_lines"
]
