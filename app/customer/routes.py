from flask import render_template, flash, redirect, url_for, request, abort, session, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import func
from . import customer_bp
from .. import db
from ..models import (
    Order, User, Service, OrderItem, Address, UserProfile, TailorService,
    SubProfile, Logistic, MeasurementProfile, SavedMeasurementValue, OrderMeasurementValue, Category, Cart, CartItem, Rating
)
from ..notifications.routes import create_notification
from app.forms import CustomerProfileForm, AddressForm, SubProfileForm, OrderForm, MeasurementForm, SaveMeasurementForm, RatingForm, SimpleSubmitForm, AddToCartForm

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
    form = CustomerProfileForm(obj=user_profile, email=current_user.email)

    if form.validate_on_submit():
        user_profile.first_name = form.first_name.data
        user_profile.last_name = form.last_name.data
        user_profile.phone_number = form.phone_number.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your profile has been updated successfully!', 'success')
        return redirect(url_for('customer.account'))

    return render_template('customer/profile.html', form=form, profile=user_profile, addresses=addresses)

@customer_bp.route('/profile/add-address', methods=['GET', 'POST'])
@login_required
def add_address():
    """Allow customer to add a new address."""
    form = AddressForm()
    if form.validate_on_submit():
        new_address = Address(
            user_id=current_user.id,
            address_line1=form.address_line1.data,
            city=form.city.data,
            state=form.state.data,
            postal_code=form.postal_code.data,
            is_default=form.is_default.data
        )
        if new_address.is_default:
            Address.query.filter_by(user_id=current_user.id).update({'is_default': False})
        db.session.add(new_address)
        db.session.commit()
        flash("New address added successfully!", "success")
        return redirect(url_for('customer.account'))
    
    return render_template('customer/add_address.html', form=form)

@customer_bp.route('/profiles', methods=['GET', 'POST'])
@login_required
def my_profiles():
    """Manage sub-profiles for the customer (e.g., family members)."""
    form = SubProfileForm()
    if form.validate_on_submit():
        new_sub_profile = SubProfile(
            user_id=current_user.id,
            name=form.name.data,
            relationship=form.relationship.data,
            gender=form.gender.data,
            age_group=form.age_group.data
        )
        db.session.add(new_sub_profile)
        db.session.commit()
        flash(f'Profile for {form.name.data} added successfully!', 'success')
        return redirect(url_for('customer.account'))

    profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/my_profiles.html', form=form, profiles=profiles)

# Order Management Routes
@customer_bp.route('/orders')
@login_required
def order_history():
    """Display a list of all past and current orders for the customer."""
    all_orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('customer/order_history.html', orders=all_orders)

