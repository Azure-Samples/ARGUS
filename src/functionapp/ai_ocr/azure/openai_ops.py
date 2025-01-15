import base64

def load_image(image_path) -> str:
    """Load image from file and encode it as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_size_of_base64_images(images):
    total_size = 0
    for img in images:
        total_size += len(img)
    return total_size
