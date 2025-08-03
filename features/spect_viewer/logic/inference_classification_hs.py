# features\spect_viewer\logic\inference_classification_hs.py - COMPLETE AND FIXED

import pandas as pd
import numpy as np
import SimpleITK as sitk
from radiomics import featureextractor
import xml.etree.ElementTree as ET
import cv2
import os
from sklearn.preprocessing import StandardScaler
import joblib
from xgboost import XGBClassifier
import json
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.image as mpimg
from PIL import Image

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.config.paths import CLASSIFICATION_XGBOOST_MODEL, CLASSIFICATION_SCALER_MODEL

# ✅ FIXED: Use correct path from config
MODEL_PATH = str(CLASSIFICATION_XGBOOST_MODEL)
SCALER_PATH = str(CLASSIFICATION_SCALER_MODEL)

# ✅ RGB to ID mapping from backup classification (for colored-to-grayscale conversion)
KEY_VALUES = {
    (0, 0, 0): 0,              # background
    (176, 230, 13): 1,         # skull
    (0, 151, 219): 2,          # cervical vertebrae
    (126, 230, 225): 3,        # thoracic vertebrae
    (166, 55, 167): 4,         # rib
    (230, 157, 180): 5,        # sternum
    (167, 110, 77): 6,         # collarbone
    (121, 0, 24): 7,           # scapula
    (56, 65, 184): 8,          # humerus
    (230, 218, 0): 9,          # lumbar vertebrae
    (230, 114, 35): 10,        # sacrum
    (12, 187, 62): 11,         # pelvis
    (230, 182, 22): 12         # femur
}

# Constants
SEGMENT_ID_DICT = {
    0: "background", 1: "skull", 2: "cervical vertebrae", 3: "thoracic vertebrae",
    4: "rib", 5: "sternum", 6: "collarbone", 7: "scapula", 8: "humerus",
    9: "lumbar vertebrae", 10: "sacrum", 11: "pelvis", 12: "femur"
}
HOTSPOT_ID_DICT = {0: "background", 1: "normal", 2: "abnormal"}
PIXEL_SPACING_X = 2.3975999355316
PIXEL_SPACING_Y = 2.3975999355316

EXPECTED_COLLUMNS = [
    'ratio_original_shape2D_PerimeterSurfaceRatio',
    'region_features_original_shape2D_Sphericity',
    'region_features_original_glrlm_ShortRunLowGrayLevelEmphasis',
    'region_features_original_shape2D_MaximumDiameter',
    'region_features_original_shape2D_Perimeter',
    'original_shape2D_MinorAxisLength',
    'original_glcm_Correlation',
    'ratio_original_glrlm_GrayLevelNonUniformity',
    'original_shape2D_MaximumDiameter',
    'ratio_original_glrlm_RunLengthNonUniformity',
    'original_shape2D_Perimeter',
    'original_shape2D_Sphericity',
    'ratio_original_shape2D_MinorAxisLength',
    'original_shape2D_MajorAxisLength',
    'original_glrlm_RunEntropy',
    'original_glrlm_GrayLevelNonUniformity',
    'original_shape2D_PerimeterSurfaceRatio',
    'region_features_original_glszm_SmallAreaLowGrayLevelEmphasis',
    'original_gldm_GrayLevelNonUniformity',
    'region_features_original_glszm_SmallAreaEmphasis',
    'original_shape2D_PixelSurface',
    'area_hotspot_pixel',
    'area_hotspot_mm2',
    'original_shape2D_MeshSurface',
    'ratio_original_glszm_GrayLevelNonUniformity',
    'region_features_original_gldm_LargeDependenceHighGrayLevelEmphasis',
    'region_features_original_glrlm_ShortRunEmphasis',
    'region_features_original_gldm_DependenceNonUniformity',
    'region_features_original_shape2D_MajorAxisLength',
    'region_features_original_shape2D_MinorAxisLength',
    'ratio_original_ngtdm_Strength',
    'region_features_original_glrlm_LongRunHighGrayLevelEmphasis',
    'segment_cervical vertebrae',
    'segment_collarbone',
    'segment_femur',
    'segment_humerus',
    'segment_lumbar vertebrae',
    'segment_pelvis',
    'segment_rib',
    'segment_sacrum',
    'segment_scapula',
    'segment_skull',
    'segment_sternum',
    'segment_thoracic vertebrae'
]

