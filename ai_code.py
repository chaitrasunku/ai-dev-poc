import os
from datetime import datetime, timedelta
import jwt
from functools import wraps
from dotenv import load_dotenv

from flask import (
    Flask, jsonify, request, g, abort, Blueprint, current_app
)
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from marshmallow import Schema, fields, validate
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from flask_marshmallow import Marshmallow

# --- Configuration (config.py equivalent) ---
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'default_fallback_secret_key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///default_expense_tracker.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = SECRET_KEY
    JWT_ACCESS_TOKEN_EXPIRES = 3600 # 1 hour

# --- Extensions initialization (models.py / app.py equivalent) ---
db = SQLAlchemy()
bcrypt = Bcrypt()
ma = Marshmallow()

# --- Database Models (models.py equivalent) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user', nullable=False) # 'user', 'admin'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    expenses = db.relationship('Expense', backref='user', lazy=True, cascade='all, delete-orphan')
    categories = db.relationship('Category', backref='owner', lazy=True, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # If null, it's a global category

    expenses = db.relationship('Expense', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Expense {self.description} - {self.amount}>'

# --- Marshmallow Schemas (schemas.py equivalent) ---
class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        exclude = ('password_hash',)

    id = fields.Integer(dump_only=True)
    username = fields.String(required=True, validate=validate.Length(min=3))
    email = fields.Email(required=True)
    role = fields.String(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class UserRegisterSchema(UserSchema):
    password = fields.String(required=True, load_only=True, validate=validate.Length(min=6))
    role = fields.String(validate=validate.OneOf(['user', 'admin']), missing='user')

class UserUpdateSchema(UserSchema):
    username = fields.String(required=False, validate=validate.Length(min=3))
    email = fields.Email(required=False)
    password = fields.String(required=False, load_only=True, validate=validate.Length(min=6))
    role = fields.String(required=False, validate=validate.OneOf(['user', 'admin']))

class CategorySchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Category
        load_instance = True

    id = fields.Integer(dump_only=True)
    name = fields.String(required=True, validate=validate.Length(min=2))
    description = fields.String(required=False)
    user_id = fields.Integer(dump_only=True)

class ExpenseSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Expense
        load_instance = True
        include_relationships = True

    id = fields.Integer(dump_only=True)
    description = fields.String(required=True, validate=validate.Length(min=3))
    amount = fields.Float(required=True, validate=validate.Range(min=0.01))
    date = fields.DateTime(required=False, format='%Y-%m-%d')
    user_id = fields.Integer(dump_only=True)
    category_id = fields.Integer(required=False, allow_none=True)
    category = fields.Nested(CategorySchema, dump_only=True)

# --- Custom Decorators (decorators.py equivalent) ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                raise Exception('User not found')
            g.current_user = current_user
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
            return jsonify({'message': f'Something went wrong with token validation: {str(e)}'}), 401

        return f(*args, **kwargs)
    return decorated

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'current_user'):
                return jsonify({'message': 'Authentication required. Token missing or invalid.'}), 401
            
            if g.current_user.role not in roles:
                return jsonify({'message': 'Access forbidden: Insufficient permissions.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Blueprints (blueprints/ equivalents) ---

# auth_bp
auth_bp = Blueprint('auth', __name__, url_prefix='/auth')
user_register_schema = UserRegisterSchema()
user_update_schema = UserUpdateSchema()
user_schema = UserSchema()

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        user_data = user_register_schema.load(request.json)
    except Exception as e:
        return jsonify(e.messages), 400

    if User.query.filter_by(username=user_data['username']).first():
        return jsonify({'message': 'Username already exists'}), 409
    if User.query.filter_by(email=user_data['email']).first():
        return jsonify({'message': 'Email already exists'}), 409

    new_user = User(username=user_data['username'], email=user_data['email'], role=user_data['role'])
    new_user.set_password(user_data['password'])

    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'}), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({'message': 'Invalid username or password'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(seconds=current_app.config['JWT_ACCESS_TOKEN_EXPIRES'])
    }, current_app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({'token': token}), 200

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_me():
    return user_schema.dump(g.current_user), 200

@auth_bp.route('/me', methods=['PUT'])
@token_required
def update_me():
    try:
        data = user_update_schema.load(request.json, partial=True)
    except Exception as e:
        return jsonify(e.messages), 400

    current_user = g.current_user

    if 'username' in data:
        if User.query.filter(User.username == data['username'], User.id != current_user.id).first():
            return jsonify({'message': 'Username already taken'}), 409
        current_user.username = data['username']
    if 'email' in data:
        if User.query.filter(User.email == data['email'], User.id != current_user.id).first():
            return jsonify({'message': 'Email already taken'}), 409
        current_user.email = data['email']
    if 'password' in data:
        current_user.set_password(data['password'])

    db.session.commit()
    return jsonify({'message': 'Profile updated successfully', 'user': user_schema.dump(current_user)}), 200

@auth_bp.route('/me', methods=['DELETE'])
@token_required
def delete_me():
    user = g.current_user
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'Account deleted successfully'}), 200

# users_bp
users_bp = Blueprint('users', __name__, url_prefix='/users')
users_schema = UserSchema(many=True)

@users_bp.route('/', methods=['GET'])
@token_required
@roles_required('admin')
def get_all_users():
    users = User.query.all()
    return users_schema.dump(users), 200

@users_bp.route('/<int:user_id>', methods=['GET'])
@token_required
@roles_required('admin')
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return user_schema.dump(user), 200

@users_bp.route('/<int:user_id>', methods=['PUT'])
@token_required
@roles_required('admin')
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    try:
        data = user_update_schema.load(request.json, partial=True)
    except Exception as e:
        return jsonify(e.messages), 400

    if 'username' in data:
        if User.query.filter(User.username == data['username'], User.id != user_id).first():
            return jsonify({'message': 'Username already taken'}), 409
        user.username = data['username']
    if 'email' in data:
        if User.query.filter(User.email == data['email'], User.id != user_id).first():
            return jsonify({'message': 'Email already taken'}), 409
        user.email = data['email']
    if 'password' in data:
        user.set_password(data['password'])
    if 'role' in data:
        user.role = data['role']

    db.session.commit()
    return jsonify({'message': 'User updated successfully', 'user': user_schema.dump(user)}), 200

@users_bp.route('/<int:user_id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted successfully'}), 200

