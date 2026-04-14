import os
import yaml
from constants.enums import (
    ApiSource
)


config_path = 'config/sources.yaml'


class APICollector:
    
    def __init__(self, api_value: str):
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        self.api_key = os.getenv(self.config['apis'][api_value]['env_key_name'])
        self.language = self.config['apis'][api_value]['language'] or None
        self.lookback_hours = self.config['collection']['lookback_hours']
        self.page_size = self.config['apis'][api_value]['page_size'] or None
        self.sort_by = self.config['apis'][api_value]['sort_by'] or None
        self.timeout_seconds = self.config['collection']['timeout_seconds']
        self.url = self.config['apis'][api_value]['url']
        
    def collect_articles(self):
        pass