# features/spect_viewer/logic/quantification_wrapper.py - UPDATED QUANTIFICATION INTEGRATION

import numpy as np
import cv2
from pathlib import Path
import json
from core.logger import _log

# Import from updated algorithm_quantification
from .algorithm_quantification import (
    DICT_SEGMENT_ID,
    DICT_HOTSPOT_COLOR, 
    DICT_SEGMENT_COLOR,
    load_image_as_array,
    calculate_BSI,
    validate_quantification_inputs
)

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

def check_available_files(paths):
    """
    Check which files are available for quantification
    
    Args:
        paths: Dictionary of file paths
        
    Returns:
        Tuple (available_paths, missing_files, can_proceed)
    """
    available_paths = {}
    missing_files = []
    
    required_files = ['segment_anterior', 'segment_posterior', 'hotspot_anterior', 'hotspot_posterior']
    
    for name in required_files:
        path = paths[name]
        if path.exists():
            available_paths[name] = path
        else:
            missing_files.append(f"{name} ({path.name})")
    
    # Check if we can proceed with partial data
    has_anterior_seg = 'segment_anterior' in available_paths
    has_posterior_seg = 'segment_posterior' in available_paths
    has_anterior_hot = 'hotspot_anterior' in available_paths
    has_posterior_hot = 'hotspot_posterior' in available_paths
    
    # We need at least one segmentation and one hotspot file
    has_segmentation = has_anterior_seg or has_posterior_seg
    has_hotspot = has_anterior_hot or has_posterior_hot
    
    # Check for matching pairs
    has_anterior_pair = has_anterior_seg and has_anterior_hot
    has_posterior_pair = has_posterior_seg and has_posterior_hot
    
    can_proceed = has_segmentation and has_hotspot and (has_anterior_pair or has_posterior_pair)
    
    return available_paths, missing_files, can_proceed

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