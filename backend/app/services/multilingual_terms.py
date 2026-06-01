import re
import unicodedata
from collections import Counter

from app.core.config import settings
from app.core.paths import SAMPLE_DIR
from app.services.json_store import read_json


TERMS_PATH = SAMPLE_DIR / "multilingual_query_terms.json"


def tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return [token for token in re.findall(r"[a-z0-9_]{3,}", normalized) if token]


def load_multilingual_terms() -> dict[str, list[str]]:
    if not TERMS_PATH.exists():
        return {}
    data = read_json(TERMS_PATH)
    return {str(category): [str(term) for term in terms] for category, terms in data.items()}


def expand_query_tokens(query: str) -> Counter[str]:
    tokens = Counter(tokenize(query))
    if not settings.multilingual_query_terms_enabled or not tokens:
        return tokens

    term_map = load_multilingual_terms()
    query_token_set = set(tokens)
    for terms in term_map.values():
        category_tokens = Counter(token for term in terms for token in tokenize(term))
        if not category_tokens:
            continue
        if query_token_set.intersection(category_tokens):
            for token, count in category_tokens.items():
                tokens[token] += settings.multilingual_query_term_weight * count
    return tokens


def infer_support_categories(text: str, *, max_categories: int = 3) -> list[str]:
    text_tokens = Counter(tokenize(text))
    if not text_tokens:
        return []
    scored: list[tuple[float, str]] = []
    for category_id, terms in load_multilingual_terms().items():
        category_tokens = Counter(token for term in terms for token in tokenize(term))
        score = sum(text_tokens.get(token, 0) * weight for token, weight in category_tokens.items())
        if score:
            scored.append((score, category_id))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [category_id for _, category_id in scored[:max_categories]]
