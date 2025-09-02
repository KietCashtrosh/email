# # app/models.py

# from datetime import datetime
# from werkzeug.security import generate_password_hash, check_password_hash
# from . import db # Import the db instance from your app package
# from flask_login import UserMixin # Import UserMixin


# class User(UserMixin, db.Model):
#     __tablename__ = 'users'
#     id = db.Column(db.Integer, primary_key=True)
#     email = db.Column(db.String(120), unique=True, nullable=True, index=True)
#     password_hash = db.Column(db.String(128))
#     role = db.Column(db.String(20), nullable=False)  # 'customer', 'tailor', 'delivery_partner'
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#     phone_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
#     is_verified = db.Column(db.Boolean, default=False, nullable=False)
#     password_hash = db.Column(db.String(128))
#     # --- Relationships ---
#     # One-to-One relationships
#     profile = db.relationship('UserProfile', backref='user', uselist=False, cascade="all, delete-orphan")
#     tailor_profile = db.relationship('TailorProfile', backref='user', uselist=False, cascade="all, delete-orphan")
#     delivery_partner_profile = db.relationship('DeliveryPartnerProfile', backref='user', uselist=False, cascade="all, delete-orphan")
    
#     # One-to-Many relationships
#     addresses = db.relationship('Address', backref='user', lazy='dynamic', cascade="all, delete-orphan")

#     # Relationships to Orders table where user can be customer, tailor, or delivery partner
#     orders_placed = db.relationship('Order', foreign_keys='Order.customer_id', backref='customer', lazy='dynamic')
#     orders_assigned_to_tailor = db.relationship('Order', foreign_keys='Order.tailor_id', backref='tailor', lazy='dynamic')
#     delivery_tasks = db.relationship('Logistic', foreign_keys='Logistic.delivery_partner_id', backref='delivery_partner', lazy='dynamic')

#     # Relationships to Ratings
#     ratings_given = db.relationship('Rating', foreign_keys='Rating.rating_by_user_id', backref='rating_user', lazy='dynamic')
#     ratings_received = db.relationship('Rating', foreign_keys='Rating.rating_for_user_id', backref='rated_user', lazy='dynamic')

#     def set_password(self, password):
#         self.password_hash = generate_password_hash(password)

#     def check_password(self, password):
#         return check_password_hash(self.password_hash, password)

#     def __repr__(self):
#         return f'<User {self.email} (Role: {self.role})>'


# class UserProfile(db.Model):
#     __tablename__ = 'user_profiles'
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
#     first_name = db.Column(db.String(50), nullable=True) # Allow NULL
#     last_name = db.Column(db.String(50), nullable=True)  # Allow NULL
#     phone_number = db.Column(db.String(20), unique=True)
#     profile_picture_url = db.Column(db.String(255))
#     updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

#     def __repr__(self):
#         return f'<UserProfile for User ID {self.user_id}>'


# class Address(db.Model):
#     __tablename__ = 'addresses'
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
#     address_line1 = db.Column(db.String(255), nullable=False)
#     address_line2 = db.Column(db.String(255))
#     city = db.Column(db.String(100), nullable=False)
#     state = db.Column(db.String(100), nullable=False)
#     postal_code = db.Column(db.String(20), nullable=False)
#     is_default = db.Column(db.Boolean, default=False)

#     def __repr__(self):
#         return f'<Address {self.id} for User {self.user_id}>'


# class TailorProfile(db.Model):
#     __tablename__ = 'tailor_profiles'
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
#     business_name = db.Column(db.String(100))
#     bio = db.Column(db.Text)
#     years_of_experience = db.Column(db.Integer)
#     specializations = db.Column(db.Text)
#     is_verified = db.Column(db.Boolean, default=False)

#     def __repr__(self):
#         return f'<TailorProfile for User ID {self.user_id}>'


