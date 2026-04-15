import yaml

from memory.database import init_db, get_session, Category, Tag, PendingApproval, OAuthToken
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

    def create_pending_approval(self, data: dict) -> dict:
        session = get_session(self.engine)
        try:
            approval = PendingApproval(**data)
            session.add(approval)
            session.commit()
            logger.info(f"Created pending approval: {approval.token[:20]}...")
            return {
                'id': approval.id,
                'token': approval.token,
                'status': approval.status,
                'expires_at': approval.expires_at.isoformat()
            }
        finally:
            session.close()

    def get_pending_approval(self, token: str) -> dict | None:
        session = get_session(self.engine)
        try:
            approval = session.query(PendingApproval).filter_by(token=token).first()
            if not approval:
                return None
            return {
                'id': approval.id,
                'token': approval.token,
                'status': approval.status,
                'created_at': approval.created_at.isoformat(),
                'expires_at': approval.expires_at.isoformat(),
                'resolved_at': approval.resolved_at.isoformat() if approval.resolved_at else None,
                'blog_title': approval.blog_title,
                'blog_content': approval.blog_content,
                'blog_excerpt': approval.blog_excerpt,
                'taxonomy_data': approval.taxonomy_data,
                'evaluation_data': approval.evaluation_data,
                'summaries_data': approval.summaries_data,
                'scores_data': approval.scores_data,
                'feedback': approval.feedback
            }
        finally:
            session.close()

    def update_approval_status(self, token: str, status: str, feedback: str = None):
        from datetime import datetime
        session = get_session(self.engine)
        try:
            approval = session.query(PendingApproval).filter_by(token=token).first()
            if approval:
                approval.status = status
                approval.resolved_at = datetime.utcnow()
                if feedback:
                    approval.feedback = feedback
                session.commit()
                logger.info(f"Updated approval {token[:20]}... to status={status}")
        finally:
            session.close()

    def get_expired_approvals(self) -> list[dict]:
        from datetime import datetime
        session = get_session(self.engine)
        try:
            expired = session.query(PendingApproval).filter(
                PendingApproval.status == 'pending',
                PendingApproval.expires_at < datetime.utcnow()
            ).all()
            return [{'token': a.token, 'blog_title': a.blog_title} for a in expired]
        finally:
            session.close()

    def update_category_wordpress_id(self, name: str, wordpress_id: int):
        session = get_session(self.engine)
        try:
            category = session.query(Category).filter_by(name=name).first()
            if category:
                category.wordpress_id = wordpress_id
                session.commit()
                logger.info(f"Updated category '{name}' wordpress_id={wordpress_id}")
        finally:
            session.close()

    def update_tag_wordpress_id(self, name: str, wordpress_id: int):
        session = get_session(self.engine)
        try:
            tag = session.query(Tag).filter_by(name=name).first()
            if tag:
                tag.wordpress_id = wordpress_id
                session.commit()
                logger.info(f"Updated tag '{name}' wordpress_id={wordpress_id}")
        finally:
            session.close()

    def save_oauth_token(self, service: str, access_token: str, blog_id: str = None, blog_url: str = None):
        session = get_session(self.engine)
        try:
            token = session.query(OAuthToken).filter_by(service=service).first()
            if token:
                token.access_token = access_token
                token.blog_id = blog_id
                token.blog_url = blog_url
            else:
                token = OAuthToken(
                    service=service,
                    access_token=access_token,
                    blog_id=blog_id,
                    blog_url=blog_url
                )
                session.add(token)
            session.commit()
            logger.info(f"Saved OAuth token for {service}")
        finally:
            session.close()

    def get_oauth_token(self, service: str) -> str | None:
        session = get_session(self.engine)
        try:
            token = session.query(OAuthToken).filter_by(service=service).first()
            return token.access_token if token else None
        finally:
            session.close()
