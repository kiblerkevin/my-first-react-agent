from anthropic import Anthropic
from typing import List, Dict
from dotenv import load_dotenv
from anthropic.types import Message
import os
import yaml

load_dotenv()

LLMS_CONFIG_PATH = 'config/llms.yaml'


class ClaudeClient:
    def __init__(self, system_prompt: str, output_schema: object = None):
        self.system_prompt = system_prompt
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        self.output_schema = output_schema

        with open(LLMS_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        self.model = config['claude']['model']
        self.temperature = config['claude']['temperature']
        self.max_tokens = config['claude']['max_tokens']

    def send_messages_with_tools(
            self,
            messages: List[Dict[str, str]],
            tools
    ) -> Message:
        try:
            return self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=messages,
                tools=tools
            )
        except Exception as e:
            raise Exception(f"Failed to create message: {str(e)}")

    def send_message(self, user_message: str) -> str:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[{"role": "user", "content": user_message}]
            )
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Failed to create message: {str(e)}")