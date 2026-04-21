"""Acceptance tests for workflow/daily_workflow.py."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.acceptance
class TestDailyWorkflowHappyPath:
    """Full workflow happy path — asserts checkpoint calls in correct order."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_happy_path_checkpoints_in_order(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
        mock_articles,
        mock_summaries,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory.get_workflow_run_db_id.return_value = 1
        mock_memory.save_blog_draft.return_value = 1
        mock_memory_cls.return_value = mock_memory

        # Scores
        scores_output = MagicMock(scores=mock_scores, score_count=3)
        mock_scores_cls.return_value.execute.return_value = scores_output

        # Articles
        articles_output = MagicMock(
            articles=mock_articles,
            new_articles=mock_articles,
            article_count=6,
            new_article_count=6,
            filtered_article_count=0,
        )
        mock_articles_cls.return_value.execute.return_value = articles_output

        # Dedup
        dedup_output = MagicMock(unique_articles=mock_articles, duplicate_count=0)
        mock_dedup_cls.return_value.execute.return_value = dedup_output

        # Summarize
        summary_output = MagicMock()
        summary_output.model_dump.return_value = mock_summaries[0]
        mock_summarize_tool = MagicMock()
        mock_summarize_tool.execute.return_value = summary_output
        mock_summarize_tool.last_cache_hit = False
        mock_summarize_cls.return_value = mock_summarize_tool

        # Revision agent
        mock_revision_cls.return_value.run.return_value = {
            'best_draft': mock_draft,
            'best_evaluation': mock_evaluation,
            'all_drafts': [mock_draft],
            'all_evaluations': [mock_evaluation],
        }
        mock_revision_cls.return_value._last_tool_calls = 4

        # Taxonomy
        taxonomy_output = MagicMock(
            categories=[{'name': 'Daily Recap'}], tags=[{'name': 'Cubs'}]
        )
        mock_taxonomy_cls.return_value.execute.return_value = taxonomy_output

        # Approval
        approval_output = MagicMock(email_sent=True, token='tok123', error=None)
        mock_approval_cls.return_value.execute.return_value = approval_output

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow(max_articles_per_team=2)

        assert result['skipped'] is False
        assert result['email_sent'] is True

        # Verify checkpoints saved in order
        checkpoint_calls = [c[0][1] for c in mock_memory.save_checkpoint.call_args_list]
        assert checkpoint_calls == [
            'fetch_scores',
            'fetch_articles',
            'deduplicate_articles',
            'summarize_articles',
            'draft_and_evaluate',
            'create_taxonomy',
            'send_approval_email',
        ]


@pytest.mark.acceptance
class TestDailyWorkflowNoNews:
    """Workflow skips when no new articles are found."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_skips_on_zero_new_articles(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory_cls.return_value = mock_memory

        mock_scores_cls.return_value.execute.return_value = MagicMock(
            scores=mock_scores, score_count=3
        )
        mock_articles_cls.return_value.execute.return_value = MagicMock(
            articles=[],
            new_articles=[],
            article_count=0,
            new_article_count=0,
            filtered_article_count=0,
        )

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow()

        assert result['skipped'] is True
        assert 'No new articles' in result['skip_reason']


@pytest.mark.acceptance
class TestDailyWorkflowNoRelevant:
    """Workflow skips when no relevant summaries after summarization."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_skips_on_zero_relevant_summaries(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
        mock_articles,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory.get_workflow_run_db_id.return_value = 1
        mock_memory_cls.return_value = mock_memory

        mock_scores_cls.return_value.execute.return_value = MagicMock(
            scores=mock_scores, score_count=3
        )
        mock_articles_cls.return_value.execute.return_value = MagicMock(
            articles=mock_articles,
            new_articles=mock_articles,
            article_count=6,
            new_article_count=6,
            filtered_article_count=0,
        )
        mock_dedup_cls.return_value.execute.return_value = MagicMock(
            unique_articles=mock_articles, duplicate_count=0
        )

        # All summaries marked irrelevant
        irrelevant = MagicMock()
        irrelevant.model_dump.return_value = {
            'is_relevant': False,
            'team': 'Cubs',
            'event_type': 'other',
        }
        mock_summarize_tool = MagicMock()
        mock_summarize_tool.execute.return_value = irrelevant
        mock_summarize_tool.last_cache_hit = False
        mock_summarize_cls.return_value = mock_summarize_tool

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow()

        assert result['skipped'] is True
        assert 'No relevant' in result['skip_reason']


