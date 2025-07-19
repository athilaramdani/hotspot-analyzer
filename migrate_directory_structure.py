# migrate_directory_structure.py
"""
Script untuk migrasi struktur direktori dari old ke new format

OLD: data/SPECT/[patient_id]_[session_code]/files...
NEW: data/SPECT/[session_code]/[patient_id]/files...
"""

import sys
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config.paths import SPECT_DATA_PATH, get_patient_spect_path, get_session_spect_path
from core.config.cloud_storage import sync_spect_data, cloud_storage

def migrate_directory_structure(dry_run: bool = True):
    """
    Migrate old directory structure to new structure
    
    Args:
        dry_run: If True, only show what would be migrated without actually doing it
    """
    print("🔄 Directory Structure Migration")
    print("=" * 50)
    print(f"Source: {SPECT_DATA_PATH}")
    print(f"Mode: {'DRY RUN' if dry_run else 'ACTUAL MIGRATION'}")
    print()
    
    if not SPECT_DATA_PATH.exists():
        print("❌ SPECT data directory does not exist")
        return
    
    # Find all old-style directories
    old_directories = []
    new_directories = []
    
    for item in SPECT_DATA_PATH.iterdir():
        if item.is_dir():
            if "_" in item.name:
                # Check if it's old format by looking for patient_id_session_code pattern
                parts = item.name.split("_")
                if len(parts) >= 2:
                    # This could be old format
                    old_directories.append(item)
            else:
                # This looks like new format (just session code)
                new_directories.append(item)
    
    print(f"📂 Found {len(old_directories)} old-format directories")
    print(f"📁 Found {len(new_directories)} new-format directories")
    print()
    
    if not old_directories:
        print("✅ No migration needed - all directories are already in new format")
        return
    
    migrated_count = 0
    failed_count = 0
    
    for old_dir in old_directories:
        try:
            # Parse old directory name
            parts = old_dir.name.split("_")
            patient_id = parts[0]
            session_code = "_".join(parts[1:])  # Handle multi-part session codes
            
            # Create new path
            new_path = get_patient_spect_path(patient_id, session_code)
            
            print(f"📦 {old_dir.name}")
            print(f"  Patient ID: {patient_id}")
            print(f"  Session: {session_code}")
            print(f"  Old path: {old_dir}")
            print(f"  New path: {new_path}")
            
            if new_path.exists():
                print(f"  ⚠️  Target already exists - skipping")
                continue
            
            if not dry_run:
                # Create parent directory
                new_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Move directory
                shutil.move(str(old_dir), str(new_path))
                print(f"  ✅ Migrated successfully")
                migrated_count += 1
            else:
                print(f"  🔍 Would migrate (dry run)")
                migrated_count += 1
            
            print()
                
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed_count += 1
            print()
    
    print("=" * 50)
    print("📊 Migration Summary:")
    print(f"  ✅ Successfully migrated: {migrated_count}")
    print(f"  ❌ Failed: {failed_count}")
    
    if dry_run:
        print(f"\n💡 This was a dry run. To perform actual migration, run:")
        print(f"   python migrate_directory_structure.py --migrate")
    else:
        print(f"\n🎉 Migration completed!")
        
        # Sync to cloud if available
        if cloud_storage.is_connected or cloud_storage.connect():
            print(f"\n☁️  Syncing to cloud storage...")
            try:
                uploaded, downloaded = sync_spect_data()
                print(f"   ✅ Cloud sync: {uploaded} uploaded, {downloaded} downloaded")
            except Exception as e:
                print(f"   ❌ Cloud sync failed: {e}")

def validate_migration():
    """Validate that migration was successful"""
    print("\n🔍 Validating Migration...")
    
    from core.config.paths import validate_paths
    from features.dicom_import.logic.directory_scanner import (
        scan_spect_directory_new_structure, 
        validate_directory_structure
    )
    
    try:
        # Validate paths
        validate_paths()
        print("✅ Path validation passed")
        
        # Validate directory structure
        if validate_directory_structure():
            print("✅ Directory structure validation passed")
        else:
            print("❌ Directory structure validation failed")
            return False
        
        # Scan with new structure
        session_patient_map = scan_spect_directory_new_structure()
        
        total_sessions = len(session_patient_map)
        total_patients = sum(len(patients) for patients in session_patient_map.values())
        total_files = sum(len(files) for patients in session_patient_map.values() 
                         for files in patients.values())
        
        print(f"📊 Scan Results:")
        print(f"  📁 Sessions: {total_sessions}")
        print(f"  👥 Patients: {total_patients}")
        print(f"  📄 Files: {total_files}")
        
        # Show breakdown by session
        for session_code, patients in session_patient_map.items():
            patient_count = len(patients)
            file_count = sum(len(files) for files in patients.values())
            print(f"    {session_code}: {patient_count} patients, {file_count} files")
        
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False

def backup_before_migration():
    """Create backup before migration"""
    print("💾 Creating backup before migration...")
    
    backup_dir = SPECT_DATA_PATH.parent / "SPECT_backup"
    
    if backup_dir.exists():
        print(f"⚠️  Backup directory already exists: {backup_dir}")
        response = input("Do you want to overwrite? (y/N): ")
        if response.lower() != 'y':
            print("❌ Migration cancelled")
            return False
        shutil.rmtree(backup_dir)
    
    try:
        shutil.copytree(SPECT_DATA_PATH, backup_dir)
        print(f"✅ Backup created: {backup_dir}")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def main():
    """Main migration function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Migrate SPECT directory structure")
    parser.add_argument("--migrate", action="store_true", 
                       help="Perform actual migration (default is dry run)")
    parser.add_argument("--backup", action="store_true",
                       help="Create backup before migration")
    parser.add_argument("--validate", action="store_true",
                       help="Only validate current structure")
    parser.add_argument("--force", action="store_true",
                       help="Skip confirmation prompts")
    
    args = parser.parse_args()
    
    if args.validate:
        validate_migration()
        return
    
    # Show current structure first
    print("🔍 Current Structure Analysis:")
    try:
        from features.dicom_import.logic.directory_scanner import scan_spect_directory_new_structure
        current_structure = scan_spect_directory_new_structure()
        
        if current_structure:
            print("📁 Found existing structure:")
            for session, patients in current_structure.items():
                print(f"  {session}: {len(patients)} patients")
        else:
            print("📂 No existing structure found")
    except Exception as e:
        print(f"⚠️  Could not analyze current structure: {e}")
    
    print()
    
    # Perform migration
    if args.migrate:
        if not args.force:
            print("⚠️  This will perform ACTUAL migration of your directory structure.")
            print("📁 OLD: data/SPECT/[patient_id]_[session_code]/")
            print("📂 NEW: data/SPECT/[session_code]/[patient_id]/")
            print()
            response = input("Do you want to continue? (y/N): ")
            if response.lower() != 'y':
                print("❌ Migration cancelled")
                return
        
        # Create backup if requested
        if args.backup:
            if not backup_before_migration():
                return
        
        # Perform migration
        migrate_directory_structure(dry_run=False)
        
        # Validate migration
        print("\n" + "="*50)
        validate_migration()
        
    else:
        # Dry run by default
        migrate_directory_structure(dry_run=True)

if __name__ == "__main__":
    main()