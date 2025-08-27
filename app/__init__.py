from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager  # Import LoginManager
from .config import config


# Intialization
db = SQLAlchemy()
migrate = Migrate()

# Create an instance of LoginManager
login_manager = LoginManager()
# Set the login view. If a user tries to access a protected page, they'll be redirected here.
login_manager.login_view = 'auth.login'


def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Import and register Blueprints
    from .auth.routes import auth_bp
    from .customer.routes import customer_bp
    from .tailor import tailor_bp
    from .delivery import delivery_bp
    from app.admin import admin_bp
    
    # ... import other blueprints as you create them

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(tailor_bp, url_prefix='/tailor')
    app.register_blueprint(delivery_bp, url_prefix='/delivery')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    # ... register other blueprints

    @app.route('/')
    def index():
        return "Welcome to the On-Demand Tailoring Service!"

    return app


# The user_loader is crucial. It tells Flask-Login how to find a specific user from the ID stored in their session cookie.
from .models import User  # Should not import on top,geting circular import errors
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))