from collections import defaultdict

from utils.logger.logger import setup_logger

logger = setup_logger(__name__)


def consolidate_summaries(summaries: list) -> list:
    """
    Merges game_recap summaries for the same team into single entries.
    Non-game summaries (trade, injury, draft, etc.) are left as individual entries.
    Returns a new list of consolidated summaries.
    """
    by_team = defaultdict(lambda: {'game_recaps': [], 'other': []})

    for s in summaries:
        team = s.get('team', 'Unknown')
        if s.get('event_type') == 'game_recap':
            by_team[team]['game_recaps'].append(s)
        else:
            by_team[team]['other'].append(s)

    consolidated = []

    for team, groups in by_team.items():
        # Merge all game_recap summaries for this team into one
        recaps = groups['game_recaps']
        if len(recaps) > 1:
            merged = _merge_recaps(team, recaps)
            consolidated.append(merged)
            logger.info(f"Consolidated {len(recaps)} game recaps for {team} into 1 summary.")
        elif len(recaps) == 1:
            consolidated.append(recaps[0])

        # Keep non-game summaries as-is
        consolidated.extend(groups['other'])

    return consolidated


def _merge_recaps(team: str, recaps: list) -> dict:
    """Merge multiple game_recap summaries into one consolidated entry."""
    # Concatenate summary texts
    combined_summary = ' '.join(r.get('summary', '') for r in recaps if r.get('summary'))

    # Combine all players mentioned, deduplicated
    all_players = []
    seen = set()
    for r in recaps:
        for p in r.get('players_mentioned', []):
            if p not in seen:
                seen.add(p)
                all_players.append(p)

    # Use the first recap's URL as the primary reference
    return {
        'url': recaps[0].get('url', ''),
        'team': team,
        'summary': combined_summary,
        'event_type': 'game_recap',
        'players_mentioned': all_players,
        'is_relevant': True
    }
