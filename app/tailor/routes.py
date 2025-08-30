from flask import flash, redirect, url_for, render_template, request
from flask_login import current_user, login_required
from functools import wraps
from sqlalchemy import func
import random
from app import db, socketio
from . import tailor_bp
from ..models import (
    User, TailorProfile, Service, TailorService, MeasurementField,
    Order, Logistic, Address, OrderNote
)
from ..notifications.routes import create_notification

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
    # Fetch new orders awaiting tailor's acceptance
    new_orders = Order.query.filter_by(
        tailor_id=current_user.id,
        order_status='pending_tailor_acceptance'
    ).all()
    
    # Fetch active orders (accepted but not yet completed)
    active_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status.in_(['awaiting_pickup', 'fabric_in_transit', 'in_progress'])
    ).order_by(Order.created_at).all()

    # Fetch recently completed orders (last 10)
    completed_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status.in_(['ready_for_delivery', 'out_for_delivery', 'completed'])
    ).order_by(Order.created_at.desc()).limit(10).all()
    
    # Fetch tailor's services
    my_services = TailorService.query.filter_by(tailor_id=current_user.id).all()

    # Build tasks map for all displayed orders
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
        tasks_map=tasks_map
    )

@tailor_bp.route('/earnings')
@login_required
@tailor_required
def earnings():
    """Display the tailor's completed orders and total earnings."""
    # Fetch completed orders for the tailor
    completed_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status == 'completed'
    ).all()
    
    # Calculate total earnings from completed orders
    total_earnings = db.session.query(func.sum(TailorService.tailor_earning)).join(OrderItem).join(Order).filter(
        Order.tailor_id == current_user.id,
        Order.order_status == 'completed'
    ).scalar() or 0.0

    return render_template(
        'tailor/earnings.html',
        orders=completed_orders,
        total_earnings=total_earnings
    )

# Service Management Routes
@tailor_bp.route('/services')
@login_required
@tailor_required
def my_services():
    """Display all services offered by the tailor."""
    services = TailorService.query.filter_by(tailor_id=current_user.id).order_by(TailorService.id.desc()).all()
    return render_template('tailor/my_services.html', my_services=services)

@tailor_bp.route('/services/add', methods=['GET', 'POST'])
@login_required
@tailor_required
def add_service():
    """Allow tailor to add a new service from the master service list."""
    master_services = Service.query.all()
    
    if request.method == 'POST':
        price = float(request.form.get('price'))
        estimated_days = int(request.form.get('estimated_days'))
        service_id = request.form.get('service_id')

        # Check if service is already offered by the tailor
        if TailorService.query.filter_by(tailor_id=current_user.id, service_id=service_id).first():
            flash('You already offer this service.', 'warning')
            return redirect(url_for('tailor.dashboard'))

        # Validate input
        if not all([service_id, price]):
            flash('Please select a service and set a price.', 'danger')
            return redirect(url_for('tailor.add_service'))

        # Calculate tailor's earning (85% of price)
        commission_rate = 0.15
        earning = price * (1 - commission_rate)

        # Create and save new service
        new_tailor_service = TailorService(
            tailor_id=current_user.id,
            service_id=service_id,
            price=price,
            estimated_days=estimated_days,
            tailor_earning=earning
        )
        db.session.add(new_tailor_service)
        db.session.commit()

        flash('Service added successfully! Now, specify the measurements required.', 'success')
        return redirect(url_for('tailor.manage_measurements', service_id=new_tailor_service.id))
    
    return render_template('tailor/add_service.html', master_services=master_services)

@tailor_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@tailor_required
def edit_service(service_id):
    """Allow tailor to edit an existing service's price and estimated days."""
    tailor_service = TailorService.query.get_or_404(service_id)
    
    # Ensure tailor owns this service
    if tailor_service.tailor_id != current_user.id:
        flash("You do not have permission to edit this service.", "danger")
        return redirect(url_for('tailor.dashboard'))

    if request.method == 'POST':
        price = float(request.form.get('price'))
        tailor_service.price = price
        tailor_service.estimated_days = int(request.form.get('estimated_days'))
        # Recalculate tailor's earning
        commission_rate = 0.15
        tailor_service.tailor_earning = price * (1 - commission_rate)
        db.session.commit()
        flash('Service details have been updated!', 'success')
        return redirect(url_for('tailor.dashboard'))
    
    return render_template('tailor/edit_service.html', tailor_service=tailor_service)

