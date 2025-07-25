#!/usr/bin/env python3
"""
Migration script to rename files from old naming convention to new naming convention with study date.

OLD: patient_id_view_type.ext
NEW: patient_id_studydate_view_type.ext

Example:
OLD: 1300_anterior_mask.png
NEW: 1300_20250627_anterior_mask.png
"""

import os
import sys
from pathlib import Path
from typing import List, Tuple
import pydicom
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from core.config.paths import (
    SPECT_DATA_PATH,
    extract_study_date_from_dicom,
    generate_filename_stem
)


def extract_study_date_from_any_dicom(directory: Path) -> str:
    """Extract study date from any DICOM file in directory"""
    try:
        # Find primary DICOM files (not processed ones)
        dicom_files = list(directory.glob("*.dcm"))
        
        for dicom_file in dicom_files:
            # Skip processed files
            if any(skip in dicom_file.name.lower() for skip in ['mask', 'colored', '_ant_', '_post_', 'edited']):
                continue
                
            try:
                study_date = extract_study_date_from_dicom(dicom_file)
                print(f"  ✓ Extracted study date {study_date} from {dicom_file.name}")
                return study_date
            except Exception as e:
                print(f"  ⚠️ Could not extract from {dicom_file.name}: {e}")
                continue
        
        # If no primary DICOM found, try any DICOM
        for dicom_file in dicom_files:
            try:
                study_date = extract_study_date_from_dicom(dicom_file)
                print(f"  ✓ Extracted study date {study_date} from {dicom_file.name} (fallback)")
                return study_date
            except Exception:
                continue
                
        # Final fallback
        fallback_date = datetime.now().strftime("%Y%m%d")
        print(f"  ❌ No valid DICOM found, using current date: {fallback_date}")
        return fallback_date
        
    except Exception as e:
        print(f"  ❌ Failed to extract study date: {e}")
        fallback_date = datetime.now().strftime("%Y%m%d")
        print(f"  ❌ Using current date: {fallback_date}")
        return fallback_date


def is_already_migrated(filename: str, patient_id: str) -> bool:
    """Check if filename already follows new naming convention"""
    try:
        # Check if filename starts with patient_id_YYYYMMDD pattern
        if not filename.startswith(f"{patient_id}_"):
            return False
            
        parts = filename.split("_")
        if len(parts) < 2:
            return False
            
        # Check if second part is 8-digit date
        date_part = parts[1]
        if len(date_part) == 8 and date_part.isdigit():
            # Validate if it's a reasonable date
            year = int(date_part[:4])
            month = int(date_part[4:6])
            day = int(date_part[6:8])
            
            if 2020 <= year <= 2030 and 1 <= month <= 12 and 1 <= day <= 31:
                return True
                
        return False
        
    except (ValueError, IndexError):
        return False


def generate_new_filename(old_filename: str, patient_id: str, study_date: str) -> str:
    """Generate new filename with study date"""
    try:
        # Remove patient_id prefix if it exists
        if old_filename.startswith(f"{patient_id}_"):
            remaining = old_filename[len(patient_id) + 1:]
        else:
            remaining = old_filename
            
        # Generate new filename with study date
        new_filename = f"{patient_id}_{study_date}_{remaining}"
        return new_filename
        
    except Exception as e:
        print(f"    ❌ Error generating new filename for {old_filename}: {e}")
        return old_filename


