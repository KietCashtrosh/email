1	Customer Places Order	pending_tailor_acceptance	pending / partially_paid
2	Tailor Accepts	awaiting_pickup	(no change)
3	Partner Dispatched	pickup_in_progress	(no change)
4	Partner Collects Fabric	fabric_collected	(no change)
5	Fabric Reaches Tailor	in_progress	(no change)
6	Tailor Finishes	ready_for_delivery	(no change)
7	Partner Picks Up Garment	out_for_delivery	(no change)
8	Customer Receives Item	completed	fully_paid

flask db init
flask db migrate -m  " message"
flask db upgrade

$env:FLASK_APP = "run.py"

===

Below is a code editor-like representation of the provided PDF content ("Tailoring_app_specifiactions.pdf") formatted with proper syntax highlighting and structure. This representation mimics a code editor environment, such as VS Code, with comments, sections, and SQL code blocks for clarity.

```plaintext
// Technical Specification: On-Demand Tailoring Platform
// ==========================================================================

// 1. Project Overview
/*
This document outlines the technical implementation of the On-Demand Tailoring web application, a
three-sided marketplace connecting customers, tailors, and delivery partners ("Threadrunners"). The
platform facilitates the entire custom tailoring process, from order placement and measurement
collection to stitching and final delivery.
*/

Technology Stack:
- Backend: Python 3.10+ with the Flask Framework
- Database ORM: Flask-SQLAlchemy
- Database: SQLite (for development), designed for scalability to PostgreSQL
- Migrations: Flask-Migrate (using Alembic)
- Authentication: Flask-Login for session management
- Frontend: HTML5, CSS3, JavaScript (rendered via Jinja2 templates)

// 2. Final Database Schema
/*
The database is designed to be relational and scalable, separating master data from transactional
data and allowing for a high degree of customization by tailors.
*/

// Core Entity-Relationship Diagram (Conceptual)
// SQL Schema (CREATE TABLE Statements)

// -- Main authentication table for all roles
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE,
    phone_number TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    role TEXT NOT NULL, -- 'customer', 'tailor', 'delivery_partner', 'admin'
    is_verified BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP
);

// -- General and role-specific user profiles
CREATE TABLE user_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    -- ... (additional columns)
);

CREATE TABLE tailor_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    -- ... (additional columns)
);

CREATE TABLE delivery_partner_profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    -- ... (additional columns)
);

CREATE TABLE addresses (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    -- ... (additional columns)
);

CREATE TABLE sub_profiles (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    -- ... (additional columns)
);

// -- Master data for services and measurements
CREATE TABLE services (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    category TEXT,
    -- ... (additional columns)
);

CREATE TABLE measurement_fields (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    image_url TEXT,
    -- ... (additional columns)
);

// -- Linking table for a service's standard measurements
CREATE TABLE standard_service_measurements (
    service_id INTEGER REFERENCES services(id),
    measurement_field_id INTEGER REFERENCES measurement_fields(id),
    PRIMARY KEY (service_id, measurement_field_id)
);

// -- Tailor's specific offerings
CREATE TABLE tailor_services (
    id INTEGER PRIMARY KEY,
    tailor_id INTEGER REFERENCES users(id),
    service_id INTEGER REFERENCES services(id),
    price REAL NOT NULL,
    estimated_days INTEGER NOT NULL
);

// -- Linking table for a tailor's custom measurements for a service
CREATE TABLE tailor_service_measurements (
    tailor_service_id INTEGER REFERENCES tailor_services(id),
    measurement_field_id INTEGER REFERENCES measurement_fields(id),
    PRIMARY KEY (tailor_service_id, measurement_field_id)
);

// -- Order and fulfillment tables
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES users(id),
    tailor_id INTEGER REFERENCES users(id),
    delivery_address_id INTEGER REFERENCES addresses(id),
    order_status TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    measurement_method TEXT NOT NULL,
    -- ... (additional columns)
);

CREATE TABLE order_items (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    tailor_service_id INTEGER REFERENCES tailor_services(id)
);

CREATE TABLE order_measurement_values (
    id INTEGER PRIMARY KEY,
    order_item_id INTEGER REFERENCES order_items(id),
    measurement_field_id INTEGER REFERENCES measurement_fields(id),
    value REAL NOT NULL
);

// -- Logistics and OTP table
CREATE TABLE logistics (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    delivery_partner_id INTEGER REFERENCES users(id),
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,
    pickup_otp TEXT,
    tailor_handover_otp TEXT,
    delivery_otp TEXT
);

// -- Saved measurement profiles
CREATE TABLE measurement_profiles (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    sub_profile_id INTEGER REFERENCES sub_profiles(id),
    service_id INTEGER REFERENCES services(id),
    -- ... (additional columns)
);

CREATE TABLE saved_measurement_values (
    -- ... (additional columns)
);

// 3. Application Architecture
/*
The application is built using a scalable Flask App Factory pattern with modular Blueprints for each
major component.
*/

Directory Structure:
/  // Root directory
├── app/  // Application package
│   ├── __init__.py           // App Factory, registers blueprints
│   ├── models.py             // All SQLAlchemy models
│   ├── config.py             // Configuration (Dev, Prod)
│   ├── auth/                 // Authentication Blueprint
│   ├── customer/             // Customer Portal Blueprint
│   ├── tailor/               // Tailor Portal Blueprint
│   ├── delivery/             // Delivery Partner Blueprint
│   ├── admin/                // Admin Panel Blueprint
|   |__ notifications         // Notifcation 
│   └── templates/            // All HTML templates, organized by blueprint
├── manage.py                 // Custom CLI commands (seeding)
└── run.py                    // Main application entry point

// 4. Core Workflow Logic
/*
The application logic is driven by a state machine where actions by one user trigger tasks and state
changes for another.
*/

// Authentication Flow (auth blueprint)
- A single registration form at /auth/register handles all roles (Customer, Tailor, Delivery Partner).
- A unified login page at /auth/login supports both Email/Password and Phone/OTP methods.
- OTP verification is handled by a single, context-aware /auth/verify route.
- A check_profile_and_redirect helper function routes users to the correct dashboard based on
  their role after a successful login.

// Order Fulfillment Lifecycle
/*
The order_status field in the orders table tracks the end-to-end flow.
*/

1. pending_tailor_acceptance: A customer creates an order via the customer.new_order or
   customer.request_visit routes.

2. awaiting_pickup: A tailor accepts the order via the tailor.accept_order route. This is the first
   trigger: a Logistic task is created with task_type='pickup_from_customer',
   delivery_partner_id=None, and two OTPs are generated (pickup_otp and tailor_handover_otp).

3. fabric_in_transit: A delivery partner accepts the task (delivery.accept_task) and verifies the
   customer's pickup_otp via the delivery.verify_otp route. If it was a home visit, measurements
   are also submitted here.

4. in_progress: The partner arrives at the tailor's location. The partner enters the
   tailor_handover_otp (which the tailor sees on their dashboard) into the delivery.verify_otp
   route. This completes the first Logistic task.

5. ready_for_delivery: The tailor marks the order as finished via the tailor.complete_order
   route. This is the second trigger: a new Logistic task is created with
   task_type='pickup_from_tailor', delivery_partner_id=None, and a new pickup_otp.

6. out_for_delivery: A partner accepts the new task, goes to the tailor, and verifies the
   pickup_otp. This completes the pickup_from_tailor task and automatically creates the final
   chained task: a new Logistic record with task_type='drop_to_customer' and a final delivery_otp.

7. completed: The partner arrives at the customer's address and verifies the delivery_otp to
   complete the final task and the order. The payment_status is updated.

// Custom CLI Commands (manage.py)
- flask seed_db: Populates the master services and measurement_fields tables and links their
  standard measurement sets. Essential for initial setup.
- flask seed_users: Creates a sample Customer, Tailor, and Delivery Partner with all associated
  profiles and addresses, allowing for immediate end-to-end testing.
```

### Notes:
- The content is structured with comments (`//` for single-line, `/* ... */` for multi-line) to mimic a code editor's readability.
- SQL `CREATE TABLE` statements are preserved as-is, with placeholders (`-- ...`) where additional columns are implied but not fully detailed in the PDF.
- Sections are clearly delineated with headers and comments to reflect the document's original structure.
- This format assumes a text-based editor environment and does not include graphical elements like diagrams, which would require a separate visualization tool.