try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
except:
    raise Exception("Model/scaler belum ada")

extractor = featureextractor.RadiomicsFeatureExtractor()
extractor.enableAllFeatures()

def region_to_key_value(image_region_path):
    """
    Convert colored segmentation image to grayscale ID values
    Same function as backup classification
    
    Args:
        image_region_path: Path to colored segmentation PNG
        
    Returns:
        Grayscale array with ID values (0-12)
    """
    try:
        img = Image.open(image_region_path).convert('RGB')
        img_array = np.array(img)
        key_array = np.zeros(img_array.shape[:2], dtype=np.uint8)

        for color, value in KEY_VALUES.items():
            mask = np.all(img_array == color, axis=-1)
            key_array[mask] = value

        return key_array
    except Exception as e:
        print(f"[ERROR] Failed to convert colored segmentation: {e}")
        return None

def convert_colored_segmentation_if_needed(segment_path):
    """
    ✅ NEW: Convert colored segmentation to grayscale if needed and save with naming convention
    
    Args:
        segment_path: Path to segmentation file (colored or grayscale)
        
    Returns:
        Path to grayscale segmentation file
    """
    segment_path_obj = Path(segment_path)
    
    print(f"[DEBUG] Checking segmentation: {segment_path_obj.name}")
    
    # Check if this is a colored segmentation file
    if 'colored' in segment_path_obj.name and not 'grayscaledSegmentation' in segment_path_obj.name:
        print(f"[DEBUG] Detected colored segmentation, converting to grayscale...")
        
        # Generate output path: [original_name]_grayscaledSegmentation.png
        output_path = segment_path_obj.parent / f"{segment_path_obj.stem}_grayscaledSegmentation{segment_path_obj.suffix}"
        
        # Check if grayscale version already exists
        if output_path.exists():
            print(f"[DEBUG] Using existing grayscale version: {output_path.name}")
            return str(output_path)
        
        # Convert colored to grayscale using backup method
        print(f"[DEBUG] Converting colored to grayscale and saving...")
        grayscale_array = region_to_key_value(segment_path_obj)
        
        if grayscale_array is None:
            print(f"[ERROR] Failed to convert, using original path")
            return str(segment_path)
        
        # Save grayscale version for future use
        try:
            Image.fromarray(grayscale_array, mode="L").save(output_path)
            print(f"[DEBUG] Saved grayscale segmentation: {output_path.name}")
            return str(output_path)
        except Exception as e:
            print(f"[ERROR] Failed to save grayscale version: {e}")
            return str(segment_path)
    else:
        print(f"[DEBUG] Using segmentation as-is: {segment_path_obj.name}")
        return str(segment_path)

def get_exact_segment_name(segment_id):
    """
    ✅ SIMPLIFIED: Use only original 0-12 segment mapping
    
    Map segment ID to anatomical names, unknown for others
    """
    
    # Use original SEGMENT_ID_DICT for 0-12 values
    if 0 <= segment_id <= 12:
        return SEGMENT_ID_DICT[segment_id]
    
    # Everything else is unknown
    return f"unknown_segment_{segment_id}"

def loadBoundingBox2List(list_bb):
    """Data sudah dalam format yang benar dari classification_wrapper"""
    return list_bb

def findCoordinate(xmin, ymin, xmax, ymax, image_hotspot):
    """Find coordinates of non-zero pixels in bounding box"""
    arrCoor = []
    height, width = image_hotspot.shape[:2]
    for x in range(xmin, min(xmax, width)):
        for y in range(ymin, min(ymax, height)):
            if image_hotspot[y][x] != 0:
                arrCoor.append([y, x])
    return arrCoor

def findSegment(arrCoor, image_segment):
    """Find the most common segment ID in the coordinate array"""
    segmentIDArr = []
    height, width = image_segment.shape
    for y, x in arrCoor:
        if 0 <= y < height and 0 <= x < width:
            segmentIDArr.append(image_segment[y][x])
    if not segmentIDArr:
        return 0
    values, counts = np.unique(segmentIDArr, return_counts=True)
    return values[np.argmax(counts)]

