# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout, QDialog
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata
from backend.hotspot_processor import HotspotProcessor
from backend.image_converter import load_frames_and_metadata_matrix

# Import the new dialog
from .dicom_import_dialog_v2 import DicomImportDialog

from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector


class MainWindow(QMainWindow):

    def __init__(self, data_root: Path, parent=None, session_code: str | None = None):
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)
        self.session_code = session_code
        self.data_root = data_root
        print("[DEBUG] session_code in MainWindow =", self.session_code)

        # Caches
        self._patient_id_map: Dict[str, List[Path]] = {}
        self._loaded: Dict[str, List[Dict]] = {}
        self.scan_buttons: List[QPushButton] = []
        
        # Hotspot processor
        self.hotspot_processor = HotspotProcessor()

        self._build_ui()
        self._scan_folder()

    def _build_ui(self) -> None:
        # --- Top Bar ---
        top_actions = QWidget()
        top_layout = QHBoxLayout(top_actions)

        search_combo = SearchableComboBox()
        search_combo.item_selected.connect(self._on_patient_selected)
        self.patient_bar = PatientInfoBar()
        self.patient_bar.set_id_combobox(search_combo)
        top_layout.addWidget(self.patient_bar)
        top_layout.addStretch()

        # Updated Import button dengan styling yang lebih baik
        import_btn = QPushButton("Import DICOM…")
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #4e73ff;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #3e63e6;
            }
            QPushButton:pressed {
                background-color: #324fc7;
            }
        """)
        import_btn.clicked.connect(self._show_import_dialog)
        
        rescan_btn = QPushButton("Rescan Folder")
        rescan_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        rescan_btn.clicked.connect(self._scan_folder)
        
        self.mode_selector = ModeSelector()
        self.view_selector = ViewSelector()
        self.mode_selector.mode_changed.connect(self._set_mode)
        self.view_selector.view_changed.connect(self._set_view)

        top_layout.addWidget(import_btn)
        top_layout.addWidget(rescan_btn)
        top_layout.addWidget(self.mode_selector)
        top_layout.addWidget(self.view_selector)

        # --- Scan & Zoom Buttons ---
        view_button_widget = QWidget()
        view_button_layout = QHBoxLayout(view_button_widget)
        self.scan_button_container = QHBoxLayout()
        view_button_layout.addLayout(self.scan_button_container)
        view_button_layout.addStretch()
        
        zoom_in_btn = QPushButton("Zoom In")
        zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_out_btn = QPushButton("Zoom Out")
        zoom_out_btn.clicked.connect(self.zoom_out)
        
        # Styling untuk zoom buttons
        zoom_style = """
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """
        zoom_in_btn.setStyleSheet(zoom_style)
        zoom_out_btn.setStyleSheet(zoom_style)
        
        view_button_layout.addWidget(zoom_in_btn)
        view_button_layout.addWidget(zoom_out_btn)

        # --- Splitter (UI Utama) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel Kiri: Timeline untuk menampilkan gambar
        self.timeline_widget = ScanTimelineWidget()
        self.timeline_widget.set_session_code(self.session_code)
        main_splitter.addWidget(self.timeline_widget)

        # Panel Kanan: Grafik dan ringkasan
        self.side_panel = SidePanel()
        main_splitter.addWidget(self.side_panel)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)

        # --- Perakitan Final ---
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(top_actions)
        main_layout.addWidget(view_button_widget)
        main_layout.addWidget(main_splitter, stretch=1)
        self.setCentralWidget(main_widget)

    def _show_import_dialog(self) -> None:
        """Show the updated import dialog"""
        print("[DEBUG] Opening DICOM import dialog...")
        
        dlg = DicomImportDialog(
            data_root=self.data_root, 
            parent=self, 
            session_code=self.session_code
        )
        
        # Connect signal untuk auto-rescan setelah import
        dlg.files_imported.connect(self._on_files_imported)
        
        # Show dialog
        result = dlg.exec()
        
        if result == QDialog.Accepted:
            print("[DEBUG] Import dialog accepted")
        else:
            print("[DEBUG] Import dialog cancelled")

    def _on_files_imported(self):
        """Handle files imported signal"""
        print("[DEBUG] Files imported signal received, rescanning folder...")
        self._scan_folder()

    def _scan_folder(self) -> None:
        """Scan folder untuk mencari DICOM files"""
        print("[DEBUG] Starting folder scan...")
        
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        
        # 1. Pindai semua direktori seperti biasa
        all_patients_map = scan_dicom_directory(self.data_root)
        print(f"[DEBUG] Semua patient ID dari scanner:")
        for pid in all_patients_map.keys():
            print(f"  - {pid}")
            
        # 2. Saring (filter) hasilnya untuk hanya menyertakan yang berakhiran '_kode'
        filter_suffix = f"_{self.session_code}"
        self._patient_id_map = {
            pid: path
            for pid, path in all_patients_map.items()
            if pid.endswith(filter_suffix)
        }
        print(f"[DEBUG] ID pasien dengan suffix {filter_suffix}: {list(self._patient_id_map.keys())}")

        # Tampilkan hasil saringan (tanpa akhiran _kode)
        id_combo.addItems([
            f"ID : {pid.removesuffix(filter_suffix)} ({self.session_code})"
            for pid in sorted(self._patient_id_map)
        ])
        print(f"[DEBUG] Added {id_combo.count()} patient IDs to combo box")

        # Clear selections dan reset UI
        id_combo.clearSelection()
        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([])
        
        print("[DEBUG] Folder scan completed")

    def _on_patient_selected(self, txt: str) -> None:
        """Handle patient selection"""
        print(f"[DEBUG] _on_patient_selected: {txt}")
        try:
            # Ambil hanya bagian ID tanpa (session_code)
            pid = txt.split(" : ")[1].split(" ")[0]
        except IndexError:
            print("[DEBUG] Failed to parse patient ID from selection")
            return
        self._load_patient(pid)

    def _load_patient(self, pid: str) -> None:
        """Load patient data"""
        print(f"[DEBUG] Loading patient: {pid}")
        
        full_pid = f"{pid}_{self.session_code}"
        scans = self._loaded.get(full_pid)
        
        if scans is None:
            print(f"[DEBUG] Loading scans for {full_pid} from disk...")
            scans = []
            for p in self._patient_id_map.get(full_pid, []):
                try:
                    frames, meta = load_frames_and_metadata(p)
                    print(frames)
                    print()
                    scan_data = {"meta": meta, "frames": frames, "path": p}
                    
                    frame_bb, meta = load_frames_and_metadata_matrix(p)
                    # Add hotspot processing capability
                    hotspot_data = self._process_hotspot_frames_dual_view(frame_bb, p, pid)
                    scan_data["hotspot_frames"] = hotspot_data["frames"]
                    scan_data["hotspot_frames_ant"] = hotspot_data["ant_frames"]
                    scan_data["hotspot_frames_post"] = hotspot_data["post_frames"]

                    #Versi Lama - 1 
                    # scan_data["hotspot_frames"] = self._process_hotspot_frames(frame_bb, p)

                    
                    scans.append(scan_data)
                except Exception as e:
                    print(f"[WARN] failed to read {p}: {e}")
                    
            scans.sort(key=lambda s: s["meta"].get("study_date", ""))
            self._loaded[full_pid] = scans  # Simpan di cache

        print(f"[DEBUG] Total scan ditemukan untuk {full_pid}: {len(scans)}")
        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self._populate_scan_buttons(scans)

        # Set initial scan selection
        if scans:
            self._on_scan_button_clicked(0)
    
    # def _process_hotspot_frames_dual_view(self, frames: List, scan_path: Path, patient_id: str) -> Dict:
    #     """
    #     Process each frame with hotspot detection using XML annotations for both anterior and posterior views.

    #     Args:
    #         frames: List of image frames (expected as np.ndarray).
    #         scan_path: Path to the scan file (e.g., data/2/2.dcm).
    #         patient_id: Patient ID for XML file lookup.

    #     Returns:
    #         Dictionary containing:
    #         - frames: Combined processed frames (fallback to original if no XML)
    #         - ant_frames: Anterior view processed frames
    #         - post_frames: Posterior view processed frames
    #     """
    #     import numpy as np
    #     from PIL import Image
    #     from pathlib import Path

    #     # Initialize result structure
    #     result = {
    #         "frames": [],
    #         "ant_frames": [],
    #         "post_frames": []
    #     }

    #     # --- Determine XML paths for both views ---
    #     ant_xml_path = Path(f"data/{patient_id}/{patient_id}_ant.xml")
    #     post_xml_path = Path(f"data/{patient_id}/{patient_id}_post.xml")
        
    #     print(f"[INFO] Anterior XML path: {ant_xml_path}")
    #     print(f"[INFO] Posterior XML path: {post_xml_path}")

    #     # Check which XML files exist
    #     ant_xml_exists = ant_xml_path.exists()
    #     post_xml_exists = post_xml_path.exists()
        
    #     if not ant_xml_exists and not post_xml_exists:
    #         print(f"[WARN] No XML files found for patient {patient_id}")
    #         # Return original frames for all views
    #         result["frames"] = frames
    #         result["ant_frames"] = frames
    #         result["post_frames"] = frames
    #         return result

    #     # --- Process each frame for both views ---
    #     for i, frame in enumerate(frames):
    #         try:
    #             # Verify frame is a valid numpy image
    #             if not isinstance(frame, np.ndarray) or frame.ndim != 2:
    #                 print(f"[WARN] Skipping frame {i}, unsupported type or dimension: {type(frame)}, shape={getattr(frame, 'shape', 'N/A')}")
    #                 result["frames"].append(frame)
    #                 result["ant_frames"].append(frame)
    #                 result["post_frames"].append(frame)
    #                 continue

    #             # Save the frame as a temporary grayscale PNG
    #             temp_image_path = self.hotspot_processor.temp_dir / f"temp_frame_{i}.png"
    #             frame_normalized = ((frame - frame.min()) / max(1e-5, frame.ptp()) * 255).astype(np.uint8)
    #             Image.fromarray(frame_normalized).save(temp_image_path)
    #             print(f"[INFO] Temp image saved: {temp_image_path}")

    #             # Process anterior view
    #             ant_processed = None
    #             if ant_xml_exists:
    #                 ant_processed = self.hotspot_processor.process_image_with_xml(
    #                     str(temp_image_path), str(ant_xml_path), patient_id, "ant"
    #                 )
    #                 if ant_processed is not None:
    #                     print(f"[INFO] Anterior hotspot processed for frame {i}")
    #                 else:
    #                     print(f"[WARN] Failed to process anterior hotspot for frame {i}")

    #             # Process posterior view
    #             post_processed = None
    #             if post_xml_exists:
    #                 post_processed = self.hotspot_processor.process_image_with_xml(
    #                     str(temp_image_path), str(post_xml_path), patient_id, "post"
    #                 )
    #                 if post_processed is not None:
    #                     print(f"[INFO] Posterior hotspot processed for frame {i}")
    #                 else:
    #                     print(f"[WARN] Failed to process posterior hotspot for frame {i}")

    #             # Store results
    #             result["ant_frames"].append(ant_processed if ant_processed is not None else frame)
    #             result["post_frames"].append(post_processed if post_processed is not None else frame)
                
    #             # For the main frames, prefer the view that matches the scan filename, or use anterior as default
    #             filename_lower = scan_path.stem.lower()
    #             if "post" in filename_lower and post_processed is not None:
    #                 result["frames"].append(post_processed)
    #             elif "ant" in filename_lower and ant_processed is not None:
    #                 result["frames"].append(ant_processed)
    #             elif ant_processed is not None:
    #                 result["frames"].append(ant_processed)
    #             elif post_processed is not None:
    #                 result["frames"].append(post_processed)
    #             else:
    #                 result["frames"].append(frame)

    #             # Optionally remove the temp image
    #             if temp_image_path.exists():
    #                 temp_image_path.unlink()

    #         except Exception as e:
    #             print(f"[ERROR] Exception while processing frame {i}: {e}")
    #             result["frames"].append(frame)
    #             result["ant_frames"].append(frame)
    #             result["post_frames"].append(frame)

    #     return result
    def _process_hotspot_frames_dual_view(self, frames: List, scan_path: Path, patient_id: str) -> Dict:
        """
        Process each frame with hotspot detection using XML annotations for both anterior and posterior views.
        First checks for existing hotspot masks, then falls back to XML processing if masks don't exist.

        Args:
            frames: List of image frames (expected as np.ndarray).
            scan_path: Path to the scan file (e.g., data/2/2.dcm).
            patient_id: Patient ID for XML file lookup.

        Returns:
            Dictionary containing:
            - frames: Combined processed frames (fallback to original if no XML)
            - ant_frames: Anterior view processed frames
            - post_frames: Posterior view processed frames
        """
        import numpy as np
        from PIL import Image
        from pathlib import Path

        # Initialize result structure
        result = {
            "frames": [],
            "ant_frames": [],
            "post_frames": []
        }

        # --- Check for existing hotspot masks ---
        ant_mask_path = Path(f"data/{patient_id}/{patient_id}_ant_hotspot_colored.png")
        post_mask_path = Path(f"data/{patient_id}/{patient_id}_post_hotspot_colored.png")
        
        print(f"[INFO] Checking for existing masks:")
        print(f"[INFO] Anterior mask path: {ant_mask_path}")
        print(f"[INFO] Posterior mask path: {post_mask_path}")

        ant_mask_exists = ant_mask_path.exists()
        post_mask_exists = post_mask_path.exists()
        
        # Load masks if they exist
        ant_mask = None
        post_mask = None
        
        if ant_mask_exists:
            try:
                ant_mask = np.array(Image.open(ant_mask_path).convert('L'))
                print(f"[INFO] Loaded anterior hotspot mask: {ant_mask.shape}")
            except Exception as e:
                print(f"[WARN] Failed to load anterior mask: {e}")
                ant_mask_exists = False
        
        if post_mask_exists:
            try:
                post_mask = np.array(Image.open(post_mask_path).convert('L'))
                print(f"[INFO] Loaded posterior hotspot mask: {post_mask.shape}")
            except Exception as e:
                print(f"[WARN] Failed to load posterior mask: {e}")
                post_mask_exists = False

        # --- Fallback to XML paths if masks don't exist ---
        ant_xml_path = Path(f"data/{patient_id}/{patient_id}_ant.xml")
        post_xml_path = Path(f"data/{patient_id}/{patient_id}_post.xml")
        
        ant_xml_exists = ant_xml_path.exists() and not ant_mask_exists
        post_xml_exists = post_xml_path.exists() and not post_mask_exists
        
        if not ant_mask_exists and not ant_xml_exists and not post_mask_exists and not post_xml_exists:
            print(f"[WARN] No hotspot masks or XML files found for patient {patient_id}")
            # Return original frames for all views
            result["frames"] = frames
            result["ant_frames"] = frames
            result["post_frames"] = frames
            return result

        # --- Helper function to apply mask to frame ---
        def apply_mask_to_frame(frame, mask):
            """Apply a grayscale mask to a frame."""
            if mask is None:
                return frame
            
            # Ensure frame and mask have compatible dimensions
            if frame.shape != mask.shape:
                # Resize mask to match frame if needed
                mask_resized = np.array(Image.fromarray(mask).resize(
                    (frame.shape[1], frame.shape[0]), Image.NEAREST
                ))
            else:
                mask_resized = mask
            
            # Normalize mask to 0-1 range
            mask_normalized = mask_resized.astype(np.float32) / 255.0
            
            # Apply mask (multiply frame by mask)
            # Areas with mask value 255 (white) will be preserved
            # Areas with mask value 0 (black) will be suppressed
            masked_frame = frame.astype(np.float32) * mask_normalized
            
            return masked_frame.astype(frame.dtype)

        # --- Process each frame for both views ---
        for i, frame in enumerate(frames):
            try:
                # Verify frame is a valid numpy image
                if not isinstance(frame, np.ndarray) or frame.ndim != 2:
                    print(f"[WARN] Skipping frame {i}, unsupported type or dimension: {type(frame)}, shape={getattr(frame, 'shape', 'N/A')}")
                    result["frames"].append(frame)
                    result["ant_frames"].append(frame)
                    result["post_frames"].append(frame)
                    continue

                # --- Process anterior view ---
                ant_processed = None
                if ant_mask_exists:
                    # Apply existing anterior mask
                    ant_processed = apply_mask_to_frame(frame, ant_mask)
                    print(f"[INFO] Applied anterior hotspot mask to frame {i}")
                elif ant_xml_exists:
                    # Process with XML (existing logic)
                    temp_image_path = self.hotspot_processor.temp_dir / f"temp_frame_{i}.png"
                    frame_normalized = ((frame - frame.min()) / max(1e-5, frame.ptp()) * 255).astype(np.uint8)
                    Image.fromarray(frame_normalized).save(temp_image_path)
                    
                    ant_processed = self.hotspot_processor.process_image_with_xml(
                        str(temp_image_path), str(ant_xml_path), patient_id, "ant"
                    )
                    
                    if ant_processed is not None:
                        print(f"[INFO] Anterior hotspot processed with XML for frame {i}")
                    else:
                        print(f"[WARN] Failed to process anterior hotspot with XML for frame {i}")
                    
                    # Clean up temp file
                    if temp_image_path.exists():
                        temp_image_path.unlink()

                # --- Process posterior view ---
                post_processed = None
                if post_mask_exists:
                    # Apply existing posterior mask
                    post_processed = apply_mask_to_frame(frame, post_mask)
                    print(f"[INFO] Applied posterior hotspot mask to frame {i}")
                elif post_xml_exists:
                    # Process with XML (existing logic)
                    temp_image_path = self.hotspot_processor.temp_dir / f"temp_frame_{i}.png"
                    frame_normalized = ((frame - frame.min()) / max(1e-5, frame.ptp()) * 255).astype(np.uint8)
                    Image.fromarray(frame_normalized).save(temp_image_path)
                    
                    post_processed = self.hotspot_processor.process_image_with_xml(
                        str(temp_image_path), str(post_xml_path), patient_id, "post"
                    )
                    
                    if post_processed is not None:
                        print(f"[INFO] Posterior hotspot processed with XML for frame {i}")
                    else:
                        print(f"[WARN] Failed to process posterior hotspot with XML for frame {i}")
                    
                    # Clean up temp file
                    if temp_image_path.exists():
                        temp_image_path.unlink()

                # --- Store results ---
                result["ant_frames"].append(ant_processed if ant_processed is not None else frame)
                result["post_frames"].append(post_processed if post_processed is not None else frame)
                
                # For the main frames, prefer the view that matches the scan filename, or use anterior as default
                filename_lower = scan_path.stem.lower()
                if "post" in filename_lower and post_processed is not None:
                    result["frames"].append(post_processed)
                elif "ant" in filename_lower and ant_processed is not None:
                    result["frames"].append(ant_processed)
                elif ant_processed is not None:
                    result["frames"].append(ant_processed)
                elif post_processed is not None:
                    result["frames"].append(post_processed)
                else:
                    result["frames"].append(frame)

            except Exception as e:
                print(f"[ERROR] Exception while processing frame {i}: {e}")
                result["frames"].append(frame)
                result["ant_frames"].append(frame)
                result["post_frames"].append(frame)

        return result


    def _populate_scan_buttons(self, scans: List[Dict]) -> None:
        """Populate scan buttons"""
        # Clear existing buttons
        for btn in self.scan_buttons:
            btn.deleteLater()
        self.scan_buttons.clear()

        # Create new buttons
        for i, scan in enumerate(scans):
            btn = QPushButton(f"Scan {i + 1}")
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #9C27B0;
                    color: white;
                    border: none;
                    padding: 6px 12px;
                    border-radius: 3px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #7B1FA2;
                }
                QPushButton:checked {
                    background-color: #4A148C;
                }
                QPushButton:pressed {
                    background-color: #4A148C;
                }
            """)
            btn.clicked.connect(partial(self._on_scan_button_clicked, i))
            self.scan_button_container.addWidget(btn)
            self.scan_buttons.append(btn)

    def _on_scan_button_clicked(self, index: int) -> None:
        """Fungsi ini sekarang menjadi pusat logika yang benar."""
        current_mode = self.mode_selector.current_mode()
        self.timeline_widget.set_image_mode(current_mode) 
        
        # 1. Update tampilan tombol
        for i, btn in enumerate(self.scan_buttons):
            btn.setChecked(i == index)

        # Get current patient data
        try:
            id_text = self.patient_bar.id_combo.currentText()
            pid = id_text.split(" : ")[1].split(" ")[0]
        except (IndexError, AttributeError):
            print("[DEBUG] Failed to get current patient ID")
            return

        # Load scan data
        full_pid = f"{pid}_{self.session_code}"
        scans = self._loaded.get(full_pid, []) 

        if not scans or index >= len(scans):
            print(f"[DEBUG] Invalid scan index {index} for patient {full_pid}")
            return
        
        selected_scan = scans[index]

        # Update timeline display
        self.timeline_widget.display_timeline(scans, active_index=index)

        # Update side panel
        self.side_panel.set_chart_data(scans)
        self.side_panel.set_summary(selected_scan["meta"])
        
        print(f"[DEBUG] Menampilkan {len(scans)} scan di timeline")

    # --- Zoom and view callbacks ---
    def zoom_in(self):
        """Zoom in timeline"""
        self.timeline_widget.zoom_in()

    def zoom_out(self):
        """Zoom out timeline"""
        self.timeline_widget.zoom_out()

    def _set_view(self, v: str) -> None:
        """Set active view"""
        self.timeline_widget.set_active_view(v)

    def _set_mode(self, m: str) -> None:
        """Handle mode changes including hotspot mode."""
        self.timeline_widget.set_image_mode(m)
        
        # If switching to hotspot mode, refresh the current scan
        if m == "Hotspot":
            # Get currently selected scan and refresh it
            for i, btn in enumerate(self.scan_buttons):
                if btn.isChecked():
                    self._on_scan_button_clicked(i)
                    break