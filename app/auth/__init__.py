# app/auth/__init__.py

from flask import Blueprint

# 1. Create a Blueprint object.
#    The first argument, 'auth', is the blueprint's name.
#    The second argument, __name__, tells the blueprint where it is defined.
auth_bp = Blueprint('auth', __name__)

# 2. Import the routes.
#    This import is at the bottom to avoid circular dependency issues,
#    as the routes.py file will in turn need to import the 'auth_bp' object defined above.

from . import routes