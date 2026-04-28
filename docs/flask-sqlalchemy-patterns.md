# Flask-SQLAlchemy Patterns

> **TL;DR**: Use declarative models with proper relationships. Always use transactions. Handle migrations with Alembic.

## Model Definition

### ✅ GOOD - Declarative SQLAlchemy models

```python
# models/article.py
from datetime import datetime
from typing import Any

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import db


class Article(db.Model):
    """Article model for storing blog posts."""
    
    __tablename__ = 'articles'
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Columns
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(String(500))
    sport: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    # Foreign keys
    author_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id'),
        nullable=False,
    )
    
    # Relationships
    author: Mapped['User'] = relationship('User', back_populates='articles')
    tags: Mapped[list['Tag']] = relationship(
        'Tag',
        secondary='article_tags',
        back_populates='articles',
    )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert article to dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'content': self.content,
            'summary': self.summary,
            'sport': self.sport,
            'published': self.published,
            'author_id': self.author_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    def __repr__(self) -> str:
        return f'<Article {self.id}: {self.title[:30]}>'
```

### ❌ BAD - Missing types and relationships

```python
# Bad patterns to avoid
class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    content = db.Column(db.Text)
    # No type hints
    # No relationships defined
    # No __tablename__
```

## Database Initialization

### ✅ GOOD - Centralized database configuration

```python
# database.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def init_db(app: Flask) -> None:
    """Initialize database with app."""
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config.get(
        'DATABASE_URL',
        'sqlite:///app.db'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
```

## Queries

### ✅ GOOD - Type-safe queries with relationships

```python
from sqlalchemy import select
from sqlalchemy.orm import Session


class ArticleRepository:
    """Repository for Article database operations."""
    
    def __init__(self, session: Session) -> None:
        self.session = session
    
    def get_by_id(self, article_id: int) -> Article | None:
        """Get article by ID."""
        return self.session.get(Article, article_id)
    
    def get_by_slug(self, slug: str) -> Article | None:
        """Get article by slug."""
        return (
            self.session
            .query(Article)
            .filter(Article.slug == slug)
            .first()
        )
    
    def list_by_sport(
        self,
        sport: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Article]:
        """List articles by sport."""
        return (
            self.session
            .query(Article)
            .filter(Article.sport == sport)
            .order_by(Article.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
    
    def create(self, article_data: dict[str, Any]) -> Article:
        """Create a new article."""
        article = Article(**article_data)
        self.session.add(article)
        self.session.commit()
        return article
    
    def update(self, article_id: int, data: dict[str, Any]) -> Article | None:
        """Update an article."""
        article = self.get_by_id(article_id)
        if article is None:
            return None
        
        for key, value in data.items():
            setattr(article, key, value)
        
        self.session.commit()
        return article
    
    def delete(self, article_id: int) -> bool:
        """Delete an article."""
        article = self.get_by_id(article_id)
        if article is None:
            return False
        
        self.session.delete(article)
        self.session.commit()
        return True
```

### ❌ BAD - Raw SQL everywhere

```python
# Avoid this pattern
def get_articles():
    result = db.session.execute(text("SELECT * FROM articles"))
    return result.fetchall()
```

## Transactions

### ✅ GOOD - Explicit transaction handling

```python
from sqlalchemy.exc import SQLAlchemyError


def bulk_create_articles(articles_data: list[dict[str, Any]]) -> list[Article]:
    """Bulk create articles with transaction."""
    articles = []
    
    try:
        for data in articles_data:
            article = Article(**data)
            articles.append(article)
            db.session.add(article)
        
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        raise DatabaseError(f"Failed to create articles: {e}") from e
    
    return articles
```

## Relationships

### ✅ GOOD - Proper relationship definitions

```python
# models/user.py
class User(db.Model):
    __tablename__ = 'users'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # One-to-many relationship
    articles: Mapped[list['Article']] = relationship(
        'Article',
        back_populates='author',
        cascade='all, delete-orphan',
    )


# models/tag.py (many-to-many)
article_tags = db.Table(
    'article_tags',
    db.Column('article_id', Integer, ForeignKey('articles.id'), primary_key=True),
    db.Column('tag_id', Integer, ForeignKey('tags.id'), primary_key=True),
)


class Tag(db.Model):
    __tablename__ = 'tags'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    
    articles: Mapped[list['Article']] = relationship(
        'Article',
        secondary=article_tags,
        back_populates='tags',
    )
```

## Migrations

### ✅ GOOD - Alembic migrations

```bash
# Generate migration
alembic revision --autogenerate -m "Add articles table"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Migration example

```python
# alembic/versions/2024_01_15_add_articles.py
"""Add articles table

Revision ID: abc123
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'abc123'
down_revision = 'previous_revision'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sport', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_articles_sport', 'articles', ['sport'])


def downgrade() -> None:
    op.drop_index('ix_articles_sport')
    op.drop_table('articles')
```

## Summary Checklist

- [ ] Use declarative models with `Mapped` types
- [ ] Define `__tablename__` explicitly
- [ ] Add proper relationships (one-to-many, many-to-many)
- [ ] Use repositories for database operations
- [ ] Handle transactions with try/except
- [ ] Use Alembic for migrations
- [ ] Add `to_dict()` method for serialization
- [ ] Add `__repr__` for debugging