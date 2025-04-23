import logging
import qrcode
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='qr_service.log'
)
logger = logging.getLogger('qr_service')

class QRService:
    """
    Service for generating QR codes for cryptocurrency payments
    """
    
    def __init__(self, logo_path=None, box_size=10, border=4, error_correction=qrcode.constants.ERROR_CORRECT_H):
        """
        Initialize QR service
        
        Args:
            logo_path: Path to logo image to overlay on QR codes (optional)
            box_size: Size of each box in the QR code
            border: Border size in boxes
            error_correction: Error correction level
        """
        self.logo_path = logo_path
        self.box_size = box_size
        self.border = border
        self.error_correction = error_correction
        self.logo_image = None
        
        # Load logo if provided
        if self.logo_path and os.path.exists(self.logo_path):
            try:
                self.logo_image = Image.open(self.logo_path)
                logger.info(f"Loaded logo from {self.logo_path}")
            except Exception as e:
                logger.error(f"Error loading logo: {str(e)}")
                self.logo_image = None
    
    def _create_qr_code(self, data, logo=True):
        """
        Create a QR code image
        
        Args:
            data: Data to encode in the QR code
            logo: Whether to add logo overlay (if available)
        
        Returns:
            PIL.Image: QR code image
        """
        try:
            # Create QR code instance
            qr = qrcode.QRCode(
                version=None,  # Auto-determine
                error_correction=self.error_correction,
                box_size=self.box_size,
                border=self.border
            )
            
            # Add data
            qr.add_data(data)
            qr.make(fit=True)
            
            # Create image
            qr_image = qr.make_image(fill_color="black", back_color="white").convert('RGBA')
            
            # Add logo if requested and available
            if logo and self.logo_image:
                # Calculate logo size (max 30% of QR code)
                qr_width, qr_height = qr_image.size
                logo_max_size = int(min(qr_width, qr_height) * 0.3)
                
                # Resize logo
                logo_size = min(self.logo_image.width, self.logo_image.height)
                logo_img = self.logo_image.copy()
                
                if logo_size > logo_max_size:
                    scale_factor = logo_max_size / logo_size
                    new_size = (
                        int(self.logo_image.width * scale_factor),
                        int(self.logo_image.height * scale_factor)
                    )
                    logo_img = logo_img.resize(new_size, Image.Resampling.LANCZOS)
                
                # Calculate position to center logo
                logo_width, logo_height = logo_img.size
                position = (
                    (qr_width - logo_width) // 2,
                    (qr_height - logo_height) // 2
                )
                
                # Create white background for logo
                logo_bg = Image.new('RGBA', logo_img.size, (255, 255, 255, 255))
                logo_bg_width, logo_bg_height = logo_bg.size
                bg_position = (
                    (qr_width - logo_bg_width) // 2,
                    (qr_height - logo_bg_height) // 2
                )
                
                # Paste logo background and logo
                qr_image.paste(logo_bg, bg_position, logo_bg)
                qr_image.paste(logo_img, position, logo_img)
            
            return qr_image
            
        except Exception as e:
            logger.error(f"Error creating QR code: {str(e)}")
            return None
    
    def create_payment_qr(self, address, amount=None, currency=None, message=None, logo=True):
        """
        Create a QR code for a cryptocurrency payment
        
        Args:
            address: Wallet address
            amount: Payment amount (optional)
            currency: Currency code (optional)
            message: Payment description (optional)
            logo: Whether to add logo overlay
        
        Returns:
            PIL.Image: QR code image
        """
        # Create basic payment string with just the address
        payment_data = address
        
        # Add amount and other details if provided
        if amount is not None and currency is not None:
            # Different formats for different cryptocurrencies
            if currency.lower() in ['btc', 'bitcoin']:
                payment_data = f"bitcoin:{address}?amount={amount}"
                if message:
                    payment_data += f"&message={message}"
            
            elif currency.lower() in ['eth', 'ethereum']:
                payment_data = f"ethereum:{address}?value={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            elif currency.lower() in ['bnb', 'bsc']:
                payment_data = f"bnb:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            elif currency.lower() in ['sol', 'solana']:
                payment_data = f"solana:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            elif currency.lower() in ['trx', 'tron']:
                payment_data = f"tron:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            elif currency.lower() in ['matic', 'polygon']:
                payment_data = f"polygon:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            elif currency.lower() in ['arb', 'arbitrum']:
                payment_data = f"arbitrum:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            elif currency.lower() in ['avax', 'avalanche']:
                payment_data = f"avalanche:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
            
            else:
                # Generic format
                payment_data = f"{currency.lower()}:{address}?amount={amount}"
                if message:
                    payment_data += f"&memo={message}"
        
        return self._create_qr_code(payment_data, logo)
    
    def create_url_qr(self, url, logo=True):
        """
        Create a QR code for a URL
        
        Args:
            url: URL to encode
            logo: Whether to add logo overlay
        
        Returns:
            PIL.Image: QR code image
        """
        return self._create_qr_code(url, logo)
    
    def get_image_base64(self, image):
        """
        Convert a PIL image to base64 data URI
        
        Args:
            image: PIL.Image object
        
        Returns:
            str: Base64 data URI
        """
        if not image:
            return None
        
        try:
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode("ascii")
            return f"data:image/png;base64,{img_str}"
        except Exception as e:
            logger.error(f"Error converting image to base64: {str(e)}")
            return None
    
    def create_payment_qr_with_text(self, address, amount, currency, message=None, logo=True):
        """
        Create a QR code with payment information text below
        
        Args:
            address: Wallet address
            amount: Payment amount
            currency: Currency code
            message: Payment description (optional)
            logo: Whether to add logo overlay
        
        Returns:
            PIL.Image: QR code image with text
        """
        try:
            # Create the QR code
            qr_image = self.create_payment_qr(address, amount, currency, message, logo)
            
            if not qr_image:
                return None
            
            # Format text
            text_lines = []
            text_lines.append(f"Amount: {amount} {currency.upper()}")
            
            # Format address with ellipsis if too long
            if len(address) > 20:
                formatted_address = address[:10] + "..." + address[-10:]
            else:
                formatted_address = address
            
            text_lines.append(f"Address: {formatted_address}")
            
            if message:
                text_lines.append(f"Memo: {message}")
            
            # Calculate text size
            font_size = 12
            try:
                # Try to use a good font if available
                font_path = os.path.join(os.path.dirname(__file__), "static", "fonts", "DejaVuSans.ttf")
                if not os.path.exists(font_path):
                    font_path = None
                    logger.warning(f"Font not found: {font_path}")
                
                font = ImageFont.truetype(font_path, font_size) if font_path else None
            except Exception as e:
                logger.warning(f"Error loading font: {str(e)}")
                font = None
            
            # Calculate text height
            line_height = font_size + 4
            text_height = len(text_lines) * line_height + 20  # 20px padding
            
            # Create new image with space for text
            qr_width, qr_height = qr_image.size
            new_height = qr_height + text_height
            
            new_image = Image.new('RGBA', (qr_width, new_height), (255, 255, 255, 255))
            
            # Paste QR code
            new_image.paste(qr_image, (0, 0))
            
            # Add text
            draw = ImageDraw.Draw(new_image)
            
            for i, line in enumerate(text_lines):
                y_position = qr_height + 10 + i * line_height
                
                # Center text
                if font:
                    text_width = draw.textlength(line, font=font)
                    x_position = (qr_width - text_width) // 2
                else:
                    x_position = 10  # Default if font metrics not available
                
                # Draw text
                draw.text(
                    (x_position, y_position),
                    line,
                    fill=(0, 0, 0, 255),
                    font=font
                )
            
            return new_image
            
        except Exception as e:
            logger.error(f"Error creating QR code with text: {str(e)}")
            return None
    
    def save_qr_code(self, qr_image, file_path):
        """
        Save a QR code image to a file
        
        Args:
            qr_image: PIL.Image object
            file_path: Path to save file
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not qr_image:
            return False
        
        try:
            qr_image.save(file_path)
            logger.info(f"QR code saved to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving QR code: {str(e)}")
            return False

# Example usage
if __name__ == "__main__":
    # Create QR service
    qr_service = QRService()
    
    # Create a payment QR code
    btc_address = "bc1q9h60nz0x3d2qn0f5nr587u5c39n0w5hkz9zv2g"
    btc_amount = 0.001
    
    qr_image = qr_service.create_payment_qr_with_text(
        address=btc_address,
        amount=btc_amount,
        currency="BTC",
        message="Test payment"
    )
    
    if qr_image:
        # Save to file
        qr_service.save_qr_code(qr_image, "btc_payment_qr.png")
        
        # Get base64 data URI
        data_uri = qr_service.get_image_base64(qr_image)
        print(f"QR Code Data URI length: {len(data_uri) if data_uri else 0}")
        print("QR code created successfully!") 