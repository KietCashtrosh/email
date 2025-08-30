# app/events.py
from flask_login import current_user
from . import socketio

@socketio.on('connect')
def handle_connect():
    """When a user connects, if they are logged in, join a room with their user_id."""
    if current_user.is_authenticated:
        socketio.join_room(str(current_user.id))
        print(f'Client {current_user.id} connected and joined room.')

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        socketio.leave_room(str(current_user.id))
        print(f'Client {current_user.id} disconnected and left room.')