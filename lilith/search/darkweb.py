import requests
from config import ONION_SEARCH_KEY
from tor.client import get_session

AHMIA_URL = "https://ahmia.fi/search/?q={query}"
ONION_API_URL = "https://api.onionsearch.com/v1/search"


def search_darkweb(query: str, max_results: int = 5) -> list[dict]:
    results = []

    # Tentativa via API Onion Search
    if ONION_SEARCH_KEY:
        try:
            r = requests.get(
                ONION_API_URL,
                headers={"Authorization": f"Bearer {ONION_SEARCH_KEY}"},
                params={"q": query, "limit": max_results},
                timeout=20,
            )
            if r.status_code == 200:
                data = r.json()
                for item in data.get("results", [])[:max_results]:
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "snippet": item.get("description", "")[:300],
                        "source": "onion-api",
                    })
        except Exception:
            pass

    # Fallback: Ahmia via Tor
    if not results:
        try:
            from bs4 import BeautifulSoup
            session = get_session()
            url = AHMIA_URL.format(query=requests.utils.quote(query))
            resp = session.get(url, timeout=25)
            soup = BeautifulSoup(resp.text, "html.parser")
            for li in soup.select("li.result")[:max_results]:
                title_el = li.select_one("h4")
                url_el = li.select_one("a[href]")
                desc_el = li.select_one("p")
                results.append({
                    "title": title_el.text.strip() if title_el else "",
                    "url": url_el["href"] if url_el else "",
                    "snippet": desc_el.text.strip()[:300] if desc_el else "",
                    "source": "ahmia",
                })
        except Exception as e:
            results.append({"error": f"Busca dark web falhou: {e}"})

    return results


def format_results(results: list[dict]) -> str:
    lines = ["🧅 Resultados Dark Web:"]
    for i, r in enumerate(results, 1):
        if "error" in r:
            lines.append(f"  ⚠️ {r['error']}")
            continue
        lines.append(f"\n{i}. {r.get('title', 'Sem título')} [{r.get('source', '')}]")
        lines.append(f"   {r.get('url', '')}")
        lines.append(f"   {r.get('snippet', '')[:200]}")
    return "\n".join(lines)
