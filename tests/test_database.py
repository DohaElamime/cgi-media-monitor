import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from modules.database import (
    count_articles,
    get_articles,
)

print("=" * 50)

print("Nombre d'articles :", count_articles())

print("=" * 50)

articles = get_articles()

for article in articles[:5]:
    print(article["title"])