import csv

IDS = {
    196, 231, 271, 288, 314,
    316, 318, 321, 322, 323,
    325, 326, 336, 337, 344
}

SOURCE_FILE = "audit_15_content.csv"

with open(SOURCE_FILE, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)

    rows = []

    for row in reader:
        try:
            article_id = int(row["id"])
        except (ValueError, TypeError):
            continue

        if article_id in IDS:
            rows.append(row)

for row in rows:

    print("\n" + "=" * 110)
    print(f"ID : {row['id']}")
    print("=" * 110)

    print("\nTITRE :")
    print(row.get("title", ""))

    print("\nSOURCE :")
    print(row.get("source", ""))

    print("\nCONTENU :")
    print(row.get("content", ""))

print("\n" + "=" * 110)
print(f"Articles affichés : {len(rows)}")
print("=" * 110)