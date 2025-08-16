# =====================================================================
# features\dicom_import\logic\directory_scanner.py
# ---------------------------------------------------------------------
"""
Pindai folder `data/…` dan kembalikan mapping untuk NEW directory structure:
    {SessionCode: {PatientID: [daftar-file scan (*.dcm)]}}

NEW Structure: data/SPECT/[session_code]/[patient_id]/files...
OLD Structure: data/SPECT/[patient_id]_[session_code]/files...

✅ FIXED: Hapus filtering _is_primary() - baca semua DICOM input tanpa filter
✅ FIXED: Tidak ada pembedaan primary/secondary - semua DICOM dibaca
"""
from pathlib import Path
from typing  import Dict, List, Tuple

import pydicom

# Use centralized path configuration
from core.config.paths import PLANAR_DATA_PATH, get_patient_planar_path, get_session_planar_path

# ✅ REMOVED: _UID_SC constant and _is_primary() function
# No more filtering - read all DICOM files

# ---------------------------------------------------------------- helpers
def _extract_session_patient_from_path(dicom_path: Path) -> Tuple[str, str]:
    try:
        parts = dicom_path.parts
        
        # Find PLANAR directory index
        planar_index = None
        for i, part in enumerate(parts):
            if part == "PLANAR":
                planar_index = i
                break
        
        if planar_index is not None and len(parts) > planar_index + 2:
            session_code = parts[planar_index + 1]
            patient_id = parts[planar_index + 2]
            
            # Validate if this looks like new structure (no underscore in session_code for patient_id)
            if "_" not in patient_id or session_code in ["NSY", "ATL", "NBL"]:
                return session_code, patient_id
        
        # Check for OLD structure: [patient_id]_[session_code]
        if planar_index is not None and len(parts) > planar_index + 1:
            folder_name = parts[planar_index + 1]
            if "_" in folder_name:
                parts_old = folder_name.split("_")
                if len(parts_old) >= 2:
                    patient_id = parts_old[0]
                    session_code = "_".join(parts_old[1:])
                    return session_code, patient_id
        
        # Fallback
        parent_name = dicom_path.parent.name
        return "UNKNOWN", parent_name
        
    except Exception:
        return "UNKNOWN", "UNKNOWN"

# ---------------------------------------------------------------- main scanning functions

def scan_dicom_directory(directory: Path) -> Dict[str, List[Path]]:
    """
    ✅ FIXED: Scan directory without any filtering
    Returns: {PatientID: [file_paths]}
    """
    patient_map: Dict[str, List[Path]] = {}

    dicoms = list(directory.glob("**/*.dcm"))
    print(f"Ditemukan {len(dicoms)} file DICOM di '{directory}'")

    for p in dicoms:
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True)
        except Exception as e:
            print(f"[WARN] Tidak bisa baca {p}: {e}")
            continue

        # ✅ REMOVED: _is_primary() filter
        # Read ALL DICOM files without any filtering

        pid = ds.get("PatientID")
        if not pid:
            continue

        patient_map.setdefault(pid, []).append(p)

    total_scans = sum(len(v) for v in patient_map.values())
    print(f"Ditemukan {len(patient_map)} ID pasien (total {total_scans} file DICOM).")
    return patient_map

def scan_spect_directory_new_structure(directory: Path = None) -> Dict[str, Dict[str, List[Path]]]:
    """
    ✅ FIXED: Scan SPECT directory with NEW structure - NO FILTERING
    Returns: {SessionCode: {PatientID: [file_paths]}}
    """
    if directory is None:
        directory = PLANAR_DATA_PATH
    
    session_patient_map: Dict[str, Dict[str, List[Path]]] = {}
    
    if not directory.exists():
        print(f"Directory tidak ditemukan: {directory}")
        return session_patient_map

    dicoms = list(directory.glob("**/*.dcm"))
    print(f"Ditemukan {len(dicoms)} file DICOM di '{directory}'")

    for p in dicoms:
        try:
            ds = pydicom.dcmread(p, stop_before_pixels=True)
        except Exception as e:
            print(f"[WARN] Tidak bisa baca {p}: {e}")
            continue

        # ✅ REMOVED: _is_primary() filter
        # Read ALL DICOM files without any filtering

        pid = ds.get("PatientID")
        if not pid:
            continue

        # Extract session and patient from path
        session_code, path_patient_id = _extract_session_patient_from_path(p)
        
        # Use path-based patient ID if available, otherwise use DICOM PatientID
        final_patient_id = path_patient_id if path_patient_id != "UNKNOWN" else pid

        # Initialize nested dict structure
        if session_code not in session_patient_map:
            session_patient_map[session_code] = {}
        
        if final_patient_id not in session_patient_map[session_code]:
            session_patient_map[session_code][final_patient_id] = []
        
        session_patient_map[session_code][final_patient_id].append(p)

    # Print summary
    total_sessions = len(session_patient_map)
    total_patients = sum(len(patients) for patients in session_patient_map.values())
    total_scans = sum(len(files) for patients in session_patient_map.values() 
                     for files in patients.values())
    
    print(f"Ditemukan {total_sessions} session, {total_patients} pasien (total {total_scans} file DICOM).")
    
    # Print detailed breakdown
    for session_code, patients in session_patient_map.items():
        patient_count = len(patients)
        scan_count = sum(len(files) for files in patients.values())
        print(f"  📁 {session_code}: {patient_count} pasien, {scan_count} file")
    
    return session_patient_map

