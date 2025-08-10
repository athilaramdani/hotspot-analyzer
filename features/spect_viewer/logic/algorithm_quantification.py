# features\spect_viewer\logic\algorithm_quantification.py
import cv2
import numpy as np

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
    """
    Load image as numpy array with improved error handling
    
    Args:
        path: Image file path (can be None)
        
    Returns:
        numpy array or None if path is None
    """
    if path is None:
        return None
    
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return image

def calculate_BSI(image_segment_anterior=None, image_segment_posterior=None,
                  image_hotspot_anterior=None, image_hotspot_posterior=None):
    """
    Calculate BSI (Bone Scan Index) from segmentation and hotspot images
    Now supports partial data (anterior only, posterior only, etc.)
    
    Args:
        image_segment_anterior: Anterior segmentation array (optional)
        image_segment_posterior: Posterior segmentation array (optional) 
        image_hotspot_anterior: Anterior hotspot array (optional)
        image_hotspot_posterior: Posterior hotspot array (optional)
        
    Returns:
        Dictionary with BSI results per segment
    """
    result = {}
    
    for segment_id in DICT_SEGMENT_ID:
        count_segment = 0
        count_hotspot_normal = 0
        count_hotspot_abnormal = 0

        # Process anterior view if available
        if image_segment_anterior is not None:
            mask_anterior = image_segment_anterior == segment_id
            count_segment += np.sum(mask_anterior)
            
            # Process anterior hotspots if available
            if image_hotspot_anterior is not None:
                count_hotspot_normal += np.sum(image_hotspot_anterior[mask_anterior] == 1)
                count_hotspot_abnormal += np.sum(image_hotspot_anterior[mask_anterior] == 2)

        # Process posterior view if available
        if image_segment_posterior is not None:
            mask_posterior = image_segment_posterior == segment_id
            count_segment += np.sum(mask_posterior)
            
            # Process posterior hotspots if available
            if image_hotspot_posterior is not None:
                count_hotspot_normal += np.sum(image_hotspot_posterior[mask_posterior] == 1)
                count_hotspot_abnormal += np.sum(image_hotspot_posterior[mask_posterior] == 2)

        # Calculate results for this segment
        result[DICT_SEGMENT_ID[segment_id]] = {
            "total_segment_pixels": int(count_segment),
            "hotspot_normal": int(count_hotspot_normal),
            "percentage_normal": float(count_hotspot_normal) / count_segment if count_segment else 0.0,
            "hotspot_abnormal": int(count_hotspot_abnormal),
            "percentage_abnormal": float(count_hotspot_abnormal) / count_segment if count_segment else 0.0,
        }
    
    return result

def process_single_quantification(path_seg_ant=None, path_seg_pos=None,
                                   path_hs_ant=None, path_hs_pos=None,
                                   path_result="bsi_result.npy"):
    """
    Process quantification for a single patient with flexible input handling
    
    Args:
        path_seg_ant: Path to anterior segmentation (optional)
        path_seg_pos: Path to posterior segmentation (optional)
        path_hs_ant: Path to anterior hotspot (optional)
        path_hs_pos: Path to posterior hotspot (optional)
        path_result: Path to save results (default: "bsi_result.npy")
        
    Returns:
        BSI calculation results
    """
    # Load images with None handling
    seg_ant = load_image_as_array(path_seg_ant)
    seg_pos = load_image_as_array(path_seg_pos)
    hot_ant = load_image_as_array(path_hs_ant)
    hot_pos = load_image_as_array(path_hs_pos)

    # Calculate BSI with flexible inputs
    bsi_result = calculate_BSI(seg_ant, seg_pos, hot_ant, hot_pos)
    
    # Save results
    np.save(path_result, bsi_result)
    
    return bsi_result

def validate_quantification_inputs(path_seg_ant=None, path_seg_pos=None,
                                   path_hs_ant=None, path_hs_pos=None):
    """
    Validate that we have at least some input files for quantification
    
    Args:
        path_seg_ant: Path to anterior segmentation (optional)
        path_seg_pos: Path to posterior segmentation (optional) 
        path_hs_ant: Path to anterior hotspot (optional)
        path_hs_pos: Path to posterior hotspot (optional)
        
    Returns:
        Tuple (is_valid, error_message, available_files)
    """
    from pathlib import Path
    
    available_files = []
    missing_files = []
    
    files_to_check = {
        "anterior_segmentation": path_seg_ant,
        "posterior_segmentation": path_seg_pos,
        "anterior_hotspot": path_hs_ant,
        "posterior_hotspot": path_hs_pos
    }
    
    for name, path in files_to_check.items():
        if path is not None:
            path_obj = Path(path)
            if path_obj.exists():
                available_files.append(name)
            else:
                missing_files.append(name)
        else:
            missing_files.append(name)
    
    # We need at least one segmentation file and one hotspot file
    has_segmentation = any("segmentation" in f for f in available_files)
    has_hotspot = any("hotspot" in f for f in available_files)
    
    if not has_segmentation:
        return False, "No segmentation files available", available_files
    
    if not has_hotspot:
        return False, "No hotspot files available", available_files
    
    if len(available_files) < 2:
        return False, f"Insufficient files for quantification. Available: {available_files}", available_files
    
    return True, "Validation passed", available_files