"""Lambda handler: Deduplicate articles using fuzzy title matching."""

from collections import defaultdict

from rapidfuzz import fuzz

from src.shared.dynamo_memory import DynamoMemory

memory = DynamoMemory()

SIMILARITY_THRESHOLD = 85


def handler(event, context):
    run_id = event.get("run_id")
    max_articles_per_team = event.get("max_articles_per_team", 2)

    # Read articles from checkpoint
    checkpoint = memory.get_checkpoint(run_id)
    new_articles = checkpoint["data"]["fetch_articles"]["new_articles"]

    if not new_articles:
        memory.save_checkpoint(run_id, "deduplicate_articles", {"unique_articles": [], "duplicate_count": 0})
        return {"unique_count": 0}

    # Group by team
    by_team: dict[str, list] = defaultdict(list)
    for article in new_articles:
        by_team[article.get("team", "Unknown")].append(article)

    unique_articles = []
    duplicate_count = 0

    for team, articles in by_team.items():
        sorted_articles = sorted(articles, key=lambda a: a.get("relevance_score", 0), reverse=True)
        accepted: list[tuple[dict, str]] = []

        for article in sorted_articles:
            title = article.get("title", "")
            title_lower = title.lower()
            is_dup = False
            for _, accepted_title in accepted:
                if fuzz.token_sort_ratio(title_lower, accepted_title) >= SIMILARITY_THRESHOLD:
                    is_dup = True
                    duplicate_count += 1
                    break
            if not is_dup:
                accepted.append((article, title_lower))

        unique_articles.extend(a for a, _ in accepted)

    memory.save_checkpoint(run_id, "deduplicate_articles", {
        "unique_articles": unique_articles,
        "duplicate_count": duplicate_count,
    })

    return {"unique_count": len(unique_articles)}
