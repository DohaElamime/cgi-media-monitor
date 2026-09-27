import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from modules.article_extractor import extract_article

url = "https://medias24.com/2025/04/23/abderrahmane-ifrassen-nomme-dg-de-la-cgi-et-dga-de-cdg-developpement/"

text = extract_article(url)

print("=" * 80)
print(text[:2000] if text else "Aucun contenu extrait.")