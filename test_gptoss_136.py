import sqlite3
import requests
import json
import csv
import os
import time

DB = r"C:\Users\yass_\cgi-media-monitor\database\articles.db"
URL = "http://localhost:11434/api/chat"
MODEL = "gpt-oss:120b-cloud"

OUTPUT = r"C:\Users\yass_\cgi-media-monitor\gptoss_136_results.csv"

PROMPT = """
Tu es un analyste de sentiment spécialisé dans les articles de presse concernant CGI.

Classe l'article dans UNE seule catégorie :

Positive :
l'article présente CGI, sa situation, ses résultats ou ses actions de manière
globalement favorable, avec une appréciation ou des conséquences favorables.

Negative :
l'article présente CGI, sa situation, ses résultats ou ses actions de manière
globalement défavorable, problématique, conflictuelle, dommageable, avec échec
ou conséquence négative.

Neutral :
l'article est principalement factuel ou descriptif, sans orientation clairement
positive ou négative envers CGI.

Règles importantes :
- Une nomination n'est PAS automatiquement positive.
- Un investissement ou un projet n'est PAS automatiquement positif.
- Un événement juridique n'est PAS automatiquement négatif.
- Ne te base jamais sur un mot isolé.
- Distingue les faits concernant CGI de ceux concernant d'autres organisations.
- Analyse le titre, le résumé et le contenu ensemble.
- Utilise le sens global de l'article.
- Choisis exactement UNE catégorie.

Réponds UNIQUEMENT avec un JSON valide :

{"sentiment":"Positive"}
{"sentiment":"Negative"}
{"sentiment":"Neutral"}
"""

# ------------------------------------------------------------
# Charger les résultats déjà sauvegardés pour permettre la reprise
# ------------------------------------------------------------

completed = {}

if os.path.exists(OUTPUT):
    with open(OUTPUT, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("id"):
                completed[int(row["id"])] = row

print("=" * 90)
print("GPT-OSS 120B CLOUD - DRY RUN 136 ARTICLES")
print("=" * 90)
print(f"Résultats déjà présents : {len(completed)}")
print()

# ------------------------------------------------------------
# Connexion SQLite en lecture seule
# ------------------------------------------------------------

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = conn.cursor()

cur.execute("""
SELECT id, title, summary, content
FROM articles
WHERE relevant = 1
ORDER BY id
""")

rows = cur.fetchall()
conn.close()

print(f"Articles pertinents : {len(rows)}")
print()

# ------------------------------------------------------------
# Création du fichier de résultats
# ------------------------------------------------------------

file_exists = os.path.exists(OUTPUT)

fieldnames = [
    "id",
    "title",
    "sentiment",
    "elapsed_seconds",
    "status"
]

if not file_exists:
    with open(OUTPUT, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

# ------------------------------------------------------------
# Fonction d'appel GPT-OSS
# ------------------------------------------------------------

def classify(article_text):

    response = requests.post(
        URL,
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": PROMPT + "\n\nARTICLE :\n" + article_text
                }
            ],
            "stream": False,
            "format": "json",
            "think": False,
            "options": {
                "temperature": 0
            }
        },
        timeout=90
    )

    response.raise_for_status()

    data = response.json()

    text = data.get("message", {}).get("content", "").strip()

    if not text:
        raise ValueError("Réponse vide du modèle")

    result = json.loads(text)

    sentiment = result.get("sentiment")

    if sentiment not in ("Positive", "Negative", "Neutral"):
        raise ValueError(f"Sentiment invalide : {sentiment}")

    return sentiment

# ------------------------------------------------------------
# Analyse
# ------------------------------------------------------------

counts = {
    "Positive": 0,
    "Negative": 0,
    "Neutral": 0,
    "ERROR": 0
}

start_total = time.time()

for index, (article_id, title, summary, content) in enumerate(rows, 1):

    # Déjà traité ?
    if article_id in completed:
        sentiment = completed[article_id].get("sentiment", "ERROR")

        if sentiment in counts:
            counts[sentiment] += 1
        else:
            counts["ERROR"] += 1

        print(
            f"[{index:03}/{len(rows)}] "
            f"ID={article_id} | "
            f"{sentiment:8} | DEJA TRAITE"
        )
        continue

    article_text = f"""
TITRE:
{title or ""}

RÉSUMÉ:
{summary or ""}

CONTENU:
{content or ""}
"""

    # Limite de sécurité pour éviter des requêtes énormes
    article_text = article_text[:15000]

    sentiment = "ERROR"
    elapsed = 0
    last_error = ""

    for attempt in range(1, 4):

        start = time.time()

        try:
            sentiment = classify(article_text)
            elapsed = time.time() - start
            break

        except Exception as e:
            last_error = str(e)
            elapsed = time.time() - start

            print(
                f"    Tentative {attempt}/3 échouée : {last_error}"
            )

            if attempt < 3:
                time.sleep(3)

    if sentiment not in ("Positive", "Negative", "Neutral"):
        counts["ERROR"] += 1
        status = "ERROR"

        print(
            f"[{index:03}/{len(rows)}] "
            f"ID={article_id} | ERROR"
        )

    else:
        counts[sentiment] += 1
        status = "OK"

        print(
            f"[{index:03}/{len(rows)}] "
            f"ID={article_id} | "
            f"{sentiment:8} | "
            f"{elapsed:.1f}s | "
            f"{title[:70]}"
        )

    # --------------------------------------------------------
    # Sauvegarde immédiate
    # --------------------------------------------------------

    with open(OUTPUT, "a", encoding="utf-8", newline="") as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames
        )

        writer.writerow({
            "id": article_id,
            "title": title or "",
            "sentiment": sentiment,
            "elapsed_seconds": f"{elapsed:.1f}",
            "status": status
        })

    # Petite pause
    time.sleep(0.2)

# ------------------------------------------------------------
# Résultat final
# ------------------------------------------------------------

total = time.time() - start_total

print()
print("=" * 90)
print("RESULTAT FINAL GPT-OSS 120B CLOUD")
print("=" * 90)

print(f"Articles : {len(rows)}")
print(f"Positive : {counts['Positive']}")
print(f"Negative : {counts['Negative']}")
print(f"Neutral  : {counts['Neutral']}")
print(f"Errors   : {counts['ERROR']}")

print()
print(f"Temps total : {total / 60:.1f} minutes")

successful = (
    counts["Positive"]
    + counts["Negative"]
    + counts["Neutral"]
)

if successful:
    print(
        f"Temps moyen : "
        f"{total / successful:.1f} secondes/article"
    )

print()
print(f"Résultats sauvegardés dans :")
print(OUTPUT)

print()
print("IMPORTANT : SQLite n'a PAS été modifiée.")
print("=" * 90)
