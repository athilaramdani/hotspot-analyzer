# core/utils/image_transparency.py
"""
DEPRECATED: This file has been merged into image_converter.py
All transparency functions are now available in core.utils.image_converter

This file should be deleted to avoid duplication and confusion.
All imports should use:
    from core.utils.image_converter import make_black_transparent, load_image_with_transparency, etc.

Instead of:
    from core.utils.image_transparency import ...
"""

# Re-export from image_converter for backward compatibility (temporary)
from .image_converter import (
    make_black_transparent,
    load_image_with_transparency,
    blend_layers_with_transparency,
    create_composite_image,
    apply_opacity_to_image,
    get_layer_preview,
    is_black_pixel,
    get_transparency_stats
)

import warnings

warnings.warn(
    "image_transparency.py is deprecated. Use core.utils.image_converter instead.",
    DeprecationWarning,
    stacklevel=2
)