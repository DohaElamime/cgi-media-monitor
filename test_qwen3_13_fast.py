import sqlite3
import requests
import json
import time

DB = r"C:\Users\yass_\cgi-media-monitor\database\articles.db"
URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:8b"

EXPECTED = {
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

PROMPT = """
Classe cet article concernant CGI en une seule catégorie :

Positive = présentation globalement favorable de CGI ou de son action.
Negative = présentation globalement défavorable, problème, conflit, échec ou conséquence négative.
Neutral = article factuel/descriptif sans orientation clairement positive ou négative.

Règles :
- nomination ≠ automatiquement positive
- investissement/projet ≠ automatiquement positif
- événement juridique ≠ automatiquement négatif
- article immobilier ≠ automatiquement positif
- utilise le sens global de l'article
- ne te base pas sur des mots isolés

Réponds uniquement :
{"sentiment":"Positive"}
ou
{"sentiment":"Negative"}
ou
{"sentiment":"Neutral"}
"""

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = conn.cursor()

placeholders = ",".join("?" * len(EXPECTED))
cur.execute(
    f"""
    SELECT id, title, summary, content
    FROM articles
    WHERE id IN ({placeholders})
    ORDER BY id
    """,
    list(EXPECTED.keys())
)

rows = cur.fetchall()
conn.close()

correct = 0
errors = 0

start_total = time.time()

for i, (article_id, title, summary, content) in enumerate(rows, 1):

    article = f"""
TITRE:
{title or ""}

RÉSUMÉ:
{summary or ""}

CONTENU:
{content or ""}
"""

    try:
        start = time.time()

        r = requests.post(
            URL,
            json={
                "model": MODEL,
                "prompt": PROMPT + "\nARTICLE:\n" + article[:12000],
                "stream": False,
                "format": "json",
                "think": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0,
                    "num_predict": 32,
                    "num_ctx": 8192
                }
            },
            timeout=60
        )

        result = json.loads(r.json()["response"])
        predicted = result.get("sentiment")
        expected = EXPECTED[article_id]

        elapsed = time.time() - start

        ok = predicted == expected

        if ok:
            correct += 1
            status = "OK"
        else:
            status = "ERREUR"

        print(
            f"[{i:02}/13] "
            f"ID={article_id} | "
            f"Attendu={expected:8} | "
            f"Qwen={str(predicted):8} | "
            f"{status} | "
            f"{elapsed:.1f}s"
        )

    except Exception as e:
        errors += 1
        print(f"[{i:02}/13] ID={article_id} | ERROR | {e}")

total = time.time() - start_total

print()
print("=" * 80)
print("RESULTAT")
print("=" * 80)
print(f"Corrects    : {correct}/13")
print(f"Erreurs     : {13 - correct - errors}")
print(f"Timeout/API : {errors}")
print(f"Temps total : {total:.1f}s")
print(f"Moyenne     : {total / len(rows):.1f}s/article")
print("=" * 80)
print("SQLite : aucune modification")
