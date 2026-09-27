"""
Test the CGI sentiment model against real articles from the database.

This script DOES NOT modify the database.
It only reads articles and prints old/new sentiment results.
"""

from __future__ import annotations

from modules.database import get_articles
from modules.sentiment_analysis import analyze_cgi_sentiment


TEST_IDS = [
    206,
    209,
    211,
    250,
    263,
    267,
    271,
    277,
    321,
    325,
    332,
]


def main() -> None:
    articles = get_articles()

    if not articles:
        print("Aucun article trouvé dans la base.")
        return

    articles_by_id = {
        int(article["id"]): article
        for article in articles
    }

    print()
    print("=" * 100)
    print("TEST SENTIMENT SUR ARTICLES RÉELS")
    print("=" * 100)

    for article_id in TEST_IDS:

        article = articles_by_id.get(article_id)

        if article is None:
            print()
            print(f"[ID {article_id}] Article introuvable.")
            continue

        title = article.get("title") or ""
        content = article.get("content") or ""
        old_sentiment = article.get("sentiment")

        result = analyze_cgi_sentiment(
            title=title,
            content=content,
        )

        print()
        print("-" * 100)
        print(f"ID              : {article_id}")
        print(f"TITRE           : {title}")
        print(f"ANCIEN SENTIMENT : {old_sentiment}")
        print(f"NOUVEAU          : {result['sentiment']}")
        print(f"SCORE            : {result['score']}")
        print("-" * 100)

    print()
    print("=" * 100)
    print("FIN DU TEST")
    print("=" * 100)


if __name__ == "__main__":
    main()