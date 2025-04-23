import logging
import requests
import json
from datetime import datetime
from decimal import Decimal, ROUND_DOWN

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='exchange_service.log'
)
logger = logging.getLogger('exchange_service')

class ExchangeService:
    """
    Service to fetch cryptocurrency exchange rates and perform conversions
    """
    
    def __init__(self, cache_service=None, api_key=None):
        """
        Initialize exchange service
        
        Args:
            cache_service: CacheService instance for caching rates
            api_key: API key for CoinMarketCap or CoinGecko (optional)
        """
        self.cache_service = cache_service
        self.api_key = api_key
        self.default_currency = 'USD'
        self.available_providers = {
            'coingecko': self._fetch_rates_coingecko,
            'coinmarketcap': self._fetch_rates_coinmarketcap,
            'binance': self._fetch_rates_binance
        }
        self.default_provider = 'coingecko'
        
        # Mapping of network names to coin IDs for CoinGecko
        self.coin_mapping = {
            'bitcoin': 'bitcoin',
            'ethereum': 'ethereum',
            'bnb': 'binancecoin',
            'solana': 'solana',
            'tron': 'tron',
            'polygon': 'matic-network',
            'arbitrum': 'arbitrum',
            'avalanche': 'avalanche-2',
            'usdt': 'tether',
            'usdc': 'usd-coin',
            'dai': 'dai',
            'busd': 'binance-usd'
        }
        
        # Mapping of token symbols to names
        self.token_symbols = {
            'btc': 'bitcoin',
            'eth': 'ethereum',
            'bnb': 'bnb',
            'sol': 'solana',
            'trx': 'tron',
            'matic': 'polygon',
            'arb': 'arbitrum',
            'avax': 'avalanche',
            'usdt': 'usdt',
            'usdc': 'usdc',
            'dai': 'dai',
            'busd': 'busd'
        }
    
    def _fetch_rates_coingecko(self):
        """Fetch rates from CoinGecko API"""
        try:
            # Get IDs for all coins we want to track
            coin_ids = list(set(self.coin_mapping.values()))
            
            # Construct API URL with all coin IDs and fiat currencies
            coins_param = ','.join(coin_ids)
            vs_currencies = 'usd,eur,gbp,jpy,cny,rub,inr,brl,aud,cad'
            
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coins_param}&vs_currencies={vs_currencies}&include_24hr_change=true"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"CoinGecko API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Normalize the data
            rates = {
                'provider': 'coingecko',
                'timestamp': datetime.utcnow().isoformat(),
                'base': 'USD',
                'rates': {}
            }
            
            # Process each coin
            for network, coin_id in self.coin_mapping.items():
                if coin_id in data:
                    coin_data = data[coin_id]
                    
                    # Add USD rate
                    usd_rate = coin_data.get('usd', 0)
                    
                    # Only add coins with valid rates
                    if usd_rate > 0:
                        rates['rates'][network] = {
                            'usd': usd_rate,
                            'eur': coin_data.get('eur', 0),
                            'gbp': coin_data.get('gbp', 0),
                            'jpy': coin_data.get('jpy', 0),
                            'cny': coin_data.get('cny', 0),
                            'rub': coin_data.get('rub', 0),
                            'inr': coin_data.get('inr', 0),
                            'brl': coin_data.get('brl', 0),
                            'aud': coin_data.get('aud', 0),
                            'cad': coin_data.get('cad', 0),
                            'usd_24h_change': coin_data.get('usd_24h_change', 0)
                        }
            
            return rates
            
        except requests.RequestException as e:
            logger.error(f"Error fetching rates from CoinGecko: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error from CoinGecko: {str(e)}")
            return None
    
    def _fetch_rates_coinmarketcap(self):
        """Fetch rates from CoinMarketCap API"""
        if not self.api_key:
            logger.error("No API key provided for CoinMarketCap")
            return None
        
        try:
            url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
            
            # Get symbols for all coins we want to track
            symbols = ','.join(self.token_symbols.keys())
            
            headers = {
                'X-CMC_PRO_API_KEY': self.api_key,
                'Accept': 'application/json'
            }
            
            params = {
                'symbol': symbols,
                'convert': 'USD'
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"CoinMarketCap API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            # Normalize the data
            rates = {
                'provider': 'coinmarketcap',
                'timestamp': datetime.utcnow().isoformat(),
                'base': 'USD',
                'rates': {}
            }
            
            # Process each coin
            for symbol, info in data.get('data', {}).items():
                network = self.token_symbols.get(symbol.lower())
                
                if network:
                    quote = info.get('quote', {}).get('USD', {})
                    
                    # Only add coins with valid rates
                    if quote and quote.get('price', 0) > 0:
                        rates['rates'][network] = {
                            'usd': quote.get('price', 0),
                            'usd_24h_change': quote.get('percent_change_24h', 0)
                        }
            
            return rates
            
        except requests.RequestException as e:
            logger.error(f"Error fetching rates from CoinMarketCap: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error from CoinMarketCap: {str(e)}")
            return None
    
    def _fetch_rates_binance(self):
        """Fetch rates from Binance API"""
        try:
            # Get ticker prices
            url = 'https://api.binance.com/api/v3/ticker/price'
            
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Binance API error: {response.status_code} - {response.text}")
                return None
            
            ticker_data = response.json()
            
            # Get 24h statistics
            url_24h = 'https://api.binance.com/api/v3/ticker/24hr'
            
            response_24h = requests.get(url_24h, timeout=10)
            
            if response_24h.status_code != 200:
                logger.error(f"Binance 24h API error: {response_24h.status_code} - {response_24h.text}")
                return None
            
            stats_24h = response_24h.json()
            
            # Create lookup dictionary for 24h data
            stats_dict = {item['symbol']: item for item in stats_24h}
            
            # Map of Binance symbols to our network names
            symbol_mapping = {
                'BTCUSDT': 'bitcoin',
                'ETHUSDT': 'ethereum',
                'BNBUSDT': 'bnb',
                'SOLUSDT': 'solana',
                'TRXUSDT': 'tron',
                'MATICUSDT': 'polygon',
                'ARBUSDT': 'arbitrum',
                'AVAXUSDT': 'avalanche',
                'USDCUSDT': 'usdc',
                'DAIUSDT': 'dai',
                'BUSDUSDT': 'busd'
            }
            
            # Normalize the data
            rates = {
                'provider': 'binance',
                'timestamp': datetime.utcnow().isoformat(),
                'base': 'USD',
                'rates': {}
            }
            
            # Process each ticker
            for ticker in ticker_data:
                symbol = ticker['symbol']
                
                if symbol in symbol_mapping:
                    network = symbol_mapping[symbol]
                    price = float(ticker['price'])
                    
                    # Get 24h change
                    change_24h = 0
                    if symbol in stats_dict:
                        prev_price = float(stats_dict[symbol]['prevClosePrice'])
                        if prev_price > 0:
                            change_24h = ((price - prev_price) / prev_price) * 100
                    
                    # Only add coins with valid rates
                    if price > 0:
                        rates['rates'][network] = {
                            'usd': price,
                            'usd_24h_change': change_24h
                        }
            
            return rates
            
        except requests.RequestException as e:
            logger.error(f"Error fetching rates from Binance: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error from Binance: {str(e)}")
            return None
    
    def fetch_rates(self, provider=None, force_refresh=False):
        """
        Fetch cryptocurrency rates from provider
        
        Args:
            provider: The data provider to use ('coingecko', 'coinmarketcap', 'binance')
            force_refresh: If True, bypass cache and fetch fresh rates
        
        Returns:
            dict: Exchange rates data
        """
        # Use default provider if none specified
        provider = provider or self.default_provider
        
        # Check if provider is supported
        if provider not in self.available_providers:
            logger.error(f"Unsupported provider: {provider}")
            return None
        
        # Try to get cached rates first
        if self.cache_service and not force_refresh:
            cached_rates = self.cache_service.get_exchange_rates()
            if cached_rates and cached_rates.get('provider') == provider:
                return cached_rates
        
        # Fetch fresh rates
        fetch_func = self.available_providers[provider]
        rates = fetch_func()
        
        # Cache the rates if successful
        if rates and self.cache_service:
            self.cache_service.set("exchange_rates:latest", rates, 300)  # Cache for 5 minutes
        
        return rates
    
    def get_rate(self, crypto, fiat='USD', provider=None):
        """
        Get exchange rate for a cryptocurrency to fiat currency
        
        Args:
            crypto: Cryptocurrency network or symbol (e.g., 'bitcoin', 'ethereum', 'btc', 'eth')
            fiat: Fiat currency (e.g., 'USD', 'EUR', 'GBP')
            provider: Data provider to use
        
        Returns:
            float: Exchange rate or 0 if not available
        """
        # Normalize inputs
        crypto = crypto.lower()
        fiat = fiat.lower()
        
        # Convert symbol to network name if needed
        if crypto in self.token_symbols:
            crypto = self.token_symbols[crypto]
        
        # Fetch rates
        rates = self.fetch_rates(provider)
        
        if not rates or 'rates' not in rates:
            logger.error("Failed to get exchange rates")
            return 0
        
        # Get cryptocurrency rates
        crypto_rates = rates['rates'].get(crypto, {})
        
        # Get rate for the requested fiat
        rate = crypto_rates.get(fiat, 0)
        
        # If the specific fiat rate is not available, try to convert from USD
        if rate == 0 and fiat != 'usd':
            usd_rate = crypto_rates.get('usd', 0)
            
            # Use exchange service to convert USD to requested fiat
            if usd_rate > 0:
                # This is just a placeholder - in a real implementation, 
                # you would use a forex service to convert between fiats
                # For now, we'll just return the USD rate
                rate = usd_rate
        
        return rate
    
    def convert(self, amount, from_currency, to_currency, provider=None):
        """
        Convert an amount between cryptocurrencies and/or fiat currencies
        
        Args:
            amount: Amount to convert
            from_currency: Source currency (crypto or fiat)
            to_currency: Target currency (crypto or fiat)
            provider: Data provider to use
        
        Returns:
            float: Converted amount or 0 if conversion failed
        """
        # Normalize inputs
        from_currency = from_currency.lower()
        to_currency = to_currency.lower()
        
        # Convert symbols to network names if needed
        if from_currency in self.token_symbols:
            from_currency = self.token_symbols[from_currency]
        
        if to_currency in self.token_symbols:
            to_currency = self.token_symbols[to_currency]
        
        # Special case: same currency
        if from_currency == to_currency:
            return float(amount)
        
        # Special case: stablecoins to USD
        stablecoins = ['usdt', 'usdc', 'dai', 'busd']
        if from_currency in stablecoins and to_currency == 'usd':
            return float(amount)
        if to_currency in stablecoins and from_currency == 'usd':
            return float(amount)
        
        # Get rates in USD
        from_rate_usd = self.get_rate(from_currency, 'usd', provider)
        to_rate_usd = self.get_rate(to_currency, 'usd', provider)
        
        # Handle fiat-to-fiat conversions
        fiat_currencies = ['usd', 'eur', 'gbp', 'jpy', 'cny', 'rub', 'inr', 'brl', 'aud', 'cad']
        
        if from_currency in fiat_currencies and to_currency in fiat_currencies:
            # For fiat-to-fiat, we would typically use a forex service
            # For now, we'll just use our cryptocurrency rates as a proxy
            # Get rates for a common cryptocurrency (Bitcoin)
            btc_from_rate = self.get_rate('bitcoin', from_currency, provider)
            btc_to_rate = self.get_rate('bitcoin', to_currency, provider)
            
            if btc_from_rate > 0 and btc_to_rate > 0:
                # Cross rate: to_value / from_value
                rate = btc_from_rate / btc_to_rate
                return float(amount) * rate
            
            return 0
        
        # For crypto-to-fiat, fiat-to-crypto, or crypto-to-crypto
        if from_rate_usd > 0 and to_rate_usd > 0:
            # First convert to USD, then to target
            usd_value = float(amount) * from_rate_usd
            
            # Then convert USD to target
            if to_rate_usd > 0:
                return usd_value / to_rate_usd
        
        logger.error(f"Conversion failed: {from_currency} to {to_currency}")
        return 0
    
    def format_currency(self, amount, currency, decimal_places=None):
        """
        Format a currency amount with the appropriate precision
        
        Args:
            amount: Amount to format
            currency: Currency code
            decimal_places: Number of decimal places to show (if None, use currency default)
        
        Returns:
            str: Formatted currency amount
        """
        # Normalize input
        currency = currency.lower()
        
        # Default decimal places by currency
        default_places = {
            'btc': 8,
            'eth': 6,
            'bnb': 6,
            'sol': 4,
            'trx': 2,
            'matic': 4,
            'arb': 4,
            'avax': 4,
            'usdt': 2,
            'usdc': 2,
            'dai': 2,
            'busd': 2,
            'usd': 2,
            'eur': 2,
            'gbp': 2,
            'jpy': 0,
            'cny': 2,
            'rub': 2,
            'inr': 2,
            'brl': 2,
            'aud': 2,
            'cad': 2
        }
        
        # Use default decimal places if not specified
        if decimal_places is None:
            decimal_places = default_places.get(currency, 2)
        
        # Convert to Decimal for proper rounding
        try:
            decimal_amount = Decimal(str(amount))
            
            # Use ROUND_DOWN to avoid showing more than the actual amount
            rounded = decimal_amount.quantize(Decimal('0.' + '0' * decimal_places), rounding=ROUND_DOWN)
            
            # Format as string
            return f"{rounded:.{decimal_places}f}"
        except Exception as e:
            logger.error(f"Error formatting currency: {str(e)}")
            return str(amount)

# Example usage
if __name__ == "__main__":
    # Create exchange service
    exchange_service = ExchangeService()
    
    # Fetch rates
    rates = exchange_service.fetch_rates()
    
    if rates:
        print("Exchange Rates:")
        for crypto, data in rates['rates'].items():
            print(f"{crypto.upper()}: ${data['usd']:.2f} (24h change: {data['usd_24h_change']:.2f}%)")
    
    # Example conversions
    btc_amount = 0.5
    eth_equiv = exchange_service.convert(btc_amount, 'btc', 'eth')
    usd_equiv = exchange_service.convert(btc_amount, 'btc', 'usd')
    
    print(f"\nConversions:")
    print(f"{btc_amount} BTC = {eth_equiv:.6f} ETH")
    print(f"{btc_amount} BTC = ${usd_equiv:.2f} USD") 