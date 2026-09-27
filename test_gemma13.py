import sqlite3
import requests
import json
import time

DB = r"C:\Users\yass_\cgi-media-monitor\database\articles.db"
URL = "http://localhost:11434/api/generate"
MODEL = "gemma3:1b"

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
Tu dois classer le sentiment d'un article concernant CGI.

Positive = présentation globalement favorable.
Negative = présentation globalement défavorable, avec problème, conflit, échec ou conséquence négative.
Neutral = article factuel ou descriptif sans orientation claire.

Ne te base pas sur un mot isolé. Utilise le sens global.
Réponds uniquement :
{"sentiment":"Positive"}
{"sentiment":"Negative"}
ou
{"sentiment":"Neutral"}
"""

conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = conn.cursor()

ids = list(EXPECTED.keys())
placeholders = ",".join("?" for _ in ids)

cur.execute(
    f"""
    SELECT id, title, summary
    FROM articles
    WHERE id IN ({placeholders})
    ORDER BY id
    """,
    ids
)

rows = cur.fetchall()
conn.close()

correct = 0
start_total = time.time()

for i, (article_id, title, summary) in enumerate(rows, 1):

    prompt = (
        PROMPT
        + "\n\nTITRE:\n"
        + (title or "")
        + "\n\nRÉSUMÉ:\n"
        + (summary or "")
    )

    try:
        start = time.time()

        r = requests.post(
            URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0,
                    "num_predict": 16
                }
            },
            timeout=30
        )

        result = json.loads(r.json()["response"])
        predicted = result.get("sentiment")
        expected = EXPECTED[article_id]

        elapsed = time.time() - start

        if predicted == expected:
            correct += 1
            status = "OK"
        else:
            status = "ERREUR"

        print(
            f"[{i:02}/13] ID={article_id} | "
            f"Attendu={expected} | Qwen={predicted} | "
            f"{status} | {elapsed:.1f}s"
        )

    except Exception as e:
        print(f"[{i:02}/13] ID={article_id} | ERROR | {e}")

total = time.time() - start_total

print()
print("=" * 70)
print("RESULTAT")
print("=" * 70)
print(f"Corrects : {correct}/13")
print(f"Accuracy : {correct/13*100:.2f}%")
print(f"Temps total : {total:.1f}s")
print(f"Moyenne/article : {total/13:.1f}s")
print("SQLite : aucune modification")
