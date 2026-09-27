import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from modules.pipeline import run_pipeline

articles = run_pipeline()

print()

print("=" * 60)

print(f"TOTAL : {len(articles)}")

print("=" * 60)

for article in articles[:20]:

    print()

    print(article["title"])

    print(article["source"])

    print(article["url"])