"""
Wikipedia parallel corpus fetcher.

Given a bokmål Wikipedia article title, use the MediaWiki langlinks API
to find the matching Nynorsk article (if any), then fetch plain text
for both. Paragraphs are aligned positionally — this is a heuristic,
not guaranteed, so you'll want to spot-check before trusting segment-
level BLEU scores.

Usage:
    from src.sources.wikipedia import fetch_parallel_article, search_nb
    pairs = fetch_parallel_article("Kunstig intelligens")
    # → [("nb paragraph 1", "nn paragraph 1"), ...]
"""
from __future__ import annotations

from typing import List, Tuple
import urllib.parse
import urllib.request
import json
import re


UA = "nb-nn-eval/0.1 (https://github.com/local; research)"


def _api_call(host: str, params: dict) -> dict:
    qs = urllib.parse.urlencode(params)
    url = f"https://{host}/w/api.php?{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def search_nb(query: str, limit: int = 10) -> List[str]:
    """Search Norwegian Bokmål Wikipedia for article titles."""
    data = _api_call("no.wikipedia.org", {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    })
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def find_nn_title(nb_title: str) -> str | None:
    """Look up the matching Nynorsk article title via langlinks."""
    data = _api_call("no.wikipedia.org", {
        "action": "query",
        "titles": nb_title,
        "prop": "langlinks",
        "lllang": "nn",
        "format": "json",
    })
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        links = page.get("langlinks", [])
        if links:
            return links[0].get("*")
    return None


def fetch_plain_text(host: str, title: str) -> str:
    """Fetch the article's plain-text extract (headings + paragraphs)."""
    data = _api_call(host, {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": "1",
        "format": "json",
    })
    pages = data.get("query", {}).get("pages", {})
    for page in pages.values():
        return page.get("extract", "") or ""
    return ""


_HEADING_LINE = re.compile(r"^\s*=+\s*[^=]+\s*=+\s*$")


def paragraphs(text: str) -> List[str]:
    """Split text into non-empty paragraphs, stripped of section headings."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        # Strip any MediaWiki heading lines that got mixed into a paragraph
        # (the extracts API sometimes doesn't put a blank line before them).
        lines = [ln for ln in block.split("\n") if not _HEADING_LINE.match(ln)]
        block = "\n".join(lines).strip()
        # Skip very short blocks (likely leftover headings, list markers, etc).
        if len(block) < 40:
            continue
        out.append(block)
    return out


def fetch_parallel_article(nb_title: str) -> List[Tuple[str, str]]:
    """
    Return a list of (nb_paragraph, nn_paragraph) tuples for an article.

    Alignment is positional: the Nth paragraph in the nb article is paired
    with the Nth paragraph in the nn article. This is crude but workable
    when both versions are reasonably parallel.
    """
    nn_title = find_nn_title(nb_title)
    if not nn_title:
        return []
    nb_text = fetch_plain_text("no.wikipedia.org", nb_title)
    nn_text = fetch_plain_text("nn.wikipedia.org", nn_title)
    nb_paras = paragraphs(nb_text)
    nn_paras = paragraphs(nn_text)
    # Positional alignment, truncated to the shorter of the two.
    n = min(len(nb_paras), len(nn_paras))
    return list(zip(nb_paras[:n], nn_paras[:n]))
