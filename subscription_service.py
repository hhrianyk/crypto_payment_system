import logging
import threading
import time
import uuid
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='subscription_service.log'
)
logger = logging.getLogger('subscription_service')

class SubscriptionService:
    """
    Service for managing cryptocurrency subscription payments
    """
    
    def __init__(self, db, email_service=None, check_interval=3600):
        """
        Initialize subscription service
        
        Args:
            db: SQLAlchemy database object
            email_service: EmailService instance for sending notifications
            check_interval: How often to check for due subscriptions (in seconds)
        """
        self.db = db
        self.email_service = email_service
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.Subscription = None  # Will be set when start() is called
        self.Transaction = None  # Will be set when start() is called
        self.WalletAddress = None  # Will be set when start() is called
        self.Merchant = None  # Will be set when start() is called
    
    def _load_models(self):
        """Load database models from app context"""
        # These imports are kept local to prevent circular imports
        from app import Subscription, Transaction, WalletAddress, Merchant
        self.Subscription = Subscription
        self.Transaction = Transaction
        self.WalletAddress = WalletAddress
        self.Merchant = Merchant
    
    def create_subscription(self, merchant_id, client_email, amount, network, token_type=None,
                          frequency='monthly', start_date=None, end_date=None, description=None):
        """
        Create a new subscription
        
        Args:
            merchant_id: ID of the merchant
            client_email: Email of the client
            amount: Subscription amount
            network: Cryptocurrency network
            token_type: Token type (for tokens like USDT)
            frequency: Subscription frequency ('daily', 'weekly', 'monthly', 'yearly')
            start_date: When the subscription starts (default: now)
            end_date: When the subscription ends (default: None, open-ended)
            description: Subscription description
        
        Returns:
            Subscription: Created subscription object or None on error
        """
        if not self.Subscription:
            logger.error("Cannot create subscription: Subscription model not initialized")
            return None
        
        try:
            # Set default start date to now
            if not start_date:
                start_date = datetime.utcnow()
            
            # Calculate first payment date
            next_payment_date = self._calculate_next_payment_date(start_date, frequency)
            
            # Create subscription record
            subscription = self.Subscription(
                merchant_id=merchant_id,
                client_email=client_email,
                amount=amount,
                network=network,
                token_type=token_type,
                frequency=frequency,
                start_date=start_date,
                end_date=end_date,
                next_payment_date=next_payment_date,
                description=description,
                status='active'
            )
            
            self.db.session.add(subscription)
            self.db.session.commit()
            
            logger.info(f"Created subscription for {client_email}: {amount} {network} {frequency}")
            
            return subscription
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            self.db.session.rollback()
            return None
    
    def update_subscription(self, subscription_id, **kwargs):
        """
        Update a subscription
        
        Args:
            subscription_id: ID of the subscription to update
            **kwargs: Fields to update (amount, frequency, status, etc.)
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.Subscription:
            logger.error("Cannot update subscription: Subscription model not initialized")
            return False
        
        try:
            # Get subscription
            subscription = self.Subscription.query.get(subscription_id)
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(subscription, key):
                    setattr(subscription, key, value)
            
            # If frequency changed, recalculate next payment date
            if 'frequency' in kwargs:
                subscription.next_payment_date = self._calculate_next_payment_date(
                    datetime.utcnow(), kwargs['frequency']
                )
            
            self.db.session.commit()
            
            logger.info(f"Updated subscription {subscription_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            self.db.session.rollback()
            return False
    
    def cancel_subscription(self, subscription_id, reason=None):
        """
        Cancel a subscription
        
        Args:
            subscription_id: ID of the subscription to cancel
            reason: Cancellation reason (optional)
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_subscription(
            subscription_id,
            status='cancelled',
            end_date=datetime.utcnow()
        )
    
    def pause_subscription(self, subscription_id, reason=None):
        """
        Pause a subscription
        
        Args:
            subscription_id: ID of the subscription to pause
            reason: Pause reason (optional)
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.update_subscription(
            subscription_id,
            status='paused'
        )
    
    def resume_subscription(self, subscription_id):
        """
        Resume a paused subscription
        
        Args:
            subscription_id: ID of the subscription to resume
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.Subscription:
            logger.error("Cannot resume subscription: Subscription model not initialized")
            return False
        
        try:
            # Get subscription
            subscription = self.Subscription.query.get(subscription_id)
            if not subscription:
                logger.error(f"Subscription not found: {subscription_id}")
                return False
            
            # Only paused subscriptions can be resumed
            if subscription.status != 'paused':
                logger.error(f"Subscription {subscription_id} is not paused (status: {subscription.status})")
                return False
            
            # Calculate next payment date from now
            next_payment_date = self._calculate_next_payment_date(
                datetime.utcnow(), subscription.frequency
            )
            
            # Update subscription
            subscription.status = 'active'
            subscription.next_payment_date = next_payment_date
            
            self.db.session.commit()
            
            logger.info(f"Resumed subscription {subscription_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error resuming subscription: {str(e)}")
            self.db.session.rollback()
            return False
    
    def get_subscription(self, subscription_id):
        """
        Get a subscription by ID
        
        Args:
            subscription_id: ID of the subscription
        
        Returns:
            Subscription: Subscription object or None if not found
        """
        if not self.Subscription:
            logger.error("Cannot get subscription: Subscription model not initialized")
            return None
        
        try:
            return self.Subscription.query.get(subscription_id)
        except Exception as e:
            logger.error(f"Error getting subscription: {str(e)}")
            return None
    
    def get_merchant_subscriptions(self, merchant_id, status=None):
        """
        Get all subscriptions for a merchant
        
        Args:
            merchant_id: ID of the merchant
            status: Filter by status (optional)
        
        Returns:
            list: List of Subscription objects
        """
        if not self.Subscription:
            logger.error("Cannot get subscriptions: Subscription model not initialized")
            return []
        
        try:
            query = self.Subscription.query.filter_by(merchant_id=merchant_id)
            
            if status:
                query = query.filter_by(status=status)
            
            return query.all()
        except Exception as e:
            logger.error(f"Error getting merchant subscriptions: {str(e)}")
            return []
    
    def get_client_subscriptions(self, client_email, status=None):
        """
        Get all subscriptions for a client
        
        Args:
            client_email: Email of the client
            status: Filter by status (optional)
        
        Returns:
            list: List of Subscription objects
        """
        if not self.Subscription:
            logger.error("Cannot get subscriptions: Subscription model not initialized")
            return []
        
        try:
            query = self.Subscription.query.filter_by(client_email=client_email)
            
            if status:
                query = query.filter_by(status=status)
            
            return query.all()
        except Exception as e:
            logger.error(f"Error getting client subscriptions: {str(e)}")
            return []
    
    def _calculate_next_payment_date(self, from_date, frequency):
        """
        Calculate the next payment date based on frequency
        
        Args:
            from_date: Date to calculate from
            frequency: Subscription frequency
        
        Returns:
            datetime: Next payment date
        """
        if frequency == 'daily':
            return from_date + timedelta(days=1)
        elif frequency == 'weekly':
            return from_date + timedelta(weeks=1)
        elif frequency == 'monthly':
            # Add one month (approximately)
            month = from_date.month + 1
            year = from_date.year
            
            if month > 12:
                month = 1
                year += 1
            
            # Handle day-of-month overflow
            day = min(from_date.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            
            return from_date.replace(year=year, month=month, day=day)
        elif frequency == 'yearly':
            return from_date.replace(year=from_date.year + 1)
        else:
            # Default to monthly
            return self._calculate_next_payment_date(from_date, 'monthly')
    
    def get_due_subscriptions(self):
        """
        Get all subscriptions due for payment
        
        Returns:
            list: List of due Subscription objects
        """
        if not self.Subscription:
            logger.error("Cannot get due subscriptions: Subscription model not initialized")
            return []
        
        try:
            now = datetime.utcnow()
            
            # Get active subscriptions where next payment date is in the past
            due_subscriptions = self.Subscription.query.filter(
                self.Subscription.status == 'active',
                self.Subscription.next_payment_date <= now
            ).all()
            
            return due_subscriptions
        except Exception as e:
            logger.error(f"Error getting due subscriptions: {str(e)}")
            return []
    
    def process_subscription_payment(self, subscription):
        """
        Process a subscription payment
        
        Args:
            subscription: Subscription object
        
        Returns:
            Transaction: Created transaction or None on error
        """
        if not self.Transaction:
            logger.error("Cannot process payment: Transaction model not initialized")
            return None
        
        try:
            # Get wallet address for the currency
            wallet_query = self.WalletAddress.query.filter_by(
                network=subscription.network,
                token_type=subscription.token_type,
                merchant_id=subscription.merchant_id
            )
            
            wallet = wallet_query.first()
            
            if not wallet:
                logger.error(f"No wallet found for {subscription.network} {subscription.token_type} (merchant: {subscription.merchant_id})")
                return None
            
            # Create a transaction record
            transaction_id = str(uuid.uuid4())
            transaction = self.Transaction(
                id=transaction_id,
                amount=subscription.amount,
                network=subscription.network,
                token_type=subscription.token_type,
                client_email=subscription.client_email,
                description=f"Subscription payment: {subscription.description}" if subscription.description else "Subscription payment",
                status='pending',
                merchant_id=subscription.merchant_id
            )
            
            self.db.session.add(transaction)
            
            # Update subscription next payment date
            subscription.next_payment_date = self._calculate_next_payment_date(
                datetime.utcnow(), subscription.frequency
            )
            
            self.db.session.commit()
            
            # Send payment notification
            if self.email_service:
                payment_link = self._generate_payment_link(transaction_id, subscription)
                
                self.email_service.send_payment_link(
                    to_email=subscription.client_email,
                    payment_link=payment_link,
                    amount=subscription.amount,
                    network=subscription.network,
                    description=transaction.description
                )
            
            logger.info(f"Processed subscription payment for {subscription.id}: {transaction_id}")
            
            return transaction
            
        except Exception as e:
            logger.error(f"Error processing subscription payment: {str(e)}")
            self.db.session.rollback()
            return None
    
    def _generate_payment_link(self, transaction_id, subscription):
        """
        Generate a payment link for a subscription
        
        Args:
            transaction_id: Transaction ID
            subscription: Subscription object
        
        Returns:
            str: Payment link URL
        """
        # This would typically be a URL to your payment page
        # For now, we'll just return a placeholder
        base_url = "https://your-domain.com/confirm_payment"
        
        token_part = f"&token_type={subscription.token_type}" if subscription.token_type else ""
        
        return f"{base_url}/{transaction_id}?amount={subscription.amount}&network={subscription.network}{token_part}"
    
    def process_due_subscriptions(self):
        """
        Process all due subscriptions
        
        Returns:
            int: Number of subscriptions processed
        """
        due_subscriptions = self.get_due_subscriptions()
        
        if not due_subscriptions:
            logger.info("No due subscriptions to process")
            return 0
        
        logger.info(f"Processing {len(due_subscriptions)} due subscriptions")
        
        count = 0
        for subscription in due_subscriptions:
            if self.process_subscription_payment(subscription):
                count += 1
        
        return count
    
    def _processor_loop(self):
        """Main processing loop that runs in a separate thread"""
        logger.info("Subscription processor started")
        
        while self.running:
            try:
                self.process_due_subscriptions()
            except Exception as e:
                logger.error(f"Error in processor loop: {str(e)}")
            
            # Sleep for the check interval before processing again
            time.sleep(self.check_interval)
        
        logger.info("Subscription processor stopped")
    
    def start(self):
        """Start the subscription processor in a separate thread"""
        if self.thread and self.thread.is_alive():
            logger.warning("Subscription processor is already running")
            return
        
        self._load_models()
        self.running = True
        self.thread = threading.Thread(target=self._processor_loop)
        self.thread.daemon = True
        self.thread.start()
        
        logger.info("Subscription processor started in background thread")
        return True
    
    def stop(self):
        """Stop the subscription processor"""
        if not self.thread or not self.thread.is_alive():
            logger.warning("Subscription processor is not running")
            return
        
        logger.info("Stopping subscription processor...")
        self.running = False
        self.thread.join(timeout=5.0)
        
        if self.thread.is_alive():
            logger.warning("Subscription processor thread did not stop gracefully")
        else:
            logger.info("Subscription processor stopped successfully")
        
        return True

# Example usage
if __name__ == "__main__":
    # This would typically be run in the context of a Flask app
    from app import app, db, Subscription, Transaction, WalletAddress, Merchant, email_service
    
    with app.app_context():
        subscription_service = SubscriptionService(
            db=db,
            email_service=email_service,
            check_interval=3600  # Check every hour
        )
        
        # Start the processor
        subscription_service.start()
        
        try:
            # Keep the script running
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Stop the processor on Ctrl+C
            subscription_service.stop() 