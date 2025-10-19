import os
from typing import Dict, Type


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    DEBUG = False
    TESTING = False
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOGGING_CONFIG = os.environ.get("LOGGING_CONFIG", "logging.conf")
    DATABASE_NAME = os.environ.get("DATABASE_NAME", "spreadsheet.db")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name: Dict[str, Type[Config]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
