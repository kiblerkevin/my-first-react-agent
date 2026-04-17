import yaml
from datetime import datetime, timedelta

from memory.database import init_db, get_session, Category, Tag, PendingApproval, OAuthToken, Article, ArticleSummary, Summary, Evaluation, WorkflowRun, ApiCallResult, SummaryStats
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

DATABASE_CONFIG_PATH = 'config/database.yaml'


class Memory:
    def __init__(self):
        with open(DATABASE_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        db_path = config['database']['path']
        self.retention_days = config['database'].get('retention_days', 30)
        self.log_retention_days = config['database'].get('log_retention_days', 30)
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

    def purge_old_logs(self):
        import os
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=self.log_retention_days)
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            return
        count = 0
        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            if not os.path.isfile(filepath):
                continue
            modified = datetime.utcfromtimestamp(os.path.getmtime(filepath))
            if modified < cutoff:
                os.remove(filepath)
                count += 1
        if count:
            logger.info(f"Purged {count} log file(s) older than {self.log_retention_days} days.")

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
            run.total_input_tokens = data.get('total_input_tokens')
            run.total_output_tokens = data.get('total_output_tokens')
            run.estimated_cost = data.get('estimated_cost')
            if data.get('usage_by_tool'):
                run.usage_by_tool = _json.dumps(data['usage_by_tool'])
            session.commit()
            logger.info(f"Workflow run updated: {run_id} -> {data.get('status')}")
        finally:
            session.close()

    def save_checkpoint(self, run_id: str, step_name: str, data: dict):
        import json as _json
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if not run:
                return
            checkpoint = _json.loads(run.checkpoint_data) if run.checkpoint_data else {}
            checkpoint[step_name] = data
            run.checkpoint_data = _json.dumps(checkpoint)
            session.commit()
        finally:
            session.close()

    def get_checkpoint(self, run_id: str) -> dict | None:
        import json as _json
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if not run or not run.checkpoint_data:
                return None
            return {
                'steps_completed': _json.loads(run.steps_completed) if run.steps_completed else [],
                'data': _json.loads(run.checkpoint_data)
            }
        finally:
            session.close()

    def get_workflow_run_db_id(self, run_id: str) -> int | None:
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            return run.id if run else None
        finally:
            session.close()

    def save_api_call_result(self, workflow_run_id: int, source_name: str, status: str, article_count: int = None, error: str = None):
        session = get_session(self.engine)
        try:
            session.add(ApiCallResult(
                workflow_run_id=workflow_run_id,
                source_name=source_name,
                status=status,
                article_count=article_count,
                error_message=error
            ))
            session.commit()
        finally:
            session.close()

    def save_summary_stats(self, workflow_run_id: int, stats: list):
        session = get_session(self.engine)
        try:
            for s in stats:
                session.add(SummaryStats(
                    workflow_run_id=workflow_run_id,
                    team=s.get('team', ''),
                    articles_fetched=s.get('articles_fetched', 0),
                    articles_summarized=s.get('articles_summarized', 0),
                    cache_hits=s.get('cache_hits', 0),
                    cache_misses=s.get('cache_misses', 0)
                ))
            session.commit()
        finally:
            session.close()

    def update_workflow_publish_result(self, run_id: str, post_id: int, post_url: str, success: bool):
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if run:
                run.publish_post_id = post_id
                run.publish_post_url = post_url
                run.publish_success = success
                session.commit()
        finally:
            session.close()

    def update_workflow_revision_metrics(self, run_id: str, tool_calls: int, draft_attempts: int, score_progression: list):
        import json as _json
        session = get_session(self.engine)
        try:
            run = session.query(WorkflowRun).filter_by(run_id=run_id).first()
            if run:
                run.revision_tool_calls = tool_calls
                run.draft_attempts = draft_attempts
                run.score_progression = _json.dumps(score_progression)
                session.commit()
        finally:
            session.close()

    # --- Dashboard query methods ---

    def get_recent_runs(self, limit: int = 30) -> list:
        import json as _json
        session = get_session(self.engine)
        try:
            runs = session.query(WorkflowRun).order_by(WorkflowRun.id.desc()).limit(limit).all()
            return [{
                'run_id': r.run_id,
                'started_at': r.started_at.isoformat() if r.started_at else None,
                'completed_at': r.completed_at.isoformat() if r.completed_at else None,
                'duration_seconds': (r.completed_at - r.started_at).total_seconds() if r.completed_at and r.started_at else None,
                'status': r.status,
                'skip_reason': r.skip_reason,
                'error': r.error,
                'steps_completed': _json.loads(r.steps_completed) if r.steps_completed else [],
                'scores_fetched': r.scores_fetched,
                'articles_fetched': r.articles_fetched,
                'articles_new': r.articles_new,
                'summaries_count': r.summaries_count,
                'overall_score': r.overall_score,
                'email_sent': r.email_sent,
                'revision_tool_calls': r.revision_tool_calls,
                'draft_attempts': r.draft_attempts,
                'score_progression': _json.loads(r.score_progression) if r.score_progression else [],
                'publish_success': r.publish_success
            } for r in runs]
        finally:
            session.close()

    def get_evaluation_trends(self, days: int = 30) -> list:
        from datetime import timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            evals = session.query(Evaluation).join(Summary).filter(
                Summary.created_at >= cutoff
            ).order_by(Summary.created_at).all()

            by_date = {}
            for e in evals:
                date_key = e.summary.created_at.strftime('%Y-%m-%d') if e.summary.created_at else 'unknown'
                if date_key not in by_date:
                    by_date[date_key] = {}
                by_date[date_key][e.criterion] = e.score

            return [{'date': d, **scores} for d, scores in sorted(by_date.items())]
        finally:
            session.close()

    def get_api_health(self, days: int = 30) -> list:
        from datetime import timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            results = session.query(ApiCallResult).filter(
                ApiCallResult.created_at >= cutoff
            ).all()

            by_source = {}
            for r in results:
                if r.source_name not in by_source:
                    by_source[r.source_name] = {'success': 0, 'error': 0, 'total_articles': 0}
                by_source[r.source_name][r.status] = by_source[r.source_name].get(r.status, 0) + 1
                if r.article_count:
                    by_source[r.source_name]['total_articles'] += r.article_count

            return [{'source': s, **counts} for s, counts in by_source.items()]
        finally:
            session.close()

    def get_approval_stats(self, days: int = 30) -> dict:
        from datetime import timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            approvals = session.query(PendingApproval).filter(
                PendingApproval.created_at >= cutoff
            ).all()

            stats = {'approved': 0, 'rejected': 0, 'expired': 0, 'pending': 0}
            for a in approvals:
                stats[a.status] = stats.get(a.status, 0) + 1
            stats['total'] = len(approvals)
            return stats
        finally:
            session.close()

    def get_team_coverage(self, days: int = 30) -> dict:
        import json as _json
        from datetime import timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            summaries = session.query(Summary).filter(
                Summary.created_at >= cutoff
            ).all()

            coverage = {}
            for s in summaries:
                teams = _json.loads(s.teams_covered) if s.teams_covered else []
                for team in teams:
                    coverage[team] = coverage.get(team, 0) + 1
            return coverage
        finally:
            session.close()

    def get_source_distribution(self, days: int = 30) -> dict:
        from datetime import timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            results = session.query(ApiCallResult).filter(
                ApiCallResult.created_at >= cutoff,
                ApiCallResult.status == 'success'
            ).all()

            dist = {}
            for r in results:
                if r.source_name not in ('espn',):  # exclude scores source
                    dist[r.source_name] = dist.get(r.source_name, 0) + (r.article_count or 0)
            return dist
        finally:
            session.close()

    def get_summary_cache_stats(self, days: int = 30) -> dict:
        from datetime import timedelta
        session = get_session(self.engine)
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            stats = session.query(SummaryStats).join(WorkflowRun).filter(
                WorkflowRun.started_at >= cutoff
            ).all()

            totals = {'cache_hits': 0, 'cache_misses': 0}
            for s in stats:
                totals['cache_hits'] += s.cache_hits
                totals['cache_misses'] += s.cache_misses
            totals['total'] = totals['cache_hits'] + totals['cache_misses']
            totals['hit_rate'] = round(totals['cache_hits'] / totals['total'] * 100, 1) if totals['total'] > 0 else 0
            return totals
        finally:
            session.close()
