# features/spect_viewer/logic/timeline_data_manager.py
"""
Data management logic for SPECT timeline widget
Handles caching, loading, and state management
"""
from __future__ import annotations
from typing import Dict, List, Optional
from PIL import Image

from core.utils.image_converter import create_composite_image
from .layer_processor import LayerProcessor


class TimelineDataManager:
    """Manages data loading and caching for timeline widget"""
    
    def __init__(self, session_code: Optional[str] = None):
        self.session_code = session_code
        self.layer_processor = LayerProcessor(session_code)
        
        # State variables
        self._scans_cache: List[Dict] = []
        self._layer_cache: Dict[int, Dict[str, Image.Image]] = {}  # scan_index -> layers
        self.active_scan_index = 0
        
        # Layer settings
        self._active_layers = []
        self._layer_opacities = {
            "Original": 1.0,
            "Segmentation": 0.7,
            "Hotspot": 0.8,
            "HotspotBBox": 1.0
        }
    
    # ===== Data Management =====
    def set_scans_data(self, scans: List[Dict], active_index: int = -1):
        """Set scan data and clear layer cache"""
        self._scans_cache = scans
        self.active_scan_index = active_index
        self._layer_cache.clear()  # Clear cache when data changes
        print(f"[DEBUG] DataManager: Set {len(scans)} scans, active index: {active_index}")
    
    def get_scans_data(self) -> List[Dict]:
        """Get current scan data"""
        return self._scans_cache
    
    def get_scan_count(self) -> int:
        """Get total number of scans"""
        return len(self._scans_cache)
    
    def get_active_scan_index(self) -> int:
        """Get currently active scan index"""
        return self.active_scan_index
    
    def set_active_scan_index(self, index: int):
        """Set active scan index"""
        if 0 <= index < len(self._scans_cache):
            self.active_scan_index = index
            print(f"[DEBUG] DataManager: Set active scan index to {index}")
    
    # ===== Layer Management =====
    def set_active_layers(self, layers: List[str]):
        """Set active layers"""
        self._active_layers = layers.copy()
        print(f"[DEBUG] DataManager: Active layers set to {self._active_layers}")
    
    def get_active_layers(self) -> List[str]:
        """Get active layers"""
        return self._active_layers.copy()
    
    def is_layer_active(self, layer: str) -> bool:
        """Check if layer is active"""
        return layer in self._active_layers
    
    def set_layer_opacity(self, layer: str, opacity: float):
        """Set layer opacity"""
        self._layer_opacities[layer] = opacity
        print(f"[DEBUG] DataManager: Set {layer} opacity to {opacity:.2f}")
    
    def get_layer_opacity(self, layer: str) -> float:
        """Get layer opacity"""
        return self._layer_opacities.get(layer, 1.0)
    
    def get_all_opacities(self) -> Dict[str, float]:
        """Get all layer opacities"""
        return self._layer_opacities.copy()
    
    # ===== Layer Data Access =====
    def get_layer_images(self, scan_index: int, current_view: str) -> Dict[str, Image.Image]:
        """Get layer images for a specific scan (with caching)"""
        # Check cache first
        if scan_index in self._layer_cache:
            print(f"[DEBUG] DataManager: Using cached layers for scan {scan_index}")
            return self._layer_cache[scan_index]
        
        # Load from disk if not cached
        if scan_index < len(self._scans_cache):
            scan = self._scans_cache[scan_index]
            layers = self.layer_processor.get_layer_images(scan, current_view)
            
            # Cache the result
            self._layer_cache[scan_index] = layers
            print(f"[DEBUG] DataManager: Loaded and cached layers for scan {scan_index}")
            return layers
        
        return {}
    
    def has_layer_data(self, layer: str) -> bool:
        """Check if layer data is available for current scans"""
        if not self._scans_cache:
            return False
        
        try:
            # Check if any scan has data for this layer
            for i, scan in enumerate(self._scans_cache):
                layers = self.get_layer_images(i, "Anterior")  # Use default view for check
                if layer in layers:
                    return True
            return False
        except Exception as e:
            print(f"[WARN] Error checking layer data: {e}")
            return False
    
    def get_processed_layers(self, scan_index: int, current_view: str) -> Dict[str, Image.Image]:
        """Get layers with opacity applied and filtered by active layers"""
        all_layers = self.get_layer_images(scan_index, current_view)
        
        # Apply opacity and filter by active layers
        processed_layers = self.layer_processor.apply_layer_opacities(
            all_layers, self._active_layers, self._layer_opacities
        )
        
        return processed_layers
    
    def create_composite_image(self, scan_index: int, current_view: str) -> Optional[Image.Image]:
        """Create composite image from active layers"""
        if not self._active_layers:
            return None
        
        processed_layers = self.get_processed_layers(scan_index, current_view)
        
        if not processed_layers:
            return None
        
        try:
            # Use opacity 1.0 for all layers since we already applied opacity
            uniform_opacities = {layer: 1.0 for layer in processed_layers.keys()}
            
            composite_image = create_composite_image(
                layers=processed_layers,
                layer_order=self._active_layers,
                layer_opacities=uniform_opacities  # Don't double-apply opacity
            )
            
            return composite_image
            
        except Exception as e:
            print(f"[ERROR] Failed to create composite image: {e}")
            return None
    
    # ===== Cache Management =====
    def clear_layer_cache(self):
        """Clear all cached layer data"""
        self._layer_cache.clear()
        print("[DEBUG] DataManager: Layer cache cleared")
    
    def clear_scan_cache(self, scan_index: int):
        """Clear cache for specific scan"""
        if scan_index in self._layer_cache:
            del self._layer_cache[scan_index]
            print(f"[DEBUG] DataManager: Cleared cache for scan {scan_index}")
    
    def get_cache_info(self) -> Dict:
        """Get cache information for debugging"""
        return {
            "cached_scans": list(self._layer_cache.keys()),
            "cache_size": len(self._layer_cache),
            "total_scans": len(self._scans_cache),
            "active_layers": self._active_layers,
            "opacities": self._layer_opacities
        }
    
    # ===== Session Management =====
    def set_session_code(self, session_code: str):
        """Set session code"""
        self.session_code = session_code
        self.layer_processor.session_code = session_code
        
    def refresh_current_view(self):
        """Refresh current view by clearing cache"""
        self.clear_layer_cache()
        print("[DEBUG] DataManager: Refreshed current view")