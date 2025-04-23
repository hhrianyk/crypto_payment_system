import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Wallet, db
from eth_account import Account
import secrets

wallet_bp = Blueprint('wallet', __name__)

@wallet_bp.route('/', methods=['POST'])
@jwt_required()
def create_wallet():
    """Create a new wallet for the authenticated user"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        currency = data.get('currency', 'ETH')
        
        # Generate wallet address and private key
        private_key = "0x" + secrets.token_hex(32)
        account = Account.from_key(private_key)
        address = account.address
        
        wallet = Wallet(
            id=str(uuid.uuid4()),
            user_id=user_id,
            address=address,
            private_key=private_key,
            balance=0.0,
            currency=currency
        )
        
        db.session.add(wallet)
        db.session.commit()
        
        return jsonify(wallet.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@wallet_bp.route('/', methods=['GET'])
@jwt_required()
def get_user_wallets():
    """Get all wallets for the authenticated user"""
    try:
        user_id = get_jwt_identity()
        wallets = Wallet.query.filter_by(user_id=user_id).all()
        return jsonify([wallet.to_dict() for wallet in wallets]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@wallet_bp.route('/<wallet_id>', methods=['GET'])
@jwt_required()
def get_wallet(wallet_id):
    """Get a specific wallet by ID"""
    try:
        user_id = get_jwt_identity()
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
        
        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404
            
        return jsonify(wallet.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@wallet_bp.route('/<wallet_id>/balance', methods=['GET'])
@jwt_required()
def get_wallet_balance(wallet_id):
    """Get the current balance of a wallet"""
    try:
        user_id = get_jwt_identity()
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
        
        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404
            
        # Here you would typically query the blockchain for real-time balance
        # For now, we'll return the stored balance
        return jsonify({
            "wallet_id": wallet.id,
            "address": wallet.address,
            "balance": wallet.balance,
            "currency": wallet.currency
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@wallet_bp.route('/<wallet_id>/private-key', methods=['GET'])
@jwt_required()
def get_private_key(wallet_id):
    """Get the private key for a wallet (sensitive operation)"""
    try:
        user_id = get_jwt_identity()
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
        
        if not wallet:
            return jsonify({"error": "Wallet not found"}), 404
            
        # Warning: This is sensitive data that should be handled carefully
        # In a production system, additional security measures would be implemented
        return jsonify({
            "wallet_id": wallet.id,
            "address": wallet.address,
            "private_key": wallet.private_key
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500 