def migrate_patient_directory(patient_dir: Path, dry_run: bool = True) -> Tuple[int, int]:
    """Migrate all files in a patient directory"""
    print(f"\n📁 Processing: {patient_dir}")
    
    patient_id = patient_dir.name
    
    # Extract study date from DICOM files
    study_date = extract_study_date_from_any_dicom(patient_dir)
    print(f"  📅 Study date: {study_date}")
    
    migrated_count = 0
    skipped_count = 0
    
    # Process all files in directory
    for file_path in patient_dir.iterdir():
        if not file_path.is_file():
            continue
            
        old_filename = file_path.name
        
        # Skip if already migrated
        if is_already_migrated(old_filename, patient_id):
            print(f"    ⏭️  Already migrated: {old_filename}")
            skipped_count += 1
            continue
        
        # Generate new filename
        new_filename = generate_new_filename(old_filename, patient_id, study_date)
        
        if new_filename == old_filename:
            print(f"    ⏭️  No change needed: {old_filename}")
            skipped_count += 1
            continue
            
        new_file_path = patient_dir / new_filename
        
        # Check if target already exists
        if new_file_path.exists():
            print(f"    ❌ Target exists: {old_filename} → {new_filename}")
            skipped_count += 1
            continue
            
        print(f"    🔄 {old_filename} → {new_filename}")
        
        if not dry_run:
            try:
                file_path.rename(new_file_path)
                print(f"    ✅ Renamed successfully")
                migrated_count += 1
            except Exception as e:
                print(f"    ❌ Failed to rename: {e}")
                skipped_count += 1
        else:
            print(f"    📝 Would rename (dry run)")
            migrated_count += 1
    
    return migrated_count, skipped_count


def migrate_session_directory(session_dir: Path, dry_run: bool = True) -> Tuple[int, int]:
    """Migrate all patient directories in a session"""
    print(f"\n🏥 Processing session: {session_dir.name}")
    
    total_migrated = 0
    total_skipped = 0
    
    patient_dirs = [d for d in session_dir.iterdir() if d.is_dir()]
    
    if not patient_dirs:
        print(f"  ⚠️ No patient directories found in {session_dir}")
        return 0, 0
    
    for patient_dir in patient_dirs:
        migrated, skipped = migrate_patient_directory(patient_dir, dry_run)
        total_migrated += migrated
        total_skipped += skipped
    
    return total_migrated, total_skipped


def migrate_all_files(dry_run: bool = True, session_filter: str = None):
    """Migrate all files in SPECT data directory"""
    print("🚀 Starting file migration to include study date in filenames")
    print(f"📂 Target directory: {SPECT_DATA_PATH}")
    
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
    else:
        print("⚠️  LIVE MODE - Files will be renamed")
    
    if not SPECT_DATA_PATH.exists():
        print(f"❌ SPECT data directory not found: {SPECT_DATA_PATH}")
        return
    
    total_migrated = 0
    total_skipped = 0
    
    # Get all session directories
    session_dirs = [d for d in SPECT_DATA_PATH.iterdir() if d.is_dir()]
    
    if session_filter:
        session_dirs = [d for d in session_dirs if d.name == session_filter]
        print(f"🔍 Filtering to session: {session_filter}")
    
    if not session_dirs:
        print("❌ No session directories found")
        return
    
    print(f"📋 Found {len(session_dirs)} session(s) to process")
    
    # Process each session
    for session_dir in session_dirs:
        migrated, skipped = migrate_session_directory(session_dir, dry_run)
        total_migrated += migrated
        total_skipped += skipped
    
    # Summary
    print(f"\n📊 Migration Summary:")
    print(f"  ✅ Files migrated: {total_migrated}")
    print(f"  ⏭️  Files skipped: {total_skipped}")
    print(f"  📁 Total processed: {total_migrated + total_skipped}")
    
    if dry_run:
        print(f"\n💡 To actually perform the migration, run with dry_run=False")
    else:
        print(f"\n🎉 Migration completed!")


def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate DICOM filenames to include study date')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Run in dry-run mode (default: True)')
    parser.add_argument('--live', action='store_true',
                       help='Run in live mode (actually rename files)')
    parser.add_argument('--session', type=str,
                       help='Process only specific session (e.g., NSY, ATL, NBL)')
    
    args = parser.parse_args()
    
    # Determine run mode
    dry_run = not args.live
    
    if args.live:
        response = input("⚠️  You are about to rename files in LIVE mode. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Migration cancelled")
            return
    
    # Run migration
    migrate_all_files(dry_run=dry_run, session_filter=args.session)


if __name__ == "__main__":
    main()