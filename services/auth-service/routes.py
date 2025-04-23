from flask import Blueprint, request, jsonify
from models import User, db
from datetime import datetime
import os
from functools import wraps

auth = Blueprint('auth', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(' ')[1]
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        
        result = User.verify_token(token)
        if 'error' in result:
            return jsonify({'message': result['error']}), 401
            
        current_user = User.query.filter_by(id=result['sub']).first()
        if not current_user:
            return jsonify({'message': 'User not found!'}), 401
            
        return f(current_user, *args, **kwargs)
    
    return decorated

@auth.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Missing required fields'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 409
        
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already registered'}), 409
    
    new_user = User(
        username=data['username'],
        email=data['email'],
        password=data['password'],
        role=data.get('role', 'user')
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    return jsonify({
        'message': 'User created successfully',
        'user': new_user.to_dict()
    }), 201

@auth.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing username or password'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    token = user.generate_token()
    
    return jsonify({
        'message': 'Login successful',
        'token': token,
        'user': user.to_dict()
    }), 200

@auth.route('/validate', methods=['GET'])
@token_required
def validate_token(current_user):
    return jsonify({
        'valid': True,
        'user': current_user.to_dict()
    }), 200

@auth.route('/users', methods=['GET'])
@token_required
def get_all_users(current_user):
    if current_user.role != 'admin':
        return jsonify({'message': 'Unauthorized'}), 403
        
    users = User.query.all()
    return jsonify({
        'users': [user.to_dict() for user in users]
    }), 200

@auth.route('/users/<user_id>', methods=['GET'])
@token_required
def get_user(current_user, user_id):
    if current_user.role != 'admin' and str(current_user.id) != user_id:
        return jsonify({'message': 'Unauthorized'}), 403
        
    user = User.query.filter_by(id=user_id).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404
        
    return jsonify({
        'user': user.to_dict()
    }), 200 