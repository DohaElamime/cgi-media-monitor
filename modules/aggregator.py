from modules.sources.ddgs_source import search_ddgs
from modules.sources.google_news_source import search_google_news


def remove_duplicates(articles):

    unique = {}

    for article in articles:

        url = article["url"]

        unique[url] = article

    return list(unique.values())


def collect_articles():

    articles = []

    print("\n===== DDGS =====")

    articles.extend(search_ddgs())

    print("\n===== GOOGLE NEWS =====")

    articles.extend(search_google_news())

    print(f"\nAvant suppression des doublons : {len(articles)}")

    articles = remove_duplicates(articles)

    print(f"Après suppression des doublons : {len(articles)}")

    return articles