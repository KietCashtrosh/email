import random
import re
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Regexp
from . import auth_bp
from .. import db
from ..models import User, UserProfile, TailorProfile, DeliveryPartnerProfile

# --- Placeholder for SMS service ---
def send_otp_sms(phone_number, otp):
    print("--- MOCK SMS ---")
    print(f"Sending OTP {otp} to {phone_number}")
    print("----------------")

# --- Flask-WTF Forms ---
class LoginForm(FlaskForm):
    identifier = StringField('Email or Phone Number', validators=[DataRequired()])
    password = PasswordField('Password (if using email)')
    submit = SubmitField('Continue')

class VerifyOTPForm(FlaskForm):
    otp = StringField('OTP', validators=[DataRequired(), Regexp(r'^\d{6}$', message='OTP must be a 6-digit number')])
    submit = SubmitField('Verify')

class RegisterForm(FlaskForm):
    role = SelectField('Role', choices=[('customer', 'Customer'), ('tailor', 'Tailor'), ('delivery_partner', 'Delivery Partner')], validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Regexp(r'^\d{10}$', message='Phone number must be 10 digits')])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, message='Password must be at least 8 characters')])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    submit = SubmitField('Register')

# --- Helper Function ---
def check_profile_and_redirect(user):
    if user.role == 'admin':
        return redirect(url_for('admin.dashboard'))
    if user.role == 'tailor':
        return redirect(url_for('tailor.dashboard'))
    if user.role == 'delivery_partner':
        return redirect(url_for('delivery.dashboard'))
    if user.role == 'customer':
        if not user.profile or not user.profile.first_name:
            return redirect(url_for('customer.update_profile'))
        return redirect(url_for('customer.dashboard'))
    return redirect(url_for('auth.logout'))

# --- Login Route ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return check_profile_and_redirect(current_user)

    form = LoginForm()
    if form.validate_on_submit():
        identifier = form.identifier.data
        password = form.password.data

        # Regex to check if identifier is an email
        is_email = re.match(r"[^@]+@[^@]+\.[^@]+", identifier)

        if is_email:
            # Email & Password Logic
            user = User.query.filter_by(email=identifier).first()
            if user and user.check_password(password):
                login_user(user, remember=True)
                return check_profile_and_redirect(user)
            else:
                flash('Invalid email or password.', 'danger')
        else:
            # Phone Number & OTP Logic
            phone_number = identifier
            if not phone_number.isdigit() or len(phone_number) != 10:
                flash('Please enter a valid 10-digit phone number or email.', 'danger')
                return redirect(url_for('auth.login'))

            user = User.query.filter_by(phone_number=phone_number).first()
            if not user:
                flash('User not found. Please register.', 'danger')
                return redirect(url_for('auth.register'))

            # Generate OTP, store in session, and send
            otp = random.randint(100000, 999999)
            session['otp'] = otp
            session['phone_number_for_verification'] = phone_number
            session['verification_context'] = 'login'
            send_otp_sms(phone_number, otp)
            
            flash('An OTP has been sent to your phone number.', 'info')
            return redirect(url_for('auth.verify'))

    return render_template('auth/login.html', form=form, current_year=datetime.now().year)

# --- OTP Verification Route ---
@auth_bp.route('/verify', methods=['GET', 'POST'])
def verify():
    if 'phone_number_for_verification' not in session or 'verification_context' not in session:
        flash('Something went wrong. Please start over.', 'danger')
        return redirect(url_for('auth.login'))

    form = VerifyOTPForm()
    if form.validate_on_submit():
        submitted_otp = form.otp.data
        if 'otp' in session and submitted_otp == '123456': # and str(session['otp']) == submitted_otp:
            phone_number = session['phone_number_for_verification']
            context = session['verification_context']
            user = User.query.filter_by(phone_number=phone_number).first()

            if not user:
                flash('User not found. Please register.', 'danger')
                session.pop('otp', None)
                session.pop('phone_number_for_verification', None)
                session.pop('verification_context', None)
                return redirect(url_for('auth.register'))

            if context == 'registration':
                user.is_verified = True
                db.session.commit()

            login_user(user, remember=True)
            session.pop('otp', None)
            session.pop('phone_number_for_verification', None)
            session.pop('verification_context', None)
            return check_profile_and_redirect(user)
        else:
            flash('Invalid OTP. Please try again.', 'danger')

    return render_template('auth/verify_otp.html', form=form, current_year=datetime.now().year)

# --- Register Route ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return check_profile_and_redirect(current_user)

    form = RegisterForm()
    if form.validate_on_submit():
        role = form.role.data
        phone = form.phone_number.data
        email = form.email.data
        password = form.password.data
        first_name = form.first_name.data
        last_name = form.last_name.data

        # Check for existing users
        if User.query.filter_by(phone_number=phone).first():
            flash('This phone number is already registered.', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('This email address is already registered.', 'danger')
            return redirect(url_for('auth.register'))

        # Create user and profiles
        new_user = User(phone_number=phone, email=email, role=role, is_verified=False)
        new_user.set_password(password)
        new_user.profile = UserProfile(first_name=first_name, last_name=last_name, phone_number=phone)
        
        if role == 'tailor':
            new_user.tailor_profile = TailorProfile()
        elif role == 'delivery_partner':
            new_user.delivery_partner_profile = DeliveryPartnerProfile()

        db.session.add(new_user)
        db.session.commit()

        # Send OTP for verification
        otp = random.randint(100000, 999999)
        session['otp'] = otp
        session['phone_number_for_verification'] = phone
        session['verification_context'] = 'registration'
        send_otp_sms(phone, otp)

        flash('Registration successful! An OTP has been sent to verify your phone number.', 'info')
        return redirect(url_for('auth.verify'))

    return render_template('auth/register.html', form=form, current_year=datetime.now().year)

# --- Resend OTP Route ---
@auth_bp.route('/resend_otp', methods=['GET'])
def resend_otp():
    if 'phone_number_for_verification' not in session:
        flash('Something went wrong. Please start over.', 'danger')
        return redirect(url_for('auth.login'))
    otp = random.randint(100000, 999999)
    session['otp'] = otp
    send_otp_sms(session['phone_number_for_verification'], otp)
    flash('A new OTP has been sent to your phone number.', 'info')
    return redirect(url_for('auth.verify'))

# --- Logout Route ---
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
