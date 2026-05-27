"""Revision agent that manages the draft-evaluate-revise cycle."""

import json
from typing import Any

import yaml

from agent.base_agent import BaseAgent
from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from prompts.revision_agent_prompt import REVISION_AGENT_PROMPT
from tools.create_blog_draft_tool import CreateBlogDraftTool
from tools.evaluate_blog_post_tool import EvaluateBlogPostTool
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'
LLMS_CONFIG_PATH = 'config/llms.yaml'


class RevisionAgent:
    """Orchestrates blog draft creation and evaluation with budget guards."""

    def __init__(self) -> None:
        """Load revision loop config from orchestration.yaml."""
        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.criterion_floors: dict[str, float] = config['revision_loop'][
            'criterion_floors'
        ]
        self.max_tool_calls: int = config['revision_loop'].get('max_tool_calls', 10)
        self._last_tool_calls: int = 0

    def run(
        self,
        summaries: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        rejection_feedback: str | None = None,
    ) -> dict[str, Any]:
        """Run the revision agent to produce a blog draft meeting criterion floors.

        Args:
            summaries: Article summaries for the blog post.
            scores: Game score data for the blog post.
            rejection_feedback: Optional feedback from a previous human rejection.

        Returns:
            Dict with best_draft, best_evaluation, all_drafts, all_evaluations,
            and agent_response.
        """
        floors_str = '\n'.join(
            f'  {k}: {v}/10' for k, v in self.criterion_floors.items()
        )

        if rejection_feedback:
            feedback_section = (
                f'Previous rejection feedback (address this in the draft):\n'
                f'  {rejection_feedback}'
            )
        else:
            feedback_section = ''

        system_prompt = REVISION_AGENT_PROMPT.format(
            criterion_floors=floors_str,
            rejection_feedback_section=feedback_section,
        )

        client = ClaudeClient(system_prompt=system_prompt)
        with open(LLMS_CONFIG_PATH, 'r') as f:
            llm_config = yaml.safe_load(f)
        orchestrator_config: dict[str, Any] = llm_config['claude_orchestrator']
        client.model = orchestrator_config['model']
        client.temperature = orchestrator_config['temperature']
        client.max_tokens = orchestrator_config['max_tokens']

        draft_tool = CreateBlogDraftTool()
        evaluate_tool = EvaluateBlogPostTool()

        required_tool_context: dict[str, dict[str, Any]] = {
            draft_tool.name: {
                'summaries': summaries,
                'scores': scores,
            },
            evaluate_tool.name: {
                'summaries': summaries,
                'scores': scores,
            },
        }
        if rejection_feedback:
            required_tool_context[draft_tool.name]['rejection_feedback'] = (
                rejection_feedback
            )
            required_tool_context[evaluate_tool.name]['rejection_feedback'] = (
                rejection_feedback
            )

        revision_tracking: dict[str, str] = {
            'draft_tool': draft_tool.name,
            'evaluate_tool': evaluate_tool.name,
        }

        context = ContextWindow(conversation_history=[])
        agent = BaseAgent(
            context=context,
            claude_client=client,
            max_tool_calls=self.max_tool_calls,
            force_first_tool='create_blog_draft',
            required_tool_context=required_tool_context,
            revision_tracking=revision_tracking,
        )

        agent.tools = {
            draft_tool.name: draft_tool,
            evaluate_tool.name: evaluate_tool,
        }

        user_message = self._build_message(summaries, scores, rejection_feedback)

        logger.info(f'Revision agent starting (max_tool_calls={self.max_tool_calls})')
        response = agent.send_message(user_message)
        self._last_tool_calls = agent.tool_call_count
        logger.info(f'Revision agent finished after {agent.tool_call_count} tool calls')
        logger.info(f'Agent response: {response[:200]}...')

        return self._extract_results(context, response)

    def _build_message(
        self,
        summaries: list[dict[str, Any]],
        scores: list[dict[str, Any]],
        rejection_feedback: str | None = None,
    ) -> str:
        """Build the initial user message with all context data.

        Args:
            summaries: Article summaries.
            scores: Game scores.
            rejection_feedback: Optional rejection feedback.

        Returns:
            Formatted user message string.
        """
        sections = [
            'Please create and evaluate a Chicago sports recap blog post using the data below.',
            '\nARTICLE SUMMARIES:',
            json.dumps(summaries, indent=2),
            '\nGAME SCORES:',
            json.dumps(scores, indent=2),
        ]
        if rejection_feedback:
            sections.append(f'\nPREVIOUS REJECTION FEEDBACK:\n{rejection_feedback}')
        return '\n'.join(sections)

    def _extract_results(
        self, context: ContextWindow, agent_response: str
    ) -> dict[str, Any]:
        """Extract all drafts and evaluations from the agent's tool call history.

        Args:
            context: The conversation context with full tool call history.
            agent_response: The agent's final text response.

        Returns:
            Dict with best_draft, best_evaluation, all_drafts, all_evaluations,
            and agent_response.
        """
        best_draft: dict[str, Any] | None = None
        best_evaluation: dict[str, Any] | None = None
        all_drafts: list[dict[str, Any]] = []
        all_evaluations: list[dict[str, Any]] = []

        for msg in context.conversation_history:
            msg_dict = msg.model_dump()

            if msg_dict.get('role') == 'user' and isinstance(
                msg_dict.get('content'), list
            ):
                for item in msg_dict['content']:
                    if item.get('type') != 'tool_result' or item.get('is_error'):
                        continue

                    try:
                        result = json.loads(item['content'])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    if 'criteria_scores' in result:
                        all_evaluations.append(result)
                        score = result.get('overall_score', 0)
                        if best_evaluation is None or score > best_evaluation.get(
                            'overall_score', 0
                        ):
                            best_evaluation = result

                    elif (
                        'title' in result
                        and 'content' in result
                        and len(result.get('content', '')) > 100
                    ):
                        all_drafts.append(result)
                        best_draft = result

        if not best_draft:
            logger.warning(
                'Could not extract draft from agent history — returning empty draft.'
            )
            best_draft = {
                'title': '',
                'content': '',
                'excerpt': '',
                'teams_covered': [],
                'article_count': 0,
            }
        if not best_evaluation:
            logger.warning(
                'Could not extract evaluation from agent history '
                '— returning empty evaluation.'
            )
            best_evaluation = {
                'evaluation_id': '',
                'overall_score': 0.0,
                'criteria_scores': {},
                'criteria_reasoning': {},
                'improvement_suggestions': {},
            }

        if all_evaluations and all_drafts:
            best_idx = max(
                range(len(all_evaluations)),
                key=lambda i: (all_evaluations[i].get('overall_score', 0), i),
            )
            if best_idx < len(all_drafts):
                best_draft = all_drafts[best_idx]
            best_evaluation = all_evaluations[best_idx]

        return {
            'best_draft': best_draft,
            'best_evaluation': best_evaluation,
            'all_drafts': all_drafts,
            'all_evaluations': all_evaluations,
            'agent_response': agent_response,
        }