@tailor_bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@tailor_required
def delete_service(service_id):
    """Allow tailor to delete a service they offer."""
    tailor_service = TailorService.query.get_or_404(service_id)
    
    # Ensure tailor owns this service
    if tailor_service.tailor_id != current_user.id:
        flash("You do not have permission to delete this service.", "danger")
        return redirect(url_for('tailor.dashboard'))
    
    db.session.delete(tailor_service)
    db.session.commit()
    flash('Service removed from your profile.', 'success')
    return redirect(url_for('tailor.dashboard'))

@tailor_bp.route('/services/<int:service_id>/measurements', methods=['GET', 'POST'])
@login_required
@tailor_required
def manage_measurements(service_id):
    """Allow tailor to customize measurement requirements for a service."""
    tailor_service = TailorService.query.get_or_404(service_id)
    
    # Ensure tailor owns this service
    if tailor_service.tailor_id != current_user.id:
        flash('You do not have permission to edit this service.', 'danger')
        return redirect(url_for('tailor.dashboard'))

    if request.method == 'POST':
        selected_ids = request.form.getlist('measurement_ids')
        # Update custom measurements
        tailor_service.custom_measurements = [
            MeasurementField.query.get(m_id) for m_id in selected_ids if MeasurementField.query.get(m_id)
        ]
        db.session.commit()
        flash(f'Measurement requirements for "{tailor_service.service.name}" have been updated!', 'success')
        return redirect(url_for('tailor.dashboard'))

    # Fetch all available measurements and current selections
    all_measurements = MeasurementField.query.all()
    custom_measurement_ids = {m.id for m in tailor_service.custom_measurements}
    ids_to_check = custom_measurement_ids or {m.id for m in tailor_service.service.standard_measurements}

    return render_template(
        'tailor/manage_measurements.html',
        tailor_service=tailor_service,
        all_measurements=all_measurements,
        ids_to_check=ids_to_check
    )

# Order Management Routes
@tailor_bp.route('/orders')
@login_required
@tailor_required
def orders():
    """Display a filterable list of all orders assigned to the tailor."""
    # Fetch all orders for the tailor
    all_orders = Order.query.filter_by(tailor_id=current_user.id).order_by(Order.created_at.desc()).all()
    
    # Categorize orders
    new_orders = [o for o in all_orders if o.order_status == 'pending_tailor_acceptance']
    active_orders = [o for o in all_orders if o.order_status in ['awaiting_pickup', 'fabric_in_transit', 'in_progress']]
    completed_orders = [o for o in all_orders if o.order_status in ['ready_for_delivery', 'out_for_delivery', 'completed']]

    return render_template(
        'tailor/orders.html',
        new_orders=new_orders,
        active_orders=active_orders,
        completed_orders=completed_orders
    )

@tailor_bp.route('/order/<int:order_id>/details', methods=['GET', 'POST'])
@login_required
@tailor_required
def order_details(order_id):
    """Display detailed job ticket for a specific order and handle note creation."""
    order = Order.query.get_or_404(order_id)
    
    # Ensure order belongs to the tailor
    if order.tailor_id != current_user.id:
        flash("You do not have permission to view this order.", "danger")
        return redirect(url_for('tailor.orders'))
    
    if request.method == 'POST':
        note_text = request.form.get('note')
        if note_text:
            new_note = OrderNote(order_id=order.id, user_id=current_user.id, note=note_text)
            db.session.add(new_note)
            db.session.commit()
            flash("Note added successfully.", "success")
            return redirect(url_for('tailor.order_details', order_id=order.id))

    return render_template('tailor/order_details.html', order=order)

