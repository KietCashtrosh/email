Code:
tailor route:

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

auth route:

# app/auth/routes.py

import random
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from .. import db
from ..models import User, UserProfile, TailorProfile, DeliveryPartnerProfile
import re

# --- Placeholder for SMS service ---
# You would replace this with a real implementation from Twilio, etc.
# --- (send_otp_sms function remains the same) ---


def send_otp_sms(phone_number, otp):
    print("--- MOCK SMS ---")
    print(f"Sending OTP {otp} to {phone_number}")
    print("----------------")


# --- NEW HELPER FUNCTION ---
def check_profile_and_redirect(user):
    """
    Checks if a user's profile is complete.
    Redirects to the update profile page if not, otherwise to the dashboard.
    """
    if user.role == 'tailor':
        return redirect(url_for('tailor.dashboard'))

    # --- NEW: Add the delivery partner case ---
    elif user.role == 'delivery_partner':
        # Assuming you will create a 'delivery_bp' blueprint for them
        return redirect(url_for('delivery.dashboard'))

    elif user.role == 'customer':
        # A profile is "incomplete" if the first_name is missing.
        if not user.profile or not user.profile.first_name:
            return redirect(url_for('customer.update_profile'))
        return redirect(url_for('customer.dashboard'))
    
    else:
        # Fallback
        return redirect(url_for('auth.logout'))



# --- MODIFIED: Unified Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        # Regex to check if the identifier is an email
        is_email = re.match(r"[^@]+@[^@]+\.[^@]+", identifier)

        if is_email:
            # --- Email & Password Logic ---
            user = User.query.filter_by(email=identifier).first()
            if user and user.check_password(password):
                login_user(user, remember=True)
                return check_profile_and_redirect(user)
            else:
                flash('Invalid email or password.', 'danger')
        else:
            # --- Phone Number & OTP Logic ---
            phone_number = identifier
            # Minimal validation for phone number
            if not phone_number or not phone_number.isdigit():
                flash('Please enter a valid phone number or email.', 'danger')
                return redirect(url_for('auth.login'))

            # Generate OTP, store it in the session, and send it
            otp = random.randint(100000, 999999)
            session['otp'] = otp
            session['phone_number_for_verification'] = phone_number
            session['verification_context'] = 'login'
            send_otp_sms(phone_number, otp)
            
            flash('An OTP has been sent to your phone number.', 'info')
            return redirect(url_for('auth.verify'))

    return render_template('auth/login.html')


