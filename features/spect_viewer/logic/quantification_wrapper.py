# features/spect_viewer/logic/quantification_wrapper.py - FIXED for Single View Support

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
    """Get input file paths for V1.2 quantification with debugging"""
    
    print(f"\n🔧 [DEBUG WRAPPER GANTENG] ===================")
    print(f"🔧 [DEBUG WRAPPER] Getting quantification input paths:")
    print(f"🔧 [DEBUG WRAPPER]   Patient folder: {patient_folder}")
    print(f"🔧 [DEBUG WRAPPER]   Filename stem: {filename_stem}")
    print(f"🔧 [DEBUG WRAPPER]   Folder exists: {patient_folder.exists()}")
    
    # Get classification files (for hotspot data)
    try:
        from core.config.paths import get_classification_files, get_segmentation_files_with_edited, get_planar_quantification_files
        
        ant_clf_files = get_classification_files(patient_folder, filename_stem, "anterior")
        post_clf_files = get_classification_files(patient_folder, filename_stem, "posterior")
        
        print(f"🔧 [DEBUG WRAPPER] Classification files:")
        print(f"🔧 [DEBUG WRAPPER]   Anterior mask: {ant_clf_files['mask_original'].exists()}")
        print(f"🔧 [DEBUG WRAPPER]   Posterior mask: {post_clf_files['mask_original'].exists()}")
        
        # Get segmentation files (for region data) - prioritize edited
        ant_seg_files = get_segmentation_files_with_edited(patient_folder, filename_stem, "anterior")
        post_seg_files = get_segmentation_files_with_edited(patient_folder, filename_stem, "posterior")
        
        print(f"🔧 [DEBUG WRAPPER] Segmentation files:")
        print(f"🔧 [DEBUG WRAPPER]   Anterior seg: {ant_seg_files['png_colored'].exists()}")
        print(f"🔧 [DEBUG WRAPPER]   Posterior seg: {post_seg_files['png_colored'].exists()}")
        
        # Use classification_mask.png (not hotspot_colored.png)
        ant_mask_to_use = ant_clf_files['mask_edited'] if ant_clf_files['mask_edited'] and ant_clf_files['mask_edited'].exists() else ant_clf_files['mask_original']
        post_mask_to_use = post_clf_files['mask_edited'] if post_clf_files['mask_edited'] and post_clf_files['mask_edited'].exists() else post_clf_files['mask_original']
        
        # Use colored segmentation (for region detection)
        ant_seg_to_use = ant_seg_files['png_colored_edited'] if ant_seg_files['png_colored_edited'] and ant_seg_files['png_colored_edited'].exists() else ant_seg_files['png_colored']
        post_seg_to_use = post_seg_files['png_colored_edited'] if post_seg_files['png_colored_edited'] and post_seg_files['png_colored_edited'].exists() else post_seg_files['png_colored']
        
        # Get output paths using new structure
        quant_files = get_planar_quantification_files(patient_folder)
        
        paths = {
            # Input files
            'segmentation_anterior': ant_seg_to_use,
            'segmentation_posterior': post_seg_to_use,
            'hotspot_anterior': ant_mask_to_use,
            'hotspot_posterior': post_mask_to_use,
            
            # ✅ UPDATED: Output files using correct short naming (ant/post)
            'output_anterior': quant_files['bsi_json_ant'],
            'output_posterior': quant_files['bsi_json_post']
        }
        
        print(f"🔧 [DEBUG WRAPPER] Final paths:")
        for key, value in paths.items():
            exists = value.exists() if hasattr(value, 'exists') else False
            print(f"🔧 [DEBUG WRAPPER]   {key}: {value} (exists: {exists})")
        
        return paths
        
    except Exception as e:
        print(f"🔧 [DEBUG WRAPPER] ❌ Error getting paths: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback to old method
        print(f"🔧 [DEBUG WRAPPER] Using fallback method...")
        return {
            'segmentation_anterior': patient_folder / f"ant_segm.png",
            'segmentation_posterior': patient_folder / f"post_segm.png", 
            'hotspot_anterior': patient_folder / f"ant_hotspot_classification.png",
            'hotspot_posterior': patient_folder / f"post_hotspot_classification.png",
            'output_anterior': patient_folder / f"{filename_stem}_bsi_quantification_anterior.json",
            'output_posterior': patient_folder / f"{filename_stem}_bsi_quantification_posterior.json"
        }

def check_available_files_v2(paths):
    """✅ FIXED: Check file availability for V1.2 quantification - ALLOW SINGLE VIEW"""
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
    
    # ✅ FIXED: Check for anterior OR posterior pair (not both required)
    has_anterior_pair = ('segmentation_anterior' in available_paths and 
                        'hotspot_anterior' in available_paths)
    has_posterior_pair = ('segmentation_posterior' in available_paths and 
                         'hotspot_posterior' in available_paths)
    
    # ✅ NEW: Can proceed if we have at least ONE complete pair
    can_proceed = has_anterior_pair or has_posterior_pair
    
    return available_paths, missing_files, can_proceed, has_anterior_pair, has_posterior_pair

def run_quantification_for_patient_v2(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """
    ✅ FIXED: Run V1.2 BSI quantification - SUPPORTS SINGLE VIEW (anterior OR posterior)
    """
    try:
        patient_folder = dicom_path.parent
        filename_stem = f"{patient_id}_{study_date}"
        
        _log(f"     Starting V1.2 BSI quantification for patient {patient_id}")
        _log(f"     New workflow: Color-based segmentation + Single/Dual view processing")
        
        # Get file paths
        paths = get_quantification_input_paths_v2(patient_folder, filename_stem)
        
        # ✅ FIXED: Check available files with new return values
        available_paths, missing_files, can_proceed, has_anterior_pair, has_posterior_pair = check_available_files_v2(paths)
        
        if not can_proceed:
            _log(f"     Cannot proceed with V1.2 quantification. Missing files: {', '.join(missing_files)}")
            _log(f"     Need at least ONE complete pair (anterior OR posterior segmentation + classification)")
            return False
        
        # ✅ NEW: Log what we have available
        _log(f"     File availability check:")
        _log(f"       Anterior pair available: {has_anterior_pair}")
        _log(f"       Posterior pair available: {has_posterior_pair}")
        
        if missing_files:
            _log(f"     [INFO] Some files missing (but proceeding): {', '.join(missing_files)}")
        
        _log(f"     Processing V1.2 quantification with color-based segmentation...")
        
        # ✅ NEW: Process available views only
        anterior_results = None
        posterior_results = None
        
        # Process anterior view if available
        if has_anterior_pair:
            _log(f"     Processing anterior view...")
            try:
                anterior_results = calculate_pixel_bsi_v2(
                    str(available_paths['segmentation_anterior']),
                    str(available_paths['hotspot_anterior'])
                )
                _log(f"     ✅ Anterior processing completed")
            except Exception as e:
                _log(f"     ❌ Anterior processing failed: {e}")
                anterior_results = None
        else:
            _log(f"     ⏭️ Skipping anterior view (files not available)")
        
        # Process posterior view if available
        if has_posterior_pair:
            _log(f"     Processing posterior view...")
            try:
                posterior_results = calculate_pixel_bsi_v2(
                    str(available_paths['segmentation_posterior']),
                    str(available_paths['hotspot_posterior'])
                )
                _log(f"     ✅ Posterior processing completed")
            except Exception as e:
                _log(f"     ❌ Posterior processing failed: {e}")
                posterior_results = None
        else:
            _log(f"     ⏭️ Skipping posterior view (files not available)")
        
        # ✅ Check if we got at least one result
        if not anterior_results and not posterior_results:
            _log(f"     ❌ No views processed successfully")
            return False
        
        # ✅ NEW: Calculate combined BSI based on available data
        _log(f"     Calculating BSI scores...")
        
        # Prepare base metadata
        base_metadata = {
            "patient_id": patient_id,
            "study_date": study_date,
            "filename_stem": filename_stem,
            "quantification_method": "BSI_v1.2_color_based_separate_views",
            "algorithm_version": "1.2"
        }
        
        # ✅ NEW: Handle different scenarios
        
        # Scenario 1: Both anterior and posterior available
        if anterior_results and posterior_results:
            _log(f"     Scenario: Both views available")
            combined_results = calculate_combined_bsi_v2(anterior_results, posterior_results)
            
            # Save both files
            anterior_final = {
                "patient_info": {
                    **base_metadata,
                    "view": "anterior",
                    "processing_mode": "dual_view",
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
                    "combined_bsi_available": True,
                    "combined_bsi": combined_results["combined_bsi"]
                }
            }
            
            posterior_final = {
                "patient_info": {
                    **base_metadata,
                    "view": "posterior",
                    "processing_mode": "dual_view",
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
                    "combined_bsi_available": True,
                    "combined_bsi": combined_results["combined_bsi"]
                }
            }
            
            # Write both files
            with open(paths['output_anterior'], 'w') as f:
                json.dump(anterior_final, f, indent=2)
            with open(paths['output_posterior'], 'w') as f:
                json.dump(posterior_final, f, indent=2)
                
            _log(f"     ✅ Dual-view BSI quantification completed")
            _log(f"     Anterior BSI: {combined_results['anterior_bsi']:.3f}")
            _log(f"     Posterior BSI: {combined_results['posterior_bsi']:.3f}")
            _log(f"     Combined BSI: {combined_results['combined_bsi']:.3f}")
            
        # Scenario 2: Only anterior available
        elif anterior_results and not posterior_results:
            _log(f"     Scenario: Only anterior view available")
            anterior_bsi = anterior_results["summary_statistics"]["bsi_score"]
            
            anterior_final = {
                "patient_info": {
                    **base_metadata,
                    "view": "anterior",
                    "processing_mode": "single_view_anterior",
                    "input_files": {
                        "segmentation": available_paths['segmentation_anterior'].name,
                        "hotspot": available_paths['hotspot_anterior'].name
                    }
                },
                "bsi_results": anterior_results["region_stats"],
                "summary_statistics": {
                    "view": "anterior",
                    "bsi_score": anterior_bsi,
                    "total_malignant_pixels": anterior_results["total_malignant_pixels"],
                    "total_benign_pixels": anterior_results["total_benign_pixels"],
                    "total_pixels": sum(anterior_results["region_total_pixels"].values()),
                    "combined_bsi_available": False,
                    "single_view_mode": True,
                    "note": "Only anterior view processed - posterior files not available"
                }
            }
            
            # Write only anterior file
            with open(paths['output_anterior'], 'w') as f:
                json.dump(anterior_final, f, indent=2)
                
            _log(f"     ✅ Single-view (anterior) BSI quantification completed")
            _log(f"     Anterior BSI: {anterior_bsi:.3f}")
            _log(f"     Note: Posterior files not available")
            
        # Scenario 3: Only posterior available
        elif posterior_results and not anterior_results:
            _log(f"     Scenario: Only posterior view available")
            posterior_bsi = posterior_results["summary_statistics"]["bsi_score"]
            
            posterior_final = {
                "patient_info": {
                    **base_metadata,
                    "view": "posterior",
                    "processing_mode": "single_view_posterior",
                    "input_files": {
                        "segmentation": available_paths['segmentation_posterior'].name,
                        "hotspot": available_paths['hotspot_posterior'].name
                    }
                },
                "bsi_results": posterior_results["region_stats"],
                "summary_statistics": {
                    "view": "posterior",
                    "bsi_score": posterior_bsi,
                    "total_malignant_pixels": posterior_results["total_malignant_pixels"],
                    "total_benign_pixels": posterior_results["total_benign_pixels"],
                    "total_pixels": sum(posterior_results["region_total_pixels"].values()),
                    "combined_bsi_available": False,
                    "single_view_mode": True,
                    "note": "Only posterior view processed - anterior files not available"
                }
            }
            
            # Write only posterior file
            with open(paths['output_posterior'], 'w') as f:
                json.dump(posterior_final, f, indent=2)
                
            _log(f"     ✅ Single-view (posterior) BSI quantification completed")
            _log(f"     Posterior BSI: {posterior_bsi:.3f}")
            _log(f"     Note: Anterior files not available")
        
        _log(f"     Results saved to patient folder")
        return True
        
    except Exception as e:
        _log(f"     V1.2 Quantification error for patient {patient_id}: {e}")
        import traceback
        _log(f"     Full traceback: {traceback.format_exc()}")
        return False

# ✅ Update the main entry point to use V1.2
def run_quantification_for_patient(dicom_path: Path, patient_id: str, study_date: str) -> bool:
    """Main entry point - now uses V1.2 algorithm with single view support"""
    return run_quantification_for_patient_v2(dicom_path, patient_id, study_date)