def cropSegmentSpot(arrCoor, image_hotspot):
    """Crop hotspot image to show only specified coordinates"""
    image_hotspot_new = np.zeros_like(image_hotspot)
    height, width = image_hotspot.shape[:2]
    for y, x in arrCoor:
        if 0 <= y < height and 0 <= x < width:
            image_hotspot_new[y][x] = image_hotspot[y][x]
    return image_hotspot_new

def cropOnlySegment(segmentID, img_segment, img_raw):
    """Crop segment from raw image"""
    mask = (img_segment == segmentID)
    if len(img_raw.shape) == 2:
        img_segment_new = np.zeros_like(img_raw)
        img_segment_new[mask] = img_raw[mask]
    elif len(img_raw.shape) == 3 and img_raw.shape[2] == 3:
        img_segment_new = np.zeros_like(img_raw)
        for c in range(3):
            img_segment_new[:, :, c][mask] = img_raw[:, :, c][mask]
    else:
        raise ValueError("img_raw must be grayscale or RGB image")
    return img_segment_new

def to_gray(image):
    """Convert to grayscale"""
    if len(image.shape) == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image

def create_hotspot_mask(image_shape, results):
    """Create hotspot mask from results with proper coloring"""
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    
    print(f"[DEBUG] Creating hotspot mask with shape: {image_shape[:2]}")
    print(f"[DEBUG] Processing {len(results)} results")
    
    for i, result in enumerate(results):
        # ✅ FIXED: Use correct values for _HOTSPOT_PALLETTE
        if result['prediction'] == 'Abnormal':
            pixel_value = 1  # Index 1 in _HOTSPOT_PALLETTE = [255, 0, 0] (Red)
        else:
            pixel_value = 2  # Index 2 in _HOTSPOT_PALLETTE = [255, 241, 188] (Light cream)
        
        coordinates = result.get('coordinates', [])
        print(f"[DEBUG] Result {i}: {result['prediction']}, {len(coordinates)} coordinates, pixel_value={pixel_value}")
        
        for coord in coordinates:
            if len(coord) >= 2:
                y, x = coord[0], coord[1]  # coordinates are [y, x]
                if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]:
                    mask[y, x] = pixel_value
        
        print(f"[DEBUG] After processing result {i}, mask has {np.sum(mask > 0)} non-zero pixels")
    
    print(f"[DEBUG] Final mask stats: shape={mask.shape}, unique_values={np.unique(mask)}, non_zero_count={np.sum(mask > 0)}")
    return mask

