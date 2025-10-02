from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, FloatField, IntegerField, SelectField, TextAreaField, SelectMultipleField, FileField, HiddenField, RadioField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, NumberRange, Regexp

# Authentication Forms
class LoginForm(FlaskForm):
    """Form for user login."""
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=128)])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    role = SelectField('Role', choices=[('customer', 'Customer'), ('tailor', 'Tailor'), ('delivery_partner', 'Delivery Partner')], validators=[DataRequired()])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Regexp(r'^\d{10}$', message='Phone number must be 10 digits')])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8, message='Password must be at least 8 characters')])
    first_name = StringField('First Name', validators=[DataRequired()])
    last_name = StringField('Last Name', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_email(self, email):
        """Ensure email is unique (validation handled in route)."""
        pass

class VerifyOTPForm(FlaskForm):
    otp = StringField('OTP', validators=[DataRequired(), Regexp(r'^\d{6}$', message='OTP must be a 6-digit number')])
    submit = SubmitField('Verify')

# Customer-related Forms
class CustomerProfileForm(FlaskForm):
    """Form for updating customer profile."""
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    phone_number = StringField('Phone Number', validators=[DataRequired(), Length(min=10, max=15), Regexp(r'^\+?\d+$', message='Invalid phone number')])
    submit = SubmitField('Update Profile')

class SubProfileForm(FlaskForm):
    """Form for creating/editing customer sub-profiles (e.g., family members)."""
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    relationship = StringField('Relationship', validators=[DataRequired(), Length(max=50)])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], validators=[DataRequired()])
    age_group = SelectField('Age Group', choices=[('child', 'Child'), ('teen', 'Teen'), ('adult', 'Adult'), ('senior', 'Senior')], validators=[DataRequired()])
    submit = SubmitField('Save Sub-Profile')

class AddressForm(FlaskForm):
    """Form for adding/editing customer or tailor addresses."""
    address_line1 = StringField('Address Line 1', validators=[DataRequired(), Length(max=255)])
    city = StringField('City', validators=[DataRequired(), Length(max=100)])
    state = StringField('State', validators=[DataRequired(), Length(max=100)])
    postal_code = StringField('Postal Code', validators=[DataRequired(), Length(min=5, max=10)])
    is_default = BooleanField('Set as Default Address')
    submit = SubmitField('Save Address')

class OrderForm(FlaskForm):
    """Form for placing a new order."""
    # measurement_method = SelectField('Measurement Method', choices=[('online_submission', 'Online Submission'), ('home_visit', 'Home Visit')], validators=[DataRequired()])
    # # payment_method = SelectField('Payment Method', choices=[('cash_on_delivery', 'Cash on Delivery'), ('online_advance', 'Online Advance'), ('online_full', 'Online Full')], validators=[DataRequired()])
    # delivery_address_id = SelectField('Delivery Address', coerce=int, validators=[DataRequired()])
    delivery_address_id = RadioField('Delivery Address', coerce=int, validators=[DataRequired()])
    
    # CHANGE this from SelectField to RadioField
    measurement_method = RadioField('Measurement Method', 
                                    choices=[('online_submission', 'Enter/Review Measurements Online'), 
                                             ('home_visit', 'Request a Home Visit')], 
                                    validators=[DataRequired()])
    submit = SubmitField('Place Order')

class MeasurementForm(FlaskForm):
    """Dynamic form for submitting measurements (used in orders or saved profiles)."""
    submit = SubmitField('Submit Measurements')

    def __init__(self, measurement_fields, *args, **kwargs):
        super(MeasurementForm, self).__init__(*args, **kwargs)
        for field in measurement_fields:
            setattr(self, f'measurement_{field.id}', FloatField(field.name, validators=[DataRequired(), NumberRange(min=0, message='Measurement must be positive')]))

class SaveMeasurementForm(FlaskForm):
    """Form for saving measurements to a profile."""
    sub_profile_id = SelectField('Sub-Profile', coerce=int, validators=[DataRequired()])
    profile_name = StringField('Profile Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Measurements')

