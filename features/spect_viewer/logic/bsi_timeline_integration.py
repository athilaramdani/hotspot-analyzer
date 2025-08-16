# features/spect_viewer/logic/bsi_timeline_integration.py - FIXED for Single View Support
"""
Integration logic for BSI quantification with timeline cards
Handles loading BSI data when patients are selected from timeline
✅ UPDATED: Now supports single view quantification (anterior OR posterior only)
"""
from pathlib import Path
from typing import Dict, Optional, Any
import json

from core.logger import _log
from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
    get_patient_planar_path
)

# Import quantification components
from features.spect_viewer.logic.quantification_integration import (
    QuantificationManager,
    get_quantification_status
)


class BSITimelineIntegration:
    """
    Integration manager for BSI quantification and timeline
    Handles patient selection and BSI data loading
    ✅ UPDATED: Now supports single view processing
    """
    
    def __init__(self):
        self.quant_manager = QuantificationManager()
        self.current_patient_data = None
        
    def get_patient_bsi_data(self, scan_data: Dict, session_code: str = None) -> Optional[Dict[str, Any]]:
        """
        Get BSI data for a patient from timeline scan data
        ✅ UPDATED: Supports single view data loading
        
        Args:
            scan_data: Timeline scan data dictionary
            session_code: Session code (NSY, ATL, etc.)
            
        Returns:
            Dictionary with BSI data or None if not available
        """
        try:
            # Extract patient info from scan data
            dicom_path = Path(scan_data["path"])
            patient_folder = dicom_path.parent
            
            # Get patient ID and study date
            patient_id, study_date = self._extract_patient_info(scan_data, session_code)
            
            if not patient_id or not study_date:
                _log(f"[BSI INTEGRATION SINGLE] Could not extract patient info from scan data")
                return None
            
            _log(f"[BSI INTEGRATION SINGLE] Loading BSI data for patient {patient_id}, study {study_date}")
            
            # Check if quantification exists (now supports single view)
            status = get_quantification_status(dicom_path, patient_id, study_date)
            
            if not status.get("quantification_complete", False):
                _log(f"[BSI INTEGRATION SINGLE] No quantification data available for {patient_id}")
                return {
                    "patient_id": patient_id,
                    "study_date": study_date,
                    "patient_folder": patient_folder,
                    "status": "no_quantification",
                    "message": "Quantification not completed"
                }
            
            # Load quantification results (supports single view)
            results = self.quant_manager.load_quantification_results(patient_folder, patient_id, study_date)
            
            if not results:
                _log(f"[BSI INTEGRATION SINGLE] Failed to load quantification results for {patient_id}")
                return {
                    "patient_id": patient_id,
                    "study_date": study_date,
                    "patient_folder": patient_folder,
                    "status": "load_error",
                    "message": "Failed to load quantification data"
                }
            
            # Get summary data (includes processing mode info)
            summary_data = self.quant_manager.get_bsi_summary()
            
            # ✅ NEW: Add processing mode info
            processing_mode = summary_data.get('processing_mode', 'unknown')
            view_info = summary_data.get('view_info', 'unknown')
            
            bsi_data = {
                "patient_id": patient_id,
                "study_date": study_date,
                "patient_folder": patient_folder,
                "status": "success",
                "bsi_results": results.get('bsi_results', {}),
                "summary_data": summary_data,
                "raw_results": results,
                "processing_mode": processing_mode,
                "view_info": view_info
            }
            
            self.current_patient_data = bsi_data
            
            # ✅ NEW: Log different message based on processing mode
            combined_bsi = summary_data.get('combined_bsi', 0)
            if processing_mode == 'dual_view':
                _log(f"[BSI INTEGRATION SINGLE] ✅ Loaded dual-view BSI data for {patient_id} (Combined BSI: {combined_bsi:.2f})")
            elif processing_mode == 'single_view_anterior':
                _log(f"[BSI INTEGRATION SINGLE] ✅ Loaded anterior-only BSI data for {patient_id} (Anterior BSI: {combined_bsi:.2f})")
            elif processing_mode == 'single_view_posterior':
                _log(f"[BSI INTEGRATION SINGLE] ✅ Loaded posterior-only BSI data for {patient_id} (Posterior BSI: {combined_bsi:.2f})")
            else:
                _log(f"[BSI INTEGRATION SINGLE] ✅ Loaded BSI data for {patient_id} (BSI: {combined_bsi:.2f})")
            
            return bsi_data
            
        except Exception as e:
            _log(f"[BSI INTEGRATION SINGLE] Error loading BSI data: {e}")
            return {
                "status": "error",
                "message": f"Error loading BSI data: {str(e)}"
            }
    
    def _extract_patient_info(self, scan_data: Dict, session_code: str = None) -> tuple[str, str]:
        """
        ✅ FIXED: Extract patient ID and study date using existing infrastructure
        """
        try:
            dicom_path = Path(scan_data["path"])
            print(f"[BSI EXTRACT INFO] Extracting from path: {dicom_path}")
            
            # ✅ REUSE: Use existing path extraction logic
            from core.config.paths import extract_study_date_from_dicom
            
            # Method 1: Extract study date from DICOM
            study_date = extract_study_date_from_dicom(dicom_path)
            print(f"[BSI EXTRACT INFO] Extracted study_date from DICOM: {study_date}")
            
            # Method 2: Extract patient ID from path structure
            patient_id = None
            
            # Check if we're in study_date folder structure
            if len(dicom_path.parent.name) == 8 and dicom_path.parent.name.isdigit():
                # Structure: .../patient_id/study_date/file.dcm
                patient_id = dicom_path.parent.parent.name
                print(f"[BSI EXTRACT INFO] Extracted patient_id from study_date structure: {patient_id}")
            else:
                # Structure: .../patient_id/file.dcm
                patient_id = dicom_path.parent.name
                print(f"[BSI EXTRACT INFO] Extracted patient_id from direct structure: {patient_id}")
            
            # Method 3: Fallback to DICOM content if path extraction fails
            if not patient_id or len(patient_id) == 8 and patient_id.isdigit():
                try:
                    import pydicom
                    ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
                    dicom_patient_id = str(ds.get("PatientID", ""))
                    
                    # Clean patient ID (remove session code if present)
                    if "_" in dicom_patient_id and session_code:
                        patient_id = dicom_patient_id.split("_")[0]
                    else:
                        patient_id = dicom_patient_id
                        
                    print(f"[BSI EXTRACT INFO] Fallback patient_id from DICOM: {patient_id}")
                    
                except Exception as e:
                    print(f"[BSI EXTRACT INFO] Could not read DICOM for patient info: {e}")
            
            print(f"[BSI EXTRACT INFO] Final result - Patient: {patient_id}, Study: {study_date}")
            return patient_id, study_date
            
        except Exception as e:
            print(f"[BSI EXTRACT INFO] Error extracting patient info: {e}")
            return None, None
    
    def get_current_patient_data(self) -> Optional[Dict[str, Any]]:
        """Get current patient data"""
        return self.current_patient_data
    
    def clear_current_patient_data(self):
        """Clear current patient data"""
        self.current_patient_data = None
    
    def check_quantification_status(self, scan_data: Dict, session_code: str = None) -> Dict[str, Any]:
        """
        Check quantification status for a patient without loading full data
        ✅ UPDATED: Now includes single view support information
        
        Args:
            scan_data: Timeline scan data
            session_code: Session code
            
        Returns:
            Dictionary with status information including processing mode
        """
        try:
            dicom_path = Path(scan_data["path"])
            patient_id, study_date = self._extract_patient_info(scan_data, session_code)
            
            if not patient_id or not study_date:
                return {
                    "has_quantification": False,
                    "status": "invalid_patient_info",
                    "message": "Could not extract patient information"
                }
            
            # Check quantification status (now supports single view)
            status = get_quantification_status(dicom_path, patient_id, study_date)
    
            return {
                "has_quantification": status.get("quantification_complete", False),
                "patient_id": patient_id,
                "study_date": study_date,
                "status": "checked",
                "bsi_score": status.get("bsi_score", 0.0),
                "total_abnormal_hotspots": status.get("total_abnormal_hotspots", 0),
                "quantification_file_exists": status.get("output_file_exists", False),
                "required_files_exist": status.get("required_files_exist", False),
                "missing_files": status.get("missing_files", []),
                # ✅ ADD: Forward BSI data dari get_quantification_status
                "anterior_bsi": status.get("anterior_bsi", 0.0),
                "posterior_bsi": status.get("posterior_bsi", 0.0),
                "combined_bsi": status.get("combined_bsi", 0.0),
                # ✅ NEW: Add single view support info
                "processing_mode": status.get("processing_mode", "unknown"),
                "v2_anterior_exists": status.get("v2_anterior_exists", False),
                "v2_posterior_exists": status.get("v2_posterior_exists", False),
                "has_anterior_pair": status.get("has_anterior_pair", False),
                "has_posterior_pair": status.get("has_posterior_pair", False),
                "can_run_quantification": status.get("can_run_quantification", False)
            }
            
        except Exception as e:
            return {
                "has_quantification": False,
                "status": "error",
                "message": f"Error checking quantification status: {str(e)}"
            }
    
    def get_bsi_summary_for_display(self, scan_data: Dict, session_code: str = None) -> Optional[str]:
        """
        Get BSI summary text for display in timeline cards
        
        Args:
            scan_data: Timeline scan data
            session_code: Session code
            
        Returns:
            BSI summary string or None if not available
        """
        try:
            status = self.check_quantification_status(scan_data, session_code)
            
            if not status.get("has_quantification", False):
                return None
            
            bsi_score = status.get("bsi_score", 0.0)
            abnormal_count = status.get("total_abnormal_hotspots", 0)
            
            # ✅ FIXED: Clean display without mode indicators
            return f"BSI: {bsi_score:.1f}% ({abnormal_count} abnormal)"
            
        except Exception as e:
            _log(f"[BSI INTEGRATION] Error getting BSI summary: {e}")
            return None
    
    def update_scan_meta_with_bsi(self, scan_data: Dict, session_code: str = None) -> Dict:
        """
        ✅ FIXED: Update scan metadata with BSI info using existing paths.py infrastructure
        """
        try:
            print(f"[BSI META INTEGRATION] Updating scan meta with BSI data")
            print(f"[BSI META INTEGRATION] Session code: {session_code}")
            print(f"[BSI META INTEGRATION] Scan path: {scan_data.get('path', 'UNKNOWN')}")
            
            # ✅ REUSE: Use existing quantification_integration infrastructure
            dicom_path = Path(scan_data["path"])
            
            # Extract patient info using existing logic
            patient_id, study_date = self._extract_patient_info(scan_data, session_code)
            print(f"[BSI META INTEGRATION] Extracted - Patient: {patient_id}, Study: {study_date}")
            
            if not patient_id or not study_date:
                print(f"[BSI META INTEGRATION] Could not extract patient info, no BSI meta added")
                if "meta" not in scan_data:
                    scan_data["meta"] = {}
                scan_data["meta"]["has_bsi"] = False
                return scan_data
            
            # ✅ REUSE: Use existing QuantificationManager to load BSI data
            from features.spect_viewer.logic.quantification_integration import QuantificationManager
            
            # Try to determine correct patient folder for BSI files
            patient_folder = None
            
            # Method 1: Check if DICOM is in study_date folder
            if len(dicom_path.parent.name) == 8 and dicom_path.parent.name.isdigit():
                # DICOM is in study_date folder: .../patient_id/study_date/file.dcm
                study_date_folder = dicom_path.parent
                patient_folder_candidate = study_date_folder.parent
                
                # Check if BSI files exist in study_date folder
                from core.config.paths import get_planar_quantification_files
                study_date_quant_files = get_planar_quantification_files(study_date_folder)
                
                if study_date_quant_files['bsi_json_ant'].exists() or study_date_quant_files['bsi_json_post'].exists():
                    print(f"[BSI META INTEGRATION] Found BSI files in study_date folder: {study_date_folder}")
                    patient_folder = study_date_folder
                else:
                    print(f"[BSI META INTEGRATION] No BSI files in study_date folder, trying patient folder: {patient_folder_candidate}")
                    patient_quant_files = get_planar_quantification_files(patient_folder_candidate)
                    if patient_quant_files['bsi_json_ant'].exists() or patient_quant_files['bsi_json_post'].exists():
                        patient_folder = patient_folder_candidate
            else:
                # DICOM is in patient folder directly
                patient_folder = dicom_path.parent
            
            if not patient_folder:
                print(f"[BSI META INTEGRATION] Could not determine patient folder with BSI files")
                if "meta" not in scan_data:
                    scan_data["meta"] = {}
                scan_data["meta"]["has_bsi"] = False
                return scan_data
            
            print(f"[BSI META INTEGRATION] Using patient folder: {patient_folder}")
            
            # ✅ REUSE: Load BSI scores using existing infrastructure
            manager = QuantificationManager()
            all_scores = manager.load_all_quantification_scores(patient_folder, patient_id)
            
            # Find scores for this study_date
            matching_scores = [score for score in all_scores if score.get("study_date") == study_date]
            
            if not matching_scores:
                print(f"[BSI META INTEGRATION] No BSI scores found for study_date: {study_date}")
                if "meta" not in scan_data:
                    scan_data["meta"] = {}
                scan_data["meta"]["has_bsi"] = False
                return scan_data
            
            # Get the BSI data for this study
            bsi_data = matching_scores[0]  # Should only be one per study_date
            
            print(f"[BSI META INTEGRATION] Found BSI data: {bsi_data}")
            
            # ✅ UPDATE: Add BSI info to meta
            if "meta" not in scan_data:
                scan_data["meta"] = {}
            
            scan_data["meta"]["has_bsi"] = True
            scan_data["meta"]["bsi_anterior"] = bsi_data.get("anterior_bsi", 0.0)
            scan_data["meta"]["bsi_posterior"] = bsi_data.get("posterior_bsi", 0.0)
            scan_data["meta"]["bsi_combined"] = bsi_data.get("combined_bsi", 0.0)  # For internal use only
            scan_data["meta"]["bsi_processing_mode"] = bsi_data.get("processing_mode", "unknown")
            scan_data["meta"]["bsi_file_source"] = bsi_data.get("file_source", "unknown")
            
            print(f"[BSI META INTEGRATION] ✅ Updated meta with BSI data:")
            print(f"[BSI META INTEGRATION]   Anterior BSI: {scan_data['meta']['bsi_anterior']}")
            print(f"[BSI META INTEGRATION]   Posterior BSI: {scan_data['meta']['bsi_posterior']}")
            print(f"[BSI META INTEGRATION]   Processing mode: {scan_data['meta']['bsi_processing_mode']}")
            
            return scan_data
            
        except Exception as e:
            print(f"[BSI META INTEGRATION] ❌ Error updating scan meta: {e}")
            import traceback
            traceback.print_exc()
            
            # Ensure meta exists even on error
            if "meta" not in scan_data:
                scan_data["meta"] = {}
            scan_data["meta"]["has_bsi"] = False
            return scan_data
    

