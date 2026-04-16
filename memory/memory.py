import yaml

from memory.database import init_db, get_session, Category, Tag, PendingApproval, OAuthToken, Article, ArticleSummary, Summary, Evaluation, WorkflowRun
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

DATABASE_CONFIG_PATH = 'config/database.yaml'


class Memory:
    def __init__(self):
        with open(DATABASE_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        db_path = config['database']['path']
        self.retention_days = config['database'].get('retention_days', 30)
        self.engine = init_db(db_path)

    def get_seen_urls(self) -> set:
        session = get_session(self.engine)
        try:
            urls = session.query(Article.url).all()
            return {url for (url,) in urls}
        finally:
            session.close()

    def save_articles(self, articles: list[dict]):
        from datetime import datetime
        session = get_session(self.engine)
        try:
            for article in articles:
                url = article.get('url')
                if not url:
                    continue
                existing = session.query(Article).filter_by(url=url).first()
                if existing:
                    continue
                published_at = None
                if article.get('publishedAt'):
                    try:
                        published_at = datetime.fromisoformat(
                            article['publishedAt'].replace('Z', '+00:00')
                        )
                    except Exception:
                        pass
                session.add(Article(
                    title=article.get('title', ''),
                    url=url,
                    source=article.get('source'),
                    team=article.get('team'),
                    published_at=published_at
                ))
            session.commit()
            logger.info(f"Saved {len(articles)} articles to memory.")
        finally:
            session.close()

    def purge_old_articles(self):
        from datetime import datetime, timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=self.retention_days)
            count = session.query(Article).filter(Article.fetched_at < cutoff).delete()
            session.commit()
            if count:
                logger.info(f"Purged {count} articles older than {self.retention_days} days.")
        finally:
            session.close()

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

    def get_most_recent_rejection(self) -> dict | None:
        session = get_session(self.engine)
        try:
            approval = session.query(PendingApproval).filter(
                PendingApproval.status == 'rejected',
                PendingApproval.feedback.isnot(None)
            ).order_by(PendingApproval.resolved_at.desc()).first()
            if not approval:
                return None
            return {
                'blog_title': approval.blog_title,
                'feedback': approval.feedback
            }
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

    def get_article_summary(self, url: str) -> dict | None:
        import json as _json
        session = get_session(self.engine)
        try:
            s = session.query(ArticleSummary).filter_by(url=url).first()
            if not s:
                return None
            return {
                'url': s.url,
                'team': s.team,
                'summary': s.summary,
                'event_type': s.event_type,
                'players_mentioned': _json.loads(s.players_mentioned) if s.players_mentioned else [],
                'is_relevant': s.is_relevant
            }
        finally:
            session.close()

    def save_article_summary(self, data: dict):
        import json as _json
        session = get_session(self.engine)
        try:
            existing = session.query(ArticleSummary).filter_by(url=data.get('url')).first()
            if existing:
                return
            session.add(ArticleSummary(
                url=data.get('url', ''),
                team=data.get('team'),
                summary=data.get('summary', ''),
                event_type=data.get('event_type'),
                players_mentioned=_json.dumps(data.get('players_mentioned', [])),
                is_relevant=data.get('is_relevant', True)
            ))
            session.commit()
            logger.info(f"Saved article summary for: {data.get('url', '')[:60]}")
        finally:
            session.close()

    def save_blog_draft(self, data: dict) -> int:
        import json as _json
        session = get_session(self.engine)
        try:
            draft = Summary(
                title=data.get('title', ''),
                html_content=data.get('content', ''),
                summary=data.get('excerpt', ''),
                teams_covered=_json.dumps(data.get('teams_covered', [])),
                article_count=data.get('article_count', 0),
                overall_score=data.get('overall_score')
            )
            session.add(draft)
            session.commit()
            logger.info(f"Saved blog draft: '{data.get('title', '')}' (id={draft.id})")
            return draft.id
        finally:
            session.close()

    def save_evaluation(self, summary_id: int, evaluation: dict):
        session = get_session(self.engine)
        try:
            evaluation_id = evaluation.get('evaluation_id', '')
            criteria_scores = evaluation.get('criteria_scores', {})
            criteria_reasoning = evaluation.get('criteria_reasoning', {})

            for criterion, score in criteria_scores.items():
                session.add(Evaluation(
                    evaluation_id=evaluation_id,
                    summary_id=summary_id,
                    criterion=criterion,
                    score=float(score),
                    reasoning=criteria_reasoning.get(criterion)
                ))
            session.commit()
            logger.info(f"Saved evaluation {evaluation_id[:20]}... ({len(criteria_scores)} criteria) for summary_id={summary_id}")
        finally:
            session.close()

    def create_workflow_run(self, run_id: str) -> int:
        from datetime import datetime
        session = get_session(self.engine)
        try:
            run = WorkflowRun(run_id=run_id, started_at=datetime.utcnow(), status='running')
            session.add(run)
            session.commit()
            logger.info(f"Workflow run started: {run_id}")
            return run.id
        finally:
            session.close()

    def update_workflow_run(self, run_id: str, data: dict):
        import json as _json
        from datetime import datetime
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if not run:
                return
            run.completed_at = datetime.utcnow()
            run.status = data.get('status', run.status)
            run.skip_reason = data.get('skip_reason')
            run.error = data.get('error')
            run.steps_completed = _json.dumps(data.get('steps_completed', []))
            run.scores_fetched = data.get('scores_fetched')
            run.articles_fetched = data.get('articles_fetched')
            run.articles_new = data.get('articles_new')
            run.summaries_count = data.get('summaries_count')
            run.overall_score = data.get('overall_score')
            run.email_sent = data.get('email_sent')
            session.commit()
            logger.info(f"Workflow run updated: {run_id} -> {data.get('status')}")
        finally:
            session.close()
