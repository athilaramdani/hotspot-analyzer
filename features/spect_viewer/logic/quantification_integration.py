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
        Memuat semua skor BSI untuk seorang pasien dari semua file kuantifikasi JSON.
        ✅ FIXED: Pattern yang benar untuk mendeteksi file edited
        """
        all_scores = []
        found_study_dates = set()
        
        try:
            # ✅ FIXED: Pattern yang lebih spesifik dan benar
            # Format file: {patient_id}_{study_date}_bsi_quantification[_edited].json
            
            # Cari semua file BSI untuk patient ini (baik edited maupun original)
            all_bsi_files = list(patient_folder.glob(f"{patient_id}_*_bsi_quantification*.json"))
            
            print(f"[BSI DEBUG] Searching in: {patient_folder}")
            print(f"[BSI DEBUG] Patient ID: {patient_id}")
            print(f"[BSI DEBUG] All BSI files found: {[f.name for f in all_bsi_files]}")
            
            # ✅ FIXED: Pisahkan file edited dan original
            edited_files = [f for f in all_bsi_files if "_bsi_quantification_edited.json" in f.name]
            original_files = [f for f in all_bsi_files if f.name.endswith("_bsi_quantification.json") and "_edited" not in f.name]
            
            print(f"[BSI DEBUG] Edited files: {[f.name for f in edited_files]}")
            print(f"[BSI DEBUG] Original files: {[f.name for f in original_files]}")
            
            # ✅ Process edited files first (higher priority)
            for file_path in edited_files:
                try:
                    # Extract study date: 130_20250628_bsi_quantification_edited.json -> 20250628
                    filename_without_ext = file_path.stem  # 130_20250628_bsi_quantification_edited
                    # Remove suffix
                    filename_base = filename_without_ext.replace('_bsi_quantification_edited', '')  # 130_20250628
                    parts = filename_base.split('_')  # ['130', '20250628']
                    
                    if len(parts) >= 2:
                        study_date = parts[1]  # 20250628
                        
                        # Mark this study date as processed (from edited file)
                        found_study_dates.add(study_date)
                        
                        # Load and process the JSON file
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        
                        # Extract BSI data
                        patient_info = data.get('patient_info', {})
                        summary = data.get('summary_statistics', {})
                        
                        json_study_date = patient_info.get('study_date')
                        bsi_score = summary.get('bsi_score')
                        
                        if json_study_date is not None and bsi_score is not None:
                            all_scores.append({
                                "study_date": json_study_date,
                                "bsi_score": bsi_score,
                                "file_source": file_path.name,
                                "is_edited": True
                            })
                            print(f"[BSI] ✅ Loaded EDITED BSI data: study_date={json_study_date}, bsi_score={bsi_score:.2f} from {file_path.name}")
                        else:
                            print(f"[BSI] ⚠️ Missing data in edited file {file_path.name}")
                    else:
                        print(f"[BSI] ❌ Invalid filename format for edited file: {file_path.name}")
                            
                except Exception as e:
                    print(f"[BSI] ❌ Error processing edited file {file_path.name}: {e}")
                    continue
            
            # ✅ Process original files only if study_date not already processed
            for file_path in original_files:
                try:
                    # Extract study date: 130_20250628_bsi_quantification.json -> 20250628
                    filename_without_ext = file_path.stem  # 130_20250628_bsi_quantification
                    # Remove suffix
                    filename_base = filename_without_ext.replace('_bsi_quantification', '')  # 130_20250628
                    parts = filename_base.split('_')  # ['130', '20250628']
                    
                    if len(parts) >= 2:
                        study_date = parts[1]  # 20250628
                        
                        # ✅ Skip if we already have edited version for this study_date
                        if study_date in found_study_dates:
                            print(f"[BSI] Skipping original file {file_path.name} - edited version already processed for study_date {study_date}")
                            continue
                        
                        # Mark this study date as processed
                        found_study_dates.add(study_date)
                        
                        # Load and process the JSON file
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        
                        # Extract BSI data
                        patient_info = data.get('patient_info', {})
                        summary = data.get('summary_statistics', {})
                        
                        json_study_date = patient_info.get('study_date')
                        bsi_score = summary.get('bsi_score')
                        
                        if json_study_date is not None and bsi_score is not None:
                            all_scores.append({
                                "study_date": json_study_date,
                                "bsi_score": bsi_score,
                                "file_source": file_path.name,
                                "is_edited": False
                            })
                            print(f"[BSI] ✅ Loaded ORIGINAL BSI data: study_date={json_study_date}, bsi_score={bsi_score:.2f} from {file_path.name}")
                        else:
                            print(f"[BSI] ⚠️ Missing data in original file {file_path.name}")
                    else:
                        print(f"[BSI] ❌ Invalid filename format for original file: {file_path.name}")
                            
                except Exception as e:
                    print(f"[BSI] ❌ Error processing original file {file_path.name}: {e}")
                    continue

            # ✅ Sort by study_date for consistent display
            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            
            print(f"[BSI] 📊 Total BSI scores loaded: {len(all_scores)} unique study dates: {list(found_study_dates)}")
            
            # ✅ Debug: Show final results
            for score in all_scores:
                priority_indicator = "🟢 EDITED" if score["is_edited"] else "🔵 ORIGINAL"
                print(f"[BSI]   {score['study_date']}: {score['bsi_score']:.1f}% ({priority_indicator}) from {score['file_source']}")

        except Exception as e:
            print(f"[BSI] ❌ Failed to load BSI scores: {e}")
            import traceback
            traceback.print_exc()
            
        return all_scores
    
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
        output_file = patient_folder / f"{filename_stem}_bsi_quantification.json"
        
        # Calculate status
        missing_inputs = []
        for name, path in required_files.items():
            if not path.exists():
                missing_inputs.append(name)
        
        status = {
            "patient_id": patient_id,
            "study_date": study_date,
            "quantification_complete": output_file.exists(),
            "required_files_exist": len(missing_inputs) == 0,
            "missing_files": missing_inputs,
            "output_file_exists": output_file.exists(),
            "can_run_quantification": len(missing_inputs) == 0
        }
        
        if status["quantification_complete"]:
            # Load and add summary info
            manager = QuantificationManager()
            results = manager.load_quantification_results(patient_folder, patient_id, study_date)
            if results:
                summary = manager.get_bsi_summary()
                status["bsi_score"] = summary.get("bsi_score", 0.0)
                status["total_abnormal_hotspots"] = summary.get("total_abnormal_hotspots", 0)
        
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