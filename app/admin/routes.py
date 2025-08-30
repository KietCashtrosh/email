from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from .. import db
from . import admin_bp
from ..models import (
    Order, Service, MeasurementField, User, TailorProfile, DeliveryPartnerProfile,
    Logistic, ServiceVariation, Category
)
from ..notifications.routes import create_notification

# Custom decorator to restrict access to admins only
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

# Dashboard Route
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Display admin dashboard with key statistics and pending actions."""
    # Fetch pending tailors and delivery partners
    pending_tailors = User.query.join(TailorProfile).filter(
        User.role == 'tailor',
        TailorProfile.is_verified == False
    ).all()
    
    pending_partners = User.query.join(DeliveryPartnerProfile).filter(
        User.role == 'delivery_partner',
        DeliveryPartnerProfile.is_approved == False
    ).all()
    
    # Fetch order statistics
    total_orders = Order.query.count()
    active_orders_count = Order.query.filter(Order.order_status != 'completed').count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        pending_tailors=pending_tailors,
        pending_partners=pending_partners,
        total_orders=total_orders,
        active_orders_count=active_orders_count,
        recent_orders=recent_orders
    )

# User Management Routes
@admin_bp.route('/users')
@login_required
@admin_required
def manage_users():
    """Display a paginated list of all users for admin management."""
    page = request.args.get('page', 1, type=int)
    users = User.query.order_by(User.created_at.desc()).paginate(page=page, per_page=15)
    return render_template('admin/manage_users.html', users=users)

@admin_bp.route('/user/<int:user_id>')
@login_required
@admin_required
def user_details(user_id):
    """Display detailed information about a specific user, including recent orders."""
    user = User.query.get_or_404(user_id)
    recent_orders = Order.query.filter(
        (Order.customer_id == user_id) | (Order.tailor_id == user_id)
    ).order_by(Order.created_at.desc()).limit(5).all()
    return render_template('admin/user_details.html', user=user, recent_orders=recent_orders)

@admin_bp.route('/tailors/pending')
@login_required
@admin_required
def pending_tailors():
    """Display a list of tailors pending approval."""
    tailors = User.query.join(TailorProfile).filter(
        TailorProfile.is_verified == False, User.role == 'tailor'
    ).all()
    return render_template('admin/pending_tailors.html', tailors=tailors)

@admin_bp.route('/tailors/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_tailor(user_id):
    """Approve a tailor's profile."""
    tailor = User.query.get_or_404(user_id)
    if tailor.role == 'tailor' and tailor.tailor_profile:
        tailor.tailor_profile.is_verified = True
        db.session.commit()
        create_notification(
            user_id=user_id,
            message="Your tailor profile has been approved! You can now accept orders.",
            link=url_for('tailor.dashboard')
        )
        create_notification(
            user_id=None,  # Admin room
            message=f"Tailor ID #{user_id} has been approved.",
            link=url_for('admin.user_details', user_id=user_id)
        )
        flash('Tailor approved.', 'success')
    else:
        flash('Invalid tailor profile.', 'danger')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delivery_partners/pending')
@login_required
@admin_required
def pending_delivery_partners():
    """Display a list of delivery partners pending approval."""
    partners = User.query.join(DeliveryPartnerProfile).filter(
        DeliveryPartnerProfile.is_approved == False, User.role == 'delivery_partner'
    ).all()
    return render_template('admin/pending_delivery_partners.html', partners=partners)

