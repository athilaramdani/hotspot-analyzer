# features/spect_viewer/logic/algorithm_quantification.py
# FIXED: V1.2 algorithm with corrected BSI calculation (no multiply by 100)
# Uses old calculation logic but maintains new JSON format structure
# Supports left-right separation and dual-view analysis

import cv2
import numpy as np
import matplotlib.pyplot as plt

#   V1.2 COLOR PALETTES (unchanged)
PALETTE_UNSEPARATED = {
    (0, 0, 0): 'background',
    (176, 230, 13): 'skull',
    (0, 151, 219): 'cervical vertebrae',
    (126, 230, 225): 'thoracic vertebrae',
    (166, 55, 167): 'rib',
    (230, 157, 180): 'sternum',
    (167, 110, 77): 'collarbone',
    (121, 0, 24): 'scapula',
    (56, 65, 184): 'humerus',
    (230, 218, 0): 'lumbar vertebrae',
    (230, 114, 35): 'sacrum',
    (12, 187, 62): 'pelvis',
    (230, 182, 22): 'femur'
}

PALETTE_SEPARATED = {
    (0, 0, 0): 'background',
    (13, 230, 176): 'skull',
    (219, 151, 0): 'cervical vertebrae',
    (225, 230, 126): 'thoracic vertebrae',
    (120, 20, 120): 'rib left',
    (200, 80, 200): 'rib right',
    (180, 157, 230): 'sternum',
    (40, 70, 120): 'clavicle left',
    (100, 140, 200): 'clavicle right',
    (15, 0, 80): 'scapula left',
    (35, 0, 160): 'scapula right',
    (140, 40, 30): 'humerus left',
    (220, 90, 80): 'humerus right',
    (0, 218, 230): 'lumbar vertebrae',
    (35, 114, 230): 'sacrum',
    (62, 187, 12): 'pelvis',
    (10, 140, 180): 'femur left',
    (40, 200, 250): 'femur right',
}

def separate_left_right_components(image, bones_to_separate=None, color_shift=50):
    if bones_to_separate is None:
        bones_to_separate = {}
        unique_colors = get_unique_colors(image)
        
        for color in unique_colors:
            if not np.array_equal(color, [0, 0, 0]):
                left_color = generate_shifted_color(color, -color_shift)
                right_color = generate_shifted_color(color, color_shift)
                bones_to_separate[tuple(color)] = (tuple(left_color), tuple(right_color))
    
    h, w, _ = image.shape
    center_x = w // 2
    separated = image.copy()
    component_info = {}
    color_parts = {}
    pixel_counts = {}
    bone_regions = {}
    
    for original_color in get_unique_colors(image):
        original_color_tuple = tuple(int(c) for c in original_color)
        color_mask = create_color_mask(image, original_color)
        pixel_count = int(np.sum(color_mask))
        
        if pixel_count == 0:
            continue
            
        pixel_counts[original_color_tuple] = pixel_count
        bone_name = PALETTE_UNSEPARATED.get(original_color_tuple, f'unknown_{original_color_tuple}')
        
        if original_color_tuple in bones_to_separate:
            left_color, right_color = bones_to_separate[original_color_tuple]
            
            components = cv2.connectedComponentsWithStats(
                color_mask.astype(np.uint8), 
                connectivity=8
            )
            num_labels, labels, stats, centroids = components
            
            if num_labels <= 2:
                color_parts[original_color_tuple] = 'single'
                bone_regions[bone_name] = pixel_count
            else:
                color_parts[original_color_tuple] = 'separated'
                left_pixels_total = 0
                right_pixels_total = 0
                
                for i in range(1, num_labels):
                    component_mask = (labels == i)
                    
                    component_pixels = np.where(component_mask)
                    x_coords = component_pixels[1]
                    
                    centroid_x = np.mean(x_coords)
                    #   FIX: Correct spatial mapping - left is right side of image
                    is_left = centroid_x > center_x  # Left anatomical = right side of image
                    
                    left_pixels = np.sum(x_coords < center_x)
                    right_pixels = np.sum(x_coords >= center_x)
                    side_ratio = left_pixels / (left_pixels + right_pixels) if (left_pixels + right_pixels) > 0 else 0
                    
                    if is_left or side_ratio > 0.5:
                        separated[component_mask] = left_color
                        side = 'left'
                        left_pixels_total += stats[i][cv2.CC_STAT_AREA]
                    else:
                        separated[component_mask] = right_color
                        side = 'right'
                        right_pixels_total += stats[i][cv2.CC_STAT_AREA]
                    
                    component_info[f"{original_color_tuple}_{i}"] = {
                        'original_color': tuple(int(c) for c in original_color_tuple),
                        'assigned_color': left_color if side == 'left' else right_color,
                        'side': side,
                        'centroid': (float(centroid_x), float(centroids[i][1])),
                        'area': int(stats[i][cv2.CC_STAT_AREA]),
                        'bbox': (int(stats[i][cv2.CC_STAT_LEFT]), int(stats[i][cv2.CC_STAT_TOP]), 
                                int(stats[i][cv2.CC_STAT_WIDTH]), int(stats[i][cv2.CC_STAT_HEIGHT])),
                        'side_ratio': float(side_ratio)
                    }
                
                if left_pixels_total > 0:
                    bone_regions[f'left {bone_name}'] = left_pixels_total
                if right_pixels_total > 0:
                    bone_regions[f'right {bone_name}'] = right_pixels_total
        else:
            color_parts[original_color_tuple] = 'single'
            bone_regions[bone_name] = pixel_count
    
    return separated, component_info, color_parts, pixel_counts, bone_regions

