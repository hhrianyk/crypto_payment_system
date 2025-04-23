import logging
import json
import redis
import pickle
import hashlib
import time
from functools import wraps
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='cache_service.log'
)
logger = logging.getLogger('cache_service')

class CacheService:
    """
    Cache service using Redis for caching API responses and blockchain data
    """
    
    def __init__(self, redis_host='localhost', redis_port=6379, redis_db=0, redis_password=None,
                 default_ttl=300, prefix='crypto_payment_system:'):
        """
        Initialize cache service
        
        Args:
            redis_host: Redis server host
            redis_port: Redis server port
            redis_db: Redis database number
            redis_password: Redis password (if required)
            default_ttl: Default time-to-live for cache entries (in seconds)
            prefix: Prefix for all cache keys
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.redis_password = redis_password
        self.default_ttl = default_ttl
        self.prefix = prefix
        self.redis_client = None
        self.enabled = True
    
    def connect(self):
        """Connect to Redis server"""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=False,  # We'll handle decoding ourselves
                socket_timeout=5,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {self.redis_host}:{self.redis_port}")
            return True
        except redis.ConnectionError as e:
            logger.error(f"Could not connect to Redis: {str(e)}")
            self.redis_client = None
            return False
        except Exception as e:
            logger.error(f"Error connecting to Redis: {str(e)}")
            self.redis_client = None
            return False
    
    def _generate_key(self, key):
        """Generate a prefixed cache key"""
        return f"{self.prefix}{key}"
    
    def _serialize_value(self, value):
        """Serialize value for storage in Redis"""
        try:
            return pickle.dumps(value)
        except Exception as e:
            logger.error(f"Error serializing value: {str(e)}")
            return None
    
    def _deserialize_value(self, value):
        """Deserialize value from Redis"""
        if value is None:
            return None
        
        try:
            return pickle.loads(value)
        except Exception as e:
            logger.error(f"Error deserializing value: {str(e)}")
            return None
    
    def get(self, key):
        """
        Get a value from the cache
        
        Args:
            key: Cache key
        
        Returns:
            The cached value, or None if not found
        """
        if not self.enabled or not self.redis_client:
            return None
        
        try:
            value = self.redis_client.get(self._generate_key(key))
            if value:
                return self._deserialize_value(value)
            return None
        except Exception as e:
            logger.error(f"Error getting value from cache: {str(e)}")
            return None
    
    def set(self, key, value, ttl=None):
        """
        Set a value in the cache
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds, or None for default
        
        Returns:
            bool: True if value was cached, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            serialized = self._serialize_value(value)
            if serialized:
                expiry = ttl if ttl is not None else self.default_ttl
                return self.redis_client.setex(
                    self._generate_key(key),
                    expiry,
                    serialized
                )
            return False
        except Exception as e:
            logger.error(f"Error setting value in cache: {str(e)}")
            return False
    
    def delete(self, key):
        """
        Delete a value from the cache
        
        Args:
            key: Cache key
        
        Returns:
            bool: True if value was deleted, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            return bool(self.redis_client.delete(self._generate_key(key)))
        except Exception as e:
            logger.error(f"Error deleting value from cache: {str(e)}")
            return False
    
    def invalidate_pattern(self, pattern):
        """
        Delete all keys matching a pattern
        
        Args:
            pattern: Redis key pattern (e.g., 'user:*')
        
        Returns:
            int: Number of keys deleted
        """
        if not self.enabled or not self.redis_client:
            return 0
        
        try:
            prefixed_pattern = self._generate_key(pattern)
            keys = self.redis_client.keys(prefixed_pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error invalidating pattern {pattern}: {str(e)}")
            return 0
    
    def cache_function(self, ttl=None, key_prefix=None):
        """
        Decorator to cache function return values
        
        Usage:
            @cache_service.cache_function(ttl=60)
            def slow_function(param1, param2):
                # This function's results will be cached for 60 seconds
                return expensive_operation(param1, param2)
        
        Args:
            ttl: Time-to-live in seconds, or None for default
            key_prefix: Custom prefix for the cache key
        
        Returns:
            function: Decorated function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled or not self.redis_client:
                    return func(*args, **kwargs)
                
                # Generate cache key based on function name, args and kwargs
                key_parts = [key_prefix or func.__name__]
                # Add stringified args to key
                for arg in args:
                    key_parts.append(str(arg))
                
                # Add sorted kwargs to key
                kwargs_parts = []
                for k, v in sorted(kwargs.items()):
                    kwargs_parts.append(f"{k}:{v}")
                
                if kwargs_parts:
                    key_parts.append("|".join(kwargs_parts))
                
                key = ":".join(key_parts)
                
                # Try to get from cache
                cached_value = self.get(key)
                if cached_value is not None:
                    return cached_value
                
                # Not in cache, call the function
                result = func(*args, **kwargs)
                
                # Cache the result
                if result is not None:
                    self.set(key, result, ttl)
                
                return result
            
            return wrapper
        
        return decorator
    
    def cache_blockchain_api(self, ttl=None, network_param='network'):
        """
        Decorator to cache blockchain API calls
        
        Usage:
            @cache_service.cache_blockchain_api(ttl=300, network_param='network')
            def get_blockchain_data(network, address):
                # This API call will be cached for 300 seconds
                return api_client.get_data(network, address)
        
        Args:
            ttl: Time-to-live in seconds, or None for default
            network_param: Name of the parameter that specifies the network
        
        Returns:
            function: Decorated function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled or not self.redis_client:
                    return func(*args, **kwargs)
                
                # Extract network from args or kwargs
                network = None
                if args and len(args) > 0 and isinstance(args[0], str):
                    network = args[0]
                elif network_param in kwargs:
                    network = kwargs[network_param]
                
                if not network:
                    # Can't determine network, can't cache
                    return func(*args, **kwargs)
                
                # Generate cache key
                key_parts = [f"blockchain:{network}", func.__name__]
                
                # Add stringified args to key
                for arg in args:
                    if isinstance(arg, (str, int, float, bool)):
                        key_parts.append(str(arg))
                
                # Add sorted kwargs to key
                kwargs_parts = []
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, (str, int, float, bool)):
                        kwargs_parts.append(f"{k}:{v}")
                
                if kwargs_parts:
                    key_parts.append("|".join(kwargs_parts))
                
                # Hash the key to prevent very long keys
                key_string = ":".join(key_parts)
                hashed_key = hashlib.md5(key_string.encode()).hexdigest()
                key = f"blockchain:{network}:{hashed_key}"
                
                # Try to get from cache
                cached_value = self.get(key)
                if cached_value is not None:
                    return cached_value
                
                # Not in cache, call the function
                result = func(*args, **kwargs)
                
                # Cache the result
                if result is not None:
                    # Use either specified TTL or default
                    network_ttl = {
                        'bitcoin': 600,  # 10 minutes
                        'ethereum': 120,  # 2 minutes
                        'bnb': 60,       # 1 minute
                        'tron': 60,
                        'solana': 60,
                        'polygon': 60,
                        'arbitrum': 60,
                        'avalanche': 60
                    }.get(network, self.default_ttl)
                    
                    # Use the specified TTL if provided, otherwise use network default
                    effective_ttl = ttl if ttl is not None else network_ttl
                    
                    self.set(key, result, effective_ttl)
                
                return result
            
            return wrapper
        
        return decorator
    
    def cache_exchange_rates(self, ttl=300):
        """
        Cache cryptocurrency exchange rates
        
        Args:
            ttl: Time-to-live in seconds, defaults to 5 minutes
        
        Usage:
            # Cache the rates
            cache_service.cache_exchange_rates(rates_data)
            
            # Get the cached rates
            rates = cache_service.get_exchange_rates()
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.enabled or not self.redis_client:
                    return func(*args, **kwargs)
                
                cache_key = "exchange_rates:latest"
                
                # Try to get from cache
                cached_rates = self.get(cache_key)
                if cached_rates is not None:
                    return cached_rates
                
                # Not in cache, call the function
                rates = func(*args, **kwargs)
                
                # Cache the result
                if rates is not None:
                    self.set(cache_key, rates, ttl)
                
                return rates
            
            return wrapper
        
        return decorator
    
    def get_exchange_rates(self):
        """
        Get cached exchange rates
        
        Returns:
            dict: Exchange rates or None if not cached
        """
        return self.get("exchange_rates:latest")
    
    def clear_all(self):
        """
        Clear all cached data (use with caution!)
        
        Returns:
            bool: True if operation was successful, False otherwise
        """
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            keys = self.redis_client.keys(self._generate_key("*"))
            if keys:
                return self.redis_client.delete(*keys) > 0
            return True  # No keys to delete
        except Exception as e:
            logger.error(f"Error clearing cache: {str(e)}")
            return False
    
    def get_stats(self):
        """
        Get cache statistics
        
        Returns:
            dict: Cache statistics
        """
        if not self.enabled or not self.redis_client:
            return {
                'status': 'disconnected',
                'count': 0,
                'memory_used': 0,
                'hit_rate': 0
            }
        
        try:
            info = self.redis_client.info()
            keys = self.redis_client.keys(self._generate_key("*"))
            
            return {
                'status': 'connected',
                'count': len(keys),
                'memory_used': info.get('used_memory_human', 'unknown'),
                'hit_rate': info.get('keyspace_hits', 0) / (info.get('keyspace_hits', 0) + info.get('keyspace_misses', 1) or 1)
            }
        except Exception as e:
            logger.error(f"Error getting cache stats: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }

# Example usage
if __name__ == "__main__":
    # Create cache service and connect to Redis
    cache_service = CacheService(
        redis_host='localhost',
        redis_port=6379,
        redis_db=0,
        default_ttl=300
    )
    
    if not cache_service.connect():
        print("Failed to connect to Redis")
        exit(1)
    
    # Example function with caching
    @cache_service.cache_function(ttl=10)
    def slow_calculation(a, b):
        print("Performing slow calculation...")
        time.sleep(2)  # Simulate slow operation
        return a + b
    
    # Example usage
    print("First call (not cached):")
    result1 = slow_calculation(5, 3)
    print(f"Result: {result1}")
    
    print("\nSecond call (should be cached):")
    result2 = slow_calculation(5, 3)
    print(f"Result: {result2}")
    
    print("\nThird call with different args (not cached):")
    result3 = slow_calculation(10, 20)
    print(f"Result: {result3}")
    
    # Get cache stats
    print("\nCache statistics:")
    print(cache_service.get_stats()) 