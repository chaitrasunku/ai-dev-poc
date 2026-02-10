Okay, this is a comprehensive request! I'll break it down into the specified files and provide the complete code for each, along with instructions.

Let's start building!

---

## 1. Project Setup (as you provided)

```bash
# 1. Create project directory
mkdir expense_tracker_api
cd expense_tracker_api

# 2. Create and activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# 3. Install necessary packages
pip install Flask Flask-SQLAlchemy Flask-Migrate Flask-JWT-Extended Werkzeug python-dotenv
```

## 2. Project Structure (creating folders)

```bash
mkdir routes
touch routes/__init__.py # This makes 'routes' a Python package
mkdir instance # For SQLite database file
```

Now, let's fill in the files.

---

## 3. Configuration (`config.py`)

```python
# config.py
import os

class Config:
    # Use os.getenv instead of os.environ.get for better dotenv integration
    SECRET_KEY = os.getenv('SECRET_KEY') or 'a_fallback_secret_key_if_dotenv_fails'
    
    # Database configuration
    # Construct an absolute path for the SQLite database within the 'instance' folder
    instance_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance')
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL') or \
                              'sqlite:///' + os.path.join(instance_path, 'expense_tracker.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT Configuration
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = 3600 # 1 hour
    # JWT_REFRESH_TOKEN_EXPIRES = 2592000 # 30 days (optional)
```

---

## 4. Environment Variables (`.env`)

Create `.env` in the `expense_tracker_api/` root directory.

```dotenv
# .env
SECRET_KEY="your_flask_session_secret_key_here_generate_with_secrets.token_urlsafe(32)"
JWT_SECRET_KEY="your_jwt_signing_secret_key_here_generate_with_secrets.token_urlsafe(32)"
DATABASE_URL="sqlite:///./instance/expense_tracker.db" # Or your PostgreSQL/MySQL URL
```

*To generate strong secret keys in Python:*
```python
import secrets
print(secrets.token_urlsafe(32)) # For SECRET_KEY
print(secrets.token_urlsafe(64)) # For JWT_SECRET_KEY (longer is generally better for JWTs)
```

---

## 5. Application Initialization (`app.py`)

```python
# app.py
import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
# The instance_path helps Flask find configuration files and the SQLite DB file.
app = Flask(__name__, instance_path=os.path.join(os.path.abspath(os.path.dirname(__file__)), 'instance'))
app.config.from_object('config.Config')

# Ensure the instance folder exists for SQLite
os.makedirs(app.instance_path, exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)

# --- JWT Custom Error Handlers ---
@jwt.unauthorized_loader
def unauthorized_response(callback):
    return jsonify({"message": "Missing Authorization Header or invalid token format"}), 401

@jwt.invalid_token_loader
def invalid_token_response(callback):
    return jsonify({"message": "Signature verification failed, invalid token"}), 401

@jwt.expired_token_loader
def expired_token_response(callback):
    return jsonify({"message": "Token has expired"}), 401

@jwt.revoked_token_loader
def revoked_token_response(callback):
    return jsonify({"message": "Token has been revoked"}), 401

@jwt.needs_fresh_token_loader
def needs_fresh_token_response(callback):
    return jsonify({"message": "Fresh token required"}), 401

@jwt.token_verification_loader
def token_verification_response(callback):
    # This handler is not usually for errors, but for customizing verification.
    # The default behavior is usually sufficient for simple cases.
    pass # No custom logic needed for verification errors here, they are caught by invalid/expired loaders.

# --- Import models so Flask-Migrate can detect them ---
# This import needs to happen AFTER 'db' is initialized
from models import User, Expense

# --- Register blueprints/routes ---
# Import Blueprints
from auth import auth_bp
from routes.users import users_bp
from routes.expenses import expenses_bp

app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(users_bp, url_prefix='/api/users')
app.register_blueprint(expenses_bp, url_prefix='/api/expenses')

# --- Basic Home Route ---
@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Expense Tracker API!"})

# --- Run the application ---
if __name__ == '__main__':
    # When running with 'flask run', this block is not executed.
    # It's primarily for directly running the script.
    app.run(debug=True)
```

---

## 6. Database Models (`models.py`)

```python
# models.py
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app import db # Import db from the initialized app instance

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True) # Added index for performance
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)   # Added index
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(10), default='user', nullable=False) # 'user', 'admin'

    # One-to-many relationship with Expense
    expenses = db.relationship('Expense', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    # cascade='all, delete-orphan' ensures that if a user is deleted, their expenses are also deleted.

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} (Role: {self.role})>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.Column(db.String(50), nullable=True) # e.g., Food, Transport, Utilities

    # Foreign key relationship to User
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True) # Added index for FK

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Expense {self.description} by User {self.user_id}>'
```

