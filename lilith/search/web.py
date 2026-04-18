from duckduckgo_search import DDGS


def search_web(query: str, max_results: int = 5) -> list[dict]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title"), "url": r.get("href"), "snippet": r.get("body")} for r in results]
    except Exception as e:
        return [{"error": str(e)}]


def format_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        if "error" in r:
            lines.append(f"Erro na busca: {r['error']}")
            continue
        lines.append(f"{i}. {r.get('title', 'Sem título')}")
        lines.append(f"   {r.get('url', '')}")
        lines.append(f"   {r.get('snippet', '')[:200]}")
    return "\n".join(lines)
