# features/spect_viewer/logic/bsi_timeline_integration.py
"""
Integration logic for BSI quantification with timeline cards
Handles loading BSI data when patients are selected from timeline
"""
from pathlib import Path
from typing import Dict, Optional, Any
import json

from core.logger import _log
from core.config.paths import (
    extract_study_date_from_dicom,
    generate_filename_stem,
    get_patient_spect_path
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
    """
    
    def __init__(self):
        self.quant_manager = QuantificationManager()
        self.current_patient_data = None
        
    def get_patient_bsi_data(self, scan_data: Dict, session_code: str = None) -> Optional[Dict[str, Any]]:
        """
        Get BSI data for a patient from timeline scan data
        
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
                _log(f"[BSI INTEGRATION] Could not extract patient info from scan data")
                return None
            
            _log(f"[BSI INTEGRATION] Loading BSI data for patient {patient_id}, study {study_date}")
            
            # Check if quantification exists
            status = get_quantification_status(dicom_path, patient_id, study_date)
            
            if not status.get("quantification_complete", False):
                _log(f"[BSI INTEGRATION] No quantification data available for {patient_id}")
                return {
                    "patient_id": patient_id,
                    "study_date": study_date,
                    "patient_folder": patient_folder,
                    "status": "no_quantification",
                    "message": "Quantification not completed"
                }
            
            # Load quantification results
            results = self.quant_manager.load_quantification_results(patient_folder, patient_id, study_date)
            
            if not results:
                _log(f"[BSI INTEGRATION] Failed to load quantification results for {patient_id}")
                return {
                    "patient_id": patient_id,
                    "study_date": study_date,
                    "patient_folder": patient_folder,
                    "status": "load_error",
                    "message": "Failed to load quantification data"
                }
            
            # Get summary data
            summary_data = self.quant_manager.get_bsi_summary()
            
            bsi_data = {
                "patient_id": patient_id,
                "study_date": study_date,
                "patient_folder": patient_folder,
                "status": "success",
                "bsi_results": results.get('bsi_results', {}),
                "summary_data": summary_data,
                "raw_results": results
            }
            
            self.current_patient_data = bsi_data
            _log(f"[BSI INTEGRATION] Successfully loaded BSI data for {patient_id} (BSI: {summary_data.get('bsi_score', 0):.2f}%)")
            
            return bsi_data
            
        except Exception as e:
            _log(f"[BSI INTEGRATION] Error loading BSI data: {e}")
            return {
                "status": "error",
                "message": f"Error loading BSI data: {str(e)}"
            }
    
    def _extract_patient_info(self, scan_data: Dict, session_code: str = None) -> tuple[str, str]:
        """
        Extract patient ID and study date from scan data
        
        Args:
            scan_data: Timeline scan data
            session_code: Session code
            
        Returns:
            Tuple of (patient_id, study_date)
        """
        try:
            dicom_path = Path(scan_data["path"])
            
            # Method 1: Extract from path structure
            if session_code:
                # NEW structure: data/SPECT/[session_code]/[patient_id]/file.dcm
                parts = dicom_path.parts
                spect_index = None
                for i, part in enumerate(parts):
                    if part == "SPECT":
                        spect_index = i
                        break
                
                if spect_index and len(parts) > spect_index + 2:
                    path_session = parts[spect_index + 1]
                    path_patient = parts[spect_index + 2]
                    
                    if path_session == session_code:
                        patient_id = path_patient
                        
                        # Extract study date from DICOM
                        study_date = extract_study_date_from_dicom(dicom_path)
                        return patient_id, study_date
            
            # Method 2: Extract from meta data
            meta = scan_data.get("meta", {})
            patient_id = meta.get("patient_id")
            study_date = meta.get("study_date")
            
            if patient_id and study_date:
                return patient_id, study_date
            
            # Method 3: Extract from DICOM file directly
            try:
                import pydicom
                ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)
                dicom_patient_id = str(ds.get("PatientID", ""))
                dicom_study_date = extract_study_date_from_dicom(dicom_path)
                
                # Clean patient ID (remove session code if present)
                if "_" in dicom_patient_id and session_code:
                    clean_patient_id = dicom_patient_id.split("_")[0]
                else:
                    clean_patient_id = dicom_patient_id
                
                return clean_patient_id, dicom_study_date
                
            except Exception as e:
                _log(f"[BSI INTEGRATION] Could not read DICOM for patient info: {e}")
                return None, None
            
        except Exception as e:
            _log(f"[BSI INTEGRATION] Error extracting patient info: {e}")
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
        
        Args:
            scan_data: Timeline scan data
            session_code: Session code
            
        Returns:
            Dictionary with status information
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
            
            # Check quantification status
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
                "missing_files": status.get("missing_files", [])
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
            
            return f"BSI: {bsi_score:.1f}% ({abnormal_count} abnormal)"
            
        except Exception as e:
            _log(f"[BSI INTEGRATION] Error getting BSI summary: {e}")
            return None
    
    def update_scan_meta_with_bsi(self, scan_data: Dict, session_code: str = None) -> Dict:
        """
        Update scan metadata with BSI information for timeline display
        
        Args:
            scan_data: Timeline scan data
            session_code: Session code
            
        Returns:
            Updated scan data with BSI info
        """
        try:
            # Check quantification status
            status = self.check_quantification_status(scan_data, session_code)
            
            # Add BSI info to meta
            if "meta" not in scan_data:
                scan_data["meta"] = {}
            
            scan_data["meta"]["has_bsi"] = status.get("has_quantification", False)
            
            if status.get("has_quantification", False):
                scan_data["meta"]["bsi_score"] = status.get("bsi_score", 0.0)
                scan_data["meta"]["bsi_abnormal_count"] = status.get("total_abnormal_hotspots", 0)
                scan_data["meta"]["bsi_summary"] = self.get_bsi_summary_for_display(scan_data, session_code)
            
            return scan_data
            
        except Exception as e:
            _log(f"[BSI INTEGRATION] Error updating scan meta with BSI: {e}")
            return scan_data


# Global integration instance
bsi_timeline_integration = BSITimelineIntegration()


def get_bsi_integration() -> BSITimelineIntegration:
    """Get the global BSI timeline integration instance"""
    return bsi_timeline_integration


def load_bsi_for_selected_patient(scan_data: Dict, session_code: str = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to load BSI data for selected patient
    
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
    
    Args:
        scan_data: Timeline scan data
        session_code: Session code
        
    Returns:
        Status dictionary
    """
    integration = get_bsi_integration()
    return integration.check_quantification_status(scan_data, session_code)


def update_timeline_scans_with_bsi(scans_data: list, session_code: str = None) -> list:
    """
    Update all timeline scans with BSI information
    
    Args:
        scans_data: List of timeline scan data
        session_code: Session code
        
    Returns:
        Updated scans data with BSI information
    """
    integration = get_bsi_integration()
    
    updated_scans = []
    for scan_data in scans_data:
        updated_scan = integration.update_scan_meta_with_bsi(scan_data, session_code)
        updated_scans.append(updated_scan)
    
    return updated_scans