import time

import requests
import yaml

from utils.logger.logger import setup_logger


logger = setup_logger(__name__)

ORCHESTRATION_CONFIG_PATH = 'config/orchestration.yaml'

_rate_limit_config = None


def _get_config():
    global _rate_limit_config
    if _rate_limit_config is None:
        with open(ORCHESTRATION_CONFIG_PATH, 'r') as f:
            config = yaml.safe_load(f)
        _rate_limit_config = config.get('rate_limiting', {})
    return _rate_limit_config


def rate_limited_request(method: str, url: str, **kwargs) -> requests.Response:
    """
    Wraps requests.get/post with retry-on-429 logic.
    Reads Retry-After header if present, otherwise uses exponential backoff.
    """
    config = _get_config()
    max_retries = config.get('max_retries', 3)
    base_delay = config.get('base_delay_seconds', 1.0)

    for attempt in range(max_retries + 1):
        response = requests.request(method, url, **kwargs)

        if response.status_code != 429:
            return response

        if attempt == max_retries:
            logger.warning(f"Rate limit exceeded after {max_retries} retries: {method} {url}")
            return response

        retry_after = response.headers.get('Retry-After')
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                delay = base_delay * (2 ** attempt)
        else:
            delay = base_delay * (2 ** attempt)

        logger.warning(f"Rate limited (429) on {method} {url} — retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
        time.sleep(delay)

    return response