# class DeliveryPartnerProfile(db.Model):
#     __tablename__ = 'delivery_partner_profiles'
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
#     vehicle_details = db.Column(db.String(100))
#     current_location_lat = db.Column(db.Float)
#     current_location_lon = db.Column(db.Float)
#     # availability_status = db.Column(db.String(20), default='offline') # 'online', 'offline', 'busy'
#     availability_status = db.Column(db.Enum(AvailabilityStatus), default=AvailabilityStatus.OFFLINE, nullable=False)
#     def __repr__(self):
#         return f'<DeliveryPartnerProfile for User ID {self.user_id}>'


# class Fabric(db.Model):
#     __tablename__ = 'fabrics'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), nullable=False)
#     description = db.Column(db.Text)
#     price_per_unit = db.Column(db.Float, nullable=False)
#     image_url = db.Column(db.String(255))
#     stock_quantity = db.Column(db.Float, nullable=False)
#     is_active = db.Column(db.Boolean, default=True)

#     def __repr__(self):
#         return f'<Fabric {self.name}>'

# # 2. Master list of all service types
# class Service(db.Model):
#     __tablename__ = 'services'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), unique=True, nullable=False) # e.g., "Blouse Stitching"
#     description = db.Column(db.Text, nullable=True)
#     category = db.Column(db.String(50), nullable=True)
#     image_url = db.Column(db.String(255), nullable=True)

#     # Relationship to get the standard measurements for this service
#     standard_measurements = db.relationship('MeasurementField', secondary='standard_service_measurements')

#     def __repr__(self):
#         return f'<Service {self.name}>'


# class Order(db.Model):
#     __tablename__ = 'orders'
#     id = db.Column(db.Integer, primary_key=True)
#     customer_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
#     tailor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
#     delivery_address_id = db.Column(db.Integer, db.ForeignKey('addresses.id', ondelete='CASCADE'), nullable=False)
#     order_status = db.Column(db.String(50), nullable=False, default='pending_acceptance')
#     fabric_source = db.Column(db.String(50), nullable=False) # 'customer_provided', 'store_purchased'
#     total_amount = db.Column(db.Float)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)
#     updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

#     items = db.relationship('OrderItem', backref='order', lazy='dynamic', cascade="all, delete-orphan")
#     logistics_tasks = db.relationship('Logistic', backref='order', lazy='dynamic', cascade="all, delete-orphan")
#     rating = db.relationship('Rating', backref='order', uselist=False, cascade="all, delete-orphan")

#     def __repr__(self):
#         return f'<Order {self.id} - Status: {self.order_status}>'


# class OrderItem(db.Model):
#     __tablename__ = 'order_items'
#     id = db.Column(db.Integer, primary_key=True)
#     order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
#     service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
#     fabric_id = db.Column(db.Integer, db.ForeignKey('fabrics.id'), nullable=True)
#     measurements = db.Column(db.Text)  # JSON stored as string
#     quantity = db.Column(db.Integer, default=1)
#     price = db.Column(db.Float, nullable=False)
#     tailor_service_id = db.Column(db.Integer, db.ForeignKey('tailor_services.id'), nullable=False)
#     order = db.relationship('Order', backref=db.backref('items', cascade="all, delete-orphan"))
#     tailor_service = db.relationship('TailorService')

#     service = db.relationship('Service', backref='order_items')
#     fabric = db.relationship('Fabric', backref='order_items')
    
#     def __repr__(self):
#         return f'<OrderItem {self.id} for Order {self.order_id}>'


# class Logistic(db.Model):
#     __tablename__ = 'logistics'
#     id = db.Column(db.Integer, primary_key=True)
#     order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
#     delivery_partner_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
#     task_type = db.Column(db.String(50), nullable=False) # 'pickup_from_customer', 'drop_to_tailor', etc.
#     status = db.Column(db.String(50), nullable=False, default='pending')
#     scheduled_time = db.Column(db.DateTime)
#     completed_time = db.Column(db.DateTime)

