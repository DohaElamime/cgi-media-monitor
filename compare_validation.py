import pandas as pd
from pathlib import Path
import re
import unicodedata


RESULTS_FILE = Path("gptoss_136_results.csv")
REFERENCE_FILE = Path("cgi_sentiment_reference_136_FINAL.csv")
OUTPUT_FILE = Path("comparison_136_results.csv")


print("=" * 70)
print("COMPARAISON GPT-OSS / RÉFÉRENCE INDÉPENDANTE")
print("=" * 70)


# ============================================================
# CHARGEMENT
# ============================================================

results = pd.read_csv(
    RESULTS_FILE,
    dtype=str,
    keep_default_na=False
)

reference = pd.read_csv(
    REFERENCE_FILE,
    dtype=str,
    keep_default_na=False
)

print(f"\nGPT-OSS   : {len(results)} lignes")
print(f"Référence : {len(reference)} lignes")


# ============================================================
# NORMALISATION
# ============================================================

def normalize_text(value):

    value = str(value).strip().lower()

    value = unicodedata.normalize(
        "NFKD",
        value
    )

    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value


def normalize_id(value):

    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    return value


results["id_norm"] = results["id"].apply(
    normalize_id
)

reference["id_norm"] = reference["id"].apply(
    normalize_id
)

results["title_norm"] = results["title"].apply(
    normalize_text
)

reference["title_norm"] = reference["title"].apply(
    normalize_text
)


# ============================================================
# SENTIMENT
# ============================================================

def normalize_sentiment(value):

    value = str(value).strip().lower()

    if value == "positive":
        return "Positive"

    if value == "negative":
        return "Negative"

    if value == "neutral":
        return "Neutral"

    if value == "review":
        return "REVIEW"

    return ""


results["gptoss_sentiment"] = (
    results["sentiment"]
    .apply(normalize_sentiment)
)

reference["reference_sentiment"] = (
    reference["reference_sentiment"]
    .apply(normalize_sentiment)
)


# ============================================================
# MATCH PAR ID
# ============================================================

reference_by_id = {}

for _, row in reference.iterrows():

    key = row["id_norm"]

    if key:
        reference_by_id[key] = row


# ============================================================
# MATCH PAR TITRE
# ============================================================

reference_by_title = {}

for _, row in reference.iterrows():

    key = row["title_norm"]

    if key:
        reference_by_title[key] = row


# ============================================================
# COMPARAISON
# ============================================================

rows = []

matched_by_id = 0
matched_by_title = 0
not_matched = 0


for _, result in results.iterrows():

    result_id = result["id_norm"]
    result_title = result["title_norm"]

    ref = None
    match_method = ""

    # --------------------------------------------------------
    # 1. ID
    # --------------------------------------------------------

    if result_id in reference_by_id:

        ref = reference_by_id[result_id]
        match_method = "ID"
        matched_by_id += 1

    # --------------------------------------------------------
    # 2. TITRE
    # --------------------------------------------------------

    elif result_title in reference_by_title:

        ref = reference_by_title[result_title]
        match_method = "TITLE"
        matched_by_title += 1

    # --------------------------------------------------------
    # Aucun match
    # --------------------------------------------------------

    else:

        not_matched += 1

        rows.append({
            "id": result["id"],
            "title": result["title"],
            "gptoss_sentiment": result["gptoss_sentiment"],
            "reference_sentiment": "",
            "match_method": "NO_MATCH",
            "comparison_status": "NOT_FOUND",
        })

        continue


    reference_sentiment = ref[
        "reference_sentiment"
    ]

    gptoss_sentiment = result[
        "gptoss_sentiment"
    ]


    # --------------------------------------------------------
    # Comparaison
    # --------------------------------------------------------

    if reference_sentiment == "REVIEW":

        status = "REFERENCE_REVIEW"

    elif gptoss_sentiment == "":

        status = "GPTOSS_EMPTY"

    elif gptoss_sentiment == "REVIEW":

        status = "GPTOSS_REVIEW"

    elif gptoss_sentiment == reference_sentiment:

        status = "MATCH"

    else:

        status = "DISAGREEMENT"


    rows.append({
        "id": result["id"],
        "title": result["title"],
        "gptoss_sentiment": gptoss_sentiment,
        "reference_sentiment": reference_sentiment,
        "match_method": match_method,
        "comparison_status": status,
        "reference_status": ref.get(
            "status",
            ""
        ),
        "reference_confidence": ref.get(
            "confidence",
            ""
        ),
        "reference_note": ref.get(
            "note",
            ""
        ),
    })


