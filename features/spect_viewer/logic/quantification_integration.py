# features/spect_viewer/logic/quantification_integration.py - FIXED for Single View Support

from pathlib import Path
import json
from typing import List,Dict, Any, Optional
from core.logger import _log
from core.config.paths import (
    get_patient_spect_path,
    extract_study_date_from_dicom,
    generate_filename_stem
)

class QuantificationManager:
    """
    Manager class for handling quantification results (Backend only - no GUI)
    ✅ FIXED: Now supports single view quantification
    """
    
    def __init__(self):
        self.current_results = None
        self.current_patient_id = None
        self.current_study_date = None

    def load_all_quantification_scores(self, patient_folder: Path, patient_id: str) -> List[Dict[str, Any]]:
        """
        ✅ FIXED: Load V1.2 quantification scores - SUPPORTS SINGLE VIEW
        Returns combined data with anterior, posterior, and combined BSI scores (when available)
        """
        all_scores = []
        found_study_dates = set()
        
        try:
            print(f"[BSI V1.2 SINGLE] Searching for V1.2 quantification files in: {patient_folder}")
            print(f"[BSI V1.2 SINGLE] Patient ID: {patient_id}")
            
            # ✅ Look for separate anterior/posterior files
            anterior_files = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification_anterior.json"))
            posterior_files = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification_posterior.json"))
            
            print(f"[BSI V1.2 SINGLE] Found anterior files: {[f.name for f in anterior_files]}")
            print(f"[BSI V1.2 SINGLE] Found posterior files: {[f.name for f in posterior_files]}")
            
            # ✅ Create study_date -> file mapping
            anterior_by_date = {}
            posterior_by_date = {}
            
            # Parse anterior files
            for file_path in anterior_files:
                try:
                    filename_base = file_path.stem.replace('_bsi_quantification_anterior', '')
                    parts = filename_base.split('_')
                    if len(parts) >= 2:
                        study_date = parts[1]
                        anterior_by_date[study_date] = file_path
                except Exception as e:
                    print(f"[BSI V1.2 SINGLE] Error parsing anterior file {file_path.name}: {e}")
            
            # Parse posterior files  
            for file_path in posterior_files:
                try:
                    filename_base = file_path.stem.replace('_bsi_quantification_posterior', '')
                    parts = filename_base.split('_')
                    if len(parts) >= 2:
                        study_date = parts[1]
                        posterior_by_date[study_date] = file_path
                except Exception as e:
                    print(f"[BSI V1.2 SINGLE] Error parsing posterior file {file_path.name}: {e}")
            
            # ✅ FIXED: Process all study dates that have at least ONE view
            all_study_dates = set(anterior_by_date.keys()) | set(posterior_by_date.keys())
            
            for study_date in all_study_dates:
                try:
                    ant_file = anterior_by_date.get(study_date)
                    post_file = posterior_by_date.get(study_date)
                    
                    # ✅ NEW: Load available files (not requiring both)
                    ant_data = None
                    post_data = None
                    
                    if ant_file:
                        with open(ant_file, 'r') as f:
                            ant_data = json.load(f)
                            
                    if post_file:
                        with open(post_file, 'r') as f:
                            post_data = json.load(f)
                    
                    # ✅ FIXED: Handle different scenarios
                    
                    # Scenario 1: Both views available
                    if ant_data and post_data:
                        ant_bsi = ant_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                        post_bsi = post_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                        combined_bsi = (ant_bsi + post_bsi) / 2
                        
                        print(f"[BSI V1.2 SINGLE] Dual view - Ant: {ant_bsi}, Post: {post_bsi}, Combined: {combined_bsi}")
                        
                        all_scores.append({
                            "study_date": study_date,
                            "anterior_bsi": ant_bsi,
                            "posterior_bsi": post_bsi,
                            "combined_bsi": combined_bsi,
                            "bsi_score": combined_bsi,  # For backward compatibility
                            "file_source": f"{ant_file.name} + {post_file.name}",
                            "processing_mode": "dual_view",
                            "is_v2": True
                        })
                    
                    # Scenario 2: Only anterior available
                    elif ant_data and not post_data:
                        ant_bsi = ant_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                        
                        print(f"[BSI V1.2 SINGLE] Single view (anterior only) - Ant: {ant_bsi}")
                        
                        all_scores.append({
                            "study_date": study_date,
                            "anterior_bsi": ant_bsi,
                            "posterior_bsi": 0.0,  # Not available
                            "combined_bsi": ant_bsi,  # Use anterior as "combined"
                            "bsi_score": ant_bsi,  # For backward compatibility
                            "file_source": ant_file.name,
                            "processing_mode": "single_view_anterior",
                            "is_v2": True,
                            "note": "Only anterior view available"
                        })
                    
                    # Scenario 3: Only posterior available
                    elif post_data and not ant_data:
                        post_bsi = post_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                        
                        print(f"[BSI V1.2 SINGLE] Single view (posterior only) - Post: {post_bsi}")
                        
                        all_scores.append({
                            "study_date": study_date,
                            "anterior_bsi": 0.0,  # Not available
                            "posterior_bsi": post_bsi,
                            "combined_bsi": post_bsi,  # Use posterior as "combined"
                            "bsi_score": post_bsi,  # For backward compatibility
                            "file_source": post_file.name,
                            "processing_mode": "single_view_posterior",
                            "is_v2": True,
                            "note": "Only posterior view available"
                        })
                    
                    found_study_dates.add(study_date)
                    
                except Exception as e:
                    print(f"[BSI V1.2 SINGLE] ❌ Error processing {study_date}: {e}")
                    continue
            
            # ✅ Sort by study_date
            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            
            print(f"[BSI V1.2 SINGLE] 📊 Total V1.2 scores loaded: {len(all_scores)} from {len(found_study_dates)} study dates")
            
            # ✅ Debug: Show results
            for score in all_scores:
                mode = score.get('processing_mode', 'unknown')
                if mode == 'dual_view':
                    print(f"[BSI V1.2 SINGLE]   {score['study_date']}: Ant={score['anterior_bsi']:.1f}% Post={score['posterior_bsi']:.1f}% Combined={score['combined_bsi']:.1f}% [DUAL]")
                elif mode == 'single_view_anterior':
                    print(f"[BSI V1.2 SINGLE]   {score['study_date']}: Ant={score['anterior_bsi']:.1f}% (Post: N/A) Combined={score['combined_bsi']:.1f}% [ANT ONLY]")
                elif mode == 'single_view_posterior':
                    print(f"[BSI V1.2 SINGLE]   {score['study_date']}: Post={score['posterior_bsi']:.1f}% (Ant: N/A) Combined={score['combined_bsi']:.1f}% [POST ONLY]")

        except Exception as e:
            print(f"[BSI V1.2 SINGLE] ❌ Failed to load V1.2 BSI scores: {e}")
            import traceback
            traceback.print_exc()
            
        return all_scores

    def load_quantification_results(self, patient_folder: Path, patient_id: str, study_date: str) -> Optional[Dict]:
        """
        ✅ FIXED: Load V1.2 quantification results - SUPPORTS SINGLE VIEW
        """
        try:
            filename_stem = generate_filename_stem(patient_id, study_date)
            
            # ✅ Look for V1.2 separate files
            ant_path = patient_folder / f"{filename_stem}_bsi_quantification_anterior.json"
            post_path = patient_folder / f"{filename_stem}_bsi_quantification_posterior.json"
            
            print(f"[BSI V1.2 SINGLE LOAD] Looking for V1.2 quantification files:")
            print(f"[BSI V1.2 SINGLE LOAD]   Anterior: {ant_path} ({'✅ EXISTS' if ant_path.exists() else '❌ NOT FOUND'})")
            print(f"[BSI V1.2 SINGLE LOAD]   Posterior: {post_path} ({'✅ EXISTS' if post_path.exists() else '❌ NOT FOUND'})")
            
            # ✅ FIXED: Allow single view loading
            if not (ant_path.exists() or post_path.exists()):
                print(f"[BSI V1.2 SINGLE LOAD] ❌ No V1.2 files found for {filename_stem}")
                return None
            
            # Load available files
            ant_results = None
            post_results = None
            
            if ant_path.exists():
                with open(ant_path, 'r') as f:
                    ant_results = json.load(f)
                print(f"[BSI V1.2 SINGLE LOAD] ✅ Loaded anterior data")
                    
            if post_path.exists():
                with open(post_path, 'r') as f:
                    post_results = json.load(f)
                print(f"[BSI V1.2 SINGLE LOAD] ✅ Loaded posterior data")
            
            # ✅ FIXED: Handle different scenarios for combined results
            
            # Scenario 1: Both views available
            if ant_results and post_results:
                print(f"[BSI V1.2 SINGLE LOAD] Processing dual-view data")
                
                combined_results = {
                    "patient_info": ant_results["patient_info"].copy(),
                    "anterior_results": ant_results,
                    "posterior_results": post_results,
                    "bsi_results": {
                        # Combine region data from both views
                        **{f"anterior_{k}": v for k, v in ant_results["bsi_results"].items()},
                        **{f"posterior_{k}": v for k, v in post_results["bsi_results"].items()}
                    },
                    "summary_statistics": {
                        "anterior_bsi": ant_results["summary_statistics"]["bsi_score"],
                        "posterior_bsi": post_results["summary_statistics"]["bsi_score"],
                        "combined_bsi": (ant_results["summary_statistics"]["bsi_score"] + post_results["summary_statistics"]["bsi_score"]) / 2,
                        "bsi_score": (ant_results["summary_statistics"]["bsi_score"] + post_results["summary_statistics"]["bsi_score"]) / 2,
                        "processing_mode": "dual_view",
                        "total_anterior_pixels": ant_results["summary_statistics"]["total_pixels"],
                        "total_posterior_pixels": post_results["summary_statistics"]["total_pixels"],
                        "total_abnormal_hotspots": ant_results["summary_statistics"]["total_malignant_pixels"] + post_results["summary_statistics"]["total_malignant_pixels"],
                        "total_normal_hotspots": ant_results["summary_statistics"]["total_benign_pixels"] + post_results["summary_statistics"]["total_benign_pixels"],
                        "segments_analyzed": len([k for k, v in ant_results["bsi_results"].items() if v.get("total_pixels", 0) > 0]) + len([k for k, v in post_results["bsi_results"].items() if v.get("total_pixels", 0) > 0]),
                        "segments_with_abnormal": len([k for k, v in ant_results["bsi_results"].items() if v.get("malignant_pixels", 0) > 0]) + len([k for k, v in post_results["bsi_results"].items() if v.get("malignant_pixels", 0) > 0])
                    }
                }
                
                combined_results["patient_info"]["view"] = "combined_anterior_posterior"
                print(f"[BSI V1.2 SINGLE LOAD] Combined BSI: {combined_results['summary_statistics']['combined_bsi']:.2f}")
            
            # Scenario 2: Only anterior available
            elif ant_results and not post_results:
                print(f"[BSI V1.2 SINGLE LOAD] Processing anterior-only data")
                
                combined_results = {
                    "patient_info": ant_results["patient_info"].copy(),
                    "anterior_results": ant_results,
                    "posterior_results": None,
                    "bsi_results": {
                        **{f"anterior_{k}": v for k, v in ant_results["bsi_results"].items()}
                    },
                    "summary_statistics": {
                        "anterior_bsi": ant_results["summary_statistics"]["bsi_score"],
                        "posterior_bsi": 0.0,  # Not available
                        "combined_bsi": ant_results["summary_statistics"]["bsi_score"],  # Use anterior as combined
                        "bsi_score": ant_results["summary_statistics"]["bsi_score"],
                        "processing_mode": "single_view_anterior",
                        "total_anterior_pixels": ant_results["summary_statistics"]["total_pixels"],
                        "total_posterior_pixels": 0,
                        "total_abnormal_hotspots": ant_results["summary_statistics"]["total_malignant_pixels"],
                        "total_normal_hotspots": ant_results["summary_statistics"]["total_benign_pixels"],
                        "segments_analyzed": len([k for k, v in ant_results["bsi_results"].items() if v.get("total_pixels", 0) > 0]),
                        "segments_with_abnormal": len([k for k, v in ant_results["bsi_results"].items() if v.get("malignant_pixels", 0) > 0]),
                        "note": "Only anterior view processed - posterior files not available"
                    }
                }
                
                combined_results["patient_info"]["view"] = "anterior_only"
                print(f"[BSI V1.2 SINGLE LOAD] Anterior-only BSI: {combined_results['summary_statistics']['combined_bsi']:.2f}")
            
            # Scenario 3: Only posterior available
            elif post_results and not ant_results:
                print(f"[BSI V1.2 SINGLE LOAD] Processing posterior-only data")
                
                combined_results = {
                    "patient_info": post_results["patient_info"].copy(),
                    "anterior_results": None,
                    "posterior_results": post_results,
                    "bsi_results": {
                        **{f"posterior_{k}": v for k, v in post_results["bsi_results"].items()}
                    },
                    "summary_statistics": {
                        "anterior_bsi": 0.0,  # Not available
                        "posterior_bsi": post_results["summary_statistics"]["bsi_score"],
                        "combined_bsi": post_results["summary_statistics"]["bsi_score"],  # Use posterior as combined
                        "bsi_score": post_results["summary_statistics"]["bsi_score"],
                        "processing_mode": "single_view_posterior",
                        "total_anterior_pixels": 0,
                        "total_posterior_pixels": post_results["summary_statistics"]["total_pixels"],
                        "total_abnormal_hotspots": post_results["summary_statistics"]["total_malignant_pixels"],
                        "total_normal_hotspots": post_results["summary_statistics"]["total_benign_pixels"],
                        "segments_analyzed": len([k for k, v in post_results["bsi_results"].items() if v.get("total_pixels", 0) > 0]),
                        "segments_with_abnormal": len([k for k, v in post_results["bsi_results"].items() if v.get("malignant_pixels", 0) > 0]),
                        "note": "Only posterior view processed - anterior files not available"
                    }
                }
                
                combined_results["patient_info"]["view"] = "posterior_only"
                print(f"[BSI V1.2 SINGLE LOAD] Posterior-only BSI: {combined_results['summary_statistics']['combined_bsi']:.2f}")
            
            # Update patient info to indicate V1.2
            combined_results["patient_info"]["quantification_method"] = "BSI_v1.2_color_based_separate_views"
            
            self.current_results = combined_results
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            print(f"[BSI V1.2 SINGLE LOAD] ✅ Successfully loaded V1.2 results")
            return combined_results
            
        except Exception as e:
            print(f"[BSI V1.2 SINGLE LOAD] ❌ Failed to load V1.2 quantification results: {e}")
            return None
        
    def _extract_study_date_from_filename(self, filename: str) -> str:
        """
        Extracts study_date from filename pattern: {patient_id}_{study_date}_quant.json
        """
        try:
            parts = filename.split('_')
            if len(parts) >= 3:
                return parts[1]
        except:
            pass
        return "Unknown"
        
    def get_bsi_summary(self) -> Dict[str, Any]:
        """
        ✅ UPDATED: Get BSI summary statistics - handles single view data
        """
        if not self.current_results:
            return {"error": "No quantification results loaded"}
        
        summary = self.current_results.get('summary_statistics', {})
        patient_info = self.current_results.get('patient_info', {})
        
        # ✅ Get processing mode for display
        processing_mode = summary.get('processing_mode', 'unknown')
        view_info = patient_info.get('view', 'unknown')
        
        return {
            "patient_id": patient_info.get('patient_id', 'Unknown'),
            "study_date": patient_info.get('study_date', 'Unknown'),
            "bsi_score": summary.get('bsi_score', 0.0),
            "anterior_bsi": summary.get('anterior_bsi', 0.0),
            "posterior_bsi": summary.get('posterior_bsi', 0.0),
            "combined_bsi": summary.get('combined_bsi', 0.0),
            "processing_mode": processing_mode,
            "view_info": view_info,
            "total_normal_hotspots": summary.get('total_normal_hotspots', 0),
            "total_abnormal_hotspots": summary.get('total_abnormal_hotspots', 0),
            "segments_analyzed": summary.get('total_segments_analyzed', summary.get('segments_analyzed', 0)),
            "segments_with_abnormal": summary.get('segments_with_abnormal_hotspots', summary.get('segments_with_abnormal', 0)),
            "overall_normal_percentage": summary.get('overall_normal_percentage', 0.0),
            "overall_abnormal_percentage": summary.get('overall_abnormal_percentage', 0.0),
            "note": summary.get('note', '')
        }
    
    def get_segment_breakdown(self) -> Dict[str, Dict]:
        """
        Get per-segment breakdown
        
        Returns:
            Dictionary with per-segment data
        """
        if not self.current_results:
            return {"error": "No quantification results loaded"}
        
        return self.current_results.get('bsi_results', {})
    
    def export_results_summary(self, output_path: Path) -> bool:
        """
        Export quantification results summary to file
        
        Args:
            output_path: Path to save the summary
            
        Returns:
            True if successful, False otherwise
        """
        if not self.current_results:
            return False
        
        try:
            summary = self.get_bsi_summary()
            segment_data = self.get_segment_breakdown()
            
            export_data = {
                "summary": summary,
                "segment_breakdown": segment_data,
                "raw_results": self.current_results
            }
            
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            _log(f"Quantification results exported to: {output_path}")
            return True
            
        except Exception as e:
            _log(f"Failed to export quantification results: {e}")
            return False