#     def __repr__(self):
#         return f'<Logistic {self.id} for Order {self.order_id} - Task: {self.task_type}>'


# class Rating(db.Model):
#     __tablename__ = 'ratings'
#     id = db.Column(db.Integer, primary_key=True)
#     order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, unique=True)
#     rating_for_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
#     rating_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
#     score = db.Column(db.Integer, nullable=False)
#     comment = db.Column(db.Text)
#     created_at = db.Column(db.DateTime, default=datetime.utcnow)

#     def __repr__(self):
#         return f'<Rating {self.id} - Score: {self.score}>'


# # Add this class later to your app/models.py
# class SubProfile(db.Model):
#     __tablename__ = 'sub_profiles'
#     id = db.Column(db.Integer, primary_key=True)
#     user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # The main account holder
#     name = db.Column(db.String(100), nullable=False) # e.g., "Rohan", "Priya"
#     relationship = db.Column(db.String(50)) # e.g., "Son", "Wife"
#     # You can add fields for measurements here later



# # --- NEW AND REFINED MODELS ---

# # 1. Master list of all possible measurement types we can collect
# class MeasurementField(db.Model):
#     __tablename__ = 'measurement_fields'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), unique=True, nullable=False) # e.g., "Bust / Chest"
#     description = db.Column(db.Text, nullable=True) # e.g., "The fullest part of the chest."
#     is_optional = db.Column(db.Boolean, default=False) # Is this a 'standard' or 'optional' measurement?

#     def __repr__(self):
#         return f'<MeasurementField {self.name}>'



# # 3. LINKING TABLE: Defines the STANDARD/DEFAULT measurements for a master service
# standard_service_measurements = db.Table('standard_service_measurements',
#     db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True),
#     db.Column('measurement_field_id', db.Integer, db.ForeignKey('measurement_fields.id'), primary_key=True)
# )

# # 4. Links a specific tailor to a master service with their own price
# class TailorService(db.Model):
#     __tablename__ = 'tailor_services'
#     id = db.Column(db.Integer, primary_key=True)
#     tailor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
#     service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
#     price = db.Column(db.Float, nullable=False)
#     is_active = db.Column(db.Boolean, default=True)
    
#     tailor = db.relationship('User', backref='tailor_services')
#     service = db.relationship('Service', backref='offered_by_tailors')
    
#     # Relationship to get the custom measurements this tailor requires
#     custom_measurements = db.relationship('MeasurementField', secondary='tailor_service_measurements')

#     def __repr__(self):
#         return f'<TailorService {self.id} by Tailor {self.tailor_id} for Service {self.service_id}>'


# # 5. LINKING TABLE: Defines the CUSTOM measurement overrides for a specific tailor's service
# tailor_service_measurements = db.Table('tailor_service_measurements',
#     db.Column('tailor_service_id', db.Integer, db.ForeignKey('tailor_services.id'), primary_key=True),
#     db.Column('measurement_field_id', db.Integer, db.ForeignKey('measurement_fields.id'), primary_key=True)
# )


# # 6. NEW TABLE: Stores the actual measurement VALUES for a specific order item
# class OrderMeasurementValue(db.Model):
#     __tablename__ = 'order_measurement_values'
#     id = db.Column(db.Integer, primary_key=True)
#     order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False)
#     measurement_field_id = db.Column(db.Integer, db.ForeignKey('measurement_fields.id'), nullable=False)
#     value = db.Column(db.Float, nullable=False)

#     order_item = db.relationship('OrderItem', backref=db.backref('measurements', cascade="all, delete-orphan"))
#     measurement_field = db.relationship('MeasurementField')


# app/models.py

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from . import db
from flask_login import UserMixin
from sqlalchemy import ForeignKeyConstraint # Add this to your imports

import enum

# Define an Enum class for the statuses
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
    # Add other relationships as needed...

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email or self.phone_number}>'

