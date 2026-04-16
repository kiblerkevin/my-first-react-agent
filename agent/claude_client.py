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
        self.cost_per_million_input = config['claude'].get('cost_per_million_input', 0.0)
        self.cost_per_million_output = config['claude'].get('cost_per_million_output', 0.0)

        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0

    def _track_usage(self, response):
        if hasattr(response, 'usage') and response.usage:
            self.total_input_tokens += response.usage.input_tokens
            self.total_output_tokens += response.usage.output_tokens
            self.call_count += 1

    def get_usage(self) -> dict:
        input_cost = (self.total_input_tokens / 1_000_000) * self.cost_per_million_input
        output_cost = (self.total_output_tokens / 1_000_000) * self.cost_per_million_output
        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'call_count': self.call_count,
            'estimated_cost': round(input_cost + output_cost, 6)
        }

    def reset_usage(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0

    def send_messages_with_tools(
            self,
            messages: List[Dict[str, str]],
            tools
    ) -> Message:
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=messages,
                tools=tools
            )
            self._track_usage(response)
            return response
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
            self._track_usage(response)
            return response.content[0].text
        except Exception as e:
            raise Exception(f"Failed to create message: {str(e)}")
