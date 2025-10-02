from flask import flash, redirect, url_for, render_template, request
from flask_login import current_user, login_required
from functools import wraps
from sqlalchemy import func
import random
from datetime import datetime
from app import db, socketio
from . import tailor_bp
from ..models import (
    User, TailorProfile, Service, TailorService, MeasurementField,
    Order, Logistic, Address, OrderNote, OrderItem
)
from ..notifications.routes import create_notification
from app.forms import TailorProfileForm, TailorServiceForm, AddressForm, SimpleSubmitForm, MeasurementSelectionForm

# Custom decorator to restrict access to tailors only
def tailor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'tailor':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dashboard Routes
@tailor_bp.route('/dashboard')
@login_required
@tailor_required
def dashboard():
    """Display tailor's dashboard with an overview of their orders and services."""
    # Fetch new orders awaiting acceptance
    new_orders = Order.query.filter_by(
        tailor_id=current_user.id,
        order_status='pending_tailor_acceptance'
    ).all()

    # Fetch active orders in progress
    active_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status.in_(['awaiting_pickup', 'fabric_in_transit', 'in_progress'])
    ).order_by(Order.created_at).all()

    # Fetch recent completed orders (limited to 10)
    completed_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status.in_(['ready_for_delivery', 'out_for_delivery', 'completed'])
    ).order_by(Order.created_at.desc()).limit(10).all()

    # Fetch tailor's offered services
    my_services = TailorService.query.filter_by(tailor_id=current_user.id).all()
    form = SimpleSubmitForm()
    # Collect order IDs for efficient task querying
    all_order_ids = [o.id for o in new_orders + active_orders + completed_orders]
    tasks_map = {
        task.order_id: task for task in Logistic.query.filter(
            Logistic.order_id.in_(all_order_ids)
        ).all()
    }

    return render_template(
        'tailor/dashboard.html',
        my_services=my_services,
        new_orders=new_orders,
        active_orders=active_orders,
        completed_orders=completed_orders,
        tasks_map=tasks_map,
        current_year=datetime.now().year,
        form = form
    )

@tailor_bp.route('/earnings')
@login_required
@tailor_required
def earnings():
    """Display the tailor's completed orders and total earnings."""
    # Fetch all completed orders for the tailor
    completed_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status == 'completed'
    ).all()

    # Calculate total earnings from completed orders (via OrderItems and TailorServices)
    total_earnings = db.session.query(func.sum(TailorService.tailor_earning)).join(OrderItem).join(Order).filter(
        Order.tailor_id == current_user.id,
        Order.order_status == 'completed'
    ).scalar() or 0.0

    return render_template(
        'tailor/earnings.html',
        orders=completed_orders,
        total_earnings=total_earnings,
        current_year=datetime.now().year
    )

# Service Management Routes
@tailor_bp.route('/services')
@login_required
@tailor_required
def my_services():
    """Display all services offered by the tailor."""
    services = TailorService.query.filter_by(tailor_id=current_user.id).order_by(TailorService.id.desc()).all()
    return render_template('tailor/my_services.html', my_services=services, current_year=datetime.now().year)

@tailor_bp.route('/services/add', methods=['GET', 'POST'])
@login_required
@tailor_required
def add_service():
    """Allow tailor to add a new service from the master service list."""
    form = TailorServiceForm()
    form.service_id.choices = [(s.id, s.name) for s in Service.query.all()]
    form.measurement_field_ids.choices = [(m.id, m.name) for m in MeasurementField.query.all()]

    if form.validate_on_submit():
        # Check for duplicate service
        if TailorService.query.filter_by(tailor_id=current_user.id, service_id=form.service_id.data).first():
            flash('You already offer this service.', 'warning')
            return redirect(url_for('tailor.my_services'))

        # Calculate tailor's earning after commission (hardcoded at 15%; consider config)
        commission_rate = 0.15
        earning = form.price.data * (1 - commission_rate)

        # Create new TailorService
        new_tailor_service = TailorService(
            tailor_id=current_user.id,
            service_id=form.service_id.data,
            price=form.price.data,
            estimated_days=form.estimated_days.data,
            tailor_earning=earning
        )
        db.session.add(new_tailor_service)
        db.session.commit()

        # Associate custom measurements
        for measurement_id in form.measurement_field_ids.data:
            measurement = MeasurementField.query.get(measurement_id)
            if measurement:
                new_tailor_service.custom_measurements.append(measurement)
        db.session.commit()

        flash('Service added successfully!', 'success')
        return redirect(url_for('tailor.my_services'))
    
    return render_template('tailor/add_service.html', form=form, current_year=datetime.now().year)

