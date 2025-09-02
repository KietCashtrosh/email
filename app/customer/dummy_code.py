# app/__init__.py (for context, not a route file, but needed for SocketIO setup)
from flask import Flask
from flask_socketio import SocketIO, join_room
from flask_login import LoginManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")  # Adjust for production
login_manager = LoginManager(app)

# SocketIO event to handle room joins
@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)
    print(f'User joined room: {room}')

# Import blueprints (assumed to be registered in app/__init__.py)
from .admin import admin_bp
from .customer import customer_bp
from .delivery import delivery_bp
from .notifications import notifications_bp
from .tailor import tailor_bp

# app/admin/routes.py
from flask import redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from .. import db
from ..models import User
from . import admin_bp
from ..notifications.routes import create_notification

# Custom decorator to restrict access to admins only
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Display admin dashboard."""
    # Placeholder for admin dashboard logic
    return render_template('admin/dashboard.html')

@admin_bp.route('/tailors/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_tailor(user_id):
    """Approve a tailor's profile and send notifications."""
    tailor = User.query.get_or_404(user_id)
    if tailor.role == 'tailor' and hasattr(tailor, 'tailor_profile'):
        tailor.tailor_profile.is_verified = True
        db.session.commit()
        create_notification(
            user_id=user_id,
            message="Your tailor profile has been approved! You can now accept orders.",
            link=url_for('tailor.dashboard')
        )
        create_notification(
            user_id=None,  # Admin room
            message=f"Tailor ID #{user_id} has been approved.",
            link=url_for('admin.user_details', user_id=user_id)
        )
        flash('Tailor approved.', 'success')
    else:
        flash('Invalid tailor profile.', 'danger')
    return redirect(url_for('admin.dashboard'))

# app/customer/routes.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .. import db
from ..models import Order, OrderItem, Address, TailorService, OrderMeasurementValue
from . import customer_bp
from ..notifications.routes import create_notification

@customer_bp.route('/dashboard')
@login_required
def dashboard():
    """Display customer dashboard."""
    # Placeholder for customer dashboard logic
    return render_template('customer/dashboard.html')

@customer_bp.route('/order/new/<int:tailor_service_id>', methods=['GET', 'POST'])
@login_required
def new_order(tailor_service_id):
    """Create a new order and send notifications."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    required_measurements = tailor_service.custom_measurements

    if request.method == 'POST':
        address = Address.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not address:
            flash("Please set a default address in your profile.", "danger")
            return redirect(url_for('customer.profile'))

        order = Order(
            customer_id=current_user.id,
            tailor_id=tailor_service.tailor_id,
            delivery_address_id=address.id,
            total_amount=tailor_service.price,
            order_status='pending_tailor_acceptance',
            measurement_method='online_submission'
        )
        db.session.add(order)
        db.session.commit()

        order_item = OrderItem(order_id=order.id, tailor_service_id=tailor_service.id)
        db.session.add(order_item)
        db.session.commit()

        for measurement_field in required_measurements:
            value = request.form.get(f"measurement_{measurement_field.id}")
            if value:
                measurement_value = OrderMeasurementValue(
                    order_item_id=order_item.id,
                    measurement_field_id=measurement_field.id,
                    value=float(value)
                )
                db.session.add(measurement_value)

        db.session.commit()

        # Notify customer
        create_notification(
            user_id=current_user.id,
            message=f"Your order #{order.id} has been placed and is awaiting tailor acceptance.",
            link=url_for('customer.order_details', order_id=order.id)
        )
        # Notify tailor
        create_notification(
            user_id=tailor_service.tailor_id,
            message=f"New order #{order.id} is awaiting your acceptance.",
            link=url_for('tailor.order_details', order_id=order.id)
        )

        flash("Your order has been placed successfully!", "success")
        return redirect(url_for('customer.confirm_order', order_id=order.id))

    return render_template(
        'customer/new_order.html',
        tailor_service=tailor_service,
        required_measurements=required_measurements
    )

# app/delivery/routes.py
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy.sql import func
import random
from .. import db, socketio
from ..models import Logistic, Order, OrderMeasurementValue
from . import delivery_bp
from ..notifications.routes import create_notification

# Custom decorator to restrict access to delivery partners only
def delivery_partner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'delivery_partner':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@delivery_bp.route('/dashboard')
@login_required
@delivery_partner_required
def dashboard():
    """Display delivery partner's dashboard with available, active, and completed tasks."""
    active_task = Logistic.query.filter(
        Logistic.delivery_partner_id == current_user.id,
        Logistic.status.in_(['assigned', 'in_transit_to_tailor'])
    ).first()

    available_tasks = []
    if not active_task:
        available_tasks = Logistic.query.filter_by(
            delivery_partner_id=None,
            status='assigned'
        ).all()

    completed_tasks = Logistic.query.filter_by(
        delivery_partner_id=current_user.id,
        status='completed'
    ).all()

    earnings = db.session.query(func.sum(Logistic.delivery_fee)).filter(
        Logistic.delivery_partner_id == current_user.id,
        Logistic.status == 'completed'
    ).scalar() or 0.0

    return render_template(
        'delivery/dashboard.html',
        active_task=active_task,
        available_tasks=available_tasks,
        completed_tasks=completed_tasks,
        earnings=earnings
    )