@admin_bp.route('/delivery_partners/approve/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def approve_delivery_partner(user_id):
    """Approve a delivery partner's profile."""
    partner = User.query.get_or_404(user_id)
    if partner.role == 'delivery_partner' and partner.delivery_partner_profile:
        partner.delivery_partner_profile.is_approved = True
        db.session.commit()
        create_notification(
            user_id=user_id,
            message="Your delivery partner profile has been approved! You can now accept delivery tasks.",
            link=url_for('delivery.dashboard')
        )
        create_notification(
            user_id=None,  # Admin room
            message=f"Delivery Partner ID #{user_id} has been approved.",
            link=url_for('admin.user_details', user_id=user_id)
        )
        flash('Delivery partner approved.', 'success')
    else:
        flash('Invalid delivery partner profile.', 'danger')
    return redirect(url_for('admin.dashboard'))

# Service Management Routes
@admin_bp.route('/services')
@login_required
@admin_required
def services():
    """Display a list of all services in the system."""
    services = Service.query.all()
    return render_template('admin/services.html', services=services)

@admin_bp.route('/services/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_service():
    """Add a new service with associated categories."""
    if request.method == 'POST':
        name = request.form.get('name')
        category_ids = request.form.getlist('category_ids')
        
        # Create new service and link categories
        new_service = Service(name=name)
        categories = Category.query.filter(Category.id.in_(category_ids)).all()
        new_service.categories = categories
        
        db.session.add(new_service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('admin.services'))

    all_categories = Category.query.all()
    return render_template('admin/add_service.html', categories=all_categories)

@admin_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    """Edit an existing service's name and categories."""
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        service.name = request.form.get('name')
        category_ids = request.form.getlist('category_ids')
        categories = Category.query.filter(Category.id.in_(category_ids)).all()
        service.categories = categories
        db.session.commit()
        flash('Service updated!', 'success')
        return redirect(url_for('admin.services'))
    
    current_category_ids = {category.id for category in service.categories}
    all_categories = Category.query.all()
    return render_template(
        'admin/edit_service.html',
        service=service,
        categories=all_categories,
        current_category_ids=current_category_ids
    )

@admin_bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_service(service_id):
    """Delete a service from the system."""
    service = Service.query.get_or_404(service_id)
    db.session.delete(service)
    db.session.commit()
    flash('Service deleted.', 'success')
    return redirect(url_for('admin.services'))

@admin_bp.route('/services/<int:service_id>/measurements', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service_measurements(service_id):
    """Manage standard measurements for a specific service."""
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        selected_ids = request.form.getlist('measurement_ids')
        service.standard_measurements = [
            MeasurementField.query.get(m_id) for m_id in selected_ids if m_id
        ]
        db.session.commit()
        flash('Measurements updated for service.', 'success')
        return redirect(url_for('admin.services'))
    
    all_measurements = MeasurementField.query.all()
    current_ids = {m.id for m in service.standard_measurements}
    return render_template(
        'admin/manage_measurements.html',
        service=service,
        all_measurements=all_measurements,
        current_ids=current_ids
    )

@admin_bp.route('/service/<int:service_id>/variations', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service_variations(service_id):
    """Manage variations for a specific service."""
    service = Service.query.get_or_404(service_id)
    
    if request.method == 'POST':
        name = request.form.get('name')
        if name:
            new_variation = ServiceVariation(name=name, service_id=service.id)
            db.session.add(new_variation)
            db.session.commit()
            flash(f'Variation "{name}" added to {service.name}.', 'success')
            return redirect(url_for('admin.manage_service_variations', service_id=service.id))

    return render_template('admin/manage_variations.html', service=service)

# Measurement Field Management Routes
@admin_bp.route('/measurements', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_measurements():
    """Manage master measurement fields."""
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

@admin_bp.route('/measurement_fields/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_measurement_field():
    """Add a new measurement field."""
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        new_field = MeasurementField(name=name, description=description, image_url=image_url)
        db.session.add(new_field)
        db.session.commit()
        flash('Measurement field added.', 'success')
        return redirect(url_for('admin.services'))
    
    return render_template('admin/add_measurement_field.html')

# Order Management Routes
@admin_bp.route('/orders')
@login_required
@admin_required
def orders():
    """Display a list of all orders, filterable by status."""
    status = request.args.get('status')
    orders = Order.query.all() if not status else Order.query.filter_by(order_status=status).all()
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/order/<int:order_id>/details')
@login_required
@admin_required
def order_details(order_id):
    """Display detailed view of a specific order."""
    order = Order.query.get_or_404(order_id)
    return render_template('admin/order_details.html', order=order)

@admin_bp.route('/orders/monitor')
@login_required
@admin_required
def monitor_orders():
    """Display a live view of all active (non-completed/cancelled) orders."""
    final_statuses = ['completed', 'cancelled']
    active_orders = Order.query.filter(
        ~Order.order_status.in_(final_statuses)
    ).order_by(Order.created_at.desc()).all()
    return render_template('admin/monitor_orders.html', orders=active_orders)

# Logistics Management Route
@admin_bp.route('/logistics')
@login_required
@admin_required
def logistics():
    """Display a list of all logistics tasks."""
    logistics = Logistic.query.all()
    return render_template('admin/logistics.html', logistics=logistics)

# Category Management Routes
@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_categories():
    """Manage master categories for services."""
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

    all_categories = Category.query.all()
    return render_template('admin/manage_categories.html', categories=all_categories)

@admin_bp.route('/category/<int:category_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    """Delete a category from the system."""
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    flash(f'Category "{category.name}" has been deleted.', 'success')
    return redirect(url_for('admin.manage_categories'))