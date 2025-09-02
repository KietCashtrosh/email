# app/config.py

import os

# Get the absolute path of the directory where the current file is located.
# This is used to create a reliable path to the SQLite database.
basedir = os.path.abspath(os.path.dirname(__file__))



class Config:
    """Base configuration class. Contains default settings."""
    # SECRET_KEY is crucial for security, used for session signing.
    # It's best practice to set this from an environment variable.
    # The default value is insecure and only for development convenience.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-hard-to-guess-string'
    
    # Disable a feature of Flask-SQLAlchemy that signals the application
    # every time a change is about to be made in the database.
    # It's often not needed and adds overhead.
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads/')

    @staticmethod
    def init_app(app):
        # This method can be used for configuration-specific initializations.
        pass


class DevelopmentConfig(Config):
    """Configuration for development."""
    DEBUG = True
    # Define the database URI for development (using a local SQLite file).
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app-dev.db')


class TestingConfig(Config):
    """Configuration for testing."""
    TESTING = True
    # Use an in-memory SQLite database for tests to keep them fast and clean.
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL') or 'sqlite://'


class ProductionConfig(Config):
    """Configuration for production."""
    # For production, it's highly recommended to use a robust database like PostgreSQL.
    # The DATABASE_URL environment variable should be set on your deployment server.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')

# A dictionary to access the configuration classes by name.
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig  # The default configuration to use.
}