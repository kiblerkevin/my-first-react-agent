from pydantic import BaseModel

class BaseTool(BaseModel):
    name: str
    description: str
    input_schema: dict
    output_schema: dict

    def execute(self, input: dict) -> dict:
        raise NotImplementedError("Each tool must implement its own execute method.")