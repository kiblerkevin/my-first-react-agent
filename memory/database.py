"""SQLAlchemy models and database initialization for the memory layer."""

import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

Base = declarative_base()


class Article(Base):
    """Persisted article metadata for deduplication across runs."""

    __tablename__ = 'articles'

    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)
    source = Column(String(255), nullable=True)
    url = Column(String(255), nullable=False, unique=True)
    published_at = Column(DateTime, nullable=True)
    team = Column(String(100), nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)


class ArticleSummary(Base):
    """Cached article summaries to avoid re-summarization."""

    __tablename__ = 'article_summaries'

    id = Column(Integer, primary_key=True)
    url = Column(String(255), nullable=False, unique=True)
    team = Column(String(100), nullable=True)
    summary = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=True)
    players_mentioned = Column(Text, nullable=True)
    is_relevant = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Summary(Base):
    """Persisted blog draft with evaluation scores."""

    __tablename__ = 'summaries'

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String(255), nullable=True)
    html_content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    teams_covered = Column(Text, nullable=True)
    article_count = Column(Integer, nullable=True)
    overall_score = Column(Float, nullable=True)

    categories = relationship('SummaryCategory', back_populates='summary')
    tags = relationship('SummaryTag', back_populates='summary')
    evaluations = relationship('Evaluation', back_populates='summary')
    improvement_suggestions = relationship(
        'ImprovementSuggestion', back_populates='summary'
    )


class Category(Base):
    """WordPress category with optional remote ID."""

    __tablename__ = 'categories'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    wordpress_id = Column(Integer, nullable=True)


class SummaryCategory(Base):
    """Many-to-many link between summaries and categories."""

    __tablename__ = 'summary_categories'

    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)

    summary = relationship('Summary', back_populates='categories')
    category = relationship('Category')


class Tag(Base):
    """WordPress tag with optional remote ID."""

    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    wordpress_id = Column(Integer, nullable=True)


class SummaryTag(Base):
    """Many-to-many link between summaries and tags."""

    __tablename__ = 'summary_tags'

    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    tag_id = Column(Integer, ForeignKey('tags.id'), nullable=False)

    summary = relationship('Summary', back_populates='tags')
    tag = relationship('Tag')


class Evaluation(Base):
    """Per-criterion evaluation score for a blog draft."""

    __tablename__ = 'evaluations'

    id = Column(Integer, primary_key=True)
    evaluation_id = Column(String(100), nullable=False)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    criterion = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)

    summary = relationship('Summary', back_populates='evaluations')


class ImprovementSuggestion(Base):
    """Improvement suggestion linked to a blog draft."""

    __tablename__ = 'improvement_suggestions'

    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    suggestion = Column(Text, nullable=False)

    summary = relationship('Summary', back_populates='improvement_suggestions')


class PendingApproval(Base):
    """Human approval request with signed token and status tracking."""

    __tablename__ = 'pending_approvals'

    id = Column(Integer, primary_key=True)
    token = Column(String(512), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    blog_title = Column(String(255), nullable=False)
    blog_content = Column(Text, nullable=False)
    blog_excerpt = Column(Text, nullable=True)
    taxonomy_data = Column(Text, nullable=True)
    evaluation_data = Column(Text, nullable=True)
    summaries_data = Column(Text, nullable=True)
    scores_data = Column(Text, nullable=True)
    feedback = Column(Text, nullable=True)


class OAuthToken(Base):
    """Stored OAuth tokens for external services."""

    __tablename__ = 'oauth_tokens'

    id = Column(Integer, primary_key=True)
    service = Column(String(50), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    blog_id = Column(String(100), nullable=True)
    blog_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowRun(Base):
    """Tracked workflow execution with metrics and checkpoint data."""

    __tablename__ = 'workflow_runs'

    id = Column(Integer, primary_key=True)
    run_id = Column(String(100), nullable=False, unique=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default='running')
    skip_reason = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    steps_completed = Column(Text, nullable=True)
    scores_fetched = Column(Integer, nullable=True)
    articles_fetched = Column(Integer, nullable=True)
    articles_new = Column(Integer, nullable=True)
    summaries_count = Column(Integer, nullable=True)
    overall_score = Column(Float, nullable=True)
    email_sent = Column(Boolean, nullable=True)
    total_input_tokens = Column(Integer, nullable=True)
    total_output_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    usage_by_tool = Column(Text, nullable=True)
    checkpoint_data = Column(Text, nullable=True)
    revision_tool_calls = Column(Integer, nullable=True)
    draft_attempts = Column(Integer, nullable=True)
    score_progression = Column(Text, nullable=True)
    publish_post_id = Column(Integer, nullable=True)
    publish_post_url = Column(String(255), nullable=True)
    publish_success = Column(Boolean, nullable=True)
    draft_iterations = Column(Text, nullable=True)

    __table_args__ = (Index('ix_workflow_runs_started_at', 'started_at'),)

    api_call_results = relationship('ApiCallResult', back_populates='workflow_run')
    summary_stats = relationship('SummaryStats', back_populates='workflow_run')


class ApiCallResult(Base):
    """Per-source API call result for a workflow run."""

    __tablename__ = 'api_call_results'

    id = Column(Integer, primary_key=True)
    workflow_run_id = Column(Integer, ForeignKey('workflow_runs.id'), nullable=False)
    source_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)
    article_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    workflow_run = relationship('WorkflowRun', back_populates='api_call_results')


class DriftAlert(Base):
    """Active or resolved drift alert for suppression and recovery tracking."""

    __tablename__ = 'drift_alerts'

    id = Column(Integer, primary_key=True)
    metric_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default='active')  # active, resolved
    triggered_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    metric_value = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    run_id = Column(String(100), nullable=True)


class SummaryStats(Base):
    """Per-team summarization statistics for a workflow run."""

    __tablename__ = 'summary_stats'

    id = Column(Integer, primary_key=True)
    workflow_run_id = Column(Integer, ForeignKey('workflow_runs.id'), nullable=False)
    team = Column(String(100), nullable=False)
    articles_fetched = Column(Integer, default=0)
    articles_summarized = Column(Integer, default=0)
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)

    workflow_run = relationship('WorkflowRun', back_populates='summary_stats')


def get_engine(db_path: str = 'data/articles.db') -> Engine:
    """Create a SQLAlchemy engine for the given database path.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLAlchemy Engine instance.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return create_engine(f'sqlite:///{db_path}')


def init_db(db_path: str = 'data/articles.db') -> Engine:
    """Initialize the database, creating all tables if needed.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        SQLAlchemy Engine instance.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine: Engine) -> Session:
    """Create a new database session.

    Args:
        engine: SQLAlchemy Engine to bind the session to.

    Returns:
        New Session instance.
    """
    SessionFactory = sessionmaker(bind=engine)
    return SessionFactory()
