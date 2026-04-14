import requests

from constants.enums import ApiSource
from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

API_SOURCE = ApiSource.ESPNAPI.value


class ESPNCollector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)
        self.chicago_teams = self.config['apis'][API_SOURCE]['chicago_teams']

    def collect_articles(self):
        scores = []

        for team in self.chicago_teams:
            team_scores = []
            try:
                url = f"{self.url}/{team['sport']}/{team['league']}/scoreboard"
                response = requests.get(url, timeout=self.timeout_seconds)
                response.raise_for_status()
                data = response.json()

                for event in data.get('events', []):
                    competition = event['competitions'][0]
                    competitors = competition['competitors']
                    team_ids = [c['team']['id'] for c in competitors]

                    if str(team['team_id']) not in team_ids:
                        continue

                    score = self._parse_score(event, competition, competitors, team['name'])
                    if score:
                        team_scores.append(score)

                scores.extend(team_scores)
                logger.info(f"Collected {len(team_scores)} scores for {team['name']} from ESPN.")

            except Exception as e:
                logger.error(f"Error collecting ESPN scores for {team['name']}: {e}")

        return scores

    def _parse_score(self, event, competition, competitors, chicago_team_name):
        status = competition.get('status', {}).get('type', {})

        home = next((c for c in competitors if c['homeAway'] == 'home'), None)
        away = next((c for c in competitors if c['homeAway'] == 'away'), None)

        if not home or not away:
            return None

        return {
            'team': chicago_team_name,
            'game_id': event.get('id'),
            'date': event.get('date'),
            'home_team': home['team']['displayName'],
            'away_team': away['team']['displayName'],
            'home_score': home.get('score'),
            'away_score': away.get('score'),
            'status': status.get('description'),
            'completed': status.get('completed', False),
            'venue': competition.get('venue', {}).get('fullName'),
        }
