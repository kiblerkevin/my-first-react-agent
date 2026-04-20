"""Base tool class for all agent-callable tools."""

from typing import Any

from pydantic import BaseModel


class BaseTool(BaseModel):
    """Abstract base for Pydantic-based tools with name, schema, and execute."""

    model_config = {'arbitrary_types_allowed': True, 'extra': 'allow'}

    name: str
    description: str
    input_schema: object
    output_schema: object

    def execute(self, input: Any) -> Any:
        """Execute the tool. Must be overridden by subclasses.

        Args:
            input: Validated input model instance.

        Returns:
            Output model instance.

        Raises:
            NotImplementedError: Always, unless overridden.
        """
        raise NotImplementedError('Each tool must implement its own execute method.')
