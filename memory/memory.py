import yaml

from memory.database import init_db, get_session, Category, Tag
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

DATABASE_CONFIG_PATH = 'config/database.yaml'


class Memory:
    def __init__(self):
        with open(DATABASE_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        db_path = config['database']['path']
        self.engine = init_db(db_path)

    def get_or_create_category(self, name: str) -> dict:
        session = get_session(self.engine)
        try:
            category = session.query(Category).filter_by(name=name).first()
            if not category:
                category = Category(name=name)
                session.add(category)
                session.commit()
                logger.info(f"Created new category: {name}")
            return {
                'id': category.id,
                'name': category.name,
                'wordpress_id': category.wordpress_id
            }
        finally:
            session.close()

    def get_or_create_tag(self, name: str) -> dict:
        session = get_session(self.engine)
        try:
            tag = session.query(Tag).filter_by(name=name).first()
            if not tag:
                tag = Tag(name=name)
                session.add(tag)
                session.commit()
                logger.info(f"Created new tag: {name}")
            return {
                'id': tag.id,
                'name': tag.name,
                'wordpress_id': tag.wordpress_id
            }
        finally:
            session.close()

    def get_all_categories(self) -> list[dict]:
        session = get_session(self.engine)
        try:
            return [
                {'id': c.id, 'name': c.name, 'wordpress_id': c.wordpress_id}
                for c in session.query(Category).all()
            ]
        finally:
            session.close()

    def get_all_tags(self) -> list[dict]:
        session = get_session(self.engine)
        try:
            return [
                {'id': t.id, 'name': t.name, 'wordpress_id': t.wordpress_id}
                for t in session.query(Tag).all()
            ]
        finally:
            session.close()
