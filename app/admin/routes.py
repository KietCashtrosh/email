from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from .. import db
from ..models import Order, Service, MeasurementField, User, TailorProfile, DeliveryPartnerProfile, Logistic, ServiceVariation, ServiceCategory, Category
from . import admin_bp

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# @admin_bp.route('/dashboard')
# @login_required
# @admin_required
# def dashboard():
#     total_orders = Order.query.count()
#     pending_orders = Order.query.filter(Order.order_status.in_(['pending_tailor_acceptance', 'awaiting_pickup', 'fabric_in_transit', 'in_progress'])).count()
#     completed_orders = Order.query.filter_by(order_status='completed').count()
#     pending_tailors = User.query.join(TailorProfile).filter(TailorProfile.is_approved == False, User.role == 'tailor').count()
#     pending_partners = User.query.join(DeliveryPartnerProfile).filter(DeliveryPartnerProfile.is_approved == False, User.role == 'delivery_partner').count()
#     active_deliveries = Logistic.query.filter(Logistic.status.in_(['assigned', 'in_transit_to_tailor'])).count()
#     recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
#     return render_template('admin/dashboard.html', 
#                            total_orders=total_orders, pending_orders=pending_orders, completed_orders=completed_orders,
#                            pending_tailors=pending_tailors, pending_partners=pending_partners, active_deliveries=active_deliveries,
#                            recent_orders=recent_orders)

@admin_bp.route('/orders')
@login_required
@admin_required
def orders():
    status = request.args.get('status')
    orders = Order.query.all() if not status else Order.query.filter_by(order_status=status).all()
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/services')
@login_required
@admin_required
def services():
    services = Service.query.all()
    return render_template('admin/services.html', services=services)

# app/admin/routes.py

# Make sure to import the new Category model
from ..models import Service, Category

