# features/spect_viewer/gui/frame_selector.py - FIXED VERSION
"""
FIXED: Frame selector with proper view change signaling
Ensures timeline gets properly updated when view changes
"""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox


class FrameSelector(QWidget):
    """
    FIXED: Dropdown selector for Anterior | Posterior views
    ✅ Proper signal emission for view changes
    ✅ Enhanced debugging for timeline integration
    """
    # ✅ FIXED: Emit view name instead of index for clarity
    frame_changed = Signal(int)    # Keep original signal for compatibility 
    view_changed = Signal(str)     # NEW: Emit view name directly
    
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        
        self.view_names = ["Anterior", "Posterior"]
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)
        
        layout.addWidget(QLabel("View:", alignment=Qt.AlignRight | Qt.AlignVCenter))
        
        self.combo = QComboBox()
        self.combo.addItems(self.view_names)
        
        # ✅ FIXED: Connect to enhanced handler
        self.combo.currentIndexChanged.connect(self._on_view_changed)
        
        layout.addWidget(self.combo)
        layout.addStretch()
        
        print("[FrameSelector] Initialized with views:", self.view_names)
    
    def _on_view_changed(self, index: int):
        """✅ FIXED: Enhanced view change handler with proper signaling"""
        if 0 <= index < len(self.view_names):
            view_name = self.view_names[index]
            print(f"[FrameSelector] View changed to: {view_name} (index: {index})")
            
            # Emit both signals for compatibility
            self.frame_changed.emit(index)    # Original signal
            self.view_changed.emit(view_name) # NEW: View name signal
        else:
            print(f"[FrameSelector] Invalid view index: {index}")
    
    def current_index(self) -> int:
        """Get current view index"""
        return self.combo.currentIndex()
    
    def current_view(self) -> str:
        """✅ NEW: Get current view name"""
        index = self.current_index()
        if 0 <= index < len(self.view_names):
            return self.view_names[index]
        return "Anterior"  # Default fallback
    
    def set_view(self, view: str):
        """✅ NEW: Set view by name"""
        try:
            index = self.view_names.index(view)
            self.combo.setCurrentIndex(index)
            print(f"[FrameSelector] Set view to: {view} (index: {index})")
        except ValueError:
            print(f"[FrameSelector] Invalid view name: {view}")
    
    def set_view_index(self, index: int):
        """Set view by index"""
        if 0 <= index < len(self.view_names):
            self.combo.setCurrentIndex(index)
            print(f"[FrameSelector] Set view index to: {index}")
        else:
            print(f"[FrameSelector] Invalid view index: {index}")