---

## 7. Custom Decorators for RBAC (`decorators.py`)

```python
# decorators.py
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request

def roles_required(*roles):
    """
    Decorator to check if the current user has any of the required roles.
    Uses the 'role' claim stored in the JWT.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            try:
                verify_jwt_in_request() # Ensures a valid JWT is present
                claims = get_jwt() # Gets all claims from the JWT
                
                # Check if 'role' claim exists and is in the list of required roles
                if "role" in claims and claims["role"] in roles:
                    return fn(*args, **kwargs)
                else:
                    return jsonify({"message": "Access Forbidden: Insufficient role permissions"}), 403
            except Exception as e:
                # Flask-JWT-Extended's error handlers will usually catch these,
                # but a fallback catch here is robust.
                return jsonify({"message": str(e)}), 401
        return decorator
    return wrapper
```

---

## 8. Authentication Routes (`auth.py`)

```python
# auth.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from app import db # Import db from the initialized app instance
from models import User # Import User model

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"message": "Username, email, and password are required"}), 400

    # Basic validation for password length
    if len(password) < 6:
        return jsonify({"message": "Password must be at least 6 characters long"}), 400

    # Check if username or email already exists
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already registered"}), 409

    new_user = User(username=username, email=email)
    new_user.set_password(password)

    # Assign 'admin' role to the very first user registered
    # This is a common pattern for initial setup, but in production,
    # admin creation might be through a separate, protected interface.
    if User.query.count() == 0:
        new_user.role = 'admin'
        print(f"DEBUG: Assigned 'admin' role to {username} as the first user.") # Debug print

    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully", "user_id": new_user.id, "role": new_user.role}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Username and password are required"}), 400

    user = User.query.filter_by(username=username).first()

    if user and user.check_password(password):
        # Create custom claims for the JWT to include the user's role
        additional_claims = {"role": user.role}
        access_token = create_access_token(identity=user.id, additional_claims=additional_claims)
        return jsonify(access_token=access_token, user_id=user.id, username=user.username, role=user.role), 200
    else:
        return jsonify({"message": "Invalid credentials"}), 401

# You might add a logout route if you implement token blacklisting.
# For simplicity, we'll skip token blacklisting in this example.
# @auth_bp.route('/logout', methods=['POST'])
# @jwt_required()
# def logout():
#     # Implement token blacklisting if desired
#     return jsonify({"message": "Successfully logged out"}), 200
```

---

## 9. Routes for Users (`routes/users.py`)

First, ensure `routes/__init__.py` exists (it can be empty).

```python
# routes/users.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db # Import db from the initialized app instance
from models import User
from decorators import roles_required

users_bp = Blueprint('users', __name__)

@users_bp.route('/', methods=['GET'])
@jwt_required()
@roles_required('admin') # Only admins can view all users
def get_all_users():
    users = User.query.all()
    output = []
    for user in users:
        output.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        })
    return jsonify(output), 200

@users_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    current_user_role = claims.get('role')

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Authorization: A user can get their own details, or an admin can get any user's details
    if current_user_id == user.id or current_user_role == 'admin':
        return jsonify({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role
        }), 200
    else:
        return jsonify({"message": "Access Forbidden: You can only view your own user data"}), 403

@users_bp.route('/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    current_user_role = claims.get('role')

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Authorization: A user can update their own details, or an admin can update any user's details
    if not (current_user_id == user.id or current_user_role == 'admin'):
        return jsonify({"message": "Access Forbidden: You can only update your own user data"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body must contain data"}), 400

    # Prevent users from changing their own role, even if they include it in the request
    if 'role' in data and current_user_role != 'admin':
        return jsonify({"message": "Access Forbidden: Only admins can change user roles"}), 403

    # Fields that can be updated by owner or admin
    if 'username' in data:
        new_username = data['username']
        if User.query.filter_by(username=new_username).first() and new_username != user.username:
            return jsonify({"message": "Username already taken"}), 409
        user.username = new_username
    if 'email' in data:
        new_email = data['email']
        if User.query.filter_by(email=new_email).first() and new_email != user.email:
            return jsonify({"message": "Email already registered"}), 409
        user.email = new_email
    if 'password' in data:
        new_password = data['password']
        if len(new_password) < 6:
            return jsonify({"message": "Password must be at least 6 characters long"}), 400
        user.set_password(new_password)

    # Only an admin can change roles
    if 'role' in data and current_user_role == 'admin':
        if data['role'] not in ['user', 'admin']:
            return jsonify({"message": "Invalid role specified. Must be 'user' or 'admin'"}), 400
        user.role = data['role']

    db.session.commit()
    return jsonify({"message": "User updated successfully", "user": {
        'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role
    }}), 200

@users_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
@roles_required('admin') # Only admins can delete users
def delete_user(user_id):
    current_user_id = get_jwt_identity()
    if current_user_id == user_id:
        return jsonify({"message": "Admins cannot delete their own active account via this endpoint. Self-deletion would require re-authentication or a specific flow to prevent accidental lockout."}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"message": "User not found"}), 404

    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "User deleted successfully"}), 200
```

