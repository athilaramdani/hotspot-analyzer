# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
import traceback
from typing import Dict, List, Optional
import cv2
import pydicom
import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow, QToolBar, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata
from backend.segment_editor import SegmentEditor
from backend.colorizer import _PALETTE, label_mask_to_rgb
from backend.input_data import _DATA_DIR

from .dicom_import_dialog import DicomImportDialog
from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

        # State variables
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, List[Dict]] = {}
        self.current_patient_id: Optional[str] = None
        self.current_scan_index: int = 0
        self.current_view: str = "Anterior"
        
        self._build_ui()
        self._scan_folder()

    def _build_ui(self) -> None:
        # Top actions layout
        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)

        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)

        top_actions = QWidget()
        top_layout = QHBoxLayout(top_actions)
        top_layout.setContentsMargins(10, 5, 10, 5)
        top_layout.setSpacing(10)

        top_layout.addWidget(self.patient_bar)
        
        # Buttons
        import_btn = QPushButton("Import DICOM…")
        import_btn.clicked.connect(self._show_import_dialog)
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.clicked.connect(self._scan_folder)
        edit_btn = QPushButton("Edit Segmentation")
        edit_btn.clicked.connect(self.launch_segment_editor)

        # Selectors
        self.mode_selector = ModeSelector()
        self.view_selector = ViewSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        self.view_selector.view_changed.connect(self._set_view)

        # Layout
        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)
        top_layout.addWidget(edit_btn)
        top_layout.addWidget(self.mode_selector)
        top_layout.addWidget(self.view_selector)
        
        # Zoom buttons
        zoom_layout = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(zoom_in_btn)
        zoom_layout.addWidget(zoom_out_btn)
        zoom_layout.addStretch()
        
        zoom_widget = QWidget()
        zoom_widget.setLayout(zoom_layout)

        # Main splitter
        main_splitter = QSplitter()
        self.left_image_panel = QWidget()
        self.left_image_panel.setMinimumWidth(600)
        self.left_image_layout = QVBoxLayout(self.left_image_panel)
        
        self.timeline_widget = ScanTimelineWidget()
        self.left_image_layout.addWidget(self.timeline_widget)
        main_splitter.addWidget(self.left_image_panel)
        
        self.side_panel = SidePanel()
        main_splitter.addWidget(self.side_panel)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        # Final assembly
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(10)
        main_layout.addWidget(top_actions)
        main_layout.addWidget(zoom_widget)
        main_layout.addWidget(main_splitter, stretch=1)
        
        self.setCentralWidget(main_widget)

    def launch_segment_editor(self):
        if not self.current_patient_id:
            QMessageBox.warning(self, "Warning", "Please select a patient first!")
            return

        patient_dir = _DATA_DIR / self.current_patient_id
        dicom_files = list(patient_dir.glob("*.dcm"))
        
        # Find the original DICOM (not the segmentation results)
        original_dicom = next((f for f in dicom_files if "_mask" not in f.stem and "_colored" not in f.stem), None)
        
        if not original_dicom:
            QMessageBox.warning(self, "Warning", "No DICOM file found for this patient!")
            return

        try:
            # Load the original image
            ds = pydicom.dcmread(original_dicom)
            img = ds.pixel_array
            
            # Handle multi-frame DICOM (select frame based on current view)
            if img.ndim == 3:
                if self.current_view == "Anterior":
                    img = img[0]  # First frame for Anterior
                else:
                    img = img[-1]  # Last frame for Posterior
            
            # Convert to uint8 if needed
            if img.dtype != np.uint8:
                img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

            # Try to load existing segmentation mask
            mask_path = patient_dir / f"{original_dicom.stem}_{self.current_view.lower()}_mask.dcm"
            colored_path = patient_dir / f"{original_dicom.stem}_{self.current_view.lower()}_colored.dcm"
            
            mask = None
            
            # Priority: try to load colored version first (has more class information)
            if colored_path.exists():
                try:
                    colored_ds = pydicom.dcmread(colored_path)
                    
                    # Fix: Set PlanarConfiguration if missing
                    if hasattr(colored_ds, 'SamplesPerPixel') and colored_ds.SamplesPerPixel == 3:
                        if not hasattr(colored_ds, 'PlanarConfiguration'):
                            colored_ds.PlanarConfiguration = 0
                    
                    colored_mask = colored_ds.pixel_array
                    
                    # Handle different formats
                    if colored_mask.ndim == 3:
                        # Check if it's channel-first (3, H, W) or channel-last (H, W, 3)
                        if colored_mask.shape[0] == 3 and colored_mask.shape[2] != 3:
                            # Channel first format - transpose to (H, W, 3)
                            colored_mask = np.transpose(colored_mask, (1, 2, 0))
                        elif colored_mask.shape[2] == 3:
                            # Already in correct format (H, W, 3)
                            pass
                        else:
                            # Unexpected format, try to handle
                            if colored_mask.shape[2] == 1:
                                colored_mask = colored_mask[:,:,0]
                            else:
                                colored_mask = colored_mask[:,:,0]
                        
                        mask = colored_mask
                    else:
                        # If somehow it's grayscale, treat as label mask
                        mask = colored_mask
                        
                    print(f"Loaded colored mask with shape: {mask.shape}")
                    
                except Exception as e:
                    print(f"Error loading colored mask: {e}")
                    mask = None
            
            # Fallback: try to load mask version
            if mask is None and mask_path.exists():
                try:
                    mask_ds = pydicom.dcmread(mask_path)
                    mask_data = mask_ds.pixel_array
                    
                    # Convert grayscale mask to proper format
                    if mask_data.ndim == 2:
                        mask = mask_data
                    elif mask_data.ndim == 3:
                        mask = mask_data[:,:,0] if mask_data.shape[2] == 1 else mask_data[:,:,0]
                    
                    # Ensure values are in correct range (0-12)
                    mask = mask.astype(np.uint8)
                    mask = np.clip(mask, 0, 12)
                    
                    print(f"Loaded grayscale mask with shape: {mask.shape}, unique values: {np.unique(mask)}")
                    
                except Exception as e:
                    print(f"Error loading mask: {e}")
                    mask = None
            
            # Try to load from PNG if DICOM failed
            if mask is None:
                png_mask_path = patient_dir / f"{original_dicom.stem}_{self.current_view.lower()}_mask.png"
                png_colored_path = patient_dir / f"{original_dicom.stem}_{self.current_view.lower()}_colored.png"
                
                if png_colored_path.exists():
                    try:
                        colored_png = cv2.imread(str(png_colored_path))
                        if colored_png is not None:
                            mask = cv2.cvtColor(colored_png, cv2.COLOR_BGR2RGB)
                            print(f"Loaded colored PNG with shape: {mask.shape}")
                    except Exception as e:
                        print(f"Error loading colored PNG: {e}")
                        
                elif png_mask_path.exists():
                    try:
                        mask_png = cv2.imread(str(png_mask_path), cv2.IMREAD_GRAYSCALE)
                        if mask_png is not None:
                            # Convert back from normalized values
                            mask = (mask_png * 12 / 255).astype(np.uint8)
                            mask = np.clip(mask, 0, 12)
                            print(f"Loaded grayscale PNG with shape: {mask.shape}")
                    except Exception as e:
                        print(f"Error loading mask PNG: {e}")
            
            # Create empty mask if none exists
            if mask is None:
                mask = np.zeros_like(img, dtype=np.uint8)
                QMessageBox.information(self, "Info", "No existing segmentation found. Creating new mask.")
            
            # Ensure mask and image have same dimensions
            if mask.shape[:2] != img.shape[:2]:
                if mask.ndim == 3:
                    mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
                else:
                    mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)
                print(f"Resized mask to match image dimensions: {mask.shape}")

            # Launch the segment editor
            self.editor = SegmentEditor(img, mask, _PALETTE)
            self.editor.saved.connect(lambda edited_mask: self._save_edited_segmentation(edited_mask, original_dicom))
            self.editor.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load DICOM: {str(e)}")
            print(f"Error loading DICOM: {traceback.format_exc()}")

    def _save_edited_segmentation(self, edited_mask: np.ndarray, original_dicom_path: Path):
        if not self.current_patient_id:
            return

        try:
            patient_dir = _DATA_DIR / self.current_patient_id
            base_name = original_dicom_path.stem
            
            # Ensure mask is 2D and has correct values
            if edited_mask.ndim == 3:
                edited_mask = edited_mask[:,:,0] if edited_mask.shape[2] == 1 else edited_mask[:,:,0]
            
            edited_mask = edited_mask.astype(np.uint8)
            edited_mask = np.clip(edited_mask, 0, 12)
            
            print(f"Saving mask with shape: {edited_mask.shape}, unique values: {np.unique(edited_mask)}")
            
            # Save mask as DICOM
            mask_path = patient_dir / f"{base_name}_{self.current_view.lower()}_mask.dcm"
            
            # Create new DICOM dataset for mask
            mask_ds = pydicom.Dataset()
            
            # Set required DICOM attributes
            mask_ds.Rows, mask_ds.Columns = edited_mask.shape
            mask_ds.PhotometricInterpretation = "MONOCHROME2"
            mask_ds.SamplesPerPixel = 1
            mask_ds.BitsAllocated = 8
            mask_ds.BitsStored = 8
            mask_ds.HighBit = 7
            mask_ds.PixelRepresentation = 0
            mask_ds.PixelData = edited_mask.tobytes()
            
            # Copy metadata from original
            original_ds = pydicom.dcmread(original_dicom_path)
            for tag in ['PatientID', 'PatientName', 'StudyDate', 'StudyTime', 'StudyInstanceUID']:
                if tag in original_ds:
                    setattr(mask_ds, tag, getattr(original_ds, tag))
            
            # Set additional attributes
            mask_ds.Modality = "OT"
            mask_ds.SeriesDescription = f"{self.current_view} Mask"
            mask_ds.SeriesNumber = 999
            mask_ds.InstanceNumber = 1
            
            # Set file meta information
            mask_ds.file_meta = pydicom.Dataset()
            mask_ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
            mask_ds.file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
            mask_ds.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
            mask_ds.file_meta.ImplementationClassUID = pydicom.uid.generate_uid()
            mask_ds.file_meta.ImplementationVersionName = "PYDICOM " + pydicom.__version__
            mask_ds.is_little_endian = True
            mask_ds.is_implicit_VR = False
            
            mask_ds.save_as(mask_path, write_like_original=False)
            print(f"Saved mask DICOM: {mask_path}")

            # Generate and save colored version
            colored_mask = label_mask_to_rgb(edited_mask)
            colored_path = patient_dir / f"{base_name}_{self.current_view.lower()}_colored.dcm"
            
            # Create new DICOM dataset for colored version
            colored_ds = pydicom.Dataset()
            colored_ds.Rows, colored_ds.Columns = colored_mask.shape[:2]
            colored_ds.PhotometricInterpretation = "RGB"
            colored_ds.SamplesPerPixel = 3
            colored_ds.PlanarConfiguration = 0  # Fix: Add missing PlanarConfiguration
            colored_ds.BitsAllocated = 8
            colored_ds.BitsStored = 8
            colored_ds.HighBit = 7
            colored_ds.PixelRepresentation = 0
            colored_ds.PixelData = colored_mask.tobytes()
            
            # Copy metadata from original
            for tag in ['PatientID', 'PatientName', 'StudyDate', 'StudyTime', 'StudyInstanceUID']:
                if tag in original_ds:
                    setattr(colored_ds, tag, getattr(original_ds, tag))
            
            # Set additional attributes
            colored_ds.Modality = "OT"
            colored_ds.SeriesDescription = f"{self.current_view} Colored"
            colored_ds.SeriesNumber = 999
            colored_ds.InstanceNumber = 2
            
            # Set file meta information
            colored_ds.file_meta = pydicom.Dataset()
            colored_ds.file_meta.TransferSyntaxUID = pydicom.uid.ExplicitVRLittleEndian
            colored_ds.file_meta.MediaStorageSOPClassUID = pydicom.uid.SecondaryCaptureImageStorage
            colored_ds.file_meta.MediaStorageSOPInstanceUID = pydicom.uid.generate_uid()
            colored_ds.file_meta.ImplementationClassUID = pydicom.uid.generate_uid()
            colored_ds.file_meta.ImplementationVersionName = "PYDICOM " + pydicom.__version__
            colored_ds.is_little_endian = True
            colored_ds.is_implicit_VR = False
            
            colored_ds.save_as(colored_path, write_like_original=False)
            print(f"Saved colored DICOM: {colored_path}")

            # Generate and save PNG versions for display
            self._save_png_versions(edited_mask, colored_mask, patient_dir, base_name)

            QMessageBox.information(self, "Success", "Segmentation saved successfully!")
            self._refresh_display()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save segmentation: {str(e)}")
            print(f"Error saving segmentation: {traceback.format_exc()}")

    def _save_png_versions(self, mask, colored_mask, patient_dir, base_name):
        """Save PNG versions of mask and colored mask for display purposes"""
        try:
            import cv2
            
            # Save mask as PNG
            mask_png_path = patient_dir / f"{base_name}_{self.current_view.lower()}_mask.png"
            
            # Normalize mask for better visualization (0-255 range)
            mask_normalized = (mask * 255 / 12).astype(np.uint8)
            cv2.imwrite(str(mask_png_path), mask_normalized)
            print(f"Saved mask PNG: {mask_png_path}")
            
            # Save colored mask as PNG
            colored_png_path = patient_dir / f"{base_name}_{self.current_view.lower()}_colored.png"
            
            # Convert RGB to BGR for OpenCV
            colored_bgr = cv2.cvtColor(colored_mask, cv2.COLOR_RGB2BGR)
            cv2.imwrite(str(colored_png_path), colored_bgr)
            print(f"Saved colored PNG: {colored_png_path}")
            
        except Exception as e:
            print(f"Error saving PNG versions: {e}")
            # Try alternative method using PIL/Pillow
            try:
                from PIL import Image
                
                # Save mask as PNG using PIL
                mask_png_path = patient_dir / f"{base_name}_{self.current_view.lower()}_mask.png"
                mask_normalized = (mask * 255 / 12).astype(np.uint8)
                Image.fromarray(mask_normalized).save(mask_png_path)
                
                # Save colored mask as PNG using PIL
                colored_png_path = patient_dir / f"{base_name}_{self.current_view.lower()}_colored.png"
                Image.fromarray(colored_mask).save(colored_png_path)
                
                print(f"Saved PNG files using PIL: {mask_png_path}, {colored_png_path}")
                
            except Exception as e2:
                print(f"Error saving PNG with PIL: {e2}")

    def _refresh_display(self):
        
        if self.current_patient_id:
            self._load_patient(self.current_patient_id)

    def _show_import_dialog(self) -> None:
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._scan_folder())
        dlg.exec()

    def _scan_folder(self) -> None:
        id_combo = self.patient_bar.id_combo
        id_combo.clear()

        self._patient_id_map = scan_dicom_directory(_DATA_DIR)
        id_combo.addItems([f"ID : {pid}" for pid in sorted(self._patient_id_map)])
        id_combo.clearSelection()

        self.patient_bar.clear_info(keep_id_list=True)
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.display_timeline([])

    def _on_patient_selected(self, txt: str) -> None:
        try:
            pid = txt.split(" : ")[1]
        except IndexError:
            return
        self.current_patient_id = pid
        self._load_patient(pid)

    def _load_patient(self, pid: str) -> None:
        scans = self._loaded.get(pid)
        if scans is None:
            scans = []
            for p in self._patient_id_map.get(pid, []):
                try:
                    frames, meta = load_frames_and_metadata(p)
                    scans.append({"meta": meta, "frames": frames, "path": p})
                except Exception as e:
                    print(f"[WARN] failed to read {p}: {e}")
            scans.sort(key=lambda s: s["meta"].get("study_date", ""))
            self._loaded[pid] = scans

        # update ui
        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self.timeline_widget.display_timeline(scans)

    def zoom_in(self):
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.zoom_in()

    def zoom_out(self):
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.zoom_out()

    def _set_view(self, v: str) -> None:
        self.current_view = v
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        if hasattr(self, 'timeline_widget'):
            self.timeline_widget.set_image_mode(m)