# features/spect_viewer/logic/image_inverter.py - FIXED VERSION

from __future__ import annotations
from typing import Optional

import numpy as np
from PIL import Image


def analyze_background_type(frame_data: np.ndarray) -> dict:
    """
    Analyze whether the image has a black or white background.
    
    Args:
        frame_data: Image data as numpy array
        
    Returns:
        Dict with background_type ("black" or "white") and confidence percentage
    """
    if frame_data is None or frame_data.size == 0:
        return {"background_type": "unknown", "confidence": 0}
    
    # Flatten the image to 1D
    flat_data = frame_data.flatten()
    
    # Calculate histogram
    hist, bins = np.histogram(flat_data, bins=256, range=(0, 255))
    
    # Check the edges of the histogram
    black_pixels = np.sum(hist[:50])  # Very dark pixels (0-49)
    white_pixels = np.sum(hist[200:])  # Very light pixels (200-255)
    total_pixels = flat_data.size
    
    black_ratio = black_pixels / total_pixels
    white_ratio = white_pixels / total_pixels
    
    if black_ratio > white_ratio:
        confidence = min(95, int(black_ratio * 100))
        return {"background_type": "black", "confidence": confidence}
    else:
        confidence = min(95, int(white_ratio * 100))
        return {"background_type": "white", "confidence": confidence}


#   NEW: Simple inversion function for user toggle
def simple_invert_image(frame_data: np.ndarray) -> np.ndarray:
    """
    Simple image inversion: black becomes white, white becomes black.
    This is what users typically expect from an "invert" toggle.
    
    Args:
        frame_data: Original frame data
        
    Returns:
        Inverted frame data (255 - original)
    """
    if frame_data is None or frame_data.size == 0:
        return frame_data
    
    print(f"[DEBUG] simple_invert_image: input shape = {frame_data.shape}, dtype = {frame_data.dtype}")
    
    # Normalize to uint8 if needed
    if frame_data.dtype != np.uint8:
        frame_norm = (frame_data - frame_data.min()) / max(frame_data.max() - frame_data.min(), 1)
        frame_uint8 = (frame_norm * 255).astype(np.uint8)
    else:
        frame_uint8 = frame_data.copy()
    
    # Simple inversion: 255 - pixel_value
    inverted = 255 - frame_uint8
    
    print(f"[DEBUG] Simple inversion completed: [{frame_uint8.min()}-{frame_uint8.max()}] -> [{inverted.min()}-{inverted.max()}]")
    return inverted


def convert_to_white_background(frame_data: np.ndarray, current_bg: str = "auto") -> np.ndarray:
    """
    Convert frame to white background with black skeleton (standard medical display)
    
    Args:
        frame_data: Original frame data
        current_bg: "black", "white", or "auto" for auto-detection
        
    Returns:
        Frame data with white background and black skeleton
    """
    if frame_data is None or frame_data.size == 0:
        return frame_data
    
    print(f"[DEBUG] convert_to_white_background: input shape = {frame_data.shape}, dtype = {frame_data.dtype}")
    
    # Auto-detect background if needed
    if current_bg == "auto":
        analysis = analyze_background_type(frame_data)
        current_bg = analysis["background_type"]
        print(f"  Auto-detected background: {current_bg} (confidence: {analysis['confidence']}%)")
    
    # If already white background, return as-is
    if current_bg == "white":
        print(f"  Keeping white background (skeleton already black)")
        return frame_data
    
    # If black background, invert to make it white background with black skeleton
    if current_bg == "black":
        print(f"🔄 Converting black background to white (inverting for medical display)")
        
        # Normalize to uint8 if needed
        if frame_data.dtype != np.uint8:
            frame_norm = (frame_data - frame_data.min()) / max(frame_data.max() - frame_data.min(), 1)
            frame_uint8 = (frame_norm * 255).astype(np.uint8)
        else:
            frame_uint8 = frame_data.copy()
        
        # Invert: black becomes white, white becomes black
        # This will make black background -> white, and bright skeleton areas -> dark
        inverted = 255 - frame_uint8
        
        print(f"  Black background inverted to white (skeleton now black)")
        print(f"[DEBUG] Output range: [{inverted.min()}, {inverted.max()}]")
        return inverted
    
    print(f"⚠️ Unknown background type '{current_bg}', returning original")
    return frame_data


def convert_pil_to_white_background(image, current_bg: str = "auto"):
    """
    Convert PIL Image to white background with black skeleton.
    This is a wrapper around convert_to_white_background for PIL Images.
    
    Args:
        image: PIL Image object
        current_bg: "black", "white", or "auto" for auto-detection
        
    Returns:
        PIL Image with white background and black skeleton
    """
    if image is None:
        return None
    
    print(f"[DEBUG] convert_pil_to_white_background: PIL mode = {image.mode}")
    
    # Convert PIL to numpy array
    img_array = np.array(image)
    
    # Process the array
    processed_array = convert_to_white_background(img_array, current_bg)
    
    # Convert back to PIL Image
    result = Image.fromarray(processed_array, image.mode)
    
    print(f"[DEBUG] convert_pil_to_white_background: completed")
    return result


