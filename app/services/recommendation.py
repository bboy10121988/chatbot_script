from __future__ import annotations

import re
from typing import List, Tuple
from difflib import SequenceMatcher

from sqlalchemy import or_, select

from ..extensions import db
from ..models import KeywordRule, Product, Synonym


def normalize(text: str) -> str:
    return text.strip().lower()


def expand_terms(tenant_id: int, text: str) -> List[str]:
    base = [text]
    # Pull synonyms where term appears in text
    syns = (
        db.session.query(Synonym)
        .filter(Synonym.tenant_id == tenant_id)
        .all()
    )
    terms = set(base)
    for s in syns:
        t = s.term.lower()
        if t in text:
            for alt in (s.synonyms or []):
                if isinstance(alt, str) and alt:
                    terms.add(alt.lower())
    return list(terms)


def match_rules(tenant_id: int, text: str) -> List[KeywordRule]:
    text_norm = normalize(text)
    rules = (
        db.session.query(KeywordRule)
        .filter(KeywordRule.tenant_id == tenant_id, KeywordRule.is_active.is_(True))
        .order_by(KeywordRule.priority.desc())
        .all()
    )
    matched: List[KeywordRule] = []
    for r in rules:
        trig = (r.trigger_text or "").lower()
        if not trig:
            continue
        if r.match_type == 'exact' and text_norm == trig:
            matched.append(r)
        elif r.match_type == 'prefix' and text_norm.startswith(trig):
            matched.append(r)
        elif r.match_type == 'contains' and trig in text_norm:
            matched.append(r)
        elif r.match_type == 'regex':
            try:
                if re.search(trig, text_norm):
                    matched.append(r)
            except re.error:
                continue
    return matched


def fuzzy_rules(tenant_id: int, text: str, threshold: float = 0.72) -> List[KeywordRule]:
    rules = (
        db.session.query(KeywordRule)
        .filter(KeywordRule.tenant_id == tenant_id, KeywordRule.is_active.is_(True))
        .all()
    )
    cand: List[Tuple[float, KeywordRule]] = []
    for r in rules:
        trig = (r.trigger_text or "").lower()
        if not trig:
            continue
        score = SequenceMatcher(None, text, trig).ratio()
        if score >= threshold:
            cand.append((score, r))
    cand.sort(key=lambda x: (x[0], x[1].priority), reverse=True)
    return [r for _, r in cand[:5]]


def fetch_products_by_ids(tenant_id: int, ids: List[int], limit: int = 5) -> List[Product]:
    if not ids:
        return []
    q = (
        db.session.query(Product)
        .filter(Product.tenant_id == tenant_id, Product.is_active.is_(True), Product.id.in_(ids))
        .limit(limit)
    )
    # maintain input order
    found = {p.id: p for p in q}
    ordered = [found[i] for i in ids if i in found]
    return ordered[:limit]


def fallback_search(tenant_id: int, terms: List[str], limit: int = 5) -> List[Product]:
    if not terms:
        return []
    like_clauses = [Product.name.ilike(f"%{t}%") for t in terms if t]
    q = (
        db.session.query(Product)
        .filter(Product.tenant_id == tenant_id, Product.is_active.is_(True))
        .filter(or_(*like_clauses))
        .limit(limit)
        .all()
    )
    return q


def recommend(tenant_id: int, text: str, limit: int = 5) -> Tuple[str | None, List[Product]]:
    text_norm = normalize(text)
    terms = expand_terms(tenant_id, text_norm)
    rules = match_rules(tenant_id, text_norm)
    if not rules:
        rules = fuzzy_rules(tenant_id, text_norm)

    response_text = None
    products: List[Product] = []
    for r in rules:
        if r.response_text and not response_text:
            response_text = r.response_text
        ids = []
        if isinstance(r.product_ids, list):
            ids = [int(x) for x in r.product_ids if isinstance(x, (int, str)) and str(x).isdigit()]
        products.extend(fetch_products_by_ids(tenant_id, ids, limit=limit))
        if len(products) >= limit:
            break
    # de-dup
    seen = set()
    deduped: List[Product] = []
    for p in products:
        if p.id in seen:
            continue
        seen.add(p.id)
        deduped.append(p)
    products = deduped[:limit]

    if not products:
        products = fallback_search(tenant_id, terms, limit=limit)
    return response_text, products
