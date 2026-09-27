import csv

IDS = {196, 316, 318, 321, 322, 323, 325, 336}

CSV_FILE = "audit_15_content.csv"

with open(CSV_FILE, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)

    for row in reader:
        article_id = int(row["id"])

        if article_id not in IDS:
            continue

        print("\n" + "=" * 100)
        print(f"ID : {article_id}")
        print("=" * 100)

        print("\nTITRE :")
        print(row.get("title", ""))

        print("\nSOURCE :")
        print(row.get("source", ""))

        print("\nCONTENU :")
        print(row.get("content", ""))

        print("\n" + "-" * 100)