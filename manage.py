import click
from flask.cli import with_appcontext
from app import db
from app.models import (Service, MeasurementField, User, UserProfile, 
                        Address, TailorProfile, DeliveryPartnerProfile,
                        ServiceVariation)

@click.command(name='seed_db')
@with_appcontext
def seed_db():
    """Seeds the database with a comprehensive list of master data."""
    print("Starting database seeding...")

    # New, more structured dictionary for master data
    master_data = {
        "Saree Blouse": {
            "category": "Womenswear",
            "measurements": [
                'Bust', 'Under Bust', 'Waist', 'Shoulder Width', 'Front Neck Depth', 'Back Neck Depth',
                'Blouse Length', 'Sleeve Length', 'Sleeve Round', 'Armhole', 'Shoulder to Bust Point', 'Bust Span'
            ],
            "variations": [
                {"name": "Princess Cut Blouse"}, {"name": "High Neck Blouse"},
                {"name": "Boat Neck Blouse"}, {"name": "Padded Blouse"}
            ]
        },
        "Jeans / Pants": {
            "category": "Unisex",
            "measurements": [
                'Waist', 'Hips', 'Thigh Round', 'Knee Round', 'Calf Round', 'Inseam Length',
                'Outseam Length', 'Crotch Depth', 'Bottom Round (Ankle)'
            ],
            "variations": [
                {"name": "Slim Fit"}, {"name": "Straight Leg"},
                {"name": "Bootcut"}, {"name": "Skinny Fit"}
            ]
        },
        "Shirt (Formal/Casual)": {
            "category": "Menswear",
            "measurements": [
                'Neck Round', 'Shoulder Width', 'Chest', 'Waist', 'Hip', 'Sleeve Length',
                'Bicep Round', 'Wrist Round', 'Shirt Length', 'Armhole'
            ],
            "variations": [
                {"name": "Formal Dress Shirt"}, {"name": "Casual Oxford Shirt"},
                {"name": "Linen Shirt"}, {"name": "Flannel Shirt"}
            ]
        },
        "Kurta": {
            "category": "Menswear",
            "measurements": [
                 'Shoulder Width', 'Chest', 'Waist', 'Hip', 'Sleeve Length', 'Kurta Length'
            ],
            "variations": [
                {"name": "Classic Long Kurta"}, {"name": "Short Kurta"},
                {"name": "Pathani Kurta"}
            ]
        },
        "Lehenga / Ghagra": {
            "category": "Womenswear",
            "measurements": [
                'Waist', 'Hip', 'Lehenga Length (Waist to Floor)'
            ],
            "variations": [
                {"name": "A-Line Lehenga"}, {"name": "Flared Lehenga"},
                {"name": "Mermaid Style Lehenga"}
            ]
        },
        "Salwar Kameez": {
            "category": "Womenswear",
            "measurements": [
                'Shoulder Width', 'Bust', 'Waist', 'Hip', 'Armhole', 'Sleeve Length',
                'Bicep', 'Wrist Round', 'Top Length', 'Front Neck Depth', 'Back Neck Depth',
                'Bottom Length'
            ],
            "variations": [
                {"name": "Anarkali Suit"}, {"name": "Patiala Suit"},
                {"name": "Straight Cut Suit"}
            ]
        },
        "Kids Frock": {
            "category": "Kidswear",
            "measurements": [
                'Chest', 'Waist', 'Shoulder Width', 'Frock Length'
            ],
            "variations": []
        },
        "Saree Fall & Pico": {
            "category": "Womenswear",
            "measurements": [],
            "variations": []
        }
    }

    # --- Step 1: Create all unique Measurement Fields ---
    print("Processing measurement fields...")
    all_measurement_names = set()
    for data in master_data.values():
        for name in data["measurements"]:
            all_measurement_names.add(name)
    
    for name in sorted(list(all_measurement_names)):
        if not MeasurementField.query.filter_by(name=name).first():
            db.session.add(MeasurementField(name=name))
    db.session.commit()

    # --- Step 2: Create Services, Variations, and Link Measurements ---
    print("Processing services and variations...")
    for service_name, data in master_data.items():
        # Create or find the master service
        service = Service.query.filter_by(name=service_name).first()
        if not service:
            service = Service(name=service_name, category=data["category"])
            db.session.add(service)
            db.session.commit()
        else:
            # Update category if it has changed
            service.category = data["category"]

        # Link standard measurements
        service.standard_measurements = []
        if data["measurements"]:
            measurements_to_link = MeasurementField.query.filter(MeasurementField.name.in_(data["measurements"])).all()
            service.standard_measurements = measurements_to_link

        # Create service variations
        for variation_data in data["variations"]:
            variation = ServiceVariation.query.filter_by(name=variation_data["name"], service_id=service.id).first()
            if not variation:
                variation = ServiceVariation(name=variation_data["name"], service=service)
                db.session.add(variation)

    db.session.commit()
    print("Database has been successfully seeded with categories and variations!")


