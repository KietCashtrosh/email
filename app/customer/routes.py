# app/customer/routes.py

from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from . import customer_bp
from ..models import Order, User, Service, OrderItem, Address, UserProfile, TailorService
from .. import db
from datetime import datetime
from ..models import SubProfile, Logistic
from ..models import MeasurementProfile, SavedMeasurementValue, OrderMeasurementValue
from flask import render_template, abort
from . import customer_bp
from app.models import Service, TailorService
from sqlalchemy import text # Make sure to import text

@customer_bp.route('/profiles', methods=['GET', 'POST'])
@login_required
def my_profiles():
    if request.method == 'POST':
        name = request.form.get('name')
        relationship = request.form.get('relationship')
        gender = request.form.get('gender')
        age_group = request.form.get('age_group')

        if name and relationship:
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

@customer_bp.route('/dashboard')
@login_required
def dashboard():
    """
    The customer dashboard, now showing available services and featured tailors.
    """
    profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/dashboard.html', profiles=profiles)
    # Fetch all master services to display as cards
    # all_services = Service.query.order_by(Service.name).all()
    
    # # Fetch a few tailors to feature on the page
    # featured_tailors = User.query.filter_by(role='tailor').limit(4).all()

    # return render_template('customer/dashboard.html',
    #                        services=all_services,
    #                        tailors=featured_tailors)

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

    # --- CORRECTED LOGIC TO FIND SAVED MEASUREMENTS ---
    # Initialize the map first
    saved_measurements_map = {}
    
    # Check if a specific saved profile ID was passed in the query string (e.g., for pre-selection)
    profile_id_to_use = request.args.get('measurement_profile_id', type=int)
    
    if profile_id_to_use:
        # Fetch the specific profile if provided and ensure it belongs to the user
        saved_profile = MeasurementProfile.query.filter_by(
            id=profile_id_to_use, 
            user_id=current_user.id
        ).first()
        if saved_profile:
            for mv in saved_profile.measurements:
                saved_measurements_map[mv.measurement_field_id] = mv.value
        else:
            flash("The selected measurement profile was not found or does not belong to you.", "warning")
    else:
        # If no specific ID, fall back to the most recent saved profile for this service
        saved_profile = MeasurementProfile.query.filter_by(
            user_id=current_user.id,
            service_id=tailor_service.service_id
        ).order_by(MeasurementProfile.id.desc()).first()  # Order by ID descending for most recent
        
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
        db.session.commit()  # Commit to get order.id

        # Create the OrderItem
        order_item = OrderItem(
            order_id=order.id,
            tailor_service_id=tailor_service.id
        )
        db.session.add(order_item)
        db.session.commit()  # Commit to get order_item.id

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
                           saved_measurements=saved_measurements_map,
                           loaded_profile=saved_profile)

# @customer_bp.route('/order/new/<int:tailor_service_id>', methods=['GET', 'POST'])
# @login_required
# def new_order(tailor_service_id):
#     """
#     Handles the creation of a new order with a specific tailor for a specific service.
#     """
#     tailor_service = TailorService.query.get_or_404(tailor_service_id)
#     required_measurements = tailor_service.custom_measurements

#     # --- NEW LOGIC TO FIND SAVED MEASUREMENTS ---
#      # Check if a saved profile ID was passed in the URL
#     profile_id_to_use = request.args.get('measurement_profile_id', type=int)
#     if profile_id_to_use:
#         # Fetch that specific profile
#         saved_profile = MeasurementProfile.query.filter_by(id=profile_id_to_use, user_id=current_user.id).first()
#         if saved_profile:
#             for mv in saved_profile.measurements:
#                 saved_measurements_map[mv.measurement_field_id] = mv.value

#     saved_measurements_map = {}
#     # Find saved measurement profiles for this USER and service type
#     saved_profile = MeasurementProfile.query.filter_by(
#         user_id=current_user.id,
#         service_id=tailor_service.service_id
#     ).first() # Find the first/most recent one

#     if saved_profile:
#         for mv in saved_profile.measurements:
#             saved_measurements_map[mv.measurement_field_id] = mv.value

#     if request.method == 'POST':
#         # Find the user's default address
#         address = Address.query.filter_by(user_id=current_user.id, is_default=True).first()
#         if not address:
#             flash("Please set a default address in your profile.", "danger")
#             return redirect(url_for('customer.profile'))

