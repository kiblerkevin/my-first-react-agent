import json

from tools.base_tool import BaseTool
from models.inputs.fetch_scores_input import FetchScoresInput
from models.outputs.fetch_scores_output import FetchScoresOutput
from utils.article_collectors.api_collectors.espn_collector import ESPNCollector
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)


class FetchScoresTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = FetchScoresInput

    name: str = "fetch_scores"
    description: str = (
        "Fetches the latest game scores for all Chicago professional sports teams from the ESPN API. "
        "Returns structured score data including final scores, game status, season records, venue, "
        "and a headline for each game. Call this tool to get score and game result information — "
        "it is separate from fetch_articles which returns news articles."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "force_refresh": {
                "type": "boolean",
                "description": "Reserved for testing. Has no effect until the memory layer is active."
            }
        },
        "required": []
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "scores": {
                "type": "array",
                "description": "List of game scores for Chicago teams.",
                "items": {
                    "type": "object",
                    "properties": {
                        "team": {"type": "string"},
                        "game_id": {"type": "string"},
                        "date": {"type": "string", "format": "date-time"},
                        "season_type": {"type": "string"},
                        "status": {"type": "string"},
                        "status_detail": {"type": "string"},
                        "completed": {"type": "boolean"},
                        "home_team": {"type": "string"},
                        "away_team": {"type": "string"},
                        "home_score": {"type": "string"},
                        "away_score": {"type": "string"},
                        "home_record": {"type": "string"},
                        "away_record": {"type": "string"},
                        "home_hits": {"type": "integer"},
                        "away_hits": {"type": "integer"},
                        "home_errors": {"type": "integer"},
                        "away_errors": {"type": "integer"},
                        "venue": {"type": "string"},
                        "neutral_site": {"type": "boolean"},
                        "headline": {"type": "string"},
                        "short_link_text": {"type": "string"},
                        "game_url": {"type": "string"}
                    }
                }
            },
            "score_count": {"type": "integer", "description": "Total number of games returned."},
            "errors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Collection errors per team, if any."
            }
        }
    }

    def __init__(self):
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default
        )
        self.collector = ESPNCollector()

    def execute(self, input: FetchScoresInput) -> FetchScoresOutput:
        # force_refresh is reserved for future memory layer integration
        logger.info(f"Fetching scores (force_refresh={input.force_refresh})")

        output = FetchScoresOutput()

        try:
            scores = self.collector.collect_articles()
            output.scores = scores
            output.score_count = len(scores)
        except Exception as e:
            error_msg = f"espn: {str(e)}"
            output.errors.append(error_msg)
            logger.error(f"Error collecting scores from ESPN: {e}")

        return output
