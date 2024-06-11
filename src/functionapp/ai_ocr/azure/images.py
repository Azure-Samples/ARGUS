import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
import io
import os

def extract_images_from_pdf(pdf_path):
    # Open the PDF file
    pdf_document = fitz.open(pdf_path)
    
    # Iterate through all the pages
    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)
        image_list = page.get_images(full=True)
        
        # Iterate through all the images in the page
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Convert the image to a PIL Image object
            image = Image.open(io.BytesIO(image_bytes))
            
            # Define the output path
            output_path = os.path.join(os.getcwd(), "/tmp/", f"page_{page_num + 1}_img_{img_index + 1}.{image_ext}")
            print(output_path)

            # Save the image as a PNG file
            image.save(output_path, "PNG")
            #print(f"Saved image: {output_path}")