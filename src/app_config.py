from common.annotation.component import Component
from common.config.config import load_config


@Component
class AppConfig:
    def __init__(self):
        config = load_config()

        self.config = config