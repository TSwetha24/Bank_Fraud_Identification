"""
Configuration Module
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration"""
    DEBUG = os.getenv('DEBUG', 'True') == 'True'
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./bank_fraud.db')
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
    API_PORT = int(os.getenv('API_PORT', 8000))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Verification thresholds
    MOTION_CONFIDENCE_THRESHOLD = 0.7
    LIVENESS_CONFIDENCE_THRESHOLD = 0.8
    MORPH_DETECTION_THRESHOLD = 0.6
    IRIS_MATCH_THRESHOLD = 0.7
    
    # Risk assessment thresholds
    LOW_RISK_THRESHOLD = 30
    MEDIUM_RISK_THRESHOLD = 60
    HIGH_RISK_THRESHOLD = 80
    
    # Session configuration
    SESSION_TIMEOUT_MINUTES = 30
    MAX_VERIFICATION_ATTEMPTS = 3
    
    # Feature flags
    ENABLE_MOTION_VERIFICATION = True
    ENABLE_LIVENESS_DETECTION = True
    ENABLE_MORPH_DETECTION = True
    ENABLE_IRIS_RECOGNITION = True
    ENABLE_TRUST_TOKEN = True
    
    # API configuration
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:8000').split(',')
    
    # Logging
    LOG_FILE = 'logs/bank_fraud.log'
    MAX_LOG_SIZE = 10485760  # 10MB
    BACKUP_COUNT = 5


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    DATABASE_URL = 'sqlite:///:memory:'


def get_config(env: str = None) -> Config:
    """Get configuration based on environment"""
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    if env == 'production':
        return ProductionConfig()
    elif env == 'testing':
        return TestingConfig()
    else:
        return DevelopmentConfig()
