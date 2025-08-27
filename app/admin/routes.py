from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from functools import wraps
from .. import db
from ..models import Order, Service, MeasurementField, User, TailorProfile, DeliveryPartnerProfile, Logistic
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

@admin_bp.route('/services/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_service():
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category')
        new_service = Service(name=name, category=category)
        db.session.add(new_service)
        db.session.commit()
        flash('Service added successfully!', 'success')
        return redirect(url_for('admin.services'))
    return render_template('admin/add_service.html')

@admin_bp.route('/services/<int:service_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_service(service_id):
    service = Service.query.get_or_404(service_id)
    if request.method == 'POST':
        service.name = request.form.get('name')
        service.category = request.form.get('category')
        db.session.commit()
        flash('Service updated!', 'success')
        return redirect(url_for('admin.services'))
    return render_template('admin/edit_service.html', service=service)

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
    
    return render_template('admin/dashboard.html', 
                           pending_tailors=pending_tailors,
                           pending_partners=pending_partners,
                           total_orders=total_orders,
                           active_orders_count=active_orders_count)

# Note: The dedicated /pending routes are now handled by the dashboard, but you can keep them if you prefer.