@tailor_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@tailor_required
def edit_service(service_id):
    """Allow tailor to edit an existing service's price and estimated days."""
    tailor_service = TailorService.query.get_or_404(service_id)
    if tailor_service.tailor_id != current_user.id:
        flash("You do not have permission to edit this service.", "danger")
        return redirect(url_for('tailor.my_services'))

    form = TailorServiceForm(obj=tailor_service)
    form.service_id.choices = [(s.id, s.name) for s in Service.query.all()]
    form.measurement_field_ids.choices = [(m.id, m.name) for m in MeasurementField.query.all()]
    form.measurement_field_ids.data = [m.id for m in tailor_service.custom_measurements]

    if form.validate_on_submit():
        # Update price and estimated days
        commission_rate = 0.15
        tailor_service.price = form.price.data
        tailor_service.estimated_days = form.estimated_days.data
        tailor_service.tailor_earning = form.price.data * (1 - commission_rate)

        # Update custom measurements
        tailor_service.custom_measurements = [
            MeasurementField.query.get(m_id) for m_id in form.measurement_field_ids.data if MeasurementField.query.get(m_id)
        ]
        db.session.commit()
        flash('Service details have been updated!', 'success')
        return redirect(url_for('tailor.my_services'))
    
    return render_template('tailor/edit_service.html', form=form, tailor_service=tailor_service, current_year=datetime.now().year)

