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

PROMPT = """
Tu fais une analyse de sentiment STRICTE d'un article concernant CGI.

OBJECTIF :
Déterminer l'orientation globale de l'article ENVERS CGI.

Positive :
L'article présente CGI, sa situation, ses résultats, ses actions ou leurs conséquences
comme favorables.

Negative :
L'article présente CGI, sa situation, ses résultats, ses actions ou leurs conséquences
comme défavorables, problématiques, conflictuelles, dommageables ou marquées par
un échec ou une conséquence négative.

Neutral :
L'article décrit principalement des faits, événements, procédures, nominations,
informations financières ou événements externes sans exprimer clairement une
orientation positive ou négative envers CGI.

RÈGLES CRITIQUES :
1. Ne considère jamais automatiquement un projet, investissement ou développement
   comme positif.
2. Ne considère jamais automatiquement un événement juridique comme négatif.
3. Une procédure, un procès ou une décision judiciaire peut rester NEUTRE si
   l'article rapporte simplement les faits sans évaluation défavorable de CGI.
4. Une information financière doit être interprétée dans son contexte global.
5. Une action ou déclaration d'une autre organisation ne doit pas être attribuée
   au sentiment de CGI.
6. Ne te base jamais sur un mot isolé.
7. Lis le titre, le résumé et le contenu ensemble.
8. Choisis l'orientation dominante de l'ensemble de l'article.
9. En cas d'absence d'orientation clairement favorable ou défavorable envers CGI,
   choisis Neutral.

Réponds UNIQUEMENT avec :
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

    start = time.time()

    try:
        r = requests.post(
            URL,
            json={
                "model": MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": PROMPT + "\n\nARTICLE :\n" + article[:15000]
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
        expected = EXPECTED[article_id]

        elapsed = time.time() - start
        status = "OK" if predicted == expected else "ERREUR"

        if predicted == expected:
            correct += 1

        print(
            f"[{i}/3] ID={article_id} | "
            f"Attendu={expected} | "
            f"GPT-OSS={predicted} | "
            f"{status} | {elapsed:.1f}s"
        )

    except Exception as e:
        print(f"[{i}/3] ID={article_id} | ERROR | {e}")

total = time.time() - start_total

print()
print("=" * 70)
print("TEST CIBLÉ DES 3 CAS DIFFICILES")
print("=" * 70)
print(f"Corrects        : {correct}/3")
print(f"Accuracy        : {correct/3*100:.2f}%")
print(f"Temps total     : {total:.1f}s")
print(f"Moyenne/article : {total/3:.1f}s")
print("=" * 70)
print("SQLite : AUCUNE MODIFICATION")
