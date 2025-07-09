# frontend/widgets/main_window.py
from __future__ import annotations

from pathlib import Path
from functools import partial
from typing import Dict, List
import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QPushButton,
    QWidget, QVBoxLayout, QHBoxLayout
)

from backend.directory_scanner import scan_dicom_directory
from backend.dicom_loader import load_frames_and_metadata
from backend.hotspot_processor import HotspotProcessor
from backend.image_converter import load_frames_and_metadata_matrix

from .dicom_import_dialog import DicomImportDialog
from .searchable_combobox import SearchableComboBox
from .patient_info import PatientInfoBar
from .scan_timeline import ScanTimelineWidget  # Menggunakan timeline widget lagi
from .side_panel import SidePanel
from .mode_selector import ModeSelector
from .view_selector import ViewSelector

class MainWindow(QMainWindow):

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Hotspot Analyzer")
        self.resize(1600, 900)

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

        import_btn = QPushButton("Import DICOM…")
        import_btn.clicked.connect(self._show_import_dialog)
        rescan_btn = QPushButton("Rescan Folder")
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
        view_button_layout.addWidget(zoom_in_btn)
        view_button_layout.addWidget(zoom_out_btn)

        # --- Splitter (UI Utama) ---
        main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Panel Kiri: Timeline untuk menampilkan gambar
        self.timeline_widget = ScanTimelineWidget()
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
        dlg = DicomImportDialog(Path("data"), self)
        dlg.files_imported.connect(lambda _: self._scan_folder())
        dlg.exec()

    def _scan_folder(self) -> None:
        id_combo = self.patient_bar.id_combo
        id_combo.clear()
        self._patient_id_map = scan_dicom_directory(Path("data"))
        id_combo.addItems([f"ID : {pid}" for pid in sorted(self._patient_id_map)])
        id_combo.clearSelection()
        self.patient_bar.clear_info(keep_id_list=True)
        self.timeline_widget.display_timeline([]) # Kosongkan timeline

    def _on_patient_selected(self, txt: str) -> None:
        try:
            pid = txt.split(" : ")[1]
        except IndexError:
            return
        self._load_patient(pid)

    def _load_patient(self, pid: str) -> None:
        scans = self._loaded.get(pid)
        if scans is None:
            scans = []
            for p in self._patient_id_map.get(pid, []):
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
            self._loaded[pid] = scans

        self.patient_bar.set_patient_meta(scans[-1]["meta"] if scans else {})
        self._populate_scan_buttons(scans)

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
        for btn in self.scan_buttons:
            btn.deleteLater()
        self.scan_buttons.clear()

        for i, scan in enumerate(scans):
            btn = QPushButton(f"Scan {i + 1}")
            btn.setCheckable(True)
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

        # 2. Ambil data scan untuk pasien saat ini (CARA YANG BENAR)
        try:
            # Ambil teks dari ComboBox, contoh: "ID : 0001443575"
            id_text = self.patient_bar.id_combo.currentText()
            # Pisahkan teks untuk mendapatkan ID saja
            pid = id_text.split(" : ")[1]
        except (IndexError, AttributeError):
            # Jika gagal (tidak ada pasien terpilih), hentikan fungsi
            return

        scans = self._loaded.get(pid, [])
        if not scans or index >= len(scans):
            return
        
        selected_scan = scans[index]

        # 3. Perintahkan timeline di KIRI untuk menampilkan HANYA scan yang dipilih
        self.timeline_widget.display_timeline(scans, active_index=index)

        # 4. Perintahkan panel di KANAN untuk update grafik dan ringkasan
        self.side_panel.set_chart_data(scans)
        self.side_panel.set_summary(selected_scan["meta"])

    # --- Callbacks untuk zoom, view, dan mode ---
    def zoom_in(self):
        self.timeline_widget.zoom_in()

    def zoom_out(self):
        self.timeline_widget.zoom_out()

    def _set_view(self, v: str) -> None:
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