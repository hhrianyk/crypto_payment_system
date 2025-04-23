import logging
import pyotp
import qrcode
import io
import base64
import ipaddress
import jwt
import secrets
import time
from functools import wraps
from flask import request, jsonify, current_app, session
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='auth_service.log'
)
logger = logging.getLogger('auth_service')

class AuthService:
    """
    Authentication service with support for 2FA, IP filtering, and JWT token management
    """
    
    def __init__(self, db, jwt_secret=None, token_expiry_minutes=30):
        """
        Initialize auth service
        
        Args:
            db: SQLAlchemy database object
            jwt_secret: Secret key for JWT tokens, defaults to app's SECRET_KEY
            token_expiry_minutes: JWT token expiry time in minutes
        """
        self.db = db
        self.jwt_secret = jwt_secret
        self.token_expiry_minutes = token_expiry_minutes
        self.Merchant = None  # Will be set when initialize() is called
        self.AuditLog = None  # Will be set when initialize() is called
    
    def initialize(self):
        """Initialize auth service with database models"""
        # This prevents circular imports
        try:
            from app import Merchant, AuditLog
            self.Merchant = Merchant
            self.AuditLog = AuditLog
            logger.info("Auth service initialized successfully")
            return True
        except ImportError as e:
            logger.error(f"Error initializing auth service: {str(e)}")
            return False
    
    def _get_jwt_secret(self):
        """Get JWT secret, falling back to app SECRET_KEY if not set"""
        if self.jwt_secret:
            return self.jwt_secret
        return current_app.config.get('SECRET_KEY')
    
    def _log_audit(self, action, merchant_id=None, details=None):
        """Log an action to the audit log"""
        if not self.AuditLog:
            logger.warning("Cannot log audit: AuditLog model not initialized")
            return False
        
        try:
            audit_log = self.AuditLog(
                merchant_id=merchant_id,
                action=action,
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string if request.user_agent else None,
                details=details
            )
            self.db.session.add(audit_log)
            self.db.session.commit()
            return True
        except Exception as e:
            logger.error(f"Error logging audit: {str(e)}")
            self.db.session.rollback()
            return False
    
    def generate_2fa_secret(self, merchant_id, merchant_email):
        """
        Generate a new 2FA secret for a merchant
        
        Args:
            merchant_id: ID of the merchant
            merchant_email: Email of the merchant
        
        Returns:
            dict: Dictionary with secret, provisioning URI, and QR code data URI
        """
        if not self.Merchant:
            logger.error("Cannot generate 2FA secret: Merchant model not initialized")
            return None
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return None
            
            # Generate a new secret
            secret = pyotp.random_base32()
            
            # Create a provisioning URI for the QR code
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=merchant_email,
                issuer_name="Crypto Payment System"
            )
            
            # Generate a QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert image to data URI
            buffered = io.BytesIO()
            img.save(buffered)
            qr_code_data = base64.b64encode(buffered.getvalue()).decode("utf-8")
            qr_code_data_uri = f"data:image/png;base64,{qr_code_data}"
            
            # Store the secret in the merchant record
            merchant.two_factor_secret = secret
            self.db.session.commit()
            
            # Log the action
            self._log_audit(
                action="2fa_secret_generated",
                merchant_id=merchant_id,
                details="New 2FA secret generated"
            )
            
            return {
                'secret': secret,
                'provisioning_uri': provisioning_uri,
                'qr_code': qr_code_data_uri
            }
            
        except Exception as e:
            logger.error(f"Error generating 2FA secret: {str(e)}")
            self.db.session.rollback()
            return None
    
    def verify_2fa_code(self, merchant_id, code):
        """
        Verify a 2FA code for a merchant
        
        Args:
            merchant_id: ID of the merchant
            code: 2FA code to verify
        
        Returns:
            bool: True if code is valid, False otherwise
        """
        if not self.Merchant:
            logger.error("Cannot verify 2FA code: Merchant model not initialized")
            return False
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return False
            
            # Check if 2FA is enabled
            if not merchant.two_factor_enabled or not merchant.two_factor_secret:
                logger.warning(f"2FA not enabled for merchant {merchant_id}")
                return False
            
            # Verify the code
            totp = pyotp.TOTP(merchant.two_factor_secret)
            result = totp.verify(code)
            
            # Log the result
            self._log_audit(
                action="2fa_code_verified" if result else "2fa_code_invalid",
                merchant_id=merchant_id,
                details=f"2FA code verification: {'success' if result else 'failure'}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error verifying 2FA code: {str(e)}")
            return False
    
    def enable_2fa(self, merchant_id, code):
        """
        Enable 2FA for a merchant after verifying a code
        
        Args:
            merchant_id: ID of the merchant
            code: 2FA code to verify
        
        Returns:
            bool: True if 2FA was enabled, False otherwise
        """
        if not self.Merchant:
            logger.error("Cannot enable 2FA: Merchant model not initialized")
            return False
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return False
            
            # Check if secret exists
            if not merchant.two_factor_secret:
                logger.error(f"2FA secret not found for merchant {merchant_id}")
                return False
            
            # Verify the code
            totp = pyotp.TOTP(merchant.two_factor_secret)
            if not totp.verify(code):
                logger.warning(f"Invalid 2FA code for merchant {merchant_id}")
                return False
            
            # Enable 2FA
            merchant.two_factor_enabled = True
            self.db.session.commit()
            
            # Log the action
            self._log_audit(
                action="2fa_enabled",
                merchant_id=merchant_id,
                details="2FA enabled for merchant"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error enabling 2FA: {str(e)}")
            self.db.session.rollback()
            return False
    
    def disable_2fa(self, merchant_id, admin_override=False):
        """
        Disable 2FA for a merchant
        
        Args:
            merchant_id: ID of the merchant
            admin_override: If True, allow admin to disable 2FA without verification
        
        Returns:
            bool: True if 2FA was disabled, False otherwise
        """
        if not self.Merchant:
            logger.error("Cannot disable 2FA: Merchant model not initialized")
            return False
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return False
            
            # Disable 2FA
            merchant.two_factor_enabled = False
            self.db.session.commit()
            
            # Log the action
            self._log_audit(
                action="2fa_disabled",
                merchant_id=merchant_id,
                details=f"2FA disabled for merchant {'by admin' if admin_override else ''}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error disabling 2FA: {str(e)}")
            self.db.session.rollback()
            return False
    
    def is_ip_allowed(self, merchant_id, ip_address=None):
        """
        Check if an IP address is allowed for a merchant
        
        Args:
            merchant_id: ID of the merchant
            ip_address: IP address to check, defaults to request.remote_addr
        
        Returns:
            bool: True if IP is allowed, False otherwise
        """
        if not self.Merchant:
            logger.error("Cannot check IP: Merchant model not initialized")
            return False
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return False
            
            # If no IP whitelist, allow all
            if not merchant.ip_whitelist:
                return True
            
            # Use request IP if none provided
            if not ip_address:
                ip_address = request.remote_addr
            
            # Parse IP address
            try:
                client_ip = ipaddress.ip_address(ip_address)
            except ValueError:
                logger.error(f"Invalid IP address: {ip_address}")
                return False
            
            # Check against whitelist
            for allowed_ip in merchant.ip_whitelist.split(','):
                allowed_ip = allowed_ip.strip()
                if not allowed_ip:
                    continue
                
                # Check if it's a network range (CIDR)
                if '/' in allowed_ip:
                    try:
                        network = ipaddress.ip_network(allowed_ip, strict=False)
                        if client_ip in network:
                            return True
                    except ValueError:
                        logger.warning(f"Invalid network range: {allowed_ip}")
                else:
                    # Direct IP comparison
                    try:
                        if client_ip == ipaddress.ip_address(allowed_ip):
                            return True
                    except ValueError:
                        logger.warning(f"Invalid IP address in whitelist: {allowed_ip}")
            
            # IP not in whitelist
            self._log_audit(
                action="ip_blocked",
                merchant_id=merchant_id,
                details=f"Access denied from IP {ip_address}"
            )
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking IP whitelist: {str(e)}")
            return False
    
    def update_ip_whitelist(self, merchant_id, ip_whitelist):
        """
        Update IP whitelist for a merchant
        
        Args:
            merchant_id: ID of the merchant
            ip_whitelist: Comma-separated list of allowed IPs
        
        Returns:
            bool: True if whitelist was updated, False otherwise
        """
        if not self.Merchant:
            logger.error("Cannot update IP whitelist: Merchant model not initialized")
            return False
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return False
            
            # Validate IP addresses and networks
            ips = []
            for ip in ip_whitelist.split(','):
                ip = ip.strip()
                if not ip:
                    continue
                
                try:
                    if '/' in ip:
                        # Network range
                        ipaddress.ip_network(ip, strict=False)
                    else:
                        # Single IP
                        ipaddress.ip_address(ip)
                    
                    ips.append(ip)
                except ValueError:
                    logger.warning(f"Invalid IP address or network: {ip}")
            
            # Update merchant record
            merchant.ip_whitelist = ','.join(ips)
            self.db.session.commit()
            
            # Log the action
            self._log_audit(
                action="ip_whitelist_updated",
                merchant_id=merchant_id,
                details=f"IP whitelist updated: {merchant.ip_whitelist}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating IP whitelist: {str(e)}")
            self.db.session.rollback()
            return False
    
    def generate_jwt_token(self, merchant_id, expiry_minutes=None):
        """
        Generate a JWT token for a merchant
        
        Args:
            merchant_id: ID of the merchant
            expiry_minutes: Token expiry time in minutes, defaults to self.token_expiry_minutes
        
        Returns:
            str: JWT token
        """
        if not self.Merchant:
            logger.error("Cannot generate token: Merchant model not initialized")
            return None
        
        try:
            # Get merchant record
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                logger.error(f"Merchant not found: {merchant_id}")
                return None
            
            # Set expiry time
            exp_time = datetime.utcnow() + timedelta(minutes=expiry_minutes or self.token_expiry_minutes)
            
            # Create token payload
            payload = {
                'sub': merchant_id,
                'email': merchant.email,
                'name': merchant.name,
                'exp': exp_time,
                'iat': datetime.utcnow(),
                'jti': secrets.token_hex(16)  # JWT ID for uniqueness
            }
            
            # Generate token
            token = jwt.encode(
                payload,
                self._get_jwt_secret(),
                algorithm='HS256'
            )
            
            # Log the action
            self._log_audit(
                action="token_generated",
                merchant_id=merchant_id,
                details=f"JWT token generated with expiry at {exp_time.isoformat()}"
            )
            
            return token
            
        except Exception as e:
            logger.error(f"Error generating JWT token: {str(e)}")
            return None
    
    def verify_jwt_token(self, token):
        """
        Verify a JWT token
        
        Args:
            token: JWT token to verify
        
        Returns:
            dict: Token payload if valid, None otherwise
        """
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self._get_jwt_secret(),
                algorithms=['HS256']
            )
            
            # Get merchant ID
            merchant_id = payload.get('sub')
            
            # Log the action
            self._log_audit(
                action="token_verified",
                merchant_id=merchant_id,
                details="JWT token verified successfully"
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error verifying JWT token: {str(e)}")
            return None
    
    def authenticate_merchant(self, email, api_key, api_secret):
        """
        Authenticate a merchant using API credentials
        
        Args:
            email: Merchant email
            api_key: Merchant API key
            api_secret: Merchant API secret
        
        Returns:
            tuple: (bool success, merchant object or None, error message or None)
        """
        if not self.Merchant:
            logger.error("Cannot authenticate: Merchant model not initialized")
            return False, None, "Authentication service not initialized"
        
        try:
            # Find merchant by email
            merchant = self.Merchant.query.filter_by(email=email).first()
            if not merchant:
                return False, None, "Merchant not found"
            
            # Check if merchant is active
            if not merchant.is_active:
                self._log_audit(
                    action="auth_failed_inactive",
                    merchant_id=merchant.id,
                    details="Authentication attempt for inactive merchant"
                )
                return False, None, "Merchant account is inactive"
            
            # Check API credentials
            if merchant.api_key != api_key or merchant.api_secret != api_secret:
                self._log_audit(
                    action="auth_failed_invalid_credentials",
                    merchant_id=merchant.id,
                    details="Authentication attempt with invalid credentials"
                )
                return False, None, "Invalid API credentials"
            
            # Log successful authentication
            self._log_audit(
                action="auth_success",
                merchant_id=merchant.id,
                details="Merchant authenticated successfully"
            )
            
            return True, merchant, None
            
        except Exception as e:
            logger.error(f"Error authenticating merchant: {str(e)}")
            return False, None, f"Authentication error: {str(e)}"
    
    def require_auth(self, f):
        """
        Decorator to require authentication for API routes
        
        Usage:
            @auth_service.require_auth
            def protected_route():
                # This route requires authentication
                return jsonify({'message': 'You are authenticated'})
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            # Check Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({'error': 'Authorization header is missing'}), 401
            
            # Extract token
            parts = auth_header.split()
            if parts[0].lower() != 'bearer' or len(parts) != 2:
                return jsonify({'error': 'Invalid authorization header format'}), 401
            
            token = parts[1]
            
            # Verify token
            payload = self.verify_jwt_token(token)
            if not payload:
                return jsonify({'error': 'Invalid or expired token'}), 401
            
            # Get merchant
            merchant_id = payload.get('sub')
            merchant = self.Merchant.query.get(merchant_id)
            if not merchant:
                return jsonify({'error': 'Merchant not found'}), 401
            
            # Check if merchant is active
            if not merchant.is_active:
                return jsonify({'error': 'Merchant account is inactive'}), 401
            
            # Check IP whitelist
            if not self.is_ip_allowed(merchant_id):
                return jsonify({'error': 'Access denied from this IP address'}), 403
            
            # Store merchant in request context
            request.merchant = merchant
            
            # Call the original function
            return f(*args, **kwargs)
        
        return decorated
    
    def require_admin(self, f):
        """
        Decorator to require admin authentication for API routes
        
        Usage:
            @auth_service.require_admin
            def admin_route():
                # This route requires admin authentication
                return jsonify({'message': 'You are an admin'})
        """
        @wraps(f)
        def decorated(*args, **kwargs):
            # Check if merchant is authenticated
            if not hasattr(request, 'merchant'):
                return jsonify({'error': 'Authentication required'}), 401
            
            # Check if merchant is admin
            # Implement your admin check logic here, e.g., by role or special flag
            # For now, we'll just check if the merchant email contains 'admin'
            if 'admin' not in request.merchant.email:
                return jsonify({'error': 'Admin access required'}), 403
            
            # Call the original function
            return f(*args, **kwargs)
        
        return decorated

# Example usage
if __name__ == "__main__":
    # This code would typically run in the context of a Flask app
    from app import app, db, Merchant, AuditLog
    
    with app.app_context():
        auth_service = AuthService(db)
        auth_service.initialize()
        
        # Generate a 2FA secret for a merchant
        merchant = Merchant.query.first()
        if merchant:
            result = auth_service.generate_2fa_secret(merchant.id, merchant.email)
            print(f"2FA Secret: {result['secret']}")
            print(f"Provisioning URI: {result['provisioning_uri']}") 