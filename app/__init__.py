from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager  # Import LoginManager
from .config import config
from flask_socketio import SocketIO, join_room # Import SocketIO
from flask_wtf.csrf import CSRFProtect


# Intialization
db = SQLAlchemy()
migrate = Migrate()

# Create an instance of LoginManager
login_manager = LoginManager()
# Set the login view. If a user tries to access a protected page, they'll be redirected here.
login_manager.login_view = 'auth.login'

socketio = SocketIO()  # Create a SocketIO instance
csrf = CSRFProtect()

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    print(f'User joined room: {room}')


def create_app(config_name='default'):
    """Application factory function."""
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    socketio.init_app(app) # Initialize SocketIO with the app
    csrf.init_app(app)  # Initialize CSRF protection


    # Import and register Blueprints
    from .auth.routes import auth_bp
    from .customer.routes import customer_bp
    from .tailor import tailor_bp
    from .delivery import delivery_bp
    from app.admin import admin_bp
    from app.notifications import notifications_bp  # Import the notifications blueprint
    
    # ... import other blueprints as you create them

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(customer_bp, url_prefix='/customer')
    app.register_blueprint(tailor_bp, url_prefix='/tailor')
    app.register_blueprint(delivery_bp, url_prefix='/delivery')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')  # Register the notifications blueprint
    # ... register other blueprints

    @app.route('/')
    def index():
        # return "Welcome to the On-Demand Tailoring Service!"
        return render_template('landing_page.html')

    return app


# The user_loader is crucial. It tells Flask-Login how to find a specific user from the ID stored in their session cookie.
from .models import User  # Should not import on top,geting circular import errors
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))