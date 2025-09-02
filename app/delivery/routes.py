from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from .. import db
from . import delivery_bp
from ..models import Logistic, Order, OrderMeasurementValue
from sqlalchemy.sql import func
import random
from app import socketio
from ..notifications.routes import create_notification
from app.forms import OTPVerificationForm, DeliveryMeasurementForm, SimpleSubmitForm

# Custom decorator to restrict access to delivery partners only
def delivery_partner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'delivery_partner':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dashboard Route
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

# Task Management Routes
@delivery_bp.route('/task/<int:task_id>/accept', methods=['POST'])
@login_required
@delivery_partner_required
def accept_task(task_id):
    """Allow delivery partner to claim an available task."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
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
    flash('Invalid form submission.', 'danger')
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
    """Verify OTP and process task actions, including measurement submission for home visits."""
    task = Logistic.query.get_or_404(task_id)
    if task.delivery_partner_id != current_user.id:
        flash("You are not assigned to this task.", "danger")
        return redirect(url_for('delivery.dashboard'))

    form = OTPVerificationForm()
    measurement_form = None
    if task.task_type == 'pickup_from_customer' and task.order.measurement_method == 'home_visit' and task.status == 'assigned':
        measurement_form = DeliveryMeasurementForm(measurement_fields=task.order.items[0].tailor_service.custom_measurements)
    else:
        measurement_form = OTPVerificationForm()  # Fallback to OTP-only form

    if request.method == 'POST':
        # Use the appropriate form based on task type and status
        active_form = measurement_form if measurement_form.__class__.__name__ == 'DeliveryMeasurementForm' else form
        if active_form.validate_on_submit():
            correct_otp = None
            if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
                correct_otp = task.pickup_otp
            elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
                correct_otp = task.tailor_handover_otp
            elif task.task_type == 'pickup_from_tailor':
                correct_otp = task.pickup_otp
            elif task.task_type == 'drop_to_customer':
                correct_otp = task.delivery_otp

            submitted_otp = active_form.otp.data
            if submitted_otp != correct_otp:
                flash('Invalid OTP. Please try again.', 'danger')
                return redirect(url_for('delivery.task_details', task_id=task.id))

            order = task.order
            if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
                task.status = 'in_transit_to_tailor'
                order.order_status = 'fabric_in_transit'
                if order.measurement_method == 'home_visit':
                    order_item = order.items[0]
                    for field in task.order.items[0].tailor_service.custom_measurements:
                        value = measurement_form[f'measurement_{field.id}'].data
                        if value:
                            measurement_value = OrderMeasurementValue(
                                order_item_id=order_item.id,
                                measurement_field_id=field.id,
                                value=float(value)
                            )
                            db.session.add(measurement_value)
                    create_notification(
                        order.customer_id,
                        f"Order #{order.id} fabric has been picked up and measurements submitted.",
                        url_for('customer.order_details', order_id=order.id)
                    )
                else:
                    create_notification(
                        order.customer_id,
                        f"Order #{order.id} fabric has been picked up.",
                        url_for('customer.order_details', order_id=order.id)
                    )
                flash('Pickup confirmed. Please proceed to the tailor.', 'success')

            elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
                task.status = 'completed'
                order.order_status = 'in_progress'
                create_notification(
                    order.customer_id,
                    f"Order #{order.id} is now with the tailor.",
                    url_for('customer.order_details', order_id=order.id)
                )
                create_notification(
                    order.tailor_id,
                    f"Fabric for Order #{order.id} has arrived.",
                    url_for('tailor.order_details', order_id=order.id)
                )
                flash('Handover to tailor confirmed. Task complete!', 'success')

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
                create_notification(
                    order.customer_id,
                    f"Your Order #{order.id} is out for delivery!",
                    url_for('customer.order_details', order_id=order.id)
                )
                flash('Pickup from tailor confirmed. Final delivery assigned.', 'success')

            elif task.task_type == 'drop_to_customer':
                task.status = 'completed'
                order.order_status = 'completed'
                if order.payment_method != 'online_full':
                    order.payment_status = 'fully_paid'
                create_notification(
                    order.customer_id,
                    f"Your Order #{order.id} has been delivered!",
                    url_for('customer.order_details', order_id=order.id)
                )
                create_notification(
                    order.tailor_id,
                    f"Order #{order.id} has been delivered.",
                    url_for('tailor.order_details', order_id=order.id)
                )
                flash('Final delivery confirmed. Order complete!', 'success')

            db.session.commit()
            return redirect(url_for('delivery.dashboard'))

        for field, errors in active_form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", "danger")
        return redirect(url_for('delivery.task_details', task_id=task.id))

    return render_template('delivery/verify_otp.html', task=task, form=measurement_form if measurement_form.__class__.__name__ == 'DeliveryMeasurementForm' else form)