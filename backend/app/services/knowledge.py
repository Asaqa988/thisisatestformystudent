"""Knowledge base: storage and the context given to the AI."""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.models import KnowledgeArticle
from app.schemas import KnowledgeArticleIn

# When the knowledge base is too big to send whole, this many articles go in.
TOP_ARTICLES = 8


def list_articles(db: Session) -> list[KnowledgeArticle]:
    return list(db.scalars(select(KnowledgeArticle).order_by(KnowledgeArticle.title)))


def total_chars(db: Session) -> int:
    return db.scalar(
        select(
            func.coalesce(
                func.sum(
                    func.length(KnowledgeArticle.title) + func.length(KnowledgeArticle.content)
                ),
                0,
            )
        )
    )


def get_article(db: Session, article_id: uuid.UUID) -> KnowledgeArticle:
    article = db.get(KnowledgeArticle, article_id)
    if article is None:
        raise NotFound("That knowledge article does not exist.")
    return article


def create_article(db: Session, data: KnowledgeArticleIn) -> KnowledgeArticle:
    article = KnowledgeArticle(
        id=uuid.uuid4(), title=data.title.strip(), content=data.content.strip()
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def update_article(
    db: Session, article_id: uuid.UUID, data: KnowledgeArticleIn
) -> KnowledgeArticle:
    article = get_article(db, article_id)
    article.title = data.title.strip()
    article.content = data.content.strip()
    article.updated_at = datetime.now(tz=UTC)
    db.commit()
    db.refresh(article)
    return article


def delete_article(db: Session, article_id: uuid.UUID) -> None:
    db.delete(get_article(db, article_id))
    db.commit()


def context_for(db: Session, query_text: str, full_context_chars: int) -> tuple[str, bool]:
    """The knowledge to show the model, and whether it is the whole knowledge base.

    Small knowledge bases are sent in full: nothing can be missed, and prompt
    caching makes repeating it cheap. Large ones are searched with PostgreSQL
    full-text search, and only the best matches are sent.
    """
    if total_chars(db) <= full_context_chars:
        articles = list_articles(db)
        return render(articles), True

    words = search_words(query_text)
    if not words:
        return "", False
    # Any word may match ("|"); articles matching more of them rank higher.
    query = func.to_tsquery("simple", " | ".join(words))
    ranked = db.scalars(
        select(KnowledgeArticle)
        .where(KnowledgeArticle.search.op("@@")(query))
        .order_by(func.ts_rank(KnowledgeArticle.search, query).desc())
        .limit(TOP_ARTICLES)
    ).all()
    return render(list(ranked)), False


def search_words(text: str, limit: int = 40) -> list[str]:
    """Plain words from the customer's text, safe to put in a search query.

    \w matches letters in any script, so Arabic words are kept as they are.
    """
    seen: list[str] = []
    for word in re.findall(r"\w+", text.lower()):
        if len(word) > 1 and word not in seen:
            seen.append(word)
    return seen[-limit:]


def render(articles: list[KnowledgeArticle]) -> str:
    if not articles:
        return ""
    return "\n\n".join(f'<article title="{a.title}">\n{a.content}\n</article>' for a in articles)
