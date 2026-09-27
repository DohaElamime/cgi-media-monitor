import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from modules.aggregator import collect_articles


def main():

    articles = collect_articles()

    print("\n")

    print("=" * 60)
    print(f"TOTAL : {len(articles)} articles")
    print("=" * 60)

    for article in articles[:10]:

        print()

        print(article["title"])

        print(article["source"])

        print(article["url"])

        print("-" * 60)


if __name__ == "__main__":
    main()