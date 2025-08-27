# app/customer/__init__.py

from flask import Blueprint

# Creates the Blueprint for the customer portal.
# All routes defined in this blueprint will be prefixed with '/customer'
# when registered in the main app factory.
customer_bp = Blueprint('customer', __name__)

# Import the routes to link them with the blueprint.
# This is placed at the end to prevent circular dependencies.
from . import routes