def get_unique_colors(image):
    reshaped = image.reshape(-1, 3)
    unique_colors = np.unique(reshaped, axis=0)
    return unique_colors

def create_color_mask(image, target_color, tolerance=2):
    return np.all(np.abs(image - np.array(target_color)) <= tolerance, axis=-1)

def generate_shifted_color(original_color, shift_amount):
    shifted = np.array(original_color) + shift_amount
    shifted = np.clip(shifted, 0, 255)
    return shifted.astype(np.uint8)

def process_image_with_predefined_colors(image_path, bones_to_separate=None):
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"Could not load image from {image_path}")
    
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    if bones_to_separate is None:
        bones_to_separate = {
            (166, 55, 167): ((120, 20, 120), (200, 80, 200)),
            (167, 110, 77): ((120, 70, 40), (200, 140, 100)),
            (121, 0, 24): ((80, 0, 15), (160, 0, 35)),
            (56, 65, 184): ((30, 40, 140), (80, 90, 220)),
            (230, 182, 22): ((180, 140, 10), (250, 200, 40)),
        }
    
    separated, component_info, color_parts, pixel_counts, bone_regions = separate_left_right_components(
        image_rgb, 
        bones_to_separate=bones_to_separate
    )
    
    return separated, component_info, bone_regions

def calculate_pixel_bsi_v2(image_region_path, image_hs_path, tolerance=2):
    """
      FIXED V1.2 BSI calculation 
    - Uses old algorithm logic (green for benign detection)
    - Returns BSI as decimal (not percentage)
    - Maintains new JSON format structure
    """
    image_region, info, bone_regions = process_image_with_predefined_colors(image_region_path)
    image_hs = cv2.imread(image_hs_path)

    if image_region is None or image_hs is None:
        raise ValueError("One of the images could not be loaded.")
    
    image_region = cv2.cvtColor(image_region, cv2.COLOR_BGR2RGB)
    image_hs = cv2.cvtColor(image_hs, cv2.COLOR_BGR2RGB)
    
    region_pixel_counts = {}
    region_malignant_counts = {}
    region_benign_counts = {}
    region_stats = {}
    
    total_malignant = 0
    total_benign = 0
    
    for color, region_name in PALETTE_SEPARATED.items():
        if region_name == 'background':
            continue
        mask_region = np.all(np.abs(image_region - np.array(color)) <= tolerance, axis=-1)
        pixel_count = int(np.sum(mask_region))
        region_pixel_counts[region_name] = pixel_count
        
        #   FIXED: Use old algorithm's green color for benign detection
        mask_malignant = np.all(np.abs(image_hs - np.array([255, 0, 0])) <= tolerance, axis=-1) & mask_region
        mask_benign = np.all(np.abs(image_hs - np.array([255, 241, 188])) <= tolerance, axis=-1) & mask_region
        
        malignant_count = int(np.sum(mask_malignant))
        benign_count = int(np.sum(mask_benign))
        
        region_malignant_counts[region_name] = malignant_count
        region_benign_counts[region_name] = benign_count
        
        total_malignant += malignant_count
        total_benign += benign_count
        
        region_stats[region_name] = {
            "total_pixels": pixel_count,
            "malignant_pixels": malignant_count,
            "benign_pixels": benign_count,
            "malignant_ratio": malignant_count / pixel_count if pixel_count > 0 else 0,
            "benign_ratio": benign_count / pixel_count if pixel_count > 0 else 0
        }
    
    #   FIXED: Calculate BSI correctly (sum of malignant ratios, not percentage)
    bsi_score = sum(stats['malignant_ratio'] for stats in region_stats.values())
    
    #   FIXED: Calculate actual percentages for total pixels
    total_pixels = sum(region_pixel_counts.values())
    malignant_percentage = (total_malignant / total_pixels * 100) if total_pixels > 0 else 0
    benign_percentage = (total_benign / total_pixels * 100) if total_pixels > 0 else 0
    
    return {
        "region_total_pixels": region_pixel_counts,
        "region_malignant_pixels": region_malignant_counts,
        "region_benign_pixels": region_benign_counts,
        "total_malignant_pixels": total_malignant,
        "total_benign_pixels": total_benign,
        "region_stats": region_stats,
        #   NEW: Add summary statistics with correct BSI calculation
        "summary_statistics": {
            "bsi_score": bsi_score,  #   FIXED: This should be ~2.37, not ~236.97
            "total_malignant_pixels": total_malignant,
            "total_benign_pixels": total_benign,
            "total_pixels": total_pixels,
            "malignant_percentage": malignant_percentage,  #   FIXED: Actual percentage of total pixels
            "benign_percentage": benign_percentage
        }
    }

