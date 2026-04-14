from pydantic import BaseModel

class BaseTool(BaseModel):
    model_config = {"arbitrary_types_allowed": True, "extra": "allow"}

    name: str
    description: str
    input_schema: object
    output_schema: object

    def execute(self, input: object) -> object:
        raise NotImplementedError("Each tool must implement its own execute method.")