@tailor_bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@tailor_required
def delete_service(service_id):
    """Allow tailor to delete a service they offer."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        tailor_service = TailorService.query.get_or_404(service_id)
        if tailor_service.tailor_id != current_user.id:
            flash("You do not have permission to delete this service.", "danger")
            return redirect(url_for('tailor.my_services'))
        db.session.delete(tailor_service)
        db.session.commit()
        flash('Service removed from your profile.', 'success')
        return redirect(url_for('tailor.my_services'))
    flash('Invalid form submission.', 'danger')
    return redirect(url_or('tailor.my_services'))

@tailor_bp.route('/services/<int:service_id>/measurements', methods=['GET', 'POST'])
@login_required
@tailor_required
def manage_measurements(service_id):
    """Allow tailor to customize measurement requirements for a service."""
    tailor_service = TailorService.query.get_or_404(service_id)
    if tailor_service.tailor_id != current_user.id:
        flash('You do not have permission to edit this service.', 'danger')
        return redirect(url_for('tailor.my_services'))

    form = MeasurementSelectionForm()
    form.measurement_ids.choices = [(m.id, m.name) for m in MeasurementField.query.all()]
    form.measurement_ids.data = [m.id for m in tailor_service.custom_measurements]

    if form.validate_on_submit():
        tailor_service.custom_measurements = [
            MeasurementField.query.get(m_id) for m_id in form.measurement_ids.data if MeasurementField.query.get(m_id)
        ]
        db.session.commit()
        flash(f'Measurement requirements for "{tailor_service.service.name}" have been updated!', 'success')
        return redirect(url_for('tailor.my_services'))

    all_measurements = MeasurementField.query.all()
    custom_measurement_ids = {m.id for m in tailor_service.custom_measurements}
    ids_to_check = custom_measurement_ids or {m.id for m in tailor_service.service.standard_measurements}
    return render_template(
        'tailor/manage_measurements.html',
        form=form,
        tailor_service=tailor_service,
        all_measurements=all_measurements,
        ids_to_check=ids_to_check,
        current_year=datetime.now().year
    )

# Order Management Routes
@tailor_bp.route('/orders')
@login_required
@tailor_required
def orders():
    """Display a filterable list of all orders assigned to the tailor."""
    form = SimpleSubmitForm()
    all_orders = Order.query.filter_by(tailor_id=current_user.id).order_by(Order.created_at.desc()).all()
    new_orders = [o for o in all_orders if o.order_status == 'pending_tailor_acceptance']
    active_orders = [o for o in all_orders if o.order_status in ['awaiting_pickup', 'fabric_in_transit', 'in_progress']]
    completed_orders = [o for o in all_orders if o.order_status in ['ready_for_delivery', 'out_for_delivery', 'completed']]
    return render_template(
        'tailor/orders.html',
        new_orders=new_orders,
        active_orders=active_orders,
        completed_orders=completed_orders,
        current_year=datetime.now().year,
        form = form
    )

@tailor_bp.route('/order/<int:order_id>/details', methods=['GET', 'POST'])
@login_required
@tailor_required
def order_details(order_id):
    """Display detailed job ticket for a specific order and handle note creation."""
    order = Order.query.get_or_404(order_id)
    if order.tailor_id != current_user.id:
        flash("You do not have permission to view this order.", "danger")
        return redirect(url_for('tailor.orders'))

    form = SimpleSubmitForm()
    note = request.form.get('note')  # Note: Consider integrating into a dedicated form for better validation
    if form.validate_on_submit() and note:
        new_note = OrderNote(order_id=order.id, user_id=current_user.id, note=note)
        db.session.add(new_note)
        db.session.commit()
        flash("Note added successfully.", "success")
        return redirect(url_for('tailor.order_details', order_id=order.id))

    return render_template('tailor/order_details.html', order=order, form=form, current_year=datetime.now().year)

@tailor_bp.route('/order/<int:order_id>/accept', methods=['POST'])
@login_required
@tailor_required
def accept_order(order_id):
    """Accept an order and create a pickup task for delivery partners."""
    # import pdb ; pdb.set_trace()
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        order = Order.query.get_or_404(order_id)
        if order.tailor_id != current_user.id:
            flash("You do not have permission to accept this order.", "danger")
            return redirect(url_for('tailor.orders'))

        # Update order status and create pickup logistic task
        order.order_status = 'awaiting_pickup'
        pickup_otp = str(random.randint(100000, 999999))
        tailor_otp = str(random.randint(100000, 999999))
        new_task = Logistic(
            order_id=order.id,
            delivery_partner_id=None,
            task_type='pickup_from_customer',
            status='assigned',
            pickup_otp=pickup_otp,
            tailor_handover_otp=tailor_otp,
        )
        db.session.add(new_task)
        db.session.commit()

        # Notify customer and broadcast to delivery partners
        create_notification(
            user_id=order.customer_id,
            message=f"Your Order #{order.id} has been accepted by the tailor.",
            link=url_for('customer.order_details', order_id=order.id)
        )
        create_notification(
            user_id=None,  # Broadcast to all delivery partners
            message=f"New pickup task available for Order #{order.id}",
            link=url_for('delivery.task_details', task_id=new_task.id)
        )
        flash(f"Order #{order.id} accepted. A task is now available for delivery partners.", "success")
        return redirect(url_for('tailor.orders'))
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('tailor.orders'))

@tailor_bp.route('/order/<int:order_id>/complete', methods=['POST'])
@login_required
@tailor_required
def complete_order(order_id):
    """Mark an order as complete and create a delivery task."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        order = Order.query.get_or_404(order_id)
        if order.tailor_id != current_user.id:
            flash("You do not have permission to complete this order.", "danger")
            return redirect(url_for('tailor.orders'))

        # Update order status and create pickup-from-tailor logistic task
        order.order_status = 'ready_for_delivery'
        tailor_pickup_otp = str(random.randint(100000, 999999))
        new_task = Logistic(
            order_id=order.id,
            delivery_partner_id=None,
            task_type='pickup_from_tailor',
            status='assigned',
            pickup_otp=tailor_pickup_otp
        )
        db.session.add(new_task)
        db.session.commit()

        # Emit real-time notification for new task (via SocketIO)
        socketio.emit('new_task', {
            'message': f'New pickup task from tailor available for Order #{order.id}'
        })
        flash(f"Order #{order.id} finished. A delivery task is now available.", "success")
        return redirect(url_for('tailor.orders'))
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('tailor.orders'))