def extractFeatures(image_raw, image_segment, image_hotspot, bb, file_path):
    """Extract features with FIXED EXACT segment mapping"""
    coordinate = findCoordinate(bb["xmin"], bb["ymin"], bb["xmax"], bb["ymax"], image_hotspot)
    if not coordinate:
        return None

    segmentID = findSegment(coordinate, image_segment)
    
    # ✅ FIXED: Use exact segment mapping
    segment_name = get_exact_segment_name(segmentID)
    
    print(f"[SEGMENT MAPPING] ID {segmentID} → {segment_name}")

    if segmentID == 0:
        return None

    hotspot = cropSegmentSpot(coordinate, image_hotspot)
    segment = cropOnlySegment(segmentID, image_segment, image_raw)

    gray_hotspot = to_gray(segment).astype(np.int16)
    mask_hotspot = (to_gray(hotspot) > 0).astype(np.uint8)
    mask_hotspot[mask_hotspot > 0] = 1

    area_hotspot_pixel = int(np.sum(mask_hotspot))
    area_hotspot_mm2 = area_hotspot_pixel * PIXEL_SPACING_X * PIXEL_SPACING_Y

    if np.sum(mask_hotspot) == 0:
        return None

    image_sitk_hotspot = sitk.GetImageFromArray(gray_hotspot)
    mask_sitk_hotspot = sitk.GetImageFromArray(mask_hotspot)

    try:
        all_features_hotspot = extractor.execute(image_sitk_hotspot, mask_sitk_hotspot)
    except Exception as e:
        print(f"Feature extraction failed for {file_path} (hotspot): {str(e)}")
        return None

    flattened_hotspot_features = {
        key: float(value) for key, value in all_features_hotspot.items()
        if not key.startswith('diagnostics_')
    }

    gray_segment = to_gray(segment).astype(np.int16)
    mask_segment = (image_segment == segmentID).astype(np.uint8)
    area_segment_pixel = int(np.sum(mask_segment))
    area_segment_mm2 = area_segment_pixel * PIXEL_SPACING_X * PIXEL_SPACING_Y

    if np.sum(mask_segment) == 0:
        return None

    image_sitk_segment = sitk.GetImageFromArray(gray_segment)
    mask_sitk_segment = sitk.GetImageFromArray(mask_segment)

    try:
        all_features_segment = extractor.execute(image_sitk_segment, mask_sitk_segment)
    except Exception as e:
        print(f"Feature extraction failed for {file_path} (segment): {str(e)}")
        return None

    flattened_segment_features = {
        f"region_features_{key}": float(value) for key, value in all_features_segment.items()
        if not key.startswith('diagnostics_')
    }

    ratio_features = {}
    for key in flattened_hotspot_features:
        region_key = f"region_features_{key}"
        if region_key in flattened_segment_features:
            region_value = flattened_segment_features[region_key]
            hotspot_value = flattened_hotspot_features[key]
            if isinstance(region_value, (int, float)) and region_value != 0:
                ratio = hotspot_value / region_value
            else:
                ratio = float('nan')
            ratio_features[f"ratio_{key}"] = ratio

    features = {
        "label": bb["label"],
        "xmin": bb["xmin"],
        "ymin": bb["ymin"],
        "xmax": bb["xmax"],
        "ymax": bb["ymax"],
        "segment": segment_name,
        "area_hotspot_pixel": area_hotspot_pixel,
        "area_hotspot_mm2": area_hotspot_mm2,
        "area_segment_pixel": area_segment_pixel,
        "area_segment_mm2": area_segment_mm2,
        "ratio_area_pixel": area_hotspot_pixel / area_segment_pixel if area_segment_pixel != 0 else float('nan'),
        "ratio_area_mm2": area_hotspot_mm2 / area_segment_mm2 if area_segment_mm2 != 0 else float('nan'),
        "coordinates": coordinate,
        **flattened_hotspot_features,
        **flattened_segment_features,
        **ratio_features
    }

    return features

def predict_features(features_list):
    """Predict features"""
    if not features_list:
        return []

    df = pd.DataFrame(features_list)
    df = pd.get_dummies(df, columns=["segment"])

    df = df.reindex(columns=[c for c in EXPECTED_COLLUMNS if c != "label"], fill_value=0)

    X_scaled = scaler.transform(df)
    preds = model.predict(X_scaled)
    probs = model.predict_proba(X_scaled)  # shape: (n_samples, 2)

    for f, pred, (prob_nrm, prob_abn) in zip(features_list, preds, probs):
        f.update(
            prediction='Abnormal' if pred == 1 else 'Normal',
            probability_abnormal=prob_abn,
            probability_normal=prob_nrm
        )
    return features_list

