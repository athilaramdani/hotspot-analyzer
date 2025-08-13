# features/spect_viewer/logic/quantification_wrapper.py - UPDATED for V1.2 Algorithm

import numpy as np
import cv2
from pathlib import Path
import json
from core.logger import _log
from core.config.paths import (
    get_classification_files, 
    get_quantification_files,
    get_segmentation_files_with_edited
)

# Import V1.2 algorithm
from .algorithm_quantification import (
    calculate_pixel_bsi_v2,
    calculate_combined_bsi_v2,
    process_image_with_predefined_colors
)

def get_quantification_input_paths_v2(patient_folder: Path, filename_stem: str) -> dict:
    """Get input file paths for V1.2 quantification (separate anterior/posterior)"""
    
    # Get classification files (for hotspot data)
    ant_clf_files = get_classification_files(patient_folder, filename_stem, "anterior")
    post_clf_files = get_classification_files(patient_folder, filename_stem, "posterior")
    
    # Get segmentation files (for region data) - prioritize edited
    ant_seg_files = get_segmentation_files_with_edited(patient_folder, filename_stem, "anterior")
    post_seg_files = get_segmentation_files_with_edited(patient_folder, filename_stem, "posterior")
    
    # ✅ FIXED: Use classification_mask.png (not hotspot_colored.png)
    ant_mask_to_use = ant_clf_files['mask_edited'] if ant_clf_files['mask_edited'].exists() else ant_clf_files['mask_original']
    post_mask_to_use = post_clf_files['mask_edited'] if post_clf_files['mask_edited'].exists() else post_clf_files['mask_original']
    
    # ✅ Use colored segmentation (for region detection)
    ant_seg_to_use = ant_seg_files['png_colored_edited'] if ant_seg_files['png_colored_edited'].exists() else ant_seg_files['png_colored']
    post_seg_to_use = post_seg_files['png_colored_edited'] if post_seg_files['png_colored_edited'].exists() else post_seg_files['png_colored']
    
    return {
        # Input files
        'segmentation_anterior': ant_seg_to_use,
        'segmentation_posterior': post_seg_to_use,
        'hotspot_anterior': ant_mask_to_use,
        'hotspot_posterior': post_mask_to_use,
        
        # Output files (separate for each view)
        'output_anterior': patient_folder / f"{filename_stem}_bsi_quantification_anterior.json",
        'output_posterior': patient_folder / f"{filename_stem}_bsi_quantification_posterior.json"
    }

def check_available_files_v2(paths):
    """Check file availability for V1.2 quantification"""
    available_paths = {}
    missing_files = []
    
    required_files = [
        'segmentation_anterior', 'hotspot_anterior',
        'segmentation_posterior', 'hotspot_posterior'
    ]
    
    for name in required_files:
        path = paths[name]
        if path.exists():
            available_paths[name] = path
        else:
            missing_files.append(f"{name} ({path.name})")
    
    # Need both anterior and posterior pairs
    has_anterior_pair = ('segmentation_anterior' in available_paths and 
                        'hotspot_anterior' in available_paths)
    has_posterior_pair = ('segmentation_posterior' in available_paths and 
                         'hotspot_posterior' in available_paths)
    
    can_proceed = has_anterior_pair and has_posterior_pair
    
    return available_paths, missing_files, can_proceed

