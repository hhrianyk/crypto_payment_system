import os
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from prometheus_flask_exporter import PrometheusMetrics
from dotenv import load_dotenv
import pika
import json
import jwt
from web3 import Web3
from eth_account import Account
import secrets
from flask_cors import CORS

# Load environment variables
load_dotenv()

# Initialize SQLAlchemy without binding to an app yet
db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Configure the SQLAlchemy database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///wallet_service.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    
    # Initialize extensions with the app
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Setup Prometheus metrics
    metrics = PrometheusMetrics(app)
    metrics.info('wallet_service_info', 'Wallet service information', version='1.0.0')

    # Connect to Ethereum node
    w3 = Web3(Web3.HTTPProvider(os.getenv('ETHEREUM_NODE_URL', 'https://eth-sepolia.g.alchemy.com/v2/your-api-key')))

    # Connect to RabbitMQ
    def connect_to_rabbitmq():
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=os.getenv('RABBITMQ_HOST', 'rabbitmq'))
            )
            channel = connection.channel()
            channel.queue_declare(queue='wallet_events', durable=True)
            return connection, channel
        except Exception as e:
            app.logger.error(f"Failed to connect to RabbitMQ: {e}")
            return None, None

    # Database models
    class Wallet(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.String(50), unique=True, nullable=False)
        address = db.Column(db.String(42), unique=True, nullable=False)
        private_key = db.Column(db.String(66), unique=True, nullable=False)
        balance = db.Column(db.Float, default=0.0)
        created_at = db.Column(db.DateTime, server_default=db.func.now())
        updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    class Transaction(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        wallet_id = db.Column(db.Integer, db.ForeignKey('wallet.id'), nullable=False)
        tx_hash = db.Column(db.String(66), unique=True, nullable=False)
        amount = db.Column(db.Float, nullable=False)
        status = db.Column(db.String(20), default='pending')
        tx_type = db.Column(db.String(20), nullable=False)
        created_at = db.Column(db.DateTime, server_default=db.func.now())
        updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # Middleware for authentication
    def authenticate():
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None
        
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, os.getenv('JWT_SECRET_KEY', 'your-secret-key'), algorithms=['HS256'])
            return payload
        except Exception as e:
            app.logger.error(f"Authentication error: {e}")
            return None

    # Register blueprints
    from routes.wallet import wallet_bp
    from routes.transaction import transaction_bp
    
    app.register_blueprint(wallet_bp, url_prefix='/api/wallets')
    app.register_blueprint(transaction_bp, url_prefix='/api/transactions')
    
    @app.route('/health')
    def health_check():
        return {'status': 'healthy'}, 200
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) 