@tailor_bp.route('/task/<int:task_id>/confirm_receipt', methods=['POST'])
@login_required
@tailor_required
def confirm_fabric_receipt(task_id):
    """Confirm receipt of fabric for an order and update its status."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        task = Logistic.query.get_or_404(task_id)
        if task.order.tailor_id != current_user.id:
            flash("You do not have permission to do this.", "danger")
            return redirect(url_for('tailor.orders'))

        # Complete the task and advance order status
        task.status = 'completed'
        task.order.order_status = 'in_progress'
        db.session.commit()
        flash("Fabric receipt confirmed. The order is now in progress.", "success")
        return redirect(url_for('tailor.orders'))
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('tailor.orders'))

# Profile Management Route
@tailor_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@tailor_required
def profile():
    """Allow tailor to view and update their profile information."""
    user_profile = current_user.profile
    tailor_profile = current_user.tailor_profile
    address = current_user.addresses.first()

    profile_form = TailorProfileForm(
        obj=tailor_profile,
        email=current_user.email,
        first_name=user_profile.first_name,
        last_name=user_profile.last_name
    )
    address_form = AddressForm(obj=address)

    if profile_form.validate_on_submit() and address_form.validate_on_submit():
        # Update user profile
        user_profile.first_name = profile_form.first_name.data
        user_profile.last_name = profile_form.last_name.data
        current_user.email = profile_form.email.data

        # Update tailor profile
        tailor_profile.business_name = profile_form.business_name.data
        tailor_profile.bio = profile_form.bio.data
        tailor_profile.years_of_experience = profile_form.years_of_experience.data
        tailor_profile.specializations = profile_form.specializations.data

        # Handle address (create if none exists)
        if not address:
            address = Address(user_id=current_user.id, is_default=True)
            db.session.add(address)
        
        address.address_line1 = address_form.address_line1.data
        address.city = address_form.city.data
        address.state = address_form.state.data
        address.postal_code = address_form.postal_code.data
        address.is_default = address_form.is_default.data

        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('tailor.profile'))

    # Flash form errors
    if profile_form.errors or address_form.errors:
        for form in [profile_form, address_form]:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"Error in {field}: {error}", "danger")

    return render_template(
        'tailor/profile.html',
        profile_form=profile_form,
        address_form=address_form,
        user_profile=user_profile,
        tailor_profile=tailor_profile,
        address=address,
        current_year=datetime.now().year
    )


@tailor_bp.route('/order/<int:order_id>/add_note', methods=['POST'])
@login_required
def add_note(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Optional: Check if the current_user is allowed to comment on this order
    # (e.g., is the assigned tailor)
    
    note_text = request.form.get('note')
    if note_text:
        new_note = Note(
            note=note_text,
            order_id=order.id,
            author_id=current_user.id
        )
        db.session.add(new_note)
        db.session.commit()
        flash('Your note has been added.', 'success')
    else:
        flash('Note cannot be empty.', 'danger')
        
    # Redirect back to the same order detail page to see the new note
    return redirect(url_for('tailor.order_detail', order_id=order.id))