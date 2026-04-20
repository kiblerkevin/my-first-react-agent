"""Tool for fetching game scores from the ESPN API."""

from typing import Any

from memory.memory import Memory
from models.inputs.fetch_scores_input import FetchScoresInput
from models.outputs.fetch_scores_output import FetchScoresOutput
from tools.base_tool import BaseTool
from utils.article_collectors.api_collectors.espn_collector import ESPNCollector
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


class FetchScoresTool(BaseTool):
    """Fetches game scores for all Chicago teams from the ESPN scoreboard API."""

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    input_model: type = FetchScoresInput

    name: str = 'fetch_scores'
    description: str = (
        'Fetches the latest game scores for all Chicago professional sports teams from the ESPN API. '
        'Returns structured score data including final scores, game status, season records, venue, '
        'and a headline for each game. Call this tool to get score and game result information — '
        'it is separate from fetch_articles which returns news articles.'
    )
    input_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'force_refresh': {
                'type': 'boolean',
                'description': 'Reserved for testing. Has no effect until the memory layer is active.',
            }
        },
        'required': [],
    }
    output_schema: dict[str, Any] = {
        'type': 'object',
        'properties': {
            'scores': {
                'type': 'array',
                'description': 'List of game scores for Chicago teams.',
                'items': {'type': 'object'},
            },
            'score_count': {'type': 'integer'},
            'errors': {'type': 'array', 'items': {'type': 'string'}},
        },
    }

    def __init__(self) -> None:
        """Initialize with ESPN collector and memory layer."""
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default,
        )
        self.collector = ESPNCollector()
        self.memory = Memory()

    def execute(self, input: FetchScoresInput) -> FetchScoresOutput:
        """Fetch scores from ESPN and persist API call results.

        Args:
            input: Fetch options including force_refresh and run_id.

        Returns:
            Output with scores, count, and any errors.
        """
        logger.info(f'Fetching scores (force_refresh={input.force_refresh})')

        output = FetchScoresOutput()

        try:
            scores = self.collector.collect_articles()
            output.scores = scores
            output.score_count = len(scores)
            if input.run_id:
                db_id = self.memory.get_workflow_run_db_id(input.run_id)
                if db_id:
                    self.memory.save_api_call_result(
                        db_id, 'espn', 'success', len(scores)
                    )
        except Exception as e:
            error_msg = f'espn: {e!s}'
            output.errors.append(error_msg)
            logger.error(f'Error collecting scores from ESPN: {e}')
            if input.run_id:
                db_id = self.memory.get_workflow_run_db_id(input.run_id)
                if db_id:
                    self.memory.save_api_call_result(
                        db_id, 'espn', 'error', error=str(e)
                    )

        return output
