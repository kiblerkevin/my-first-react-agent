"""Tests for memory/memory.py."""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from memory.database import init_db


class TestMemoryCRUD:
    """Tests for Memory CRUD operations."""

    def test_save_and_get_seen_urls(self, memory):
        articles = [
            {'url': 'http://a.com', 'title': 'A'},
            {'url': 'http://b.com', 'title': 'B'},
        ]
        memory.save_articles(articles)
        seen = memory.get_seen_urls()
        assert 'http://a.com' in seen
        assert 'http://b.com' in seen

    def test_save_articles_skips_duplicates(self, memory):
        articles = [{'url': 'http://a.com', 'title': 'A'}]
        memory.save_articles(articles)
        memory.save_articles(articles)  # second save should not error
        seen = memory.get_seen_urls()
        assert len(seen) == 1

    def test_get_or_create_category(self, memory):
        cat = memory.get_or_create_category('Daily Recap')
        assert cat['name'] == 'Daily Recap'
        assert cat['id'] is not None
        # Second call returns same
        cat2 = memory.get_or_create_category('Daily Recap')
        assert cat2['id'] == cat['id']

    def test_get_or_create_tag(self, memory):
        tag = memory.get_or_create_tag('Cubs')
        assert tag['name'] == 'Cubs'
        tag2 = memory.get_or_create_tag('Cubs')
        assert tag2['id'] == tag['id']

    def test_save_and_get_article_summary(self, memory):
        data = {
            'url': 'http://x.com',
            'team': 'Cubs',
            'summary': 'Test summary.',
            'event_type': 'game_recap',
            'players_mentioned': ['A', 'B'],
            'is_relevant': True,
        }
        memory.save_article_summary(data)
        cached = memory.get_article_summary('http://x.com')
        assert cached is not None
        assert cached['summary'] == 'Test summary.'
        assert cached['players_mentioned'] == ['A', 'B']

    def test_get_article_summary_returns_none_on_miss(self, memory):
        assert memory.get_article_summary('http://nonexistent.com') is None

    def test_save_blog_draft_returns_id(self, memory):
        draft_id = memory.save_blog_draft({
            'title': 'Test',
            'content': '<h1>Test</h1>',
            'excerpt': 'Excerpt',
            'teams_covered': ['Cubs'],
            'article_count': 3,
            'overall_score': 8.5,
        })
        assert draft_id > 0

    def test_create_and_get_workflow_run(self, memory):
        run_id = 'test-run-001'
        db_id = memory.create_workflow_run(run_id)
        assert db_id > 0
        assert memory.get_workflow_run_db_id(run_id) == db_id

    def test_save_and_get_checkpoint(self, memory):
        run_id = 'test-run-002'
        memory.create_workflow_run(run_id)
        memory.save_checkpoint(run_id, 'fetch_scores', {'scores': [1, 2, 3]})
        checkpoint = memory.get_checkpoint(run_id)
        assert checkpoint is not None
        assert 'fetch_scores' in checkpoint['data']
        assert checkpoint['data']['fetch_scores'] == {'scores': [1, 2, 3]}

    def test_get_checkpoint_returns_none_for_unknown_run(self, memory):
        assert memory.get_checkpoint('nonexistent') is None

    def test_oauth_token_save_and_retrieve(self, memory):
        memory.save_oauth_token('wordpress', 'token123', blog_id='1', blog_url='http://blog.com')
        assert memory.get_oauth_token('wordpress') == 'token123'
        assert memory.get_oauth_token('unknown') is None

    def test_oauth_token_update(self, memory):
        memory.save_oauth_token('wordpress', 'old_token')
        memory.save_oauth_token('wordpress', 'new_token')
        assert memory.get_oauth_token('wordpress') == 'new_token'

    def test_pending_approval_lifecycle(self, memory):
        data = {
            'token': 'abc123',
            'status': 'pending',
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'blog_title': 'Test Post',
            'blog_content': '<p>Content</p>',
        }
        memory.create_pending_approval(data)
        approval = memory.get_pending_approval('abc123')
        assert approval is not None
        assert approval['status'] == 'pending'

        memory.update_approval_status('abc123', 'approved')
        approval = memory.get_pending_approval('abc123')
        assert approval['status'] == 'approved'

    def test_get_most_recent_rejection(self, memory):
        # No rejections yet
        assert memory.get_most_recent_rejection() is None

        # Create a rejected approval with feedback
        data = {
            'token': 'rej1',
            'status': 'pending',
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'blog_title': 'Rejected Post',
            'blog_content': '<p>Content</p>',
        }
        memory.create_pending_approval(data)
        memory.update_approval_status('rej1', 'rejected', feedback='Needs more detail')

        rejection = memory.get_most_recent_rejection()
        assert rejection is not None
        assert rejection['feedback'] == 'Needs more detail'


