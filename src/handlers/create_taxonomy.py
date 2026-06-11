"""Lambda handler: Assign categories and tags for the blog post."""

from collections import Counter

from src.shared.config import APPROVAL_EXPIRY_HOURS
from src.shared.dynamo_memory import DynamoMemory

memory = DynamoMemory()

DEFAULT_CATEGORY = "Daily Recap"
MAX_PLAYER_TAGS = 4


def handler(event, context):
    run_id = event.get("run_id")

    checkpoint = memory.get_checkpoint(run_id)
    draft_data = checkpoint["data"]["draft_and_evaluate"]
    summaries_data = checkpoint["data"]["summarize_articles"]

    best_draft = draft_data["best_draft"]
    relevant = summaries_data["relevant"]

    teams_covered = best_draft.get("teams_covered", [])

    # Gather all players mentioned
    all_players: list[str] = []
    for s in relevant:
        all_players.extend(s.get("players_mentioned", []))

    # Build categories
    categories = []
    category_names = [DEFAULT_CATEGORY] + list(teams_covered)
    for name in category_names:
        cat = memory.get_or_create_category(name)
        categories.append(cat)

    # Build tags: teams + top players
    tag_names: list[str] = list(teams_covered)
    if all_players:
        top_players = [name for name, _ in Counter(all_players).most_common(MAX_PLAYER_TAGS)]
        tag_names.extend(top_players)

    seen: set[str] = set()
    unique_tag_names = []
    for name in tag_names:
        if name not in seen:
            seen.add(name)
            unique_tag_names.append(name)

    tags = []
    for name in unique_tag_names:
        tag = memory.get_or_create_tag(name)
        tags.append(tag)

    memory.save_checkpoint(run_id, "create_taxonomy", {
        "categories": categories,
        "tags": tags,
    })

    return {"category_count": len(categories), "tag_count": len(tags)}
