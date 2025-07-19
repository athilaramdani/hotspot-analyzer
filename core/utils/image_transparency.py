# core/utils/image_transparency.py
"""
Image transparency utilities for layer processing in Hotspot Analyzer.
Handles making black pixels transparent for segmentation and hotspot overlays.
"""

import numpy as np
from PIL import Image
from pathlib import Path
from typing import Union, Tuple, Optional


def make_black_transparent(image: Union[Image.Image, np.ndarray], 
                          tolerance: int = 5) -> Image.Image:
    """
    Convert black pixels (#000000) to transparent in an image.
    
    Args:
        image: PIL Image or numpy array to process
        tolerance: Color tolerance for black detection (0-255)
        
    Returns:
        PIL Image with RGBA mode and transparent black pixels
    """
    # Convert input to PIL Image if needed
    if isinstance(image, np.ndarray):
        if image.dtype != np.uint8:
            # Normalize to 0-255 if needed
            image = ((image - image.min()) / (image.max() - image.min()) * 255).astype(np.uint8)
        
        if len(image.shape) == 2:
            # Grayscale to RGB
            image = Image.fromarray(image).convert('RGB')
        elif len(image.shape) == 3:
            image = Image.fromarray(image)
    
    # Ensure image is in RGBA mode for transparency
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # Convert to numpy array for processing
    data = np.array(image)
    
    # Create mask for black pixels (with tolerance)
    # Black pixels are where R, G, B are all <= tolerance
    black_mask = (
        (data[:, :, 0] <= tolerance) & 
        (data[:, :, 1] <= tolerance) & 
        (data[:, :, 2] <= tolerance)
    )
    
    # Set alpha channel to 0 for black pixels
    data[black_mask, 3] = 0  # Make transparent
    
    # Convert back to PIL Image
    return Image.fromarray(data, 'RGBA')


