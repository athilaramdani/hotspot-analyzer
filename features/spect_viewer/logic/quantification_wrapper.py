# features/spect_viewer/logic/quantification_wrapper.py - UPDATED QUANTIFICATION INTEGRATION

import numpy as np
import cv2
from pathlib import Path
import json
from core.logger import _log
from core.config.paths import get_classification_files, get_quantification_files # Pastikan ini di-import


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
        if path is None:
            return None
            
        # Load as RGB
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            _log(f"     [WARNING] Could not load colored segmentation: {path}")
            return None
        
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
        if path is None:
            return None
            
        # Load as RGB
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            _log(f"     [WARNING] Could not load classification mask: {path}")
            return None
        
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
    Updated to handle None parameters (missing data)
    """
    result = {}
    for segment_id in DICT_SEGMENT_ID:
        # Initialize counts
        count_segment = 0
        count_hotspot_normal = 0
        count_hotspot_abnormal = 0
        
        # Process anterior data if available
        if image_segment_anterior is not None and image_hotspot_anterior is not None:
            mask_anterior = image_segment_anterior == segment_id
            count_segment += np.sum(mask_anterior)
            count_hotspot_normal += np.sum(image_hotspot_anterior[mask_anterior] == 1)
            count_hotspot_abnormal += np.sum(image_hotspot_anterior[mask_anterior] == 2)
        
        # Process posterior data if available
        if image_segment_posterior is not None and image_hotspot_posterior is not None:
            mask_posterior = image_segment_posterior == segment_id
            count_segment += np.sum(mask_posterior)
            count_hotspot_normal += np.sum(image_hotspot_posterior[mask_posterior] == 1)
            count_hotspot_abnormal += np.sum(image_hotspot_posterior[mask_posterior] == 2)
        
        # Store results
        result[DICT_SEGMENT_ID[segment_id]] = {
            "total_segment_pixels": int(count_segment),
            "hotspot_normal": int(count_hotspot_normal),
            "percentage_normal": float(count_hotspot_normal) / count_segment if count_segment else 0.0,
            "hotspot_abnormal": int(count_hotspot_abnormal),
            "percentage_abnormal": float(count_hotspot_abnormal) / count_segment if count_segment else 0.0,
        }
    
    return result

def get_quantification_input_paths(patient_folder: Path, filename_stem: str) -> dict:
    """Get input file paths for quantification, prioritizing _edited files."""
    # Import function dari paths.py
    from core.config.paths import get_segmentation_files_for_quantification
    
    # Dapatkan path untuk kedua view menggunakan fungsi dari paths.py
    ant_clf_files = get_classification_files(patient_folder, filename_stem, "anterior")
    post_clf_files = get_classification_files(patient_folder, filename_stem, "posterior")
    quant_files = get_quantification_files(patient_folder, filename_stem)
    
    # ✅ NEW: Get segmentation files with edited priority
    ant_seg_files = get_segmentation_files_for_quantification(patient_folder, filename_stem, "anterior")
    post_seg_files = get_segmentation_files_for_quantification(patient_folder, filename_stem, "posterior")
    
    # Pilih path mask yang benar (prioritaskan _edited jika ada)
    ant_mask_to_use = ant_clf_files['mask_edited'] if ant_clf_files['mask_edited'].exists() else ant_clf_files['mask_original']
    post_mask_to_use = post_clf_files['mask_edited'] if post_clf_files['mask_edited'].exists() else post_clf_files['mask_original']
    
    # ✅ UPDATED: Check for any edited files (segmentation OR classification)
    has_edited_files = (
        ant_clf_files['mask_edited'].exists() or 
        post_clf_files['mask_edited'].exists() or
        ant_seg_files['colored_edited'].exists() or 
        post_seg_files['colored_edited'].exists()
    )
    
    output_file = quant_files['bsi_json_edited'] if has_edited_files else quant_files['bsi_json_original']

    return {
        'segment_anterior': ant_seg_files['colored_to_use'],    # ✅ PRIORITY: edited → original
        'segment_posterior': post_seg_files['colored_to_use'],  # ✅ PRIORITY: edited → original
        'hotspot_anterior': ant_mask_to_use,                   # ✅ Already has priority
        'hotspot_posterior': post_mask_to_use,                 # ✅ Already has priority
        'output_result': output_file                           # ✅ Use edited JSON if any edited files
    }
    
def check_available_files(paths):
    """
    ✅ FIXED: Better validation for empty XML files
    """
    available_paths = {}
    missing_files = []
    
    # Check each path (except output_result)
    for name, path in paths.items():
        if name != 'output_result':
            if path.exists():
                # ✅ SPECIAL CHECK: For XML files, validate they have proper structure
                if name.endswith('_xml') or 'xml' in name:
                    if _validate_xml_file(path):
                        available_paths[name] = path
                    else:
                        print(f"[QUANTIFICATION] XML file exists but invalid: {path}")
                        missing_files.append(f"{name} (invalid XML)")
                else:
                    available_paths[name] = path
            else:
                missing_files.append(f"{name} ({path.name})")
    
    # Determine if we can proceed
    has_anterior_pair = ('segment_anterior' in available_paths and 
                        'hotspot_anterior' in available_paths)
    has_posterior_pair = ('segment_posterior' in available_paths and 
                         'hotspot_posterior' in available_paths)
    
    can_proceed = has_anterior_pair or has_posterior_pair
    
    return available_paths, missing_files, can_proceed

def _validate_xml_file(xml_path: Path) -> bool:
    """Validate XML file has proper structure (even if empty)"""
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        # Check basic structure exists
        if root.tag != 'annotation':
            return False
        
        # XML is valid even if no objects (empty is OK for quantification)
        return True
        
    except Exception as e:
        print(f"[XML VALIDATION] Error validating {xml_path}: {e}")
        return False


def run_quantification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    Run BSI quantification for a patient using UPDATED workflow
    Now supports partial data (anterior only, posterior only, etc.)
    
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
        _log(f"     Using UPDATED quantification with flexible input handling")
        _log(f"     New workflow: Segmentation + Classification -> Quantification")
        
        # Get file paths
        paths = get_quantification_input_paths(patient_folder, filename_stem)
        
        # Check available files
        available_paths, missing_files, can_proceed = check_available_files(paths)
        
        if not can_proceed:
            _log(f"     Cannot proceed with quantification. Missing files: {', '.join(missing_files)}")
            _log(f"     Need at least one matching segmentation-hotspot pair")
            return False
        
        if missing_files:
            _log(f"     [WARNING] Some files missing: {', '.join(missing_files)}")
            _log(f"     Proceeding with available files: {list(available_paths.keys())}")
        
        # Load files with None handling
        _log(f"     Loading segmentation files...")
        seg_anterior = None
        seg_posterior = None
        
        if 'segment_anterior' in available_paths:
            seg_anterior = load_colored_segmentation_as_id(available_paths['segment_anterior'])
            
        if 'segment_posterior' in available_paths:
            seg_posterior = load_colored_segmentation_as_id(available_paths['segment_posterior'])
        
        _log(f"     Loading classification mask files...")
        hot_anterior = None
        hot_posterior = None
        
        if 'hotspot_anterior' in available_paths:
            hot_anterior = load_classification_mask_as_hotspot(available_paths['hotspot_anterior'])
            
        if 'hotspot_posterior' in available_paths:
            hot_posterior = load_classification_mask_as_hotspot(available_paths['hotspot_posterior'])
        
        # Validate we have at least some data
        if all(x is None for x in [seg_anterior, seg_posterior]):
            _log(f"     [ERROR] No segmentation data could be loaded")
            return False
            
        if all(x is None for x in [hot_anterior, hot_posterior]):
            _log(f"     [ERROR] No hotspot data could be loaded")
            return False
        
        _log(f"     Calculating BSI with flexible inputs...")
        # Calculate BSI using updated function with None handling
        bsi_result = calculate_BSI(seg_anterior, seg_posterior, hot_anterior, hot_posterior)
        
        # Add metadata to result
        final_result = {
            "patient_info": {
                "patient_id": patient_id,
                "study_date": study_date,
                "filename_stem": filename_stem,
                "quantification_method": "BSI_with_classification_masks_v2",
                "input_files": {
                    "segmentation_anterior": available_paths.get('segment_anterior', {}).name if 'segment_anterior' in available_paths else "Not available",
                    "segmentation_posterior": available_paths.get('segment_posterior', {}).name if 'segment_posterior' in available_paths else "Not available",
                    "hotspot_anterior": available_paths.get('hotspot_anterior', {}).name if 'hotspot_anterior' in available_paths else "Not available",
                    "hotspot_posterior": available_paths.get('hotspot_posterior', {}).name if 'hotspot_posterior' in available_paths else "Not available"
                },
                "data_availability": {
                    "has_anterior_data": seg_anterior is not None and hot_anterior is not None,
                    "has_posterior_data": seg_posterior is not None and hot_posterior is not None,
                    "missing_files": missing_files
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
        
        # Log data availability summary
        data_summary = final_result["patient_info"]["data_availability"]
        _log(f"     Data availability: Anterior={data_summary['has_anterior_data']}, Posterior={data_summary['has_posterior_data']}")
        
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
    data_availability = patient_info.get('data_availability', {})
    
    text = f"=== BSI Quantification Results ===\n"
    text += f"Patient: {patient_info.get('patient_id', 'Unknown')}\n"
    text += f"Study Date: {patient_info.get('study_date', 'Unknown')}\n"
    text += f"Method: Classification-based BSI v2\n"
    
    # Data availability info
    text += f"\nData Availability:\n"
    text += f"• Anterior Data: {'✓' if data_availability.get('has_anterior_data') else '✗'}\n"
    text += f"• Posterior Data: {'✓' if data_availability.get('has_posterior_data') else '✗'}\n"
    
    if data_availability.get('missing_files'):
        text += f"• Missing Files: {len(data_availability['missing_files'])}\n"
    
    text += f"\nOverall Statistics:\n"
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

def get_quantification_capabilities(patient_folder: Path, filename_stem: str):
    """
    Check what quantification capabilities are available for a patient
    
    Args:
        patient_folder: Patient directory path
        filename_stem: Filename stem ([patient_id]_[study_date])
        
    Returns:
        Dictionary with capability information
    """
    paths = get_quantification_input_paths(patient_folder, filename_stem)
    available_paths, missing_files, can_proceed = check_available_files(paths)
    
    return {
        "can_quantify": can_proceed,
        "available_files": list(available_paths.keys()),
        "missing_files": missing_files,
        "has_anterior_pair": 'segment_anterior' in available_paths and 'hotspot_anterior' in available_paths,
        "has_posterior_pair": 'segment_posterior' in available_paths and 'hotspot_posterior' in available_paths,
        "partial_data_only": can_proceed and len(missing_files) > 0
    }