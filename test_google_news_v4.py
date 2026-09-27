# test_google_news_v4.py

import csv
from pathlib import Path

from modules.google_news_resolver_v4 import (
    resolve_google_news_url,
)


BASE_DIR = Path(
    __file__
).resolve().parent

INPUT_FILE = (
    BASE_DIR
    / "google_news_v2_results.csv"
)

OUTPUT_FILE = (
    BASE_DIR
    / "google_news_v4_resolution.csv"
)


def read_csv(path):

    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        return list(
            csv.DictReader(f)
        )


def write_csv(path, rows):

    if not rows:
        return

    fields = []

    for row in rows:

        for key in row:

            if key not in fields:
                fields.append(key)

    with open(
        path,
        "w",
        encoding="utf-8-sig",
        newline=""
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()
        writer.writerows(rows)


def main():

    print()
    print("=" * 70)
    print("GOOGLE NEWS V4 - TEST DE RÉSOLUTION")
    print("=" * 70)
    print()

    rows = read_csv(
        INPUT_FILE
    )

    relevant = [
        row
        for row in rows
        if str(
            row.get(
                "relevant",
                ""
            )
        ).lower()
        in {
            "true",
            "1",
            "yes",
            "oui"
        }
    ]

    print(
        f"Articles pertinents : "
        f"{len(relevant)}"
    )

    print()

    results = []

    resolved = 0
    unresolved = 0

    methods = {}

    for index, row in enumerate(
        relevant,
        start=1
    ):

        title = str(
            row.get(
                "title",
                ""
            )
        ).strip()

        url = str(
            row.get(
                "url",
                ""
            )
        ).strip()

        print(
            f"[{index}/{len(relevant)}] "
            f"{title[:80]}"
        )

        resolved_url, method = (
            resolve_google_news_url(
                url
            )
        )

        result = {
            "title": title,
            "original_url": url,
            "resolved_url": (
                resolved_url or ""
            ),
            "resolution_method": method,
        }

        results.append(
            result
        )

        methods[method] = (
            methods.get(
                method,
                0
            ) + 1
        )

        if resolved_url:

            resolved += 1

            print(
                f"    -> RESOLVED"
            )

            print(
                f"       {resolved_url[:150]}"
            )

            print(
                f"       méthode : {method}"
            )

        else:

            unresolved += 1

            print(
                f"    -> UNRESOLVED"
            )

    write_csv(
        OUTPUT_FILE,
        results
    )

    print()
    print("=" * 70)
    print("RÉSULTAT")
    print("=" * 70)

    print(
        f"Résolues                : "
        f"{resolved}"
    )

    print(
        f"Non résolues            : "
        f"{unresolved}"
    )

    print()

    print("MÉTHODES")

    for method, count in sorted(
        methods.items(),
        key=lambda x: x[1],
        reverse=True
    ):

        print(
            f"{method:<25} : {count}"
        )

    print()

    print(
        f"Fichier : "
        f"{OUTPUT_FILE.name}"
    )

    print()

    print("SQLITE")
    print(
        "AUCUNE MODIFICATION"
    )

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()