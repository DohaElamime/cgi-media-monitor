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

PROMPT_PASS1 = """
Tu es un analyste de sentiment spécialisé dans les articles concernant CGI.

Classe l'article dans UNE seule catégorie :

Positive :
l'article présente CGI, sa situation, ses résultats ou ses actions de manière
globalement favorable.

Negative :
l'article présente CGI, sa situation, ses résultats ou ses actions de manière
globalement défavorable, problématique, conflictuelle, dommageable ou avec
une conséquence négative.

Neutral :
l'article est principalement factuel ou descriptif sans orientation clairement
positive ou négative envers CGI.

Règles :
- une nomination n'est pas automatiquement Positive ;
- un investissement ou un projet n'est pas automatiquement Positive ;
- un événement juridique n'est pas automatiquement Negative ;
- ne te base pas sur un mot isolé ;
- distingue CGI des autres organisations ;
- analyse le titre, le résumé et le contenu ensemble.

Réponds uniquement en JSON :
{"sentiment":"Positive"}
{"sentiment":"Negative"}
{"sentiment":"Neutral"}
"""

PROMPT_PASS2 = """
Tu es un VÉRIFICATEUR de sentiment d'articles concernant CGI.

Une première analyse a proposé un sentiment. Tu dois maintenant RELIRE L'ARTICLE
et vérifier cette proposition.

Ne conserve la première proposition que si elle correspond réellement au sens
global de l'article.

Définitions :

Positive :
présentation globalement favorable de CGI ou de ses actions.

Negative :
présentation globalement défavorable de CGI ou de ses actions, avec problème,
conflit, échec, dommage ou conséquence négative.

Neutral :
présentation essentiellement factuelle ou descriptive, sans orientation claire.

Règles critiques :
- nomination ≠ automatiquement positive ;
- investissement/projet ≠ automatiquement positif ;
- événement juridique ≠ automatiquement négatif ;
- une information concernant une autre organisation ne définit pas forcément
  le sentiment envers CGI ;
- ne te base pas sur un mot isolé ;
- utilise le sens global du titre, du résumé et du contenu ;
- tu PEUX corriger la première proposition.

Réponds uniquement avec :
{"sentiment":"Positive"}
{"sentiment":"Negative"}
{"sentiment":"Neutral"}
"""

def call_model(prompt):
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

    if not text:
        raise ValueError("Réponse vide")

    result = json.loads(text)
    sentiment = result.get("sentiment")

    if sentiment not in ("Positive", "Negative", "Neutral"):
        raise ValueError(f"Sentiment invalide : {sentiment}")

    return sentiment

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
agreements = 0
disagreements = 0

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
        # PASS 1
        start1 = time.time()

        first_prompt = (
            PROMPT_PASS1
            + "\n\nARTICLE :\n"
            + article[:15000]
        )

        first = call_model(first_prompt)
        time1 = time.time() - start1

        # PASS 2
        start2 = time.time()

        second_prompt = (
            PROMPT_PASS2
            + "\n\nARTICLE :\n"
            + article[:15000]
            + "\n\nPREMIÈRE PROPOSITION : "
            + first
        )

        second = call_model(second_prompt)
        time2 = time.time() - start2

        expected = EXPECTED[article_id]

        if first == second:
            agreements += 1
        else:
            disagreements += 1

        if second == expected:
            correct += 1
            status = "OK"
        else:
            incorrect += 1
            status = "ERREUR"

        print(
            f"[{i:02}/13] "
            f"ID={article_id} | "
            f"Attendu={expected:8} | "
            f"P1={first:8} | "
            f"P2={second:8} | "
            f"{status} | "
            f"{time1:.1f}s + {time2:.1f}s"
        )

    except Exception as e:
        errors += 1
        print(
            f"[{i:02}/13] "
            f"ID={article_id} | ERROR | {e}"
        )

total = time.time() - start_total

print()
print("=" * 80)
print("RESULTAT GPT-OSS 120B CLOUD - DOUBLE PASSE")
print("=" * 80)
print(f"Corrects P2          : {correct}/13")
print(f"Incorrects P2        : {incorrect}")
print(f"Erreurs API          : {errors}")
print(f"Accuracy finale      : {correct/13*100:.2f}%")
print(f"Accords P1/P2        : {agreements}/13")
print(f"Désaccords P1/P2     : {disagreements}/13")
print(f"Temps total          : {total:.1f}s")
print(f"Moyenne/article      : {total/13:.1f}s")
print("=" * 80)
print("SQLite : AUCUNE MODIFICATION")
