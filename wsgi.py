import os
import sys

# Add the project directory to the python path
# Add the project directory to the python path
project_home = os.path.expanduser('~/prop_management')
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set environment variables for SQLite with an absolute path
# Replace 'yourusername' with your actual PythonAnywhere username if different
username = os.environ.get('USER', 'yourusername')
os.environ['DATABASE_URL'] = f'sqlite:////home/{username}/prop_management/property_mgmt.db'

from app.main import app
from asgiref.wsgi import WsgiToAsgi

# This is the WSGI application that PythonAnywhere will look for
application = WsgiToAsgi(app)
