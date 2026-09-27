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
Tu analyses le sentiment d'un article concernant CGI.

Positive = l'article présente CGI ou une action de CGI de manière globalement favorable.
Negative = l'article présente CGI ou une action de CGI de manière globalement défavorable,
avec problème, conflit, échec, dommage ou conséquence négative.
Neutral = article principalement factuel ou descriptif sans orientation claire.

Règles :
- une nomination n'est pas automatiquement positive ;
- un investissement ou un projet n'est pas automatiquement positif ;
- un événement juridique n'est pas automatiquement négatif ;
- ne juge pas le sentiment à partir d'un mot isolé ;
- utilise le sens global de l'article ;
- distingue CGI des autres organisations.

Réponds uniquement avec :
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
    SELECT id, title, summary, content
    FROM articles
    WHERE id IN ({placeholders})
    ORDER BY id
    """,
    ids
)

rows = cur.fetchall()
conn.close()

correct = 0
errors = 0
total_start = time.time()

for i, (article_id, title, summary, content) in enumerate(rows, 1):

    # On garde le début du contenu pour réduire fortement le temps CPU
    content_short = (content or "")[:4000]

    article = f"""
TITRE:
{title or ""}

RÉSUMÉ:
{summary or ""}

CONTENU:
{content_short}
"""

    start = time.time()

    try:
        r = requests.post(
            URL,
            json={
                "model": MODEL,
                "prompt": PROMPT + "\nARTICLE:\n" + article,
                "stream": False,
                "format": "json",
                "think": False,
                "keep_alive": -1,
                "options": {
                    "temperature": 0,
                    "num_predict": 32,
                    "num_ctx": 4096
                }
            },
            timeout=90
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
        elapsed = time.time() - start
        print(
            f"[{i:02}/13] "
            f"ID={article_id} | ERROR | "
            f"{elapsed:.1f}s | {e}"
        )

total = time.time() - total_start

print()
print("=" * 80)
print("RESULTAT FINAL")
print("=" * 80)
print(f"Corrects     : {correct}/13")
print(f"Incorrects   : {13 - correct - errors}")
print(f"Erreurs API  : {errors}")
print(f"Temps total  : {total:.1f}s")
print(f"Moyenne      : {total/13:.1f}s/article")
print("=" * 80)
print("SQLite : AUCUNE MODIFICATION")