class TestMemoryWorkflowOps:
    """Tests for workflow run and dashboard query methods."""

    def test_update_workflow_run(self, memory):
        run_id = 'wf-update-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_run(run_id, {
            'status': 'success',
            'steps_completed': ['fetch_scores', 'fetch_articles'],
            'scores_fetched': 5,
            'articles_fetched': 10,
            'articles_new': 8,
            'summaries_count': 4,
            'overall_score': 8.5,
            'email_sent': True,
        })
        runs = memory.get_recent_runs(1)
        assert len(runs) == 1
        assert runs[0]['status'] == 'success'
        assert runs[0]['overall_score'] == 8.5

    def test_save_api_call_result(self, memory):
        run_id = 'wf-api-test'
        db_id = memory.create_workflow_run(run_id)
        memory.save_api_call_result(db_id, 'newsapi', 'success', article_count=15)
        memory.save_api_call_result(db_id, 'espn', 'error', error='timeout')

        health = memory.get_api_health(30)
        sources = {h['source'] for h in health}
        assert 'newsapi' in sources
        assert 'espn' in sources

    def test_save_summary_stats(self, memory):
        run_id = 'wf-stats-test'
        db_id = memory.create_workflow_run(run_id)
        memory.save_summary_stats(db_id, [
            {'team': 'Cubs', 'articles_fetched': 5, 'articles_summarized': 3, 'cache_hits': 1, 'cache_misses': 2},
        ])
        cache = memory.get_summary_cache_stats(30)
        assert cache['cache_hits'] == 1
        assert cache['cache_misses'] == 2

    def test_update_workflow_publish_result(self, memory):
        run_id = 'wf-publish-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_publish_result(run_id, post_id=42, post_url='http://x.com/42', success=True)
        # Verify via get_recent_runs
        runs = memory.get_recent_runs(1)
        assert runs[0]['publish_success'] is True

    def test_update_workflow_revision_metrics(self, memory):
        run_id = 'wf-revision-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_revision_metrics(
            run_id, tool_calls=4, draft_attempts=2,
            score_progression=[7.0, 8.5],
            draft_iterations=[{'title': 'Draft 1'}, {'title': 'Draft 2'}],
        )
        runs = memory.get_recent_runs(1)
        assert runs[0]['draft_attempts'] == 2
        assert runs[0]['score_progression'] == [7.0, 8.5]

    def test_get_recent_runs_respects_limit(self, memory):
        for i in range(5):
            memory.create_workflow_run(f'run-{i}')
        runs = memory.get_recent_runs(3)
        assert len(runs) == 3

    def test_get_runs_in_window(self, memory):
        for i in range(3):
            run_id = f'window-run-{i}'
            memory.create_workflow_run(run_id)
            memory.update_workflow_run(run_id, {'status': 'success', 'steps_completed': []})
        runs = memory.get_runs_in_window(offset=0, limit=2)
        assert len(runs) == 2

    def test_get_total_run_count(self, memory):
        for i in range(3):
            run_id = f'count-run-{i}'
            memory.create_workflow_run(run_id)
            memory.update_workflow_run(run_id, {'status': 'success', 'steps_completed': []})
        assert memory.get_total_run_count() == 3

    def test_get_team_coverage(self, memory):
        import json
        from memory.database import Summary, get_session
        session = get_session(memory.engine)
        session.add(Summary(html_content='x', teams_covered=json.dumps(['Cubs', 'Sox'])))
        session.add(Summary(html_content='y', teams_covered=json.dumps(['Cubs'])))
        session.commit()
        session.close()

        coverage = memory.get_team_coverage(30)
        assert coverage['Cubs'] == 2
        assert coverage['Sox'] == 1

    def test_get_approval_stats(self, memory):
        memory.create_pending_approval({
            'token': 'a1', 'status': 'pending',
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'blog_title': 'T1', 'blog_content': 'C1',
        })
        memory.create_pending_approval({
            'token': 'a2', 'status': 'pending',
            'expires_at': datetime.utcnow() + timedelta(hours=24),
            'blog_title': 'T2', 'blog_content': 'C2',
        })
        memory.update_approval_status('a2', 'approved')

        stats = memory.get_approval_stats(30)
        assert stats['pending'] == 1
        assert stats['approved'] == 1
        assert stats['total'] == 2

    def test_get_expired_approvals(self, memory):
        memory.create_pending_approval({
            'token': 'expired1', 'status': 'pending',
            'expires_at': datetime.utcnow() - timedelta(hours=1),
            'blog_title': 'Old', 'blog_content': 'X',
        })
        expired = memory.get_expired_approvals()
        assert len(expired) == 1
        assert expired[0]['token'] == 'expired1'

    def test_save_and_get_evaluation(self, memory):
        draft_id = memory.save_blog_draft({
            'title': 'T', 'content': 'C', 'excerpt': 'E',
            'teams_covered': [], 'article_count': 0, 'overall_score': 8.0,
        })
        memory.save_evaluation(draft_id, {
            'evaluation_id': 'eval-1',
            'criteria_scores': {'accuracy': 9.0, 'completeness': 8.0},
            'criteria_reasoning': {'accuracy': 'Good', 'completeness': 'OK'},
        })
        trends = memory.get_evaluation_trends(30)
        assert len(trends) > 0


