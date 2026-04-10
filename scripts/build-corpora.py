#!/usr/bin/env python3
"""
Fetch and save pre-built parallel corpora from Wikipedia.

Run once to populate corpora/ with ready-to-use test sets:
    cd /Users/lars/projects/nb-nn-eval
    ./.venv/bin/python scripts/build-corpora.py

Saved corpora show up automatically in the eval UI.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.sources.wikipedia import fetch_parallel_article, find_nn_title

CORPORA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "corpora")
os.makedirs(CORPORA_DIR, exist_ok=True)


def save(name, description, source, pairs):
    """Save a corpus as JSON, converting tuple pairs to {nb, nn} dicts."""
    data = {
        "name": name,
        "description": description,
        "source": source,
        "pairs": [{"nb": nb, "nn": nn} for nb, nn in pairs],
    }
    path = os.path.join(CORPORA_DIR, f"{name}.json")
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved {name}: {len(data['pairs'])} pairs")


def fetch_wiki_corpus(name, description, articles):
    """Fetch multiple Wikipedia articles and merge into one corpus."""
    all_pairs = []
    for title in articles:
        nn_title = find_nn_title(title)
        if not nn_title:
            print(f"  SKIP {title} (no nn version)")
            continue
        pairs = fetch_parallel_article(title)
        print(f"  {title} → {nn_title}: {len(pairs)} pairs")
        all_pairs.extend(pairs)
    if all_pairs:
        save(name, description, "Wikipedia (nb/nn parallell)", all_pairs)
    return all_pairs


if __name__ == "__main__":
    print("=== Building Wikipedia corpora ===\n")

    print("1. wiki-byer (Norwegian cities)")
    fetch_wiki_corpus(
        "wiki-byer",
        "Parallelle Wikipedia-artiklar om norske byar: Bergen, Oslo, Trondheim, Stavanger, Tromsø.",
        ["Bergen", "Oslo", "Trondheim", "Stavanger", "Tromsø"],
    )

    print("\n2. wiki-samfunn (Society & politics)")
    fetch_wiki_corpus(
        "wiki-samfunn",
        "Parallelle Wikipedia-artiklar om norsk samfunn: Stortinget, Klimaendring, Nynorsk, Bokmål.",
        ["Stortinget", "Klimaendring", "Nynorsk", "Bokmål"],
    )

    print("\n3. wiki-natur (Nature & geography)")
    fetch_wiki_corpus(
        "wiki-natur",
        "Parallelle Wikipedia-artiklar om norsk natur: Fjord, Nasjonalpark, Fotball.",
        ["Fjord", "Nasjonalpark", "Fotball", "Helse"],
    )

    print("\n4. wiki-teknologi (Technology)")
    fetch_wiki_corpus(
        "wiki-teknologi",
        "Parallelle Wikipedia-artiklar om teknologi: Kunstig intelligens.",
        ["Kunstig intelligens"],
    )

    print("\nDone!")