#         # Create the main Order
#         order = Order(
#             customer_id=current_user.id,
#             tailor_id=tailor_service.tailor_id,
#             delivery_address_id=address.id,
#             total_amount=tailor_service.price,
#             order_status='pending_tailor_acceptance',
#             measurement_method='online_submission'
#         )
#         db.session.add(order)
#         db.session.commit() # Commit to get order.id

#         # Create the OrderItem
#         order_item = OrderItem(
#             order_id=order.id,
#             tailor_service_id=tailor_service.id
#         )
#         db.session.add(order_item)
#         db.session.commit() # Commit to get order_item.id

#         # Loop through the form to get measurement values and save them
#         for measurement_field in required_measurements:
#             value = request.form.get(f"measurement_{measurement_field.id}")
#             if value:
#                 measurement_value = OrderMeasurementValue(
#                     order_item_id=order_item.id,
#                     measurement_field_id=measurement_field.id,
#                     value=float(value)
#                 )
#                 db.session.add(measurement_value)

#         db.session.commit()
#         flash("Your order has been placed successfully!", "success")
#         return redirect(url_for('customer.confirm_order', order_id=order.id))

#     return render_template('customer/new_order_form.html', 
#                            tailor_service=tailor_service,
#                            measurements=required_measurements,
#                            saved_measurements=saved_measurements_map)

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
            profile_name=profile_name,
            sub_profile_id=int(sub_profile_id) if sub_profile_id else None
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

@customer_bp.route('/services/for/<int:profile_id>')
@login_required
def services_for_profile(profile_id):
    """
    Shows a filtered list of services based on the selected profile's gender/age.
    """
    profile = SubProfile.query.get_or_404(profile_id)
    # Security check: ensure profile belongs to current user
    if profile.user_id != current_user.id:
        return redirect(url_for('customer.dashboard'))

    show_all = request.args.get('show') == 'all'

    # Determine which categories to show
    if show_all:
        services = Service.query.order_by(Service.name).all()
    else:
        # Determine which categories to show based on profile
        categories_to_show = ['Unisex'] # Always include Unisex items
        if profile.gender == 'Female':
            categories_to_show.append('Womenswear')
        elif profile.gender == 'Male':
            categories_to_show.append('Menswear')
        
        if profile.age_group == 'Kid':
            categories_to_show.append('Kidswear')

        # Query services based on the list of categories
        services = Service.query.filter(Service.category.in_(categories_to_show)).all()

        return render_template('customer/services.html', profile=profile, services=services)
            

    return render_template('customer/services.html', 
                           profile=profile, 
                           services=services,
                           show_all=show_all)

# In app/customer/routes.py

@customer_bp.route('/service/<int:service_id>/variations')
def service_variations(service_id):
    print("\n" + "="*50)
    print(f"DEBUGGING SERVICE VARIATIONS PAGE")
    print("="*50)

    # Step 1: Check the incoming service ID from the URL
    print(f"[STEP 1] Incoming service_id from URL: {service_id}")

    # Step 2: Try to fetch the service with this ID
    service = Service.query.get(service_id)
    if not service:
        print(f"[RESULT] No service found for id={service_id}. This is why it's failing.")
        print("="*50 + "\n")
        abort(404) # Service not found
    
    print(f"[STEP 2] Fetched Service from DB: ID={service.id}, Name='{service.name}'")
    
    # Step 3: Check ALL tailor offerings in the database to see what's there
    all_offerings = TailorService.query.all()
    print(f"[STEP 3] Found a total of {len(all_offerings)} offerings in the 'tailor_services' table.")
    for offer in all_offerings:
        print(f"  -> Offering ID: {offer.id}, Tailor ID: {offer.tailor_id}, Service ID: {offer.service_id}, Price: {offer.price}")

    # Step 4: Run the ACTUAL query the page uses and see what it returns
    print(f"[STEP 4] Running the final query for Service ID: {service.id} ('{service.name}')")
    variations = TailorService.query.filter_by(service_id=service.id).all()
    
    print(f"[RESULT] The query returned {len(variations)} items.")
    print("="*50 + "\n")

    # The rest of the function remains the same
    return render_template(
        'customer/service_variations.html', 
        service=service, 
        variations=variations
    )

# app/customer/routes.py

@customer_bp.route('/order/select-measurements/<int:tailor_service_id>')
@login_required
def select_measurements(tailor_service_id):
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    
    # Find all saved measurement profiles for this user and this specific service type
    saved_profiles = MeasurementProfile.query.filter_by(
        user_id=current_user.id,
        service_id=tailor_service.service_id
    ).all()

    return render_template('customer/select_measurements.html', 
                           tailor_service=tailor_service,
                           saved_profiles=saved_profiles)