def run_quantification_for_patient_v2(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    ✅ Run V1.2 BSI quantification - separate anterior/posterior processing
    """
    try:
        patient_folder = dicom_path.parent
        filename_stem = f"{patient_id}_{study_date}"
        
        _log(f"     Starting V1.2 BSI quantification for patient {patient_id}")
        _log(f"     New workflow: Color-based segmentation + Separate view processing")
        
        # Get file paths
        paths = get_quantification_input_paths_v2(patient_folder, filename_stem)
        
        # Check available files
        available_paths, missing_files, can_proceed = check_available_files_v2(paths)
        
        if not can_proceed:
            _log(f"     Cannot proceed with V1.2 quantification. Missing files: {', '.join(missing_files)}")
            _log(f"     Need both anterior and posterior segmentation + classification pairs")
            return False
        
        if missing_files:
            _log(f"     [WARNING] Some files missing: {', '.join(missing_files)}")
        
        _log(f"     Processing V1.2 quantification with color-based segmentation...")
        
        # ✅ Process anterior view
        _log(f"     Processing anterior view...")
        anterior_results = calculate_pixel_bsi_v2(
            str(available_paths['segmentation_anterior']),
            str(available_paths['hotspot_anterior'])
        )
        
        # ✅ Process posterior view
        _log(f"     Processing posterior view...")
        posterior_results = calculate_pixel_bsi_v2(
            str(available_paths['segmentation_posterior']),
            str(available_paths['hotspot_posterior'])
        )
        
        # ✅ Calculate combined BSI using team-approved formula
        _log(f"     Calculating combined BSI...")
        combined_results = calculate_combined_bsi_v2(anterior_results, posterior_results)

        # ✅ DEBUG: Log individual BSI values
        ant_bsi_raw = sum(stats['malignant_ratio'] for stats in anterior_results['region_stats'].values())
        post_bsi_raw = sum(stats['malignant_ratio'] for stats in posterior_results['region_stats'].values()) 
        print(f"[BSI DEBUG] Raw anterior BSI sum: {ant_bsi_raw}")
        print(f"[BSI DEBUG] Raw posterior BSI sum: {post_bsi_raw}")
        print(f"[BSI DEBUG] Combined BSI: {(ant_bsi_raw + post_bsi_raw) / 2}")
                
        # ✅ Prepare metadata
        base_metadata = {
            "patient_id": patient_id,
            "study_date": study_date,
            "filename_stem": filename_stem,
            "quantification_method": "BSI_v1.2_color_based_separate_views",
            "algorithm_version": "1.2"
        }
        
        # ✅ Save anterior results
        anterior_final = {
            "patient_info": {
                **base_metadata,
                "view": "anterior",
                "input_files": {
                    "segmentation": available_paths['segmentation_anterior'].name,
                    "hotspot": available_paths['hotspot_anterior'].name
                }
            },
            "bsi_results": anterior_results["region_stats"],
            "summary_statistics": {
                "view": "anterior",
                "bsi_score": combined_results["anterior_bsi"], 
                "total_malignant_pixels": anterior_results["total_malignant_pixels"],
                "total_benign_pixels": anterior_results["total_benign_pixels"],
                "total_pixels": sum(anterior_results["region_total_pixels"].values()),
                "malignant_percentage": combined_results["anterior_bsi"],
                "benign_percentage": (sum(anterior_results["region_benign_pixels"].values()) / 
                                    sum(anterior_results["region_total_pixels"].values()) * 100) if sum(anterior_results["region_total_pixels"].values()) > 0 else 0
            }
        }
        
        # ✅ Save posterior results
        posterior_final = {
            "patient_info": {
                **base_metadata,
                "view": "posterior",
                "input_files": {
                    "segmentation": available_paths['segmentation_posterior'].name,
                    "hotspot": available_paths['hotspot_posterior'].name
                }
            },
            "bsi_results": posterior_results["region_stats"],
            "summary_statistics": {
                "view": "posterior",
                "bsi_score": combined_results["posterior_bsi"],
                "total_malignant_pixels": posterior_results["total_malignant_pixels"],
                "total_benign_pixels": posterior_results["total_benign_pixels"],
                "total_pixels": sum(posterior_results["region_total_pixels"].values()),
                "malignant_percentage": combined_results["posterior_bsi"],
                "benign_percentage": (sum(posterior_results["region_benign_pixels"].values()) / 
                                    sum(posterior_results["region_total_pixels"].values()) * 100) if sum(posterior_results["region_total_pixels"].values()) > 0 else 0
            }
        }
        
        # ✅ Write separate JSON files
        with open(paths['output_anterior'], 'w') as f:
            json.dump(anterior_final, f, indent=2)
            
        with open(paths['output_posterior'], 'w') as f:
            json.dump(posterior_final, f, indent=2)
        
        _log(f"     ✅ V1.2 BSI quantification completed")
        _log(f"     Anterior BSI: {combined_results['anterior_bsi'] * 100:.2f}%")
        _log(f"     Posterior BSI: {combined_results['posterior_bsi'] * 100:.2f}%") 
        _log(f"     Combined BSI: {combined_results['combined_bsi'] * 100:.2f}%")
        _log(f"     Results saved: {paths['output_anterior'].name}, {paths['output_posterior'].name}")
        
        return True
        
    except Exception as e:
        _log(f"     V1.2 Quantification error for patient {patient_id}: {e}")
        import traceback
        _log(f"     Full traceback: {traceback.format_exc()}")
        return False

# ✅ Update the main entry point to use V1.2
def run_quantification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """Main entry point - now uses V1.2 algorithm"""
    return run_quantification_for_patient_v2(dicom_path, patient_id, study_date)