@customer_bp.route('/order/<int:order_id>')
@login_required
def order_details(order_id):
    """Display detailed view of a specific order, including OTPs and delivery partner info."""
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

    form = OrderForm()
    measurement_form = MeasurementForm(measurement_fields=required_measurements)
    form.delivery_address_id.choices = [(addr.id, f"{addr.address_line1}, {addr.city}") for addr in Address.query.filter_by(user_id=current_user.id).all()]

    profile_id_to_use = request.args.get('measurement_profile_id', type=int)
    if profile_id_to_use:
        saved_profile = MeasurementProfile.query.filter_by(id=profile_id_to_use, user_id=current_user.id).first()
        if not saved_profile:
            flash("The selected measurement profile was not found or does not belong to you.", "warning")
    else:
        saved_profile = MeasurementProfile.query.filter_by(user_id=current_user.id, service_id=tailor_service.service_id).order_by(MeasurementProfile.id.desc()).first()

    if saved_profile:
        for mv in saved_profile.measurements:
            saved_measurements_map[mv.measurement_field_id] = mv.value
            # Pre-fill measurement form
            if hasattr(measurement_form, f'measurement_{mv.measurement_field_id}'):
                getattr(measurement_form, f'measurement_{mv.measurement_field_id}').data = mv.value

    if request.method == 'POST' and form.validate() and (form.measurement_method.data == 'home_visit' or measurement_form.validate()):
        address = Address.query.get(form.delivery_address_id.data)
        if not address:
            flash("Invalid address selected.", "danger")
            return redirect(url_for('customer.profile'))

        order = Order(
            customer_id=current_user.id,
            tailor_id=tailor_service.tailor_id,
            delivery_address_id=address.id,
            total_amount=tailor_service.price,
            order_status='pending_tailor_acceptance',
            measurement_method=form.measurement_method.data
        )
        db.session.add(order)
        db.session.commit()

        order_item = OrderItem(order_id=order.id, tailor_service_id=tailor_service.id)
        db.session.add(order_item)
        db.session.commit()

        if form.measurement_method.data == 'online_submission':
            for measurement_field in required_measurements:
                value = measurement_form[f'measurement_{measurement_field.id}'].data
                if value:
                    measurement_value = OrderMeasurementValue(
                        order_item_id=order_item.id,
                        measurement_field_id=measurement_field.id,
                        value=float(value)
                    )
                    db.session.add(measurement_value)

        db.session.commit()
        create_notification(
            user_id=current_user.id,
            message=f"Your order #{order.id} has been placed and is awaiting tailor acceptance.",
            link=url_for('customer.order_details', order_id=order.id)
        )
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
        form=form,
        measurement_form=measurement_form,
        measurements=required_measurements,
        saved_measurements=saved_measurements_map,
        loaded_profile=saved_profile
    )

@customer_bp.route('/order/request-visit/<int:tailor_service_id>', methods=['GET', 'POST'])
@login_required
def request_visit(tailor_service_id):
    """Handle request for a home visit to take measurements."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
    form = OrderForm()
    form.delivery_address_id.choices = [(addr.id, f"{addr.address_line1}, {addr.city}") for addr in Address.query.filter_by(user_id=current_user.id).all()]

    if form.validate_on_submit():
        address = Address.query.get(form.delivery_address_id.data)
        if not address:
            flash("Invalid address selected.", "danger")
            return redirect(url_for('customer.request_visit', tailor_service_id=tailor_service_id))

        order = Order(
            customer_id=current_user.id,
            tailor_id=tailor_service.tailor_id,
            delivery_address_id=address.id,
            total_amount=tailor_service.price,
            order_status='pending_tailor_acceptance',
            measurement_method='home_visit'
        )
        db.session.add(order)
        db.session.commit()

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
        form=form,
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

    form = OrderForm()
    form.delivery_address_id.choices = [(addr.id, f"{addr.address_line1}, {addr.city}") for addr in Address.query.filter_by(user_id=current_user.id).all()]
    del form.measurement_method  # Remove measurement_method as it's already set

    if form.validate_on_submit():
        if form.payment_method.data == 'cash_on_delivery':
            order.payment_method = 'cash_on_delivery'
            order.payment_status = 'pending'
        elif form.payment_method.data == 'online_advance':
            order.payment_method = 'online_advance'
            order.payment_status = 'partially_paid'
            order.prepayment_amount = order.total_amount * 0.30
        elif form.payment_method.data == 'online_full':
            order.payment_method = 'online_full'
            order.payment_status = 'fully_paid'
            order.prepayment_amount = order.total_amount
        else:
            flash("Invalid payment option.", "danger")
            return redirect(url_for('customer.confirm_order', order_id=order.id))

        order.order_status = 'pending_tailor_acceptance'
        db.session.commit()
        flash("Your order has been confirmed! The tailor will be notified.", "success")
        return redirect(url_for('customer.order_details', order_id=order.id))

    return render_template('customer/confirm_order.html', order=order, form=form)

@customer_bp.route('/order_item/<int:item_id>/save-measurements', methods=['GET', 'POST'])
@login_required
def save_measurements(item_id):
    """Save measurements from an order item to a reusable profile."""
    order_item = OrderItem.query.get_or_404(item_id)
    if order_item.order.customer_id != current_user.id:
        flash("You do not have permission to access this order item.", "danger")
        return redirect(url_for('customer.order_history'))

    form = SaveMeasurementForm()
    form.sub_profile_id.choices = [(p.id, p.name) for p in SubProfile.query.filter_by(user_id=current_user.id).all()]

    if form.validate_on_submit():
        new_measurement_profile = MeasurementProfile(
            user_id=current_user.id,
            service_id=order_item.tailor_service.service_id,
            profile_name=form.profile_name.data,
            sub_profile_id=form.sub_profile_id.data
        )
        db.session.add(new_measurement_profile)
        db.session.commit()

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
    return render_template('customer/save_measurements_form.html', form=form, order_item=order_item, sub_profiles=sub_profiles)

# Service Browsing Routes
@customer_bp.route('/services/for/<int:profile_id>')
@login_required
def services_for_profile(profile_id):
    """Display services filtered by a sub-profile's gender and age group."""
    profile = SubProfile.query.get_or_404(profile_id)
    if profile.user_id != current_user.id:
        flash("You do not have permission to view this profile.", "danger")
        return redirect(url_for('customer.dashboard'))

    show_all = request.args.get('show') == 'all'
    if show_all:
        services = Service.query.order_by(Service.name).all()
    else:
        category_names_to_show = ['Unisex']
        if profile.gender == 'female':
            category_names_to_show.append('Womenswear')
        elif profile.gender == 'male':
            category_names_to_show.append('Menswear')
        if profile.age_group == 'child':
            category_names_to_show.append('Kidswear')

        services = Service.query.join(Service.categories).filter(
            Category.name.in_(category_names_to_show)
        ).all()

    session['active_profile_id'] = profile.id
    session['active_profile_name'] = profile.name
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
    avg_rating = db.session.query(func.avg(Rating.score)).filter_by(rating_for_user_id=tailor.id).scalar() or 0
    reviews = Rating.query.filter_by(rating_for_user_id=tailor.id).order_by(Rating.created_at.desc()).limit(5).all()
    form = AddToCartForm()
    return render_template(
        'customer/tailor_profile.html',
        tailor=tailor,
        services_offered=services_offered,
        avg_rating=avg_rating,
        reviews=reviews,
        form=form
    )

