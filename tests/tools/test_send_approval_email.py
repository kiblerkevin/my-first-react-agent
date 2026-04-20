"""Tests for tools/send_approval_email_tool.py."""

from unittest.mock import MagicMock, patch

from models.inputs.send_approval_email_input import SendApprovalEmailInput
from tools.send_approval_email_tool import SendApprovalEmailTool, send_failure_email


def _make_tool():
    with patch('tools.send_approval_email_tool.Memory') as mock_mem_cls, \
         patch('tools.send_approval_email_tool.yaml.safe_load', return_value={'approval': {'expiry_hours': 24}}), \
         patch('builtins.open'), \
         patch.dict('os.environ', {
             'APPROVAL_SECRET_KEY': 'test-secret-key-1234567890',
             'APPROVAL_BASE_URL': 'http://localhost:5000',
             'EMAIL_SMTP_SERVER': 'smtp.test.com',
             'EMAIL_SMTP_PORT': '587',
             'EMAIL_FROM': 'test@test.com',
             'EMAIL_PASSWORD': 'pass',
             'EMAIL_TO': 'admin@test.com',
         }):
        tool = SendApprovalEmailTool()
        tool.memory = mock_mem_cls.return_value
        return tool


class TestSendApprovalEmailTool:
    """Tests for SendApprovalEmailTool.execute."""

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    def test_sends_email_successfully(self, mock_smtp):
        tool = _make_tool()
        tool.memory.create_pending_approval.return_value = {'id': 1, 'token': 'x', 'status': 'pending', 'expires_at': '2026-01-01'}

        result = tool.execute(SendApprovalEmailInput(
            title='Test Post', content='<p>Content</p>',
            evaluation_scores={'accuracy': 9.0},
        ))

        assert result.email_sent is True
        assert result.token != ''
        assert result.error is None
        tool.memory.create_pending_approval.assert_called_once()

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    def test_returns_error_on_smtp_failure(self, mock_smtp):
        tool = _make_tool()
        tool.memory.create_pending_approval.return_value = {'id': 1, 'token': 'x', 'status': 'pending', 'expires_at': '2026-01-01'}
        mock_smtp.return_value.__enter__ = MagicMock(side_effect=Exception('SMTP down'))

        result = tool.execute(SendApprovalEmailInput(title='Test', content='<p>X</p>'))

        assert result.email_sent is False
        assert result.error is not None
        assert result.token != ''  # token still generated

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    def test_email_contains_approve_reject_links(self, mock_smtp):
        tool = _make_tool()
        tool.memory.create_pending_approval.return_value = {'id': 1, 'token': 'x', 'status': 'pending', 'expires_at': '2026-01-01'}

        tool.execute(SendApprovalEmailInput(
            title='Test Post', content='<p>Content</p>',
            categories=[{'name': 'Daily Recap'}],
            tags=[{'name': 'Cubs'}],
        ))

        # Verify SMTP was called — decode MIME to check content
        import email
        smtp_instance = mock_smtp.return_value.__enter__.return_value
        raw = smtp_instance.sendmail.call_args[0][2]
        msg = email.message_from_string(raw)
        html_part = None
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                html_part = part.get_payload(decode=True).decode()
                break
        assert html_part is not None
        assert '/approve/' in html_part
        assert '/reject/' in html_part


class TestSendFailureEmail:
    """Tests for the standalone send_failure_email function."""

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    @patch('tools.send_approval_email_tool.yaml.safe_load', return_value={'failure_notification': {'enabled': True}})
    @patch('builtins.open')
    @patch.dict('os.environ', {
        'EMAIL_SMTP_SERVER': 'smtp.test.com',
        'EMAIL_SMTP_PORT': '587',
        'EMAIL_FROM': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_TO': 'admin@test.com',
    })
    def test_sends_failure_email(self, mock_open, mock_yaml, mock_smtp):
        send_failure_email(
            run_id='run-123',
            error='Something broke',
            steps_completed=['fetch_scores', 'fetch_articles'],
        )

        import email as email_mod
        smtp_instance = mock_smtp.return_value.__enter__.return_value
        smtp_instance.sendmail.assert_called_once()
        raw = smtp_instance.sendmail.call_args[0][2]
        msg = email_mod.message_from_string(raw)
        html = None
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_payload(decode=True).decode()
                break
        assert 'Something broke' in html
        assert 'run-123' in html

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    @patch('tools.send_approval_email_tool.yaml.safe_load', return_value={'failure_notification': {'enabled': False}})
    @patch('builtins.open')
    @patch.dict('os.environ', {'EMAIL_TO': 'x@x.com'})
    def test_skips_when_disabled(self, mock_open, mock_yaml, mock_smtp):
        send_failure_email(run_id='run-123', error='err', steps_completed=[])
        mock_smtp.assert_not_called()

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    @patch('tools.send_approval_email_tool.yaml.safe_load', return_value={'failure_notification': {'enabled': True}})
    @patch('builtins.open')
    @patch.dict('os.environ', {
        'EMAIL_SMTP_SERVER': 'smtp.test.com',
        'EMAIL_SMTP_PORT': '587',
        'EMAIL_FROM': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_TO': 'admin@test.com',
    })
    def test_identifies_failed_step(self, mock_open, mock_yaml, mock_smtp):
        send_failure_email(
            run_id='run-456',
            error='Timeout',
            steps_completed=['fetch_scores'],
        )

        import email as email_mod
        raw = mock_smtp.return_value.__enter__.return_value.sendmail.call_args[0][2]
        msg = email_mod.message_from_string(raw)
        html = None
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_payload(decode=True).decode()
                break
        assert 'fetch_articles' in html  # first step not in completed


class TestSendFailureEmailEdgeCases:
    """Tests for send_failure_email edge cases."""

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    @patch('tools.send_approval_email_tool.yaml.safe_load', return_value={'failure_notification': {'enabled': True}})
    @patch('builtins.open')
    @patch.dict('os.environ', {
        'EMAIL_SMTP_SERVER': 'smtp.test.com',
        'EMAIL_SMTP_PORT': '587',
        'EMAIL_FROM': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_TO': 'admin@test.com',
    })
    def test_includes_context_data(self, mock_open, mock_yaml, mock_smtp):
        send_failure_email(
            run_id='run-ctx',
            error='Oops',
            steps_completed=['fetch_scores'],
            context={'articles_fetched': 10, 'scores_fetched': 3},
        )

        import email as email_mod
        raw = mock_smtp.return_value.__enter__.return_value.sendmail.call_args[0][2]
        msg = email_mod.message_from_string(raw)
        html = None
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                html = part.get_payload(decode=True).decode()
                break
        assert 'articles_fetched' in html
        assert 'Partial Data' in html

    @patch('tools.send_approval_email_tool.smtplib.SMTP')
    @patch('tools.send_approval_email_tool.yaml.safe_load', return_value={'failure_notification': {'enabled': True}})
    @patch('builtins.open')
    @patch.dict('os.environ', {
        'EMAIL_SMTP_SERVER': 'smtp.test.com',
        'EMAIL_SMTP_PORT': '587',
        'EMAIL_FROM': 'test@test.com',
        'EMAIL_PASSWORD': 'pass',
        'EMAIL_TO': 'admin@test.com',
    })
    def test_handles_smtp_failure_gracefully(self, mock_open, mock_yaml, mock_smtp):
        mock_smtp.return_value.__enter__.return_value.sendmail.side_effect = Exception('SMTP dead')

        # Should not raise
        send_failure_email(run_id='run-fail', error='X', steps_completed=[])
