# features\spect_viewer\logic\inference_classification_hs.py - FIXED to match backup preprocessing
# Preliminaries
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

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from core.config.paths import CLASSIFICATION_XGBOOST_MODEL, CLASSIFICATION_SCALER_MODEL

# Kemudian gunakan:
MODEL_PATH = str(CLASSIFICATION_XGBOOST_MODEL)
SCALER_PATH = str(CLASSIFICATION_SCALER_MODEL)

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

def loadBoundingBox2List(list_bb):
    """Data sudah dalam format yang benar dari classification_wrapper"""
    return list_bb

def findCoordinate(xmin, ymin, xmax, ymax, image_hotspot):
    """Find coordinates of non-zero pixels in bounding box - EXACT SAME AS BACKUP with DEBUG"""
    arrCoor = []
    height, width = image_hotspot.shape[:2]
    
    print(f"[COORD DEBUG] Image size: {width}x{height}")
    print(f"[COORD DEBUG] Bounding box: ({xmin},{ymin}) to ({xmax},{ymax})")
    
    # Check if bounding box is within image bounds
    if xmin >= width or ymin >= height or xmax <= 0 or ymax <= 0:
        print(f"[COORD DEBUG] FAILED: Bounding box completely outside image bounds")
        return arrCoor
    
    # Count pixels in bounding box
    total_pixels = 0
    non_zero_pixels = 0
    pixel_values = []
    
    for x in range(xmin, min(xmax, width)):
        for y in range(ymin, min(ymax, height)):
            total_pixels += 1
            pixel_value = image_hotspot[y][x]
            pixel_values.append(pixel_value)
            if pixel_value != 0:
                arrCoor.append([y, x])
                non_zero_pixels += 1
    
    print(f"[COORD DEBUG] Total pixels checked: {total_pixels}")
    print(f"[COORD DEBUG] Non-zero pixels found: {non_zero_pixels}")
    print(f"[COORD DEBUG] Unique pixel values: {sorted(set(pixel_values))}")
    print(f"[COORD DEBUG] Min/Max pixel values: {min(pixel_values) if pixel_values else 'N/A'} / {max(pixel_values) if pixel_values else 'N/A'}")
    
    return arrCoor

def findSegment(arrCoor, image_segment):
    """Find the most common segment ID in the coordinate array - EXACT SAME AS BACKUP with DEBUG"""
    segmentIDArr = []
    height, width = image_segment.shape
    
    print(f"[SEGMENT DEBUG] Processing {len(arrCoor)} coordinates")
    print(f"[SEGMENT DEBUG] Segment image size: {width}x{height}")
    
    for y, x in arrCoor:
        if 0 <= y < height and 0 <= x < width:
            segment_id = image_segment[y][x]
            segmentIDArr.append(segment_id)
    
    if not segmentIDArr:
        print(f"[SEGMENT DEBUG] FAILED: No valid segment IDs found")
        return 0
    
    values, counts = np.unique(segmentIDArr, return_counts=True)
    most_common_id = values[np.argmax(counts)]
    
    print(f"[SEGMENT DEBUG] Segment IDs found: {dict(zip(values, counts))}")
    print(f"[SEGMENT DEBUG] Most common segment ID: {most_common_id}")
    print(f"[SEGMENT DEBUG] Segment name: {SEGMENT_ID_DICT.get(most_common_id, 'unknown')}")
    
    return most_common_id

def cropSegmentSpot(arrCoor, image_hotspot):
    """Crop hotspot image to show only specified coordinates - EXACT SAME AS BACKUP"""
    image_hotspot_new = np.zeros_like(image_hotspot)
    height, width = image_hotspot.shape[:2]
    for y, x in arrCoor:
        if 0 <= y < height and 0 <= x < width:
            image_hotspot_new[y][x] = image_hotspot[y][x]
    return image_hotspot_new

def cropOnlySegment(segmentID, img_segment, img_raw):
    """Crop segment from raw image - EXACT SAME AS BACKUP"""
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
    """Convert to grayscale - EXACT SAME AS BACKUP"""
    if len(image.shape) == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image

def create_hotspot_mask(image_shape, results):
    """Create hotspot mask from results - EXACT SAME AS BACKUP"""
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    
    for result in results:
        pixel_value = 2 if result['prediction'] == 'Abnormal' else 1
        
        for y, x in result['coordinates']:
            if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]:
                mask[y, x] = pixel_value
                
    return mask

def extractFeatures(image_raw, image_segment, image_hotspot, bb, file_path):
    """Extract features - EXACT SAME AS BACKUP"""
    coordinate = findCoordinate(bb["xmin"], bb["ymin"], bb["xmax"], bb["ymax"], image_hotspot)
    if not coordinate:
        return None

    segmentID = findSegment(coordinate, image_segment)
    segment_name = SEGMENT_ID_DICT.get(segmentID, "unknown")

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
    """Predict features - EXACT SAME AS BACKUP"""
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
    Main inference function - FIXED to use PNG files with same preprocessing as backup
    """
    print(f"[INFERENCE DEBUG] Starting inference with PNG files")
    print(f"[INFERENCE DEBUG] Input paths:")
    print(f"  Raw: {path_raw}")
    print(f"  Segment: {path_segment}")
    print(f"  Hotspot: {path_hotspot}")
    print(f"  XML: {len(path_xml) if isinstance(path_xml, list) else path_xml}")
    
    # ✅ FIXED: Use simple OpenCV loading like backup - NO SMART LOADING
    # Load images using exact same method as backup classification
    image_raw = cv2.imread(path_raw, cv2.IMREAD_GRAYSCALE)
    image_segment = cv2.imread(path_segment, cv2.IMREAD_GRAYSCALE)
    
    # Handle both array and path inputs for hotspot (same as backup)
    if isinstance(path_hotspot, np.ndarray):
        image_hotspot = np.squeeze(path_hotspot)
    else:
        image_hotspot = cv2.imread(str(path_hotspot), cv2.IMREAD_GRAYSCALE)
    
    # Ensure all images are 2D (same as backup)
    image_raw = np.squeeze(image_raw)
    image_segment = np.squeeze(image_segment)
    image_hotspot = np.squeeze(image_hotspot)
    
    print(f"[INFERENCE DEBUG] Images loaded using OpenCV (same as backup):")
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
    
    # Create output mask (same as backup)
    if output_list:
        hotspot_mask_gray = create_hotspot_mask(image_raw.shape, output_list)
        hotspot_mask = cv2.cvtColor(hotspot_mask_gray, cv2.COLOR_GRAY2BGR)
    else:
        hotspot_mask = np.zeros((image_raw.shape[0], image_raw.shape[1], 3), dtype=np.uint8)
    
    return output_list, hotspot_mask