class TestMemoryPurgeAndEdgeCases:
    """Tests for purge operations and edge cases."""

    def test_purge_old_articles(self, memory):
        from memory.database import Article, get_session

        session = get_session(memory.engine)
        old_date = datetime.utcnow() - timedelta(days=60)
        session.add(Article(title='Old', url='http://old.com', fetched_at=old_date))
        session.add(Article(title='New', url='http://new.com'))
        session.commit()
        session.close()

        memory.purge_old_articles()
        seen = memory.get_seen_urls()
        assert 'http://old.com' not in seen
        assert 'http://new.com' in seen

    def test_purge_old_logs(self, memory, tmp_path):
        import os

        log_dir = str(tmp_path / 'logs')
        os.makedirs(log_dir)
        # Create an old file
        old_file = os.path.join(log_dir, 'old.log')
        with open(old_file, 'w') as f:
            f.write('old')
        # Set mtime to 60 days ago
        old_time = (datetime.utcnow() - timedelta(days=60)).timestamp()
        os.utime(old_file, (old_time, old_time))

        # Create a new file
        new_file = os.path.join(log_dir, 'new.log')
        with open(new_file, 'w') as f:
            f.write('new')

        # Monkey-patch the log dir
        import unittest.mock
        with unittest.mock.patch('os.path.exists', return_value=True), \
             unittest.mock.patch('os.listdir', return_value=['old.log', 'new.log']), \
             unittest.mock.patch('os.path.isfile', return_value=True), \
             unittest.mock.patch('os.path.getmtime', side_effect=[old_time, datetime.utcnow().timestamp()]), \
             unittest.mock.patch('os.remove') as mock_remove:
            memory.purge_old_logs()
            mock_remove.assert_called_once()

    def test_save_articles_with_published_at(self, memory):
        articles = [{'url': 'http://dated.com', 'title': 'Dated', 'publishedAt': '2026-04-14T12:00:00Z'}]
        memory.save_articles(articles)
        seen = memory.get_seen_urls()
        assert 'http://dated.com' in seen

    def test_save_articles_skips_no_url(self, memory):
        articles = [{'title': 'No URL'}]
        memory.save_articles(articles)
        seen = memory.get_seen_urls()
        assert len(seen) == 0

    def test_save_articles_handles_bad_date(self, memory):
        articles = [{'url': 'http://baddate.com', 'title': 'Bad', 'publishedAt': 'not-a-date'}]
        memory.save_articles(articles)
        seen = memory.get_seen_urls()
        assert 'http://baddate.com' in seen

    def test_update_category_wordpress_id(self, memory):
        memory.get_or_create_category('TestCat')
        memory.update_category_wordpress_id('TestCat', 42)
        cats = memory.get_all_categories()
        cat = next(c for c in cats if c['name'] == 'TestCat')
        assert cat['wordpress_id'] == 42

    def test_update_tag_wordpress_id(self, memory):
        memory.get_or_create_tag('TestTag')
        memory.update_tag_wordpress_id('TestTag', 99)
        tags = memory.get_all_tags()
        tag = next(t for t in tags if t['name'] == 'TestTag')
        assert tag['wordpress_id'] == 99

    def test_get_source_distribution(self, memory):
        run_id = 'dist-test'
        db_id = memory.create_workflow_run(run_id)
        memory.save_api_call_result(db_id, 'newsapi', 'success', article_count=10)
        memory.save_api_call_result(db_id, 'serpapi', 'success', article_count=5)
        memory.save_api_call_result(db_id, 'espn', 'success', article_count=3)  # excluded

        dist = memory.get_source_distribution(30)
        assert dist.get('newsapi') == 10
        assert dist.get('serpapi') == 5
        assert 'espn' not in dist

    def test_get_runs_in_range(self, memory):
        run_id = 'range-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_run(run_id, {'status': 'success', 'steps_completed': []})

        start = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        end = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        runs = memory.get_runs_in_range(start, end)
        assert len(runs) >= 1
        assert any(r['run_id'] == run_id for r in runs)

    def test_get_run_iterations(self, memory):
        import json
        run_id = 'iter-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_revision_metrics(
            run_id, tool_calls=4, draft_attempts=2,
            score_progression=[7.0, 8.5],
            draft_iterations=[{'title': 'D1', 'content': 'C1'}, {'title': 'D2', 'content': 'C2'}],
        )
        result = memory.get_run_iterations(run_id)
        assert result is not None
        assert result['run_id'] == run_id
        assert result['draft_attempts'] == 2

    def test_get_run_iterations_returns_none_for_unknown(self, memory):
        assert memory.get_run_iterations('nonexistent') is None

    def test_update_workflow_run_with_usage_by_tool(self, memory):
        run_id = 'usage-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_run(run_id, {
            'status': 'success',
            'steps_completed': [],
            'usage_by_tool': {'summarize': {'input': 100, 'output': 50}},
        })
        # Just verify it doesn't crash — usage_by_tool is stored as JSON

    def test_save_article_summary_skips_duplicate(self, memory):
        data = {
            'url': 'http://dup.com', 'team': 'Cubs', 'summary': 'First.',
            'event_type': 'game_recap', 'players_mentioned': [], 'is_relevant': True,
        }
        memory.save_article_summary(data)
        # Save again — should not error
        memory.save_article_summary(data)
        cached = memory.get_article_summary('http://dup.com')
        assert cached['summary'] == 'First.'