def get_session_patients(session_code: str) -> Dict[str, List[Path]]:
    """
    ✅ FIXED: Get all patients and their files for a specific session - NO FILTERING
    Returns: {PatientID: [file_paths]}
    """
    session_path = get_session_planar_path(session_code)
    
    if not session_path.exists():
        print(f"Session directory tidak ditemukan: {session_path}")
        return {}
    
    patient_map: Dict[str, List[Path]] = {}
    
    # Scan each patient directory in the session
    for patient_dir in session_path.iterdir():
        if not patient_dir.is_dir():
            continue
            
        patient_id = patient_dir.name
        patient_files = []
        
        # Find all DICOM files for this patient
        for dicom_file in patient_dir.glob("*.dcm"):
            try:
                # ✅ REMOVED: _is_primary() check
                # Add ALL DICOM files
                ds = pydicom.dcmread(dicom_file, stop_before_pixels=True)
                patient_files.append(dicom_file)
            except Exception as e:
                print(f"[WARN] Tidak bisa baca {dicom_file}: {e}")
                continue
        
        if patient_files:
            patient_map[patient_id] = patient_files
    
    return patient_map

def get_all_sessions() -> List[str]:
    """
    Get list of all available session codes
    Returns: [session_code1, session_code2, ...]
    """
    if not PLANAR_DATA_PATH.exists():
        return []
    
    sessions = []
    for item in PLANAR_DATA_PATH.iterdir():
        if item.is_dir():
            # Check if this is a session directory (contains patient subdirectories)
            has_patients = any(subitem.is_dir() for subitem in item.iterdir())
            if has_patients:
                sessions.append(item.name)
    
    return sorted(sessions)

def get_patient_files(session_code: str, patient_id: str) -> List[Path]:
    """
    Get all files for a specific patient in a session
    Returns: [file_path1, file_path2, ...]
    """
    patient_path = get_patient_planar_path(patient_id, session_code)
    
    if not patient_path.exists():
        return []
    
    files = []
    for file_path in patient_path.glob("*"):
        if file_path.is_file():
            files.append(file_path)
    
    return sorted(files)

def get_patient_dicom_files(session_code: str, patient_id: str, primary_only: bool = True) -> List[Path]:
    """
    ✅ FIXED: Get DICOM files for a specific patient - NO FILTERING
    
    Args:
        session_code: Session code (NSY, ATL, NBL, etc.)
        patient_id: Patient ID
        primary_only: IGNORED - all DICOM files returned
        
    Returns:
        List of DICOM file paths
    """
    patient_path = get_patient_planar_path(patient_id, session_code)
    
    if not patient_path.exists():
        return []
    
    dicom_files = []
    for dicom_file in patient_path.glob("*.dcm"):
        try:
            # ✅ REMOVED: _is_primary() check
            # Return ALL DICOM files regardless of primary_only parameter
            ds = pydicom.dcmread(dicom_file, stop_before_pixels=True)
            dicom_files.append(dicom_file)
        except Exception as e:
            print(f"[WARN] Tidak bisa baca {dicom_file}: {e}")
            continue
    
    return sorted(dicom_files)

def scan_and_migrate_old_structure() -> Dict[str, Dict[str, List[Path]]]:
    """
    Scan directory and migrate old structure to new structure if needed
    Returns: Session-Patient mapping with new structure
    """
    # First, try to migrate old structure
    from core.config.paths import migrate_old_to_new_structure
    try:
        migrate_old_to_new_structure()
    except Exception as e:
        print(f"[WARN] Migration failed: {e}")
    
    # Then scan with new structure
    return scan_spect_directory_new_structure()

def validate_directory_structure() -> bool:
    """
    Validate if the directory structure is correct
    Returns True if structure is valid
    """
    try:
        if not PLANAR_DATA_PATH.exists():
            print("❌ SPECT data directory does not exist")
            return False
        
        sessions = get_all_sessions()
        if not sessions:
            print("⚠️  No sessions found")
            return True  # Empty is valid
        
        print(f"✅ Found {len(sessions)} sessions: {', '.join(sessions)}")
        
        # Check each session
        for session in sessions:
            session_path = get_session_planar_path(session)
            patients = get_session_patients(session)
            print(f"  📁 {session}: {len(patients)} patients")
            
            # Check if any patients have files
            total_files = sum(len(files) for files in patients.values())
            if total_files == 0:
                print(f"  ⚠️  Session {session} has no DICOM files")
        
        return True
        
    except Exception as e:
        print(f"❌ Directory validation failed: {e}")
        return False

# Compatibility functions for old code
def scan_dicom_directory_legacy(directory: Path) -> Dict[str, List[Path]]:
    """
    Legacy function for backward compatibility
    Converts new structure results to old format
    """
    new_structure = scan_spect_directory_new_structure(directory)
    
    # Flatten to old format: {PatientID: [files]}
    legacy_format: Dict[str, List[Path]] = {}
    
    for session_code, patients in new_structure.items():
        for patient_id, files in patients.items():
            # Use patient_id_session_code as key for uniqueness
            key = f"{patient_id}_{session_code}"
            legacy_format[key] = files
    
    return legacy_format

def scan_planar_directory_new_structure(planar_data_path):
    """Alias for PLANAR scanning - same logic as SPECT"""
    return scan_spect_directory_new_structure(planar_data_path)