import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from modules.ai_classifier import is_relevant_ai
from modules.article_extractor import extract_article

url = "https://medias24.com/2025/04/23/abderrahmane-ifrassen-nomme-dg-de-la-cgi-et-dga-de-cdg-developpement/"

text = extract_article(url)

relevant, score = is_relevant_ai(text)

print("Pertinent :", relevant)
print("Confiance :", score)