class TestMemoryInit:
    """Tests for Memory.__init__ and remaining edge cases."""

    @patch('memory.memory.yaml.safe_load')
    @patch('builtins.open')
    @patch('memory.memory.init_db')
    def test_init_reads_config(self, mock_init_db, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'database': {'path': 'test.db', 'retention_days': 14, 'log_retention_days': 7}
        }
        mock_init_db.return_value = MagicMock()

        from memory.memory import Memory
        m = Memory()
        assert m.retention_days == 14
        assert m.log_retention_days == 7

    def test_purge_old_logs_no_log_dir(self, memory):
        """Line 105: returns early when log dir doesn't exist."""
        import unittest.mock
        with unittest.mock.patch('os.path.exists', return_value=False):
            memory.purge_old_logs()  # Should not raise

    def test_purge_old_logs_skips_directories(self, memory):
        """Line 110: skips non-file entries."""
        import unittest.mock
        with unittest.mock.patch('os.path.exists', return_value=True), \
             unittest.mock.patch('os.listdir', return_value=['subdir']), \
             unittest.mock.patch('os.path.isfile', return_value=False), \
             unittest.mock.patch('os.remove') as mock_remove:
            memory.purge_old_logs()
            mock_remove.assert_not_called()

    def test_update_approval_status_nonexistent_token(self, memory):
        """Line 197: does nothing for nonexistent token."""
        memory.update_approval_status('nonexistent', 'approved')  # Should not raise

    def test_save_checkpoint_nonexistent_run(self, memory):
        """Line 449: does nothing for nonexistent run."""
        memory.save_checkpoint('nonexistent', 'step', {'data': 1})  # Should not raise

    def test_update_workflow_run_nonexistent(self, memory):
        """Line 479: does nothing for nonexistent run."""
        memory.update_workflow_run('nonexistent', {'status': 'success', 'steps_completed': []})

    def test_get_run_iterations_with_evaluations(self, memory):
        """Lines 838-856: get_run_iterations returns evaluations paired with drafts."""
        import json
        from memory.database import Summary, Evaluation, get_session

        run_id = 'iter-eval-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_revision_metrics(
            run_id, tool_calls=2, draft_attempts=1,
            score_progression=[8.0],
            draft_iterations=[{'title': 'D1', 'content': 'C1'}],
        )

        # Create a summary and evaluation linked to it
        session = get_session(memory.engine)
        summary = Summary(html_content='<p>X</p>', title='T')
        session.add(summary)
        session.commit()

        session.add(Evaluation(
            evaluation_id='eval-1', summary_id=summary.id,
            criterion='accuracy', score=9.0, reasoning='Good',
        ))
        session.add(Evaluation(
            evaluation_id='eval-1', summary_id=summary.id,
            criterion='completeness', score=8.0, reasoning='OK',
        ))
        session.commit()
        session.close()

        result = memory.get_run_iterations(run_id)
        assert result is not None
        assert len(result['iterations']) >= 1
        # Check that evaluations are populated
        has_eval = any(
            i.get('evaluation') and i['evaluation'].get('criteria_scores')
            for i in result['iterations']
        )
        assert has_eval


    def test_get_pending_approval_returns_none(self, memory):
        """Line 197: returns None when token not found."""
        assert memory.get_pending_approval('nonexistent-token') is None


