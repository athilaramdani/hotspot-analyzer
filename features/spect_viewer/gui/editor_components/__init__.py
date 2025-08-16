# features/spect_viewer/gui/editor_components/__init__.py
"""
Modular editor components for SPECT viewer.

This package provides base components and specialized implementations
for hotspot and segmentation editors, following DRY principles.
"""

# Base components
from .base_components import (
    BaseBrightnessContrastPad,
    BaseOpacitySlider,
    BaseCanvas,
    BaseEditorDialog,
    BaseSaveThread
)

# Hotspot components
from .hotspot_components import (
    HotspotCanvas,
    HotspotOpacityPanel,
    HotspotPalette,
    HotspotSaveThread
)

# Segmentation components  
from .segmentation_components import (
    SegmentationCanvas,
    SegmentationOpacityPanel,
    SegmentationPalette,
    SegmentationSaveThread,
    SegmentationToolPanel
)

# Utilities
from .xml_utils import (
    mask_to_bounding_boxes,
    create_xml_from_bboxes,
    save_xml_file
)

__all__ = [
    # Base components
    'BaseBrightnessContrastPad',
    'BaseOpacitySlider', 
    'BaseCanvas',
    'BaseEditorDialog',
    'BaseSaveThread',
    
    # Hotspot components
    'HotspotCanvas',
    'HotspotOpacityPanel',
    'HotspotPalette', 
    'HotspotSaveThread',
    
    # Segmentation components
    'SegmentationCanvas',
    'SegmentationOpacityPanel',
    'SegmentationPalette',
    'SegmentationSaveThread',
    'SegmentationToolPanel',
    
    # Utilities
    'mask_to_bounding_boxes',
    'create_xml_from_bboxes',
    'save_xml_file'
]