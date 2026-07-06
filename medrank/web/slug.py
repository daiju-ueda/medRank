import re
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s_]+", "-", text) or "x"


def researcher_slug(id: str, name: str) -> str:
    return f"{id}-{slugify(name)}"


def id_from_slug(slug: str) -> str:
    return slug.split("-", 1)[0]
