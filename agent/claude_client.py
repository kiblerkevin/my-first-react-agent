from anthropic import Anthropic, RateLimitError
from typing import List, Dict
from dotenv import load_dotenv
from anthropic.types import Message
from langfuse import observe
import os
import time
import yaml

load_dotenv()

LLMS_CONFIG_PATH = 'config/llms.yaml'
ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

from utils.logger.logger import setup_logger
logger = setup_logger(__name__)


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

        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            rl_config = yaml.safe_load(f).get('rate_limiting', {})
        self._rl_max_retries = rl_config.get('max_retries', 3)
        self._rl_base_delay = rl_config.get('base_delay_seconds', 1.0)

    @observe(as_type="generation")
    def send_messages_with_tools(
            self,
            messages: List[Dict[str, str]],
            tools
    ) -> Message:
        for attempt in range(self._rl_max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    messages=messages,
                    tools=tools
                )
                return response
            except RateLimitError as e:
                if attempt < self._rl_max_retries:
                    delay = self._rl_base_delay * (2 ** attempt)
                    logger.warning(f"Anthropic rate limited — retrying in {delay:.1f}s (attempt {attempt + 1}/{self._rl_max_retries})")
                    time.sleep(delay)
                else:
                    raise Exception(f"Anthropic rate limit exceeded after {self._rl_max_retries} retries: {str(e)}")
            except Exception as e:
                raise Exception(f"Failed to create message: {str(e)}")

    @observe(as_type="generation")
    def send_message(self, user_message: str) -> str:
        for attempt in range(self._rl_max_retries + 1):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": user_message}]
                )
                return response.content[0].text
            except RateLimitError as e:
                if attempt < self._rl_max_retries:
                    delay = self._rl_base_delay * (2 ** attempt)
                    logger.warning(f"Anthropic rate limited — retrying in {delay:.1f}s (attempt {attempt + 1}/{self._rl_max_retries})")
                    time.sleep(delay)
                else:
                    raise Exception(f"Anthropic rate limit exceeded after {self._rl_max_retries} retries: {str(e)}")
            except Exception as e:
                raise Exception(f"Failed to create message: {str(e)}")
