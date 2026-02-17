import os
import sys

# Add the project directory to the python path
path = os.path.expanduser('~/Property Management V2')
if path not in sys.path:
    sys.path.append(path)

# Set environment variables if needed (though usually better in PA dashboard)
# os.environ['DATABASE_URL'] = '...'

from app.main import app
from asgiref.wsgi import WsgiToAsgi

# This is the WSGI application that PythonAnywhere will look for
application = WsgiToAsgi(app)
