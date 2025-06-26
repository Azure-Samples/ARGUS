import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
import io
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

def convert_pdf_into_image(pdf_path):
    """
    Convert PDF pages to PNG images in a temporary directory.
    Returns the temporary directory path containing the images.
    Caller is responsible for cleaning up the temporary directory.
    """
    # Create a temporary directory for the images
    temp_dir = tempfile.mkdtemp(prefix="pdf_images_")
    
    # Open the PDF file
    pdf_document = None
    try:
        pdf_document = fitz.open(pdf_path)
        
        # Iterate through all the pages
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            # Convert the page to an image  
            pix = page.get_pixmap()  

            # Convert the pixmap to bytes  
            image_bytes = pix.tobytes("png")  
            
            # Convert the image to a PIL Image object
            image = Image.open(io.BytesIO(image_bytes))
            
            # Define the output path in the temporary directory
            output_path = os.path.join(temp_dir, f"page_{page_num + 1}.png")

            # Save the image as a PNG file
            image.save(output_path, "PNG")
            logger.debug(f"Saved image: {output_path}")
            
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        raise
    finally:
        # Ensure PDF document is properly closed
        if pdf_document:
            pdf_document.close()
    
    return temp_dir
