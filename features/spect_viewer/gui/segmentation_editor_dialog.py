# features/spect_viewer/gui/segmentation_editor_dialog.py - Refactored with modular components
"""
Segmentation editor dialog using modular components.
Significantly reduced code through inheritance and composition.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict
import numpy as np
from PIL import Image

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PySide6.QtGui import QGuiApplication

# Import NEW config paths and cloud storage
from core.config.paths import (
    get_planar_segmentation_files,
    generate_filename_stem,
    extract_study_date_from_dicom
)

# Import for extract session and patient info
from features.dicom_import.logic.dicom_loader import extract_patient_info_from_path

# Import modular components
from .editor_components import (
    BaseEditorDialog,
    SegmentationCanvas,
    SegmentationOpacityPanel,
    SegmentationPalette,
    SegmentationToolPanel,
    SegmentationSaveThread,
    BaseOpacitySlider
)


class SegmentationEditorDialog(BaseEditorDialog):
    """Segmentation editor dialog using modular components."""
    
    def __init__(self, scan: Dict, view: str, parent=None):
        # Initialize data first
        self._setup_data_paths(scan, view)
        self._load_images_and_masks(scan, view)
        
        # Initialize base dialog
        super().__init__(f"Manual Edit – {view}", parent)

    def _setup_data_paths(self, scan: Dict, view: str):
        """Setup file paths for segmentation editing."""
        dicom_path = scan["path"]
        filename_stem = dicom_path.stem
        
        # Extract patient and session info from path
        self.patient_id, self.session_code = extract_patient_info_from_path(dicom_path)
        print(f"[DEBUG] Extracted - Patient ID: {self.patient_id}, Session: {self.session_code}")
        
        # Extract study date for proper naming
        try:
            self.study_date = extract_study_date_from_dicom(dicom_path)
            print(f"[DEBUG] Extracted study date: {self.study_date}")
        except Exception as e:
            print(f"[WARN] Could not extract study date: {e}")
            from datetime import datetime
            self.study_date = datetime.now().strftime("%Y%m%d")
        
        # Validate session info
        self._validate_session_info()
        
        # Use function for edited files support with study date
        filename_stem_with_date = generate_filename_stem(self.patient_id, self.study_date)
        self.seg_files = get_planar_segmentation_files(dicom_path.parent, filename_stem_with_date, view)
        
        # Store paths - prioritize edited versions if they exist
        self.png_mask = self.seg_files['png_mask_edited'] if self.seg_files['png_mask_edited'].exists() else self.seg_files['png_mask']
        self.png_color = self.seg_files['png_colored_edited'] if self.seg_files['png_colored_edited'].exists() else self.seg_files['png_colored']
        
        # Store for saving
        self.dicom_path = Path(dicom_path)
        self.filename_stem_with_date = filename_stem_with_date
        self.view_normalized = view.lower()

    def _validate_session_info(self):
        """Validate session and patient info."""
        if not self.session_code or self.session_code == "UNKNOWN":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "Session Info Missing",
                "Could not determine session code from file path.\n"
                "Files will be saved locally but may not sync to cloud properly."
            )
        
        if not self.patient_id or self.patient_id == "UNKNOWN":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Patient Info Missing", 
                "Could not determine patient ID from file path.\n"
                "Files will be saved locally but may not sync to cloud properly."
            )

    def _load_images_and_masks(self, scan: Dict, view: str):
        """Load original image and segmentation mask."""
        # Load original image (prefer PNG over DICOM)
        orig_png_path = self.dicom_path.parent / f"{self.filename_stem_with_date}_{self.view_normalized}_original.png"
        
        print(f"Looking for original PNG: {orig_png_path}")

        if orig_png_path.exists():
            try:
                self.orig_arr = np.array(Image.open(orig_png_path).convert('L'))
                print(f"✓ Loaded original PNG: {orig_png_path}")
                self.has_orig_png = True
            except Exception as e:
                print(f"✗ Failed to load PNG {orig_png_path}: {e}")
                self.orig_arr = scan["frames"][view]
                self.has_orig_png = False
        else:
            print(f"✗ Original PNG not found: {orig_png_path}")
            if view in scan["frames"]:
                self.orig_arr = scan["frames"][view]
                self.has_orig_png = False
            else:
                available_views = list(scan["frames"].keys())
                raise KeyError(f"View '{view}' not found in frames: {available_views}. PNG also not available.")
        
        # Load mask from PNG if available, or create empty mask
        if self.png_color.exists():
            self.mask_arr = self._load_mask_from_png()
            # Ensure mask has same dimensions as original image
            if self.mask_arr.shape != self.orig_arr.shape:
                print(f"⚠️ WARNING: Mask shape {self.mask_arr.shape} != original shape {self.orig_arr.shape}")
                print("🔄 Resizing mask to match original image...")
                from PIL import Image as PILImage
                mask_pil = PILImage.fromarray(self.mask_arr)
                mask_resized = mask_pil.resize((self.orig_arr.shape[1], self.orig_arr.shape[0]), PILImage.NEAREST)
                self.mask_arr = np.array(mask_resized)
                print(f"✅ Mask resized to: {self.mask_arr.shape}")
        else:
            self.mask_arr = np.zeros_like(self.orig_arr, np.uint8)
            print(f"✅ Created empty mask with shape: {self.mask_arr.shape}")

    def _load_mask_from_png(self) -> np.ndarray:
        """Load mask from PNG colored with prioritized edited version."""
        # Try edited version first
        if self.seg_files['png_colored_edited'].exists():
            png_path = self.seg_files['png_colored_edited']
            print(f"✓ Loading edited mask from: {png_path}")
        elif self.seg_files['png_colored'].exists():
            png_path = self.seg_files['png_colored']
            print(f"✓ Loading original mask from: {png_path}")
        else:
            print(f"✗ No mask files found, creating empty mask")
            return np.zeros((1024, 256), np.uint8)
        
        try:
            from features.spect_viewer.logic.colorizer import _PALETTE
            rgb = np.array(Image.open(png_path).convert("RGB"))
            mask = np.zeros(rgb.shape[:2], np.uint8)
            for lbl, col in enumerate(_PALETTE):
                mask[(rgb == col).all(-1)] = lbl
            print(f"✓ Loaded mask shape: {mask.shape}")
            return mask
        except Exception as e:
            print(f"✗ Failed to load mask from {png_path}: {e}")
            return np.zeros((1024, 256), np.uint8)

    def _create_toolbar(self):
        """Create segmentation-specific toolbar."""
        super()._create_toolbar()
        
        # Palette
        self.palette = SegmentationPalette()
        self.toolbar_layout.addWidget(self.palette)
        
        # Tool panel
        self.tool_panel = SegmentationToolPanel()
        self.toolbar_layout.addWidget(self.tool_panel)
        
        # Opacity panel
        self.opacity_panel = SegmentationOpacityPanel()
        self.toolbar_layout.addWidget(self.opacity_panel)
        
        # Contrast button
        btn_contrast = QPushButton("Contrast…")
        self.toolbar_layout.addWidget(btn_contrast)
        
        # Instructions
        instructions = self._create_instructions_label()
        self.toolbar_layout.addWidget(instructions)
        
        # Save/Cancel buttons
        btn_save = QPushButton("Save")
        btn_cancel = QPushButton("Cancel")
        self.toolbar_layout.addWidget(btn_save)
        self.toolbar_layout.addWidget(btn_cancel)
        self.toolbar_layout.addStretch()
        
        # Store references
        self.btn_contrast = btn_contrast
        self.btn_save = btn_save
        self.btn_cancel = btn_cancel

    def _create_instructions_label(self) -> QLabel:
        """Create instructions with current data info."""
        # Determine data sources
        data_source = "Original PNG loaded" if self.has_orig_png else "DICOM frames used"
        
        # Check if we're loading edited or original mask
        if self.seg_files['png_colored_edited'].exists():
            mask_status = "Edited mask loaded"
        elif self.seg_files['png_colored'].exists():
            mask_status = "Original mask loaded"
        else:
            mask_status = "New mask created"

        instructions = QLabel(
            "<b>Controls:</b><br>"
            "• Left click/drag: Paint<br>"
            "• Middle click/drag: Pan<br>"
            "• Ctrl+scroll: Zoom<br>"
            "• Ctrl+Z: Undo edit<br>"
            "• Ctrl+Y: Redo Edit<br>"
            "• Grid appears at 2x+ zoom<br><br>"
            f"<b>Data Info:</b><br>"
            f"• Image: {data_source}<br>"
            f"• Mask: {mask_status}<br>"
            f"• Session: {self.session_code}<br>"
            f"• Patient: {self.patient_id}<br>"
            f"• Study Date: {self.study_date}<br>"
            f"• Size: {self.orig_arr.shape[1]}×{self.orig_arr.shape[0]}<br>"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("QLabel { background: #f0f0f0; padding: 8px; border-radius: 4px; }")
        return instructions

    def _create_main_area(self):
        """Create main canvas area."""
        super()._create_main_area()
        
        # Info panel
        info_frame = self._create_info_panel()
        self.main_area_layout.addWidget(info_frame)
        
        # Main canvas
        self.canvas = SegmentationCanvas(self.orig_arr, self.mask_arr)
        self.canvas.set_info_callback(self._update_info_display)
        self.main_area_layout.addWidget(self.canvas)

    def _connect_signals(self):
        """Connect UI signals to functionality."""
        # Palette
        self.palette.currentRowChanged.connect(self._change_label)
        
        # Tool panel
        self.tool_panel.connect_to_canvas(self.canvas)
        self.tool_panel.connect_undo_redo(self._perform_undo, self._perform_redo)
        
        # Opacity panel  
        self.opacity_panel.connect_to_canvas(self.canvas)
        
        # Contrast
        self.btn_contrast.clicked.connect(self._open_contrast_popup)
        
        # Save/Cancel
        self.btn_save.clicked.connect(self._save_all)
        self.btn_cancel.clicked.connect(self.reject)

    def _change_label(self, idx: int):
        """Handle palette selection."""
        self.tool_panel.btn_brush.setChecked(True)
        self.tool_panel.btn_eraser.setChecked(False)
        self.canvas.set_label(idx)

    def _perform_undo(self):
        """Perform undo for current layer."""
        current_label = self.palette.list_palette.currentRow()
        self.canvas.undo(current_label)

    def _perform_redo(self):
        """Perform redo for current layer."""
        current_label = self.palette.list_palette.currentRow()
        self.canvas.redo(current_label)

    def _save_all(self):
        """Save using threaded process."""
        save_thread = SegmentationSaveThread(
            self.canvas,
            {
                'png_mask_edited': self.seg_files['png_mask_edited'],
                'png_colored_edited': self.seg_files['png_colored_edited']
            },
            self.patient_id,
            self.session_code,
            self.study_date
        )
        self._start_save_process(SegmentationSaveThread, save_thread)