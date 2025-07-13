# Di file backend, misal: backend/processing_wrapper.py

from pathlib import Path
from typing import List, Dict
# Import yang diperlukan oleh HotspotProcessor di sini
from .hotspot_processor import HotspotProcessor

def run_hotspot_processing_in_process(scan_path: Path, patient_id: str) -> Dict:
    """
    Fungsi ini akan dijalankan dalam proses terpisah.
    Fixed version with proper error handling.
    """
    try:
        print(f"[DEBUG] Starting hotspot processing for {scan_path}")
        
        # Import here to avoid issues with multiprocessing
        from .hotspot_processor import HotspotProcessor
        
        # Inisialisasi prosesor HANYA di dalam proses ini
        processor = HotspotProcessor()
        
        # Load frames first
        from features.dicom_import.logic.dicom_loader import load_frames_and_metadata
        frames, meta = load_frames_and_metadata(scan_path)
        
        if not frames:
            print(f"[WARN] No frames loaded for {scan_path}")
            return {"frames": [], "ant_frames": [], "post_frames": []}
        
        # Process frames for both views
        result = {
            "frames": [],
            "ant_frames": [],
            "post_frames": []
        }
        
        # Check for XML files
        session_code = None
        folder_name = scan_path.parent.name
        if "_" in folder_name:
            pid, session_code = folder_name.split("_", 1)
        else:
            pid = folder_name
            
        ant_xml_path = scan_path.parent / f"{pid}_ant.xml"
        post_xml_path = scan_path.parent / f"{pid}_post.xml"
        
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
                    ant_processed = processor.process_frame_with_xml(frame, ant_xml_path, patient_id, "ant")
                    result["ant_frames"].append(ant_processed or frame)
                else:
                    result["ant_frames"].append(frame)
                
                # Process posterior view
                if post_xml_path.exists():
                    post_processed = processor.process_frame_with_xml(frame, post_xml_path, patient_id, "post")
                    result["post_frames"].append(post_processed or frame)
                else:
                    result["post_frames"].append(frame)
                
                # For main frames, use the appropriate view based on filename
                filename_lower = scan_path.stem.lower()
                if "post" in filename_lower and post_xml_path.exists():
                    processed = processor.process_frame_with_xml(frame, post_xml_path, patient_id, "post")
                    result["frames"].append(processed or frame)
                elif "ant" in filename_lower and ant_xml_path.exists():
                    processed = processor.process_frame_with_xml(frame, ant_xml_path, patient_id, "ant")
                    result["frames"].append(processed or frame)
                else:
                    result["frames"].append(frame)
                    
            except Exception as e:
                print(f"[ERROR] Error processing frame {view_name}: {e}")
                result["frames"].append(frame)
                result["ant_frames"].append(frame)
                result["post_frames"].append(frame)
        
        # Cleanup
        if hasattr(processor, 'cleanup'):
            processor.cleanup()
            
        print(f"[DEBUG] Hotspot processing completed for {scan_path}")
        return result
        
    except Exception as e:
        print(f"[ERROR] Exception in hotspot processing: {e}")
        import traceback
        traceback.print_exc()
        return {"frames": [], "ant_frames": [], "post_frames": []}