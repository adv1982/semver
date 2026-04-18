import requests
from config import TOR_PROXY

_TOR_PROXIES = {
    "http": TOR_PROXY,
    "https": TOR_PROXY,
}


def get_session() -> requests.Session:
    s = requests.Session()
    s.proxies = _TOR_PROXIES
    s.headers.update({"User-Agent": "Mozilla/5.0 (compatible; Lilith/1.0)"})
    return s


def is_tor_up() -> bool:
    try:
        s = get_session()
        r = s.get("http://check.torproject.org/api/ip", timeout=15)
        return r.json().get("IsTor", False)
    except Exception:
        return False


def fetch(url: str, timeout: int = 20) -> str:
    s = get_session()
    r = s.get(url, timeout=timeout)
    r.raise_for_status()
    return r.text
