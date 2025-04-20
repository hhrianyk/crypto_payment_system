import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

from app import app

if __name__ == '__main__':
    # Get host and port from environment variables or use defaults
    host = '0.0.0.0'  # Changed to listen on all interfaces
    port = 5000
    debug = True  # Force debug mode
    
    print(f"Server starting on http://{host}:{port}")
    print(f"Debug mode: enabled")
    
    try:
        app.run(debug=debug, host=host, port=port)
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        
