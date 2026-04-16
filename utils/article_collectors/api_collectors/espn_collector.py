from datetime import datetime, timedelta

from constants.enums import ApiSource
from utils.article_collectors.api_collectors.api_collector import APICollector
from utils.http import rate_limited_request
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

API_SOURCE = ApiSource.ESPNAPI.value


class ESPNCollector(APICollector):
    def __init__(self):
        super().__init__(API_SOURCE)
        self.chicago_teams = self.config['apis'][API_SOURCE]['chicago_teams']

    def collect_articles(self):
        scores = []
        date_range = (
            f"{(datetime.now() - timedelta(days=1)).strftime('%Y%m%d')}"
            f"-{datetime.now().strftime('%Y%m%d')}"
        )

        for team in self.chicago_teams:
            team_scores = []
            try:
                url = f"{self.url}/{team['sport']}/{team['league']}/scoreboard"
                response = rate_limited_request('GET', url, params={'dates': date_range}, timeout=self.timeout_seconds)
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
        status_type = competition.get('status', {}).get('type', {})

        home = next((c for c in competitors if c['homeAway'] == 'home'), None)
        away = next((c for c in competitors if c['homeAway'] == 'away'), None)

        if not home or not away:
            return None

        headline = next(iter(competition.get('headlines', [])), {})
        game_url = next(
            (l['href'] for l in event.get('links', []) if 'summary' in l.get('rel', [])),
            None
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
            'home_record': next((r['summary'] for r in home.get('records', []) if r.get('type') == 'total'), None),
            'away_record': next((r['summary'] for r in away.get('records', []) if r.get('type') == 'total'), None),
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