@customer_bp.route('/order/select-measurements/<int:tailor_service_id>')
@login_required
def select_measurements(tailor_service_id):
    """Display saved measurement profiles for a specific service."""
    tailor_service = TailorService.query.get_or_404(tailor_service_id)
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

# # Cart Management Routes
# @customer_bp.route('/cart/add/<int:tailor_service_id>', methods=['POST'])
# @login_required
# def add_to_cart(tailor_service_id):
#     """Add a tailor service to the cart."""
#     form = SimpleSubmitForm()
#     if form.validate_on_submit():
#         tailor_service = TailorService.query.get_or_404(tailor_service_id)
#         cart = Cart.query.filter_by(user_id=current_user.id).first()
#         if not cart:
#             cart = Cart(user_id=current_user.id)
#             db.session.add(cart)

#         if cart.items and cart.items[0].tailor_service.tailor_id != tailor_service.tailor_id:
#             return jsonify({'success': False, 'message': 'You can only order from one tailor at a time.'}), 400

#         existing_item = CartItem.query.filter_by(cart_id=cart.id, tailor_service_id=tailor_service.id).first()
#         if existing_item:
#             message = f'"{tailor_service.service.name}" is already in your cart.'
#         else:
#             new_item = CartItem(cart_id=cart.id, tailor_service_id=tailor_service.id)
#             db.session.add(new_item)
#             message = f'"{tailor_service.service.name}" has been added to your cart.'
        
#         db.session.commit()
#         return jsonify({'success': True, 'message': message})
#     return jsonify({'success': False, 'message': 'Invalid form submission.'}), 400

