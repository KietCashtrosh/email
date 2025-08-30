from flask import render_template, flash, redirect, url_for, request, abort
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import text
from . import customer_bp
from .. import db
from ..models import (
    Order, User, Service, OrderItem, Address, UserProfile, TailorService,
    SubProfile, Logistic, MeasurementProfile, SavedMeasurementValue, OrderMeasurementValue, Category
)
from ..notifications.routes import create_notification

# Dashboard Route
@customer_bp.route('/dashboard')
@login_required
def dashboard():
    """Display customer dashboard with available profiles."""
    profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/dashboard.html', profiles=profiles)

# Profile Management Routes
@customer_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Allow customer to view and update their profile information."""
    user_profile = current_user.profile
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    
    if request.method == 'POST':
        # Update user profile details
        user_profile.first_name = request.form.get('first_name')
        user_profile.last_name = request.form.get('last_name')
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('customer.profile'))

    return render_template('customer/profile.html', profile=user_profile, addresses=addresses)

@customer_bp.route('/profile/add-address', methods=['GET', 'POST'])
@login_required
def add_address():
    """Allow customer to add a new address."""
    if request.method == 'POST':
        # Create new address from form data
        new_address = Address(
            user_id=current_user.id,
            address_line1=request.form.get('address_line1'),
            city=request.form.get('city'),
            state=request.form.get('state'),
            postal_code=request.form.get('postal_code'),
            is_default=request.form.get('is_default') == 'on'
        )
        
        # Ensure only one default address
        if new_address.is_default:
            Address.query.filter_by(user_id=current_user.id).update({'is_default': False})
        
        db.session.add(new_address)
        db.session.commit()
        flash("New address added successfully!", "success")
        return redirect(url_for('customer.profile'))

    return render_template('customer/add_address.html')

@customer_bp.route('/profiles', methods=['GET', 'POST'])
@login_required
def my_profiles():
    """Manage sub-profiles for the customer (e.g., family members)."""
    if request.method == 'POST':
        name = request.form.get('name')
        relationship = request.form.get('relationship')
        gender = request.form.get('gender')
        age_group = request.form.get('age_group')

        if name and relationship:
            # Create new sub-profile
            new_sub_profile = SubProfile(
                user_id=current_user.id,
                name=name,
                relationship=relationship,
                gender=gender,
                age_group=age_group
            )
            db.session.add(new_sub_profile)
            db.session.commit()
            flash(f'Profile for {name} added successfully!', 'success')
            return redirect(url_for('customer.services_for_profile', profile_id=new_sub_profile.id))

    profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/my_profiles.html', profiles=profiles)

# Order Management Routes
@customer_bp.route('/orders')
@login_required
def order_history():
    """Display a list of all past and current orders for the customer."""
    all_orders = Order.query.filter_by(customer_id=current_user.id)\
                            .order_by(Order.created_at.desc()).all()
    return render_template('customer/order_history.html', orders=all_orders)

@customer_bp.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """Display detailed view of a specific order, including OTPs and delivery partner info."""
    order = Order.query.get_or_404(order_id)
    
    # Ensure order belongs to the customer
    if order.customer_id != current_user.id:
        flash('You do not have permission to view this order.', 'danger')
        return redirect(url_for('customer.order_history'))

    # Fetch delivery partner and OTPs
    pickup_otp, delivery_otp = None, None
    delivery_partner = None
    task_with_partner = Logistic.query.filter(
        Logistic.order_id == order.id,
        Logistic.delivery_partner_id.isnot(None)
    ).first()
    if task_with_partner:
        delivery_partner = task_with_partner.delivery_partner
    
    pickup_task = Logistic.query.filter_by(order_id=order.id, task_type='pickup_from_customer').first()
    if pickup_task:
        pickup_otp = pickup_task.pickup_otp

    delivery_task = Logistic.query.filter_by(order_id=order.id, task_type='drop_to_customer').first()
    if delivery_task:
        delivery_otp = delivery_task.delivery_otp

    return render_template(
        'customer/order_details.html',
        order=order,
        delivery_partner=delivery_partner,
        pickup_otp=pickup_otp,
        delivery_otp=delivery_otp
    )

@customer_bp.route('/order/new/<int:tailor_service_id>', methods=['GET', 'POST'])
@login_required
def new_order(tailor_service_id):
    """Handle creation of a new order with a specific tailor's service."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    required_measurements = tailor_service.custom_measurements
    saved_measurements_map = {}
    saved_profile = None

    # Fetch saved measurement profile if specified or most recent for the service
    profile_id_to_use = request.args.get('measurement_profile_id', type=int)
    if profile_id_to_use:
        saved_profile = MeasurementProfile.query.filter_by(
            id=profile_id_to_use, user_id=current_user.id
        ).first()
        if not saved_profile:
            flash("The selected measurement profile was not found or does not belong to you.", "warning")
    else:
        saved_profile = MeasurementProfile.query.filter_by(
            user_id=current_user.id, service_id=tailor_service.service_id
        ).order_by(MeasurementProfile.id.desc()).first()

    if saved_profile:
        for mv in saved_profile.measurements:
            saved_measurements_map[mv.measurement_field_id] = mv.value

    if request.method == 'POST':
        # Validate default address
        address = Address.query.filter_by(user_id=current_user.id, is_default=True).first()
        if not address:
            flash("Please set a default address in your profile.", "danger")
            return redirect(url_for('customer.profile'))

        # Create order
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

        # Create order item
        order_item = OrderItem(order_id=order.id, tailor_service_id=tailor_service.id)
        db.session.add(order_item)
        db.session.commit()

        # Save measurement values
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
        'customer/new_order_form.html',
        tailor_service=tailor_service,
        measurements=required_measurements,
        saved_measurements=saved_measurements_map,
        loaded_profile=saved_profile
    )

