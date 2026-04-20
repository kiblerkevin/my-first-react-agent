"""ESPN scoreboard API collector for Chicago team game scores."""

from datetime import datetime, timedelta
from typing import Any

from constants.enums import ApiSource
from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.http import rate_limited_request
from utils.logger.logger import setup_logger

logger = setup_logger(__name__)

API_SOURCE = ApiSource.ESPNAPI.value


class ESPNCollector(APICollector):
    """Collects game scores for all Chicago teams from ESPN's scoreboard API."""

    def __init__(self) -> None:
        """Initialize with ESPN API config and Chicago team definitions."""
        super().__init__(API_SOURCE)
        self.chicago_teams: list[dict[str, Any]] = self.config['apis'][API_SOURCE][
            'chicago_teams'
        ]

    def collect_articles(self) -> list[dict[str, Any]]:
        """Fetch yesterday's and today's scores for all Chicago teams.

        Returns:
            List of score dicts, one per game involving a Chicago team.
        """
        scores: list[dict[str, Any]] = []
        date_range = (
            f'{(datetime.now() - timedelta(days=1)).strftime("%Y%m%d")}'
            f'-{datetime.now().strftime("%Y%m%d")}'
        )

        for team in self.chicago_teams:
            team_scores: list[dict[str, Any]] = []
            try:
                url = f'{self.url}/{team["sport"]}/{team["league"]}/scoreboard'
                response = rate_limited_request(
                    'GET',
                    url,
                    params={'dates': date_range},
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                data = response.json()

                for event in data.get('events', []):
                    competition = event['competitions'][0]
                    competitors = competition['competitors']
                    team_ids = [c['team']['id'] for c in competitors]

                    if str(team['team_id']) not in team_ids:
                        continue

                    score = self._parse_score(
                        event, competition, competitors, team['name']
                    )
                    if score:
                        team_scores.append(score)

                scores.extend(team_scores)
                logger.info(
                    f'Collected {len(team_scores)} scores for {team["name"]} from ESPN.'
                )

            except Exception as e:
                logger.error(f'Error collecting ESPN scores for {team["name"]}: {e}')

        return scores

    def _parse_score(
        self,
        event: dict[str, Any],
        competition: dict[str, Any],
        competitors: list[dict[str, Any]],
        chicago_team_name: str,
    ) -> dict[str, Any] | None:
        """Parse a single ESPN event into a structured score dict.

        Args:
            event: ESPN event object.
            competition: First competition from the event.
            competitors: List of competitor objects.
            chicago_team_name: Display name of the Chicago team.

        Returns:
            Parsed score dict, or None if home/away teams can't be identified.
        """
        status_type = competition.get('status', {}).get('type', {})

        home = next((c for c in competitors if c['homeAway'] == 'home'), None)
        away = next((c for c in competitors if c['homeAway'] == 'away'), None)

        if not home or not away:
            return None

        headline = next(iter(competition.get('headlines', [])), {})
        game_url = next(
            (
                link['href']
                for link in event.get('links', [])
                if 'summary' in link.get('rel', [])
            ),
            None,
        )

        return {
            'team': chicago_team_name,
            'game_id': event.get('id'),
            'date': event.get('date'),
            'season_type': event.get('season', {}).get('slug'),
            'status': status_type.get('description'),
            'status_detail': status_type.get('shortDetail'),
            'completed': status_type.get('completed', False),
            'home_team': home['team']['displayName'],
            'away_team': away['team']['displayName'],
            'home_score': home.get('score'),
            'away_score': away.get('score'),
            'home_record': next(
                (
                    r['summary']
                    for r in home.get('records', [])
                    if r.get('type') == 'total'
                ),
                None,
            ),
            'away_record': next(
                (
                    r['summary']
                    for r in away.get('records', [])
                    if r.get('type') == 'total'
                ),
                None,
            ),
            'home_hits': home.get('hits'),
            'away_hits': away.get('hits'),
            'home_errors': home.get('errors'),
            'away_errors': away.get('errors'),
            'venue': competition.get('venue', {}).get('fullName'),
            'neutral_site': competition.get('neutralSite', False),
            'headline': headline.get('description'),
            'short_link_text': headline.get('shortLinkText'),
            'game_url': game_url,
        }
