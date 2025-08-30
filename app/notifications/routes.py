# app/notifications/routes.py
from flask import jsonify
from flask_login import login_required, current_user
from .. import db, socketio
from . import notifications_bp
from ..models import Notification
from datetime import datetime

# app/notifications/routes.py
def create_notification(user_id, message, link=None):
    """Create a notification in the database and emit a SocketIO event."""
    if user_id:
        # Store and emit to specific user
        notification = Notification(
            user_id=user_id,
            message=message,
            link=link,
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
        socketio.emit('new_notification', {
            'message': message,
            'link': link
        }, room=str(user_id))
    else:
        # Broadcast to a group (e.g., admins or delivery partners)
        role = 'admin' if 'admin' in link else 'delivery_partner'
        socketio.emit('new_notification', {
            'message': message,
            'link': link
        }, room=role)
        
        # Optionally store for all users of the role
        if role == 'admin':
            admins = User.query.filter_by(role='admin').all()
            for admin in admins:
                notification = Notification(
                    user_id=admin.id,
                    message=message,
                    link=link,
                    is_read=False,
                    created_at=datetime.utcnow()
                )
                db.session.add(notification)
        db.session.commit()

@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    """Return the number of unread notifications for the current user."""
    count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@notifications_bp.route('/all')
@login_required
def get_notifications():
    """Fetch the 5 most recent notifications and mark them as read."""
    notifications = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).limit(5).all()
    
    # Mark fetched notifications as read
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    
    return jsonify([{'message': n.message, 'link': n.link} for n in notifications])