import requests
import time
import json
import logging
import secrets
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='blockchain_verifier.log'
)
logger = logging.getLogger('blockchain_verifier')

class BlockchainVerifier:
    """Class to verify cryptocurrency transactions on various blockchains"""
    
    def __init__(self, api_keys=None):
        self.api_keys = api_keys or {}
        # Initialize API endpoints
        self.api_endpoints = {
            'bitcoin': 'https://blockchain.info/rawaddr/{address}',
            'ethereum': 'https://api.etherscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={api_key}',
            'bnb': 'https://api.bscscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={api_key}',
            'tron': 'https://apilist.tronscan.org/api/transaction?address={address}&count=30&start=0',
            'solana': 'https://public-api.solscan.io/account/transactions?account={address}&limit=20',
            # New networks
            'polygon': 'https://api.polygonscan.com/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={api_key}',
            'arbitrum': 'https://api.arbiscan.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={api_key}',
            'avalanche': 'https://api.snowtrace.io/api?module=account&action=txlist&address={address}&startblock=0&endblock=99999999&sort=desc&apikey={api_key}',
            # Token endpoints for ERC20 tokens
            'ethereum_token': 'https://api.etherscan.io/api?module=account&action=tokentx&address={address}&contractaddress={contract}&sort=desc&apikey={api_key}',
            'bnb_token': 'https://api.bscscan.com/api?module=account&action=tokentx&address={address}&contractaddress={contract}&sort=desc&apikey={api_key}',
            'polygon_token': 'https://api.polygonscan.com/api?module=account&action=tokentx&address={address}&contractaddress={contract}&sort=desc&apikey={api_key}',
            'arbitrum_token': 'https://api.arbiscan.io/api?module=account&action=tokentx&address={address}&contractaddress={contract}&sort=desc&apikey={api_key}',
            'avalanche_token': 'https://api.snowtrace.io/api?module=account&action=tokentx&address={address}&contractaddress={contract}&sort=desc&apikey={api_key}'
        }
        
        # Contract addresses for common tokens
        self.token_contracts = {
            # USDT
            'ethereum_usdt': '0xdAC17F958D2ee523a2206206994597C13D831ec7',
            'bnb_usdt': '0x55d398326f99059fF775485246999027B3197955',
            'polygon_usdt': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',
            'arbitrum_usdt': '0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9',
            'avalanche_usdt': '0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7',
            # USDC
            'ethereum_usdc': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
            'bnb_usdc': '0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d',
            'polygon_usdc': '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            'arbitrum_usdc': '0xFF970A61A04b1cA14834A43f5dE4533eBDDB5CC8',
            'avalanche_usdc': '0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E',
            # DAI
            'ethereum_dai': '0x6B175474E89094C44Da98b954EedeAC495271d0F',
            'bnb_dai': '0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3',
            'polygon_dai': '0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063',
            'arbitrum_dai': '0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1',
            'avalanche_dai': '0xd586E7F844cEa2F87f50152665BCbc2C279D8d70',
            # BUSD
            'ethereum_busd': '0x4Fabb145d64652a948d72533023f6E7A623C7C53',
            'bnb_busd': '0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56'
        }
    
    def _get_api_key(self, network):
        """Get API key for the specified network"""
        return self.api_keys.get(network, '')
    
    def _format_address(self, address, network):
        """Format address according to network requirements"""
        return address.strip()
    
    def _check_transaction_bitcoin(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Bitcoin transaction"""
        try:
            for tx in tx_data.get('txs', []):
                # Check if transaction is recent
                tx_time = datetime.fromtimestamp(tx.get('time', 0))
                if datetime.now() - tx_time > timedelta(minutes=max_age_minutes):
                    continue
                
                # Check for incoming transactions
                for output in tx.get('out', []):
                    if output.get('addr') == address and output.get('value', 0) / 100000000 >= float(amount):
                        return {
                            'success': True,
                            'tx_hash': tx.get('hash'),
                            'amount': output.get('value') / 100000000,
                            'timestamp': tx_time.isoformat()
                        }
            return {'success': False, 'message': 'No matching transaction found'}
        except Exception as e:
            logger.error(f"Error checking Bitcoin transaction: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _check_transaction_ethereum(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Ethereum transaction"""
        try:
            if tx_data.get('status') != '1':
                return {'success': False, 'message': 'API error: ' + tx_data.get('message', 'Unknown error')}
            
            for tx in tx_data.get('result', []):
                # Check if transaction is recent
                tx_time = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
                if datetime.now() - tx_time > timedelta(minutes=max_age_minutes):
                    continue
                
                # Check if transaction is to our address and value matches
                if tx.get('to', '').lower() == address.lower() and float(tx.get('value', 0)) / 1e18 >= float(amount):
                    return {
                        'success': True,
                        'tx_hash': tx.get('hash'),
                        'amount': float(tx.get('value')) / 1e18,
                        'timestamp': tx_time.isoformat()
                    }
            return {'success': False, 'message': 'No matching transaction found'}
        except Exception as e:
            logger.error(f"Error checking Ethereum transaction: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _check_transaction_evm_compatible(self, address, amount, tx_data, max_age_minutes=30, decimals=18):
        """Generic method for EVM-compatible chains like Ethereum, BSC, Polygon, etc."""
        try:
            if tx_data.get('status') != '1':
                return {'success': False, 'message': 'API error: ' + tx_data.get('message', 'Unknown error')}
            
            for tx in tx_data.get('result', []):
                # Check if transaction is recent
                tx_time = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
                if datetime.now() - tx_time > timedelta(minutes=max_age_minutes):
                    continue
                
                # Check if transaction is to our address and value matches
                if tx.get('to', '').lower() == address.lower() and float(tx.get('value', 0)) / (10**decimals) >= float(amount):
                    return {
                        'success': True,
                        'tx_hash': tx.get('hash'),
                        'amount': float(tx.get('value')) / (10**decimals),
                        'timestamp': tx_time.isoformat()
                    }
            return {'success': False, 'message': 'No matching transaction found'}
        except Exception as e:
            logger.error(f"Error checking EVM transaction: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _check_token_transaction(self, address, amount, tx_data, max_age_minutes=30, decimals=18):
        """Check token transactions for ERC20 tokens"""
        try:
            if tx_data.get('status') != '1':
                return {'success': False, 'message': 'API error: ' + tx_data.get('message', 'Unknown error')}
            
            for tx in tx_data.get('result', []):
                # Check if transaction is recent
                tx_time = datetime.fromtimestamp(int(tx.get('timeStamp', 0)))
                if datetime.now() - tx_time > timedelta(minutes=max_age_minutes):
                    continue
                
                # For tokens, we need to check the "to" field specifically
                if tx.get('to', '').lower() == address.lower() and float(tx.get('value', 0)) / (10**decimals) >= float(amount):
                    return {
                        'success': True,
                        'tx_hash': tx.get('hash'),
                        'token_name': tx.get('tokenName'),
                        'token_symbol': tx.get('tokenSymbol'),
                        'amount': float(tx.get('value')) / (10**decimals),
                        'timestamp': tx_time.isoformat()
                    }
            return {'success': False, 'message': 'No matching token transaction found'}
        except Exception as e:
            logger.error(f"Error checking token transaction: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _check_transaction_bnb(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching BNB transaction (similar to Ethereum)"""
        return self._check_transaction_evm_compatible(address, amount, tx_data, max_age_minutes, 18)
    
    def _check_transaction_polygon(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Polygon (MATIC) transaction"""
        return self._check_transaction_evm_compatible(address, amount, tx_data, max_age_minutes, 18)
    
    def _check_transaction_arbitrum(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Arbitrum (ARB) transaction"""
        return self._check_transaction_evm_compatible(address, amount, tx_data, max_age_minutes, 18)
    
    def _check_transaction_avalanche(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Avalanche (AVAX) transaction"""
        return self._check_transaction_evm_compatible(address, amount, tx_data, max_age_minutes, 18)
    
    def _check_transaction_tron(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Tron transaction"""
        try:
            for tx in tx_data.get('data', []):
                if tx.get('toAddress') == address and float(tx.get('amount', 0)) / 1e6 >= float(amount):
                    # Tron timestamps are in milliseconds
                    tx_time = datetime.fromtimestamp(int(tx.get('timestamp', 0)) / 1000)
                    if datetime.now() - tx_time > timedelta(minutes=max_age_minutes):
                        continue
                    
                    return {
                        'success': True,
                        'tx_hash': tx.get('hash'),
                        'amount': float(tx.get('amount')) / 1e6,
                        'timestamp': tx_time.isoformat()
                    }
            return {'success': False, 'message': 'No matching transaction found'}
        except Exception as e:
            logger.error(f"Error checking Tron transaction: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def _check_transaction_solana(self, address, amount, tx_data, max_age_minutes=30):
        """Check if there's a matching Solana transaction"""
        try:
            for tx in tx_data:
                # Solana transaction data structure is more complex
                # This is a simplified check and may need to be adjusted
                tx_time = datetime.fromtimestamp(int(tx.get('blockTime', 0)))
                if datetime.now() - tx_time > timedelta(minutes=max_age_minutes):
                    continue
                
                for instruction in tx.get('meta', {}).get('innerInstructions', []):
                    for inner in instruction.get('instructions', []):
                        if inner.get('parsed', {}).get('type') == 'transfer':
                            info = inner.get('parsed', {}).get('info', {})
                            if info.get('destination') == address and float(info.get('lamports', 0)) / 1e9 >= float(amount):
                                return {
                                    'success': True,
                                    'tx_hash': tx.get('signature'),
                                    'amount': float(info.get('lamports')) / 1e9,
                                    'timestamp': tx_time.isoformat()
                                }
            return {'success': False, 'message': 'No matching transaction found'}
        except Exception as e:
            logger.error(f"Error checking Solana transaction: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def verify_transaction(self, network, address, amount, max_age_minutes=30, simulation_mode=True, token_type=None):
        """
        Verify if a transaction of the specified amount has been sent to the address
        on the specified network within the last max_age_minutes.
        
        Args:
            network: Blockchain network (e.g., 'ethereum', 'bnb')
            address: Wallet address to check
            amount: Expected transaction amount
            max_age_minutes: Maximum age of transaction to consider (in minutes)
            simulation_mode: If True, simulate successful verification without blockchain check
            token_type: For token transactions, specify the token (e.g., 'usdt', 'usdc')
            
        Returns:
            dict: Verification result with success flag and details
        """
        # For development/testing - simulate successful verification
        if simulation_mode:
            logger.info(f"SIMULATION MODE: Simulating successful transaction for {amount} {network} to {address}")
            return {
                'success': True,
                'tx_hash': 'simulated_tx_' + secrets.token_hex(16),
                'amount': float(amount),
                'timestamp': datetime.now().isoformat(),
                'simulation': True
            }
        
        try:
            # Format address for the specific network
            formatted_address = self._format_address(address, network)
            
            # Check if this is a token transaction
            is_token_tx = token_type is not None
            
            # For token transactions, use the appropriate endpoint and contract
            if is_token_tx:
                token_key = f"{network}_{token_type.lower()}"
                contract_address = self.token_contracts.get(token_key)
                
                if not contract_address:
                    return {'success': False, 'message': f'Unsupported token: {token_type} on {network}'}
                
                api_endpoint_key = f"{network}_token"
                api_endpoint = self.api_endpoints.get(api_endpoint_key, '')
                
                if not api_endpoint:
                    return {'success': False, 'message': f'Unsupported network for token transactions: {network}'}
                
                api_endpoint = api_endpoint.format(
                    address=formatted_address,
                    contract=contract_address,
                    api_key=self._get_api_key(network)
                )
            else:
                # Regular cryptocurrency transaction
                api_endpoint = self.api_endpoints.get(network, '')
                if not api_endpoint:
                    return {'success': False, 'message': f'Unsupported network: {network}'}
                
                api_endpoint = api_endpoint.format(
                    address=formatted_address,
                    api_key=self._get_api_key(network)
                )
            
            # Make API request
            response = requests.get(api_endpoint)
            if response.status_code != 200:
                return {'success': False, 'message': f'API error: {response.status_code}'}
            
            tx_data = response.json()
            
            # For token transactions, use the token transaction checker
            if is_token_tx:
                # Get token decimals - defaults vary by token
                token_decimals = {
                    'usdt': 6,  # USDT usually has 6 decimals
                    'usdc': 6,  # USDC usually has 6 decimals
                    'dai': 18,  # DAI has 18 decimals
                    'busd': 18  # BUSD has 18 decimals
                }.get(token_type.lower(), 18)
                
                return self._check_token_transaction(
                    formatted_address, amount, tx_data, max_age_minutes, token_decimals
                )
            
            # Call the appropriate transaction checker based on network
            if network == 'bitcoin':
                return self._check_transaction_bitcoin(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'ethereum':
                return self._check_transaction_ethereum(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'bnb':
                return self._check_transaction_bnb(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'polygon':
                return self._check_transaction_polygon(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'arbitrum':
                return self._check_transaction_arbitrum(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'avalanche':
                return self._check_transaction_avalanche(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'tron':
                return self._check_transaction_tron(formatted_address, amount, tx_data, max_age_minutes)
            elif network == 'solana':
                return self._check_transaction_solana(formatted_address, amount, tx_data, max_age_minutes)
            else:
                return {'success': False, 'message': f'Unsupported network: {network}'}
                
        except Exception as e:
            logger.error(f"Error verifying {network} transaction: {str(e)}")
            return {'success': False, 'message': str(e)}

# Example usage
if __name__ == "__main__":
    # Example API keys (replace with your actual API keys)
    api_keys = {
        'ethereum': 'YOUR_ETHERSCAN_API_KEY',
        'bnb': 'YOUR_BSCSCAN_API_KEY',
        'polygon': 'YOUR_POLYGONSCAN_API_KEY',
        'arbitrum': 'YOUR_ARBISCAN_API_KEY',
        'avalanche': 'YOUR_SNOWTRACE_API_KEY'
    }
    
    verifier = BlockchainVerifier(api_keys)
    
    # Example verification (simulated)
    result = verifier.verify_transaction(
        network='ethereum',
        address='0x742d35Cc6634C0532925a3b844Bc454e4438f44e',
        amount=0.1,
        simulation_mode=True
    )
    
    print(json.dumps(result, indent=2)) 