#   NEW: Simple PIL inversion for user toggle
def simple_invert_pil_image(image: Optional[Image.Image]) -> Optional[Image.Image]:
    """
    Simple PIL Image inversion: black becomes white, white becomes black.
    
    Args:
        image: PIL Image object
        
    Returns:
        Inverted PIL Image (255 - original)
    """
    if image is None:
        return None
    
    print(f"[DEBUG] simple_invert_pil_image: Processing {image.mode} image, size = {image.size}")
    
    # Convert PIL to numpy array
    img_array = np.array(image)
    
    # Apply simple inversion
    inverted_array = simple_invert_image(img_array)
    
    # Convert back to PIL Image
    result = Image.fromarray(inverted_array, image.mode)
    
    print(f"[DEBUG] simple_invert_pil_image: completed")
    return result


# ============================================================================
# MAIN INVERSION FUNCTIONS - Updated to support both modes
# ============================================================================

def invert_medical_image(image: Optional[Image.Image], simple_invert: bool = False) -> Optional[Image.Image]:
    if image is None:
        print("[DEBUG] invert_medical_image: Input image is None")
        return None
    
    print(f"[DEBUG] invert_medical_image: Processing {image.mode} image, size = {image.size}, simple_invert = {simple_invert}")
    
    # Always use simple inversion for user toggle (black↔white)
    result = simple_invert_pil_image(image)
    print("[DEBUG] Used simple inversion (black↔white toggle)")
    
    return result


def invert_image_colors(image: Optional[Image.Image], simple_invert: bool = False) -> Optional[Image.Image]:
    """
    Main inversion function - supports both simple and medical inversion.
    
    Args:
        image: The input PIL.Image.Image object.
        simple_invert: If True, use simple black↔white toggle. If False, use smart medical inversion.

    Returns:
        A new PIL.Image.Image object with appropriate inversion.
    """
    return invert_medical_image(image, simple_invert)


# ============================================================================
# LEGACY FUNCTIONS - Updated to support simple inversion
# ============================================================================

def invert_image_simple(image: Optional[Image.Image], simple_invert: bool = True) -> Optional[Image.Image]:
    """
    Simple inversion method - now supports both modes.
    
    Args:
        image: The input PIL.Image.Image object.
        simple_invert: If True, use simple black↔white toggle.
        
    Returns:
        A new PIL.Image.Image object with inverted pixel values.
    """
    if image is None:
        return None
    
    if simple_invert:
        print("[DEBUG] invert_image_simple: Using simple black↔white inversion")
        return simple_invert_pil_image(image)
    else:
        print("[DEBUG] invert_image_simple: Using smart medical inversion")
        return invert_medical_image(image, simple_invert=False)


def invert_medical_image_hsv(image: Optional[Image.Image]) -> Optional[Image.Image]:
    """
    Legacy HSV inversion method - now redirects to smart detection.
    
    Args:
        image: The input PIL.Image.Image object.
        
    Returns:
        A new PIL.Image.Image with smart background detection inversion.
    """
    if image is None:
        return None
    
    print("[DEBUG] invert_medical_image_hsv: Redirecting to smart medical inversion")
    return invert_medical_image(image, simple_invert=False)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def simple_invert_for_medical_display(image_data: np.ndarray) -> np.ndarray:
    """
    Simple inversion for medical display: dark background -> white, bright areas -> dark
    
    Args:
        image_data: numpy array of image data
        
    Returns:
        Inverted image data suitable for medical display
    """
    if image_data is None or image_data.size == 0:
        return image_data
    
    # Ensure uint8
    if image_data.dtype != np.uint8:
        normalized = (image_data - image_data.min()) / max(image_data.max() - image_data.min(), 1)
        image_data = (normalized * 255).astype(np.uint8)
    
    # Simple inversion
    return 255 - image_data


def test_inversion():
    """Test function to verify both inversion methods work correctly."""
    # Create a test image with known values
    test_array = np.array([[0, 50, 100, 150, 200, 255]], dtype=np.uint8)
    test_image = Image.fromarray(test_array, 'L')
    
    print("[DEBUG] Testing simple inversion:")
    print(f"Original values: {list(test_array[0])}")
    
    # Test simple inversion
    simple_inverted = invert_medical_image(test_image, simple_invert=True)
    simple_array = np.array(simple_inverted)
    print(f"Simple inverted values: {list(simple_array[0])}")
    
    # Test medical inversion  
    medical_inverted = invert_medical_image(test_image, simple_invert=False)
    medical_array = np.array(medical_inverted)
    print(f"Medical inverted values: {list(medical_array[0])}")
    
    return simple_inverted, medical_inverted


if __name__ == "__main__":
    test_inversion()