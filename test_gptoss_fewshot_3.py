import sqlite3
import requests
import json
import time

DB = r"C:\Users\yass_\cgi-media-monitor\database\articles.db"
URL = "http://localhost:11434/api/chat"
MODEL = "gpt-oss:120b-cloud"

EXPECTED = {
    250: "Negative",
    314: "Neutral",
    337: "Negative",
}

ALL_LABELS = {
    183: "Positive",
    210: "Positive",
    219: "Negative",
    250: "Negative",
    268: "Neutral",
    279: "Negative",
    280: "Neutral",
    282: "Positive",
    314: "Neutral",
    325: "Negative",
    337: "Negative",
    340: "Negative",
    341: "Negative",
}

BASE_PROMPT = """
Tu es un analyste de sentiment spécialisé dans les articles concernant CGI.

Tu dois reproduire la logique de classification illustrée par les exemples.

Positive :
l'article présente CGI, sa situation, ses résultats ou ses actions de manière
globalement favorable.

Negative :
l'article présente CGI, sa situation, ses résultats ou ses actions de manière
globalement défavorable, problématique, conflictuelle ou avec une conséquence négative.

Neutral :
l'article est principalement factuel ou descriptif sans orientation clairement positive
ou négative envers CGI.

Important :
- Une nomination n'est pas automatiquement Positive.
- Un investissement ou un projet n'est pas automatiquement Positive.
- Un événement juridique n'est pas automatiquement Negative.
- Ne te base pas sur un mot isolé.
- Distingue CGI des autres organisations.
- Utilise le sens global de l'article.
- Les exemples sont uniquement des références de décision.
- Analyse réellement l'article cible.

Réponds uniquement avec :
{"sentiment":"Positive"}
{"sentiment":"Negative"}
{"sentiment":"Neutral"}
"""

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = conn.cursor()

ids = list(ALL_LABELS.keys())
placeholders = ",".join("?" for _ in ids)

cur.execute(
    f"""
    SELECT id, title, summary, content
    FROM articles
    WHERE id IN ({placeholders})
    """,
    ids
)

rows = {row[0]: row for row in cur.fetchall()}
conn.close()

correct = 0
start_total = time.time()

for target_id, expected in EXPECTED.items():

    examples = []

    for example_id, label in ALL_LABELS.items():
        if example_id == target_id:
            continue

        row = rows[example_id]
        _, title, summary, _ = row

        examples.append(
            f"""
EXEMPLE {example_id}
Titre : {title or ""}
Résumé : {summary or ""}
Label de référence : {label}
"""
        )

    _, title, summary, content = rows[target_id]

    target_article = f"""
ARTICLE CIBLE

TITRE:
{title or ""}

RÉSUMÉ:
{summary or ""}

CONTENU:
{content or ""}
"""

    prompt = (
        BASE_PROMPT
        + "\n\nEXEMPLES DE RÉFÉRENCE :\n"
        + "\n".join(examples)
        + "\n\n"
        + target_article
    )

    start = time.time()

    try:
        r = requests.post(
            URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "format": "json",
                "think": False,
                "options": {
                    "temperature": 0
                }
            },
            timeout=60
        )

        r.raise_for_status()

        data = r.json()
        text = data.get("message", {}).get("content", "").strip()

        result = json.loads(text)
        predicted = result.get("sentiment")

        elapsed = time.time() - start

        status = "OK" if predicted == expected else "ERREUR"

        if predicted == expected:
            correct += 1

        print(
            f"ID={target_id} | "
            f"Attendu={expected} | "
            f"GPT-OSS={predicted} | "
            f"{status} | {elapsed:.1f}s"
        )

    except Exception as e:
        print(f"ID={target_id} | ERROR | {e}")

total = time.time() - start_total

print()
print("=" * 70)
print("RESULTAT FEW-SHOT")
print("=" * 70)
print(f"Corrects        : {correct}/3")
print(f"Accuracy        : {correct/3*100:.2f}%")
print(f"Temps total     : {total:.1f}s")
print("=" * 70)
print("SQLite : AUCUNE MODIFICATION")
