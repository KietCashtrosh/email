from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from . import delivery_bp
from .. import db
from ..models import Logistic, Order, OrderMeasurementValue
from sqlalchemy.sql import func
from functools import wraps
import random

# --- Decorator to ensure only delivery partners can access these routes ---
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
    """Shows tasks in three categories: available, active, and completed."""
    
    # Check if the partner already has an active task
    # Fetch active tasks
    active_task = Logistic.query.filter(
        Logistic.delivery_partner_id == current_user.id,
        Logistic.status.in_(['assigned', 'in_transit_to_tailor'])
        ).first()

    # If they don't have an active task, show them the pool of available tasks
    available_tasks = []
    if not active_task:
        available_tasks = Logistic.query.filter_by(
            delivery_partner_id=None,
            status='assigned'
        ).all()
        
    # Fetch completed tasks for the earnings tab
    completed_tasks = Logistic.query.filter_by(
        delivery_partner_id=current_user.id,
        status='completed'
    ).all()
    
    # Calculate earnings (₹50 per completed task)
    earnings = db.session.query(func.sum(Logistic.delivery_fee)).filter(
        Logistic.delivery_partner_id == current_user.id,
        Logistic.status == 'completed'
    ).scalar() or 0.0

    return render_template('delivery/dashboard.html', 
                           active_task=active_task,
                           available_tasks=available_tasks,
                           completed_tasks=completed_tasks,
                           earnings=earnings,
                           )

@delivery_bp.route('/task/<int:task_id>/accept', methods=['POST'])
@login_required
@delivery_partner_required
def accept_task(task_id):
    """Allows a partner to claim an available task."""
    # Check if partner already has an active task
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
    """Shows full details for an active task."""
    task = Logistic.query.get_or_404(task_id)
    # Security check to ensure task belongs to the current partner
    if task.delivery_partner_id != current_user.id:
        flash("You do not have permission to view this task.", "danger")
        return redirect(url_for('delivery.dashboard'))
    
    # --- THIS IS THE CORRECTED LOGIC ---

    # 1. Initialize variables to None to prevent UnboundLocalError
    required_measurements = []
    contact_person = None
    contact_address = None

    # 2. Use a clean if/elif structure to determine the context
    if task.task_type == 'pickup_from_customer':
        contact_person = task.order.customer
        contact_address = task.order.delivery_address
        if task.order.measurement_method == 'home_visit' and task.status == 'assigned':
            required_measurements = task.order.items[0].tailor_service.custom_measurements
            
    elif task.task_type == 'pickup_from_tailor':
        contact_person = task.order.tailor
        # Check if the tailor has any addresses before accessing the list
        if task.order.tailor.addresses:
            contact_address = task.order.tailor.addresses[0] # Use list index [0]
        else:
            # Handle case where tailor has no address (important for stability)
            flash("Tailor's address is not available.", "warning")

    elif task.task_type == 'drop_to_customer':
        contact_person = task.order.customer
        contact_address = task.order.delivery_address
        
    # --- END OF CORRECTION ---
    
    return render_template('delivery/task_details.html', 
                           task=task,
                           contact_person=contact_person,
                           contact_address=contact_address,
                           required_measurements=required_measurements)

# @delivery_bp.route('/task/<int:task_id>/details')
# @login_required
# @delivery_partner_required
# def task_details(task_id):
#     """Shows full details for an active task."""
#     task = Logistic.query.get_or_404(task_id)
#     # Security check to ensure task belongs to the current partner
#     if task.delivery_partner_id != current_user.id:
#         flash("You do not have permission to view this task.", "danger")
#         return redirect(url_for('delivery.dashboard'))
    
#     # --- ADD THIS LOGIC TO DETERMINE THE CORRECT CONTACT ---
#     required_measurements = []
    
#     if task.task_type == 'pickup_from_customer':
#         contact_person = task.order.customer
#         contact_address = task.order.delivery_address # Customer's address
#         # Fetch measurements only for home visits
#         if task.order.measurement_method == 'home_visit':
#             required_measurements = task.order.items[0].tailor_service.custom_measurements
    
#     elif task.task_type == 'drop_to_customer':
#         contact_person = task.order.customer
#         contact_address = task.order.delivery_address # Customer's address
    
#     elif task.task_type == 'pickup_from_tailor':
#         contact_person = task.order.tailor
#         # Check if the tailor has any addresses before accessing the list
#         if task.order.tailor.addresses:
#             contact_address = task.order.tailor.addresses[0] # Use list index [0]

#     else: # This handles pickup_from_tailor or drop_to_tailor
#         contact_person = task.order.tailor
#         contact_address = task.order.tailor.addresses.first() # Tailor's address
#     # --- END OF NEW LOGIC ---
    
#     return render_template('delivery/task_details.html', 
#                            task=task,
#                            contact_person=contact_person,
#                            contact_address=contact_address,
#                            required_measurements=required_measurements)


# @delivery_bp.route('/task/<int:task_id>/verify', methods=['GET', 'POST'])
# @login_required
# @delivery_partner_required
# def verify_otp(task_id):
#     task = Logistic.query.get_or_404(task_id)
#     # ... (security check)