class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    first_name = db.Column(db.String(50), nullable=True) # Allow NULL
    last_name = db.Column(db.String(50), nullable=True)  # Allow NULL
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

# --- Service and Measurement Master Tables ---

class MeasurementField(db.Model):
    __tablename__ = 'measurement_fields'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_optional = db.Column(db.Boolean, default=False)
    image_url = db.Column(db.String(255), nullable=True) # URL to an illustrative image

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False) # e.g., "Womenswear"

    def __repr__(self):
        return self.name


# --- NEW: The linking table for the many-to-many relationship ---
# --- CORRECT: The linking table is defined here, in the main scope ---
service_categories = db.Table('service_categories',
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id'), primary_key=True)
)
    
class Service(db.Model):
    __tablename__ = 'services'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    standard_measurements = db.relationship('MeasurementField', secondary='standard_service_measurements')
    categories = db.relationship('Category', secondary=service_categories,
                                 lazy='subquery', backref=db.backref('services', lazy=True))

# --- Linking Tables (Many-to-Many) ---
standard_service_measurements = db.Table('standard_service_measurements',
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True),
    db.Column('measurement_field_id', db.Integer, db.ForeignKey('measurement_fields.id'), primary_key=True))
    
    


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

    tailor_service_measurements = db.Table('tailor_service_measurements',
    db.Column('tailor_service_id', db.Integer, db.ForeignKey('tailor_services.id'), primary_key=True),
    db.Column('measurement_field_id', db.Integer, db.ForeignKey('measurement_fields.id'), primary_key=True)
)

# --- Order-Related Models ---
class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, nullable=False)
    tailor_id = db.Column(db.Integer, nullable=True)
    delivery_address_id = db.Column(db.Integer, nullable=False)

    payment_method = db.Column(db.String(50), nullable=True) # e.g., 'online_advance', 'cod'
    payment_status = db.Column(db.String(50), nullable=False, default='pending') # pending, partially_paid, fully_paid
    prepayment_amount = db.Column(db.Float, nullable=True) # To store the 30% advance

    order_status = db.Column(db.String(50), nullable=False, default='pending_acceptance')
    total_amount = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan")
    customer = db.relationship('User', foreign_keys=[customer_id])
    tailor = db.relationship('User', foreign_keys=[tailor_id])
    delivery_address = db.relationship('Address', foreign_keys=[delivery_address_id])

    measurement_method = db.Column(db.String(50),
                                   nullable=False,
                                   server_default='online_submission') # Use server_default
    
    pickup_slot_start = db.Column(db.DateTime, nullable=True)
    pickup_slot_end = db.Column(db.DateTime, nullable=True)

    # --- ADD THIS __table_args__ BLOCK ---
    __table_args__ = (
        ForeignKeyConstraint(['customer_id'], ['users.id'], name='fk_order_customer_id'),
        ForeignKeyConstraint(['tailor_id'], ['users.id'], name='fk_order_tailor_id'),
        ForeignKeyConstraint(['delivery_address_id'], ['addresses.id'], name='fk_order_delivery_address_id'),
    )


# You will also need to re-add the Address model if it was removed
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
    user = db.relationship('User', backref='addresses')

    def __repr__(self):
        return f'<Address {self.id} for User {self.user_id}>'
 

class OrderItem(db.Model):
    __tablename__ = 'order_items'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    tailor_service_id = db.Column(db.Integer, db.ForeignKey('tailor_services.id'), nullable=False)
    
    # This is correct: links to the tailor's specific offering
    tailor_service = db.relationship('TailorService')
    # This relationship will hold the actual measurement values
    measurements = db.relationship('OrderMeasurementValue', backref='order_item', cascade="all, delete-orphan")
    
    # Note: The old 'service_id' and 'measurements' text field have been removed.


