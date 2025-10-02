# app/models.py

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import UserMixin
from sqlalchemy import ForeignKeyConstraint
import enum

# --- Enums ---
class AvailabilityStatus(enum.Enum):
    ONLINE = 'online'
    OFFLINE = 'offline'
    BUSY = 'busy'

class ServiceCategory(enum.Enum):
    WOMENSWEAR = "Womenswear"
    MENSWEAR = "Menswear"
    KIDSWEAR = "Kidswear"
    UNISEX = "Unisex"
    ALTERATIONS = "Alterations"

# --- User & Profile Models ---
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)  # 'customer', 'tailor', 'delivery_partner'
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship('UserProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    tailor_profile = db.relationship('TailorProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    delivery_partner_profile = db.relationship('DeliveryPartnerProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    addresses = db.relationship('Address', backref='user', lazy='dynamic', cascade="all, delete-orphan")
    orders_placed = db.relationship('Order', foreign_keys='Order.customer_id', backref='customer', lazy='dynamic')
    orders_assigned_to_tailor = db.relationship('Order', foreign_keys='Order.tailor_id', backref='tailor', lazy='dynamic')
    delivery_tasks = db.relationship('Logistic', foreign_keys='Logistic.delivery_partner_id', backref='delivery_partner', lazy='dynamic')
    ratings_given = db.relationship('Rating', foreign_keys='Rating.rating_by_user_id', backref='rating_user', lazy='dynamic')
    ratings_received = db.relationship('Rating', foreign_keys='Rating.rating_for_user_id', backref='rated_user', lazy='dynamic')
    sub_profiles = db.relationship('SubProfile', backref='user', lazy='dynamic')
    measurement_profiles = db.relationship('MeasurementProfile', backref='user', lazy='dynamic')
    cart = db.relationship('Cart', backref='user', uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email or self.phone_number}>'

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    phone_number = db.Column(db.String(20), unique=True)
    profile_picture_url = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<UserProfile for User ID {self.user_id}>'

class TailorProfile(db.Model):
    __tablename__ = 'tailor_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    business_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    years_of_experience = db.Column(db.Integer)
    specializations = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<TailorProfile for User ID {self.user_id}>'

class DeliveryPartnerProfile(db.Model):
    __tablename__ = 'delivery_partner_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    vehicle_details = db.Column(db.String(100), nullable=True)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    availability_status = db.Column(db.Enum(AvailabilityStatus), default=AvailabilityStatus.OFFLINE, nullable=False)
    current_location_lat = db.Column(db.Float, nullable=True)
    current_location_lon = db.Column(db.Float, nullable=True)
    location_last_updated = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<DeliveryPartnerProfile for User ID {self.user_id}>'

class SubProfile(db.Model):
    __tablename__ = 'sub_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    relationship = db.Column(db.String(50))
    gender = db.Column(db.String(20))
    age_group = db.Column(db.String(20))

    def __repr__(self):
        return f'<SubProfile {self.name} for User ID {self.user_id}>'

# --- Service and Measurement Master Tables ---
class MeasurementField(db.Model):
    __tablename__ = 'measurement_fields'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_optional = db.Column(db.Boolean, default=False)
    image_url = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<MeasurementField {self.name}>'

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return self.name

class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    standard_measurements = db.relationship('MeasurementField', secondary='standard_service_measurements')
    categories = db.relationship('Category', secondary='service_categories', lazy='subquery', backref=db.backref('services', lazy=True))
    variations = db.relationship('ServiceVariation', backref='service')

    def __repr__(self):
        return f'<Service {self.name}>'

# --- Linking Tables (Many-to-Many) ---
service_categories = db.Table('service_categories',
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id'), primary_key=True))

standard_service_measurements = db.Table('standard_service_measurements',
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True),
    db.Column('measurement_field_id', db.Integer, db.ForeignKey('measurement_fields.id'), primary_key=True))

tailor_service_measurements = db.Table('tailor_service_measurements',
    db.Column('tailor_service_id', db.Integer, db.ForeignKey('tailor_services.id'), primary_key=True),
    db.Column('measurement_field_id', db.Integer, db.ForeignKey('measurement_fields.id'), primary_key=True))

# --- Tailor Service Model ---
class TailorService(db.Model):
    __tablename__ = 'tailor_services'
    id = db.Column(db.Integer, primary_key=True)
    tailor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    price = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    estimated_days = db.Column(db.Integer, nullable=False, default=7)
    tailor_earning = db.Column(db.Float, nullable=True)

    tailor = db.relationship('User', backref='tailor_services')
    service = db.relationship('Service', backref='offered_by_tailors')
    custom_measurements = db.relationship('MeasurementField', secondary='tailor_service_measurements')

    def __repr__(self):
        return f'<TailorService {self.id} by Tailor {self.tailor_id}>'

# --- Order-Related Models ---
class Address(db.Model):
    __tablename__ = 'addresses'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    address_line1 = db.Column(db.String(255), nullable=False)
    address_line2 = db.Column(db.String(255))
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    postal_code = db.Column(db.String(20), nullable=False)
    is_default = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<Address {self.id} for User {self.user_id}>'

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, nullable=False)
    tailor_id = db.Column(db.Integer, nullable=True)
    delivery_address_id = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(50), nullable=True)
    payment_status = db.Column(db.String(50), nullable=False, default='pending')
    prepayment_amount = db.Column(db.Float, nullable=True)
    order_status = db.Column(db.String(50), nullable=False, default='pending_acceptance')
    total_amount = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    measurement_method = db.Column(db.String(50), nullable=False, server_default='online_submission')
    pickup_slot_start = db.Column(db.DateTime, nullable=True)
    pickup_slot_end = db.Column(db.DateTime, nullable=True)

    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan")
    logistics_tasks = db.relationship('Logistic', backref='order', lazy='dynamic', cascade="all, delete-orphan")
    notes = db.relationship('OrderNote', backref='order', cascade="all, delete-orphan")
    rating = db.relationship('Rating', backref='order', uselist=False, cascade="all, delete-orphan")
    # customer = db.relationship('User', foreign_keys=[customer_id])
    # tailor = db.relationship('User', foreign_keys=[tailor_id])
    delivery_address = db.relationship('Address', foreign_keys=[delivery_address_id])
    

    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['users.id'], name='fk_order_customer_id'),
        ForeignKeyConstraint(['tailor_id'], ['users.id'], name='fk_order_tailor_id'),
        ForeignKeyConstraint(['delivery_address_id'], ['addresses.id'], name='fk_order_delivery_address_id'),
    )

    def __repr__(self):
        return f'<Order {self.id} - Status: {self.order_status}>'

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    tailor_service_id = db.Column(db.Integer, db.ForeignKey('tailor_services.id'), nullable=False)

    tailor_service = db.relationship('TailorService')
    measurements = db.relationship('OrderMeasurementValue', backref='order_item', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<OrderItem {self.id} for Order {self.order_id}>'

class OrderMeasurementValue(db.Model):
    __tablename__ = 'order_measurement_values'
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False)
    measurement_field_id = db.Column(db.Integer, db.ForeignKey('measurement_fields.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

    measurement_field = db.relationship('MeasurementField')

    def __repr__(self):
        return f'<OrderMeasurementValue {self.id}>'

class MeasurementProfile(db.Model):
    __tablename__ = 'measurement_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    sub_profile_id = db.Column(db.Integer, db.ForeignKey('sub_profiles.id'), nullable=True)
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    profile_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    measurements = db.relationship('SavedMeasurementValue', backref='profile', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<MeasurementProfile {self.profile_name}>'

class SavedMeasurementValue(db.Model):
    __tablename__ = 'saved_measurement_values'
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('measurement_profiles.id'), nullable=False)
    measurement_field_id = db.Column(db.Integer, db.ForeignKey('measurement_fields.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

    measurement_field = db.relationship('MeasurementField')

    def __repr__(self):
        return f'<SavedMeasurementValue {self.id}>'

class Logistic(db.Model):
    __tablename__ = 'logistics'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='pending')
    delivery_partner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    delivery_fee = db.Column(db.Float, nullable=True, default=50.0)
    pickup_otp = db.Column(db.String(10), nullable=True)
    tailor_handover_otp = db.Column(db.String(10), nullable=True)
    delivery_otp = db.Column(db.String(10), nullable=True)
    scheduled_time = db.Column(db.DateTime)
    completed_time = db.Column(db.DateTime)

    def __repr__(self):
        return f'<Logistic {self.id} for Order {self.order_id} - Task: {self.task_type}>'

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, unique=True)
    rating_for_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    rating_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Rating {self.id} - Score: {self.score}>'

class ServiceVariation(db.Model):
    __tablename__ = 'service_variations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)

    def __repr__(self):
        return f'<ServiceVariation {self.name}>'

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Notification {self.id}>'

class OrderNote(db.Model):
    __tablename__ = 'order_notes'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<OrderNote {self.id}>'

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('CartItem', backref='cart', cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Cart {self.id}>'

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False)
    tailor_service_id = db.Column(db.Integer, db.ForeignKey('tailor_services.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)

    tailor_service = db.relationship('TailorService')

    def __repr__(self):
        return f'<CartItem {self.id}>'