def inference_classification(path_raw, path_segment, path_hotspot, path_xml):
    """
    Main inference function - FIXED with automatic colored-to-grayscale conversion
    
    Args:
        path_raw: Path to original PNG file
        path_segment: Path to segmentation file (colored or grayscale)
        path_hotspot: Path to hotspot mask
        path_xml: List of bounding boxes or XML path
        
    Returns:
        Tuple of (results_list, classification_mask)
    """
    print(f"[INFERENCE DEBUG] Starting inference with automatic conversion")
    print(f"[INFERENCE DEBUG] Input paths:")
    print(f"  Raw: {path_raw}")
    print(f"  Segment: {path_segment}")
    print(f"  Hotspot: {path_hotspot}")
    print(f"  XML: {len(path_xml) if isinstance(path_xml, list) else path_xml}")
    
    # ✅ STEP 1: Convert colored segmentation to grayscale if needed
    converted_segment_path = convert_colored_segmentation_if_needed(path_segment)
    print(f"[INFERENCE DEBUG] Using segmentation: {Path(converted_segment_path).name}")
    
    # ✅ STEP 2: Load images using OpenCV (same as backup)
    image_raw = cv2.imread(path_raw, cv2.IMREAD_GRAYSCALE)
    image_segment = cv2.imread(converted_segment_path, cv2.IMREAD_GRAYSCALE)
    
    # Handle both array and path inputs for hotspot
    if isinstance(path_hotspot, np.ndarray):
        image_hotspot = np.squeeze(path_hotspot)
    else:
        image_hotspot = cv2.imread(str(path_hotspot), cv2.IMREAD_GRAYSCALE)
    
    # Ensure all images are 2D
    image_raw = np.squeeze(image_raw)
    image_segment = np.squeeze(image_segment)
    image_hotspot = np.squeeze(image_hotspot)
    
    print(f"[INFERENCE DEBUG] Images loaded:")
    print(f"  Raw: {image_raw.shape if image_raw is not None else 'Failed'}")
    print(f"  Segment: {image_segment.shape if image_segment is not None else 'Failed'}")
    print(f"  Hotspot: {image_hotspot.shape if image_hotspot is not None else 'Failed'}")
    
    if image_raw is None or image_segment is None or image_hotspot is None:
        print(f"[INFERENCE ERROR] Failed to load one or more images")
        return [], None
    
    # Process bounding boxes
    list_bb = loadBoundingBox2List(path_xml)
    print(f"[INFERENCE DEBUG] Loaded {len(list_bb)} bounding boxes")

    # Extract features (same processing as backup)
    list_features = []
    for i, bb in enumerate(list_bb):
        print(f"[INFERENCE DEBUG] Processing bbox {i}: {bb}")
        feature = extractFeatures(image_raw, image_segment, image_hotspot, bb, path_raw)
        if feature is None:
            print(f"[INFERENCE DEBUG] Feature extraction failed for bbox {i}")
            continue
        list_features.append(feature)
        print(f"[INFERENCE DEBUG] Feature extracted for bbox {i}: segment={feature.get('segment')}")

    if not list_features:
        print(f"[INFERENCE DEBUG] No valid features extracted")
        return [], None

    print(f"[INFERENCE DEBUG] Extracted {len(list_features)} valid features")

    # Predict (same as backup)
    try:
        results = predict_features(list_features)
        print(f"[INFERENCE DEBUG] Prediction completed: {len(results)} results")
    except Exception as e:
        print(f"[INFERENCE ERROR] Prediction failed: {e}")
        return [], None
    
    # Format output (same as backup)
    output_list = []
    for result in results:
        output_dict = {
            'bounding_box': {
                'xmin': result['xmin'],
                'ymin': result['ymin'],
                'xmax': result['xmax'],
                'ymax': result['ymax'],
            },
            'coordinates': [list(coord) for coord in result['coordinates']],
            'segment': result['segment'],
            'prediction': result['prediction'],
            'probability_abnormal': float(result['probability_abnormal']),
            'probability_normal': float(result['probability_normal']),
            'area_measurements': {
                'hotspot_pixels': result['area_hotspot_pixel'],
                'hotspot_mm2': result['area_hotspot_mm2'],
                'segment_pixels': result['area_segment_pixel'],
                'segment_mm2': result['area_segment_mm2'],
                'ratio_pixels': result['ratio_area_pixel'],
                'ratio_mm2': result['ratio_area_mm2']
            },
            'raw_features': {k: v for k, v in result.items()
                            if k not in ['xmin', 'ymin', 'xmax', 'ymax',
                                        'segment', 'label', 'prediction',
                                        'probability_abnormal', 'probability_normal',
                                        'area_hotspot_pixel', 'area_hotspot_mm2',
                                        'area_segment_pixel', 'area_segment_mm2',
                                        'ratio_area_pixel', 'ratio_area_mm2',
                                        'coordinates']}
        }
        output_list.append(output_dict)
        
    print(f"[INFERENCE DEBUG] Final output: {len(output_list)} classifications")
    
    # ✅ Create output mask with RGB format (will be converted to BGR in save function)
    if output_list:
        hotspot_mask_gray = create_hotspot_mask(image_raw.shape, output_list)
        
        # Create RGB mask (BGR conversion will happen in save function)
        h, w = hotspot_mask_gray.shape
        hotspot_mask = np.zeros((h, w, 3), dtype=np.uint8)
        
        print(f"[INFERENCE DEBUG] Creating RGB mask for BGR conversion in save")
        
        # Apply RGB colors (will be converted to BGR when saving)
        hotspot_mask[hotspot_mask_gray == 0] = [0, 0, 0]        # Black background
        hotspot_mask[hotspot_mask_gray == 1] = [255, 0, 0]      # Red for Abnormal
        hotspot_mask[hotspot_mask_gray == 2] = [255, 241, 188]  # Cream for Normal
        
        print(f"[INFERENCE DEBUG] RGB mask created - will be converted to BGR in save function")
        
    else:
        hotspot_mask = np.zeros((image_raw.shape[0], image_raw.shape[1], 3), dtype=np.uint8)
        print(f"[INFERENCE DEBUG] Created empty mask - no results")
    
    return output_list, hotspot_mask
    """
    Main inference function - FIXED with automatic colored-to-grayscale conversion
    
    Args:
        path_raw: Path to original PNG file
        path_segment: Path to segmentation file (colored or grayscale)
        path_hotspot: Path to hotspot mask
        path_xml: List of bounding boxes or XML path
        
    Returns:
        Tuple of (results_list, classification_mask)
    """
    print(f"[INFERENCE DEBUG] Starting inference with automatic conversion")
    print(f"[INFERENCE DEBUG] Input paths:")
    print(f"  Raw: {path_raw}")
    print(f"  Segment: {path_segment}")
    print(f"  Hotspot: {path_hotspot}")
    print(f"  XML: {len(path_xml) if isinstance(path_xml, list) else path_xml}")
    
    # ✅ STEP 1: Convert colored segmentation to grayscale if needed
    converted_segment_path = convert_colored_segmentation_if_needed(path_segment)
    print(f"[INFERENCE DEBUG] Using segmentation: {Path(converted_segment_path).name}")
    
    # ✅ STEP 2: Load images using OpenCV (same as backup)
    image_raw = cv2.imread(path_raw, cv2.IMREAD_GRAYSCALE)
    image_segment = cv2.imread(converted_segment_path, cv2.IMREAD_GRAYSCALE)
    
    # Handle both array and path inputs for hotspot
    if isinstance(path_hotspot, np.ndarray):
        image_hotspot = np.squeeze(path_hotspot)
    else:
        image_hotspot = cv2.imread(str(path_hotspot), cv2.IMREAD_GRAYSCALE)
    
    # Ensure all images are 2D
    image_raw = np.squeeze(image_raw)
    image_segment = np.squeeze(image_segment)
    image_hotspot = np.squeeze(image_hotspot)
    
    print(f"[INFERENCE DEBUG] Images loaded:")
    print(f"  Raw: {image_raw.shape if image_raw is not None else 'Failed'}")
    print(f"  Segment: {image_segment.shape if image_segment is not None else 'Failed'}")
    print(f"  Hotspot: {image_hotspot.shape if image_hotspot is not None else 'Failed'}")
    
    if image_raw is None or image_segment is None or image_hotspot is None:
        print(f"[INFERENCE ERROR] Failed to load one or more images")
        return [], None
    
    # Process bounding boxes
    list_bb = loadBoundingBox2List(path_xml)
    print(f"[INFERENCE DEBUG] Loaded {len(list_bb)} bounding boxes")

    # Extract features (same processing as backup)
    list_features = []
    for i, bb in enumerate(list_bb):
        print(f"[INFERENCE DEBUG] Processing bbox {i}: {bb}")
        feature = extractFeatures(image_raw, image_segment, image_hotspot, bb, path_raw)
        if feature is None:
            print(f"[INFERENCE DEBUG] Feature extraction failed for bbox {i}")
            continue
        list_features.append(feature)
        print(f"[INFERENCE DEBUG] Feature extracted for bbox {i}: segment={feature.get('segment')}")

    if not list_features:
        print(f"[INFERENCE DEBUG] No valid features extracted")
        return [], None

    print(f"[INFERENCE DEBUG] Extracted {len(list_features)} valid features")

    # Predict (same as backup)
    try:
        results = predict_features(list_features)
        print(f"[INFERENCE DEBUG] Prediction completed: {len(results)} results")
    except Exception as e:
        print(f"[INFERENCE ERROR] Prediction failed: {e}")
        return [], None
    
    # Format output (same as backup)
    output_list = []
    for result in results:
        output_dict = {
            'bounding_box': {
                'xmin': result['xmin'],
                'ymin': result['ymin'],
                'xmax': result['xmax'],
                'ymax': result['ymax'],
            },
            'coordinates': [list(coord) for coord in result['coordinates']],
            'segment': result['segment'],
            'prediction': result['prediction'],
            'probability_abnormal': float(result['probability_abnormal']),
            'probability_normal': float(result['probability_normal']),
            'area_measurements': {
                'hotspot_pixels': result['area_hotspot_pixel'],
                'hotspot_mm2': result['area_hotspot_mm2'],
                'segment_pixels': result['area_segment_pixel'],
                'segment_mm2': result['area_segment_mm2'],
                'ratio_pixels': result['ratio_area_pixel'],
                'ratio_mm2': result['ratio_area_mm2']
            },
            'raw_features': {k: v for k, v in result.items()
                            if k not in ['xmin', 'ymin', 'xmax', 'ymax',
                                        'segment', 'label', 'prediction',
                                        'probability_abnormal', 'probability_normal',
                                        'area_hotspot_pixel', 'area_hotspot_mm2',
                                        'area_segment_pixel', 'area_segment_mm2',
                                        'ratio_area_pixel', 'ratio_area_mm2',
                                        'coordinates']}
        }
        output_list.append(output_dict)
        
    print(f"[INFERENCE DEBUG] Final output: {len(output_list)} classifications")
    