def run_quantification_for_patient_integrated(dicom_path: Path, patient_id: str, study_date: str = None) -> bool:
    """
    Integrated function to run quantification for a patient using the new workflow
    Integrates with existing processing pipeline
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date (optional, will be extracted if not provided)
        
    Returns:
        True if quantification successful, False otherwise
    """
    try:
        if not study_date:
            study_date = extract_study_date_from_dicom(dicom_path)
        
        print(f"[QUANTIFICATION] Starting BSI quantification for patient {patient_id}")
        print(f"[QUANTIFICATION] Study date: {study_date}")
        print(f"[QUANTIFICATION] Using classification masks instead of Otsu results")
        
        # Import quantification function
        from features.spect_viewer.logic.quantification_wrapper import run_quantification_for_patient
        
        # Run quantification
        result = run_quantification_for_patient(dicom_path, patient_id, study_date)
        
        if result:
            print(f"[QUANTIFICATION] BSI quantification completed successfully")
        else:
            print(f"[QUANTIFICATION] BSI quantification failed")
            
        return result
        
    except Exception as e:
        print(f"[QUANTIFICATION ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def get_quantification_status(dicom_path: Path, patient_id: str, study_date: str = None) -> Dict:
    """
    ✅ FIXED: Check quantification status for a patient - SUPPORTS SINGLE VIEW
    """
    try:
        if not study_date:
            study_date = extract_study_date_from_dicom(dicom_path)
        
        patient_folder = dicom_path.parent
        filename_stem = generate_filename_stem(patient_id, study_date)
        
        # Check for required input files
        required_files = {
            "segment_anterior": patient_folder / f"{filename_stem}_anterior_colored.png",
            "segment_posterior": patient_folder / f"{filename_stem}_posterior_colored.png",
            "hotspot_anterior": patient_folder / f"{filename_stem}_anterior_classification_mask.png",
            "hotspot_posterior": patient_folder / f"{filename_stem}_posterior_classification_mask.png"
        }
        
        # Check for output files
        output_file_anterior = patient_folder / f"{filename_stem}_bsi_quantification_anterior.json"
        output_file_posterior = patient_folder / f"{filename_stem}_bsi_quantification_posterior.json"
        output_file_old = patient_folder / f"{filename_stem}_bsi_quantification.json"

        # ✅ FIXED: Quantification complete if we have at least ONE V1.2 file OR old file exists
        v2_anterior_exists = output_file_anterior.exists()
        v2_posterior_exists = output_file_posterior.exists()
        v1_complete = output_file_old.exists()
        quantification_complete = v2_anterior_exists or v2_posterior_exists or v1_complete

        # ✅ Check which input files are missing
        missing_inputs = []
        for name, path in required_files.items():
            if not path.exists():
                missing_inputs.append(name)

        # ✅ FIXED: Can run quantification if we have at least ONE complete pair
        has_anterior_pair = (required_files["segment_anterior"].exists() and 
                           required_files["hotspot_anterior"].exists())
        has_posterior_pair = (required_files["segment_posterior"].exists() and 
                            required_files["hotspot_posterior"].exists())
        
        can_run_quantification = has_anterior_pair or has_posterior_pair

        status = {
            "patient_id": patient_id,
            "study_date": study_date,
            "quantification_complete": quantification_complete,
            "required_files_exist": len(missing_inputs) == 0,
            "missing_files": missing_inputs,
            "output_file_exists": quantification_complete,
            "v2_anterior_exists": v2_anterior_exists,
            "v2_posterior_exists": v2_posterior_exists,
            "v1_file_exists": v1_complete,
            "can_run_quantification": can_run_quantification,
            "has_anterior_pair": has_anterior_pair,
            "has_posterior_pair": has_posterior_pair
        }

        if status["quantification_complete"]:
            # Load and add summary info
            manager = QuantificationManager()
            results = manager.load_quantification_results(patient_folder, patient_id, study_date)
            if results:
                summary = results.get("summary_statistics", {})
                status["anterior_bsi"] = summary.get("anterior_bsi", 0.0)      
                status["posterior_bsi"] = summary.get("posterior_bsi", 0.0)    
                status["combined_bsi"] = summary.get("combined_bsi", 0.0)      
                status["bsi_score"] = summary.get("combined_bsi", 0.0)         
                status["total_abnormal_hotspots"] = summary.get("total_abnormal_hotspots", 0)
                status["processing_mode"] = summary.get("processing_mode", "unknown")
                
                # ✅ DEBUG: Print what we're returning
                print(f"[BSI STATUS DEBUG] Returning status with:")
                print(f"[BSI STATUS DEBUG]   anterior_bsi: {status['anterior_bsi']}")
                print(f"[BSI STATUS DEBUG]   posterior_bsi: {status['posterior_bsi']}")
                print(f"[BSI STATUS DEBUG]   combined_bsi: {status['combined_bsi']}")
                print(f"[BSI STATUS DEBUG]   processing_mode: {status['processing_mode']}")
                        
        return status
        
    except Exception as e:
        print(f"[QUANTIFICATION STATUS ERROR] {e}")
        return {
            "patient_id": patient_id,
            "study_date": study_date or "unknown",
            "quantification_complete": False,
            "required_files_exist": False,
            "missing_files": ["error"],
            "error": str(e)
        }


def format_quantification_report(patient_folder: Path, patient_id: str, study_date: str) -> str:
    """
    ✅ UPDATED: Format quantification results into a readable report - handles single view
    """
    try:
        manager = QuantificationManager()
        results = manager.load_quantification_results(patient_folder, patient_id, study_date)
        
        if not results:
            return f"No quantification results found for patient {patient_id}"
        
        summary = manager.get_bsi_summary()
        segment_data = manager.get_segment_breakdown()
        
        report = []
        report.append("=" * 60)
        report.append("BSI QUANTIFICATION REPORT (V1.2)")
        report.append("=" * 60)
        report.append(f"Patient ID: {summary['patient_id']}")
        report.append(f"Study Date: {summary['study_date']}")
        report.append(f"Analysis Method: Classification-based BSI V1.2")
        report.append(f"Processing Mode: {summary.get('processing_mode', 'Unknown')}")
        report.append(f"View Info: {summary.get('view_info', 'Unknown')}")
        if summary.get('note'):
            report.append(f"Note: {summary['note']}")
        report.append("")
        
        report.append("OVERALL STATISTICS:")
        report.append("-" * 30)
        
        # ✅ Show different stats based on processing mode
        processing_mode = summary.get('processing_mode', 'unknown')
        
        if processing_mode == 'dual_view':
            report.append(f"Anterior BSI: {summary['anterior_bsi']:.2f}%")
            report.append(f"Posterior BSI: {summary['posterior_bsi']:.2f}%")
            report.append(f"Combined BSI: {summary['combined_bsi']:.2f}%")
        elif processing_mode == 'single_view_anterior':
            report.append(f"Anterior BSI: {summary['anterior_bsi']:.2f}%")
            report.append(f"Posterior BSI: N/A (files not available)")
            report.append(f"Single View BSI: {summary['combined_bsi']:.2f}%")
        elif processing_mode == 'single_view_posterior':
            report.append(f"Anterior BSI: N/A (files not available)")
            report.append(f"Posterior BSI: {summary['posterior_bsi']:.2f}%")
            report.append(f"Single View BSI: {summary['combined_bsi']:.2f}%")
        else:
            report.append(f"BSI Score: {summary['bsi_score']:.2f}%")
        
        report.append(f"Total Normal Hotspots: {summary['total_normal_hotspots']}")
        report.append(f"Total Abnormal Hotspots: {summary['total_abnormal_hotspots']}")
        report.append(f"Segments Analyzed: {summary['segments_analyzed']}")
        report.append(f"Segments with Abnormal: {summary['segments_with_abnormal']}")
        report.append("")
        
        report.append("PER-SEGMENT BREAKDOWN:")
        report.append("-" * 30)
        
        for segment_name, data in segment_data.items():
            if isinstance(data, dict) and data.get('total_pixels', 0) > 0:
                report.append(f"{segment_name}:")
                report.append(f"  Total Pixels: {data.get('total_pixels', 0)}")
                report.append(f"  Normal: {data.get('benign_pixels', 0)} ({data.get('benign_ratio', 0):.3f})")
                report.append(f"  Abnormal: {data.get('malignant_pixels', 0)} ({data.get('malignant_ratio', 0):.3f})")
                report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
        
    except Exception as e:
        return f"Error generating quantification report: {e}"