@tailor_bp.route('/order/<int:order_id>/accept', methods=['POST'])
@login_required
@tailor_required
def accept_order(order_id):
    """Accept an order and create a pickup task for delivery partners."""
    order = Order.query.get_or_404(order_id)
    
    # Ensure order belongs to the tailor
    if order.tailor_id != current_user.id:
        flash("You do not have permission to accept this order.", "danger")
        return redirect(url_for('tailor.dashboard'))
    
    order.order_status = 'awaiting_pickup'
    
    # Create a pickup task for delivery partners
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

    # Notify delivery partners of new task
    # socketio.emit('new_task', {
    #     'task_id': new_task.id,
    #     'message': f'New pickup task available for Order #{order.id}'
    # })

    create_notification(
        user_id=order.customer_id,
        message=f"Your Order #{order.id} has been accepted by the tailor.",
        link=url_for('customer.order_details', order_id=order.id)
    )
    create_notification(
        user_id=None,  # Broadcast to delivery partners
        message=f"New pickup task available for Order #{order.id}",
        link=url_for('delivery.task_details', task_id=new_task.id)
    )
    
    flash(f"Order #{order.id} accepted. A task is now available for delivery partners.", "success")
    return redirect(url_for('tailor.dashboard'))

@tailor_bp.route('/order/<int:order_id>/complete', methods=['POST'])
@login_required
@tailor_required
def complete_order(order_id):
    """Mark an order as complete and create a delivery task."""
    order = Order.query.get_or_404(order_id)
    
    # Ensure order belongs to the tailor
    if order.tailor_id != current_user.id:
        flash("You do not have permission to complete this order.", "danger")
        return redirect(url_for('tailor.dashboard'))
    
    order.order_status = 'ready_for_delivery'
    
    # Create a delivery task for pickup from tailor
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

    # Notify delivery partners of new task
    socketio.emit('new_task', {
        'message': f'New pickup task from tailor available for Order #{order.id}'
    })
    
    flash(f"Order #{order.id} finished. A delivery task is now available.", "success")
    return redirect(url_for('tailor.dashboard'))

@tailor_bp.route('/task/<int:task_id>/confirm_receipt', methods=['POST'])
@login_required
@tailor_required
def confirm_fabric_receipt(task_id):
    """Confirm receipt of fabric for an order and update its status."""
    task = Logistic.query.get_or_404(task_id)
    
    # Ensure task's order belongs to the tailor
    if task.order.tailor_id != current_user.id:
        flash("You do not have permission to do this.", "danger")
        return redirect(url_for('tailor.dashboard'))
    
    # Mark task as complete and update order status
    task.status = 'completed'
    task.order.order_status = 'in_progress'
    db.session.commit()
    
    flash("Fabric receipt confirmed. The order is now in progress.", "success")
    return redirect(url_for('tailor.dashboard'))

# Profile Management Route
@tailor_bp.route('/profile', methods=['GET', 'POST'])
@login_required
@tailor_required
def profile():
    """Allow tailor to view and update their profile information."""
    user_profile = current_user.profile
    tailor_profile = current_user.tailor_profile
    address = current_user.addresses.first()

    if request.method == 'POST':
        # Update user profile
        user_profile.first_name = request.form.get('first_name')
        user_profile.last_name = request.form.get('last_name')
        current_user.email = request.form.get('email')

        # Update tailor profile
        tailor_profile.business_name = request.form.get('business_name')
        tailor_profile.bio = request.form.get('bio')
        tailor_profile.years_of_experience = request.form.get('years_of_experience')
        tailor_profile.specializations = request.form.get('specializations')

        # Update or create address
        if not address:
            address = Address(user_id=current_user.id, is_default=True)
            db.session.add(address)
        
        address.address_line1 = request.form.get('address_line1')
        address.city = request.form.get('city')
        address.state = request.form.get('state')
        address.postal_code = request.form.get('postal_code')
        
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('tailor.profile'))

    return render_template(
        'tailor/profile.html',
        user_profile=user_profile,
        tailor_profile=tailor_profile,
        address=address
    )