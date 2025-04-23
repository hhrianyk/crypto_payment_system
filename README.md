# Crypto Payment System

An advanced cryptocurrency payment processing system supporting multiple blockchains, tokens, and merchants.

## Features

- **Multiple Blockchain Support**:
  - Bitcoin, Ethereum, Binance Smart Chain, Solana, Tron, Polygon, Arbitrum, Avalanche
  - Support for stablecoins (USDT, USDC, DAI, BUSD) on various chains

- **Enhanced Security**:
  - Two-factor authentication for admin and merchant accounts
  - Message signing for transaction verification
  - IP address filtering for admin access
  - JWT-based authentication with configurable expiry
  - Comprehensive audit logging

- **Advanced Functionality**:
  - Subscription and recurring payment support
  - Multi-merchant architecture with isolation
  - QR code generation for cryptocurrency payments
  - Real-time exchange rates with multiple providers
  - Automatic currency conversion

- **Performance Optimizations**:
  - Redis caching for API responses and blockchain data
  - Asynchronous processing for background tasks
  - Optimized database queries
  - Thread-safe operations

- **User Interface**:
  - Admin dashboard for monitoring transactions
  - Merchant portal for managing payments
  - Client payment pages with QR codes
  - Mobile-responsive design

- **Integration**:
  - RESTful API for integration with external systems
  - Webhook notifications for payment events
  - Email notifications for both merchants and clients

- **Deployment**:
  - Docker containerization for easy deployment
  - Docker Compose for orchestration
  - Nginx for SSL termination and static file serving
  - PostgreSQL for data storage

## Architecture

The application follows a modular architecture with the following components:

- **Core Application (Flask)**: Handles HTTP requests, routing, and business logic
- **Database Layer (SQLAlchemy)**: Manages data persistence and relationships
- **Blockchain Services**: Verifies transactions on different blockchains
- **Payment Processor**: Processes and monitors payments
- **Email Service**: Handles all email communications
- **Authentication Service**: Manages user authentication and security
- **Cache Service**: Provides caching functionality with Redis
- **Exchange Service**: Fetches and manages cryptocurrency exchange rates
- **QR Service**: Generates QR codes for payments
- **Subscription Service**: Manages recurring payments

## Installation

### Prerequisites

- Docker and Docker Compose
- Git

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/crypto_payment_system.git
   cd crypto_payment_system
   ```

2. Create the environment file:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file with your settings, including wallet addresses and API keys.

4. Start the application:
   ```bash
   docker-compose up -d
   ```

5. Access the application:
   - Web application: `http://localhost`
   - Admin panel: `http://localhost/admin`
   - Database admin: `http://localhost:8080`
   - Redis admin: `http://localhost:8081`

### Manual Installation

1. Create a virtual environment:
   ```bash
python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
   ```bash
pip install -r requirements.txt
```

3. Set up the database:
   ```bash
   flask db upgrade
   ```

4. Run the application:
   ```bash
python run.py
```

## Configuration

The system is highly configurable through environment variables. See `.env.example` for the full list of options.

Key configuration sections include:

- **Database Connection**: Configure PostgreSQL or SQLite
- **Blockchain Settings**: API keys and wallet addresses
- **Email Settings**: SMTP server configuration
- **Redis Cache**: Connection settings
- **Security Options**: JWT secret, 2FA settings
- **Feature Flags**: Enable/disable specific features

## API Documentation

The API provides endpoints for:

- Creating payment links
- Checking transaction status
- Managing subscriptions
- Viewing transaction history
- User authentication
- Exchange rate conversion

For detailed API documentation, visit `/api/docs` after starting the application.

## Development

### Running Tests

```bash
pytest
```

### Code Style

```bash
flake8
black .
```

## License

This project is licensed under the MIT License - see the LICENSE file for details. 

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgements

- [Flask](https://flask.palletsprojects.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [Web3.py](https://web3py.readthedocs.io/)
- [Redis](https://redis.io/)
- [Docker](https://www.docker.com/) 