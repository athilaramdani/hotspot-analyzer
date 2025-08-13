# features/spect_viewer/logic/quantification_integration.py - GUI Integration for Quantification

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
    """
    
    def __init__(self):
        self.current_results = None
        self.current_patient_id = None
        self.current_study_date = None
    
    def load_quantification_results(self, patient_folder: Path, patient_id: str, study_date: str) -> Optional[Dict]:
        try:
            filename_stem = generate_filename_stem(patient_id, study_date)
            
            # ✅ FIXED: Priority system - check edited first
            result_path_edited = patient_folder / f"{filename_stem}_bsi_quantification_edited.json"
            result_path_original = patient_folder / f"{filename_stem}_bsi_quantification.json"
            
            print(f"[BSI LOAD] Looking for quantification files:")
            print(f"[BSI LOAD]   Edited: {result_path_edited} ({'✅ EXISTS' if result_path_edited.exists() else '❌ NOT FOUND'})")
            print(f"[BSI LOAD]   Original: {result_path_original} ({'✅ EXISTS' if result_path_original.exists() else '❌ NOT FOUND'})")
            
            # Use edited version if exists, otherwise use original
            if result_path_edited.exists():
                result_path = result_path_edited
                print(f"[BSI LOAD] Using EDITED quantification: {result_path.name}")
            elif result_path_original.exists():
                result_path = result_path_original
                print(f"[BSI LOAD] Using ORIGINAL quantification: {result_path.name}")
            else:
                print(f"[BSI LOAD] ❌ No quantification results found for {filename_stem}")
                return None
            
            with open(result_path, 'r') as f:
                results = json.load(f)
            
            self.current_results = results
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            print(f"[BSI LOAD] ✅ Successfully loaded quantification results")
            return results
            
        except Exception as e:
            print(f"[BSI LOAD] ❌ Failed to load quantification results: {e}")
            return None

    def load_all_quantification_scores(self, patient_folder: Path, patient_id: str) -> List[Dict[str, Any]]:
        """
        ✅ UPDATED: Load V1.2 quantification scores (separate anterior/posterior files)
        Returns combined data with anterior, posterior, and combined BSI scores
        """
        all_scores = []
        found_study_dates = set()
        
        try:
            print(f"[BSI V1.2] Searching for V1.2 quantification files in: {patient_folder}")
            print(f"[BSI V1.2] Patient ID: {patient_id}")
            
            # ✅ NEW: Look for separate anterior/posterior files
            anterior_files = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification_anterior.json"))
            posterior_files = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification_posterior.json"))
            
            print(f"[BSI V1.2] Found anterior files: {[f.name for f in anterior_files]}")
            print(f"[BSI V1.2] Found posterior files: {[f.name for f in posterior_files]}")
            
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
                    print(f"[BSI V1.2] Error parsing anterior file {file_path.name}: {e}")
            
            # Parse posterior files  
            for file_path in posterior_files:
                try:
                    filename_base = file_path.stem.replace('_bsi_quantification_posterior', '')
                    parts = filename_base.split('_')
                    if len(parts) >= 2:
                        study_date = parts[1]
                        posterior_by_date[study_date] = file_path
                except Exception as e:
                    print(f"[BSI V1.2] Error parsing posterior file {file_path.name}: {e}")
            
            # ✅ Combine data for each study_date
            all_study_dates = set(anterior_by_date.keys()) | set(posterior_by_date.keys())
            
            for study_date in all_study_dates:
                try:
                    ant_file = anterior_by_date.get(study_date)
                    post_file = posterior_by_date.get(study_date)
                    
                    if not ant_file or not post_file:
                        print(f"[BSI V1.2] Incomplete pair for {study_date}: ant={bool(ant_file)}, post={bool(post_file)}")
                        continue
                    
                    # Load both files
                    with open(ant_file, 'r') as f:
                        ant_data = json.load(f)
                        
                    with open(post_file, 'r') as f:
                        post_data = json.load(f)
                    
                    # Extract BSI scores
                    ant_bsi = ant_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                    post_bsi = post_data.get('summary_statistics', {}).get('bsi_score', 0.0)
                    
                    # ✅ Calculate combined BSI using team formula
                    combined_bsi = (ant_bsi + post_bsi) / 2
    
                    print(f"[BSI V1.2 DEBUG] Loaded scores - Ant: {ant_bsi}, Post: {post_bsi}, Combined: {combined_bsi}")
                    
                    # Add to results
                    all_scores.append({
                        "study_date": study_date,
                        "anterior_bsi": ant_bsi,
                        "posterior_bsi": post_bsi,
                        "combined_bsi": combined_bsi,
                        "bsi_score": combined_bsi,  # For backward compatibility
                        "file_source": f"{ant_file.name} + {post_file.name}",
                        "is_v2": True
                    })
                    
                    found_study_dates.add(study_date)
                    print(f"[BSI V1.2] ✅ Loaded: {study_date} - Ant:{ant_bsi:.1f}% Post:{post_bsi:.1f}% Combined:{combined_bsi:.1f}%")
                    
                except Exception as e:
                    print(f"[BSI V1.2] ❌ Error processing {study_date}: {e}")
                    continue
            
            # ✅ Sort by study_date
            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            
            print(f"[BSI V1.2] 📊 Total V1.2 scores loaded: {len(all_scores)} from {len(found_study_dates)} study dates")
            
            # ✅ Debug: Show results
            for score in all_scores:
                print(f"[BSI V1.2]   {score['study_date']}: Ant={score['anterior_bsi']:.1f}% Post={score['posterior_bsi']:.1f}% Combined={score['combined_bsi']:.1f}%")

        except Exception as e:
            print(f"[BSI V1.2] ❌ Failed to load V1.2 BSI scores: {e}")
            import traceback
            traceback.print_exc()
            
        return all_scores

    def load_quantification_results(self, patient_folder: Path, patient_id: str, study_date: str) -> Optional[Dict]:
        """
        ✅ UPDATED: Load V1.2 quantification results (combines anterior + posterior)
        """
        try:
            filename_stem = generate_filename_stem(patient_id, study_date)
            
            # ✅ NEW: Look for V1.2 separate files
            ant_path = patient_folder / f"{filename_stem}_bsi_quantification_anterior.json"
            post_path = patient_folder / f"{filename_stem}_bsi_quantification_posterior.json"
            
            print(f"[BSI V1.2 LOAD] Looking for V1.2 quantification files:")
            print(f"[BSI V1.2 LOAD]   Anterior: {ant_path} ({'✅ EXISTS' if ant_path.exists() else '❌ NOT FOUND'})")
            print(f"[BSI V1.2 LOAD]   Posterior: {post_path} ({'✅ EXISTS' if post_path.exists() else '❌ NOT FOUND'})")
            
            if not (ant_path.exists() and post_path.exists()):
                print(f"[BSI V1.2 LOAD] ❌ V1.2 files not found for {filename_stem}")
                return None
            
            # Load both files
            with open(ant_path, 'r') as f:
                ant_results = json.load(f)
                
            with open(post_path, 'r') as f:
                post_results = json.load(f)
            
            # ✅ Combine results for backward compatibility
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
                    "total_anterior_pixels": ant_results["summary_statistics"]["total_pixels"],
                    "total_posterior_pixels": post_results["summary_statistics"]["total_pixels"],
                    "total_abnormal_hotspots": ant_results["summary_statistics"]["total_malignant_pixels"] + post_results["summary_statistics"]["total_malignant_pixels"],
                    "total_normal_hotspots": ant_results["summary_statistics"]["total_benign_pixels"] + post_results["summary_statistics"]["total_benign_pixels"],
                    "segments_analyzed": len([k for k, v in ant_results["bsi_results"].items() if v.get("total_pixels", 0) > 0]) + len([k for k, v in post_results["bsi_results"].items() if v.get("total_pixels", 0) > 0]),
                    "segments_with_abnormal": len([k for k, v in ant_results["bsi_results"].items() if v.get("malignant_pixels", 0) > 0]) + len([k for k, v in post_results["bsi_results"].items() if v.get("malignant_pixels", 0) > 0])
                }
            }
            
            # Update patient info to indicate V1.2
            combined_results["patient_info"]["quantification_method"] = "BSI_v1.2_color_based_separate_views"
            combined_results["patient_info"]["view"] = "combined_anterior_posterior"
            
            self.current_results = combined_results
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            print(f"[BSI V1.2 LOAD] ✅ Successfully loaded and combined V1.2 results")
            print(f"[BSI V1.2 LOAD] Combined BSI: {combined_results['summary_statistics']['combined_bsi']:.2f}%")
            return combined_results
            
        except Exception as e:
            print(f"[BSI V1.2 LOAD] ❌ Failed to load V1.2 quantification results: {e}")
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
        Get BSI summary statistics
        
        Returns:
            Dictionary with summary statistics
        """
        if not self.current_results:
            return {"error": "No quantification results loaded"}
        
        summary = self.current_results.get('summary_statistics', {})
        patient_info = self.current_results.get('patient_info', {})
        
        return {
            "patient_id": patient_info.get('patient_id', 'Unknown'),
            "study_date": patient_info.get('study_date', 'Unknown'),
            "bsi_score": summary.get('bsi_score', 0.0),
            "total_normal_hotspots": summary.get('total_normal_hotspots', 0),
            "total_abnormal_hotspots": summary.get('total_abnormal_hotspots', 0),
            "segments_analyzed": summary.get('total_segments_analyzed', 0),
            "segments_with_abnormal": summary.get('segments_with_abnormal_hotspots', 0),
            "overall_normal_percentage": summary.get('overall_normal_percentage', 0.0),
            "overall_abnormal_percentage": summary.get('overall_abnormal_percentage', 0.0)
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
    Check quantification status for a patient
    
    Args:
        dicom_path: Path to patient's DICOM file
        patient_id: Patient ID
        study_date: Study date (optional, will be extracted if not provided)
        
    Returns:
        Dictionary with quantification status
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
        
        # Check for output file
        output_file_anterior = patient_folder / f"{filename_stem}_bsi_quantification_anterior.json"
        output_file_posterior = patient_folder / f"{filename_stem}_bsi_quantification_posterior.json"
        output_file_old = patient_folder / f"{filename_stem}_bsi_quantification.json"

        # ✅ Quantification complete if V1.2 files exist OR old file exists
        v2_complete = output_file_anterior.exists() and output_file_posterior.exists()
        v1_complete = output_file_old.exists()
        quantification_complete = v2_complete or v1_complete

        # Calculate status
        missing_inputs = []
        for name, path in required_files.items():
            if not path.exists():
                missing_inputs.append(name)

        status = {
            "patient_id": patient_id,
            "study_date": study_date,
            "quantification_complete": quantification_complete,  # ✅ FIXED
            "required_files_exist": len(missing_inputs) == 0,
            "missing_files": missing_inputs,
            "output_file_exists": quantification_complete,  # ✅ FIXED
            "v2_files_exist": v2_complete,
            "v1_file_exists": v1_complete,
            "can_run_quantification": len(missing_inputs) == 0
        }

        if status["quantification_complete"]:  # ✅ NOW TRUE
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
                
                # ✅ DEBUG: Print what we're returning
                print(f"[BSI STATUS DEBUG] Returning status with:")
                print(f"[BSI STATUS DEBUG]   anterior_bsi: {status['anterior_bsi']}")
                print(f"[BSI STATUS DEBUG]   posterior_bsi: {status['posterior_bsi']}")
                print(f"[BSI STATUS DEBUG]   combined_bsi: {status['combined_bsi']}")
                        
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
    Format quantification results into a readable report
    
    Args:
        patient_folder: Patient directory path
        patient_id: Patient ID
        study_date: Study date
        
    Returns:
        Formatted string report
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
        report.append("BSI QUANTIFICATION REPORT")
        report.append("=" * 60)
        report.append(f"Patient ID: {summary['patient_id']}")
        report.append(f"Study Date: {summary['study_date']}")
        report.append(f"Analysis Method: Classification-based BSI")
        report.append("")
        
        report.append("OVERALL STATISTICS:")
        report.append("-" * 30)
        report.append(f"BSI Score: {summary['bsi_score']:.2f}%")
        report.append(f"Total Normal Hotspots: {summary['total_normal_hotspots']}")
        report.append(f"Total Abnormal Hotspots: {summary['total_abnormal_hotspots']}")
        report.append(f"Segments Analyzed: {summary['segments_analyzed']}")
        report.append(f"Segments with Abnormal: {summary['segments_with_abnormal']}")
        report.append(f"Overall Normal %: {summary['overall_normal_percentage']:.2f}%")
        report.append(f"Overall Abnormal %: {summary['overall_abnormal_percentage']:.2f}%")
        report.append("")
        
        report.append("PER-SEGMENT BREAKDOWN:")
        report.append("-" * 30)
        
        for segment_name, data in segment_data.items():
            if data['total_segment_pixels'] > 0:
                report.append(f"{segment_name}:")
                report.append(f"  Total Pixels: {data['total_segment_pixels']}")
                report.append(f"  Normal: {data['hotspot_normal']} ({data['percentage_normal']:.1f}%)")
                report.append(f"  Abnormal: {data['hotspot_abnormal']} ({data['percentage_abnormal']:.1f}%)")
                report.append("")
        
        report.append("=" * 60)
        
        return "\n".join(report)
        
    except Exception as e:
        return f"Error generating quantification report: {e}"