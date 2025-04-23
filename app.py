from flask import Flask, request, redirect, jsonify, render_template, url_for, flash, send_from_directory
import uuid
import secrets
from datetime import datetime
import os
import json
from urllib.parse import urlencode
from dotenv import load_dotenv
import logging
import threading
from flask_wtf.csrf import CSRFProtect, generate_csrf, validate_csrf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',
    filemode='a'
)
logger = logging.getLogger('crypto_payment_app')

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Import configuration
from config import config

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['WTF_CSRF_ENABLED'] = True

# Configure the app based on environment
env = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[env])

# Import our services
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from blockchain_verifier import BlockchainVerifier
from email_service import EmailService

# Initialize extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# Initialize services
email_service = EmailService(
    server=app.config.get('EMAIL_SERVER'),
    port=app.config.get('EMAIL_PORT'),
    username=app.config.get('EMAIL_USERNAME'),
    password=app.config.get('EMAIL_PASSWORD'),
    sender=app.config.get('EMAIL_SENDER'),
    use_background_thread=True
)

# Database models
class Transaction(db.Model):
    id = db.Column(db.String(36), primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    network = db.Column(db.String(20), nullable=False)
    client_email = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, completed
    tx_hash = db.Column(db.String(100), nullable=True)  # blockchain transaction hash
    token_type = db.Column(db.String(20), nullable=True)  # For tokens like USDT, USDC, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=True)  # For multi-merchant support

    def __repr__(self):
        return f'<Transaction {self.id}>'
    
    def to_dict(self):
        """Convert transaction to dictionary for API responses"""
        return {
            'id': self.id,
            'amount': self.amount,
            'network': self.network,
            'client_email': self.client_email,
            'description': self.description,
            'status': self.status,
            'tx_hash': self.tx_hash,
            'token_type': self.token_type,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'merchant_id': self.merchant_id
        }

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='user')  # admin, user
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Set password hash for security"""
        # In a real app, use proper password hashing
        import hashlib
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        """Check if password matches"""
        import hashlib
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

class WalletAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    network = db.Column(db.String(20), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    label = db.Column(db.String(100), nullable=True)
    token_type = db.Column(db.String(20), nullable=True)  # For tokens like USDT, USDC, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=True)  # For multi-merchant support
    
    __table_args__ = (db.UniqueConstraint('network', 'merchant_id', name='_wallet_network_merchant_uc'),)

    def __repr__(self):
        token_str = f" ({self.token_type})" if self.token_type else ""
        return f'<WalletAddress {self.network}{token_str}: {self.address}>'

class BlockchainAPIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    network = db.Column(db.String(20), unique=True, nullable=False)
    api_key = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<BlockchainAPIKey {self.network}>'

# New model for merchants (for multi-merchant support)
class Merchant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    api_key = db.Column(db.String(64), unique=True, nullable=False)
    api_secret = db.Column(db.String(64), nullable=False)
    webhook_url = db.Column(db.String(255), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)
    ip_whitelist = db.Column(db.Text, nullable=True)  # Comma-separated list of allowed IPs
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationship with transactions
    transactions = db.relationship('Transaction', backref='merchant', lazy=True)
    
    # Define relationship with wallet addresses
    wallets = db.relationship('WalletAddress', backref='merchant', lazy=True)
    
    def __repr__(self):
        return f'<Merchant {self.name}>'
    
    def to_dict(self):
        """Convert merchant to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'webhook_url': self.webhook_url,
            'two_factor_enabled': self.two_factor_enabled,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Subscription model for recurring payments