# @customer_bp.route('/cart')
# @login_required
# def view_cart():
#     """Displays the user's shopping cart."""
#     cart = Cart.query.filter_by(user_id=current_user.id).first()
#     if not cart:
#         cart = {'items': [], 'total': 0.0}
#     else:
#         cart.total = sum(item.tailor_service.price for item in cart.items)
#     return render_template('customer/view_cart.html', cart=cart)

# @customer_bp.route('/cart/remove/<int:item_id>', methods=['POST'])
# @login_required
# def remove_from_cart(item_id):
#     """Removes an item from the cart."""
#     form = SimpleSubmitForm()
#     if form.validate_on_submit():
#         item = CartItem.query.get_or_404(item_id)
#         if item.cart.user_id != current_user.id:
#             abort(403)
#         db.session.delete(item)
#         db.session.commit()
#         flash("Item removed from your cart.", "success")
#         return redirect(url_for('customer.view_cart'))
#     flash("Invalid form submission.", "danger")
#     return redirect(url_for('customer.view_cart'))

# @customer_bp.route('/checkout', methods=['GET', 'POST'])
# @login_required
# def checkout():
#     """Handle checkout process for cart items."""
#     cart = Cart.query.filter_by(user_id=current_user.id).first()
#     if not cart or not cart.items:
#         flash("Your cart is empty.", "warning")
#         return redirect(url_for('customer.dashboard'))

#     form = OrderForm()
#     form.delivery_address_id.choices = [(addr.id, f"{addr.address_line1}, {addr.city}") for addr in Address.query.filter_by(user_id=current_user.id).all()]

#     if form.validate_on_submit():
#         tailor_id = cart.items[0].tailor_service.tailor_id
#         total_amount = sum(item.tailor_service.price for item in cart.items)

#         new_order = Order(
#             customer_id=current_user.id,
#             tailor_id=tailor_id,
#             delivery_address_id=form.delivery_address_id.data,
#             total_amount=total_amount,
#             measurement_method=form.measurement_method.data,
#             order_status='pending_tailor_acceptance'
#         )
#         db.session.add(new_order)
#         db.session.commit()

#         for item in cart.items:
#             order_item = OrderItem(
#                 order_id=new_order.id,
#                 tailor_service_id=item.tailor_service_id
#             )
#             db.session.add(order_item)

#         db.session.delete(cart)
#         db.session.commit()

#         create_notification(
#             user_id=current_user.id,
#             message=f"Your order #{new_order.id} has been placed and is awaiting tailor acceptance.",
#             link=url_for('customer.order_details', order_id=new_order.id)
#         )
#         create_notification(
#             user_id=tailor_id,
#             message=f"New order #{new_order.id} is awaiting your acceptance.",
#             link=url_for('tailor.order_details', order_id=new_order.id)
#         )
#         flash("Your order has been placed successfully!", "success")
#         return redirect(url_for('customer.confirm_order', order_id=new_order.id))

#     cart.total = sum(item.tailor_service.price for item in cart.items)
#     addresses = Address.query.filter_by(user_id=current_user.id).all()
#     return render_template('customer/checkout.html', cart=cart, addresses=addresses, form=form)

# @customer_bp.route('/account')
# @login_required
# def account():
#     """Renders the main, tabbed 'My Account' page."""
#     addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()
#     sub_profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
#     return render_template('customer/account.html', addresses=addresses, sub_profiles=sub_profiles)

# @customer_bp.route('/profile/update', methods=['POST'])
# @login_required
# def update_profile():
#     """Handles the form submission for updating personal details."""
#     form = CustomerProfileForm()
#     if form.validate_on_submit():
#         profile = current_user.profile
#         profile.first_name = form.first_name.data
#         profile.last_name = form.last_name.data
#         profile.phone_number = form.phone_number.data
#         current_user.email = form.email.data
#         db.session.commit()
#         flash("Your details have been updated.", "success")
#         return redirect(url_for('customer.account'))
#     for field, errors in form.errors.items():
#         for error in errors:
#             flash(f"Error in {field}: {error}", "danger")
#     return redirect(url_for('customer.account'))