@delivery_bp.route('/task/<int:task_id>/accept', methods=['POST'])
@login_required
@delivery_partner_required
def accept_task(task_id):
    """Allow delivery partner to claim an available task."""
    if Logistic.query.filter_by(delivery_partner_id=current_user.id, status='assigned').first():
        flash("You already have an active task. Complete it before accepting a new one.", "warning")
        return redirect(url_for('delivery.dashboard'))

    task = Logistic.query.get_or_404(task_id)
    if task.delivery_partner_id is None:
        task.delivery_partner_id = current_user.id
        db.session.commit()
        flash(f"Task #{task.id} has been assigned to you!", "success")
    else:
        flash("This task has already been taken by another partner.", "danger")

    return redirect(url_for('delivery.dashboard'))

@delivery_bp.route('/task/<int:task_id>/details')
@login_required
@delivery_partner_required
def task_details(task_id):
    """Display detailed information for an active task, including journey steps."""
    task = Logistic.query.get_or_404(task_id)
    
    if task.delivery_partner_id != current_user.id:
        flash("You do not have permission to view this task.", "danger")
        return redirect(url_for('delivery.dashboard'))
    
    required_measurements = []
    contact_person = None
    contact_address = None

    if task.task_type == 'pickup_from_customer':
        contact_person = task.order.customer
        contact_address = task.order.delivery_address
        if task.order.measurement_method == 'home_visit' and task.status == 'assigned':
            required_measurements = task.order.items[0].tailor_service.custom_measurements
    elif task.task_type == 'pickup_from_tailor':
        contact_person = task.order.tailor
        contact_address = task.order.tailor.addresses[0] if task.order.tailor.addresses else None
        if not contact_address:
            flash("Tailor's address is not available.", "warning")
    elif task.task_type == 'drop_to_customer':
        contact_person = task.order.customer
        contact_address = task.order.delivery_address

    journey_steps = []
    if task.task_type == 'pickup_from_customer':
        journey_steps = [
            {
                'title': 'Pickup From Customer',
                'contact': task.order.customer,
                'address': task.order.delivery_address,
                'is_active': task.status == 'assigned'
            },
            {
                'title': 'Drop-off To Tailor',
                'contact': task.order.tailor,
                'address': task.order.tailor.addresses[0] if task.order.tailor.addresses else None,
                'is_active': task.status == 'in_transit_to_tailor'
            }
        ]
    elif task.task_type == 'pickup_from_tailor':
        journey_steps = [
            {
                'title': 'Pickup From Tailor',
                'contact': task.order.tailor,
                'address': task.order.tailor.addresses[0] if task.order.tailor.addresses else None,
                'is_active': True
            }
        ]
    elif task.task_type == 'drop_to_customer':
        journey_steps = [
            {
                'title': 'Deliver To Customer',
                'contact': task.order.customer,
                'address': task.order.delivery_address,
                'is_active': True
            }
        ]

    return render_template(
        'delivery/task_details.html',
        task=task,
        contact_person=contact_person,
        contact_address=contact_address,
        required_measurements=required_measurements,
        journey_steps=journey_steps
    )