@customer_bp.route('/order/request-visit/<int:tailor_service_id>', methods=['GET', 'POST'])
@login_required
def request_visit(tailor_service_id):
    """Handle request for a home visit to take measurements."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    
    if request.method == 'POST':
        address_id = request.form.get('address_id')
        pickup_date = request.form.get('pickup_date')
        pickup_time = request.form.get('pickup_time')

        if not address_id:
            flash("Please select a delivery address.", "danger")
            return redirect(url_for('customer.request_visit', tailor_service_id=tailor_service_id))

        # Create order for home visit
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

        # Create order item
        order_item = OrderItem(order_id=order.id, tailor_service_id=tailor_service_id)
        db.session.add(order_item)
        db.session.commit()

        flash("Your request for a home visit has been confirmed!", "success")
        return redirect(url_for('customer.confirm_order', order_id=order.id))

    all_addresses = Address.query.filter_by(user_id=current_user.id).all()
    if not all_addresses:
        flash("Please add an address to your profile first.", "info")
        return redirect(url_for('customer.profile'))

    return render_template(
        'customer/request_visit_form.html',
        tailor_service=tailor_service,
        addresses=all_addresses,
        now=datetime.utcnow()
    )

@customer_bp.route('/order/<int:order_id>/confirm', methods=['GET', 'POST'])
@login_required
def confirm_order(order_id):
    """Confirm order details and process payment selection."""
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
            order.payment_method = 'online_advance'
            order.payment_status = 'partially_paid'
            order.prepayment_amount = order.total_amount * 0.30
        elif payment_option == 'full':
            order.payment_method = 'online_full'
            order.payment_status = 'fully_paid'
            order.prepayment_amount = order.total_amount
        else:
            flash("Please select a valid payment option.", "danger")
            return redirect(url_for('customer.confirm_order', order_id=order.id))

        order.order_status = 'pending_tailor_acceptance'
        db.session.commit()
        flash("Your order has been confirmed! The tailor will be notified.", "success")
        return redirect(url_for('customer.order_details', order_id=order.id))

    return render_template('customer/confirm_order.html', order=order)

@customer_bp.route('/order_item/<int:item_id>/save-measurements', methods=['GET', 'POST'])
@login_required
def save_measurements(item_id):
    """Save measurements from an order item to a reusable profile."""
    order_item = OrderItem.query.get_or_404(item_id)
    
    # Ensure order item belongs to the customer
    if order_item.order.customer_id != current_user.id:
        flash("You do not have permission to access this order item.", "danger")
        return redirect(url_for('customer.order_history'))

    if request.method == 'POST':
        sub_profile_id = request.form.get('sub_profile_id')
        profile_name = request.form.get('profile_name')

        if not sub_profile_id or not profile_name:
            flash("Please select a profile and provide a name for the measurement set.", "danger")
            return redirect(url_for('customer.save_measurements', item_id=item_id))

        # Create new measurement profile
        new_measurement_profile = MeasurementProfile(
            user_id=current_user.id,
            service_id=order_item.tailor_service.service_id,
            profile_name=profile_name,
            sub_profile_id=int(sub_profile_id) if sub_profile_id else None
        )
        db.session.add(new_measurement_profile)
        db.session.commit()

        # Copy measurements to the new profile
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

# Service Browsing Routes
@customer_bp.route('/services/for/<int:profile_id>')
@login_required
def services_for_profile(profile_id):
    """Display services filtered by a sub-profile's gender and age group."""
    profile = SubProfile.query.get_or_404(profile_id)
    
    # Ensure profile belongs to the customer
    if profile.user_id != current_user.id:
        flash("You do not have permission to view this profile.", "danger")
        return redirect(url_for('customer.dashboard'))

    show_all = request.args.get('show') == 'all'
    
    if show_all:
        services = Service.query.order_by(Service.name).all()
    else:
        # Filter services by gender and age group
        category_names_to_show = ['Unisex']
        if profile.gender == 'Female':
            category_names_to_show.append('Womenswear')
        elif profile.gender == 'Male':
            category_names_to_show.append('Menswear')
        if profile.age_group == 'Kid':
            category_names_to_show.append('Kidswear')

        services = Service.query.join(Service.categories).filter(
            Category.name.in_(category_names_to_show)
        ).all()

    return render_template(
        'customer/services.html',
        profile=profile,
        services=services,
        show_all=show_all
    )

