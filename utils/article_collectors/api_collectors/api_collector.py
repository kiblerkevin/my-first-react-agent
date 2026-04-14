import os
import yaml
from constants.enums import (
    ApiSource
)
from dotenv import load_dotenv


config_path = 'config/sources.yaml'


class APICollector:
    
    def __init__(self, api_value: str):
        load_dotenv()
        
        with open(config_path, 'r') as file:
            self.config = yaml.safe_load(file)
        self.api_key = self.config['apis'][api_value].get('api_key_env_var', None)
        self.language = self.config['apis'][api_value].get('language', None)
        self.lookback_hours = self.config['collection']['lookback_hours']
        self.page_size = self.config['apis'][api_value].get('page_size', None)
        self.sort_by = self.config['apis'][api_value].get('sort_by', None)
        self.timeout_seconds = self.config['collection']['timeout_seconds']
        self.url = self.config['apis'][api_value]['url']
        
    def collect_articles(self):
        pass