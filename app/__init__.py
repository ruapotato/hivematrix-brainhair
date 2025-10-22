from flask import Flask
import json
import os
import configparser

app = Flask(__name__, instance_relative_config=True)

# --- Explicitly load all required configuration from environment variables ---
app.config['CORE_SERVICE_URL'] = os.environ.get('CORE_SERVICE_URL')
app.config['SERVICE_NAME'] = os.environ.get('SERVICE_NAME', 'brainhair')
app.config['HELM_SERVICE_URL'] = os.environ.get('HELM_SERVICE_URL', 'http://localhost:5004')

if not app.config['CORE_SERVICE_URL']:
    raise ValueError("CORE_SERVICE_URL must be set in the .flaskenv file.")

# Load database connection from config file
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

config_path = os.path.join(app.instance_path, 'brainhair.conf')
config = configparser.RawConfigParser()
config.read(config_path)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database', 'connection_string',
    fallback=f"sqlite:///{os.path.join(app.instance_path, 'brainhair.db')}")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
from extensions import db
db.init_app(app)

# Load services configuration from services.json (for service-to-service calls)
try:
    with open('services.json') as f:
        services_config = json.load(f)
        app.config['SERVICES'] = services_config
except FileNotFoundError:
    print("WARNING: services.json not found. Service-to-service calls will not work.")
    app.config['SERVICES'] = {}

# Initialize Helm logger for centralized logging
from app.helm_logger import init_helm_logger
helm_logger = init_helm_logger(
    app.config['SERVICE_NAME'],
    app.config['HELM_SERVICE_URL']
)

# Download spaCy language model for Presidio if not already installed
try:
    import spacy
    try:
        spacy.load("en_core_web_sm")
    except OSError:
        # Model not found, download it
        helm_logger.info("Downloading spaCy language model en_core_web_sm...")
        from spacy.cli import download
        download("en_core_web_sm")
        helm_logger.info("spaCy model downloaded successfully")
except Exception as e:
    helm_logger.warning(f"Could not download spaCy model: {e}. Presidio may use limited functionality.")

# Apply ProxyFix to handle X-Forwarded headers from Nexus proxy
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(
    app.wsgi_app,
    x_for=1,      # Trust X-Forwarded-For
    x_proto=1,    # Trust X-Forwarded-Proto
    x_host=1,     # Trust X-Forwarded-Host
    x_prefix=1    # Trust X-Forwarded-Prefix (sets SCRIPT_NAME for url_for)
)

from app import routes
from app import chat_routes

# Log service startup
helm_logger.info(f"{app.config['SERVICE_NAME']} service started")