class TestMemoryDrift:
    """Tests for drift detection memory methods."""

    def test_get_drift_metrics(self, memory):
        run_id = 'drift-metrics-test'
        memory.create_workflow_run(run_id)
        memory.update_workflow_run(run_id, {
            'status': 'success', 'steps_completed': [], 'overall_score': 8.5,
        })
        memory.update_workflow_revision_metrics(run_id, tool_calls=3, draft_attempts=1, score_progression=[8.5])

        data = memory.get_drift_metrics(window=5)
        assert len(data['runs']) >= 1
        assert data['runs'][0]['overall_score'] == 8.5
        assert data['runs'][0]['status'] == 'success'

    def test_create_and_get_active_drift_alerts(self, memory):
        alert_id = memory.create_drift_alert(
            metric_name='test_metric', metric_value=5.0, threshold=7.0, run_id='run-1'
        )
        assert alert_id > 0

        alerts = memory.get_active_drift_alerts()
        assert len(alerts) == 1
        assert alerts[0]['metric_name'] == 'test_metric'
        assert alerts[0]['metric_value'] == 5.0

    def test_resolve_drift_alert(self, memory):
        memory.create_drift_alert(metric_name='to_resolve', metric_value=3.0, threshold=7.0)
        memory.resolve_drift_alert('to_resolve')

        alerts = memory.get_active_drift_alerts()
        assert len(alerts) == 0

    def test_resolve_nonexistent_alert(self, memory):
        # Should not raise
        memory.resolve_drift_alert('nonexistent_metric')

    def test_has_active_alert(self, memory):
        assert memory.has_active_alert('some_metric') is False
        memory.create_drift_alert(metric_name='some_metric', metric_value=1.0, threshold=5.0)
        assert memory.has_active_alert('some_metric') is True

    def test_has_active_alert_after_resolve(self, memory):
        memory.create_drift_alert(metric_name='resolved_metric', metric_value=1.0, threshold=5.0)
        memory.resolve_drift_alert('resolved_metric')
        assert memory.has_active_alert('resolved_metric') is False


