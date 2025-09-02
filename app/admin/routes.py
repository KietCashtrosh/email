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
from werkzeug.utils import secure_filename
import os
from flask import current_app
from app.forms import ServiceForm, CategoryForm, MeasurementFieldForm, SimpleSubmitForm, MeasurementSelectionForm, VariationForm

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
    pending_tailors = User.query.join(TailorProfile).filter(
        User.role == 'tailor',
        TailorProfile.is_verified == False
    ).all()
    pending_partners = User.query.join(DeliveryPartnerProfile).filter(
        User.role == 'delivery_partner',
        DeliveryPartnerProfile.is_approved == False
    ).all()
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
    form = SimpleSubmitForm()
    if form.validate_on_submit():
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
                user_id=None,
                message=f"Tailor ID #{user_id} has been approved.",
                link=url_for('admin.user_details', user_id=user_id)
            )
            flash('Tailor approved.', 'success')
        else:
            flash('Invalid tailor profile.', 'danger')
        return redirect(url_for('admin.dashboard'))
    flash('Invalid form submission.', 'danger')
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
    form = SimpleSubmitForm()
    if form.validate_on_submit():
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
                user_id=None,
                message=f"Delivery Partner ID #{user_id} has been approved.",
                link=url_for('admin.user_details', user_id=user_id)
            )
            flash('Delivery partner approved.', 'success')
        else:
            flash('Invalid delivery partner profile.', 'danger')
        return redirect(url_for('admin.dashboard'))
    flash('Invalid form submission.', 'danger')
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
    form = ServiceForm()
    form.category_ids.choices = [(c.id, c.name) for c in Category.query.all()]

    if form.validate_on_submit():
        filename = None
        if form.image_file.data:
            filename = secure_filename(form.image_file.data.filename)
            form.image_file.data.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        
        new_service = Service(name=form.name.data, image_url=filename)
        new_service.categories = Category.query.filter(Category.id.in_(form.category_ids.data)).all()
        db.session.add(new_service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('admin.services'))

    return render_template('admin/add_service.html', form=form)

@admin_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    """Edit an existing service's name and categories."""
    service = Service.query.get_or_404(service_id)
    form = ServiceForm(obj=service)
    form.category_ids.choices = [(c.id, c.name) for c in Category.query.all()]
    form.category_ids.data = [c.id for c in service.categories]

    if form.validate_on_submit():
        service.name = form.name.data
        service.categories = Category.query.filter(Category.id.in_(form.category_ids.data)).all()
        if form.image_file.data:
            old_filename = service.image_url
            filename = secure_filename(form.image_file.data.filename)
            form.image_file.data.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            service.image_url = filename
            if old_filename:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], old_filename))
                except OSError as e:
                    print(f"Error deleting old file: {e}")
        db.session.commit()
        flash('Service updated!', 'success')
        return redirect(url_for('admin.services'))

    return render_template('admin/edit_service.html', form=form, service=service)

@admin_bp.route('/services/<int:service_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_service(service_id):
    """Delete a service from the system."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        service = Service.query.get_or_404(service_id)
        if service.image_url:
            try:
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], service.image_url))
            except OSError as e:
                print(f"Error deleting file: {e}")
        db.session.delete(service)
        db.session.commit()
        flash('Service deleted.', 'success')
        return redirect(url_for('admin.services'))
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('admin.services'))

@admin_bp.route('/services/<int:service_id>/measurements', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service_measurements(service_id):
    """Manage standard measurements for a specific service."""
    service = Service.query.get_or_404(service_id)
    form = MeasurementSelectionForm()
    form.measurement_ids.choices = [(m.id, m.name) for m in MeasurementField.query.all()]
    form.measurement_ids.data = [m.id for m in service.standard_measurements]

    if form.validate_on_submit():
        service.standard_measurements = [
            MeasurementField.query.get(m_id) for m_id in form.measurement_ids.data if m_id
        ]
        db.session.commit()
        flash('Measurements updated for service.', 'success')
        return redirect(url_for('admin.services'))

    return render_template(
        'admin/manage_measurements.html',
        form=form,
        service=service,
        all_measurements=MeasurementField.query.all(),
        current_ids={m.id for m in service.standard_measurements}
    )

@admin_bp.route('/service/<int:service_id>/variations', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_service_variations(service_id):
    """Manage variations for a specific service."""
    service = Service.query.get_or_404(service_id)
    form = VariationForm()

    if form.validate_on_submit():
        filename = None
        if form.image_file.data:
            filename = secure_filename(form.image_file.data.filename)
            form.image_file.data.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        
        new_variation = ServiceVariation(name=form.name.data, service_id=service.id, image_url=filename)
        db.session.add(new_variation)
        db.session.commit()
        flash(f'Variation "{form.name.data}" added to {service.name}.', 'success')
        return redirect(url_for('admin.manage_service_variations', service_id=service.id))

    return render_template('admin/manage_variations.html', form=form, service=service)

@admin_bp.route('/variation/<int:variation_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_variation(variation_id):
    """Edit an existing service variation."""
    variation = ServiceVariation.query.get_or_404(variation_id)
    form = VariationForm(obj=variation)

    if form.validate_on_submit():
        variation.name = form.name.data
        if form.image_file.data:
            old_filename = variation.image_url
            filename = secure_filename(form.image_file.data.filename)
            form.image_file.data.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            variation.image_url = filename
            if old_filename:
                try:
                    os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], old_filename))
                except OSError as e:
                    print(f"Error deleting old file: {e}")
        db.session.commit()
        flash("Variation updated successfully.", "success")
        return redirect(url_for('admin.manage_service_variations', service_id=variation.service_id))

    return render_template('admin/edit_variation.html', form=form, variation=variation)

@admin_bp.route('/variation/<int:variation_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_variation(variation_id):
    """Delete a service variation."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        variation = ServiceVariation.query.get_or_404(variation_id)
        service_id = variation.service_id
        if variation.image_url:
            try:
                os.remove(os.path.join(current_app.config['UPLOAD_FOLDER'], variation.image_url))
            except OSError as e:
                print(f"Error deleting file: {e}")
        db.session.delete(variation)
        db.session.commit()
        flash("Variation deleted.", "success")
        return redirect(url_for('admin.manage_service_variations', service_id=service_id))
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('admin.services'))