class OrderMeasurementValue(db.Model):
    __tablename__ = 'order_measurement_values'
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('order_items.id'), nullable=False)
    measurement_field_id = db.Column(db.Integer, db.ForeignKey('measurement_fields.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)
    
    measurement_field = db.relationship('MeasurementField')


class DeliveryPartnerProfile(db.Model):
    __tablename__ = 'delivery_partner_profiles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    
    # Details for admin verification
    vehicle_details = db.Column(db.String(100), nullable=True)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)

    # Live status and location data
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
    name = db.Column(db.String(100), nullable=False) # e.g., "Rohan", "Priya"
    relationship = db.Column(db.String(50)) # e.g., "Son", "Wife"
    gender = db.Column(db.String(20)) # 'male', 'female', 'unisex'
    age_group = db.Column(db.String(20)) # 'adult', 'kid'
    
    user = db.relationship('User', backref='sub_profiles')


class MeasurementProfile(db.Model):
    __tablename__ = 'measurement_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # Direct link to the main user
    sub_profile_id = db.Column(db.Integer, db.ForeignKey('sub_profiles.id'), nullable=True) # Optional link to a family member
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    profile_name = db.Column(db.String(100), nullable=False) # e.g., "Rahul's School Uniform Shirt"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='measurement_profiles')
    sub_profile = db.relationship('SubProfile', backref='measurement_profiles')
    service = db.relationship('Service')
    
# You'll also need a table for the saved values, similar to OrderMeasurementValue
class SavedMeasurementValue(db.Model):
    __tablename__ = 'saved_measurement_values'
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('measurement_profiles.id'), nullable=False)
    measurement_field_id = db.Column(db.Integer, db.ForeignKey('measurement_fields.id'), nullable=False)
    value = db.Column(db.Float, nullable=False)

    profile = db.relationship('MeasurementProfile', backref=db.backref('measurements', cascade="all, delete-orphan"))
    measurement_field = db.relationship('MeasurementField')

class Logistic(db.Model):
    __tablename__ = 'logistics'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False)
    task_type = db.Column(db.String(50), nullable=False) # 'pickup_from_customer', 'drop_to_tailor', etc.
    status = db.Column(db.String(50), nullable=False, default='pending')
    delivery_partner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    delivery_fee = db.Column(db.Float, nullable=True, default=50.0) 
    pickup_otp = db.Column(db.String(10), nullable=True)
    tailor_handover_otp = db.Column(db.String(10), nullable=True)
    delivery_otp = db.Column(db.String(10), nullable=True)
    scheduled_time = db.Column(db.DateTime)
    completed_time = db.Column(db.DateTime)
    order = db.relationship('Order', backref='logistics_tasks')
    delivery_partner = db.relationship('User', foreign_keys=[delivery_partner_id])

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
    name = db.Column(db.String(100), nullable=False) # e.g., "Slim Fit Jeans"
    description = db.Column(db.Text)
    image_url = db.Column(db.String(255))
    # Link back to the parent service
    service_id = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    
    service = db.relationship('Service', backref='variations')

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Null for broadcast messages
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    link = db.Column(db.String(255), nullable=True) # URL the notification links to

class OrderNote(db.Model):
    __tablename__ = 'order_notes'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # Who wrote the note
    note = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order = db.relationship('Order', backref='notes')
    author = db.relationship('User')

# app/models.py

class Cart(db.Model):
    __tablename__ = 'carts'
    id = db.Column(db.Integer, primary_key=True)
    # A cart belongs to one user
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='cart', uselist=False)
    items = db.relationship('CartItem', backref='cart', cascade="all, delete-orphan")

class CartItem(db.Model):
    __tablename__ = 'cart_items'
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False)
    # A cart item points to a specific tailor's service offering
    tailor_service_id = db.Column(db.Integer, db.ForeignKey('tailor_services.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    
    # We will store the selected variations and measurements here later
    
    tailor_service = db.relationship('TailorService')