---

## 10. Routes for Expenses (`routes/expenses.py`)

```python
# routes/expenses.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from app import db # Import db from the initialized app instance
from models import Expense, User
from decorators import roles_required # Not strictly needed here, but good practice for clarity
from datetime import datetime

expenses_bp = Blueprint('expenses', __name__)

@expenses_bp.route('/', methods=['POST'])
@jwt_required()
def create_expense():
    current_user_id = get_jwt_identity()
    data = request.get_json()

    description = data.get('description')
    amount = data.get('amount')
    expense_date_str = data.get('date') # Expected format: YYYY-MM-DD
    category = data.get('category')

    if not description or amount is None: # Amount can be 0, but not missing
        return jsonify({"message": "Description and amount are required"}), 400

    try:
        amount = float(amount)
        if amount <= 0: # Or allow 0 for special cases if required
            return jsonify({"message": "Amount must be positive"}), 400
    except ValueError:
        return jsonify({"message": "Amount must be a valid number"}), 400

    expense_date = datetime.utcnow() # Default to now
    if expense_date_str:
        try:
            expense_date = datetime.strptime(expense_date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({"message": "Invalid date format for 'date'. Use YYYY-MM-DD"}), 400

    new_expense = Expense(
        description=description,
        amount=amount,
        date=expense_date,
        category=category,
        user_id=current_user_id
    )
    db.session.add(new_expense)
    db.session.commit()

    return jsonify({
        "message": "Expense created successfully",
        "expense": {
            "id": new_expense.id,
            "description": new_expense.description,
            "amount": new_expense.amount,
            "date": new_expense.date.strftime('%Y-%m-%d'),
            "category": new_expense.category,
            "user_id": new_expense.user_id,
            "created_at": new_expense.created_at.isoformat(),
            "updated_at": new_expense.updated_at.isoformat()
        }
    }), 201

@expenses_bp.route('/', methods=['GET'])
@jwt_required()
def get_expenses():
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    current_user_role = claims.get('role')

    expenses_query = Expense.query

    if current_user_role != 'admin':
        # Regular user can only see their own expenses
        expenses_query = expenses_query.filter_by(user_id=current_user_id)
    # Admins see all by default as no filter is applied

    all_expenses = expenses_query.order_by(Expense.date.desc()).all() # Order by date, latest first

    output = []
    for expense in all_expenses:
        output.append({
            'id': expense.id,
            'description': expense.description,
            'amount': expense.amount,
            'date': expense.date.strftime('%Y-%m-%d'),
            'category': expense.category,
            'user_id': expense.user_id,
            'created_at': expense.created_at.isoformat(),
            'updated_at': expense.updated_at.isoformat()
        })
    return jsonify(output), 200

@expenses_bp.route('/<int:expense_id>', methods=['GET'])
@jwt_required()
def get_expense(expense_id):
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    current_user_role = claims.get('role')

    expense = Expense.query.get(expense_id)

    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    # Authorization: Allow access if it's the owner or an admin
    if expense.user_id == current_user_id or current_user_role == 'admin':
        return jsonify({
            'id': expense.id,
            'description': expense.description,
            'amount': expense.amount,
            'date': expense.date.strftime('%Y-%m-%d'),
            'category': expense.category,
            'user_id': expense.user_id,
            'created_at': expense.created_at.isoformat(),
            'updated_at': expense.updated_at.isoformat()
        }), 200
    else:
        return jsonify({"message": "Access Forbidden: You do not own this expense or lack admin privileges"}), 403

@expenses_bp.route('/<int:expense_id>', methods=['PUT'])
@jwt_required()
def update_expense(expense_id):
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    current_user_role = claims.get('role')

    expense = Expense.query.get(expense_id)

    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    # Authorization: Only owner or admin can update
    if not (expense.user_id == current_user_id or current_user_role == 'admin'):
        return jsonify({"message": "Access Forbidden: You do not own this expense or lack admin privileges"}), 403

    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body must contain data"}), 400

    if 'description' in data:
        expense.description = data['description']
    if 'amount' in data:
        try:
            amount = float(data['amount'])
            if amount <= 0:
                return jsonify({"message": "Amount must be positive"}), 400
            expense.amount = amount
        except ValueError:
            return jsonify({"message": "Amount must be a valid number"}), 400
    if 'date' in data:
        try:
            expense.date = datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            return jsonify({"message": "Invalid date format for 'date'. Use YYYY-MM-DD"}), 400
    if 'category' in data:
        expense.category = data['category']

    db.session.commit()
    return jsonify({
        "message": "Expense updated successfully",
        "expense": {
            "id": expense.id,
            "description": expense.description,
            "amount": expense.amount,
            "date": expense.date.strftime('%Y-%m-%d'),
            "category": expense.category,
            "user_id": expense.user_id,
            "created_at": expense.created_at.isoformat(),
            "updated_at": expense.updated_at.isoformat()
        }
    }), 200

@expenses_bp.route('/<int:expense_id>', methods=['DELETE'])
@jwt_required()
def delete_expense(expense_id):
    current_user_id = get_jwt_identity()
    claims = get_jwt()
    current_user_role = claims.get('role')

    expense = Expense.query.get(expense_id)

    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    # Authorization: Only owner or admin can delete
    if not (expense.user_id == current_user_id or current_user_role == 'admin'):
        return jsonify({"message": "Access Forbidden: You do not own this expense or lack admin privileges"}), 403

    db.session.delete(expense)
    db.session.commit()
    return jsonify({"message": "Expense deleted successfully"}), 200
```

