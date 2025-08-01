# process_wrapper.py
"""
Processing wrapper for SPECT viewer with DICOM integration
Handles YOLO detection and hotspot processing
"""

import sys
import traceback
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image
from .segmenter import predict_bone_mask
from PIL import Image
# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

# Import configurations and utilities
from core.config.paths import (
    YOLO_MODEL_PATH, 
    get_hotspot_files, 
    extract_study_date_from_dicom, 
    generate_filename_stem,
    get_patient_spect_path
)

# Import DICOM loader
from features.dicom_import.logic.dicom_loader import (
    load_frames_and_metadata,
    extract_patient_info_from_path
)

# Import box detection
from .box_detection import run_yolo_detection_for_patient

# Import hotspot processor with fallback
try:
    from .hotspot_processor import HotspotProcessor
except ImportError as e:
    print(f"Warning: Could not import HotspotProcessor: {e}")
    
    class HotspotProcessor:
        """Fallback HotspotProcessor for when the real one isn't available"""
        def process_frame_with_xml(self, frame, xml_path, patient_id, view,study_date=None):
            print(f"[FALLBACK] HotspotProcessor not available, returning original frame")
            return frame
        
        def cleanup(self):
            pass


def run_yolo_detection_wrapper(scan_path: Path, patient_id: str) -> Dict[str, bool]:
    """
    Wrapper function to run YOLO detection for a patient scan
    
    Args:
        scan_path: Path to DICOM file
        patient_id: Patient ID
        
    Returns:
        Dictionary indicating success for each view
    """
    try:
        print(f"[YOLO WRAPPER] Starting YOLO detection for {patient_id}")
        print(f"[YOLO WRAPPER] Model path: {YOLO_MODEL_PATH}")
        print(f"[YOLO WRAPPER] DICOM path: {scan_path}")
        
        if not YOLO_MODEL_PATH.exists():
            print(f"[YOLO ERROR] Model file not found: {YOLO_MODEL_PATH}")
            return {"anterior": False, "posterior": False}
        
        if not scan_path.exists():
            print(f"[YOLO ERROR] DICOM file not found: {scan_path}")
            return {"anterior": False, "posterior": False}
        
        # Run detection
        results = run_yolo_detection_for_patient(scan_path, patient_id)
        
        print(f"[YOLO WRAPPER] Detection completed with results: {results}")
        return results
        
    except Exception as e:
        print(f"[YOLO WRAPPER ERROR] Exception in YOLO detection: {e}")
        traceback.print_exc()
        return {"anterior": False, "posterior": False}


# GANTIKAN FUNGSI LAMA ANDA DENGAN YANG INI SECARA KESELURUHAN

# Di dalam file features/spect_viewer/logic/processing_wrapper.py

# Pastikan import ini ada di bagian atas file
from PIL import Image
# ... import lainnya ...

# UPDATE run_hotspot_processing_in_process function in processing_wrapper.py

def run_hotspot_processing_in_process(scan_path: Path, patient_id: str) -> Dict:
    """
    Menjalankan proses hotspot dan MENYIMPAN hasilnya ke file gambar.
    FIXED: Proper study date extraction and passing
    """
    print("--- MENJALANKAN FUNGSI HOTSPOT DENGAN LOGIKA PENYIMPANAN FILE ---")
    try:
        from .hotspot_processor import HotspotProcessor
        from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, extract_study_date_from_dicom
        from core.config.paths import get_hotspot_files, generate_filename_stem

        processor = HotspotProcessor()
        frames, meta = load_frames_and_metadata(str(scan_path))

        if not frames:
            return {"frames": [], "ant_frames": [], "post_frames": []}

        # ✅ FIX: Extract study date from DICOM path properly
        try:
            study_date = extract_study_date_from_dicom(scan_path)
            session_code = scan_path.parent.parent.name
            filename_stem = generate_filename_stem(patient_id, study_date)
            print(f"[DEBUG] Extracted study_date: {study_date}, session: {session_code}")
        except Exception as e:
            print(f"[WARN] Could not extract study date from DICOM: {e}")
            # ✅ FIX: Use study_date from meta if available
            study_date = meta.get("study_date")
            if not study_date:
                from datetime import datetime
                study_date = datetime.now().strftime("%Y%m%d")
            session_code = "unknown"
            filename_stem = f"{patient_id}_{study_date}"
            print(f"[DEBUG] Using fallback study_date: {study_date}")
        
        ant_hotspot_files = get_hotspot_files(patient_id, session_code, "ant", study_date)
        post_hotspot_files = get_hotspot_files(patient_id, session_code, "post", study_date)
        ant_xml_path = Path(ant_hotspot_files['xml_file'])
        post_xml_path = Path(post_hotspot_files['xml_file'])

        result = {"frames": [], "ant_frames": [], "post_frames": []}

        for view_name, frame in frames.items():
            if not isinstance(frame, np.ndarray):
                continue
            
            processing_frame = np.sum(frame, axis=0) if frame.ndim == 3 else frame

            # Proses Anterior
            if ant_xml_path.exists() and "ant" in view_name.lower():
                print(f"[DEBUG] Processing anterior with XML: {ant_xml_path}")
                ant_processed = processor.process_frame_with_xml(
                    processing_frame, str(ant_xml_path), patient_id, "ant", study_date=study_date  # ✅ Pass study_date
                )
                if ant_processed is not None:
                    print(f"[PROCESS] Anterior hotspot processing completed (both versions saved)")
                    result["ant_frames"].append(ant_processed)
                else:
                    print(f"[PROCESS] Anterior processing failed, using original frame")
                    result["ant_frames"].append(processing_frame)
            elif "ant" in view_name.lower():
                result["ant_frames"].append(processing_frame)

            # Proses Posterior
            if post_xml_path.exists() and "post" in view_name.lower():
                print(f"[DEBUG] Processing posterior with XML: {post_xml_path}")
                post_processed = processor.process_frame_with_xml(
                    processing_frame, str(post_xml_path), patient_id, "post", study_date=study_date  # ✅ Pass study_date
                )
                if post_processed is not None:
                    print(f"[PROCESS] Posterior hotspot processing completed (both versions saved)")
                    result["post_frames"].append(post_processed)
                else:
                    print(f"[PROCESS] Posterior processing failed, using original frame")
                    result["post_frames"].append(processing_frame)
            elif "post" in view_name.lower():
                result["post_frames"].append(processing_frame)
        
        result["frames"] = result["ant_frames"] + result["post_frames"]

        print(f"[PROCESS] Hotspot processing and file saving completed for {scan_path.name}")
        print(f"[PROCESS] Expected files:")
        print(f"  - Blended: {filename_stem}_ant_hotspot_colored.png")
        print(f"  - Pure: {filename_stem}_anterior_hotspot_colored.png")
        print(f"  - Blended: {filename_stem}_post_hotspot_colored.png")
        print(f"  - Pure: {filename_stem}_posterior_hotspot_colored.png")
        
        return result

    except Exception as e:
        import traceback
        print(f"[PROCESS FATAL ERROR] Exception in hotspot processing: {e}")
        traceback.print_exc()
        return {"frames": [], "ant_frames": [], "post_frames": []}

