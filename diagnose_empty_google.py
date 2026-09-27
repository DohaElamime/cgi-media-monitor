import csv

from modules.article_extractor import decode_google_news


INPUT_FILE = "diagnosed_extraction_errors.csv"


with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
    rows = list(csv.DictReader(f))


rows = [
    r for r in rows
    if r["status"] == "EMPTY"
    and "news.google.com" in r["url"]
]


print(f"Google News EMPTY : {len(rows)}")
print("=" * 80)


for i, row in enumerate(rows, 1):

    google_url = row["url"]

    print()
    print(f"[{i}/{len(rows)}]")
    print("Google News :", google_url)

    try:
        decoded = decode_google_news(google_url)

        if decoded and decoded != google_url:
            print("SOURCE      :", decoded)
        else:
            print("SOURCE      : DECODAGE IMPOSSIBLE")

    except Exception as e:
        print("DECODAGE ERROR:", e)