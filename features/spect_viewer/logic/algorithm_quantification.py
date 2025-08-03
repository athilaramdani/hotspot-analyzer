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
    1: (0, 255, 0),
    2: (255, 0, 0)
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
    image = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(f"Could not load image: {path}")
    return image

def calculate_BSI(image_segment_anterior, image_segment_posterior, image_hotspot_anterior, image_hotspot_posterior):
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

def process_single_quantification(path_seg_ant, path_seg_pos, path_hs_ant, path_hs_pos, path_result):
    seg_ant = load_image_as_array(path_seg_ant)
    seg_pos = load_image_as_array(path_seg_pos)
    hot_ant = load_image_as_array(path_hs_ant)
    hot_pos = load_image_as_array(path_hs_pos)

    bsi_result = calculate_BSI(seg_ant, seg_pos, hot_ant, hot_pos)
    np.save(path_result, bsi_result)