from urllib.parse import urlparse

from config import ALLOWED_DOMAINS


def is_allowed_domain(url: str) -> bool:
    """
    Vérifie que l'URL appartient à un domaine autorisé.
    """

    try:

        domain = urlparse(url).netloc.lower()

        domain = domain.replace("www.", "")

        for allowed in ALLOWED_DOMAINS:

            if domain.endswith(allowed):
                return True

        return False

    except Exception:

        return False