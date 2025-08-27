# app/auth/routes.py

import random
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from . import auth_bp
from .. import db
from ..models import User, UserProfile, TailorProfile, DeliveryPartnerProfile
import re

# --- Placeholder for SMS service ---
# You would replace this with a real implementation from Twilio, etc.
# --- (send_otp_sms function remains the same) ---


def send_otp_sms(phone_number, otp):
    print("--- MOCK SMS ---")
    print(f"Sending OTP {otp} to {phone_number}")
    print("----------------")


# --- NEW HELPER FUNCTION ---
def check_profile_and_redirect(user):
    """
    Checks if a user's profile is complete.
    Redirects to the update profile page if not, otherwise to the dashboard.
    """
    if user.role == 'admin':
        return redirect(url_for('admin.dashboard'))

    if user.role == 'tailor':
        return redirect(url_for('tailor.dashboard'))

    # --- NEW: Add the delivery partner case ---
    elif user.role == 'delivery_partner':
        # Assuming you will create a 'delivery_bp' blueprint for them
        return redirect(url_for('delivery.dashboard'))

    elif user.role == 'customer':
        # A profile is "incomplete" if the first_name is missing.
        if not user.profile or not user.profile.first_name:
            return redirect(url_for('customer.update_profile'))
        return redirect(url_for('customer.dashboard'))
    
    else:
        # Fallback
        return redirect(url_for('auth.logout'))



# --- MODIFIED: Unified Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        # Regex to check if the identifier is an email
        is_email = re.match(r"[^@]+@[^@]+\.[^@]+", identifier)

        if is_email:
            # --- Email & Password Logic ---
            user = User.query.filter_by(email=identifier).first()
            if user and user.check_password(password):
                login_user(user, remember=True)
                return check_profile_and_redirect(user)
            else:
                flash('Invalid email or password.', 'danger')
        else:
            # --- Phone Number & OTP Logic ---
            phone_number = identifier
            # Minimal validation for phone number
            if not phone_number or not phone_number.isdigit():
                flash('Please enter a valid phone number or email.', 'danger')
                return redirect(url_for('auth.login'))

            # Generate OTP, store it in the session, and send it
            otp = random.randint(100000, 999999)
            session['otp'] = otp
            session['phone_number_for_verification'] = phone_number
            session['verification_context'] = 'login'
            send_otp_sms(phone_number, otp)
            
            flash('An OTP has been sent to your phone number.', 'info')
            return redirect(url_for('auth.verify'))

    return render_template('auth/login.html')


# --- MODIFIED: OTP Verification with Implicit Registration ---
@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    # Check if we have the necessary info in the session
    if 'phone_number_for_verification' not in session or 'verification_context' not in session:
        flash('Something went wrong. Please start over.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        submitted_otp = request.form.get('otp')
        if 'otp' in session and str(session['otp']) == submitted_otp:
            phone_number = session['phone_number_for_verification']
            context = session['verification_context']

            user = User.query.filter_by(phone_number=phone_number).first()

            # Logic for new registration
            if context == 'registration':
                if not user: # This should always be true for registration
                     # Create new user
                    user = User(phone_number=phone_number, role='customer', is_verified=True)
                    # Create a blank profile
                    profile = UserProfile(user=user, phone_number=phone_number)
                    db.session.add(user)
                    db.session.add(profile)
                    db.session.commit()
                    flash('Your account has been created and verified!', 'success')
                else: # This is an edge case, but good to handle
                    user.is_verified = True
                    db.session.commit()

            # This handles both login and the final step of registration
            if not user:
                flash('User not found. Please register.', 'danger')
                return redirect(url_for('auth.register'))

            login_user(user, remember=True)

            # Clean up session
            session.pop('otp', None)
            session.pop('phone_number_for_verification', None)
            session.pop('verification_context', None)

            return check_profile_and_redirect(user)
        else:
            flash('Invalid OTP. Please try again.', 'danger')

    # For the GET request, just render the template
    return render_template('auth/verify_otp.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('customer.dashboard'))

    if request.method == 'POST':
        role = request.form.get('role')
        if role not in ['customer', 'tailor', 'delivery_partner']:
            flash('Please select a valid role.', 'danger')
            return redirect(url_for('auth.register'))
        
        phone = request.form.get('phone_number')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')

        # Check for existing users
        if User.query.filter_by(phone_number=phone).first():
            flash('This phone number is already registered.', 'danger')
            return redirect(url_for('auth.register'))
        if email and User.query.filter_by(email=email).first():
            flash('This email address is already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # --- THIS IS THE CORRECTED LOGIC ---

        # 1. Create the User object
        new_user = User(
            phone_number=phone, 
            email=email,
            role=role,
            is_verified=False
        )
        new_user.set_password(password)
        
        # 2. Create the associated profiles
        new_user.profile = UserProfile(
            first_name=first_name, 
            last_name=last_name, 
            phone_number=phone
        )
        
        if role == 'tailor':
            new_user.tailor_profile = TailorProfile()
        elif role == 'delivery_partner':
            new_user.delivery_partner_profile = DeliveryPartnerProfile()

        # 3. Add the parent User object to the session.
        #    SQLAlchemy will handle saving the associated profiles automatically due to the 'cascade' option.
        db.session.add(new_user)
        db.session.commit()
        
        # --- END OF CORRECTION ---

        # Send OTP for verification
        otp = random.randint(100000, 999999)
        session['otp'] = otp
        session['phone_number_for_verification'] = phone
        session['verification_context'] = 'registration'
        send_otp_sms(phone, otp)

        flash('Registration successful! An OTP has been sent to verify your phone number.', 'info')
        return redirect(url_for('auth.verify'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))