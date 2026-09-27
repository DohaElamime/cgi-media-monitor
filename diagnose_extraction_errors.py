import csv
from collections import Counter
from modules.article_extractor import extract_article


INPUT_FILE = "dryrun_errors.csv"
OUTPUT_FILE = "diagnosed_extraction_errors.csv"


def get_domain(url):
    try:
        return url.split("/")[2]
    except Exception:
        return ""


def main():
    with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"URLs à diagnostiquer : {len(rows)}")
    print("=" * 70)

    results = []

    for i, row in enumerate(rows, 1):
        url = row.get("url", "").strip()

        print()
        print(f"[{i}/{len(rows)}] {url}")

        try:
            content = extract_article(url)
            length = len(content)

            if length >= 300:
                status = "OK"
            else:
                status = "EMPTY"

        except Exception as e:
            content = ""
            length = 0
            status = "ERROR"

            print(f"[EXCEPTION] {e}")

        results.append({
            "id": row.get("id", ""),
            "title": row.get("title", ""),
            "url": url,
            "domain_google_news": get_domain(url),
            "status": status,
            "content_length": length,
        })

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=results[0].keys()
        )
        writer.writeheader()
        writer.writerows(results)

    print()
    print("=" * 70)
    print("DIAGNOSTIC TERMINÉ")
    print("=" * 70)

    counter = Counter(r["status"] for r in results)

    print("OK    :", counter["OK"])
    print("EMPTY :", counter["EMPTY"])
    print("ERROR :", counter["ERROR"])

    print()
    print(f"Résultat : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()