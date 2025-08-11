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
            
            # Use edited version if exists, otherwise use original
            if result_path_edited.exists():
                result_path = result_path_edited
                print(f"[BSI] Loading EDITED quantification: {result_path.name}")
            elif result_path_original.exists():
                result_path = result_path_original
                print(f"[BSI] Loading ORIGINAL quantification: {result_path.name}")
            else:
                _log(f"Quantification results not found: {result_path_original.name}")
                return None
            
            with open(result_path, 'r') as f:
                results = json.load(f)
            
            self.current_results = results
            self.current_patient_id = patient_id
            self.current_study_date = study_date
            
            _log(f"Loaded quantification results for patient {patient_id}")
            return results
            
        except Exception as e:
            _log(f"Failed to load quantification results: {e}")
            return None
    # GANTI FUNGSI INI DI quantification_integration.py

    def load_all_quantification_scores(self, patient_folder: Path, patient_id: str) -> List[Dict[str, Any]]:
        """
        Memuat semua skor BSI untuk seorang pasien dari semua file kuantifikasi JSON.
        ✅ FIXED: Prioritaskan file _edited, hindari duplikasi study_date
        """
        all_scores = []
        found_study_dates = set()  # Track processed study dates to avoid duplicates
        
        # ✅ FIXED: Search patterns dengan prioritas
        search_patterns = [
            f"{patient_id}_*_bsi_quantification_edited.json",  # Priority 1: edited files
            f"{patient_id}_*_bsi_quantification.json"          # Priority 2: original files
        ]
        
        try:
            # Process each pattern in priority order
            for pattern in search_patterns:
                for file_path in patient_folder.glob(pattern):
                    try:
                        # Extract study date from filename to check for duplicates
                        filename_parts = file_path.stem.split('_')
                        if len(filename_parts) >= 2:
                            study_date = filename_parts[1]
                            
                            # ✅ Skip if we already processed this study date (from higher priority file)
                            if study_date in found_study_dates:
                                print(f"[BSI] Skipping {file_path.name} - study_date {study_date} already processed from higher priority file")
                                continue
                            
                            # Mark this study date as processed
                            found_study_dates.add(study_date)
                        else:
                            print(f"[BSI] Invalid filename format: {file_path.name}")
                            continue
                        
                        # Load and process the JSON file
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        
                        # AMBIL DARI LOKASI YANG BENAR DI DALAM JSON
                        patient_info = data.get('patient_info', {})
                        summary = data.get('summary_statistics', {})

                        # Ekstrak data dari dictionary masing-masing
                        json_study_date = patient_info.get('study_date')
                        bsi_score = summary.get('bsi_score')

                        if json_study_date is not None and bsi_score is not None:
                            # ✅ Use study_date from JSON content, not filename
                            all_scores.append({
                                "study_date": json_study_date,
                                "bsi_score": bsi_score,
                                "file_source": file_path.name,  # ✅ Track which file was used
                                "is_edited": "_edited" in file_path.name  # ✅ Track if edited version
                            })
                            print(f"[BSI] ✅ Loaded BSI data from {file_path.name}: study_date={json_study_date}, bsi_score={bsi_score:.2f}")
                        else:
                            print(f"[BSI] ⚠️ Missing study_date or bsi_score in {file_path.name}")
                            
                    except Exception as e:
                        print(f"[BSI] ❌ Error processing {file_path.name}: {e}")
                        continue

            # ✅ Sort by study_date for consistent display
            all_scores = sorted(all_scores, key=lambda x: x["study_date"])
            
            print(f"[BSI] 📊 Total BSI scores loaded: {len(all_scores)} (from {len(found_study_dates)} unique study dates)")
            
            # ✅ Debug: Show which files were used
            for score in all_scores:
                priority_indicator = "🟢 EDITED" if score["is_edited"] else "🔵 ORIGINAL"
                print(f"[BSI]   {score['study_date']}: {score['bsi_score']:.1f}% ({priority_indicator}) from {score['file_source']}")

        except Exception as e:
            print(f"[BSI] ❌ Failed to load BSI scores: {e}")
            
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