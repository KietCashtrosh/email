from flask import flash, redirect, url_for, render_template, request
import random
from app import db  # Import the db object
from flask_login import current_user, login_required
from functools import wraps
from sqlalchemy import func
from . import tailor_bp  # Removed to avoid redefinition error
from ..models import (User, TailorProfile, Service, TailorService,
                      MeasurementField, standard_service_measurements, Order, Logistic,
                      DeliveryPartnerProfile, OrderItem)

def tailor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is logged in and if their role is 'tailor'
        if not current_user.is_authenticated or current_user.role != 'tailor':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@tailor_bp.route('/earnings')
@login_required
@tailor_required
def earnings():
    # Fetch all completed orders for this tailor
    completed_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status == 'completed' # Or other "finished" statuses
    ).all()
    
    # Calculate total earnings
    total_earnings = db.session.query(func.sum(TailorService.tailor_earning)).join(OrderItem).join(Order).filter(
        Order.tailor_id == current_user.id,
        Order.order_status == 'completed'
    ).scalar() or 0.0

    return render_template('tailor/earnings.html', 
                           orders=completed_orders, 
                           total_earnings=total_earnings)


# app/tailor/routes.py

@tailor_bp.route('/dashboard')
@login_required
@tailor_required
def dashboard():
    """Shows a full overview of all orders assigned to the tailor."""
    
    # 1. New orders waiting for the tailor's acceptance
    new_orders = Order.query.filter_by(
        tailor_id=current_user.id,
        order_status='pending_tailor_acceptance'
    ).all()
    
    # 2. Active orders that have been accepted but are not yet finished stitching
    active_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status.in_(['awaiting_pickup', 'fabric_in_transit', 'in_progress'])
    ).order_by(Order.created_at).all()

    # 3. Orders the tailor has finished stitching
    completed_orders = Order.query.filter(
        Order.tailor_id == current_user.id,
        Order.order_status.in_(['ready_for_delivery', 'out_for_delivery', 'completed'])
    ).order_by(Order.created_at.desc()).limit(10).all() # Show the last 10
    
    my_services = TailorService.query.filter_by(tailor_id=current_user.id).all()

    # 1. Collect the IDs from ALL order categories
    all_order_ids = [o.id for o in new_orders] + [o.id for o in active_orders] + [o.id for o in completed_orders]

    # 2. Build the tasks_map based on all the orders being displayed
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

# @tailor_bp.route('/dashboard')
# @login_required
# @tailor_required
# def dashboard():
#     """Main dashboard for the tailor to see their services, orders, etc."""
#     # --- MOVED THE QUERIES INSIDE THE FUNCTION ---
#     new_orders = Order.query.filter_by(
#         tailor_id=current_user.id, 
#         order_status='pending_tailor_acceptance'
#     ).all()
    
#     in_progress_orders = Order.query.filter_by(
#         tailor_id=current_user.id, 
#         order_status='in_progress'
#     ).all()

#     awaiting_fabric_orders = Order.query.filter_by(
#     tailor_id=current_user.id,
#     order_status='fabric_in_transit'
# ).all()
    
#     # --- NEW: Create a dictionary to easily find the relevant task ---
#     tasks_map = {}
#     for order in awaiting_fabric_orders:
#         task = Logistic.query.filter_by(
#             order_id=order.id,
#             status='in_transit_to_tailor'
#         ).first()
#         if task:
#             tasks_map[order.id] = task
    
#     my_services = TailorService.query.filter_by(tailor_id=current_user.id).all()

#     # --- PASS THE ORDER LISTS TO THE TEMPLATE ---
#     return render_template(
#         'tailor/dashboard.html', 
#         my_services=my_services,
#         new_orders=new_orders,
#         in_progress_orders=in_progress_orders,
#         awaiting_fabric_orders=awaiting_fabric_orders,
#         tasks_map=tasks_map  # Pass the task map to the template
#     )

@tailor_bp.route('/services/add', methods=['GET', 'POST'])
@login_required
@tailor_required
def add_service():
    """Allow a tailor to add a new service they offer from the master list."""
    # Get all master services to display in a dropdown
    master_services = Service.query.all()
    
    if request.method == 'POST':
        service_id = request.form.get('service_id')
        price = request.form.get('price')

        # Check if the tailor already offers this service
        existing_offer = TailorService.query.filter_by(
            tailor_id=current_user.id, 
            service_id=service_id
        ).first()

        if existing_offer:
            flash('You already offer this service.', 'warning')
            return redirect(url_for('tailor.dashboard'))

        if not all([service_id, price]):
            flash('Please select a service and set a price.', 'danger')
            return redirect(url_for('tailor.add_service'))

        new_tailor_service = TailorService(
            tailor_id=current_user.id,
            service_id=service_id,
            price=float(price)
        )
        db.session.add(new_tailor_service)
        db.session.commit()

        flash('Service added successfully! Now, specify the measurements required.', 'success')
        # Redirect to the measurement management page for the newly created service
        return redirect(url_for('tailor.manage_measurements', service_id=new_tailor_service.id))
    
    return render_template('tailor/add_service.html', master_services=master_services)


