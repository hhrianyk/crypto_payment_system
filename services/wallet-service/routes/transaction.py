import uuid
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Transaction, Wallet, db
from web3 import Web3
import os

transaction_bp = Blueprint('transaction', __name__)

# Initialize Web3 with an Ethereum provider
w3 = Web3(Web3.HTTPProvider(os.getenv('ETHEREUM_NODE_URL', 'https://mainnet.infura.io/v3/your-infura-key')))

@transaction_bp.route('/send', methods=['POST'])
@jwt_required()
def create_transaction():
    """Create a new transaction to send cryptocurrency"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['wallet_id', 'to_address', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        wallet_id = data['wallet_id']
        to_address = data['to_address']
        amount = float(data['amount'])
        gas_price = data.get('gas_price')  # Optional
        gas_limit = data.get('gas_limit', 21000)  # Default gas limit
        
        # Verify wallet ownership
        wallet = Wallet.query.filter_by(id=wallet_id, user_id=user_id).first()
        if not wallet:
            return jsonify({"error": "Wallet not found or not owned by user"}), 404
        
        # Verify sufficient balance
        if wallet.balance < amount:
            return jsonify({"error": "Insufficient funds"}), 400
            
        # In a real implementation, this would sign and broadcast the transaction
        # to the blockchain network. Here we just create a record.
        
        # Create transaction record
        transaction = Transaction(
            id=str(uuid.uuid4()),
            wallet_id=wallet_id,
            from_address=wallet.address,
            to_address=to_address,
            amount=amount,
            status='pending',
            gas_price=gas_price,
            gas_limit=gas_limit
        )
        
        # Update wallet balance (in a real implementation this would happen 
        # after blockchain confirmation)
        wallet.balance -= amount
        
        db.session.add(transaction)
        db.session.commit()
        
        # In a real implementation, you would now broadcast the transaction
        # and update its status based on blockchain confirmation
        
        return jsonify(transaction.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/', methods=['GET'])
@jwt_required()
def get_user_transactions():
    """Get all transactions for the authenticated user's wallets"""
    try:
        user_id = get_jwt_identity()
        
        # Get all user's wallets
        wallets = Wallet.query.filter_by(user_id=user_id).all()
        wallet_ids = [wallet.id for wallet in wallets]
        
        # Get transactions for these wallets
        transactions = Transaction.query.filter(Transaction.wallet_id.in_(wallet_ids)).all()
        
        return jsonify([tx.to_dict() for tx in transactions]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/<transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    """Get details of a specific transaction"""
    try:
        user_id = get_jwt_identity()
        
        # Get transaction
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        
        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404
            
        # Verify ownership
        wallet = Wallet.query.filter_by(id=transaction.wallet_id).first()
        if not wallet or wallet.user_id != user_id:
            return jsonify({"error": "Transaction not found or not owned by user"}), 404
            
        return jsonify(transaction.to_dict()), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@transaction_bp.route('/<transaction_id>/status', methods=['GET'])
@jwt_required()
def get_transaction_status(transaction_id):
    """Get current status of a transaction"""
    try:
        user_id = get_jwt_identity()
        
        # Get transaction
        transaction = Transaction.query.filter_by(id=transaction_id).first()
        
        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404
            
        # Verify ownership
        wallet = Wallet.query.filter_by(id=transaction.wallet_id).first()
        if not wallet or wallet.user_id != user_id:
            return jsonify({"error": "Transaction not found or not owned by user"}), 404
        
        # In a real implementation, you would check the blockchain for the 
        # current status of the transaction
        
        return jsonify({
            "transaction_id": transaction.id,
            "status": transaction.status,
            "confirmations": transaction.confirmations
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500 