class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=False)
    client_email = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    network = db.Column(db.String(20), nullable=False)
    token_type = db.Column(db.String(20), nullable=True)
    frequency = db.Column(db.String(20), nullable=False)  # daily, weekly, monthly, yearly
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=True)  # null for open-ended subscriptions
    next_payment_date = db.Column(db.DateTime, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, paused, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationship with merchant
    merchant = db.relationship('Merchant', backref='subscriptions', lazy=True)
    
    def __repr__(self):
        return f'<Subscription {self.id} - {self.amount} {self.network} {self.frequency}>'
    
    def to_dict(self):
        """Convert subscription to dictionary for API responses"""
        return {
            'id': self.id,
            'merchant_id': self.merchant_id,
            'client_email': self.client_email,
            'amount': self.amount,
            'network': self.network,
            'token_type': self.token_type,
            'frequency': self.frequency,
            'start_date': self.start_date.strftime('%Y-%m-%d %H:%M:%S'),
            'end_date': self.end_date.strftime('%Y-%m-%d %H:%M:%S') if self.end_date else None,
            'next_payment_date': self.next_payment_date.strftime('%Y-%m-%d %H:%M:%S'),
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

# Audit log for security tracking
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    merchant_id = db.Column(db.Integer, db.ForeignKey('merchant.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 addresses can be up to 45 chars
    user_agent = db.Column(db.String(255), nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Define relationship with merchant
    merchant = db.relationship('Merchant', backref='audit_logs', lazy=True)
    
    def __repr__(self):
        return f'<AuditLog {self.id} - {self.action}>'

# Initialize payment processor
from payment_processor import PaymentProcessor

# Create tables and initialize data
def initialize_app():
    """Initialize application with default data"""
    try:
        # Create tables if they don't exist
        with app.app_context():
            db.create_all()
            
            # Check if we already have some wallets configured
            wallet_query = WalletAddress.query.filter_by(network='btc')
            wallet = wallet_query.first()
            
            if not wallet:
                # Add default wallet addresses for testing
                default_wallets = [
                    WalletAddress(
                        network='btc',
                        address='1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa',
                        label='Bitcoin'
                    ),
                    WalletAddress(
                        network='eth',
                        address='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
                        label='Ethereum'
                    ),
                    WalletAddress(
                        network='bnb',
                        address='bnb1jxfh2g85q3v0tdq56fnevx6xcxtcnhtsmcu64m',
                        label='Binance Coin'
                    ),
                    WalletAddress(
                        network='sol',
                        address='HN7cABqLq46Es1jh92dQQisAq662SmxELLLsHHe4YWrH',
                        label='Solana'
                    ),
                    WalletAddress(
                        network='trx',
                        address='TJmKPH6rSgNoMWrX1GemhcDE8G6qEUVHDV',
                        label='Tron'
                    ),
                    WalletAddress(
                        network='bnb_usdt',
                        address='bnb1jxfh2g85q3v0tdq56fnevx6xcxtcnhtsmcu64m',
                        label='USDT on BNB Chain'
                    )
                ]
                
                for wallet in default_wallets:
                    db.session.add(wallet)
                
                db.session.commit()
                logger.info("Default wallet addresses added")
                
            # Add admin user if one doesn't exist
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    username='admin',
                    email='admin@example.com',
                    role='admin',
                    is_active=True
                )
                admin.set_password('admin123')  # Never use this in production
                db.session.add(admin)
                db.session.commit()
                logger.info("Default admin user created")
    except Exception as e:
        logger.error(f"Error initializing app: {str(e)}")

# Call initialize_app with the app context
with app.app_context():
    initialize_app()

# Helper functions
def get_wallet_addresses():
    """Get all wallet addresses from database as a dictionary"""
    wallets = WalletAddress.query.all()
    return {wallet.network: wallet.address for wallet in wallets}

def get_api_keys():
    """Get all API keys from database as a dictionary"""
    keys = BlockchainAPIKey.query.all()
    return {key.network: key.api_key for key in keys}

def generate_payment_link(transaction_id, amount, network, description=None):
    """Generate a payment link with transaction ID and amount"""
    base_url = request.host_url.rstrip('/')
    params = {
        'amount': amount,
        'network': network
    }
    if description:
        params['description'] = description
        
    payment_link = f"{base_url}/confirm_payment/{transaction_id}?{urlencode(params)}"
    return payment_link

def generate_trust_wallet_uri(network, address, amount, description=None):
    """Generate Trust Wallet URI for direct payment with enhanced parameters"""
    # Map our network names to Trust Wallet asset codes and contract addresses
    asset_map = {
        'bnb': {
            'coin': '714',
            'token': 'BNB',
            'contract': None
        },
        'eth': {
            'coin': '60',
            'token': 'ETH',
            'contract': None
        },
        'sol': {
            'coin': '501',
            'token': 'SOL',
            'contract': None
        },
        'btc': {
            'coin': '0',
            'token': 'BTC',
            'contract': None
        },
        'trx': {
            'coin': '195',
            'token': 'TRX',
            'contract': None
        },
        'bnb_usdt': {
            'coin': '714',
            'token': 'USDT',
            'contract': '0x55d398326f99059fF775485246999027B3197955'
        },
        'eth_usdt': {
            'coin': '60',
            'token': 'USDT',
            'contract': '0xdAC17F958D2ee523a2206206994597C13D831ec7'
        },
        'trx_usdt': {
            'coin': '195',
            'token': 'USDT',
            'contract': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t'
        }
    }
    
    # Validate network
    if network not in asset_map:
        raise ValueError(f"Unsupported network: {network}")
    
    # Get asset info
    asset_info = asset_map[network]
    
    # Format amount to avoid scientific notation and validate
    try:
        formatted_amount = "{:.8f}".format(float(amount)).rstrip('0').rstrip('.')
        if float(formatted_amount) <= 0:
            raise ValueError("Amount must be greater than 0")
    except ValueError as e:
        raise ValueError(f"Invalid amount format: {str(e)}")
    
    # Generate transaction ID for tracking
    tx_id = secrets.token_hex(8)
    
    # Create transaction record
    transaction = Transaction(
        id=tx_id,
        amount=float(amount),
        network=network,
        client_email='',
        status='pending',
        description=description,
        tx_hash=None
    )
    db.session.add(transaction)
    db.session.commit()
    
    # Build base parameters - use the proper format Trust Wallet expects
    params = {
        'coin': asset_info['coin'],
        'address': address,
        'amount': formatted_amount,
        'action': 'pay',  # Changed from 'transfer' to 'pay' for direct payment
        'token': asset_info['token']
    }
    
    # Add contract address for tokens
    if asset_info['contract']:
        params['contract'] = asset_info['contract']
    
    # Add description as memo if provided
    if description:
        params['memo'] = description
    
    # Add callback URL to handle the payment confirmation
    callback_url = request.host_url.rstrip('/') + f"/payment_callback/{tx_id}"
    params['callback'] = callback_url
    
    # Add additional parameters for better tracking
    params.update({
        'tx_id': tx_id,
        'timestamp': str(int(datetime.utcnow().timestamp())),
        'version': '1.0'
    })
    
    # Generate both direct and web URLs
    # The trust:// protocol will open Trust Wallet directly if installed
    direct_url = f"trust://wallet/v1/pay?{urlencode(params)}"
    web_url = f"https://link.trustwallet.com/pay?{urlencode(params)}"
    
    # Return both URLs and transaction ID
    return {
        'direct_url': direct_url,
        'web_url': web_url,
        'transaction_id': tx_id
    }

def send_payment_link_email(to_email, payment_link, amount, network, description=None):
    """Send email with payment link to the client"""
    return email_service.send_payment_link(to_email, payment_link, amount, network, description)

def send_payment_confirmation_email(to_email, transaction_id, amount, network, tx_hash=None):
    """Send payment confirmation email to the client"""
    return email_service.send_payment_confirmation(to_email, transaction_id, amount, network, tx_hash)

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/landing')
def landing():
    """Serve the landing page"""
    return send_from_directory('static', 'landing.html')

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard"""
    wallet_addresses = get_wallet_addresses()
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).limit(10).all()
    return render_template('admin.html', wallets=wallet_addresses, transactions=transactions)

@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    """Admin settings page"""
    if request.method == 'POST':
        # Handle API key updates
        api_keys = {}
        for key in request.form:
            if key.endswith('_api_key'):
                network = key.replace('_api_key', '')
                api_keys[network] = request.form[key]
        
        # Update API keys in database
        for network, api_key in api_keys.items():
            if api_key.strip():  # Only update non-empty keys
                existing = BlockchainAPIKey.query.filter_by(network=network).first()
                if existing:
                    existing.api_key = api_key
                else:
                    new_key = BlockchainAPIKey(network=network, api_key=api_key)
                    db.session.add(new_key)
        
        db.session.commit()
        flash('API keys updated successfully', 'success')
        
        # Restart payment processor with new API keys
        if 'payment_processor' in globals():
            payment_processor.stop()
            payment_processor.api_keys = get_api_keys()
            payment_processor.start()
            
        return redirect(url_for('admin_settings'))
    
    # GET request - show form
    api_keys = get_api_keys()
    return render_template('admin_settings.html', api_keys=api_keys)

@app.route('/send_payment_link', methods=['GET', 'POST'])
def send_payment_link():
    if request.method == 'POST':
        try:
            # Validate CSRF token
            csrf_token = request.form.get('csrf_token')
            if not csrf_token:
                return jsonify({
                    'success': False,
                    'error': 'CSRF token is missing'
                }), 400

            try:
                validate_csrf(csrf_token)
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': 'Invalid CSRF token'
                }), 400

            # Get form data
            amount = request.form.get('amount')
            network = request.form.get('network')
            description = request.form.get('description')

            # Validate required fields
            if not amount or not network:
                return jsonify({
                    'success': False,
                    'error': 'Amount and network are required'
                }), 400

            # Convert amount to float
            try:
                amount = float(amount)
                if amount <= 0:
                    raise ValueError("Amount must be greater than 0")
            except ValueError as e:
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 400

            # Get wallet address for the selected network
            wallet = WalletAddress.query.filter_by(network=network).first()
            if not wallet:
                return jsonify({
                    'success': False,
                    'error': f'No wallet address configured for {network}'
                }), 400

            # Generate payment links
            result = generate_trust_wallet_uri(
                network=network,
                address=wallet.address,
                amount=amount,
                description=description
            )

            return jsonify({
                'success': True,
                'message': 'Payment links generated successfully',
                'direct_url': result['direct_url'],
                'web_url': result['web_url'],
                'transaction_id': result['transaction_id']
            })

        except Exception as e:
            logger.error(f"Error generating payment link: {str(e)}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # GET request - show form
    return render_template('send_link.html', csrf_token=generate_csrf())

@app.route('/api/generate_link', methods=['POST'])
def api_generate_link():
    """API endpoint to generate payment link"""
    amount = request.form.get('amount')
    client_email = request.form.get('client_email')
    network = request.form.get('network', 'ethereum')
    description = request.form.get('description')
    
    # Validate input
    if not amount or not client_email or not network:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        amount = float(amount)
    except ValueError:
        return jsonify({'error': 'Invalid amount'}), 400
        
    wallet_addresses = get_wallet_addresses()
    if network not in wallet_addresses:
        return jsonify({'error': 'Unsupported network'}), 400
    
    # Create transaction record
    transaction_id = str(uuid.uuid4())
    transaction = Transaction(
        id=transaction_id,
        amount=amount,
        network=network,
        client_email=client_email,
        description=description
    )
    db.session.add(transaction)
    db.session.commit()
    
    # Generate payment link
    payment_link = generate_payment_link(transaction_id, amount, network, description)
    
    return jsonify({
        'success': True,
        'transaction_id': transaction_id,
        'payment_link': payment_link
    })

@app.route('/api/send_email', methods=['POST'])
def api_send_email():
    """API endpoint to send payment link email"""
    data = request.json
    transaction_id = data.get('transaction_id')
    client_email = data.get('client_email')
    payment_link = data.get('payment_link')
    
    if not transaction_id or not client_email or not payment_link:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Get transaction details
    transaction = Transaction.query.get(transaction_id)
    if not transaction:
        return jsonify({'error': 'Transaction not found'}), 404
    
    # Send email
    if send_payment_link_email(client_email, payment_link, transaction.amount, transaction.network, transaction.description):
        return jsonify({
            'success': True,
            'message': f'Email sent to {client_email}'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to send email'
        }), 500

@app.route('/update_wallet_addresses', methods=['POST'])
def update_wallet_addresses():
    """Update wallet addresses"""
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        for network, address in data.items():
            if not address.strip():
                continue
                
            wallet = WalletAddress.query.filter_by(network=network).first()
            if wallet:
                wallet.address = address
            else:
                wallet = WalletAddress(network=network, address=address)
                db.session.add(wallet)
        
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/confirm_payment/<transaction_id>', methods=['GET'])
def confirm_payment(transaction_id):
    """Process payment confirmation"""
    try:
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if not transaction:
            logger.error(f"Payment confirmation: Transaction not found: {transaction_id}")
            return render_template('error.html', message="Transaction not found"), 404
        
        # Get URL parameters
        amount = request.args.get('amount', transaction.amount)
        network = request.args.get('network', transaction.network)
        description = request.args.get('description', transaction.description)
        
        # Check if we're on a mobile device that might have Trust Wallet installed
        user_agent = request.headers.get('User-Agent', '').lower()
        is_mobile = 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent or 'ipad' in user_agent
        
        # Check if we should attempt direct Trust Wallet integration
        trust_wallet_uri = None
        if is_mobile:
            try:
                # Get wallet address for receiving payment - use only network filter
                wallet_query = WalletAddress.query.filter_by(
                    network=network
                )
                wallet = wallet_query.first()
                
                if wallet:
                    # Generate Trust Wallet URI
                    uri_data = generate_trust_wallet_uri(
                        network=network,
                        address=wallet.address,
                        amount=amount,
                        description=description
                    )
                    trust_wallet_uri = uri_data['direct_url']
                    
                    # Redirect directly to Trust Wallet if we're on mobile
                    return redirect(trust_wallet_uri)
            except Exception as e:
                logger.error(f"Error generating Trust Wallet URI: {str(e)}")
                # Fall back to standard flow if there's an error
        
        # Standard flow - first show signing page before proceeding
        return redirect(url_for('sign_protocol', transaction_id=transaction_id))
    
    except Exception as e:
        logger.error(f"Error in confirm payment: {str(e)}")
        return render_template('error.html', message="An error occurred processing your payment"), 500

@app.route('/sign_protocol/<transaction_id>', methods=['GET', 'POST'])
@csrf.exempt  # Exempt this route from CSRF (you should implement proper protection)
def sign_protocol(transaction_id):
    """Handle the signing protocol for cryptocurrency transactions"""
    try:
        # Get the transaction
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404
        
        # If POST request, process the signed protocol
        if request.method == 'POST':
            data = request.get_json()
            signature = data.get('signature')
            
            if not signature:
                return jsonify({"error": "Missing signature"}), 400
            
            # In a real-world scenario, you would verify the signature here
            # For now, we'll assume the signature is valid and trigger the payment
            
            # Get the wallet address for this transaction's network
            # Use only network filter to avoid token_type column issue
            wallet_query = WalletAddress.query.filter_by(
                network=transaction.network
            )
            wallet = wallet_query.first()
            
            if not wallet:
                return jsonify({"error": f"No wallet found for {transaction.network}"}), 400
            
            # Create Trust Wallet URI for immediate payment
            payment_info = generate_trust_wallet_uri(
                network=transaction.network,
                address=wallet.address,
                amount=transaction.amount,
                description=transaction.description
            )
            
            # Update transaction status to 'signed'
            transaction.status = 'signed'
            db.session.commit()
            
            # Immediately mark the transaction as confirmed without requiring additional steps
            # This simulates automatic payment processing once protocol is signed
            transaction.status = 'confirmed'
            transaction.updated_at = datetime.utcnow()
            db.session.commit()
            
            # Return success with payment link and redirect to success page
            return jsonify({
                "success": True, 
                "payment_link": payment_info['direct_url'],
                "web_link": payment_info['web_url'],
                "auto_payment": True,
                "redirect_url": url_for('payment_success', transaction_id=transaction_id)
            })
        
        # GET request - render template
        return render_template(
            'sign_protocol.html',
            transaction_id=transaction_id,
            amount=transaction.amount,
            network=transaction.network,
            description=transaction.description
        )
        
    except Exception as e:
        logger.error(f"Error in sign protocol: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Add a new route for payment success page
@app.route('/payment_success/<transaction_id>')
def payment_success(transaction_id):
    """Show payment success page"""
    try:
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if not transaction:
            return render_template('error.html', message="Transaction not found"), 404
        
        return render_template(
            'payment_success.html',
            transaction_id=transaction_id,
            amount=transaction.amount,
            network=transaction.network,
            description=transaction.description
        )
    except Exception as e:
        logger.error(f"Error in payment success: {str(e)}")
        return render_template('error.html', message="An error occurred"), 500

@app.route('/admin/transactions')
def view_transactions():
    """Admin view to see all transactions"""
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return render_template('transactions.html', transactions=transactions)

@app.route('/api/transactions')
def api_transactions():
    """API endpoint to get all transactions"""
    transactions = Transaction.query.order_by(Transaction.created_at.desc()).all()
    return jsonify({
        'transactions': [t.to_dict() for t in transactions]
    })

@app.route('/api/server-info')
def server_info():
    """API endpoint to get server information"""
    host = request.host
    wallet_addresses = get_wallet_addresses()
    return jsonify({
        'success': True,
        'host': host,
        'environment': os.environ.get('FLASK_ENV', 'development'),
        'wallet_count': len(wallet_addresses),
        'transaction_count': Transaction.query.count(),
        'automatic_verification': os.environ.get('SIMULATION_MODE', 'true').lower() == 'true'
    })

@app.route('/api/verify-pending')
def api_verify_pending():
    """API endpoint to manually trigger verification of pending transactions"""
    if 'payment_processor' in globals():
        # Trigger a manual check
        threading.Thread(target=payment_processor.process_pending_transactions).start()
        return jsonify({
            'success': True,
            'message': 'Verification process triggered'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Payment processor not initialized'
        }), 500

@app.route('/payment_callback/<transaction_id>', methods=['GET', 'POST'])
def payment_callback(transaction_id):
    """Handle callback from Trust Wallet after payment is made"""
    try:
        # Get the transaction
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        if not transaction:
            logger.error(f"Payment callback: Transaction not found: {transaction_id}")
            return jsonify({"error": "Transaction not found"}), 404
        
        # For automatic processing, mark as completed immediately since we've already
        # confirmed it in the sign_protocol step
        if transaction.status == 'confirmed':
            # Transaction has already been confirmed in sign_protocol step
            logger.info(f"Transaction {transaction_id} already confirmed, proceeding to success")
            return redirect(url_for('payment_success', transaction_id=transaction_id))
        
        # Check if we're getting POST data (Trust Wallet sends transaction details)
        if request.method == 'POST':
            data = request.get_json()
            tx_hash = data.get('tx_hash')
            status = data.get('status')
            
            if tx_hash or status == 'completed':
                # Update transaction with confirmed status and hash
                transaction.status = 'completed'
                if tx_hash:
                    transaction.tx_hash = tx_hash
                transaction.updated_at = datetime.utcnow()
                db.session.commit()
                
                # Send confirmation email if client email exists
                if transaction.client_email:
                    send_payment_confirmation_email(
                        transaction.client_email,
                        transaction.id,
                        transaction.amount,
                        transaction.network,
                        tx_hash or "Auto-processed"
                    )
                
                logger.info(f"Payment confirmed for transaction {transaction_id}: {tx_hash or 'Auto-processed'}")
                return jsonify({"success": True, "status": "completed"}), 200
            else:
                # Handle failed or pending transaction
                logger.warning(f"Payment callback with status {status} for transaction {transaction_id}")
                return jsonify({"success": False, "status": status}), 200
                
        # For GET requests, redirect to payment success page
        return redirect(url_for('payment_success', transaction_id=transaction_id))
        
    except Exception as e:
        logger.error(f"Error in payment callback: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', message="Server error, please try again later"), 500

# Cleanup when shutting down
@app.teardown_appcontext
def shutdown_services(exception=None):
    if 'payment_processor' in globals() and hasattr(payment_processor, 'stop'):
        payment_processor.stop()
    
    if hasattr(email_service, 'stop'):
        email_service.stop()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9000, debug=app.config['DEBUG']) 