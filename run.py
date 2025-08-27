# run.py

import os
from app import create_app
from manage import seed_db, seed_users, seed_admin

# Create the Flask app instance using the app factory.
# This pattern allows for different configurations (e.g., development, testing, production).
# It will look for a FLASK_CONFIG environment variable, otherwise it will use 'default'.
app = create_app(os.getenv('FLASK_CONFIG') or 'default')
# Register the command with the app
app.cli.add_command(seed_db)
app.cli.add_command(seed_users)
app.cli.add_command(seed_admin)

if __name__ == '__main__':
    # The app.run() call is placed inside this conditional
    # to ensure it only runs when the script is executed directly.
    # debug=True enables auto-reloading and an in-browser debugger for development.
    app.run(debug=True)