def load_image_with_transparency(image_path: Path, 
                                make_transparent: bool = True,
                                tolerance: int = 5) -> Image.Image:
    """
    Load an image and optionally make black pixels transparent.
    
    Args:
        image_path: Path to the image file
        make_transparent: Whether to make black pixels transparent
        tolerance: Color tolerance for black detection
        
    Returns:
        PIL Image with or without transparency applied
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Load the image
    image = Image.open(image_path)
    
    # Apply transparency if requested
    if make_transparent:
        image = make_black_transparent(image, tolerance)
    else:
        # Just ensure RGBA mode for consistency
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
    
    return image


def blend_layers_with_transparency(base_layer: Image.Image, 
                                  overlay_layer: Image.Image, 
                                  overlay_opacity: float = 1.0) -> Image.Image:
    """
    Blend two layers where overlay may have transparent pixels.
    
    Args:
        base_layer: Base layer image (usually Original)
        overlay_layer: Overlay layer image (Segmentation or Hotspot)
        overlay_opacity: Global opacity for overlay layer (0.0-1.0)
        
    Returns:
        Blended PIL Image
    """
    # Ensure both images are RGBA
    if base_layer.mode != 'RGBA':
        base_layer = base_layer.convert('RGBA')
    if overlay_layer.mode != 'RGBA':
        overlay_layer = overlay_layer.convert('RGBA')
    
    # Resize overlay to match base if needed
    if overlay_layer.size != base_layer.size:
        overlay_layer = overlay_layer.resize(base_layer.size, Image.Resampling.LANCZOS)
    
    # Convert to numpy arrays
    base_data = np.array(base_layer, dtype=np.float32)
    overlay_data = np.array(overlay_layer, dtype=np.float32)
    
    # Apply global opacity to overlay
    overlay_data[:, :, 3] *= overlay_opacity
    
    # Get alpha channels
    base_alpha = base_data[:, :, 3] / 255.0
    overlay_alpha = overlay_data[:, :, 3] / 255.0
    
    # Calculate combined alpha (Porter-Duff "over" operation)
    combined_alpha = overlay_alpha + base_alpha * (1.0 - overlay_alpha)
    
    # Avoid division by zero
    combined_alpha_safe = np.where(combined_alpha == 0, 1.0, combined_alpha)
    
    # Blend RGB channels
    result_rgb = np.zeros_like(base_data[:, :, :3])
    for i in range(3):  # RGB channels
        result_rgb[:, :, i] = (
            overlay_data[:, :, i] * overlay_alpha + 
            base_data[:, :, i] * base_alpha * (1.0 - overlay_alpha)
        ) / combined_alpha_safe
    
    # Combine result
    result_data = np.zeros_like(base_data)
    result_data[:, :, :3] = result_rgb
    result_data[:, :, 3] = combined_alpha * 255.0
    
    # Convert back to PIL Image
    result_data = np.clip(result_data, 0, 255).astype(np.uint8)
    return Image.fromarray(result_data, 'RGBA')


def create_composite_image(layers: dict, 
                          layer_order: list = None,
                          layer_opacities: dict = None) -> Image.Image:
    """
    Create a composite image from multiple layers.
    
    Args:
        layers: Dict with layer names as keys and PIL Images as values
        layer_order: Order of layers from bottom to top (default: Original, Segmentation, Hotspot)
        layer_opacities: Dict with layer names as keys and opacity values (0.0-1.0) as values
        
    Returns:
        Composite PIL Image
    """
    if layer_order is None:
        layer_order = ["Original", "Segmentation", "Hotspot"]
    
    if layer_opacities is None:
        layer_opacities = {"Original": 1.0, "Segmentation": 0.7, "Hotspot": 0.8}
    
    # Find the first available layer as base
    base_layer = None
    for layer_name in layer_order:
        if layer_name in layers and layers[layer_name] is not None:
            base_layer = layers[layer_name].copy()
            if base_layer.mode != 'RGBA':
                base_layer = base_layer.convert('RGBA')
            
            # Apply base layer opacity if not Original
            if layer_name != "Original":
                opacity = layer_opacities.get(layer_name, 1.0)
                base_layer = apply_opacity_to_image(base_layer, opacity)
            break
    
    if base_layer is None:
        # No layers available, return a blank image
        return Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    
    # Get reference size from base layer
    reference_size = base_layer.size
    
    # Composite remaining layers on top
    result = base_layer
    base_layer_processed = False
    
    for layer_name in layer_order:
        if layer_name not in layers or layers[layer_name] is None:
            continue
            
        # Skip if this was our base layer
        if not base_layer_processed:
            base_layer_processed = True
            continue
        
        overlay = layers[layer_name]
        opacity = layer_opacities.get(layer_name, 1.0)
        
        # Apply transparency to non-Original layers
        if layer_name in ["Segmentation", "Hotspot"]:
            overlay = make_black_transparent(overlay)
        
        # Blend with current result
        result = blend_layers_with_transparency(result, overlay, opacity)
    
    return result


def apply_opacity_to_image(image: Image.Image, opacity: float) -> Image.Image:
    """
    Apply global opacity to an image.
    
    Args:
        image: PIL Image to modify
        opacity: Opacity value (0.0-1.0)
        
    Returns:
        PIL Image with applied opacity
    """
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    data = np.array(image)
    data[:, :, 3] = (data[:, :, 3] * opacity).astype(np.uint8)
    
    return Image.fromarray(data, 'RGBA')


def get_layer_preview(layer_name: str, 
                     image: Image.Image, 
                     make_transparent: bool = True) -> Image.Image:
    """
    Get a preview version of a layer with appropriate processing.
    
    Args:
        layer_name: Name of the layer ("Original", "Segmentation", "Hotspot")
        image: PIL Image to process
        make_transparent: Whether to apply transparency
        
    Returns:
        Processed PIL Image ready for display
    """
    if layer_name == "Original":
        # Original layer - no transparency processing
        if image.mode != 'RGB':
            return image.convert('RGB')
        return image
    
    elif layer_name in ["Segmentation", "Hotspot"]:
        # Apply transparency to overlay layers
        if make_transparent:
            return make_black_transparent(image)
        else:
            if image.mode != 'RGBA':
                return image.convert('RGBA')
            return image
    
    else:
        # Unknown layer type
        if image.mode != 'RGBA':
            return image.convert('RGBA')
        return image


# Utility functions for common operations
def is_black_pixel(rgb_tuple: Tuple[int, int, int], tolerance: int = 5) -> bool:
    """Check if a pixel is considered black within tolerance."""
    r, g, b = rgb_tuple
    return r <= tolerance and g <= tolerance and b <= tolerance


def get_transparency_stats(image: Image.Image) -> dict:
    """Get statistics about transparency in an image."""
    if image.mode != 'RGBA':
        return {"has_transparency": False, "transparent_pixels": 0, "total_pixels": 0}
    
    data = np.array(image)
    alpha_channel = data[:, :, 3]
    
    transparent_pixels = np.sum(alpha_channel == 0)
    total_pixels = alpha_channel.size
    
    return {
        "has_transparency": transparent_pixels > 0,
        "transparent_pixels": int(transparent_pixels),
        "total_pixels": int(total_pixels),
        "transparency_percentage": (transparent_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    }