@customer_bp.route('/service/<int:service_id>/tailors')
@login_required
def tailors_for_service(service_id):
    """Display list of tailors offering a specific service."""
    service = Service.query.get_or_404(service_id)
    
    # Fetch tailors offering this service
    tailors = User.query.join(User.tailor_services).filter(
        TailorService.service_id == service_id
    ).all()

    return render_template(
        'customer/tailors_for_service.html',
        service=service,
        tailors=tailors
    )

@customer_bp.route('/service/<int:service_id>/variations')
def service_variations(service_id):
    """Display variations of a service offered by different tailors."""
    service = Service.query.get_or_404(service_id)
    variations = TailorService.query.filter_by(service_id=service.id).all()
    
    return render_template(
        'customer/service_variations.html',
        service=service,
        variations=variations
    )

@customer_bp.route('/tailor/<int:tailor_id>')
@login_required
def tailor_profile(tailor_id):
    """Display public profile of a specific tailor."""
    tailor = User.query.filter_by(id=tailor_id, role='tailor').first_or_404()
    services_offered = TailorService.query.filter_by(tailor_id=tailor.id).all()

    return render_template(
        'customer/tailor_profile.html',
        tailor=tailor,
        services_offered=services_offered
    )

@customer_bp.route('/order/select-measurements/<int:tailor_service_id>')
@login_required
def select_measurements(tailor_service_id):
    """Display saved measurement profiles for a specific service."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    
    # Fetch saved measurement profiles for this user and service
    saved_profiles = MeasurementProfile.query.filter_by(
        user_id=current_user.id,
        service_id=tailor_service.service_id
    ).all()

    return render_template(
        'customer/select_measurements.html',
        tailor_service=tailor_service,
        saved_profiles=saved_profiles
    )

@customer_bp.route('/order/options/<int:tailor_service_id>')
@login_required
def order_options(tailor_service_id):
    """Display options for providing measurements and fabric for an order."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    return render_template('customer/order_options.html', tailor_service=tailor_service)