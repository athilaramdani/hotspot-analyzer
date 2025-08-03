# features/spect_viewer/logic/processing_wrapper.py - COMPLETE WITH QUANTIFICATION INTEGRATION
"""
Processing wrapper for SPECT viewer with DICOM integration
Handles YOLO detection, hotspot processing, classification, and NEW quantification
"""

import sys
import traceback
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
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

# Import segmenter
from .segmenter import predict_bone_mask

# Import box detection
from .box_detection import run_yolo_detection_for_patient

# Import hotspot processor with fallback
try:
    from .hotspot_processor import HotspotProcessor
except ImportError as e:
    print(f"Warning: Could not import HotspotProcessor: {e}")
    
    class HotspotProcessor:
        """Fallback HotspotProcessor for when the real one isn't available"""
        def process_frame_with_xml(self, frame, xml_path, patient_id, view, study_date=None):
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
                    processing_frame, str(ant_xml_path), patient_id, "ant", study_date=study_date
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
                    processing_frame, str(post_xml_path), patient_id, "post", study_date=study_date
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


def run_classification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    Run classification for patient using the new classification wrapper
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date in YYYYMMDD format
        
    Returns:
        True if classification successful, False otherwise
    """
    try:
        print(f"[CLASSIFICATION] Starting classification for patient {patient_id}")
        from .classification_wrapper import run_classification_for_patient as clf_runner
        result = clf_runner(dicom_path, patient_id, study_date)
        
        if result:
            print(f"[CLASSIFICATION] Classification completed successfully")
        else:
            print(f"[CLASSIFICATION] Classification failed")
            
        return result
        
    except Exception as e:
        print(f"[CLASSIFICATION ERROR] Classification import/run failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_quantification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    NEW: Run BSI quantification for patient using classification masks
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date in YYYYMMDD format
        
    Returns:
        True if quantification successful, False otherwise
    """
    try:
        print(f"[QUANTIFICATION] Starting BSI quantification for patient {patient_id}")
        print(f"[QUANTIFICATION] Using classification masks instead of Otsu results")
        
        from .quantification_wrapper import run_quantification_for_patient as quant_runner
        result = quant_runner(dicom_path, patient_id, study_date)
        
        if result:
            print(f"[QUANTIFICATION] BSI quantification completed successfully")
        else:
            print(f"[QUANTIFICATION] BSI quantification failed")
            
        return result
        
    except Exception as e:
        print(f"[QUANTIFICATION ERROR] Quantification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


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


def run_complete_analysis_pipeline(dicom_path: Path, patient_id: str, study_date: str = None) -> Dict:
    """
    NEW: Run complete analysis pipeline for a patient
    Pipeline: YOLO → Otsu → Classification → Quantification
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date (optional, will be extracted if not provided)
        
    Returns:
        Dictionary with processing results summary
    """
    
    if not study_date:
        study_date = extract_study_date_from_dicom(dicom_path)
    
    print(f"## Starting complete analysis pipeline for patient {patient_id}")
    print(f"## Study date: {study_date}")
    print(f"## Pipeline: YOLO → Otsu → Classification → QUANTIFICATION")
    
    results = {
        "patient_id": patient_id,
        "study_date": study_date,
        "dicom_path": str(dicom_path),
        "steps": {
            "yolo_detection": False,
            "otsu_processing": False,
            "classification": False,
            "quantification": False
        },
        "files_generated": [],
        "errors": []
    }
    
    try:
        # Step 1: YOLO Detection
        print(f"## Step 1: YOLO Detection")
        yolo_result = run_yolo_detection_wrapper(dicom_path, patient_id)
        yolo_success = any(yolo_result.values())
        results["steps"]["yolo_detection"] = yolo_success
        if yolo_success:
            results["files_generated"].extend(["XML files"])
            print(f"[PIPELINE] YOLO detection completed successfully")
        else:
            results["errors"].append("YOLO detection failed")
            print(f"[PIPELINE] YOLO detection failed")
        
        # Step 2: Otsu Processing
        print(f"## Step 2: Otsu Hotspot Processing")
        otsu_result = run_hotspot_processing_in_process(dicom_path, patient_id)
        otsu_success = len(otsu_result.get("frames", [])) > 0
        results["steps"]["otsu_processing"] = otsu_success
        if otsu_success:
            results["files_generated"].extend(["Hotspot PNG files"])
            print(f"[PIPELINE] Otsu processing completed successfully")
        else:
            results["errors"].append("Otsu processing failed")
            print(f"[PIPELINE] Otsu processing failed")
        
        # Step 3: Classification
        print(f"## Step 3: Classification Analysis")
        classification_result = run_classification_for_patient(dicom_path, patient_id, study_date)
        results["steps"]["classification"] = classification_result
        if classification_result:
            results["files_generated"].extend(["Classification JSON", "Classification mask PNG"])
            print(f"[PIPELINE] Classification completed successfully")
        else:
            results["errors"].append("Classification failed")
            print(f"[PIPELINE] Classification failed")
        
        # Step 4: NEW Quantification (only if classification successful)
        print(f"## Step 4: BSI Quantification")
        if classification_result:
            quantification_result = run_quantification_for_patient(dicom_path, patient_id, study_date)
            results["steps"]["quantification"] = quantification_result
            if quantification_result:
                results["files_generated"].extend(["BSI quantification JSON"])
                print(f"[PIPELINE] BSI quantification completed successfully")
            else:
                results["errors"].append("Quantification failed")
                print(f"[PIPELINE] BSI quantification failed")
        else:
            results["errors"].append("Quantification skipped - classification required")
            print(f"[PIPELINE] Quantification skipped - classification required for input")
        
        # Summary
        success_count = sum(1 for step in results["steps"].values() if step)
        total_steps = len(results["steps"])
        
        print(f"## Pipeline completed: {success_count}/{total_steps} steps successful")
        print(f"## Files generated: {', '.join(results['files_generated'])}")
        
        if results["errors"]:
            print(f"## Errors: {', '.join(results['errors'])}")
        
        results["success_rate"] = success_count / total_steps
        results["pipeline_successful"] = success_count == total_steps
        
        return results
        
    except Exception as e:
        print(f"## Pipeline error: {e}")
        results["errors"].append(f"Pipeline error: {e}")
        results["success_rate"] = 0.0
        results["pipeline_successful"] = False
        return results


def get_patient_analysis_status(dicom_path: Path, patient_id: str, study_date: str = None) -> Dict:
    """
    Get analysis status for a patient - check which files exist
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date (optional, will be extracted if not provided)
        
    Returns:
        Dictionary with file existence status
    """
    
    if not study_date:
        study_date = extract_study_date_from_dicom(dicom_path)
    
    patient_folder = dicom_path.parent
    filename_stem = generate_filename_stem(patient_id, study_date)
    
    # Check for key files
    status = {
        "patient_id": patient_id,
        "study_date": study_date,
        "filename_stem": filename_stem,
        "files_exist": {
            "dicom": dicom_path.exists(),
            "segmentation": {
                "anterior_colored": (patient_folder / f"{filename_stem}_anterior_colored.png").exists(),
                "posterior_colored": (patient_folder / f"{filename_stem}_posterior_colored.png").exists(),
            },
            "yolo_xml": {
                "anterior": (patient_folder / f"{filename_stem}_ant.xml").exists(),
                "posterior": (patient_folder / f"{filename_stem}_post.xml").exists(),
            },
            "otsu_hotspot": {
                "anterior": (patient_folder / f"{filename_stem}_ant_hotspot_mask.png").exists(),
                "posterior": (patient_folder / f"{filename_stem}_post_hotspot_mask.png").exists(),
            },
            "classification": {
                "anterior_json": (patient_folder / f"{filename_stem}_anterior_classification.json").exists(),
                "anterior_mask": (patient_folder / f"{filename_stem}_anterior_classification_mask.png").exists(),
                "posterior_json": (patient_folder / f"{filename_stem}_posterior_classification.json").exists(),
                "posterior_mask": (patient_folder / f"{filename_stem}_posterior_classification_mask.png").exists(),
            },
            "quantification": {
                "bsi_json": (patient_folder / f"{filename_stem}_bsi_quantification.json").exists(),
            }
        }
    }
    
    # Calculate completion percentages
    seg_complete = all(status["files_exist"]["segmentation"].values())
    yolo_complete = all(status["files_exist"]["yolo_xml"].values())
    otsu_complete = all(status["files_exist"]["otsu_hotspot"].values())
    classification_complete = all(status["files_exist"]["classification"].values())
    quantification_complete = all(status["files_exist"]["quantification"].values())
    
    status["completion"] = {
        "segmentation": seg_complete,
        "yolo_detection": yolo_complete,
        "otsu_processing": otsu_complete,
        "classification": classification_complete,
        "quantification": quantification_complete,
        "overall_complete": all([seg_complete, yolo_complete, otsu_complete, classification_complete, quantification_complete])
    }
    
    # Determine next step needed
    if not seg_complete:
        status["next_step"] = "segmentation"
    elif not yolo_complete:
        status["next_step"] = "yolo_detection"
    elif not otsu_complete:
        status["next_step"] = "otsu_processing"
    elif not classification_complete:
        status["next_step"] = "classification"
    elif not quantification_complete:
        status["next_step"] = "quantification"
    else:
        status["next_step"] = "complete"
    
    return status


def run_missing_analysis_steps(dicom_path: Path, patient_id: str, study_date: str = None) -> Dict:
    """
    Run only missing analysis steps for a patient
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date (optional, will be extracted if not provided)
        
    Returns:
        Dictionary with processing results
    """
    
    if not study_date:
        study_date = extract_study_date_from_dicom(dicom_path)
    
    # Check current status
    status = get_patient_analysis_status(dicom_path, patient_id, study_date)
    
    print(f"## Checking analysis status for patient {patient_id}")
    print(f"## Next step needed: {status['next_step']}")
    
    results = {
        "patient_id": patient_id,
        "study_date": study_date,
        "initial_status": status["next_step"],
        "steps_run": [],
        "success": False
    }
    
    if status["next_step"] == "complete":
        print(f"## All analysis steps already complete")
        results["success"] = True
        return results
    
    # Run missing steps in order
    completion = status["completion"]
    
    try:
        # YOLO Detection (if needed)
        if not completion["yolo_detection"]:
            print(f"## Running missing step: YOLO Detection")
            yolo_result = run_yolo_detection_wrapper(dicom_path, patient_id)
            yolo_success = any(yolo_result.values())
            results["steps_run"].append(("yolo_detection", yolo_success))
            if not yolo_success:
                return results
        
        # Otsu Processing (if needed)
        if not completion["otsu_processing"]:
            print(f"## Running missing step: Otsu Processing")
            otsu_result = run_hotspot_processing_in_process(dicom_path, patient_id)
            otsu_success = len(otsu_result.get("frames", [])) > 0
            results["steps_run"].append(("otsu_processing", otsu_success))
            if not otsu_success:
                return results
        
        # Classification (if needed)
        if not completion["classification"]:
            print(f"## Running missing step: Classification")
            classification_result = run_classification_for_patient(dicom_path, patient_id, study_date)
            results["steps_run"].append(("classification", classification_result))
            if not classification_result:
                return results
        
        # Quantification (if needed)
        if not completion["quantification"]:
            print(f"## Running missing step: Quantification")
            quantification_result = run_quantification_for_patient(dicom_path, patient_id, study_date)
            results["steps_run"].append(("quantification", quantification_result))
            if not quantification_result:
                return results
        
        results["success"] = True
        print(f"## Missing analysis steps completed successfully")
        
    except Exception as e:
        print(f"## Error running missing steps: {e}")
        results["error"] = str(e)
    
    return results


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
        
        # Check classification and quantification modules
        try:
            from .classification_wrapper import run_classification_for_patient
            print("[VALIDATION] Classification wrapper import successful")
        except ImportError as e:
            print(f"[VALIDATION WARNING] Classification wrapper not available: {e}")
        
        try:
            from .quantification_wrapper import run_quantification_for_patient
            print("[VALIDATION] Quantification wrapper import successful")
        except ImportError as e:
            print(f"[VALIDATION WARNING] Quantification wrapper not available: {e}")
        
        print("[VALIDATION] Processing environment is valid")
        return True
        
    except Exception as e:
        print(f"[VALIDATION ERROR] Environment validation failed: {e}")
        return False


def get_processing_summary(dicom_path: Path, patient_id: str, study_date: str = None) -> str:
    """
    Get a formatted summary of processing status for a patient
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date (optional, will be extracted if not provided)
        
    Returns:
        Formatted string summary
    """
    try:
        if not study_date:
            study_date = extract_study_date_from_dicom(dicom_path)
        
        status = get_patient_analysis_status(dicom_path, patient_id, study_date)
        
        summary = []
        summary.append("=" * 50)
        summary.append("PROCESSING STATUS SUMMARY")
        summary.append("=" * 50)
        summary.append(f"Patient ID: {patient_id}")
        summary.append(f"Study Date: {study_date}")
        summary.append(f"Next Step Needed: {status['next_step']}")
        summary.append("")
        
        summary.append("STEP COMPLETION:")
        summary.append("-" * 30)
        completion = status["completion"]
        summary.append(f"✅ Segmentation: {'Complete' if completion['segmentation'] else 'Incomplete'}")
        summary.append(f"✅ YOLO Detection: {'Complete' if completion['yolo_detection'] else 'Incomplete'}")
        summary.append(f"✅ Otsu Processing: {'Complete' if completion['otsu_processing'] else 'Incomplete'}")
        summary.append(f"✅ Classification: {'Complete' if completion['classification'] else 'Incomplete'}")
        summary.append(f"✅ Quantification: {'Complete' if completion['quantification'] else 'Incomplete'}")
        summary.append("")
        
        if completion["quantification"]:
            # Add quantification summary if available
            try:
                from .quantification_integration import get_quantification_status
                quant_status = get_quantification_status(dicom_path, patient_id, study_date)
                if quant_status.get("quantification_complete"):
                    summary.append("QUANTIFICATION RESULTS:")
                    summary.append("-" * 30)
                    summary.append(f"BSI Score: {quant_status.get('bsi_score', 0):.2f}%")
                    summary.append(f"Abnormal Hotspots: {quant_status.get('total_abnormal_hotspots', 0)}")
            except Exception:
                pass
        
        summary.append("=" * 50)
        
        return "\n".join(summary)
        
    except Exception as e:
        return f"Error generating processing summary: {e}"


# Test function
if __name__ == "__main__":
    if len(sys.argv) > 2:
        dicom_path = Path(sys.argv[1])
        patient_id = sys.argv[2]
        
        if not validate_processing_environment():
            print("Environment validation failed")
            sys.exit(1)
        
        if dicom_path.exists():
            print(f"Testing complete pipeline for: {dicom_path}")
            
            # Run complete analysis
            results = run_complete_analysis_pipeline(dicom_path, patient_id)
            print(f"Pipeline completed with success rate: {results['success_rate']:.2f}")
            
            # Print summary
            summary = get_processing_summary(dicom_path, patient_id)
            print(summary)
            
        else:
            print(f"DICOM file not found: {dicom_path}")
    else:
        print("Usage: python processing_wrapper.py <dicom_path> <patient_id>")
        print("Running environment validation...")
        validate_processing_environment()