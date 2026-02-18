import sys
import os

# Add the project directory to the python path
project_home = '/home/rymaai/prop_management'
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Set environment variables for SQLite with an absolute path
os.environ['DATABASE_URL'] = 'sqlite:////home/rymaai/prop_management/property_mgmt.db'

from app.main import app
from a2wsgi import ASGIMiddleware

# PythonAnywhere serves WSGI — wrap the ASGI FastAPI app as WSGI
application = ASGIMiddleware(app)