# Global integration instance
bsi_timeline_integration = BSITimelineIntegration()


def get_bsi_integration() -> BSITimelineIntegration:
    """Get the global BSI timeline integration instance"""
    return bsi_timeline_integration


def load_bsi_for_selected_patient(scan_data: Dict, session_code: str = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to load BSI data for selected patient
    ✅ UPDATED: Now supports single view loading
    
    Args:
        scan_data: Timeline scan data
        session_code: Session code
        
    Returns:
        BSI data dictionary or None
    """
    integration = get_bsi_integration()
    return integration.get_patient_bsi_data(scan_data, session_code)


def check_patient_quantification_status(scan_data: Dict, session_code: str = None) -> Dict[str, Any]:
    """
    Convenience function to check quantification status
    ✅ UPDATED: Now includes single view support info
    
    Args:
        scan_data: Timeline scan data
        session_code: Session code
        
    Returns:
        Status dictionary with processing mode info
    """
    integration = get_bsi_integration()
    return integration.check_quantification_status(scan_data, session_code)


def update_timeline_scans_with_bsi(scans_data: list, session_code: str = None) -> list:
    """
    Update all timeline scans with BSI information
    ✅ UPDATED: Now includes single view processing mode info
    
    Args:
        scans_data: List of timeline scan data
        session_code: Session code
        
    Returns:
        Updated scans data with BSI information including processing modes
    """
    integration = get_bsi_integration()
    
    updated_scans = []
    for scan_data in scans_data:
        updated_scan = integration.update_scan_meta_with_bsi(scan_data, session_code)
        updated_scans.append(updated_scan)
    
    return updated_scans