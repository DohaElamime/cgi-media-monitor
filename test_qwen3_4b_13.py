import sqlite3
import requests
import json
import time

DB = r"C:\Users\yass_\cgi-media-monitor\database\articles.db"
URL = "http://localhost:11434/api/generate"
MODEL = "qwen3:4b"

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
Tu analyses le sentiment d'un article concernant CGI.

Positive = présentation globalement favorable de CGI ou de son action.
Negative = présentation globalement défavorable de CGI ou de son action,
avec problème, conflit, échec, dommage ou conséquence négative.
Neutral = article factuel ou descriptif sans orientation clairement positive ou négative.

Règles :
- une nomination n'est pas automatiquement positive ;
- un investissement ou un projet n'est pas automatiquement positif ;
- un événement juridique n'est pas automatiquement négatif ;
- ne te base pas sur un mot isolé ;
- utilise le sens global ;
- distingue CGI des autres organisations.

Réponds uniquement :
{"sentiment":"Positive"}
{"sentiment":"Negative"}
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
incorrect = 0
errors = 0
total_start = time.time()

for i, (article_id, title, summary) in enumerate(rows, 1):

    prompt = (
        PROMPT
        + "\n\nTITRE:\n"
        + (title or "")
        + "\n\nRÉSUMÉ:\n"
        + (summary or "")
    )

    start = time.time()

    try:
        r = requests.post(
            URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "think": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0,
                    "num_predict": 16,
                    "num_ctx": 2048
                }
            },
            timeout=60
        )

        r.raise_for_status()

        result = json.loads(r.json()["response"])
        predicted = result.get("sentiment")
        expected = EXPECTED[article_id]

        elapsed = time.time() - start

        if predicted == expected:
            correct += 1
            status = "OK"
        else:
            incorrect += 1
            status = "ERREUR"

        print(
            f"[{i:02}/13] "
            f"ID={article_id} | "
            f"Attendu={expected:8} | "
            f"Qwen4B={str(predicted):8} | "
            f"{status} | {elapsed:.1f}s"
        )

    except Exception as e:
        errors += 1
        elapsed = time.time() - start
        print(
            f"[{i:02}/13] "
            f"ID={article_id} | ERROR | "
            f"{elapsed:.1f}s | {e}"
        )

total = time.time() - total_start

print()
print("=" * 70)
print("RESULTAT QWEN3 4B")
print("=" * 70)
print(f"Corrects        : {correct}/13")
print(f"Incorrects      : {incorrect}")
print(f"Erreurs API     : {errors}")
print(f"Accuracy        : {correct/13*100:.2f}%")
print(f"Temps total     : {total:.1f}s")
print(f"Moyenne/article : {total/13:.1f}s")
print("=" * 70)
print("SQLite : AUCUNE MODIFICATION")
