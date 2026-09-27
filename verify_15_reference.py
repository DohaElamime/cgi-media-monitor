import csv
from pathlib import Path

REFERENCE_FILE = Path(r"C:\Users\yass_\cgi-media-monitor\cgi_sentiment_reference_136_FINAL.csv")

TEST_IDS = [
    196, 231, 271, 314, 316,
    318, 321, 322, 323, 325,
    326, 336, 337, 340, 344
]

with open(REFERENCE_FILE, "r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

by_id = {int(row["id"]): row for row in rows}

print("=" * 90)
print("VÉRIFICATION DES RÉFÉRENCES")
print("=" * 90)

for article_id in TEST_IDS:
    row = by_id.get(article_id)

    if row is None:
        print(f"{article_id}: ABSENT DU FICHIER")
        continue

    print(
        f"{article_id:<5} | "
        f"Référence = {row['reference_sentiment']:<8} | "
        f"GPT-OSS = {row['gptoss_120b']:<8} | "
        f"Titre = {row['title']}"
    )

print("=" * 90)