def calculate_combined_bsi_v2(anterior_results, posterior_results):
    """
      Calculate combined BSI using team-approved formula: (anterior + posterior) / 2
    """
    anterior_bsi = anterior_results['summary_statistics']['bsi_score']
    posterior_bsi = posterior_results['summary_statistics']['bsi_score']
    
    #   Team-approved formula
    combined_bsi = (anterior_bsi + posterior_bsi) / 2
    
    return {
        "anterior_bsi": anterior_bsi,
        "posterior_bsi": posterior_bsi, 
        "combined_bsi": combined_bsi,
        "anterior_details": anterior_results,
        "posterior_details": posterior_results
    }

#   USAGE EXAMPLE:
def generate_json_format(image_region_path, image_hs_path, patient_id, study_date, view="anterior"):
    """
    Generate JSON output with new format but correct BSI calculation
    """
    results = calculate_pixel_bsi_v2(image_region_path, image_hs_path)
    
    # Extract filename from path
    import os
    filename_stem = f"{patient_id}_{study_date}"
    
    output = {
        "patient_info": {
            "patient_id": patient_id,
            "study_date": study_date,
            "filename_stem": filename_stem,
            "quantification_method": "BSI_v1.2_color_based_separate_views",
            "view": view,
            "input_files": {
                "segmentation": os.path.basename(image_region_path),
                "hotspot": os.path.basename(image_hs_path)
            }
        },
        "bsi_results": results["region_stats"],
        "summary_statistics": {
            "view": view,
            "bsi_score": results["summary_statistics"]["bsi_score"],  #   Now correct: ~2.37
            "total_malignant_pixels": results["summary_statistics"]["total_malignant_pixels"],
            "total_benign_pixels": results["summary_statistics"]["total_benign_pixels"],
            "total_pixels": results["summary_statistics"]["total_pixels"],
            "malignant_percentage": results["summary_statistics"]["malignant_percentage"],  #   Real percentage
            "benign_percentage": results["summary_statistics"]["benign_percentage"]
        }
    }
    
    return output

# Example usage:
# result = generate_fixed_json_format(
#     "path/to/anterior_region.png",
#     "path/to/anterior_hotspot.png", 
#     "0001573732",
#     "20250108",
#     "anterior"
# )