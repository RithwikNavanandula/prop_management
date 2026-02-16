"""QR Code Generation Service."""
import os
import qrcode
from app.config import get_settings

settings = get_settings()

def generate_qr_code(data: str, filename: str) -> str:
    """
    Generates a QR code image and saves it to the static/qrcodes directory.
    Returns the relative URL path to the image.
    """
    # Ensure directory exists
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    save_dir = os.path.join(base_dir, "static", "qrcodes")
    os.makedirs(save_dir, exist_ok=True)
    
    file_path = os.path.join(save_dir, filename)
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img.save(file_path)
    
    return f"/static/qrcodes/{filename}"