@pytest.mark.acceptance
class TestDailyWorkflowResume:
    """Workflow resumes from checkpoint."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_resumes_from_checkpoint(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
        mock_articles,
        mock_summaries,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        # Simulate checkpoint with first 4 steps done
        mock_memory.get_checkpoint.return_value = {
            'steps_completed': [
                'fetch_scores',
                'fetch_articles',
                'deduplicate_articles',
                'summarize_articles',
            ],
            'data': {
                'fetch_scores': {'scores': mock_scores, 'score_count': 3},
                'fetch_articles': {
                    'articles': mock_articles,
                    'new_articles': mock_articles,
                    'article_count': 6,
                    'new_article_count': 6,
                    'filtered_article_count': 0,
                },
                'deduplicate_articles': {
                    'unique_articles': mock_articles,
                    'duplicate_count': 0,
                },
                'summarize_articles': {
                    'summaries': mock_summaries,
                    'relevant': mock_summaries,
                },
            },
        }
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory.save_blog_draft.return_value = 1
        mock_memory_cls.return_value = mock_memory

        mock_revision_cls.return_value.run.return_value = {
            'best_draft': mock_draft,
            'best_evaluation': mock_evaluation,
            'all_drafts': [mock_draft],
            'all_evaluations': [mock_evaluation],
        }
        mock_revision_cls.return_value._last_tool_calls = 4

        mock_taxonomy_cls.return_value.execute.return_value = MagicMock(
            categories=[], tags=[]
        )
        mock_approval_cls.return_value.execute.return_value = MagicMock(
            email_sent=True, token='tok', error=None
        )

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow(resume_run_id='existing-run-id')

        assert result['skipped'] is False
        # Should only checkpoint the remaining steps
        checkpoint_steps = [c[0][1] for c in mock_memory.save_checkpoint.call_args_list]
        assert 'fetch_scores' not in checkpoint_steps
        assert 'draft_and_evaluate' in checkpoint_steps


@pytest.mark.acceptance
class TestDailyWorkflowFailure:
    """Workflow sends failure email on exception."""

    @patch('workflow.daily_workflow.send_failure_email')
    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_sends_failure_email_on_exception(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_failure_email,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory_cls.return_value = mock_memory

        mock_scores_cls.return_value.execute.side_effect = Exception(
            'ESPN API exploded'
        )

        from workflow.daily_workflow import run_daily_workflow

        with pytest.raises(Exception, match='ESPN API exploded'):
            run_daily_workflow()

        mock_failure_email.assert_called_once()
        call_kwargs = mock_failure_email.call_args[1]
        assert 'ESPN API exploded' in call_kwargs['error']


@pytest.mark.acceptance
class TestDailyWorkflowCheckpointAllSteps:
    """Workflow resumes with draft_and_evaluate + taxonomy + approval already done."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_resumes_with_all_steps_checkpointed(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
        mock_articles,
        mock_summaries,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = {
            'steps_completed': [
                'fetch_scores',
                'fetch_articles',
                'deduplicate_articles',
                'summarize_articles',
                'draft_and_evaluate',
                'create_taxonomy',
                'send_approval_email',
            ],
            'data': {
                'fetch_scores': {'scores': mock_scores, 'score_count': 3},
                'fetch_articles': {
                    'articles': mock_articles,
                    'new_articles': mock_articles,
                    'article_count': 6,
                    'new_article_count': 6,
                    'filtered_article_count': 0,
                },
                'deduplicate_articles': {
                    'unique_articles': mock_articles,
                    'duplicate_count': 0,
                },
                'summarize_articles': {
                    'summaries': mock_summaries,
                    'relevant': mock_summaries,
                },
                'draft_and_evaluate': {
                    'best_draft': mock_draft,
                    'best_evaluation': mock_evaluation,
                    'all_evaluations': [mock_evaluation],
                },
                'create_taxonomy': {
                    'categories': [{'name': 'Daily Recap'}],
                    'tags': [{'name': 'Cubs'}],
                },
                'send_approval_email': {
                    'email_sent': True,
                    'token': 'tok123',
                    'error': None,
                },
            },
        }
        mock_memory.get_most_recent_rejection.return_value = {
            'blog_title': 'Old',
            'feedback': 'Fix title',
        }
        mock_memory.save_blog_draft.return_value = 1
        mock_memory_cls.return_value = mock_memory

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow(resume_run_id='full-checkpoint-run')

        assert result['skipped'] is False
        assert result['email_sent'] is True
        # No new checkpoints should be saved since all steps were already done
        mock_memory.save_checkpoint.assert_not_called()


