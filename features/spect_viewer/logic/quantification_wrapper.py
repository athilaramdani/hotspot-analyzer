# features/spect_viewer/logic/quantification_wrapper.py - NEW QUANTIFICATION INTEGRATION

import numpy as np
import cv2
from pathlib import Path
import json
from core.logger import _log

# Quantification constants from your provided code
DICT_SEGMENT_ID = {
    0: "background", 
    1: "skull", 
    2: "cervical vertebrae", 
    3: "thoracic vertebrae",
    4: "rib", 
    5: "sternum", 
    6: "collarbone", 
    7: "scapula", 
    8: "humerus",
    9: "lumbar vertebrae", 
    10: "sacrum", 
    11: "pelvis", 
    12: "femur"
}

DICT_HOTSPOT_COLOR = {
    1: (0, 255, 0),     # Normal - Green
    2: (255, 0, 0)      # Abnormal - Red
}

DICT_SEGMENT_COLOR = {
    0: (0, 0, 0), 
    1: (176, 230, 13), 
    2: (0, 151, 219), 
    3: (126, 230, 225),
    4: (166, 55, 167), 
    5: (230, 157, 180), 
    6: (167, 110, 77), 
    7: (121, 0, 24),
    8: (56, 65, 184), 
    9: (230, 218, 0), 
    10: (230, 114, 35), 
    11: (12, 187, 62),
    12: (230, 182, 22)
}

def load_image_as_array(path):
    """Load image as numpy array"""
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return image

def load_colored_segmentation_as_id(path):
    """
    Convert colored segmentation PNG to segment ID array
    Uses the RGB to ID mapping from DICT_SEGMENT_COLOR
    """
    try:
        # Load as RGB
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Could not load colored segmentation: {path}")
        
        # Convert BGR to RGB for proper color matching
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Create ID array
        id_array = np.zeros(image_rgb.shape[:2], dtype=np.uint8)
        
        # Map RGB colors to segment IDs
        for segment_id, rgb_color in DICT_SEGMENT_COLOR.items():
            # Create mask for this color
            mask = np.all(image_rgb == rgb_color, axis=-1)
            id_array[mask] = segment_id
        
        _log(f"     Converted colored segmentation to ID array: {np.unique(id_array)}")
        return id_array
        
    except Exception as e:
        _log(f"     [ERROR] Failed to convert colored segmentation: {e}")
        return None

def load_classification_mask_as_hotspot(path):
    """
    Convert classification mask PNG to hotspot ID array
    Expected colors:
    - Black (0,0,0): Background -> 0
    - Red (255,0,0): Abnormal -> 2
    - Cream (255,241,188): Normal -> 1
    """
    try:
        # Load as RGB
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            raise FileNotFoundError(f"Could not load classification mask: {path}")
        
        # Convert BGR to RGB for proper color matching
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Create hotspot array
        hotspot_array = np.zeros(image_rgb.shape[:2], dtype=np.uint8)
        
        # Map classification colors to hotspot IDs
        # Black background -> 0 (already initialized)
        
        # Red (abnormal) -> 2
        red_mask = np.all(image_rgb == [255, 0, 0], axis=-1)
        hotspot_array[red_mask] = 2
        
        # Cream (normal) -> 1
        cream_mask = np.all(image_rgb == [255, 241, 188], axis=-1)
        hotspot_array[cream_mask] = 1
        
        _log(f"     Converted classification mask to hotspot array: {np.unique(hotspot_array)}")
        return hotspot_array
        
    except Exception as e:
        _log(f"     [ERROR] Failed to convert classification mask: {e}")
        return None

def calculate_BSI(image_segment_anterior, image_segment_posterior, image_hotspot_anterior, image_hotspot_posterior):
    """
    Calculate BSI (Bone Scan Index) from segmentation and hotspot images
    Same as your original code
    """
    result = {}
    for segment_id in DICT_SEGMENT_ID:
        mask_anterior = image_segment_anterior == segment_id
        mask_posterior = image_segment_posterior == segment_id
        count_segment = np.sum(mask_anterior) + np.sum(mask_posterior)
        count_hotspot_normal = np.sum(image_hotspot_anterior[mask_anterior] == 1) + np.sum(image_hotspot_posterior[mask_posterior] == 1)
        count_hotspot_abnormal = np.sum(image_hotspot_anterior[mask_anterior] == 2) + np.sum(image_hotspot_posterior[mask_posterior] == 2)
        result[DICT_SEGMENT_ID[segment_id]] = {
            "total_segment_pixels": int(count_segment),
            "hotspot_normal": int(count_hotspot_normal),
            "percentage_normal": float(count_hotspot_normal) / count_segment if count_segment else 0.0,
            "hotspot_abnormal": int(count_hotspot_abnormal),
            "percentage_abnormal": float(count_hotspot_abnormal) / count_segment if count_segment else 0.0,
        }
    return result