# --- MODIFIED: OTP Verification with Implicit Registration ---
@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    # Check if we have the necessary info in the session
    if 'phone_number_for_verification' not in session or 'verification_context' not in session:
        flash('Something went wrong. Please start over.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        submitted_otp = request.form.get('otp')
        if 'otp' in session and str(session['otp']) == submitted_otp:
            phone_number = session['phone_number_for_verification']
            context = session['verification_context']

            user = User.query.filter_by(phone_number=phone_number).first()

            # Logic for new registration
            if context == 'registration':
                if not user: # This should always be true for registration
                     # Create new user
                    user = User(phone_number=phone_number, role='customer', is_verified=True)
                    # Create a blank profile
                    profile = UserProfile(user=user, phone_number=phone_number)
                    db.session.add(user)
                    db.session.add(profile)
                    db.session.commit()
                    flash('Your account has been created and verified!', 'success')
                else: # This is an edge case, but good to handle
                    user.is_verified = True
                    db.session.commit()

            # This handles both login and the final step of registration
            if not user:
                flash('User not found. Please register.', 'danger')
                return redirect(url_for('auth.register'))

            login_user(user, remember=True)

            # Clean up session
            session.pop('otp', None)
            session.pop('phone_number_for_verification', None)
            session.pop('verification_context', None)

            return check_profile_and_redirect(user)
        else:
            flash('Invalid OTP. Please try again.', 'danger')

    # For the GET request, just render the template
    return render_template('auth/verify_otp.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        role = request.form.get('role')
        if role not in ['customer', 'tailor', 'delivery_partner']:
            flash('Please select a valid role.', 'danger')
            return redirect(url_for('auth.register'))
        
        phone = request.form.get('phone_number')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        # Check for existing users
        if User.query.filter_by(phone_number=phone).first():
            flash('This phone number is already registered.', 'danger')
            return redirect(url_for('auth.register'))
        if email and User.query.filter_by(email=email).first():
            flash('This email address is already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # --- THIS IS THE CORRECTED LOGIC ---

        # 1. Create the User object
        new_user = User(
            phone_number=phone, 
            email=email,
            role=role,
            is_verified=False
        )
        new_user.set_password(password)
        
        # 2. Create the associated profiles
        new_user.profile = UserProfile(
            first_name=first_name, 
            last_name=last_name, 
            phone_number=phone
        )
        
        if role == 'tailor':
            new_user.tailor_profile = TailorProfile()
        elif role == 'delivery_partner':
            new_user.delivery_partner_profile = DeliveryPartnerProfile()

        # 3. Add the parent User object to the session.
        #    SQLAlchemy will handle saving the associated profiles automatically due to the 'cascade' option.
        db.session.add(new_user)
        db.session.commit()
        
        # --- END OF CORRECTION ---

        # Send OTP for verification
        otp = random.randint(100000, 999999)
        session['otp'] = otp
        session['phone_number_for_verification'] = phone
        session['verification_context'] = 'registration'
        send_otp_sms(phone, otp)

        flash('Registration successful! An OTP has been sent to verify your phone number.', 'info')
        return redirect(url_for('auth.verify'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))


Customers route:
# app/customer/routes.py
# app/customer/routes.py

from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from . import customer_bp
from ..models import Order, User, Service, OrderItem, Address, UserProfile, TailorService
from .. import db
from datetime import datetime
from ..models import SubProfile, Logistic
from ..models import MeasurementProfile, SavedMeasurementValue, OrderMeasurementValue


@customer_bp.route('/profiles', methods=['GET', 'POST'])
@login_required
def my_profiles():
    if request.method == 'POST':
        name = request.form.get('name')
        relationship = request.form.get('relationship')

        if name and relationship:
            new_sub_profile = SubProfile(
                user_id=current_user.id,
                name=name,
                relationship=relationship
            )
            db.session.add(new_sub_profile)
            db.session.commit()
            flash(f'Profile for {name} added successfully!', 'success')
            return redirect(url_for('customer.my_profiles'))

    profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/my_profiles.html', profiles=profiles)

@customer_bp.route('/dashboard')
@login_required
def dashboard():
    """
    The customer dashboard, now showing available services and featured tailors.
    """
    # Fetch all master services to display as cards
    all_services = Service.query.order_by(Service.name).all()
    
    # Fetch a few tailors to feature on the page
    featured_tailors = User.query.filter_by(role='tailor').limit(4).all()

    return render_template('customer/dashboard.html',
                           services=all_services,
                           tailors=featured_tailors)

@customer_bp.route('/orders')
@login_required
def order_history():
    """
    Displays a list of all past and current orders for the customer.
    """
    all_orders = Order.query.filter_by(customer_id=current_user.id)\
                            .order_by(Order.created_at.desc()).all()
    return render_template('customer/order_history.html', orders=all_orders)


@customer_bp.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """
    Shows the detailed view of a single order.
    """
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        flash('You do not have permission to view this order.', 'danger')
        return redirect(url_for('customer.order_history'))
    pickup_otp, delivery_otp = None, None
    delivery_partner = None
    task_with_partner = Logistic.query.filter(
        Logistic.order_id == order.id,
        Logistic.delivery_partner_id.isnot(None)
    ).first()
    if task_with_partner:
        delivery_partner = task_with_partner.delivery_partner
    
    # Find the pickup task to show its OTP
    pickup_task = Logistic.query.filter_by(order_id=order.id, task_type='pickup_from_customer').first()
    if pickup_task:
        pickup_otp = pickup_task.pickup_otp

    # Find the delivery task to show its OTP
    delivery_task = Logistic.query.filter_by(order_id=order.id, task_type='drop_to_customer').first()
    if delivery_task:
        delivery_otp = delivery_task.delivery_otp

    return render_template('customer/order_details.html', 
                           order=order,
                           delivery_partner=delivery_partner,
                           pickup_otp=pickup_otp,
                           delivery_otp=delivery_otp)



@customer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Allows the customer to view and update their profile information.
    """
    user_profile = current_user.profile
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    if request.method == 'POST':
        user_profile.first_name = request.form.get('first_name')
        user_profile.last_name = request.form.get('last_name')
        # user_profile.phone_number = request.form.get('phone_number')
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('customer.profile'))

    return render_template('customer/profile.html', profile=current_user.profile, addresses=addresses)


@customer_bp.route('/service/<int:service_id>/tailors')
@login_required
def tailors_for_service(service_id):
    """
    Displays a list of all tailors who offer a specific service.
    """
    service = Service.query.get_or_404(service_id)

    # Find all TailorService offerings for the given service_id
    # and from there, get the User object for each tailor.
    tailors = User.query.join(User.tailor_services).filter(
        TailorService.service_id == service_id
    ).all()

    return render_template('customer/tailors_for_service.html', 
                           service=service, 
                           tailors=tailors)


@customer_bp.route('/tailor/<int:tailor_id>')
@login_required
def tailor_profile(tailor_id):
    """Displays a public profile page for a specific tailor."""
    tailor = User.query.filter_by(id=tailor_id, role='tailor').first_or_404()

    # Fetch all services offered by this tailor
    services_offered = TailorService.query.filter_by(tailor_id=tailor.id).all()

    # Fetch ratings for this tailor (we'll add this feature later)
    # ratings = Rating.query.filter_by(rating_for_user_id=tailor.id).all()

    return render_template('customer/tailor_profile.html', 
                           tailor=tailor, 
                           services_offered=services_offered)


@customer_bp.route('/order/new/<int:tailor_service_id>', methods=['GET', 'POST'])
@login_required
def new_order(tailor_service_id):
    """
    Handles the creation of a new order with a specific tailor for a specific service.
    """
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    required_measurements = tailor_service.custom_measurements

    # --- NEW LOGIC TO FIND SAVED MEASUREMENTS ---
    saved_measurements_map = {}
    # Find saved measurement profiles for this USER and service type
    saved_profile = MeasurementProfile.query.filter_by(
        user_id=current_user.id,
        service_id=tailor_service.service_id
    ).first() # Find the first/most recent one

    if saved_profile:
        for mv in saved_profile.measurements:
            saved_measurements_map[mv.measurement_field_id] = mv.value

    if request.method == 'POST':
        # Find the user's default address
        address = Address.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not address:
            flash("Please set a default address in your profile.", "danger")
            return redirect(url_for('customer.profile'))

        # Create the main Order
        order = Order(
            customer_id=current_user.id,
            tailor_id=tailor_service.tailor_id,
            delivery_address_id=address.id,
            total_amount=tailor_service.price,
            order_status='pending_tailor_acceptance',
            measurement_method='online_submission'
        )
        db.session.add(order)
        db.session.commit() # Commit to get order.id

        # Create the OrderItem
        order_item = OrderItem(
            order_id=order.id,
            tailor_service_id=tailor_service.id
        )
        db.session.add(order_item)
        db.session.commit() # Commit to get order_item.id

        # Loop through the form to get measurement values and save them
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
        flash("Your order has been placed successfully!", "success")
        return redirect(url_for('customer.confirm_order', order_id=order.id))

    return render_template('customer/new_order_form.html', 
                           tailor_service=tailor_service,
                           measurements=required_measurements,
                           saved_measurements=saved_measurements_map)

# app/customer/routes.py

@customer_bp.route('/order/request-visit/<int:tailor_service_id>', methods=['GET', 'POST'])
@login_required
def request_visit(tailor_service_id):
    """
    Handles the request for a home visit and creates a preliminary order.
    """
    tailor_service = TailorService.query.get_or_404(tailor_service_id)

    # POST request logic (when the user submits the form)
    if request.method == 'POST':
        address_id = request.form.get('address_id')
        pickup_date = request.form.get('pickup_date')
        pickup_time = request.form.get('pickup_time')

        if not address_id:
            flash("Please select a delivery address.", "danger")
            return redirect(url_for('customer.request_visit', tailor_service_id=tailor_service_id))

        # You can add logic here to parse and save the pickup_date and pickup_time
        # For example: start_time = datetime.strptime(f"{pickup_date} {pickup_time.split('-')[0]}", "%Y-%m-%d %H:%M")

        # Create the Order with a 'pending_home_visit' status
        order = Order(
            customer_id=current_user.id,
            tailor_id=tailor_service.tailor_id,
            delivery_address_id=address_id,
            total_amount=tailor_service.price,
            order_status='pending_tailor_acceptance',
            measurement_method='home_visit'
        )
        db.session.add(order)
        db.session.commit()

        # Create the associated OrderItem
        order_item = OrderItem(order_id=order.id, tailor_service_id=tailor_service_id)
        db.session.add(order_item)
        db.session.commit()

        flash("Your request for a home visit has been confirmed!", "success")
        return redirect(url_for('customer.confirm_order', order_id=order.id))

    # --- Corrected GET request logic (when the page first loads) ---
    # 1. Fetch ALL of the user's addresses to display in the form
    all_addresses = Address.query.filter_by(user_id=current_user.id).all()

    # 2. Check if the user has any addresses at all
    if not all_addresses:
        flash("Please add an address to your profile first.", "info")
        return redirect(url_for('customer.profile'))

    # 3. Render the form, passing the list of addresses
    return render_template('customer/request_visit_form.html',
                           tailor_service=tailor_service,
                           addresses=all_addresses, # Pass the full list
                           now=datetime.utcnow())



@customer_bp.route('/order/options/<int:tailor_service_id>')
@login_required
def order_options(tailor_service_id):
    """
    Shows the user the options for providing measurements and fabric.
    """
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    return render_template('customer/order_options.html', tailor_service=tailor_service)


@customer_bp.route('/order/<int:order_id>/confirm', methods=['GET', 'POST'])
@login_required
def confirm_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id:
        flash("You do not have permission to view this order.", "danger")
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        payment_option = request.form.get('payment_option')

        if payment_option == 'cod':
            order.payment_method = 'cash_on_delivery'
            order.payment_status = 'pending'

        elif payment_option == 'advance':
            # In a real app, you would redirect to a payment gateway here
            # For our dummy integration, we'll just simulate a successful payment
            advance_amount = order.total_amount * 0.30
            order.payment_method = 'online_advance'
            order.payment_status = 'partially_paid'
            order.prepayment_amount = advance_amount

        elif payment_option == 'full':
            # In a real app, you would redirect to a payment gateway here
            order.payment_method = 'online_full'
            order.payment_status = 'fully_paid'
            order.prepayment_amount = order.total_amount

        else:
            flash("Please select a valid payment option.", "danger")
            return redirect(url_for('customer.confirm_order', order_id=order.id))

        # Update order status to the next step in the lifecycle
        if order.measurement_method == 'home_visit':
            order.order_status = 'pending_tailor_acceptance'
        else:
            order.order_status = 'pending_tailor_acceptance'

        db.session.commit()
        flash("Your order has been confirmed! The tailor will be notified.", "success")
        return redirect(url_for('customer.order_details', order_id=order.id))

    return render_template('customer/confirm_order.html', order=order)

@customer_bp.route('/profile/add-address', methods=['GET', 'POST'])
@login_required
def add_address():
    if request.method == 'POST':
        # Create new Address object from form data
        new_address = Address(
            user_id=current_user.id,
            address_line1=request.form.get('address_line1'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            postal_code=request.form.get('postal_code'),
            is_default=request.form.get('is_default') == 'on'
        )
        
        # If this new address is the default, make sure no others are
        if new_address.is_default:
            Address.query.filter_by(user_id=current_user.id).update({'is_default': False})
        
        db.session.add(new_address)
        db.session.commit()
        flash("New address added successfully!", "success")
        return redirect(url_for('customer.profile'))

    return render_template('customer/add_address.html')

@customer_bp.route('/order_item/<int:item_id>/save-measurements', methods=['GET', 'POST'])
@login_required
def save_measurements(item_id):
    order_item = OrderItem.query.get_or_404(item_id)
    # Security checks...

    if request.method == 'POST':
        sub_profile_id = request.form.get('sub_profile_id')
        profile_name = request.form.get('profile_name')

        if not sub_profile_id or not profile_name:
            flash("Please select a profile and provide a name for the measurement set.", "danger")
            return redirect(url_for('customer.save_measurements', item_id=item_id))

        # Create the main measurement profile
        new_measurement_profile = MeasurementProfile(
            user_id=current_user.id,
            service_id=order_item.tailor_service.service_id,
            profile_name=profile_name
        )
        db.session.add(new_measurement_profile)
        db.session.commit()

        # Copy the measurements from the order to the new saved profile
        for measured_value in order_item.measurements:
            new_saved_value = SavedMeasurementValue(
                profile_id=new_measurement_profile.id,
                measurement_field_id=measured_value.measurement_field_id,
                value=measured_value.value
            )
            db.session.add(new_saved_value)

        db.session.commit()
        flash("Measurements saved successfully!", "success")
        return redirect(url_for('customer.my_profiles'))

    sub_profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/save_measurements_form.html', order_item=order_item, sub_profiles=sub_profiles)

delivery route:
# app/delivery/routes.py
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