# --- NEW FUNCTION TO SEED USERS ---
@click.command(name='seed_users')
@with_appcontext
def seed_users():
    """Seeds the database with sample users."""
    print("Deleting existing users and profiles...")
    
    # --- ADD THESE LINES TO CLEAR OLD PROFILES ---
    UserProfile.query.delete()
    TailorProfile.query.delete()
    DeliveryPartnerProfile.query.delete()
    Address.query.delete()
    # --- END OF ADDITIONS ---

    User.query.delete() # Clears out all users
    db.session.commit() # Commit the deletions

    print("Creating sample users...")
    
    # --- Create a Customer ---
    customer = User(email='customer@test.com', phone_number='1111111111', role='customer', is_verified=True)
    customer.set_password('password')
    # Create and assign the profiles
    customer.profile = UserProfile(first_name='Riya', last_name='Sharma', phone_number='1111111111')
    customer.addresses.append(Address(address_line1='123, Rose Villa', city='Bengaluru', state='Karnataka', postal_code='560001', is_default=True))
    db.session.add(customer)

    # --- Create a Tailor ---
    # --- Create a Tailor ---
    tailor = User(email='tailor@test.com', phone_number='2222222222', role='tailor', is_verified=True)
    tailor.set_password('password')
    tailor.profile = UserProfile(first_name='Ashok', last_name='Kumar', phone_number='2222222222')
    
    # --- THIS IS THE CORRECTED LINE ---
    tailor.tailor_profile = TailorProfile(
        business_name='Ashok Master Tailors', 
        bio='Expert in ethnic wear.',
        years_of_experience=15, 
        specializations='Womenswear, Blouses, Suits',
        is_verified=True
    )
    
    tailor.addresses.append(Address(address_line1='456, Silk Plaza', city='Bengaluru', state='Karnataka', postal_code='560029', is_default=True))
    db.session.add(tailor)

    # --- Create a Delivery Partner ---
    partner = User(email='partner@test.com', phone_number='3333333333', role='delivery_partner', is_verified=True)
    partner.set_password('password')
    
    # Create and assign the profiles
    partner.profile = UserProfile(first_name='Sanjay', last_name='Singh', phone_number='3333333333')
    
    # --- THIS IS THE KEY PART ---
    # Ensure the DeliveryPartnerProfile is created with is_approved=True
    partner.delivery_partner_profile = DeliveryPartnerProfile(
        vehicle_details='Honda Activa - KA01AB1234', 
        is_approved=True
    )
    partner.addresses.append(Address(address_line1='789, Connect Rd', city='Bengaluru', state='Karnataka', postal_code='560068'))
    # partner.addresses.append(Address(user=partner, address_line1='789, Connect Rd', city='Bengaluru', state='Karnataka', postal_code='560068'))
    db.session.add(partner)

    db.session.commit()
    print("Sample users created successfully!")
    print("- Customer: customer@test.com (password: password)")
    print("- Tailor: tailor@test.com (password: password)")
    print("- Delivery Partner: partner@test.com (password: password)")


@click.command(name='seed_admin')
@with_appcontext
def seed_admin():
    """Creates a default admin user."""
    
    admin_email = 'admin@admin.com'
    admin_phone = '9999999999'
    
    # Check if the admin user already exists
    if User.query.filter_by(email=admin_email).first():
        print(f"Admin user with email {admin_email} already exists.")
        return

    print("Creating admin user...")
    
    admin_user = User(
        email=admin_email,
        phone_number=admin_phone,
        role='admin',
        is_verified=True # Admins are auto-verified
    )
    admin_user.set_password('admin') # Change this in a real environment
    
    admin_user.profile = UserProfile(
        first_name='Admin',
        last_name='User',
        phone_number=admin_phone
    )
    
    db.session.add(admin_user)
    db.session.commit()
    
    print("Admin user created successfully!")
    print(f"- Email: {admin_email}")
    print("- Password: admin")