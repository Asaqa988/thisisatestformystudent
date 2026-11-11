"""Knowledge base endpoints: what the AI is allowed to tell customers."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import KnowledgeArticle
from app.schemas import KnowledgeArticleIn, KnowledgeArticleList, KnowledgeArticleOut
from app.services import knowledge

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


def _out(article: KnowledgeArticle) -> KnowledgeArticleOut:
    return KnowledgeArticleOut(
        id=article.id, title=article.title, content=article.content, updated_at=article.updated_at
    )


@router.get("", response_model=KnowledgeArticleList)
def list_articles(db: Session = Depends(get_db)):
    return KnowledgeArticleList(
        items=[_out(a) for a in knowledge.list_articles(db)],
        total_chars=knowledge.total_chars(db),
    )


@router.post("", response_model=KnowledgeArticleOut, status_code=status.HTTP_201_CREATED)
def create_article(data: KnowledgeArticleIn, db: Session = Depends(get_db)):
    return _out(knowledge.create_article(db, data))


@router.put("/{article_id}", response_model=KnowledgeArticleOut)
def update_article(article_id: uuid.UUID, data: KnowledgeArticleIn, db: Session = Depends(get_db)):
    return _out(knowledge.update_article(db, article_id, data))


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: uuid.UUID, db: Session = Depends(get_db)):
    knowledge.delete_article(db, article_id)