def validate_processing_environment() -> bool:
    """
    Validate that the processing environment is properly set up
    
    Returns:
        True if environment is valid, False otherwise
    """
    try:
        print("[VALIDATION] Checking processing environment...")
        
        # Check YOLO model
        if not YOLO_MODEL_PATH.exists():
            print(f"[VALIDATION ERROR] YOLO model not found: {YOLO_MODEL_PATH}")
            return False
        
        print(f"[VALIDATION] YOLO model found: {YOLO_MODEL_PATH}")
        
        # Try to import required modules
        try:
            from ultralytics import YOLO
            print("[VALIDATION] YOLO import successful")
        except ImportError as e:
            print(f"[VALIDATION ERROR] Cannot import YOLO: {e}")
            return False
        
        try:
            from features.dicom_import.logic.dicom_loader import load_frames_and_metadata
            print("[VALIDATION] DICOM loader import successful")
        except ImportError as e:
            print(f"[VALIDATION ERROR] Cannot import DICOM loader: {e}")
            return False
        
        print("[VALIDATION] Processing environment is valid")
        return True
        
    except Exception as e:
        print(f"[VALIDATION ERROR] Environment validation failed: {e}")
        return False


# Test function
if __name__ == "__main__":
    if len(sys.argv) > 2:
        dicom_path = Path(sys.argv[1])
        patient_id = sys.argv[2]
        
        if not validate_processing_environment():
            print("Environment validation failed")
            sys.exit(1)
        
        if dicom_path.exists():
            print(f"Testing processing for: {dicom_path}")
            results = run_hotspot_processing_in_process(dicom_path, patient_id)
            print(f"Processing completed. Results: {len(results.get('frames', []))} frames")
        else:
            print(f"DICOM file not found: {dicom_path}")
    else:
        print("Usage: python process_wrapper.py <dicom_path> <patient_id>")
        print("Running environment validation...")
        validate_processing_environment()

def run_segmentation_in_process(dicom_path: Path, patient_id: str) -> Dict[str, str]:
    """
    Menjalankan proses segmentasi tulang dalam proses terpisah.
    Menyimpan hasilnya sebagai file PNG.
    """
    try:
        print(f"[SEGMENTER-PROC] Starting segmentation for {dicom_path.name}")

        # 1. Load frame original dari DICOM (misal, hanya view Anterior)
        frames, meta = load_frames_and_metadata(str(dicom_path))
        anterior_frame = frames.get("Anterior")

        if anterior_frame is None:
            print(f"[SEGMENTER-ERROR] No 'Anterior' view found in {dicom_path.name}")
            return {"status": "error", "message": "Anterior frame not found."}
        
        # Jika frame multi-slice, buat sum projection
        if anterior_frame.ndim == 3:
            anterior_frame = np.sum(anterior_frame, axis=0)

        # 2. Jalankan prediksi segmentasi
        # predict_bone_mask akan mengembalikan gambar RGB berwarna
        segmented_rgb = predict_bone_mask(anterior_frame, to_rgb=True)

        # 3. Simpan hasilnya ke file PNG
        study_date = meta.get("study_date", "unknown_date")
        filename_stem = generate_filename_stem(patient_id, study_date)
        
        # Tentukan nama file output yang konsisten
        output_path = dicom_path.parent / f"{filename_stem}_segmentation_colored.png"
        
        # Simpan gambar menggunakan PIL
        Image.fromarray(segmented_rgb).save(output_path)
        
        print(f"[SEGMENTER-PROC] Segmentation saved to: {output_path}")
        return {"status": "success", "output_path": str(output_path)}

    except Exception as e:
        import traceback
        print(f"[SEGMENTER-FATAL-ERROR] Failed to process segmentation for {dicom_path.name}: {e}")
        traceback.print_exc()
        return {"status": "error", "message": str(e)}