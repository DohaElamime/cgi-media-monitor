from urllib.parse import urlparse

from ddgs import DDGS

from config import SEARCH_QUERIES, MAX_RESULTS
from modules.utils import is_allowed_domain


def search_ddgs():

    articles = []

    seen_urls = set()

    with DDGS() as ddgs:

        for query in SEARCH_QUERIES:

            print(f"Recherche : {query}")

            try:

                results = ddgs.text(
                    query,
                    max_results=MAX_RESULTS,
                )

                if not results:
                    continue

                for result in results:

                    url = result.get("href", "").strip()

                    if not url:
                        continue

                    if url in seen_urls:
                        continue

                    if not is_allowed_domain(url):
                        continue

                    seen_urls.add(url)

                    # Récupération automatique du domaine
                    source = urlparse(url).netloc.replace("www.", "")

                    articles.append({

                        "title": result.get("title", ""),

                        "url": url,

                        "body": result.get("body", ""),

                        "source": source,

                        "date": ""

                    })

            except Exception as e:

                print(f"Erreur DDGS : {e}")

    print(f"\nDDGS : {len(articles)} articles\n")

    return articles