import sqlite3
import requests
import json
import time

DB = r"C:\Users\yass_\cgi-media-monitor\database\articles.db"
URL = "http://localhost:11434/api/chat"
MODEL = "gpt-oss:120b-cloud"

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
Tu es un analyste de sentiment spécialisé dans les articles de presse concernant CGI.

Analyse l'article dans son ensemble.

Positive :
l'article présente CGI, sa situation ou son action comme globalement favorable,
avec une appréciation favorable ou des conséquences favorables.

Negative :
l'article présente CGI, sa situation ou son action comme globalement défavorable,
avec problème, échec, conflit, dommage, conséquence négative ou critique.

Neutral :
l'article est principalement factuel ou descriptif et ne présente pas
d'orientation clairement positive ou négative envers CGI.

Règles importantes :
- Une nomination ou un changement de dirigeant n'est PAS automatiquement positif.
- Un investissement ou un projet n'est PAS automatiquement positif.
- Un événement juridique n'est PAS automatiquement négatif.
- Ne juge jamais le sentiment à partir d'un mot isolé.
- Distingue les faits concernant CGI de ceux concernant d'autres organisations.
- Prends en compte le titre, le résumé et le contenu.
- Choisis exactement UNE catégorie.

Réponds UNIQUEMENT avec un JSON valide :
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
incorrect = 0
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
        response_text = data.get("message", {}).get("content", "").strip()

        if not response_text:
            raise ValueError("Réponse vide")

        result = json.loads(response_text)
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
            f"GPT-OSS={str(predicted):8} | "
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

total = time.time() - start_total

print()
print("=" * 70)
print("RESULTAT GPT-OSS 120B CLOUD - 13 ARTICLES COMPLETS")
print("=" * 70)
print(f"Corrects        : {correct}/13")
print(f"Incorrects      : {incorrect}")
print(f"Erreurs API     : {errors}")
print(f"Accuracy        : {correct/13*100:.2f}%")
print(f"Temps total     : {total:.1f}s")
print(f"Moyenne/article : {total/13:.1f}s")
print("=" * 70)
print("SQLite : AUCUNE MODIFICATION")
