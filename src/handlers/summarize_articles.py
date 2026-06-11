"""Lambda handler: Summarize top articles per team via LLM."""

import json
from collections import defaultdict

from bs4 import BeautifulSoup

from agent.claude_client import ClaudeClient
from prompts.summarize_article_prompt import SUMMARIZE_ARTICLE_PROMPT
from src.shared.config import (
    LLM_SUMMARIZER_MAX_TOKENS,
    LLM_SUMMARIZER_MODEL,
    LLM_SUMMARIZER_TEMPERATURE,
)
from src.shared.dynamo_memory import DynamoMemory
from utils.consolidate import consolidate_summaries
from utils.http import rate_limited_request

memory = DynamoMemory()

MAX_CONTENT_CHARS = 3000


def handler(event, context):
    """Summarize top articles per team using LLM with caching."""
    run_id = event.get('run_id')
    max_articles_per_team = event.get('max_articles_per_team', 2)

    checkpoint = memory.get_checkpoint(run_id)
    unique_articles = checkpoint['data']['deduplicate_articles']['unique_articles']

    # Group by team
    by_team: dict[str, list] = defaultdict(list)
    for article in unique_articles:
        by_team[article.get('team', 'Unknown')].append(article)

    claude = ClaudeClient(system_prompt=SUMMARIZE_ARTICLE_PROMPT)
    claude.model = LLM_SUMMARIZER_MODEL
    claude.temperature = LLM_SUMMARIZER_TEMPERATURE
    claude.max_tokens = LLM_SUMMARIZER_MAX_TOKENS

    all_summaries = []
    all_stats = []

    for team, articles in by_team.items():
        top = sorted(articles, key=lambda a: a.get('relevance_score', 0), reverse=True)[
            :max_articles_per_team
        ]
        stats = {
            'team': team,
            'articles_fetched': len(articles),
            'articles_summarized': 0,
            'cache_hits': 0,
            'cache_misses': 0,
        }

        for article in top:
            url = article['url']
            cached = memory.get_article_summary(url)
            if cached:
                all_summaries.append(cached)
                stats['articles_summarized'] += 1
                stats['cache_hits'] += 1
                continue

            content = _fetch_content(url)
            prompt = _build_prompt(article, team, content)

            try:
                response_text = claude.send_message(prompt)
                response_text = (
                    response_text.strip()
                    .removeprefix('```json')
                    .removeprefix('```')
                    .removesuffix('```')
                    .strip()
                )
                parsed = json.loads(response_text)
                summary_data = {
                    'url': url,
                    'team': team,
                    'summary': parsed.get('summary', ''),
                    'event_type': parsed.get('event_type', 'other'),
                    'players_mentioned': parsed.get('players_mentioned', []),
                    'is_relevant': False
                    if content is None
                    else parsed.get('is_relevant', True),
                }
            except Exception:
                summary_data = {
                    'url': url,
                    'team': team,
                    'summary': article.get('title', ''),
                    'event_type': 'other',
                    'players_mentioned': [],
                    'is_relevant': False,
                }

            memory.save_article_summary(summary_data)
            all_summaries.append(summary_data)
            stats['articles_summarized'] += 1
            stats['cache_misses'] += 1

        all_stats.append(stats)

    relevant = [s for s in all_summaries if s.get('is_relevant')]
    relevant = consolidate_summaries(relevant)

    memory.save_summary_stats(run_id, all_stats)
    memory.save_checkpoint(
        run_id,
        'summarize_articles',
        {
            'summaries': all_summaries,
            'relevant': relevant,
        },
    )

    return {'summary_count': len(all_summaries), 'relevant_count': len(relevant)}


def _fetch_content(url: str) -> str | None:
    try:
        response = rate_limited_request(
            'GET', url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            tag.decompose()
        return soup.get_text(separator=' ', strip=True)[:MAX_CONTENT_CHARS]
    except Exception:
        return None


def _build_prompt(article: dict, team: str, content: str | None) -> str:
    lines = [
        f'Team: {team}',
        f'Title: {article.get("title", "")}',
        f'Published: {article.get("publishedAt", "unknown")}',
    ]
    if content:
        lines.append(f'Content: {content}')
    else:
        lines.append(
            'Content: unavailable — summarize from title only and set is_relevant to false.'
        )
    return '\n'.join(lines)