# @customer_bp.route('/order/<int:order_id>/rate', methods=['POST'])
# @login_required
# def rate_order(order_id):
#     """Rate a completed order."""
#     order = Order.query.get_or_404(order_id)
#     if order.customer_id != current_user.id or order.order_status != 'completed':
#         flash("You cannot rate this order at this time.", "danger")
#         return redirect(url_for('customer.order_history'))

#     form = RatingForm()
#     if form.validate_on_submit():
#         if Rating.query.filter_by(order_id=order.id).first():
#             flash("You have already submitted a review for this order.", "info")
#             return redirect(url_for('customer.order_details', order_id=order.id))

#         new_rating = Rating(
#             order_id=order.id,
#             rating_for_user_id=order.tailor_id,
#             rating_by_user_id=current_user.id,
#             score=form.score.data,
#             comment=form.comment.data
#         )
#         db.session.add(new_rating)
#         db.session.commit()
#         flash("Thank you for your feedback!", "success")
#         return redirect(url_for('customer.order_details', order_id=order.id))

#     for field, errors in form.errors.items():
#         for error in errors:
#             flash(f"Error in {field}: {error}", "danger")
#     return redirect(url_for('customer.order_details', order_id=order.id))

# @customer_bp.route('/cart/count')
# @login_required
# def cart_count():
#     """Returns the number of items in the user's cart as JSON."""
#     cart = Cart.query.filter_by(user_id=current_user.id).first()
#     count = len(cart.items) if cart else 0
#     return jsonify({'count': count})

# @customer_bp.route('/cart/add/<int:tailor_service_id>', methods=['POST'])
# @login_required
# def add_to_cart(tailor_service_id):
#     form = AddToCartForm()
#     if form.validate_on_submit():
#         try:
#             tailor_service = TailorService.query.get_or_404(tailor_service_id)
#             if not tailor_service.tailor.tailor_profile.is_verified:
#                 return jsonify({'success': False, 'message': 'This tailor is not verified.'}), 403
            
#             cart = Cart.query.filter_by(user_id=current_user.id).first()
#             if not cart:
#                 cart = Cart(user_id=current_user.id)
#                 db.session.add(cart)
            
#             # Check if cart has items from a different tailor
#             if cart.items and any(item.tailor_service.tailor_id != tailor_service.tailor_id for item in cart.items):
#                 return jsonify({'success': False, 'message': 'You can only order from one tailor at a time.'}), 400
            
#             # Check if item is already in cart
#             if any(item.tailor_service_id == tailor_service_id for item in cart.items):
#                 return jsonify({'success': True, 'message': f'{tailor_service.service.name} is already in your cart.'})
            
#             cart_item = CartItem(cart_id=cart.id, tailor_service_id=tailor_service_id)
#             db.session.add(cart_item)
#             db.session.commit()
#             return jsonify({'success': True, 'message': f'{tailor_service.service.name} has been added to your cart.'})
#         except Exception as e:
#             db.session.rollback()
#             return jsonify({'success': False, 'message': f'Error adding item to cart: {str(e)}'}), 500
#     return jsonify({'success': False, 'message': 'Invalid form submission.'}), 400

# @customer_bp.route('/cart/add/<int:tailor_service_id>', methods=['POST'])
# @login_required
# def add_to_cart(tailor_service_id):
#     """Adds a tailor service to the user's cart."""
#     form = AddToCartForm()
    
#     # This check now succeeds because the frontend sends valid form data
#     if form.validate_on_submit():
#         try:
#             tailor_service = TailorService.query.get_or_404(tailor_service_id)
            
#             # Check if tailor is verified
#             if not tailor_service.tailor.tailor_profile.is_verified:
#                 return jsonify({'success': False, 'message': 'This tailor is not verified.'}), 403
            
