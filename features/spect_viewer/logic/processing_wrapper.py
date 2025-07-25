# Di file backend, misal: backend/processing_wrapper.py

from pathlib import Path
from typing import List, Dict
import numpy as np

# Import yang diperlukan oleh HotspotProcessor di sini
from .hotspot_processor import HotspotProcessor

def run_hotspot_processing_in_process(scan_path: Path, patient_id: str) -> Dict:
    """
    Fungsi ini akan dijalankan dalam proses terpisah.
    Enhanced version with study date support for XML file detection.
    """
    try:
        print(f"[DEBUG] Starting hotspot processing for {scan_path}")
        
        # Import here to avoid issues with multiprocessing
        from .hotspot_processor import HotspotProcessor
        
        # Inisialisasi prosesor HANYA di dalam proses ini
        processor = HotspotProcessor()
        
        # Load frames first
        from features.dicom_import.logic.dicom_loader import load_frames_and_metadata, extract_study_date_from_dicom
        frames, meta = load_frames_and_metadata(scan_path)
        
        if not frames:
            print(f"[WARN] No frames loaded for {scan_path}")
            return {"frames": [], "ant_frames": [], "post_frames": []}
        
        # Extract study date from DICOM for XML file naming
        try:
            study_date = extract_study_date_from_dicom(scan_path)
            print(f"[DEBUG] Extracted study date: {study_date}")
        except Exception as e:
            print(f"[WARN] Could not extract study date: {e}")
            from datetime import datetime
            study_date = datetime.now().strftime("%Y%m%d")
        
        # Process frames for both views
        result = {
            "frames": [],
            "ant_frames": [],
            "post_frames": []
        }
        
        # Generate filename stem with study date for XML detection
        from core.config.paths import generate_filename_stem
        filename_stem = generate_filename_stem(patient_id, study_date)
        
        # Check for XML files with NEW naming convention (includes study date)
        ant_xml_path = scan_path.parent / f"{filename_stem}_ant.xml"
        post_xml_path = scan_path.parent / f"{filename_stem}_post.xml"
        
        # Fallback to OLD naming convention if new files don't exist
        if not ant_xml_path.exists():
            ant_xml_path_old = scan_path.parent / f"{patient_id}_ant.xml"
            if ant_xml_path_old.exists():
                ant_xml_path = ant_xml_path_old
                print(f"[DEBUG] Using old XML naming: {ant_xml_path}")
        
        if not post_xml_path.exists():
            post_xml_path_old = scan_path.parent / f"{patient_id}_post.xml"
            if post_xml_path_old.exists():
                post_xml_path = post_xml_path_old
                print(f"[DEBUG] Using old XML naming: {post_xml_path}")
        
        print(f"[DEBUG] Looking for XML files:")
        print(f"  Anterior: {ant_xml_path} (exists: {ant_xml_path.exists()})")
        print(f"  Posterior: {post_xml_path} (exists: {post_xml_path.exists()})")
        
        # Process each frame
        for view_name, frame in frames.items():
            try:
                if not isinstance(frame, np.ndarray):
                    print(f"[WARN] Skipping non-array frame: {view_name}")
                    result["frames"].append(frame)
                    result["ant_frames"].append(frame)
                    result["post_frames"].append(frame)
                    continue
                
                # Process anterior view
                if ant_xml_path.exists():
                    ant_processed = processor.process_frame_with_xml(frame, str(ant_xml_path), patient_id, "ant")
                    result["ant_frames"].append(ant_processed or frame)
                    print(f"[DEBUG] Processed anterior frame with XML")
                else:
                    result["ant_frames"].append(frame)
                    print(f"[DEBUG] No anterior XML found, using original frame")
                
                # Process posterior view
                if post_xml_path.exists():
                    post_processed = processor.process_frame_with_xml(frame, str(post_xml_path), patient_id, "post")
                    result["post_frames"].append(post_processed or frame)
                    print(f"[DEBUG] Processed posterior frame with XML")
                else:
                    result["post_frames"].append(frame)
                    print(f"[DEBUG] No posterior XML found, using original frame")
                
                # For main frames, use the appropriate view based on filename or view_name
                view_lower = view_name.lower()
                filename_lower = scan_path.stem.lower()
                
                if ("post" in view_lower or "post" in filename_lower) and post_xml_path.exists():
                    processed = processor.process_frame_with_xml(frame, str(post_xml_path), patient_id, "post")
                    result["frames"].append(processed or frame)
                    print(f"[DEBUG] Used posterior processing for main frames")
                elif ("ant" in view_lower or "ant" in filename_lower) and ant_xml_path.exists():
                    processed = processor.process_frame_with_xml(frame, str(ant_xml_path), patient_id, "ant")
                    result["frames"].append(processed or frame)
                    print(f"[DEBUG] Used anterior processing for main frames")
                else:
                    # Default: try anterior first, then posterior, then original
                    if ant_xml_path.exists():
                        processed = processor.process_frame_with_xml(frame, str(ant_xml_path), patient_id, "ant")
                        result["frames"].append(processed or frame)
                        print(f"[DEBUG] Used anterior processing as default for main frames")
                    elif post_xml_path.exists():
                        processed = processor.process_frame_with_xml(frame, str(post_xml_path), patient_id, "post")
                        result["frames"].append(processed or frame)
                        print(f"[DEBUG] Used posterior processing as fallback for main frames")
                    else:
                        result["frames"].append(frame)
                        print(f"[DEBUG] No XML files found, using original frame for main frames")
                    
            except Exception as e:
                print(f"[ERROR] Error processing frame {view_name}: {e}")
                result["frames"].append(frame)
                result["ant_frames"].append(frame)
                result["post_frames"].append(frame)
        
        # Cleanup
        if hasattr(processor, 'cleanup'):
            processor.cleanup()
            
        print(f"[DEBUG] Hotspot processing completed for {scan_path}")
        print(f"[DEBUG] Processed {len(result['frames'])} main frames, {len(result['ant_frames'])} ant frames, {len(result['post_frames'])} post frames")
        return result
        
    except Exception as e:
        print(f"[ERROR] Exception in hotspot processing: {e}")
        import traceback
        traceback.print_exc()
        return {"frames": [], "ant_frames": [], "post_frames": []}