@delivery_bp.route('/task/<int:task_id>/verify', methods=['GET', 'POST'])
@login_required
@delivery_partner_required
def verify_otp(task_id):
    """Verify OTP and process task actions (e.g., pickup, handover, delivery)."""
    task = Logistic.query.get_or_404(task_id)
    
    if task.delivery_partner_id != current_user.id:
        flash("You are not assigned to this task.", "danger")
        return redirect(url_for('delivery.dashboard'))

    if request.method == 'POST':
        submitted_otp = request.form.get('otp')
        order = task.order
        
        correct_otp = None
        if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
            correct_otp = task.pickup_otp
        elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
            correct_otp = task.tailor_handover_otp
        elif task.task_type == 'pickup_from_tailor':
            correct_otp = task.pickup_otp
        elif task.task_type == 'drop_to_customer':
            correct_otp = task.delivery_otp

        if submitted_otp != correct_otp:
            flash('Invalid OTP. Please try again.', 'danger')
            return redirect(url_for('delivery.task_details', task_id=task.id))

        if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
            task.status = 'in_transit_to_tailor'
            order.order_status = 'fabric_in_transit'
            if order.measurement_method == 'home_visit':
                order_item = order.items[0]
                required_measurements = order_item.tailor_service.custom_measurements
                for field in required_measurements:
                    value = request.form.get(f"measurement_{field.id}")
                    if value:
                        measurement_value = OrderMeasurementValue(
                            order_item_id=order_item.id,
                            measurement_field_id=field.id,
                            value=float(value)
                        )
                        db.session.add(measurement_value)
            db.session.commit()
            create_notification(
                user_id=order.customer_id,
                message=f"Your Order #{order.id} fabric has been picked up and is in transit to the tailor.",
                link=url_for('customer.order_details', order_id=order.id)
            )
            flash('Pickup from customer confirmed. Please proceed to the tailor.', 'success')
            return redirect(url_for('delivery.dashboard'))

        elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
            task.status = 'completed'
            order.order_status = 'in_progress'
            db.session.commit()
            create_notification(
                user_id=order.customer_id,
                message=f"Your Order #{order.id} has been delivered to the tailor and stitching is in progress!",
                link=url_for('customer.order_details', order_id=order.id)
            )
            create_notification(
                user_id=order.tailor_id,
                message=f"Order #{order.id} fabric has arrived. You can start stitching now.",
                link=url_for('tailor.order_details', order_id=order.id)
            )
            create_notification(
                user_id=None,
                message=f"Order #{order.id} fabric delivered to tailor.",
                link=url_for('admin.order_details', order_id=order.id)
            )
            flash('Handover to tailor confirmed. Pickup task is complete!', 'success')
            return redirect(url_for('delivery.dashboard'))

        elif task.task_type == 'pickup_from_tailor':
            task.status = 'completed'
            order.order_status = 'out_for_delivery'
            delivery_otp = str(random.randint(100000, 999999))
            final_task = Logistic(
                order_id=order.id,
                delivery_partner_id=current_user.id,
                task_type='drop_to_customer',
                status='assigned',
                delivery_otp=delivery_otp
            )
            db.session.add(final_task)
            db.session.commit()
            create_notification(
                user_id=order.customer_id,
                message=f"Your Order #{order.id} has been picked up from the tailor and is now out for delivery!",
                link=url_for('customer.order_details', order_id=order.id)
            )
            flash('Pickup from tailor confirmed. You have been assigned the final delivery.', 'success')
            return redirect(url_for('delivery.dashboard'))

        elif task.task_type == 'drop_to_customer':
            task.status = 'completed'
            order.order_status = 'completed'
            if order.payment_method != 'online_full':
                order.payment_status = 'fully_paid'
            db.session.commit()
            create_notification(
                user_id=order.customer_id,
                message=f"Your Order #{order.id} has been delivered successfully!",
                link=url_for('customer.order_details', order_id=order.id)
            )
            create_notification(
                user_id=order.tailor_id,
                message=f"Order #{order.id} has been delivered to the customer.",
                link=url_for('tailor.order_details', order_id=order.id)
            )
            flash('Final delivery confirmed. Order complete!', 'success')
            return redirect(url_for('delivery.dashboard'))

    return render_template('delivery/verify_otp.html', task=task)

# app/notifications/routes.py
from flask import jsonify
from flask_login import login_required, current_user
from .. import db, socketio
from ..models import Notification
from . import notifications_bp
from datetime import datetime

def create_notification(user_id, message, link=None):
    """Create a notification in the database and emit a SocketIO event."""
    if user_id:
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
        role = 'admin' if 'admin' in link else 'delivery_partner'
        socketio.emit('new_notification', {
            'message': message,
            'link': link
        }, room=role)
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
    
    for notification in notifications:
        notification.is_read = True
    db.session.commit()
    
    return jsonify([{'message': n.message, 'link': n.link} for n in notifications])

# app/tailor/routes.py
from flask import render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from functools import wraps
from .. import db
from ..models import Order, Logistic
from . import tailor_bp
from ..notifications.routes import create_notification
import random

# Custom decorator to restrict access to tailors only
def tailor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'tailor':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@tailor_bp.route('/dashboard')
@login_required
@tailor_required
def dashboard():
    """Display tailor dashboard."""
    # Placeholder for tailor dashboard logic
    return render_template('tailor/dashboard.html')

@tailor_bp.route('/order/<int:order_id>/accept', methods=['POST'])
@login_required
@tailor_required
def accept_order(order_id):
    """Accept an order and create a delivery task."""
    order = Order.query.get_or_404(order_id)
    
    if order.tailor_id != current_user.id:
        flash("You do not have permission to accept this order.", "danger")
        return redirect(url_for('tailor.dashboard'))
    
    order.order_status = 'awaiting_pickup'
    pickup_otp = str(random.randint(100000, 999999))
    tailor_otp = str(random.randint(100000, 999999))
    new_task = Logistic(
        order_id=order.id,
        delivery_partner_id=None,
        task_type='pickup_from_customer',
        status='assigned',
        pickup_otp=pickup_otp,
        tailor_handover_otp=tailor_otp
    )
    db.session.add(new_task)
    db.session.commit()

    create_notification(
        user_id=order.customer_id,
        message=f"Your Order #{order.id} has been accepted by the tailor.",
        link=url_for('customer.order_details', order_id=order.id)
    )
    create_notification(
        user_id=None,
        message=f"New pickup task available for Order #{order.id}",
        link=url_for('delivery.task_details', task_id=new_task.id)
    )
    
    flash(f"Order #{order.id} accepted. A task is now available for delivery partners.", "success")
    return redirect(url_for('tailor.dashboard'))