#             cart = Cart.query.filter_by(user_id=current_user.id).first()
#             if not cart:
#                 cart = Cart(user_id=current_user.id)
#                 db.session.add(cart)
            
#             # Check if cart has items from a different tailor
#             if cart.items and any(item.tailor_service.tailor_id != tailor_service.tailor_id for item in cart.items):
#                 return jsonify({'success': False, 'message': 'You can only order from one tailor at a time.'}), 400
            
#             # Check if item is already in cart
#             if any(item.tailor_service_id == tailor_service_id for item in cart.items):
#                 return jsonify({'success': True, 'message': f'{tailor_service.service.name} is already in your cart.'})
            
#             cart_item = CartItem(cart_id=cart.id, tailor_service_id=tailor_service_id)
#             db.session.add(cart_item)
#             db.session.commit()
            
#             return jsonify({'success': True, 'message': f'{tailor_service.service.name} has been added to your cart.'})
        
#         except Exception as e:
#             db.session.rollback()
#             print(f"Error adding to cart: {e}")
#             return jsonify({'success': False, 'message': f'Error adding item to cart: {str(e)}'}), 500
    
    # This part of the code is now only reached if the form submission is genuinely invalid
    # (e.g., missing CSRF token, which should be handled by the frontend)
#    return jsonify({'success': False, 'message': 'Invalid form submission.'}), 400

# @customer_bp.route('/cart/add/<int:tailor_service_id>', methods=['POST'])
# @login_required
# def add_to_cart(tailor_service_id):
#     """Adds a tailor service to the user's cart."""
#     form = AddToCartForm()
    
#     if form.validate_on_submit():
#         try:
#             tailor_service = TailorService.query.get_or_404(tailor_service_id)
            
#             if not tailor_service.tailor.tailor_profile.is_verified:
#                 return jsonify({'success': False, 'message': 'This tailor is not verified.'}), 403
            
#             # Get or create the cart and commit to assign an ID
#             cart = Cart.query.filter_by(user_id=current_user.id).first()
#             if not cart:
#                 cart = Cart(user_id=current_user.id)
#                 db.session.add(cart)
#                 db.session.commit()  # Commit to get cart.id
            
#             # Check if cart has items from a different tailor
#             if cart.items and any(item.tailor_service.tailor_id != tailor_service.tailor_id for item in cart.items):
#                 return jsonify({'success': False, 'message': 'You can only order from one tailor at a time.'}), 400
            
#             # Check if item is already in cart
#             if any(item.tailor_service_id == tailor_service_id for item in cart.items):
#                 return jsonify({'success': True, 'message': f'{tailor_service.service.name} is already in your cart.'})
            
#             # Now cart.id is guaranteed to exist
#             cart_item = CartItem(cart_id=cart.id, tailor_service_id=tailor_service_id)
#             db.session.add(cart_item)
#             db.session.commit()
            
#             return jsonify({'success': True, 'message': f'{tailor_service.service.name} has been added to your cart.'})
        
#         except Exception as e:
#             db.session.rollback()
#             print(f"Error adding to cart: {e}")
#             return jsonify({'success': False, 'message': f'Error adding item to cart: {str(e)}'}), 500

#     return jsonify({'success': False, 'message': 'Invalid form submission.'}), 400

