import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from modules.sources.ddgs_source import search_ddgs
from modules.article_extractor import extract_article
from modules.relevance_filter import is_relevant

articles = search_ddgs()

print(f"{len(articles)} articles trouvés.\n")

relevant = 0

for article in articles:

    text = extract_article(article["url"])

    if text and is_relevant(text):
        relevant += 1
        print("✔", article["title"])

print(f"\nArticles pertinents : {relevant}")