@admin_bp.route('/measurements', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_measurements():
    """Manage master measurement fields."""
    form = MeasurementFieldForm()

    if form.validate_on_submit():
        new_field = MeasurementField(
            name=form.name.data,
            description=form.description.data,
            image_url=form.image_url.data
        )
        db.session.add(new_field)
        db.session.commit()
        flash(f'Measurement field "{form.name.data}" created successfully!', 'success')
        return redirect(url_for('admin.manage_measurements'))

    measurements = MeasurementField.query.all()
    return render_template('admin/manage_measurements.html', form=form, measurements=measurements)

@admin_bp.route('/measurement_fields/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_measurement_field():
    """Add a new measurement field."""
    form = MeasurementFieldForm()

    if form.validate_on_submit():
        new_field = MeasurementField(
            name=form.name.data,
            description=form.description.data,
            image_url=form.image_url.data
        )
        db.session.add(new_field)
        db.session.commit()
        flash('Measurement field added.', 'success')
        return redirect(url_for('admin.services'))

    return render_template('admin/add_measurement_field.html', form=form)

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

@admin_bp.route('/logistics')
@login_required
@admin_required
def logistics():
    """Display a list of all logistics tasks."""
    logistics = Logistic.query.all()
    return render_template('admin/logistics.html', logistics=logistics)

@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_categories():
    """Manage master categories for services."""
    form = CategoryForm()

    if form.validate_on_submit():
        if Category.query.filter_by(name=form.name.data).first():
            flash(f'Category "{form.name.data}" already exists.', 'danger')
        else:
            new_category = Category(name=form.name.data)
            db.session.add(new_category)
            db.session.commit()
            flash(f'Category "{form.name.data}" created successfully!', 'success')
        return redirect(url_for('admin.manage_categories'))

    all_categories = Category.query.all()
    return render_template('admin/manage_categories.html', form=form, categories=all_categories)

@admin_bp.route('/category/<int:category_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_category(category_id):
    """Delete a category from the system."""
    form = SimpleSubmitForm()
    if form.validate_on_submit():
        category = Category.query.get_or_404(category_id)
        db.session.delete(category)
        db.session.commit()
        flash(f'Category "{category.name}" has been deleted.', 'success')
        return redirect(url_for('admin.manage_categories'))
    flash('Invalid form submission.', 'danger')
    return redirect(url_for('admin.manage_categories'))

# app/admin/routes.py
import random # Make sure random is imported

@admin_bp.route('/qc-queue')
@login_required
@admin_required
def qc_queue():
    """Displays all orders waiting for Quality Check."""
    pending_qc_orders = Order.query.filter_by(order_status='pending_qc').all()
    return render_template('admin/qc_queue.html', orders=pending_qc_orders)


@admin_bp.route('/qc/pass/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def qc_pass(order_id):
    """Marks an order as QC passed and creates the final delivery task."""
    order = Order.query.get_or_404(order_id)
    order.order_status = 'ready_for_delivery'
    
    # This is the same logic from the old 'complete_order' route
    delivery_otp = str(random.randint(100000, 999999))
    new_task = Logistic(
        order_id=order.id,
        delivery_partner_id=None,
        task_type='pickup_from_tailor',
        status='assigned',
        pickup_otp=delivery_otp
    )
    db.session.add(new_task)
    db.session.commit()
    
    flash(f"Order #{order.id} passed QC. A delivery task has been created.", "success")
    return redirect(url_for('admin.qc_queue'))


@admin_bp.route('/qc/fail/<int:order_id>', methods=['POST'])
@login_required
@admin_required
def qc_fail(order_id):
    """Marks an order as QC failed and notifies the tailor."""
    order = Order.query.get_or_404(order_id)
    order.order_status = 'qc_failed'
    db.session.commit()
    
    # Create a notification for the tailor
    # create_notification(user_id=order.tailor_id, message=...)
    
    flash(f"Order #{order.id} failed QC. The tailor has been notified to rework.", "danger")
    return redirect(url_for('admin.qc_queue'))