@customer_bp.route('/cart/add/<int:tailor_service_id>', methods=['POST'])
@login_required
def add_to_cart(tailor_service_id):
    """Adds a tailor service to the user's cart or increments quantity if already present."""
    form = AddToCartForm()
    
    if form.validate_on_submit():
        try:
            tailor_service = TailorService.query.get_or_404(tailor_service_id)
            
            if not tailor_service.tailor.tailor_profile.is_verified:
                return jsonify({'success': False, 'message': 'This tailor is not verified.'}), 403
            
            # Get or create the cart and commit to assign an ID
            cart = Cart.query.filter_by(user_id=current_user.id).first()
            if not cart:
                cart = Cart(user_id=current_user.id)
                db.session.add(cart)
                db.session.commit()  # Commit to get cart.id
            
            # Check if cart has items from a different tailor
            if cart.items and any(item.tailor_service.tailor_id != tailor_service.tailor_id for item in cart.items):
                return jsonify({'success': False, 'message': 'You can only order from one tailor at a time.'}), 400
            
            # Check if item is already in cart and increment quantity
            existing_item = next((item for item in cart.items if item.tailor_service_id == tailor_service_id), None)
            if existing_item:
                existing_item.quantity += 1
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': f'Quantity for {tailor_service.service.name} increased to {existing_item.quantity}.',
                    'quantity': existing_item.quantity
                })
            
            # Add new item if not present
            cart_item = CartItem(cart_id=cart.id, tailor_service_id=tailor_service_id)
            db.session.add(cart_item)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'{tailor_service.service.name} has been added to your cart.',
                'quantity': 1
            })
        
        except Exception as e:
            db.session.rollback()
            print(f"Error adding to cart: {e}")
            return jsonify({'success': False, 'message': f'Error adding item to cart: {str(e)}'}), 500

    return jsonify({'success': False, 'message': 'Invalid form submission.'}), 400

@customer_bp.route('/cart')
@login_required
def view_cart():
    """Displays the user's shopping cart."""
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    form = SimpleSubmitForm()
    if not cart:
        cart = {'items': [], 'total': 0.0}
    else:
        cart.total = sum(item.tailor_service.price for item in cart.items)
    return render_template('customer/view_cart.html', cart=cart, form=form, current_year=datetime.now().year)

@customer_bp.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    """Removes an item from the cart."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        item = CartItem.query.get_or_404(item_id)
        if item.cart.user_id != current_user.id:
            abort(403)
        db.session.delete(item)
        db.session.commit()
        flash("Item removed from your cart.", "success")
        return redirect(url_for('customer.view_cart'))
    flash("Invalid form submission.", "danger")
    return redirect(url_for('customer.view_cart'))

@customer_bp.route('/cart_count')
@login_required
def cart_count():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    count = sum(item.quantity for item in cart.items) if cart and cart.items else 0
    return jsonify({'count': count})

@customer_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Handle checkout process for cart items."""
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart or not cart.items:
        flash("Your cart is empty.", "warning")
        return redirect(url_for('customer.dashboard'))
    form = OrderForm()
    form.delivery_address_id.choices = [(addr.id, f"{addr.address_line1}, {addr.city}") for addr in Address.query.filter_by(user_id=current_user.id).all()]
    if form.validate_on_submit():
        tailor_id = cart.items[0].tailor_service.tailor_id
        total_amount = sum(item.tailor_service.price for item in cart.items)
        new_order = Order(
            customer_id=current_user.id,
            tailor_id=tailor_id,
            delivery_address_id=form.delivery_address_id.data,
            total_amount=total_amount,
            measurement_method=form.measurement_method.data,
            order_status='pending_tailor_acceptance'
        )
        db.session.add(new_order)
        db.session.commit()
        for item in cart.items:
            order_item = OrderItem(
                order_id=new_order.id,
                tailor_service_id=item.tailor_service_id
            )
            db.session.add(order_item)
        db.session.delete(cart)
        db.session.commit()
        create_notification(
            user_id=current_user.id,
            message=f"Your order #{new_order.id} has been placed and is awaiting tailor acceptance.",
            link=url_for('customer.order_details', order_id=new_order.id)
        )
        create_notification(
            user_id=tailor_id,
            message=f"New order #{new_order.id} is awaiting your acceptance.",
            link=url_for('tailor.order_details', order_id=new_order.id)
        )
        flash("Your order has been placed successfully!", "success")
        return redirect(url_for('customer.confirm_order', order_id=new_order.id))
    cart.total = sum(item.tailor_service.price for item in cart.items)
    addresses = Address.query.filter_by(user_id=current_user.id).all()
    return render_template('customer/checkout.html', cart=cart, addresses=addresses, form=form, current_year=datetime.now().year)