def inference_classification(path_raw, path_segment, path_hotspot, path_xml):
    """
    Main inference function - FIXED with automatic colored-to-grayscale conversion
    
    Args:
        path_raw: Path to original PNG file
        path_segment: Path to segmentation file (colored or grayscale)
        path_hotspot: Path to hotspot mask
        path_xml: List of bounding boxes or XML path
        
    Returns:
        Tuple of (results_list, classification_mask)
    """
    print(f"[INFERENCE DEBUG] Starting inference with automatic conversion")
    print(f"[INFERENCE DEBUG] Input paths:")
    print(f"  Raw: {path_raw}")
    print(f"  Segment: {path_segment}")
    print(f"  Hotspot: {path_hotspot}")
    print(f"  XML: {len(path_xml) if isinstance(path_xml, list) else path_xml}")
    
    # ✅ STEP 1: Convert colored segmentation to grayscale if needed
    converted_segment_path = convert_colored_segmentation_if_needed(path_segment)
    print(f"[INFERENCE DEBUG] Using segmentation: {Path(converted_segment_path).name}")
    
    # ✅ STEP 2: Load images using OpenCV (same as backup)
    image_raw = cv2.imread(path_raw, cv2.IMREAD_GRAYSCALE)
    image_segment = cv2.imread(converted_segment_path, cv2.IMREAD_GRAYSCALE)
    
    # Handle both array and path inputs for hotspot
    if isinstance(path_hotspot, np.ndarray):
        image_hotspot = np.squeeze(path_hotspot)
    else:
        image_hotspot = cv2.imread(str(path_hotspot), cv2.IMREAD_GRAYSCALE)
    
    # Ensure all images are 2D
    image_raw = np.squeeze(image_raw)
    image_segment = np.squeeze(image_segment)
    image_hotspot = np.squeeze(image_hotspot)
    
    print(f"[INFERENCE DEBUG] Images loaded:")
    print(f"  Raw: {image_raw.shape if image_raw is not None else 'Failed'}")
    print(f"  Segment: {image_segment.shape if image_segment is not None else 'Failed'}")
    print(f"  Hotspot: {image_hotspot.shape if image_hotspot is not None else 'Failed'}")
    
    if image_raw is None or image_segment is None or image_hotspot is None:
        print(f"[INFERENCE ERROR] Failed to load one or more images")
        return [], None
    
    # Process bounding boxes
    list_bb = loadBoundingBox2List(path_xml)
    print(f"[INFERENCE DEBUG] Loaded {len(list_bb)} bounding boxes")

    # Extract features (same processing as backup)
    list_features = []
    for i, bb in enumerate(list_bb):
        print(f"[INFERENCE DEBUG] Processing bbox {i}: {bb}")
        feature = extractFeatures(image_raw, image_segment, image_hotspot, bb, path_raw)
        if feature is None:
            print(f"[INFERENCE DEBUG] Feature extraction failed for bbox {i}")
            continue
        list_features.append(feature)
        print(f"[INFERENCE DEBUG] Feature extracted for bbox {i}: segment={feature.get('segment')}")

    if not list_features:
        print(f"[INFERENCE DEBUG] No valid features extracted")
        return [], None

    print(f"[INFERENCE DEBUG] Extracted {len(list_features)} valid features")

    # Predict (same as backup)
    try:
        results = predict_features(list_features)
        print(f"[INFERENCE DEBUG] Prediction completed: {len(results)} results")
    except Exception as e:
        print(f"[INFERENCE ERROR] Prediction failed: {e}")
        return [], None
    
    # Format output (same as backup)
    output_list = []
    for result in results:
        output_dict = {
            'bounding_box': {
                'xmin': result['xmin'],
                'ymin': result['ymin'],
                'xmax': result['xmax'],
                'ymax': result['ymax'],
            },
            'coordinates': [list(coord) for coord in result['coordinates']],
            'segment': result['segment'],
            'prediction': result['prediction'],
            'probability_abnormal': float(result['probability_abnormal']),
            'probability_normal': float(result['probability_normal']),
            'area_measurements': {
                'hotspot_pixels': result['area_hotspot_pixel'],
                'hotspot_mm2': result['area_hotspot_mm2'],
                'segment_pixels': result['area_segment_pixel'],
                'segment_mm2': result['area_segment_mm2'],
                'ratio_pixels': result['ratio_area_pixel'],
                'ratio_mm2': result['ratio_area_mm2']
            },
            'raw_features': {k: v for k, v in result.items()
                            if k not in ['xmin', 'ymin', 'xmax', 'ymax',
                                        'segment', 'label', 'prediction',
                                        'probability_abnormal', 'probability_normal',
                                        'area_hotspot_pixel', 'area_hotspot_mm2',
                                        'area_segment_pixel', 'area_segment_mm2',
                                        'ratio_area_pixel', 'ratio_area_mm2',
                                        'coordinates']}
        }
        output_list.append(output_dict)
        
    print(f"[INFERENCE DEBUG] Final output: {len(output_list)} classifications")
    
    # ✅ Create output mask with RGB format for PIL save
    if output_list:
        hotspot_mask_gray = create_hotspot_mask(image_raw.shape, output_list)
        
        # Create RGB mask for PIL save
        h, w = hotspot_mask_gray.shape
        hotspot_mask = np.zeros((h, w, 3), dtype=np.uint8)
        
        print(f"[INFERENCE DEBUG] Creating RGB mask for PIL save")
        
        # Apply RGB colors (PIL will preserve RGB order)
        hotspot_mask[hotspot_mask_gray == 0] = [0, 0, 0]        # Black background
        hotspot_mask[hotspot_mask_gray == 1] = [255, 0, 0]      # Red for Abnormal
        hotspot_mask[hotspot_mask_gray == 2] = [255, 241, 188]  # Cream for Normal
        
        print(f"[INFERENCE DEBUG] RGB mask created - PIL will preserve colors correctly")
        
    else:
        hotspot_mask = np.zeros((image_raw.shape[0], image_raw.shape[1], 3), dtype=np.uint8)
        print(f"[INFERENCE DEBUG] Created empty mask - no results")
    
    return output_list, hotspot_mask