#     if request.method == 'POST':
#         submitted_otp = request.form.get('otp')
#         correct_otp = task.pickup_otp if task.task_type.startswith('pickup') else task.delivery_otp
        
#         # --- STEP 1: VERIFY THE OTP ---
#         if submitted_otp != correct_otp:
#             flash('Invalid OTP. Please try again.', 'danger')
#             # If the task was a home visit, redirect back to the details page with the form
#             if task.order.measurement_method == 'home_visit':
#                 return redirect(url_for('delivery.task_details', task_id=task.id))
#             # Otherwise, redirect to the simple OTP form
#             return redirect(url_for('delivery.verify_otp', task_id=task.id))

#         # --- STEP 2: IF OTP IS CORRECT, PROCEED WITH ALL ACTIONS ---
#         order = task.order
#         if task.task_type == 'pickup_from_customer':
#             # Instead of completing, transition to the next step
#             task.status = 'in_transit_to_tailor'
#             order.order_status = 'fabric_in_transit'
#             if order.measurement_method == 'home_visit' and task.task_type == 'pickup_from_customer':
#                 order_item = order.items[0]
#                 required_measurements = order_item.tailor_service.custom_measurements
            
#                 for field in required_measurements:
#                     value = request.form.get(f"measurement_{field.id}")
#                     if value:
#                         measurement_value = OrderMeasurementValue(
#                         order_item_id=order_item.id,
#                         measurement_field_id=field.id,
#                         value=float(value)
#                      )
#                     db.session.add(measurement_value)
#             db.session.commit()
#             flash('Pickup confirmed. Please deliver the fabric to the tailor.', 'success')
#             return redirect(url_for('delivery.dashboard'))

#         elif task.task_type == 'drop_to_customer':
#             # This is the final delivery, so we complete the task
#             task.status = 'completed'
#             order.order_status = 'completed'
#             if order.payment_method == 'cash_on_delivery':
#                 order.payment_status = 'fully_paid'
#             db.session.commit()
#             flash(f'Task #{task.id} verified and completed successfully!', 'success')
#             flash('Final delivery confirmed and task completed!', 'success')
#             return redirect(url_for('delivery.dashboard'))
        
            
#     # For GET request, render the simple OTP form (for non-visit tasks)
#     return render_template('delivery/verify_otp.html', task=task)

# app/delivery/routes.py

@delivery_bp.route('/task/<int:task_id>/verify', methods=['GET', 'POST'])
@login_required
@delivery_partner_required
def verify_otp(task_id):
    task = Logistic.query.get_or_404(task_id)
    # Security check: Ensure task belongs to current partner
    if task.delivery_partner_id != current_user.id:
        flash("You are not assigned to this task.", "danger")
        return redirect(url_for('delivery.dashboard'))

    if request.method == 'POST':
        submitted_otp = request.form.get('otp')
        order = task.order
        
        # --- Step 1: Determine the correct OTP for the current task stage ---
        correct_otp = None
        if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
            correct_otp = task.pickup_otp
        elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
            correct_otp = task.tailor_handover_otp
        elif task.task_type == 'pickup_from_tailor':
            correct_otp = task.pickup_otp # Using the same field for tailor pickup
        elif task.task_type == 'drop_to_customer':
            correct_otp = task.delivery_otp

        # --- Step 2: Validate the OTP ---
        if submitted_otp != correct_otp:
            flash('Invalid OTP. Please try again.', 'danger')
            return redirect(url_for('delivery.task_details', task_id=task.id))

        # --- Step 3: If OTP is valid, perform the action based on task type ---
        
        # Action for Pickup from Customer (Home Visit or Regular)
        if task.task_type == 'pickup_from_customer' and task.status == 'assigned':
            task.status = 'in_transit_to_tailor'
            order.order_status = 'fabric_in_transit'
            # Save measurements if it was a home visit
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
            flash('Pickup from customer confirmed. Please proceed to the tailor.', 'success')
            return redirect(url_for('delivery.dashboard'))

        # Action for Handover to Tailor
        elif task.task_type == 'pickup_from_customer' and task.status == 'in_transit_to_tailor':
            task.status = 'completed'
            order.order_status = 'in_progress'
            db.session.commit()
            flash('Handover to tailor confirmed. Pickup task is complete!', 'success')
            return redirect(url_for('delivery.dashboard'))
            
        # Action for Pickup from Tailor (after stitching is done)
        elif task.task_type == 'pickup_from_tailor':
            task.status = 'completed'
            order.order_status = 'out_for_delivery'
            # Create the final delivery task and assign it to the same partner
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
            flash('Pickup from tailor confirmed. You have been assigned the final delivery.', 'success')
            return redirect(url_for('delivery.dashboard'))

        # Action for Final Delivery to Customer
        elif task.task_type == 'drop_to_customer':
            task.status = 'completed'
            order.order_status = 'completed'
            if order.payment_method != 'online_full': # Assuming 'cod' or 'advance'
                order.payment_status = 'fully_paid'
            db.session.commit()
            flash('Final delivery confirmed. Order complete!', 'success')
            return redirect(url_for('delivery.dashboard'))

    # For GET request, render the simple OTP form
    return render_template('delivery/verify_otp.html', task=task)