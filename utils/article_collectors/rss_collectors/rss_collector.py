import yaml

config_path = 'config/sources.yaml'
class RssCollector:
    
    def __init__(self, rss_value: str):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.lookback_hours = self.config['collection']['lookback_hours']
        self.timeout_seconds = self.config['collection']['timeout_seconds']
        self.url = self.config['apis'][rss_value]['url']

    def collect_articles(self):
        # Implement RSS feed fetching logic here
        pass