class RatingForm(FlaskForm):
    """Form for rating an order."""
    score = SelectField('Rating', coerce=int, choices=[(i, f'{i} Star{"s" if i != 1 else ""}') for i in range(1, 6)], validators=[DataRequired()])
    comment = TextAreaField('Comment', validators=[Length(max=500)])
    submit = SubmitField('Submit Rating')

# Tailor-related Forms
class TailorProfileForm(FlaskForm):
    """Form for updating tailor profile."""
    business_name = StringField('Business Name', validators=[DataRequired(), Length(max=100)])
    bio = TextAreaField('Bio', validators=[Length(max=500)])
    years_of_experience = IntegerField('Years of Experience', validators=[DataRequired(), NumberRange(min=0, max=100)])
    specializations = StringField('Specializations', validators=[Length(max=255)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    first_name = StringField('First Name', validators=[DataRequired(), Length(max=50)])
    last_name = StringField('Last Name', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Update Profile')

class TailorServiceForm(FlaskForm):
    """Form for adding/editing tailor services."""
    service_id = SelectField('Service', coerce=int, validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    estimated_days = IntegerField('Estimated Days', validators=[DataRequired(), NumberRange(min=1)])
    measurement_field_ids = SelectMultipleField('Custom Measurements', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save Service')

class MeasurementSelectionForm(FlaskForm):
    """Form for selecting measurement fields for a service."""
    measurement_ids = SelectMultipleField('Measurements', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Save Measurements')

# Delivery-related Forms
class OTPVerificationForm(FlaskForm):
    """Form for verifying OTP during logistics tasks."""
    otp = StringField('6-Digit OTP', validators=[DataRequired(), Regexp(r'^\d{6}$', message='OTP must be 6 digits')])
    submit = SubmitField('Verify OTP')

class DeliveryMeasurementForm(FlaskForm):
    """Form for delivery partner to submit measurements during home visits."""
    submit = SubmitField('Submit Measurements and OTP')

    def __init__(self, measurement_fields, *args, **kwargs):
        super(DeliveryMeasurementForm, self).__init__(*args, **kwargs)
        for field in measurement_fields:
            setattr(self, f'measurement_{field.id}', FloatField(field.name, validators=[DataRequired(), NumberRange(min=0, message='Measurement must be positive')]))
        self.otp = StringField('6-Digit OTP', validators=[DataRequired(), Regexp(r'^\d{6}$', message='OTP must be 6 digits')])

# Admin-related Forms
class SimpleSubmitForm(FlaskForm):
    """Generic form for simple POST actions (e.g., approve, delete)."""
    submit = SubmitField('Submit')

class ServiceForm(FlaskForm):
    """Form for admin to add/edit services."""
    name = StringField('Service Name', validators=[DataRequired(), Length(max=100)])
    category_ids = SelectMultipleField('Categories', coerce=int, validators=[DataRequired()])
    image_file = FileField('Service Image')
    submit = SubmitField('Save Service')

class CategoryForm(FlaskForm):
    """Form for admin to add/edit categories."""
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Save Category')

class MeasurementFieldForm(FlaskForm):
    """Form for admin to add/edit measurement fields."""
    name = StringField('Measurement Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Length(max=500)])
    image_url = StringField('Image URL', validators=[Length(max=255)])
    submit = SubmitField('Save Measurement')

class VariationForm(FlaskForm):
    """Form for admin to add/edit service variations."""
    name = StringField('Variation Name', validators=[DataRequired(), Length(max=100)])
    image_file = FileField('Variation Image')
    submit = SubmitField('Save Variation')

class AddToCartForm(FlaskForm):
    csrf_token = HiddenField()  # this is auto-populated by Flask-WTF
    tailor_service_id = HiddenField("Service ID", validators=[DataRequired()])

class PaymentForm(FlaskForm):
    """Form for selecting a payment option."""
    payment_option = RadioField(
        'Payment Method', 
        choices=[
            ('cod', 'Pay on Delivery / Visit'),
            ('advance', 'Pay 40% Advance Now'),
            ('full', 'Pay Full Amount Now')
        ],
        default='cod',
        validators=[DataRequired()]
    )
    submit = SubmitField('Pay & Confirm Order')