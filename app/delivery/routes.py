from flask import render_template, redirect, session, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from datetime import datetime
from .. import db
from . import delivery_bp
from ..models import Logistic, MeasurementProfile, Order, OrderMeasurementValue, SavedMeasurementValue, SubProfile
from sqlalchemy.sql import func
import random
from app import socketio  # Note: Imported but not used in this blueprint; consider removing if unnecessary
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
    # Check for active tasks
    active_task = Logistic.query.filter(
        Logistic.delivery_partner_id == current_user.id,
        Logistic.status.in_(['assigned', 'in_transit_to_tailor'])
    ).first()

    # Fetch available tasks only if no active task
    available_tasks = []
    if not active_task:
        available_tasks = Logistic.query.filter_by(
            delivery_partner_id=None,
            status='assigned'
        ).all()

    # Fetch completed tasks for the partner
    completed_tasks = Logistic.query.filter_by(
        delivery_partner_id=current_user.id,
        status='completed'
    ).all()

    # Calculate total earnings from completed tasks
    earnings = db.session.query(func.sum(Logistic.delivery_fee)).filter(
        Logistic.delivery_partner_id == current_user.id,
        Logistic.status == 'completed'
    ).scalar() or 0.0

    return render_template(
        'delivery/dashboard.html',
        active_task=active_task,
        available_tasks=available_tasks,
        completed_tasks=completed_tasks,
        earnings=earnings,
        current_year=datetime.now().year
    )

# Task Management Routes
@delivery_bp.route('/task/<int:task_id>/accept', methods=['POST'])
@login_required
@delivery_partner_required
def accept_task(task_id):
    """Allow delivery partner to claim an available task."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        # Check if the partner already has an active task
        if Logistic.query.filter_by(delivery_partner_id=current_user.id, status='assigned').first():
            flash("You already have an active task. Complete it before accepting a new one.", "warning")
            return redirect(url_for('delivery.dashboard'))

        # Assign the task if available
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
    
    # Determine required measurements, contact person, and address based on task type
    required_measurements = []
    contact_person = None
    contact_address = None
    if task.task_type == 'pickup_from_customer':
        contact_person = task.order.customer
        contact_address = task.order.delivery_address
        if task.order.measurement_method == 'home_visit' and task.status == 'assigned':
            required_measurements = task.order.items[0].tailor_service.custom_measurements  # Note: Assumes single order item; refactor if multi-item support needed
    elif task.task_type == 'pickup_from_tailor':
        contact_person = task.order.tailor
        contact_address = task.order.tailor.addresses[0] if task.order.tailor.addresses else None
        if not contact_address:
            flash("Tailor's address is not available.", "warning")
    elif task.task_type == 'drop_to_customer':
        contact_person = task.order.customer
        contact_address = task.order.delivery_address

    # Define journey steps based on task type
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
        journey_steps=journey_steps,
        current_year=datetime.now().year
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

    # Determine the appropriate form based on task type and status
    if task.task_type == 'pickup_from_customer' and task.order.measurement_method == 'home_visit' and task.status == 'assigned':
        form = DeliveryMeasurementForm(measurement_fields=task.order.items[0].tailor_service.custom_measurements)  # Note: Assumes single order item; refactor if multi-item support needed
    else:
        form = OTPVerificationForm()

    if request.method == 'POST':
        if form.validate_on_submit():
            # Determine the correct OTP based on task type and status
            correct_otp = None
            if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
                correct_otp = task.pickup_otp
            elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
                correct_otp = task.tailor_handover_otp
            elif task.task_type == 'pickup_from_tailor':
                correct_otp = task.pickup_otp
            elif task.task_type == 'drop_to_customer':
                correct_otp = task.delivery_otp

            submitted_otp = form.otp.data
            if submitted_otp != correct_otp:
                flash('Invalid OTP. Please try again.', 'danger')
                return redirect(url_for('delivery.task_details', task_id=task.id))

            order = task.order
            if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
                task.status = 'in_transit_to_tailor'
                order.order_status = 'fabric_in_transit'
                if order.measurement_method == 'home_visit':
                    order_item = order.items[0]  # Note: Assumes single item
                    # This list will hold the measurement values we just collected
                    collected_measurements = []
                    for field in order_item.tailor_service.custom_measurements:
                        value = form[f'measurement_{field.id}'].data
                        
                        if value:
                            measurement_value = OrderMeasurementValue(
                                order_item_id=order_item.id,
                                measurement_field_id=field.id,
                                value=float(value)
                            )
                            db.session.add(measurement_value)
                            collected_measurements.append(measurement_value)
                    
                    # --- THIS IS THE NEW AUTOMATION LOGIC ---
                    # Now, automatically create a saved profile for the customer
                    
                    # Find the customer's sub-profile being shopped for
                    active_profile = SubProfile.query.get(session.get('active_profile_id'))
                    profile_name = f"{active_profile.name}'s {order_item.tailor_service.service.name} - {datetime.utcnow().strftime('%d %b %Y')}"

                    new_measurement_profile = MeasurementProfile(
                        user_id=order.customer_id,
                        sub_profile_id=session.get('active_profile_id'),
                        service_id=order_item.tailor_service.service_id,
                        profile_name=profile_name
                    )
                    db.session.add(new_measurement_profile)
                    db.session.commit() # Commit to get the ID

                    # Copy the collected measurements into the new saved profile
                    for mv in collected_measurements:
                        db.session.add(SavedMeasurementValue(
                            profile_id=new_measurement_profile.id,
                            measurement_field_id=mv.measurement_field_id,
                            value=mv.value
                        ))
                    
                    flash('Measurements submitted and automatically saved for the customer.', 'info')
                    db.session.commit()
                    # --- END OF NEW LOGIC ---
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

        # Flash form errors
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {field}: {error}", "danger")
        return redirect(url_for('delivery.task_details', task_id=task.id))

    return render_template('delivery/verify_otp.html', task=task, form=form, current_year=datetime.now().year)