comparison = pd.DataFrame(rows)


# ============================================================
# STATISTIQUES MATCHING
# ============================================================

print("\n")
print("=" * 70)
print("CORRESPONDANCE DES ARTICLES")
print("=" * 70)

print(
    f"\nMatch par ID      : {matched_by_id}"
)

print(
    f"Match par titre   : {matched_by_title}"
)

print(
    f"Non trouvés       : {not_matched}"
)

print(
    f"Total comparé     : {len(comparison)}"
)


# ============================================================
# STATISTIQUES SENTIMENT
# ============================================================

print("\n")
print("=" * 70)
print("RÉSULTATS DE COMPARAISON")
print("=" * 70)


counts = (
    comparison[
        comparison["comparison_status"]
        != "NOT_FOUND"
    ]["comparison_status"]
    .value_counts()
)


for status, count in counts.items():

    print(
        f"{status:<25} : {count}"
    )


# ============================================================
# ACCORD
# ============================================================

comparable = comparison[
    comparison["comparison_status"].isin(
        [
            "MATCH",
            "DISAGREEMENT",
        ]
    )
]


matches = comparable[
    comparable["comparison_status"]
    == "MATCH"
]


disagreements = comparable[
    comparable["comparison_status"]
    == "DISAGREEMENT"
]


print("\n")
print(
    f"Articles comparables : {len(comparable)}"
)

print(
    f"Accords             : {len(matches)}"
)

print(
    f"Désaccords          : {len(disagreements)}"
)


if len(comparable) > 0:

    agreement = (
        len(matches)
        / len(comparable)
        * 100
    )

    print(
        f"Accord              : {agreement:.2f}%"
    )


# ============================================================
# MATRICE
# ============================================================

print("\n")
print("=" * 70)
print("MATRICE GPT-OSS / RÉFÉRENCE")
print("=" * 70)


matrix = pd.crosstab(
    comparable["reference_sentiment"],
    comparable["gptoss_sentiment"]
)


print("\n")
print(matrix)


# ============================================================
# DÉSACCORDS
# ============================================================

print("\n")
print("=" * 70)
print("DÉSACCORDS")
print("=" * 70)


if disagreements.empty:

    print("\nAucun désaccord.")

else:

    print(
        disagreements[
            [
                "id",
                "title",
                "gptoss_sentiment",
                "reference_sentiment",
                "match_method",
            ]
        ].to_string(index=False)
    )


# ============================================================
# REVIEW
# ============================================================

reviews = comparison[
    comparison["comparison_status"].isin(
        [
            "REFERENCE_REVIEW",
            "GPTOSS_REVIEW",
        ]
    )
]


print("\n")
print("=" * 70)
print("ARTICLES REVIEW")
print("=" * 70)


if reviews.empty:

    print("\nAucun REVIEW.")

else:

    print(
        reviews[
            [
                "id",
                "title",
                "gptoss_sentiment",
                "reference_sentiment",
                "reference_note",
            ]
        ].to_string(index=False)
    )


# ============================================================
# SAUVEGARDE
# ============================================================

comparison.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)


print("\n")
print("=" * 70)
print("TERMINÉ")
print("=" * 70)

print(
    f"\n📄 Résultat : {OUTPUT_FILE}"
)

print(
    "\n⚠️ SQLite : AUCUNE MODIFICATION"
)