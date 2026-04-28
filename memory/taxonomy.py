"""Mixin for taxonomy (category and tag) operations."""

from typing import Any

from memory.database import Category, Tag, get_session
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class TaxonomyMixin:
    """Category and tag database operations."""

    def get_or_create_category(self, name: str) -> dict[str, Any]:
        """Get or create a category by name."""
        session = get_session(self.engine)
        try:
            category = session.query(Category).filter_by(name=name).first()
            if not category:
                category = Category(name=name)
                session.add(category)
                session.commit()
                logger.info(f'Created new category: {name}')
            return {
                'id': category.id,
                'name': category.name,
                'wordpress_id': category.wordpress_id,
            }
        finally:
            session.close()

    def get_or_create_tag(self, name: str) -> dict[str, Any]:
        """Get or create a tag by name."""
        session = get_session(self.engine)
        try:
            tag = session.query(Tag).filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                session.add(tag)
                session.commit()
                logger.info(f'Created new tag: {name}')
            return {'id': tag.id, 'name': tag.name, 'wordpress_id': tag.wordpress_id}
        finally:
            session.close()

    def get_all_categories(self) -> list[dict[str, Any]]:
        """Get all categories."""
        session = get_session(self.engine)
        try:
            return [
                {'id': c.id, 'name': c.name, 'wordpress_id': c.wordpress_id}
                for c in session.query(Category).all()
            ]
        finally:
            session.close()

    def get_all_tags(self) -> list[dict[str, Any]]:
        """Get all tags."""
        session = get_session(self.engine)
        try:
            return [
                {'id': t.id, 'name': t.name, 'wordpress_id': t.wordpress_id}
                for t in session.query(Tag).all()
            ]
        finally:
            session.close()

    def update_category_wordpress_id(self, name: str, wordpress_id: int) -> None:
        """Update the WordPress ID for a category."""
        session = get_session(self.engine)
        try:
            category = session.query(Category).filter_by(name=name).first()
            if category:
                category.wordpress_id = wordpress_id
                session.commit()
                logger.info(f"Updated category '{name}' wordpress_id={wordpress_id}")
        finally:
            session.close()

    def update_tag_wordpress_id(self, name: str, wordpress_id: int) -> None:
        """Update the WordPress ID for a tag."""
        session = get_session(self.engine)
        try:
            tag = session.query(Tag).filter_by(name=name).first()
            if tag:
                tag.wordpress_id = wordpress_id
                session.commit()
                logger.info(f"Updated tag '{name}' wordpress_id={wordpress_id}")
        finally:
            session.close()