@tailor_bp.route('/services/<int:service_id>/measurements', methods=['GET', 'POST'])
@login_required
@tailor_required
def manage_measurements(service_id):
    """Allow a tailor to select the measurements they need for a specific service."""
    tailor_service = TailorService.query.get_or_404(service_id)

    # Security check: ensure this service belongs to the current tailor
    if tailor_service.tailor_id != current_user.id:
        flash('You do not have permission to edit this service.', 'danger')
        return redirect(url_for('tailor.dashboard'))

    if request.method == 'POST':
        selected_ids = request.form.getlist('measurement_ids')
        
        # Clear existing custom measurements and add the new selection
        tailor_service.custom_measurements = []
        for m_id in selected_ids:
            field = MeasurementField.query.get(m_id)
            if field:
                tailor_service.custom_measurements.append(field)

        db.session.commit()
        flash(f'Measurement requirements for "{tailor_service.service.name}" have been updated!', 'success')
        return redirect(url_for('tailor.dashboard'))

    # --- Logic for GET request ---
    all_measurements = MeasurementField.query.all()

    # Get the IDs of the tailor's currently saved custom measurements
    custom_measurement_ids = {m.id for m in tailor_service.custom_measurements}
    
    # If the tailor hasn't customized yet, use the standard measurements as the default
    if not custom_measurement_ids:
        standard_measurement_ids = {m.id for m in tailor_service.service.standard_measurements}
        ids_to_check = standard_measurement_ids
    else:
        ids_to_check = custom_measurement_ids

    return render_template('tailor/manage_measurements.html',
                           tailor_service=tailor_service,
                           all_measurements=all_measurements,
                           ids_to_check=ids_to_check)

@tailor_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@tailor_required
def edit_service(service_id):
    tailor_service = TailorService.query.get_or_404(service_id)
    # Security check...

    if request.method == 'POST':
        tailor_service.price = float(request.form.get('price'))
        tailor_service.estimated_days = int(request.form.get('estimated_days'))
        db.session.commit()
        flash('Service updated successfully!', 'success')
        return redirect(url_for('tailor.dashboard'))
    
    return render_template('tailor/edit_service.html', tailor_service=tailor_service)

@tailor_bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@tailor_required
def delete_service(service_id):
    tailor_service = TailorService.query.get_or_404(service_id)
    # Security check...
    
    db.session.delete(tailor_service)
    db.session.commit()
    flash('Service removed from your profile.', 'success')
    return redirect(url_for('tailor.dashboard'))

# @tailor_bp.route('/order/<int:order_id>/accept', methods=['POST'])
# @login_required
# @tailor_required
# def accept_order(order_id):
#     order = Order.query.get_or_404(order_id)
#     # Security check...
    
#     order.order_status = 'pickup_is_pending'
#     # This is the trigger point to notify logistics!
#     # We would add logic here to create a 'Logistic' task for fabric pickup.
#     db.session.commit()
#     flash(f"Order #{order.id} has been accepted.", "success")
#     return redirect(url_for('tailor.dashboard'))

# @tailor_bp.route('/order/<int:order_id>/complete', methods=['POST'])
# @login_required
# @tailor_required
# def complete_order(order_id):
#     order = Order.query.get_or_404(order_id)
#     # Security check...
    
#     order.order_status = 'ready_for_delivery'
#     # This is the trigger to notify logistics for final delivery!
#     db.session.commit()
#     flash(f"Order #{order.id} marked as complete.", "success")
#     return redirect(url_for('tailor.dashboard'))


# app/tailor/routes.py
import random
from ..models import Logistic # Make sure Logistic is imported

@tailor_bp.route('/order/<int:order_id>/accept', methods=['POST'])
@login_required
@tailor_required
def accept_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.order_status = 'awaiting_pickup'
    
    # --- CORRECTED LOGIC ---
    # Create the task without assigning a partner.
    # It now enters the pool of available tasks.
    pickup_otp = str(random.randint(100000, 999999))
    tailor_otp = str(random.randint(100000, 999999))
    new_task = Logistic(
        order_id=order.id,
        delivery_partner_id=None, # Set to None to make it available
        task_type='pickup_from_customer',
        status='assigned', # 'assigned' now means "ready to be taken"
        pickup_otp=pickup_otp,
        tailor_handover_otp=tailor_otp
    )
    db.session.add(new_task)
    db.session.commit()
    
    flash(f"Order #{order.id} accepted. A task is now available for delivery partners.", "success")
    return redirect(url_for('tailor.dashboard'))

@tailor_bp.route('/order/<int:order_id>/complete', methods=['POST'])
@login_required
@tailor_required
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    order.order_status = 'ready_for_delivery'

    # --- CORRECTED LOGIC ---
    # Create the delivery task and make it available in the pool
    tailor_pickup_otp = str(random.randint(100000, 999999))
    
    new_task = Logistic(
        order_id=order.id,
        delivery_partner_id=None, # It's available for any partner to accept
        task_type='pickup_from_tailor', # The specific task
        status='assigned',
        pickup_otp=tailor_pickup_otp # Using the pickup_otp field for this handover
    )
    db.session.add(new_task)
    db.session.commit()
    
    flash(f"Order #{order.id} finished. A delivery task is now available.", "success")
    return redirect(url_for('tailor.dashboard'))

# app/tailor/routes.py

@tailor_bp.route('/task/<int:task_id>/confirm_receipt', methods=['POST'])
@login_required
@tailor_required
def confirm_fabric_receipt(task_id):
    task = Logistic.query.get_or_404(task_id)
    # Security check to ensure this task's order belongs to the tailor
    if task.order.tailor_id != current_user.id:
        flash("You do not have permission to do this.", "danger")
        return redirect(url_for('tailor.dashboard'))
    
    # Mark the logistic task as complete
    task.status = 'completed'
    # Update the main order status to 'in_progress'
    task.order.order_status = 'in_progress'
    db.session.commit()
    
    flash("Fabric receipt confirmed. The order is now in progress.", "success")
    return redirect(url_for('tailor.dashboard'))