@customer_bp.route('/account', methods=['GET', 'POST'])
@login_required
def account():
    """Renders the main, tabbed 'My Account' page."""
    profile_form = CustomerProfileForm(obj=current_user.profile)
    subprofile_form = SubProfileForm()
    addresses = Address.query.filter_by(user_id=current_user.id).order_by(Address.is_default.desc()).all()
    sub_profiles = SubProfile.query.filter_by(user_id=current_user.id).all()
    if profile_form.validate_on_submit() and profile_form.submit.data:
        profile = current_user.profile or UserProfile(user_id=current_user.id)
        profile.first_name = profile_form.first_name.data
        profile.last_name = profile_form.last_name.data
        profile.email = profile_form.email.data
        profile.phone_number = profile_form.phone_number.data
        current_user.email = profile_form.email.data
        if not current_user.profile:
            db.session.add(profile)
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('customer.account', tab='details'))
    if subprofile_form.validate_on_submit() and subprofile_form.submit.data:
        sub_profile = SubProfile(
            user_id=current_user.id,
            name=subprofile_form.name.data,
            relationship=subprofile_form.relationship.data,
            gender=subprofile_form.gender.data,
            age_group=subprofile_form.age_group.data
        )
        db.session.add(sub_profile)
        db.session.commit()
        flash('Family member added successfully!', 'success')
        return redirect(url_for('customer.account', tab='family'))
    for field, errors in profile_form.errors.items():
        for error in errors:
            flash(f"Error in {field}: {error}", "danger")
    for field, errors in subprofile_form.errors.items():
        for error in errors:
            flash(f"Error in {field}: {error}", "danger")
    return render_template('customer/account.html', 
                         profile_form=profile_form, 
                         subprofile_form=subprofile_form, 
                         addresses=addresses, 
                         sub_profiles=sub_profiles, 
                         current_year=datetime.now().year)

@customer_bp.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Handles the form submission for updating personal details."""
    form = CustomerProfileForm()
    if form.validate_on_submit():
        profile = current_user.profile or UserProfile(user_id=current_user.id)
        profile.first_name = form.first_name.data
        profile.last_name = form.last_name.data
        profile.phone_number = form.phone_number.data
        current_user.email = form.email.data
        if not current_user.profile:
            db.session.add(profile)
        db.session.commit()
        flash("Your details have been updated.", "success")
        return redirect(url_for('customer.account', tab='details'))
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {field}: {error}", "danger")
    return redirect(url_for('customer.account', tab='details'))

@customer_bp.route('/order/<int:order_id>/rate', methods=['POST'])
@login_required
def rate_order(order_id):
    """Rate a completed order."""
    order = Order.query.get_or_404(order_id)
    if order.customer_id != current_user.id or order.order_status != 'completed':
        flash("You cannot rate this order at this time.", "danger")
        return redirect(url_for('customer.order_history'))
    form = RatingForm()
    if form.validate_on_submit():
        if Rating.query.filter_by(order_id=order.id).first():
            flash("You have already submitted a review for this order.", "info")
            return redirect(url_for('customer.order_details', order_id=order.id))
        new_rating = Rating(
            order_id=order.id,
            rating_for_user_id=order.tailor_id,
            rating_by_user_id=current_user.id,
            score=form.score.data,
            comment=form.comment.data
        )
        db.session.add(new_rating)
        db.session.commit()
        flash("Thank you for your feedback!", "success")
        return redirect(url_for('customer.order_details', order_id=order.id))
    for field, errors in form.errors.items():
        for error in errors:
            flash(f"Error in {field}: {error}", "danger")
    return redirect(url_for('customer.order_details', order_id=order.id))

# @customer_bp.route('/cart/count')
# @login_required
# def cart_count():
#     """Returns the number of items in the user's cart as JSON."""
#     cart = Cart.query.filter_by(user_id=current_user.id).first()
#     count = len(cart.items) if cart else 0
#     return jsonify({'count': count})