# expenses_bp
expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')
expense_schema = ExpenseSchema()
expenses_schema = ExpenseSchema(many=True)

@expenses_bp.route('/', methods=['POST'])
@token_required
def create_expense():
    try:
        data = expense_schema.load(request.json)
    except Exception as e:
        return jsonify(e.messages), 400

    data['user_id'] = g.current_user.id

    if data.get('category_id'):
        category = Category.query.get(data['category_id'])
        if not category:
            return jsonify({'message': 'Category not found'}), 400

    new_expense = Expense(**data)
    db.session.add(new_expense)
    db.session.commit()
    return expense_schema.dump(new_expense), 201

@expenses_bp.route('/', methods=['GET'])
@token_required
def get_expenses():
    if g.current_user.role == 'admin':
        expenses = Expense.query.all()
    else:
        expenses = Expense.query.filter_by(user_id=g.current_user.id).all()
    return expenses_schema.dump(expenses), 200

@expenses_bp.route('/<int:expense_id>', methods=['GET'])
@token_required
def get_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != g.current_user.id and g.current_user.role != 'admin':
        abort(403, description='Access forbidden: You can only view your own expenses.')
    return expense_schema.dump(expense), 200

@expenses_bp.route('/<int:expense_id>', methods=['PUT'])
@token_required
def update_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != g.current_user.id and g.current_user.role != 'admin':
        abort(403, description='Access forbidden: You can only update your own expenses.')

    try:
        data = expense_schema.load(request.json, partial=True)
    except Exception as e:
        return jsonify(e.messages), 400
    
    data.pop('user_id', None)

    if data.get('category_id'):
        category = Category.query.get(data['category_id'])
        if not category:
            return jsonify({'message': 'Category not found'}), 400

    for key, value in data.items():
        setattr(expense, key, value)
    db.session.commit()
    return expense_schema.dump(expense), 200

@expenses_bp.route('/<int:expense_id>', methods=['DELETE'])
@token_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    if expense.user_id != g.current_user.id and g.current_user.role != 'admin':
        abort(403, description='Access forbidden: You can only delete your own expenses.')
    
    db.session.delete(expense)
    db.session.commit()
    return jsonify({'message': 'Expense deleted successfully'}), 200

# categories_bp
categories_bp = Blueprint('categories', __name__, url_prefix='/categories')
category_schema = CategorySchema()
categories_schema = CategorySchema(many=True)

@categories_bp.route('/', methods=['POST'])
@token_required
@roles_required('admin')
def create_category():
    try:
        data = category_schema.load(request.json)
    except Exception as e:
        return jsonify(e.messages), 400
    
    if Category.query.filter_by(name=data['name']).first():
        return jsonify({'message': 'Category with this name already exists'}), 409

    new_category = Category(name=data['name'], description=data.get('description'))
    db.session.add(new_category)
    db.session.commit()
    return category_schema.dump(new_category), 201

@categories_bp.route('/', methods=['GET'])
def get_categories():
    categories = Category.query.all()
    return categories_schema.dump(categories), 200

@categories_bp.route('/<int:category_id>', methods=['GET'])
def get_category(category_id):
    category = Category.query.get_or_404(category_id)
    return category_schema.dump(category), 200

@categories_bp.route('/<int:category_id>', methods=['PUT'])
@token_required
@roles_required('admin')
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    try:
        data = category_schema.load(request.json, partial=True)
    except Exception as e:
        return jsonify(e.messages), 400
    
    if 'name' in data and Category.query.filter(Category.name == data['name'], Category.id != category_id).first():
        return jsonify({'message': 'Category with this name already exists'}), 409

    for key, value in data.items():
        setattr(category, key, value)
    db.session.commit()
    return category_schema.dump(category), 200

@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@token_required
@roles_required('admin')
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    
    if category.expenses:
        return jsonify({'message': 'Cannot delete category: it is linked to existing expenses.'}), 409

    db.session.delete(category)
    db.session.commit()
    return jsonify({'message': 'Category deleted successfully'}), 200

# --- Main Application (app.py / run.py equivalent) ---
def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    bcrypt.init_app(app)
    ma.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(categories_bp)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'message': 'Not Found', 'details': str(error)}), 404

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'message': 'Forbidden', 'details': str(error)}), 403

    @app.errorhandler(409)
    def conflict(error):
        return jsonify({'message': 'Conflict', 'details': str(error)}), 409
    
    @app.cli.command("init-db")
    def init_db_command():
        with app.app_context():
            db.drop_all()
            db.create_all()
            print("Initialized the database.")
            
            admin_user = User(username='admin', email='admin@example.com', role='admin')
            admin_user.set_password('adminpassword')
            db.session.add(admin_user)
            db.session.commit()
            print("Created default admin user (username: admin, password: adminpassword)")

    return app

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Expense': Expense, 'Category': Category}

if __name__ == '__main__':
    app.run(debug=True)