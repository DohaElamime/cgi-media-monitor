import sqlite3
import csv
from pathlib import Path

DB_PATH = Path(r"C:\Users\yass_\cgi-media-monitor\database\articles.db")
TEST_IDS = [
    196,
    231,
    271,
    314,
    316,
    318,
    321,
    322,
    323,
    325,
    326,
    336,
    337,
    340,
    344,
]

db_uri = f"file:{DB_PATH.resolve().as_posix()}?mode=ro"

conn = sqlite3.connect(db_uri, uri=True)

placeholders = ",".join("?" for _ in TEST_IDS)

query = f"""
SELECT
    id,
    title,
    summary,
    content,
    source,
    url,
    sentiment,
    sentiment_score
FROM articles
WHERE id IN ({placeholders})
ORDER BY id
"""

rows = conn.execute(query, TEST_IDS).fetchall()
conn.close()

output = Path("audit_15_content.csv")

with open(output, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f)

    writer.writerow([
        "id",
        "title",
        "source",
        "url",
        "old_sentiment",
        "old_score",
        "summary",
        "content"
    ])

    for row in rows:
        (
            article_id,
            title,
            summary,
            content,
            source,
            url,
            old_sentiment,
            old_score
        ) = row

        writer.writerow([
            article_id,
            title,
            source,
            url,
            old_sentiment,
            old_score,
            summary or "",
            content or ""
        ])

print("=" * 90)
print("AUDIT CONTENU")
print("=" * 90)
print(f"Articles trouvés : {len(rows)}")
print(f"Fichier          : {output.resolve()}")
print()
print("SQLite : AUCUNE MODIFICATION")
print("=" * 90)