---

## Database Migrations

With the files in place, let's set up the database. Ensure your virtual environment is active.

```bash
# 1. Initialize migration repository
# This creates the 'migrations' folder and initial scripts.
flask db init

# 2. Create the first migration script based on your models.py
# This generates a script with instructions to create your User and Expense tables.
flask db migrate -m "Initial migration"

# 3. Apply the migration to create the tables in your SQLite database file.
flask db upgrade
```
You should now have an `expense_tracker.db` file inside your `instance/` folder.

---

## Running the Application

To run the Flask development server:

```bash
flask run
```
The API will be available at `http://127.0.0.1:5000`.

---

## Testing the API (with `curl`)

Make sure your server is running (`flask run`).

**Important:** Replace `$ADMIN_TOKEN` and `$USER_TOKEN` with the actual tokens you receive from the login responses. You might want to export them as environment variables in your terminal for easier testing:
`export ADMIN_TOKEN="your_actual_admin_jwt_here"`
`export USER_TOKEN="your_actual_user_jwt_here"`

---

**1. Register a User (This will be an Admin if it's the first user in the DB)**

```bash
curl -X POST -H "Content-Type: application/json" -d '{"username": "adminuser", "email": "admin@example.com", "password": "adminpassword"}' http://127.0.0.1:5000/api/auth/register
```
*Expected Output:* `{"message": "User registered successfully", "user_id": 1, "role": "admin"}`

**2. Login the Admin User to get a JWT Token**

```bash
curl -X POST -H "Content-Type: application/json" -d '{"username": "adminuser", "password": "adminpassword"}' http://127.0.0.1:5000/api/auth/login
```
*Expected Output:* `{"access_token": "eyJ...", "user_id": 1, "username": "adminuser", "role": "admin"}`
**COPY THE "access_token" VALUE!** Set it as your `$ADMIN_TOKEN`.

**3. Register a Regular User**

```bash
curl -X POST -H "Content-Type: application/json" -d '{"username": "testuser", "email": "user@example.com", "password": "userpassword"}' http://127.0.0.1:5000/api/auth/register
```
*Expected Output:* `{"message": "User registered successfully", "user_id": 2, "role": "user"}`

**4. Login the Regular User**

```bash
curl -X POST -H "Content-Type: application/json" -d '{"username": "testuser", "password": "userpassword"}' http://127.0.0.1:5000/api/auth/login
```
*Expected Output:* `{"access_token": "eyJ...", "user_id": 2, "username": "testuser", "role": "user"}`
**COPY THIS TOKEN TOO!** Set it as your `$USER_TOKEN`.

---

### Using the Admin Token (`$ADMIN_TOKEN`)

**5. Admin: Get All Users**
*(Requires `roles_required('admin')`)*

```bash
curl -X GET -H "Authorization: Bearer $ADMIN_TOKEN" http://127.0.0.1:5000/api/users/
```
*Expected Output:* List of all users including `adminuser` and `testuser`.

**6. Admin: Get Specific User (e.g., `testuser` with ID 2)**
*(Allows owner OR admin)*

```bash
curl -X GET -H "Authorization: Bearer $ADMIN_TOKEN" http://127.0.0.1:5000/api/users/2
```
*Expected Output:* Details of `testuser`.

**7. Admin: Update Regular User's Role (e.g., promote `testuser` to admin)**
*(Admins can update roles)*

```bash
curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"role": "admin"}' http://127.0.0.1:5000/api/users/2
```
*Expected Output:* `{"message": "User updated successfully", "user": {"id": 2, "username": "testuser", "email": "user@example.com", "role": "admin"}}`
*(Note: For this change to reflect in `testuser`'s JWT, `testuser` would need to log in again to get a new token with the updated role claim.)*

**8. Admin: Create an Expense for `testuser` (ID 2)**
*(Admins can theoretically create expenses for anyone, but the endpoint currently links to `current_user_id`. Let's create one for the admin first, then for testuser.)*

```bash
# Admin creating an expense for themselves
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"description": "Server Hosting", "amount": 25.50, "date": "2023-10-25", "category": "Utilities"}' http://127.0.0.1:5000/api/expenses/
```
*Expected: Success with `user_id: 1`* (assuming adminuser is ID 1). Let's say this expense gets ID 1.

**9. Admin: Get All Expenses**
*(Admins can view all expenses)*

```bash
curl -X GET -H "Authorization: Bearer $ADMIN_TOKEN" http://127.0.0.1:5000/api/expenses/
```
*Expected Output:* List including the "Server Hosting" expense and any others.

**10. Admin: Delete Regular User (e.g., `testuser`)**
*(Requires `roles_required('admin')`)*
*(Be careful, this is permanent! If you delete `testuser`, their expenses (if any) will also be deleted due to `cascade`.)*

```bash
# curl -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" http://127.0.0.1:5000/api/users/2
# Expected: {"message": "User deleted successfully"}
```

---

### Using the Regular User Token (`$USER_TOKEN`)

**(Assuming you've logged in as `testuser` (ID 2) and have `$USER_TOKEN`)**

**11. Regular User: Create an Expense**

```bash
curl -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $USER_TOKEN" -d '{"description": "Coffee", "amount": 4.50, "date": "2023-10-26", "category": "Food"}' http://127.0.0.1:5000/api/expenses/
```
*Expected Output:* `{"message": "Expense created successfully", "expense": {"id": ..., "user_id": 2, ...}}`. Let's assume this expense gets ID 2.

**12. Regular User: Get Their Own Expenses**
*(Regular users only see their own expenses)*

```bash
curl -X GET -H "Authorization: Bearer $USER_TOKEN" http://127.0.0.1:5000/api/expenses/
```
*Expected Output:* List containing the "Coffee" expense (and any other expenses created by `testuser`).

**13. Regular User: Get a Specific Expense (Owned by them)**

```bash
curl -X GET -H "Authorization: Bearer $USER_TOKEN" http://127.0.0.1:5000/api/expenses/2 # Assuming Coffee expense is ID 2
```
*Expected Output:* Details of the "Coffee" expense.

**14. Regular User: Try to Get Another User's Expense (will fail)**
*(Assuming adminuser's expense "Server Hosting" has ID 1)*

```bash
curl -X GET -H "Authorization: Bearer $USER_TOKEN" http://127.0.0.1:5000/api/expenses/1
```
*Expected Output:* `{"message": "Access Forbidden: You do not own this expense or lack admin privileges"}, 403`

**15. Regular User: Update an Expense (Owned by them)**

```bash
curl -X PUT -H "Content-Type: application/json" -H "Authorization: Bearer $USER_TOKEN" -d '{"amount": 5.00, "category": "Beverage"}' http://127.0.0.1:5000/api/expenses/2
```
*Expected Output:* `{"message": "Expense updated successfully", "expense": {...}}`

**16. Regular User: Delete an Expense (Owned by them)**

```bash
curl -X DELETE -H "Authorization: Bearer $USER_TOKEN" http://127.0.0.1:5000/api/expenses/2
```
*Expected Output:* `{"message": "Expense deleted successfully"}`

---

This robust setup covers all the requirements, including secure authentication, role-based access control, and comprehensive CRUD operations for both users and expenses. Remember to secure your `.env` file and use strong, randomly generated keys in production!