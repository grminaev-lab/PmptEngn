import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///database/polling.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    YANDEX_API_KEY = os.getenv('YANDEX_API_KEY')
    FOLDER_ID = os.getenv('FOLDER_ID')
    TIMEOUT = int(os.getenv('TIMEOUT', 30))
    
    @staticmethod
    def load_config():
        """Загрузка конфигурации из config.json"""
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_config(config_data):
        """Сохранение конфигурации в config.json"""
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)