class TestMemoryBackup:
    """Tests for database backup and purge methods."""

    def test_backup_database_creates_file(self, memory, tmp_path):
        backup_dir = str(tmp_path / 'backups')
        memory.backup_path = backup_dir

        result = memory.backup_database()

        assert result is not None
        assert os.path.exists(result)
        assert 'articles_' in result

    def test_backup_database_returns_none_on_failure(self, memory, tmp_path):
        memory.db_path = str(tmp_path / 'nonexistent' / 'deep' / 'db.sqlite')
        memory.backup_path = str(tmp_path / 'backups')

        # Patch sqlite3.connect to raise on the source connection
        import unittest.mock
        with unittest.mock.patch('sqlite3.connect', side_effect=Exception('Cannot open')):
            result = memory.backup_database()

        assert result is None

    def test_purge_old_backups(self, memory, tmp_path):
        backup_dir = str(tmp_path / 'backups')
        os.makedirs(backup_dir)
        memory.backup_path = backup_dir
        memory.backup_retention_days = 30

        # Create an old backup
        old_file = os.path.join(backup_dir, 'articles_old.db')
        with open(old_file, 'w') as f:
            f.write('old')
        old_time = (datetime.utcnow() - timedelta(days=60)).timestamp()
        os.utime(old_file, (old_time, old_time))

        # Create a recent backup
        new_file = os.path.join(backup_dir, 'articles_new.db')
        with open(new_file, 'w') as f:
            f.write('new')

        memory.purge_old_backups()

        assert not os.path.exists(old_file)
        assert os.path.exists(new_file)

    def test_purge_old_backups_no_dir(self, memory):
        memory.backup_path = '/nonexistent/backups'
        # Should not raise
        memory.purge_old_backups()

    def test_purge_old_backups_skips_directories(self, memory, tmp_path):
        backup_dir = str(tmp_path / 'backups')
        os.makedirs(os.path.join(backup_dir, 'subdir'))
        memory.backup_path = backup_dir
        memory.backup_retention_days = 0  # purge everything

        memory.purge_old_backups()
        # subdir should still exist
        assert os.path.exists(os.path.join(backup_dir, 'subdir'))


class TestMemoryInitBackupConfig:
    """Tests for Memory.__init__ backup config loading."""

    @patch('memory.memory.yaml.safe_load')
    @patch('builtins.open')
    @patch('memory.memory.init_db')
    def test_loads_backup_config(self, mock_init_db, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'database': {'path': 'test.db', 'retention_days': 14, 'log_retention_days': 7},
            'backup': {'path': 'my/backups', 'retention_days': 60},
        }
        mock_init_db.return_value = MagicMock()

        from memory.memory import Memory
        m = Memory()
        assert m.backup_path == 'my/backups'
        assert m.backup_retention_days == 60

    @patch('memory.memory.yaml.safe_load')
    @patch('builtins.open')
    @patch('memory.memory.init_db')
    def test_defaults_when_backup_config_missing(self, mock_init_db, mock_open, mock_yaml):
        mock_yaml.return_value = {
            'database': {'path': 'test.db'},
        }
        mock_init_db.return_value = MagicMock()

        from memory.memory import Memory
        m = Memory()
        assert m.backup_path == 'data/backups'
        assert m.backup_retention_days == 30


class TestWALMode:
    """Test that WAL mode is enabled on database init."""

    def test_wal_mode_enabled(self, tmp_path):
        from memory.database import get_session

        db_path = str(tmp_path / 'wal_test.db')
        engine = init_db(db_path)

        # Query via SQLAlchemy to trigger the connect event
        session = get_session(engine)
        result = session.execute(__import__('sqlalchemy').text('PRAGMA journal_mode')).fetchone()
        session.close()
        assert result[0] == 'wal'
