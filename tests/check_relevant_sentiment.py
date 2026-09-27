from __future__ import annotations

import sqlite3

from config import DATABASE_PATH


def main() -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            id,
            title,
            source,
            relevant,
            sentiment,
            sentiment_score
        FROM articles
        WHERE relevant = 1
        ORDER BY id ASC
        """
    ).fetchall()

    print("=" * 100)
    print("ARTICLES PERTINENTS CGI")
    print("=" * 100)

    print(f"Nombre total : {len(rows)}")

    for row in rows:
        print()
        print("-" * 100)
        print(f"ID        : {row['id']}")
        print(f"Titre     : {row['title']}")
        print(f"Source    : {row['source']}")
        print(f"Sentiment : {row['sentiment']}")
        print(
            f"Score     : "
            f"{float(row['sentiment_score'] or 0.0):.2%}"
        )

    conn.close()


if __name__ == "__main__":
    main()