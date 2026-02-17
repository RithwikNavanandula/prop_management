import os
from flask import Flask, render_template, redirect, url_for, flash, request, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

# --- Configuration ---
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_key_change_this_later'
    # Use SQLite by default, but allow override for PythonAnywhere MySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///prop_mgmt_v3.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

app = Flask(__name__)
app.config.from_object(Config)

# --- Extensions ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- Models ---

# Association table for User-Role (Simplified: User has one role for now)
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON) # Store permissions as JSON

    users = db.relationship('User', backref='role', lazy=True)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    full_name = db.Column(db.String(100))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# --- Other Models (Simplified placeholders to match templates) ---
class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    type = db.Column(db.String(50)) # Residential, Commercial
    status = db.Column(db.String(20), default='Active')

class Unit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'))
    unit_number = db.Column(db.String(20))
    status = db.Column(db.String(20), default='Vacant')

class Tenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    email = db.Column(db.String(100))
    
class Lease(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit.id'))
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenant.id'))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(20))
    
class WorkOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    description = db.Column(db.Text)
    status = db.Column(db.String(20), default='Open')
    priority = db.Column(db.String(20), default='Medium')

# --- Helper Functions ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Context processor to make settings available to all templates (simulating V2)
@app.context_processor
def inject_globals():
    return {
        'settings': {'APP_NAME': 'PropManager Pro V3', 'APP_VERSION': '3.0.0'},
        'current_year': datetime.utcnow().year
    }

# --- CLI Commands ---
@app.cli.command("init-db")
def init_db_command():
    """Create database tables and seed default data."""
    db.create_all()
    
    # Seed Role
    if not Role.query.filter_by(role_name='admin').first():
        admin_role = Role(role_name='admin', description='Administrator', permissions={'all': True})
        db.session.add(admin_role)
        db.session.commit()
        print("Created admin role.")
        
    # Seed Admin User
    if not User.query.filter_by(username='admin').first():
        admin_user = User(username='admin', email='admin@example.com', full_name='System Admin', role_id=1)
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print("Created admin user (admin/admin123).")
    
    print("Database initialized.")

# --- Routes ---

@app.route('/')
def root():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # V2 templates usually send form data
        # Check if it's JSON or Form data (FastAPI might have handled both, Flask is explicit)
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password')
            
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Pass 'role' to template as V2 templates expect 'user' and 'role'
    return render_template('dashboard/index.html', user=current_user, role=current_user.role)

# Generic fallback for other pages to load their templates
# V2 had specific routes for /properties, /tenants etc. We will map them here.

@app.route('/properties')
@login_required
def properties():
    properties = Property.query.all()
    return render_template('properties/index.html', user=current_user, role=current_user.role, properties=properties)

@app.route('/tenants')
@login_required
def tenants():
    return render_template('tenants/index.html', user=current_user, role=current_user.role)

@app.route('/leases')
@login_required
def leases():
    return render_template('leasing/index.html', user=current_user, role=current_user.role)

@app.route('/maintenance')
@login_required
def maintenance():
    return render_template('maintenance/index.html', user=current_user, role=current_user.role)

@app.route('/reports')
@login_required
def reports():
    return render_template('reports/index.html', user=current_user, role=current_user.role)

@app.route('/profile')
@login_required
def profile():
    # Attempt to render a profile or settings page if it exists in V2 templates
    # Often V2 had /settings
    return render_template('system/settings.html', user=current_user, role=current_user.role, active_page='settings')


# Catch-all for other simple GET template routes might be tricky without listing them.
# Adding commonly used ones from V2 structure:

@app.route('/users')
@login_required
def users():
    if current_user.role.role_name != 'admin':
        return redirect(url_for('dashboard'))
    users_list = User.query.all()
    return render_template('auth/users.html', user=current_user, role=current_user.role, users=users_list)

if __name__ == '__main__':
    app.run(debug=True)
