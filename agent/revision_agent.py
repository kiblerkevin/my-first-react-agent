import json

import yaml

from agent.base_agent import BaseAgent
from agent.claude_client import ClaudeClient
from agent.context_window import ContextWindow
from tools.create_blog_draft_tool import CreateBlogDraftTool
from tools.evaluate_blog_post_tool import EvaluateBlogPostTool
from prompts.revision_agent_prompt import REVISION_AGENT_PROMPT
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'
LLMS_CONFIG_PATH = 'config/llms.yaml'


class RevisionAgent:
    def __init__(self):
        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.criterion_floors = config['revision_loop']['criterion_floors']
        self.max_tool_calls = config['revision_loop'].get('max_tool_calls', 10)

    def run(self, summaries: list, scores: list, rejection_feedback: str = None) -> dict:
        """
        Runs the revision agent to produce a blog draft that meets all criterion floors.
        Returns dict with best_draft, best_evaluation, all_evaluations.
        """
        # Build system prompt with criterion floors and optional rejection feedback
        floors_str = "\n".join(f"  {k}: {v}/10" for k, v in self.criterion_floors.items())

        if rejection_feedback:
            feedback_section = (
                f"Previous rejection feedback (address this in the draft):\n"
                f"  {rejection_feedback}"
            )
        else:
            feedback_section = ""

        system_prompt = REVISION_AGENT_PROMPT.format(
            criterion_floors=floors_str,
            rejection_feedback_section=feedback_section
        )

        # Create agent with tools
        client = ClaudeClient(system_prompt=system_prompt)
        context = ContextWindow(conversation_history=[])
        agent = BaseAgent(
            context=context,
            claude_client=client,
            max_tool_calls=self.max_tool_calls,
            force_first_tool='create_blog_draft'
        )

        draft_tool = CreateBlogDraftTool()
        evaluate_tool = EvaluateBlogPostTool()

        agent.tools = {
            draft_tool.name: draft_tool,
            evaluate_tool.name: evaluate_tool
        }

        # Build the user message with all context
        user_message = self._build_message(summaries, scores, rejection_feedback)

        logger.info(f"Revision agent starting (max_tool_calls={self.max_tool_calls})")
        response = agent.send_message(user_message)
        logger.info(f"Revision agent finished after {agent.tool_call_count} tool calls")
        logger.info(f"Agent response: {response[:200]}...")

        # Extract results from tool call history
        return self._extract_results(context, response)

    def _build_message(self, summaries: list, scores: list, rejection_feedback: str = None) -> str:
        sections = [
            "Please create and evaluate a Chicago sports recap blog post using the data below.",
            "\nARTICLE SUMMARIES:",
            json.dumps(summaries, indent=2),
            "\nGAME SCORES:",
            json.dumps(scores, indent=2)
        ]
        if rejection_feedback:
            sections.append(f"\nPREVIOUS REJECTION FEEDBACK:\n{rejection_feedback}")
        return '\n'.join(sections)

    def _extract_results(self, context: ContextWindow, agent_response: str) -> dict:
        """Extract the best draft and all evaluations from the agent's tool call history."""
        best_draft = None
        best_evaluation = None
        all_evaluations = []

        for msg in context.conversation_history:
            msg_dict = msg.model_dump()

            # Look for tool results
            if msg_dict.get('role') == 'user' and isinstance(msg_dict.get('content'), list):
                for item in msg_dict['content']:
                    if item.get('type') != 'tool_result' or item.get('is_error'):
                        continue

                    try:
                        result = json.loads(item['content'])
                    except (json.JSONDecodeError, TypeError):
                        continue

                    # Detect evaluation results (have criteria_scores)
                    if 'criteria_scores' in result:
                        all_evaluations.append(result)
                        score = result.get('overall_score', 0)
                        if best_evaluation is None or score > best_evaluation.get('overall_score', 0):
                            best_evaluation = result

                    # Detect draft results (have title and content)
                    elif 'title' in result and 'content' in result and len(result.get('content', '')) > 100:
                        best_draft = result

        # Fallback if extraction fails
        if not best_draft:
            logger.warning("Could not extract draft from agent history — returning empty draft.")
            best_draft = {'title': '', 'content': '', 'excerpt': '', 'teams_covered': [], 'article_count': 0}
        if not best_evaluation:
            logger.warning("Could not extract evaluation from agent history — returning empty evaluation.")
            best_evaluation = {'evaluation_id': '', 'overall_score': 0.0, 'criteria_scores': {}, 'criteria_reasoning': {}, 'improvement_suggestions': {}}

        return {
            'best_draft': best_draft,
            'best_evaluation': best_evaluation,
            'all_evaluations': all_evaluations,
            'agent_response': agent_response
        }
