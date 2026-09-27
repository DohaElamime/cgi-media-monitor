import sqlite3
import os
import sys
import feedparser

ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.insert(0, ROOT)

DATABASE = os.path.join(
    ROOT,
    "database",
    "articles.db"
)

conn = sqlite3.connect(DATABASE)
conn.row_factory = sqlite3.Row

article = conn.execute(
    "SELECT title, source, url FROM articles WHERE id=253"
).fetchone()

conn.close()

title = article["title"]
source = article["source"]

print("=" * 70)
print("TEST GOOGLE NEWS RSS")
print("=" * 70)

print()
print("TITRE =", title)
print("SOURCE =", source)

query = (
    '"' +
    title.replace(
        " - Le360",
        ""
    ) +
    '" ' +
    source
)

rss_url = (
    "https://news.google.com/rss/search?"
    "q=" + __import__("urllib.parse").parse.quote_plus(query) +
    "&hl=fr&gl=MA&ceid=MA:fr"
)

print()
print("RSS URL =")
print(rss_url)

feed = feedparser.parse(
    rss_url
)

print()
print("ENTRIES =", len(feed.entries))

for i, entry in enumerate(
    feed.entries,
    1
):

    print()
    print("=" * 70)
    print("ENTRY", i)
    print("=" * 70)

    print()
    print("TITLE:")
    print(entry.get("title"))

    print()
    print("LINK:")
    print(entry.get("link"))

    print()
    print("ID:")
    print(entry.get("id"))

    print()
    print("GUID:")
    print(entry.get("guid"))

    print()
    print("SOURCE:")
    print(entry.get("source"))

    print()
    print("SUMMARY:")
    print(
        entry.get(
            "summary",
            ""
        )[:2000]
    )

    print()
    print("ALL KEYS:")
    print(
        list(
            entry.keys()
        )
    )

    print()
    print("RAW ENTRY:")

    for key, value in entry.items():

        print(
            key,
            "=",
            value
        )