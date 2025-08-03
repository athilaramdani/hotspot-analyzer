# backupclassificationreference.py
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
from PIL import image

# Path
PATH_MAIN = "D:/penelitian/Pipeline/models"
MODEL_PATH = PATH_MAIN + "/model_classification_hs_xgboost_250724.pkl"
SCALER_PATH = PATH_MAIN + "/scaler_classification_32features.pkl"

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
    (230, 182, 22): 12         # Âfemur
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

def loadBoundingBox2List(list_bb):
    bboxes = []
    for bbox in list_bb:
        x_min, y_min, x_max, y_max = map(int, bbox['bbox'])
        label = bbox['label']
        bboxes.append({
            "label": label,
            "xmin": x_min,
            "ymin": y_min,
            "xmax": x_max,
            "ymax": y_max
        })
    return bboxes

def findCoordinate(xmin, ymin, xmax, ymax, image_hotspot):
    arrCoor = []
    height, width = image_hotspot.shape[:2]
    for x in range(xmin, min(xmax, width)):
        for y in range(ymin, min(ymax, height)):
            if image_hotspot[y][x] != 0:
                arrCoor.append([y, x])
    return arrCoor

def findSegment(arrCoor, image_segment):
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
    image_hotspot_new = np.zeros_like(image_hotspot)
    height, width = image_hotspot.shape[:2]
    for y, x in arrCoor:
        if 0 <= y < height and 0 <= x < width:
            image_hotspot_new[y][x] = image_hotspot[y][x]
    return image_hotspot_new

def cropOnlySegment(segmentID, img_segment, img_raw):
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
    if len(image.shape) == 3 and image.shape[2] == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image

def create_hotspot_mask(image_shape, results):
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    
    for result in results:
        pixel_value = 2 if result['prediction'] == 'Abnormal' else 1
        
        for y, x in result['coordinates']:
            if 0 <= y < mask.shape[0] and 0 <= x < mask.shape[1]:
                mask[y, x] = pixel_value
                
    return mask

def extractFeatures(image_raw, image_segment, image_hotspot, bb, file_path):
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

def process_new_image(raw_path, segment_path, hotspot_path, xml_path):
    images = [cv2.imread(p, cv2.IMREAD_GRAYSCALE) for p in [raw_path, segment_path, hotspot_path]]
    list_bb = loadBoundingBox2List(xml_path)
    return [f for bb in list_bb if (f := extractFeatures(*images, bb, raw_path))]

def predict_features(features_list):
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

def region_to_key_value(image_region_path):
    img = image.open(image_region_path).convert('RGB')
    img_array = np.array(img)
    key_array = np.zeros(img_array.shape[:2], dtype=np.uint8)

    for color, value in KEY_VALUES.items():
        mask = np.all(img_array == color, axis=-1)
        key_array[mask] = value

    return key_array

def inference_classification(path_raw, path_segment, path_hotspot, path_xml):
    image_raw = cv2.imread(path_raw, cv2.IMREAD_GRAYSCALE)
    image_segment = region_to_key_value(path_segment)
    image_hotspot = cv2.imread(path_hotspot, cv2.IMREAD_GRAYSCALE)
    list_bb = loadBoundingBox2List(path_xml)

    list_features = []
    for bb in list_bb:
        feature = extractFeatures(image_raw, image_segment, image_hotspot, bb, path_raw)
        if feature is None:
            continue
        list_features.append(feature)

    if not list_features:
        return []

    results = predict_features(list_features)
    
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
        
    hotspot_mask_gray = create_hotspot_mask(image_raw.shape, output_list)
    hotspot_mask= cv2.cvtColor(hotspot_mask_gray, cv2.COLOR_GRAY2BGR)
    
    return output_list, hotspot_mask