@admin_bp.route('/services/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_service():
    if request.method == 'POST':
        name = request.form.get('name')
        # Get a list of all selected category IDs
        category_ids = request.form.getlist('category_ids')
        
        new_service = Service(name=name)
        
        # Find the category objects and link them
        categories = Category.query.filter(Category.id.in_(category_ids)).all()
        new_service.categories = categories
        
        db.session.add(new_service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('admin.services'))

    # Pass all available categories to the template
    all_categories = Category.query.all()
    import pdb; pdb.set_trace()
    return render_template('admin/add_service.html', categories=all_categories)


@admin_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        service.name = request.form.get('name')
        category_ids = request.form.getlist('category_ids')
        
        # Update the linked categories
        categories = Category.query.filter(Category.id.in_(category_ids)).all()
        service.categories = categories
        
        db.session.commit()
        flash('Service updated!', 'success')
        return redirect(url_for('admin.services'))
    
    # Get IDs of the service's current categories for pre-selecting checkboxes
    current_category_ids = {category.id for category in service.categories}
    all_categories = Category.query.all()
    return render_template('admin/edit_service.html', service=service, 
                           categories=all_categories, current_category_ids=current_category_ids)

@admin_bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_service(service_id):
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash('Service deleted.', 'success')
    return redirect(url_for('admin.services'))

@admin_bp.route('/services/<int:service_id>/measurements', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service_measurements(service_id):
    service = Service.query.get_or_404(service_id)
    all_measurements = MeasurementField.query.all()
    if request.method == 'POST':
        selected_ids = request.form.getlist('measurement_ids')
        service.standard_measurements = [MeasurementField.query.get(m_id) for m_id in selected_ids if m_id]
        db.session.commit()
        flash('Measurements updated for service.', 'success')
        return redirect(url_for('admin.services'))
    current_ids = {m.id for m in service.standard_measurements}
    return render_template('admin/manage_measurements.html', service=service, all_measurements=all_measurements, current_ids=current_ids)

@admin_bp.route('/measurement_fields/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_measurement_field():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        new_field = MeasurementField(name=name, description=description, image_url=image_url)
        db.session.add(new_field)
        db.session.commit()
        flash('Measurement field added.', 'success')
        return redirect(url_for('admin.services'))  # Redirect to services as fields are related
    return render_template('admin/add_measurement_field.html')

@admin_bp.route('/logistics')
@login_required
@admin_required
def logistics():
    logistics = Logistic.query.all()
    return render_template('admin/logistics.html', logistics=logistics)

@admin_bp.route('/tailors/pending')
@login_required
@admin_required
def pending_tailors():
    tailors = User.query.join(TailorProfile).filter(TailorProfile.is_verified == False, User.role == 'tailor').all()
    return render_template('admin/pending_tailors.html', tailors=tailors)

@admin_bp.route('/tailors/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_tailor(user_id):
    tailor = User.query.get_or_404(user_id)
    if tailor.role == 'tailor' and tailor.tailor_profile:
        tailor.tailor_profile.is_verified = True # Corrected from is_approved
        db.session.commit()
        flash('Tailor approved.', 'success')
    return redirect(url_for('admin.dashboard')) # Redirect to the main dashboard

@admin_bp.route('/delivery_partners/pending')
@login_required
@admin_required
def pending_delivery_partners():
    partners = User.query.join(DeliveryPartnerProfile).filter(DeliveryPartnerProfile.is_approved == False, User.role == 'delivery_partner').all()
    return render_template('admin/pending_delivery_partners.html', partners=partners)

@admin_bp.route('/delivery_partners/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_delivery_partner(user_id):
    partner = User.query.get_or_404(user_id)
    if partner.role == 'delivery_partner' and partner.delivery_partner_profile:
        partner.delivery_partner_profile.is_approved = True
        db.session.commit()
        flash('Delivery partner approved.', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """A consolidated dashboard for key stats and actions."""
    # Fetch pending users directly for display
    pending_tailors = User.query.join(TailorProfile).filter(
        User.role == 'tailor',
        TailorProfile.is_verified == False # Corrected from is_approved
    ).all()
    
    pending_partners = User.query.join(DeliveryPartnerProfile).filter(
        User.role == 'delivery_partner',
        DeliveryPartnerProfile.is_approved == False
    ).all()
    
    # Fetch key stats
    total_orders = Order.query.count()
    active_orders_count = Order.query.filter(Order.order_status != 'completed').count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                           pending_tailors=pending_tailors,
                           pending_partners=pending_partners,
                           total_orders=total_orders,
                           active_orders_count=active_orders_count,
                           recent_orders=recent_orders)

# Note: The dedicated /pending routes are now handled by the dashboard, but you can keep them if you prefer.

@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """Displays a searchable and filterable list of all users."""
    # The page parameter is for pagination in the future
    page = request.args.get('page', 1, type=int)
    # Simple pagination query
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=15)
    return render_template('admin/manage_users.html', users=users)


@admin_bp.route('/user/<int:user_id>')
@login_required
@admin_required
def user_details(user_id):
    """Displays a detailed view of a single user and their related profiles."""
    user = User.query.get_or_404(user_id)
    # Fetch recent orders for this user (as customer or tailor)
    recent_orders = Order.query.filter(
        (Order.customer_id == user_id) | (Order.tailor_id == user_id)
    ).order_by(Order.created_at.desc()).limit(5).all()

    return render_template('admin/user_details.html', user=user, recent_orders=recent_orders)

# app/admin/routes.py

@admin_bp.route('/measurements', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_measurements():
    """Admin page to view and add new master MeasurementFields."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        
        if name:
            new_field = MeasurementField(
                name=name, 
                description=description, 
                image_url=image_url
            )
            db.session.add(new_field)
            db.session.commit()
            flash(f'Measurement field "{name}" created successfully!', 'success')
            return redirect(url_for('admin.manage_measurements'))

    measurements = MeasurementField.query.all()
    return render_template('admin/manage_measurements.html', measurements=measurements)

@admin_bp.route('/order/<int:order_id>/details')
@login_required
@admin_required
def order_details(order_id):
    """Shows a complete, detailed view of an order for the admin."""
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_details.html', order=order)

@admin_bp.route('/service/<int:service_id>/variations', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service_variations(service_id):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        # Logic to add a new variation
        name = request.form.get('name')
        if name:
            new_variation = ServiceVariation(name=name, service_id=service.id)
            db.session.add(new_variation)
            db.session.commit()
            flash(f'Variation "{name}" added to {service.name}.', 'success')
            return redirect(url_for('admin.manage_service_variations', service_id=service.id))

    return render_template('admin/manage_variations.html', service=service)

# app/admin/routes.py

# Add Category to your imports
from ..models import Category 

@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_categories():
    """Admin page to view, add, and manage master categories."""
    if request.method == 'POST':
        name = request.form.get('name')
        if name and not Category.query.filter_by(name=name).first():
            new_category = Category(name=name)
            db.session.add(new_category)
            db.session.commit()
            flash(f'Category "{name}" created successfully!', 'success')
        else:
            flash(f'Category "{name}" already exists or is invalid.', 'danger')
        return redirect(url_for('admin.manage_categories'))

    # For the GET request, fetch all categories to display
    all_categories = Category.query.all()
    return render_template('admin/manage_categories.html', categories=all_categories)

@admin_bp.route('/category/<int:category_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    # Optional: Add logic here to check if any services are using this category before deleting
    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{category.name}" has been deleted.', 'success')
    return redirect(url_for('admin.manage_categories'))

# app/admin/routes.py

@admin_bp.route('/orders/monitor')
@login_required
@admin_required
def monitor_orders():
    """A live view of all orders that are not yet completed."""
    
    # Define the statuses that are considered "final"
    final_statuses = ['completed', 'cancelled']
    
    # Fetch all orders that are not in a final state
    active_orders = Order.query.filter(
        ~Order.order_status.in_(final_statuses)
    ).order_by(Order.created_at.desc()).all()

    return render_template('admin/monitor_orders.html', orders=active_orders)