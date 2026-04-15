from collections import Counter

import yaml

from tools.base_tool import BaseTool
from models.inputs.create_blog_taxonomy_input import CreateBlogTaxonomyInput
from models.outputs.create_blog_taxonomy_output import CreateBlogTaxonomyOutput
from memory.memory import Memory
from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

DATABASE_CONFIG_PATH = 'config/database.yaml'


class CreateBlogTaxonomyTool(BaseTool):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    input_model: type = CreateBlogTaxonomyInput

    name: str = "create_blog_taxonomy"
    description: str = (
        "Assigns WordPress categories and tags for a blog post based on teams covered "
        "and players mentioned. Always assigns a 'Daily Recap' category plus one category "
        "per team. Tags include team names and the top 4 most-mentioned players. "
        "Resolves names to local database IDs and WordPress IDs where available."
    )
    input_schema: dict = {
        "type": "object",
        "properties": {
            "teams_covered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Team names covered in the blog post."
            },
            "players_mentioned": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All player names mentioned across article summaries."
            }
        },
        "required": ["teams_covered"]
    }
    output_schema: dict = {
        "type": "object",
        "properties": {
            "categories": {"type": "array", "items": {"type": "object"}},
            "tags": {"type": "array", "items": {"type": "object"}},
            "new_categories": {"type": "array", "items": {"type": "string"}},
            "new_tags": {"type": "array", "items": {"type": "string"}}
        }
    }

    def __init__(self):
        super().__init__(
            name=self.model_fields['name'].default,
            description=self.model_fields['description'].default,
            input_schema=self.model_fields['input_schema'].default,
            output_schema=self.model_fields['output_schema'].default
        )
        with open(DATABASE_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.default_category = config['taxonomy']['default_category']
        self.max_player_tags = config['taxonomy']['max_player_tags']
        self.memory = Memory()

    def execute(self, input: CreateBlogTaxonomyInput) -> CreateBlogTaxonomyOutput:
        existing_categories = {c['name'] for c in self.memory.get_all_categories()}
        existing_tags = {t['name'] for t in self.memory.get_all_tags()}

        categories = []
        new_categories = []
        tags = []
        new_tags = []

        # Assign categories: Daily Recap + one per team
        category_names = [self.default_category] + list(input.teams_covered)
        for name in category_names:
            cat = self.memory.get_or_create_category(name)
            categories.append(cat)
            if name not in existing_categories:
                new_categories.append(name)

        # Assign tags: team names + top N players by mention frequency
        tag_names = list(input.teams_covered)
        if input.players_mentioned:
            player_counts = Counter(input.players_mentioned)
            top_players = [name for name, _ in player_counts.most_common(self.max_player_tags)]
            tag_names.extend(top_players)

        # Deduplicate tag names preserving order
        seen = set()
        unique_tag_names = []
        for name in tag_names:
            if name not in seen:
                seen.add(name)
                unique_tag_names.append(name)

        for name in unique_tag_names:
            tag = self.memory.get_or_create_tag(name)
            tags.append(tag)
            if name not in existing_tags:
                new_tags.append(name)

        logger.info(
            f"Taxonomy assigned: {len(categories)} categories, {len(tags)} tags "
            f"({len(new_categories)} new categories, {len(new_tags)} new tags)"
        )

        return CreateBlogTaxonomyOutput(
            categories=categories,
            tags=tags,
            new_categories=new_categories,
            new_tags=new_tags
        )