@pytest.mark.acceptance
class TestDailyWorkflowNoCheckpointFound:
    """Workflow starts fresh when resume_run_id has no checkpoint."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_starts_fresh_when_no_checkpoint(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
        mock_articles,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None  # No checkpoint found
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory_cls.return_value = mock_memory

        # Make it skip early via no new articles
        mock_scores_cls.return_value.execute.return_value = MagicMock(
            scores=mock_scores, score_count=3
        )
        mock_articles_cls.return_value.execute.return_value = MagicMock(
            articles=[],
            new_articles=[],
            article_count=0,
            new_article_count=0,
            filtered_article_count=0,
        )

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow(resume_run_id='nonexistent-run')

        assert result['skipped'] is True


@pytest.mark.acceptance
class TestDailyWorkflowCacheHit:
    """Workflow handles summarize cache hits."""

    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_tracks_cache_hits(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_scores,
        mock_articles,
        mock_summaries,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory.get_workflow_run_db_id.return_value = 1
        mock_memory.save_blog_draft.return_value = 1
        mock_memory_cls.return_value = mock_memory

        mock_scores_cls.return_value.execute.return_value = MagicMock(
            scores=mock_scores, score_count=3
        )
        mock_articles_cls.return_value.execute.return_value = MagicMock(
            articles=mock_articles,
            new_articles=mock_articles,
            article_count=6,
            new_article_count=6,
            filtered_article_count=0,
        )
        mock_dedup_cls.return_value.execute.return_value = MagicMock(
            unique_articles=mock_articles, duplicate_count=0
        )

        # Summarize returns relevant with cache hit
        summary_output = MagicMock()
        summary_output.model_dump.return_value = mock_summaries[0]
        mock_summarize_tool = MagicMock()
        mock_summarize_tool.execute.return_value = summary_output
        mock_summarize_tool.last_cache_hit = True  # Cache hit!
        mock_summarize_cls.return_value = mock_summarize_tool

        mock_revision_cls.return_value.run.return_value = {
            'best_draft': mock_draft,
            'best_evaluation': mock_evaluation,
            'all_drafts': [mock_draft],
            'all_evaluations': [mock_evaluation],
        }
        mock_revision_cls.return_value._last_tool_calls = 2
        mock_taxonomy_cls.return_value.execute.return_value = MagicMock(
            categories=[], tags=[]
        )
        mock_approval_cls.return_value.execute.return_value = MagicMock(
            email_sent=True, token='t', error=None
        )

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow(max_articles_per_team=1)

        assert result['skipped'] is False
        # Verify summary stats were saved with cache hits
        mock_memory.save_summary_stats.assert_called_once()


@pytest.mark.acceptance
class TestDailyWorkflowDriftCheck:
    """Workflow runs drift check after completion."""

    @patch('workflow.daily_workflow.DriftDetector')
    @patch('workflow.daily_workflow.send_drift_alert_email')
    @patch('workflow.daily_workflow.send_drift_recovery_email')
    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.RevisionAgent')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_drift_check_called_after_success(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_revision_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_recovery_email,
        mock_alert_email,
        mock_detector_cls,
        mock_scores,
        mock_articles,
        mock_summaries,
        mock_draft,
        mock_evaluation,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory.get_workflow_run_db_id.return_value = 1
        mock_memory.save_blog_draft.return_value = 1
        mock_memory_cls.return_value = mock_memory

        mock_scores_cls.return_value.execute.return_value = MagicMock(
            scores=mock_scores, score_count=3
        )
        mock_articles_cls.return_value.execute.return_value = MagicMock(
            articles=mock_articles,
            new_articles=mock_articles,
            article_count=6,
            new_article_count=6,
            filtered_article_count=0,
        )
        mock_dedup_cls.return_value.execute.return_value = MagicMock(
            unique_articles=mock_articles, duplicate_count=0
        )

        summary_output = MagicMock()
        summary_output.model_dump.return_value = mock_summaries[0]
        mock_summarize_tool = MagicMock()
        mock_summarize_tool.execute.return_value = summary_output
        mock_summarize_tool.last_cache_hit = False
        mock_summarize_cls.return_value = mock_summarize_tool

        mock_revision_cls.return_value.run.return_value = {
            'best_draft': mock_draft,
            'best_evaluation': mock_evaluation,
            'all_drafts': [mock_draft],
            'all_evaluations': [mock_evaluation],
        }
        mock_revision_cls.return_value._last_tool_calls = 4
        mock_taxonomy_cls.return_value.execute.return_value = MagicMock(
            categories=[], tags=[]
        )
        mock_approval_cls.return_value.execute.return_value = MagicMock(
            email_sent=True, token='t', error=None
        )

        # Drift detector returns alerts
        mock_detector = MagicMock()
        mock_detector.check.return_value = {
            'new_alerts': [
                {
                    'metric_name': 'test',
                    'value': 1,
                    'threshold': 5,
                    'description': 'x',
                    'suggested_actions': [],
                }
            ],
            'recoveries': [{'metric_name': 'other', 'value': 9, 'description': 'y'}],
        }
        mock_detector_cls.return_value = mock_detector

        from workflow.daily_workflow import run_daily_workflow

        run_daily_workflow(max_articles_per_team=1)

        mock_detector.check.assert_called_once()
        mock_alert_email.assert_called_once()
        mock_recovery_email.assert_called_once()

    @patch('workflow.daily_workflow.DriftDetector')
    @patch('workflow.daily_workflow.send_drift_alert_email')
    @patch('workflow.daily_workflow.send_drift_recovery_email')
    @patch('workflow.daily_workflow.Memory')
    @patch('workflow.daily_workflow.SendApprovalEmailTool')
    @patch('workflow.daily_workflow.CreateBlogTaxonomyTool')
    @patch('workflow.daily_workflow.SummarizeArticleTool')
    @patch('workflow.daily_workflow.DeduplicateArticlesTool')
    @patch('workflow.daily_workflow.FetchArticlesTool')
    @patch('workflow.daily_workflow.FetchScoresTool')
    @patch('workflow.daily_workflow.yaml.safe_load')
    @patch('builtins.open')
    def test_drift_check_error_does_not_crash_workflow(
        self,
        mock_open,
        mock_yaml,
        mock_scores_cls,
        mock_articles_cls,
        mock_dedup_cls,
        mock_summarize_cls,
        mock_taxonomy_cls,
        mock_approval_cls,
        mock_memory_cls,
        mock_recovery_email,
        mock_alert_email,
        mock_detector_cls,
        mock_scores,
    ):
        mock_yaml.return_value = {}
        mock_memory = MagicMock()
        mock_memory.get_checkpoint.return_value = None
        mock_memory.get_most_recent_rejection.return_value = None
        mock_memory_cls.return_value = mock_memory

        # Skip early via no new articles
        mock_scores_cls.return_value.execute.return_value = MagicMock(
            scores=mock_scores, score_count=3
        )
        mock_articles_cls.return_value.execute.return_value = MagicMock(
            articles=[],
            new_articles=[],
            article_count=0,
            new_article_count=0,
            filtered_article_count=0,
        )

        from workflow.daily_workflow import run_daily_workflow

        result = run_daily_workflow()

        # Skipped workflows don't run drift check (it's only after full success)
        assert result['skipped'] is True