def get_quantification_input_paths(patient_folder: Path, filename_stem: str):
    """
    Get input file paths for quantification
    
    Args:
        patient_folder: Patient directory path
        filename_stem: Filename stem ([patient_id]_[study_date])
        
    Returns:
        Dictionary with all required file paths
    """
    
    return {
        # Segmentation files (colored PNG converted to ID arrays)
        'segment_anterior': patient_folder / f"{filename_stem}_anterior_colored.png",
        'segment_posterior': patient_folder / f"{filename_stem}_posterior_colored.png",
        
        # Classification mask files (converted to hotspot ID arrays)  
        'hotspot_anterior': patient_folder / f"{filename_stem}_anterior_classification_mask.png",
        'hotspot_posterior': patient_folder / f"{filename_stem}_posterior_classification_mask.png",
        
        # Output file
        'output_result': patient_folder / f"{filename_stem}_bsi_quantification.json"
    }

def run_quantification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    Run BSI quantification for a patient using NEW workflow
    Uses classification masks instead of Otsu hotspot results
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date in YYYYMMDD format
        
    Returns:
        True if quantification successful, False otherwise
    """
    try:
        patient_folder = dicom_path.parent
        filename_stem = f"{patient_id}_{study_date}"
        
        _log(f"     Starting BSI quantification for patient {patient_id}")
        _log(f"     Using classification masks instead of Otsu results")
        _log(f"     New workflow: Segmentation + Classification -> Quantification")
        
        # Get file paths
        paths = get_quantification_input_paths(patient_folder, filename_stem)
        
        # Check if all required files exist
        missing_files = []
        for name, path in paths.items():
            if name != 'output_result' and not path.exists():
                missing_files.append(f"{name} ({path.name})")
        
        if missing_files:
            _log(f"     Missing files for quantification: {', '.join(missing_files)}")
            return False
        
        _log(f"     Loading segmentation files...")
        # Load colored segmentation files and convert to ID arrays
        seg_anterior = load_colored_segmentation_as_id(paths['segment_anterior'])
        seg_posterior = load_colored_segmentation_as_id(paths['segment_posterior'])
        
        if seg_anterior is None or seg_posterior is None:
            _log(f"     Failed to load segmentation files")
            return False
        
        _log(f"     Loading classification mask files...")
        # Load classification mask files and convert to hotspot ID arrays
        hot_anterior = load_classification_mask_as_hotspot(paths['hotspot_anterior'])
        hot_posterior = load_classification_mask_as_hotspot(paths['hotspot_posterior'])
        
        if hot_anterior is None or hot_posterior is None:
            _log(f"     Failed to load classification mask files")
            return False
        
        _log(f"     Calculating BSI...")
        # Calculate BSI using your original function
        bsi_result = calculate_BSI(seg_anterior, seg_posterior, hot_anterior, hot_posterior)
        
        # Add metadata to result
        final_result = {
            "patient_info": {
                "patient_id": patient_id,
                "study_date": study_date,
                "filename_stem": filename_stem,
                "quantification_method": "BSI_with_classification_masks",
                "input_files": {
                    "segmentation_anterior": paths['segment_anterior'].name,
                    "segmentation_posterior": paths['segment_posterior'].name,
                    "hotspot_anterior": paths['hotspot_anterior'].name,
                    "hotspot_posterior": paths['hotspot_posterior'].name
                }
            },
            "bsi_results": bsi_result,
            "summary_statistics": calculate_summary_statistics(bsi_result)
        }
        
        # Save results to JSON
        with open(paths['output_result'], 'w') as f:
            json.dump(final_result, f, indent=2)
        
        _log(f"     BSI quantification completed")
        _log(f"     Results saved: {paths['output_result'].name}")
        _log(f"     Total segments analyzed: {len([k for k, v in bsi_result.items() if v['total_segment_pixels'] > 0])}")
        
        return True
        
    except Exception as e:
        _log(f"     Quantification error for patient {patient_id}: {e}")
        import traceback
        _log(f"     Full traceback: {traceback.format_exc()}")
        return False

def calculate_summary_statistics(bsi_result):
    """Calculate summary statistics from BSI results"""
    total_segment_pixels = sum(v['total_segment_pixels'] for v in bsi_result.values())
    total_normal_hotspots = sum(v['hotspot_normal'] for v in bsi_result.values())
    total_abnormal_hotspots = sum(v['hotspot_abnormal'] for v in bsi_result.values())
    
    # Overall percentages
    overall_normal_percentage = total_normal_hotspots / total_segment_pixels if total_segment_pixels > 0 else 0.0
    overall_abnormal_percentage = total_abnormal_hotspots / total_segment_pixels if total_segment_pixels > 0 else 0.0
    
    # Count segments with findings
    segments_with_normal = sum(1 for v in bsi_result.values() if v['hotspot_normal'] > 0)
    segments_with_abnormal = sum(1 for v in bsi_result.values() if v['hotspot_abnormal'] > 0)
    total_segments_analyzed = sum(1 for v in bsi_result.values() if v['total_segment_pixels'] > 0)
    
    return {
        "total_segment_pixels": total_segment_pixels,
        "total_normal_hotspots": total_normal_hotspots,
        "total_abnormal_hotspots": total_abnormal_hotspots,
        "overall_normal_percentage": overall_normal_percentage,
        "overall_abnormal_percentage": overall_abnormal_percentage,
        "segments_with_normal_hotspots": segments_with_normal,
        "segments_with_abnormal_hotspots": segments_with_abnormal,
        "total_segments_analyzed": total_segments_analyzed,
        "bsi_score": overall_abnormal_percentage * 100  # BSI score as percentage
    }

def load_quantification_results(patient_folder: Path, filename_stem: str):
    """
    Load quantification results from JSON file
    
    Args:
        patient_folder: Patient directory path
        filename_stem: Filename stem ([patient_id]_[study_date])
        
    Returns:
        Dictionary with quantification results or None if not found
    """
    try:
        result_path = patient_folder / f"{filename_stem}_bsi_quantification.json"
        
        if not result_path.exists():
            return None
        
        with open(result_path, 'r') as f:
            results = json.load(f)
        
        return results
        
    except Exception as e:
        _log(f"Failed to load quantification results: {e}")
        return None

def format_quantification_summary(results):
    """
    Format quantification results for display
    
    Args:
        results: Quantification results dictionary
        
    Returns:
        Formatted string for display
    """
    if not results:
        return "No quantification results available"
    
    summary = results.get('summary_statistics', {})
    patient_info = results.get('patient_info', {})
    
    text = f"=== BSI Quantification Results ===\n"
    text += f"Patient: {patient_info.get('patient_id', 'Unknown')}\n"
    text += f"Study Date: {patient_info.get('study_date', 'Unknown')}\n"
    text += f"Method: Classification-based BSI\n\n"
    
    text += f"Overall Statistics:\n"
    text += f"• BSI Score: {summary.get('bsi_score', 0):.2f}%\n"
    text += f"• Normal Hotspots: {summary.get('total_normal_hotspots', 0)}\n"
    text += f"• Abnormal Hotspots: {summary.get('total_abnormal_hotspots', 0)}\n"
    text += f"• Segments Analyzed: {summary.get('total_segments_analyzed', 0)}\n"
    text += f"• Segments with Abnormal: {summary.get('segments_with_abnormal_hotspots', 0)}\n\n"
    
    # Per-segment breakdown
    bsi_results = results.get('bsi_results', {})
    text += f"Per-Segment Breakdown:\n"
    
    for segment_name, data in bsi_results.items():
        if data['total_segment_pixels'] > 0:
            text += f"• {segment_name}:\n"
            text += f"  - Normal: {data['hotspot_normal']} ({data['percentage_normal']:.1f}%)\n"
            text += f"  - Abnormal: {data['hotspot_abnormal']} ({data['percentage_abnormal']:.1f}%)\n"
    
    return text