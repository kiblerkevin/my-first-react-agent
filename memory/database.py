from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os


Base = declarative_base()


class Article(Base):
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
    __tablename__ = 'article_summaries'

    id = Column(Integer, primary_key=True)
    url = Column(String(255), nullable=False, unique=True)
    team = Column(String(100), nullable=True)
    summary = Column(Text, nullable=False)
    event_type = Column(String(50), nullable=True)
    players_mentioned = Column(Text, nullable=True)  # JSON string
    is_relevant = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Summary(Base):
    __tablename__ = 'summaries'
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    title = Column(String(255), nullable=True)
    html_content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)  # excerpt
    teams_covered = Column(Text, nullable=True)  # JSON string
    article_count = Column(Integer, nullable=True)
    overall_score = Column(Float, nullable=True)
    
    categories = relationship("SummaryCategory", back_populates="summary")
    tags = relationship("SummaryTag", back_populates="summary")
    evaluations = relationship("Evaluation", back_populates="summary")
    improvement_suggestions = relationship("ImprovementSuggestion", back_populates="summary")
    
    
class Category(Base):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    wordpress_id = Column(Integer, nullable=True)
    
    
class SummaryCategory(Base):
    __tablename__ = 'summary_categories'
    
    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'), nullable=False)
    
    summary = relationship("Summary", back_populates="categories")
    category = relationship("Category")
    

class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    wordpress_id = Column(Integer, nullable=True)
    
    
class SummaryTag(Base):
    __tablename__ = 'summary_tags'
    
    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    tag_id = Column(Integer, ForeignKey('tags.id'), nullable=False)
    
    summary = relationship("Summary", back_populates="tags")
    tag = relationship("Tag")
    
    
class Evaluation(Base):
    __tablename__ = 'evaluations'
    
    id = Column(Integer, primary_key=True)
    evaluation_id = Column(String(100), nullable=False)  # ISO timestamp identifying the evaluation run
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    criterion = Column(String(100), nullable=False)
    score = Column(Float, nullable=False)
    reasoning = Column(Text, nullable=True)
    
    summary = relationship("Summary", back_populates="evaluations")
    
    
class ImprovementSuggestion(Base):
    __tablename__ = 'improvement_suggestions'
    
    id = Column(Integer, primary_key=True)
    summary_id = Column(Integer, ForeignKey('summaries.id'), nullable=False)
    suggestion = Column(Text, nullable=False)
    
    summary = relationship("Summary", back_populates="improvement_suggestions")


class PendingApproval(Base):
    __tablename__ = 'pending_approvals'

    id = Column(Integer, primary_key=True)
    token = Column(String(512), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default='pending')  # pending, approved, rejected, expired
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    blog_title = Column(String(255), nullable=False)
    blog_content = Column(Text, nullable=False)
    blog_excerpt = Column(Text, nullable=True)
    taxonomy_data = Column(Text, nullable=True)  # JSON string
    evaluation_data = Column(Text, nullable=True)  # JSON string
    summaries_data = Column(Text, nullable=True)  # JSON string
    scores_data = Column(Text, nullable=True)  # JSON string
    feedback = Column(Text, nullable=True)


class OAuthToken(Base):
    __tablename__ = 'oauth_tokens'

    id = Column(Integer, primary_key=True)
    service = Column(String(50), nullable=False, unique=True)  # e.g. 'wordpress'
    access_token = Column(Text, nullable=False)
    blog_id = Column(String(100), nullable=True)
    blog_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowRun(Base):
    __tablename__ = 'workflow_runs'

    id = Column(Integer, primary_key=True)
    run_id = Column(String(100), nullable=False, unique=True)
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False, default='running')  # running, success, skipped, failed
    skip_reason = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    steps_completed = Column(Text, nullable=True)  # JSON list
    scores_fetched = Column(Integer, nullable=True)
    articles_fetched = Column(Integer, nullable=True)
    articles_new = Column(Integer, nullable=True)
    summaries_count = Column(Integer, nullable=True)
    overall_score = Column(Float, nullable=True)
    email_sent = Column(Boolean, nullable=True)
    
    
def get_engine(db_path='data/articles.db'):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return create_engine(f'sqlite:///{db_path}')


def init_db(db_path='data/articles.db'):
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(engine):
    Session = sessionmaker(bind=engine)
    return Session()
    
