# features/spect_viewer/gui/segmentation_editor_dialog.py - Fixed duplicate method
"""
Segmentation editor dialog using modular components.
Fixed mask loading logic and simplified saving to match hotspot editor pattern.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict
import numpy as np
from PIL import Image
import datetime
import json
from datetime import datetime
import time
import csv
from core.config.paths import PLANAR_DATA_PATH, generate_edit_date, generate_edit_timestamp
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame, QCheckBox,QScrollArea  
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
    SegmentationSaveThread
)

# Import colorizer for mask processing
from features.spect_viewer.logic.colorizer import label_mask_to_rgb, _PALETTE
from core.gui.loading_dialog import LoadingDialog, show_loading_dialog

class SegmentationEditorDialog(BaseEditorDialog):
    """Segmentation editor dialog using modular components."""
    editor_completed = Signal()
    def __init__(self, scan: Dict, view: str, parent=None):
        # 1. STORE INITIAL DATA
        self.scan = scan
        self.view = view
        view_key = view.lower()
        vtag = "ant" if "ant" in view_key else "post"

        # 2. ASSIGN DICOM PATH FIRST (before using it)
        self.dicom_path = Path(scan["path"])

        # 3. Extract patient info needed for getting newest paths
        patient_folder = self.dicom_path.parent
        self.patient_id = patient_folder.parent.name
        self.session_code = patient_folder.parent.parent.name
        self.study_date = extract_study_date_from_dicom(self.dicom_path)
        self.filename_stem = generate_filename_stem(self.patient_id, self.study_date)
        self.view_short = vtag

        # 4. LOAD ORIGINAL IMAGE DATA FIRST
        workflow_files = self.scan.get('workflow_files', {})
        original_png_path = workflow_files.get('original', {}).get(vtag)

        if original_png_path and original_png_path.exists():
            self.original_image_data = np.array(Image.open(original_png_path).convert('L'))
        else:
            # Fallback to raw DICOM frame if original PNG is missing
            self.original_image_data = scan["frames"][view_key]

        from features.spect_viewer.logic.image_inverter import simple_invert_image
        self.processed_image_data = simple_invert_image(self.original_image_data.copy())

        # 4. GET NEWEST PATHS USING YOUR NEW METHODS (like hotspot editor)
        from core.config.paths import get_newest_segmentation_path
        
        # Use the newest segmentation file
        self.segmentation_path = get_newest_segmentation_path(patient_folder, view)

        # 5. LOAD IMAGES AND MASKS (using the newest paths)
        # Get original image path from workflow_files (this should be correct)
        workflow_files = self.scan.get('workflow_files', {})
        original_png_path = workflow_files.get('original', {}).get(vtag)
        
        if original_png_path and original_png_path.exists():
            self.orig_arr = np.array(Image.open(original_png_path).convert('L'))
            self.has_orig_png = True
        else:
            # Fallback to raw DICOM frame if original PNG is missing
            self.orig_arr = scan["frames"][view_key]
            self.has_orig_png = False

        # Load mask using the newest segmentation path
        self.mask_arr = self._load_existing_mask()

        # 6. INITIALIZE THE BASE DIALOG UI
        super().__init__(f"Manual Edit – {view}", parent)
        # 8. INITIALIZE TIMER
        self._setup_editing_timer()
        # 9. INITIALIZE EDITOR SESSION
        self.editor_session = None

    def _load_existing_mask(self) -> np.ndarray:
        """Load existing mask with proper priority using NEWEST paths."""
        
        # Debug output to show which files we're using
        print(f"🔍 [SEGMENTATION LOAD] Loading mask for {self.view_short}")
        print(f"🔍 [SEGMENTATION LOAD] Segmentation file: {self.segmentation_path}")
        print(f"🔍 [SEGMENTATION LOAD] File exists: {self.segmentation_path.exists() if self.segmentation_path else False}")
        
        # The path self.segmentation_path now points to the NEWEST file
        if self.segmentation_path and self.segmentation_path.exists():
            print(f"✓ Loading NEWEST segmentation mask from: {self.segmentation_path.name}")
            return self._load_mask_from_segmentation_png(self.segmentation_path)
        else:
            print(f"✗ No segmentation data found. Creating empty mask.")
            return np.zeros_like(self.orig_arr, np.uint8)
    
    def _on_invert_changed(self, state: int):
        """Handle image inversion toggle."""
        from features.spect_viewer.logic.image_inverter import simple_invert_image
        
        try:
            if self.invert_checkbox.isChecked():
                inverted_data = simple_invert_image(self.original_image_data)
            else:
                inverted_data = self.original_image_data.copy()
            
            # Recreate the canvas with new image data
            old_canvas = self.canvas
            self.canvas = SegmentationCanvas(inverted_data, self.mask_arr)
            self.canvas.set_info_callback(self._update_info_display)
            
            # Replace in layout
            self.main_area_layout.replaceWidget(old_canvas, self.canvas)
            old_canvas.deleteLater()
            
            # Reconnect tool panel signals
            self.tool_panel.connect_to_canvas(self.canvas)
            self.opacity_panel.connect_to_canvas(self.canvas)
            
        except Exception as e:
            print(f"✗ Error during image inversion: {e}")
            self.invert_checkbox.setChecked(not self.invert_checkbox.isChecked())
    def _load_mask_from_segmentation_png(self, segmentation_path: Path) -> np.ndarray:
        """Load mask from segmentation PNG file."""
        try:
            img = Image.open(segmentation_path)
            
            # Check if image is colored (RGB/RGBA) or grayscale
            if img.mode in ['RGB', 'RGBA']:
                print(f"  Loading as colored segmentation from: {segmentation_path.name}")
                return self._load_mask_from_colored_png(segmentation_path)
            else:
                # Load as grayscale mask
                print(f"  Loading as grayscale segmentation from: {segmentation_path.name}")
                mask = np.array(img.convert('L'))
                
                # Convert grayscale values to label indices if needed
                # Assuming segmentation uses label indices directly
                unique_vals = np.unique(mask)
                print(f"✓ Loaded grayscale mask with unique values: {unique_vals}")
                return mask
                
        except Exception as e:
            print(f"✗ Failed to load segmentation mask: {e}")
            return np.zeros_like(self.orig_arr, np.uint8)

    def _load_mask_from_colored_png(self, png_path: Path) -> np.ndarray:
        """Load mask from colored PNG file using proper palette."""
        try:
            from features.spect_viewer.logic.colorizer import _PALETTE
            
            rgb = np.array(Image.open(png_path).convert("RGB"))
            mask = np.zeros(rgb.shape[:2], np.uint8)
            
            # Use the correct palette from colorizer
            for lbl, col in enumerate(_PALETTE):
                matches = (rgb == col).all(-1)
                mask[matches] = lbl
                if matches.any():
                    print(f"  Found {matches.sum()} pixels for label {lbl} (color {col})")
            
            print(f"✓ Loaded colored segmentation mask with {len(np.unique(mask))} unique labels: {np.unique(mask)}")
            return mask
            
        except Exception as e:
            print(f"✗ Failed to load colored segmentation mask from {png_path}: {e}")
            return np.zeros_like(self.orig_arr, np.uint8)
        
    def _setup_data_paths(self):
        """Set up all necessary file paths for segmentation data."""
        self.dicom_path = self.scan_data["path"]
        patient_folder = self.dicom_path.parent

        # Extract patient info
        self.patient_id, self.session_code = extract_patient_info_from_path(self.dicom_path)
        try:
            self.study_date = extract_study_date_from_dicom(self.dicom_path)
        except Exception:
            from datetime import datetime
            self.study_date = datetime.now().strftime("%Y%m%d")

        self._validate_session_info()

        # ✅ CORRECTED: Use proper filename stem with study date
        filename_stem_with_date = generate_filename_stem(self.patient_id, self.study_date)
        self.seg_files = get_planar_segmentation_files(patient_folder, filename_stem_with_date, self.view)
        
        # ✅ FIX: Correct the paths based on actual view
        # The get_planar_segmentation_files() function seems to be returning wrong paths
        # Let's fix them based on the actual view
        view_short = self.view.lower()[:3]  # "anterior" -> "ant", "posterior" -> "pos"
        
        # Create corrected paths
        corrected_seg_files = {}
        for key, path in self.seg_files.items():
            if path:
                # Replace the view part in the filename
                filename = path.name
                if 'post_' in filename and view_short == 'ant':
                    # Replace post_ with ant_
                    new_filename = filename.replace('post_', 'ant_')
                    corrected_seg_files[key] = path.parent / new_filename
                elif 'ant_' in filename and view_short == 'pos':
                    # Replace ant_ with post_
                    new_filename = filename.replace('ant_', 'post_')
                    corrected_seg_files[key] = path.parent / new_filename
                else:
                    corrected_seg_files[key] = path
            else:
                corrected_seg_files[key] = path
        
        self.seg_files = corrected_seg_files
        
        # Debug: Print available keys and actual paths
        print(f"DEBUG: Available seg_files keys: {list(self.seg_files.keys())}")
        for key, path in self.seg_files.items():
            exists = path.exists() if path else False
            print(f"  {key}: {path} (exists: {exists})")

    def _validate_session_info(self):
        """Validate session and patient info."""
        if not getattr(self, 'session_code', None) or self.session_code == "UNKNOWN":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, 
                "Session Info Missing",
                "Could not determine session code from file path.\n"
                "Files will be saved locally but may not sync to cloud properly."
            )
        
        if not getattr(self, 'patient_id', None) or self.patient_id == "UNKNOWN":
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Patient Info Missing", 
                "Could not determine patient ID from file path.\n"
                "Files will be saved locally but may not sync to cloud properly."
            )

    def _load_images_and_masks(self):
        """Load original image and segmentation mask with corrected logic."""
        # ✅ CORRECTED: Load original PNG with proper naming
        filename_stem_with_date = generate_filename_stem(self.patient_id, self.study_date)
        patient_folder = self.dicom_path.parent
        view_normalized = self.view.lower()
        
        # Look for original PNG file
        orig_png_path = patient_folder / f"{filename_stem_with_date}_{view_normalized}_original.png"
        
        print(f"Looking for original PNG: {orig_png_path}")
        
        if orig_png_path.exists():
            try:
                self.orig_arr = np.array(Image.open(orig_png_path).convert('L'))
                print(f"✓ Loaded original PNG: {orig_png_path}")
                self.has_orig_png = True
            except Exception as e:
                print(f"✗ Failed to load PNG {orig_png_path}: {e}")
                self._load_from_scan_frames()
                self.has_orig_png = False
        else:
            print(f"✗ Original PNG not found: {orig_png_path}")
            self._load_from_scan_frames()
            self.has_orig_png = False

        # ✅ CORRECTED: Load mask with proper priority and path handling
        self.mask_arr = self._load_mask_from_available_sources()

        # Ensure mask has same dimensions as original image
        if self.mask_arr.shape != self.orig_arr.shape:
            print(f"⚠️ WARNING: Mask shape {self.mask_arr.shape} != original shape {self.orig_arr.shape}")
            print("🔄 Resizing mask to match original image...")
            mask_pil = Image.fromarray(self.mask_arr)
            mask_resized = mask_pil.resize((self.orig_arr.shape[1], self.orig_arr.shape[0]), Image.NEAREST)
            self.mask_arr = np.array(mask_resized)
            print(f"✅ Mask resized to: {self.mask_arr.shape}")

        print(f"✅ Final mask loaded with shape: {self.mask_arr.shape}, unique values: {np.unique(self.mask_arr)}")

    def _load_from_scan_frames(self):
        """Load from scan frames with case-insensitive matching."""
        def find_matching_view(target_view: str, available_views: list) -> str:
            """Find matching view name, handling case differences."""
            target_lower = target_view.lower()
            for available_view in available_views:
                if available_view.lower() == target_lower:
                    return available_view
            return None
        
        # Try case-insensitive matching
        matching_view = find_matching_view(self.view, list(self.scan_data["frames"].keys()))
        if matching_view:
            self.orig_arr = self.scan_data["frames"][matching_view]
            print(f"✓ Using scan frame '{matching_view}' for view '{self.view}'")
        else:
            available_views = list(self.scan_data["frames"].keys())
            raise KeyError(f"View '{self.view}' not found in frames: {available_views}")

    def _load_mask_from_available_sources(self) -> np.ndarray:
        """✅ FIXED: Load mask from available files with safe key access."""
        print(f"DEBUG: Looking for mask files for view '{self.view}'")
        
        # Define possible key mappings based on your actual file structure
        possible_keys = [
            'segmentation_png',  # Your actual key name
            'mask_png',          # Your actual key name  
            'png_colored_edited',
            'colored_edited', 
            'png_colored',
            'colored',
            'png_segm',
            'segm'
        ]
        
        # Try to find existing colored/segmentation files
        for key in possible_keys:
            if key in self.seg_files:
                path = self.seg_files[key]
                print(f"  Checking key '{key}': {path}")
                if path and path.exists():
                    print(f"✅ Loading mask from: {path}")
                    
                    # Handle different file types
                    if key in ['segmentation_png', 'mask_png']:
                        # These might be grayscale masks, try both colored and grayscale loading
                        mask = self._load_mask_from_file(path)
                    else:
                        # These are colored masks
                        mask = self._load_mask_from_colored_png(path)
                    
                    if mask is not None:
                        # Check if the loaded mask is empty
                        if np.all(mask == 0):
                            print(f"⚠️ WARNING: Loaded mask file '{path.name}' is all black (empty).")
                        else:
                            print(f"✅ Loaded mask with {len(np.unique(mask))} unique values: {np.unique(mask)}")
                        return mask
                else:
                    print(f"  Key '{key}' path does not exist: {path}")
        
        print(f"❌ No valid segmentation file found. Creating empty mask.")
        return np.zeros_like(self.orig_arr, dtype=np.uint8)

    def _load_mask_from_file(self, png_path: Path) -> np.ndarray:
        """✅ NEW: Load mask from file, handling both colored and grayscale formats."""
        try:
            img = Image.open(png_path)
            
            # Check if image is colored (RGB/RGBA) or grayscale
            if img.mode in ['RGB', 'RGBA']:
                print(f"  Loading as colored mask from: {png_path.name}")
                return self._load_mask_from_colored_png(png_path)
            else:
                # Load as grayscale mask
                print(f"  Loading as grayscale mask from: {png_path.name}")
                mask = np.array(img.convert('L'))
                print(f"✓ Loaded grayscale mask with unique values: {np.unique(mask)}")
                return mask
                
        except Exception as e:
            print(f"✗ Failed to load mask from {png_path}: {e}")
            return np.zeros((self.orig_arr.shape[0], self.orig_arr.shape[1]), np.uint8)

    def _create_toolbar(self):
        """✅ MODULAR: Create segmentation-specific toolbar using modular components."""
        super()._create_toolbar()
        
        # Palette component
        self.palette = SegmentationPalette()
        self.toolbar_layout.addWidget(self.palette)
        
        # Tool panel component
        self.tool_panel = SegmentationToolPanel()
        self.toolbar_layout.addWidget(self.tool_panel)
        
        # Opacity panel component
        self.opacity_panel = SegmentationOpacityPanel()
        self.toolbar_layout.addWidget(self.opacity_panel)
        
        # Contrast button
        btn_contrast = QPushButton("Contrast…")
        self.toolbar_layout.addWidget(btn_contrast)

        # Invert checkbox
        self.invert_checkbox = QCheckBox("Invert Image Colors")
        self.invert_checkbox.setChecked(True)
        self.invert_checkbox.setStyleSheet("margin-top: 8px; font-weight: bold;")
        self.toolbar_layout.addWidget(self.invert_checkbox)
        
        # Instructions
        instructions = self._create_instructions_label()
        self.toolbar_layout.addWidget(instructions)
          # Timer display
        self.timer_widget = self._create_timer_widget()
        self.toolbar_layout.addWidget(self.timer_widget)
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

    def _create_instructions_label(self) -> QWidget:
        """Create instructions with current data info using NEWEST file logic."""
        data_source = "Original PNG loaded" if self.has_orig_png else "DICOM frames used"
        
        # ✅ UPDATED LOGIC: Show info about newest segmentation file loaded
        mask_status = ""
        
        if self.segmentation_path and self.segmentation_path.exists():
            # Check if this is a timestamped (edited) version
            if "_" in self.segmentation_path.stem:
                segm_parts = self.segmentation_path.stem.split("_")
                if len(segm_parts) >= 3 and len(segm_parts[-1]) == 6 and segm_parts[-1].isdigit():
                    timestamp = segm_parts[-1]
                    # Extract date from parent folder
                    date_folder = self.segmentation_path.parent.name
                    if len(date_folder) == 8 and date_folder.isdigit():
                        mask_status = f"✨ NEWEST edited segmentation: {date_folder} {timestamp[:2]}:{timestamp[2:4]}:{timestamp[4:6]}"
                    else:
                        mask_status = f"✨ NEWEST edited segmentation ({self.segmentation_path.name})"
                else:
                    mask_status = "Original segmentation loaded"
            else:
                mask_status = "Original segmentation loaded"
        else:
            mask_status = "New segmentation will be created"

        session_code = getattr(self, 'session_code', 'Unknown')
        patient_id = getattr(self, 'patient_id', 'Unknown')
        study_date = getattr(self, 'study_date', 'Unknown')

        # ✅ CREATE COMPACT SCROLLABLE INSTRUCTIONS
        # Create main container
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(5, 5, 5, 5)
        container_layout.setSpacing(3)
        
        # Header label
        header_label = QLabel("<b>Instructions & Data Info</b>")
        header_label.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #333;
                padding: 3px;
                background: #e8f4f8;
                border-radius: 3px;
            }
        """)
        container_layout.addWidget(header_label)
        
        # Create scrollable area for instructions
        scroll_area = QScrollArea()
        scroll_area.setMaximumHeight(120)  # ✅ Compact height
        scroll_area.setMinimumHeight(100)  # ✅ Minimum height
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Instructions content
        instructions_content = QLabel(
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
            f"• Session: {session_code}<br>"
            f"• Patient: {patient_id}<br>"
            f"• Study Date: {study_date}<br>"
            f"• Size: {self.processed_image_data.shape[1]}×{self.processed_image_data.shape[0]}<br>"
            f"• Save: Creates new timestamped file"
        )
        instructions_content.setWordWrap(True)
        instructions_content.setStyleSheet("""
            QLabel {
                background: #f9f9f9;
                padding: 6px;
                border-radius: 4px;
                font-size: 12px;        /* ✅ BIGGER FONT: 10px -> 12px */
                line-height: 1.4;       /* ✅ BETTER SPACING */
                color: #333;            /* ✅ DARKER COLOR */
                font-weight: 500;       /* ✅ MEDIUM WEIGHT */
            }
        """)
        
        scroll_area.setWidget(instructions_content)
        container_layout.addWidget(scroll_area)
        
        # Style the container with height limit
        container.setMaximumHeight(180)  # ✅ LIMIT TOTAL HEIGHT
        container.setStyleSheet("""
            QWidget {
                background: #f0f0f0;
                border-radius: 4px;
            }
        """)
        
        return container


    def _create_main_area(self):
        """✅ MODULAR: Create main canvas area using modular components."""
        super()._create_main_area()
        
        # Info panel
        info_frame = self._create_info_panel()
        self.main_area_layout.addWidget(info_frame)
        
        # Main canvas - using modular SegmentationCanvas
        self.canvas = SegmentationCanvas(self.processed_image_data, self.mask_arr)
        self.canvas.set_info_callback(self._update_info_display)
        self.main_area_layout.addWidget(self.canvas)

    def _create_info_panel(self) -> QFrame:
        """Create info display panel."""
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.Box)
        info_frame.setMaximumHeight(60)
        info_layout = QHBoxLayout(info_frame)
        
        self.lbl_image_info = QLabel("Image: 0×0")
        self.lbl_zoom_info = QLabel("Zoom: 1.0x")
        self.lbl_grid_info = QLabel("Grid: Off")
        
        info_layout.addWidget(QLabel("<b>Info:</b>"))
        info_layout.addWidget(self.lbl_image_info)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.lbl_zoom_info)
        info_layout.addWidget(QLabel("|"))
        info_layout.addWidget(self.lbl_grid_info)
        info_layout.addStretch()
        
        return info_frame

    def _update_info_display(self, width: int, height: int, zoom: float, grid_size: int):
        """Update the info display."""
        self.lbl_image_info.setText(f"Image: {width}×{height}")
        self.lbl_zoom_info.setText(f"Zoom: {zoom:.1f}x")
        if zoom >= 2.0:
            if grid_size == 1:
                self.lbl_grid_info.setText("Grid: 1px")
            else:
                self.lbl_grid_info.setText(f"Grid: {grid_size}px")
        else:
            self.lbl_grid_info.setText("Grid: Off")

    def _connect_signals(self):
        """✅ MODULAR: Connect UI signals using modular components."""
        # Palette signals
        self.palette.currentRowChanged.connect(self._change_label)
        
        # Tool panel signals
        self.tool_panel.connect_to_canvas(self.canvas)
        self.tool_panel.connect_undo_redo(self._perform_undo, self._perform_redo)
        
        # Opacity panel signals
        self.opacity_panel.connect_to_canvas(self.canvas)

        # Contrast and invert
        self.btn_contrast.clicked.connect(self._open_contrast_popup)
        self.invert_checkbox.stateChanged.connect(self._on_invert_changed)
        
        # Contrast button
        self.btn_contrast.clicked.connect(self._open_contrast_popup)
        
        # Save/Cancel buttons
        self.btn_save.clicked.connect(self._save_all)
        self.btn_cancel.clicked.connect(self.reject)
        self.setFocus()
        
        print("✅ All signals connected in SegmentationEditorDialog")

    def _change_label(self, idx: int):
        """Handle palette selection."""
        self.tool_panel.btn_brush.setChecked(True)
        self.tool_panel.btn_eraser.setChecked(False)
        self.canvas.set_label(idx)

    def _perform_undo(self):
        """Perform undo for current layer."""
        """Perform undo for current layer - IMPROVED implementation."""
        print("🔍 _perform_undo called in SegmentationEditorDialog")
        
        # ✅ FIX: Add safety checks and better error handling
        if not hasattr(self, 'palette') or not self.palette:
            print("❌ No palette available for undo")
            return
            
        if not hasattr(self, 'canvas') or not self.canvas:
            print("❌ No canvas available for undo")
            return
        
        current_label = self.palette.list_palette.currentRow()
        if current_label < 0:
            print("❌ No valid label selected for undo")
            return
            
        print(f"🔄 Performing undo for label {current_label}")
        
        # Call canvas undo method
        try:
            self.canvas.undo(current_label)
            print("✅ Undo operation completed")
        except Exception as e:
            print(f"❌ Undo failed: {e}")

    def _perform_redo(self):
        """Perform redo for current layer."""
        print("🔍 _perform_redo called in SegmentationEditorDialog")
        
        # ✅ FIX: Add safety checks and better error handling
        if not hasattr(self, 'palette') or not self.palette:
            print("❌ No palette available for redo")
            return
            
        if not hasattr(self, 'canvas') or not self.canvas:
            print("❌ No canvas available for redo")
            return
        
        current_label = self.palette.list_palette.currentRow()
        if current_label < 0:
            print("❌ No valid label selected for redo")
            return
            
        print(f"🔄 Performing redo for label {current_label}")
        
        # Call canvas redo method
        try:
            self.canvas.redo(current_label)
            print("✅ Redo operation completed")
        except Exception as e:
            print(f"❌ Redo failed: {e}")


    def _save_all(self):
        """Save segmentation data with proper session handling (same as hotspot editor)."""
        # Handle session selection for ALL users (same logic as hotspot editor)
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        elapsed_seconds, formatted_time = self._get_editing_duration()
        
        # Handle session selection for ALL users
        self.editor_session = None
        if self.session_code == "ALL":
            session_choice = self._show_session_selector_dialog()
            if not session_choice:
                # Resume timer if user cancels
                if hasattr(self, 'update_timer'):
                    self.update_timer.start(1000)
                return  # User cancelled
            self.editor_session = session_choice
        
        # Show loading dialog immediately after session selection
        self.save_loading_dialog = LoadingDialog(
            title="Saving Segmentation",
            message="Preparing to save segmentation data...",
            show_progress=True,
            show_cancel=False,
            parent=self
        )
        self.save_loading_dialog.show()
        
        # Disable save button during save operation
        self.btn_save.setEnabled(False)
        
        try:
            # Create and start save thread with editor session (same as hotspot editor)
            self.save_thread = SegmentationSaveThread(
                canvas=self.canvas,
                session_path=self._get_session_base_path(),
                patient_id=self.patient_id,
                view_short=self.view_short,
                filename_stem=self.filename_stem,
                dicom_path=self.dicom_path,
                study_date=self.study_date,
                current_session=self.session_code,
                editor_session=self.editor_session
            )
            
            # ✅ FIX: Connect signals - HANYA GUNAKAN SATU COMPLETION SIGNAL
            if hasattr(self.save_thread, 'progress_updated'):
                self.save_thread.progress_updated.connect(self._update_progress)

            # ✅ GUNAKAN HANYA save_completed (yang ada editing time)
            if hasattr(self.save_thread, 'save_completed'):
                self.save_thread.save_completed.connect(self._on_save_success)

            # ✅ HAPUS finished connection untuk avoid duplicate dialog
            # self.save_thread.finished.connect(self._on_save_finished)  # HAPUS INI

            if hasattr(self.save_thread, 'error_occurred'):
                self.save_thread.error_occurred.connect(self._on_save_error)
            
            # Start the thread
            self.save_thread.start()
            
        except Exception as e:
            # Re-enable save button if there's an error during setup
            self.btn_save.setEnabled(True)
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Save Error", f"Failed to start save operation: {str(e)}")
            
    def _on_save_success(self, success_message: str):
        """Handle successful save with message."""
        from PySide6.QtWidgets import QMessageBox
        
        # Close loading dialog
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.close()
            self.save_loading_dialog = None
        
        # Save editing time to log
        elapsed_seconds, formatted_time = self._get_editing_duration()
        self._save_editing_time_log(elapsed_seconds, formatted_time)
        
        # Get save information if available
        if hasattr(self.save_thread, 'get_save_info'):
            save_info = self.save_thread.get_save_info()
            if save_info and save_info:
                detailed_message = (
                    f"Files saved successfully!\n\n"
                    f"Location: {save_info.get('date_dir', 'Unknown')}\n"
                    f"Files:\n"
                    f"• {save_info.get('png_path', {}).name if save_info.get('png_path') else 'File 1'}\n"
                    f"• {save_info.get('xml_path', {}).name if save_info.get('xml_path') else 'File 2'}\n\n"
                    f"⏱️ Editing Time: {formatted_time}"
                )
            else:
                detailed_message = f"{success_message}\n\n⏱️ Editing Time: {formatted_time}"
        else:
            detailed_message = f"{success_message}\n\n⏱️ Editing Time: {formatted_time}"
        
        # Re-enable save button
        self.btn_save.setEnabled(True)
        
        # Show ONE dialog with editing time
        QMessageBox.information(self, "Save Complete", detailed_message)
        
        # Emit signal and close
        if hasattr(self, 'editor_completed'):
            self.editor_completed.emit()
        
        # Close dialog
        self.accept()

    def _on_save_finished(self):
        """Handle save thread completion (cleanup only - same as hotspot editor)."""
        # Re-enable save button
        self.btn_save.setEnabled(True)
        
        # Note: Success message is handled by _on_save_success
        # This method only handles cleanup

    def _on_save_error(self, error_message: str):
        """Handle save errors (same as hotspot editor)."""
        from PySide6.QtWidgets import QMessageBox
        
        # Close loading dialog
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.close()
            self.save_loading_dialog = None
        
        QMessageBox.critical(self, "Save Error", error_message)
        
        # Re-enable save button
        self.btn_save.setEnabled(True)


    def _get_session_base_path(self) -> Path:
        """Get the base session path for saving files (same as hotspot editor)."""
        if hasattr(self, 'segmentation_path') and self.segmentation_path:
            # Navigate up to PLANAR level from segmentation file
            # Example: .../PLANAR/ATL/5001/20250115/ant_segm.png
            # We want: .../PLANAR
            current_path = Path(self.segmentation_path)
            # Go up levels: filename -> study_date -> patient -> session -> PLANAR
            return current_path.parent.parent.parent.parent
        
        # Fallback to config path
        from core.config.paths import PLANAR_DATA_PATH
        return PLANAR_DATA_PATH

    def _show_session_selector_dialog(self):
        """Show session selector dialog reading from doctor_tags.json."""
        import json
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem
        from PySide6.QtCore import Qt
        
        try:
            # Load doctor tags from config file using proper config path
            from core.config.paths import CONFIG_ROOT
            config_path = CONFIG_ROOT / "doctor_tags.json"
            
            if not config_path.exists():
                print(f"Config file not found: {config_path}")
                return "NSY"  # Fallback to default
            
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            # Filter out "ALL" and get available tags
            available_tags = [tag for tag in config_data.get("doctor_tags", []) if tag.get("code") != "ALL"]
            
            if not available_tags:
                print("No available doctor tags found")
                return "NSY"  # Fallback to default
            
            # Create dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Select Session Code")
            dialog.setModal(True)
            dialog.resize(400, 300)
            
            layout = QVBoxLayout(dialog)
            
            layout.addWidget(QLabel("Select doctor code for saving edited segmentation:"))
            
            # Create list widget
            list_widget = QListWidget()
            for tag in available_tags:
                item = QListWidgetItem()
                
                # Create widget for each item
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                
                # Color indicator
                color_label = QLabel()
                color_label.setFixedSize(20, 20)
                color_label.setStyleSheet(f"background-color: {tag.get('color', '#000000')}; border: 1px solid #ccc;")
                
                # Code and name
                text_label = QLabel(f"{tag.get('code', 'N/A')} - {tag.get('name', 'Unknown')}")
                
                item_layout.addWidget(color_label)
                item_layout.addWidget(text_label)
                item_layout.addStretch()
                
                item.setSizeHint(item_widget.sizeHint())
                list_widget.addItem(item)
                list_widget.setItemWidget(item, item_widget)
                
                # Store the code in the item data
                item.setData(Qt.UserRole, tag.get('code'))
            
            # Select first item by default
            if list_widget.count() > 0:
                list_widget.setCurrentRow(0)
            
            layout.addWidget(list_widget)
            
            # Buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton("OK")
            cancel_button = QPushButton("Cancel")
            
            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)
            
            button_layout.addStretch()
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            # Show dialog
            if dialog.exec() == QDialog.Accepted:
                current_item = list_widget.currentItem()
                if current_item:
                    return current_item.data(Qt.UserRole)
            
            return None  # User cancelled
            
        except Exception as e:
            print(f"Error showing session selection dialog: {e}")
            return "NSY"  # Fallback to default

    def _update_progress(self, value: int, message: str):
        """Update progress bar and message (same as hotspot editor)."""
        print(f"Save progress: {value}% - {message}")
        
        # Update loading dialog if exists
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.set_progress(value)
            self.save_loading_dialog.set_message(f"Saving segmentation data...\n{message}")

    def _on_save_finished(self):
        """Handle save thread completion (same as hotspot editor)."""
        from PySide6.QtWidgets import QMessageBox
        
        print("🧪 [DEBUG SEGMENTATION] ===================")
        print("🧪 [DEBUG SEGMENTATION] Save finished!")
        print("🧪 [DEBUG SEGMENTATION] About to emit signal...")
        
        # Close loading dialog
        if hasattr(self, 'save_loading_dialog') and self.save_loading_dialog:
            self.save_loading_dialog.close()
            self.save_loading_dialog = None
        
        # Get save information
        if hasattr(self.save_thread, 'get_save_info'):
            save_info = self.save_thread.get_save_info()
            success_message = (
                f"Files saved successfully!\n\n"
                f"Location: {save_info['date_dir']}\n"
                f"Files:\n"
                f"• {save_info['mask_path'].name}\n"
                f"• {save_info['colored_path'].name}"
            )
        else:
            success_message = "Segmentation data saved successfully!"
        
        QMessageBox.information(self, "Save Complete", success_message)
        
        # Re-enable save button
        self.btn_save.setEnabled(True)
            
        # ✅ EMIT SIGNAL SEPERTI HOTSPOT EDITOR
        print("🧪 [DEBUG SEGMENTATION] Checking if signal exists...")
        if hasattr(self, 'editor_completed'):
            print("🧪 [DEBUG SEGMENTATION] Signal exists, emitting...")
            self.editor_completed.emit()
            print("🧪 [DEBUG SEGMENTATION] Signal emitted!")
        else:
            print("🧪 [DEBUG SEGMENTATION] ❌ Signal does not exist!")
        
        # Close dialog
        self.accept()
    
    def _create_timer_widget(self) -> QWidget:
        """Create compact timer widget."""
        timer_widget = QWidget()
        timer_layout = QVBoxLayout(timer_widget)
        timer_layout.setContentsMargins(0, 0, 0, 0)
        timer_layout.setSpacing(2)
        
        # Timer label
        timer_header = QLabel("⏱️ Editing Time")
        timer_header.setAlignment(Qt.AlignCenter)
        timer_header.setStyleSheet("""
            QLabel {
                font-size: 10px;
                font-weight: bold;
                color: #666;
                padding: 2px;
            }
        """)
        
        self.timer_display = QLabel("00:00:00")
        self.timer_display.setAlignment(Qt.AlignCenter)
        self.timer_display.setStyleSheet("""
            QLabel {
                font-family: 'Courier New', monospace;
                font-size: 14px;
                font-weight: bold;
                color: #2c5282;
                background: #f0f8ff;
                border: 1px solid #4a90e2;
                border-radius: 4px;
                padding: 4px;
                min-width: 70px;
            }
        """)
        
        timer_layout.addWidget(timer_header)
        timer_layout.addWidget(self.timer_display)
        
        return timer_widget

    def _setup_editing_timer(self):
        """Initialize editing timer."""
        from PySide6.QtCore import QTimer
        import time
        
        self.start_time = time.time()
        self.editing_start_time = datetime.now()
        
        # Create update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_timer_display)
        self.update_timer.start(1000)  # Update every second

    def _update_timer_display(self):
        """Update timer display."""
        import time
        
        elapsed = int(time.time() - self.start_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.timer_display.setText(time_str)

    # hotspot_editor_dialog.py -> _get_editing_duration()

    def _get_editing_duration(self) -> tuple[float, str]:
        """Get editing duration with millisecond precision."""
        import time
        
        elapsed_seconds_float = time.time() - self.start_time
        
        # Calculate components
        total_seconds_int = int(elapsed_seconds_float)
        hours = total_seconds_int // 3600
        minutes = (total_seconds_int % 3600) // 60
        seconds = total_seconds_int % 60
        milliseconds = int((elapsed_seconds_float - total_seconds_int) * 1000)
        
        # Format the string as HH:MM:SS:ms
        formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
        
        return elapsed_seconds_float, formatted_time

    # hotspot_editor_dialog.py -> _save_editing_time_log()

    def _save_editing_time_log(self, elapsed_seconds: float, formatted_time: str):
        """Save editing time to a CSV log file."""
        try:
            from pathlib import Path
            import csv
            from datetime import datetime

            # 1. Definisikan path dan buat direktori jika belum ada
            time_log_dir = Path(__file__).parent.parent.parent.parent / "data" / "PLANAR" / "timeEdit"
            time_log_dir.mkdir(parents=True, exist_ok=True)
            log_file = time_log_dir / "time_editing.csv"

            # 2. Tentukan kode dokter untuk log
            doctor_code = self.editor_session if self.session_code == "ALL" else self.session_code

            # 3. Siapkan data log
            log_entry = {
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'session': self.session_code,
                'kode_dokter': doctor_code,
                'patient_id': self.patient_id,
                'study_date': self.study_date,
                'view': self.view_short,
                'duration_seconds': f"{elapsed_seconds:.3f}",
                'duration_formatted': formatted_time,
                'edit_type' : 'segmentation'  # New field for edit type
            }
            
            fieldnames = list(log_entry.keys())

            # 4. Cek apakah file sudah ada untuk menentukan perlu header atau tidak
            file_exists = log_file.exists()

            # 5. Tambahkan (append) ke file CSV
            with open(log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow(log_entry)
            
            print(f"✅ Editing time logged to '{log_file.name}': {formatted_time} for patient {self.patient_id}")

        except Exception as e:
            print(f"❌ Failed to save editing time log: {e}")

    def closeEvent(self, event):
        """Handle dialog close to stop timer."""
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        super().closeEvent(event)
    