import csv
from pathlib import Path
import requests
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "google_news_v2_results.csv"
OUTPUT_FILE = BASE_DIR / "google_news_url_diagnostic.csv"

TIMEOUT = 15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}


def read_csv(path):
    with open(
        path,
        "r",
        encoding="utf-8-sig",
        newline=""
    ) as f:
        return list(csv.DictReader(f))


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


def diagnose(url):

    result = {
        "url": url,
        "hostname": "",
        "status_code": "",
        "final_url": "",
        "final_hostname": "",
        "content_type": "",
        "response_length": "",
        "redirect_count": "",
        "error": "",
    }

    try:

        parsed = urlparse(url)

        result["hostname"] = parsed.netloc

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        final = urlparse(
            response.url
        )

        result["status_code"] = (
            response.status_code
        )

        result["final_url"] = (
            response.url
        )

        result["final_hostname"] = (
            final.netloc
        )

        result["content_type"] = (
            response.headers.get(
                "Content-Type",
                ""
            )
        )

        result["response_length"] = len(
            response.content
        )

        result["redirect_count"] = len(
            response.history
        )

    except Exception as exc:

        result["error"] = str(exc)

    return result


def main():

    print()
    print("=" * 70)
    print("DIAGNOSTIC GOOGLE NEWS URL")
    print("=" * 70)
    print()

    if not INPUT_FILE.exists():

        print(
            f"Fichier introuvable : {INPUT_FILE}"
        )

        return

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
        f"Articles pertinents : {len(relevant)}"
    )

    print()

    results = []

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
            f"{title[:70]}"
        )

        diagnostic = diagnose(
            url
        )

        diagnostic[
            "title"
        ] = title

        results.append(
            diagnostic
        )

        print(
            f"    HTTP : "
            f"{diagnostic['status_code']}"
        )

        print(
            f"    Final : "
            f"{diagnostic['final_hostname']}"
        )

        print(
            f"    Redirects : "
            f"{diagnostic['redirect_count']}"
        )

        if diagnostic["error"]:
            print(
                f"    ERROR : "
                f"{diagnostic['error']}"
            )

    write_csv(
        OUTPUT_FILE,
        results
    )

    # --------------------------------------------------------
    # Résumé
    # --------------------------------------------------------

    google_final = 0
    external_final = 0
    errors = 0
    status_counts = {}

    for row in results:

        if row["error"]:
            errors += 1

        hostname = (
            row["final_hostname"]
            or ""
        ).lower()

        if "news.google.com" in hostname:
            google_final += 1

        elif hostname:
            external_final += 1

        status = str(
            row["status_code"]
        )

        status_counts[status] = (
            status_counts.get(
                status,
                0
            ) + 1
        )

    print()
    print("=" * 70)
    print("RÉSULTAT")
    print("=" * 70)

    print(
        f"URLs finales Google News : "
        f"{google_final}"
    )

    print(
        f"URLs finales média       : "
        f"{external_final}"
    )

    print(
        f"Erreurs                  : "
        f"{errors}"
    )

    print()

    print("CODES HTTP")

    for status, count in sorted(
        status_counts.items()
    ):

        print(
            f"{status:<10} : {count}"
        )

    print()

    print(
        f"Fichier : "
        f"{OUTPUT_FILE.name}"
    )

    print()

    print("SQLITE")
    print("AUCUNE MODIFICATION")

    print()
    print("=" * 70)


if __name__ == "__main__":
    main()