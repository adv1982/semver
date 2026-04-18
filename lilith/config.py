import os
from dotenv import load_dotenv

load_dotenv()

LILITH_PASSWORD = os.getenv("LILITH_PASSWORD", "")
ONION_SEARCH_KEY = os.getenv("ONION_SEARCH_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
PORT = int(os.getenv("PORT", 5000))
PETALS_MODEL = os.getenv("PETALS_MODEL", "nicoboss/Hermes-3-Llama-3.1-405B-Uncensored")
TOR_PROXY = os.getenv("TOR_PROXY", "socks5h://127.0.0.1:9050")
MEMORY_PATH = os.getenv("MEMORY_PATH", "./memory_db")
GIT_REPO_PATH = os.getenv("GIT_REPO_PATH", "..")
SECRET_KEY = os.urandom(24).hex()
