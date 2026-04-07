from anthropic import Anthropic
from typing import List, Dict
from dotenv import load_dotenv
from anthropic.types import Message

import os

load_dotenv()


class ClaudeClient:
    def __init__(self, system_prompt: str, output_schema: object):
        self.system_prompt = system_prompt
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.output_schema = output_schema if output_schema else None

    def send_messages_with_tools(
            self,
            messages: List[Dict[str, str]],
            tools
    ) -> Message:
        try:
            return self.client.messages.create(
                max_tokens=1028,
                model="claude-sonnet-4-6",
                system=self.system_prompt,
                messages=messages,
                tools=tools,
                output_config={"format": {
                        "schema": self.output_schema,
                        "type": "json_schema"
                    }
                } if self.output_schema else {}
            )
        except Exception as e:
            raise Exception(f"Failed to create message: {str(e)}")