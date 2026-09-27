import os
import sqlite3


ROOT_DIR = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

DATABASE_PATH = os.path.join(
    ROOT_DIR,
    "database",
    "articles.db"
)


conn = sqlite3.connect(
    DATABASE_PATH
)

conn.row_factory = sqlite3.Row


rows = conn.execute(
    """
    SELECT
        id,
        title,
        source,
        url
    FROM articles
    WHERE content IS NULL
       OR TRIM(content) = ''
    ORDER BY id
    """
).fetchall()


print("=" * 70)
print("ARTICLES RESTANTS")
print("=" * 70)

print()
print(
    "TOTAL =",
    len(rows)
)


for row in rows:

    print()
    print("-" * 70)

    print(
        "ID     =",
        row["id"]
    )

    print(
        "SOURCE =",
        row["source"]
    )

    print(
        "TITRE  =",
        row["title"]
    )

    print(
        "URL    =",
        row["url"]
    )


conn.close()