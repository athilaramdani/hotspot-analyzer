# test_cloud_connection.py
"""
Script untuk test koneksi BackBlaze B2 Cloud Storage
"""
import sys
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup logging BEFORE importing modules that use logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Import modules AFTER logging setup
from core.config.cloud_storage import cloud_storage, test_cloud_connection
from core.config.paths import validate_cloud_config, is_cloud_enabled

def main():
    """Test cloud storage connection and basic operations"""
    print("🚀 Testing BackBlaze B2 Cloud Storage Connection...")
    print("=" * 60)
    
    # 1. Check configuration
    print("1️⃣  Checking cloud configuration...")
    is_valid, message = validate_cloud_config()
    
    if not is_valid:
        print(f"❌ Configuration Error: {message}")
        print("\n💡 Make sure you have:")
        print("   - Created .env file with your BackBlaze credentials")
        print("   - Set CLOUD_SYNC_ENABLED=true")
        print("   - Installed required dependencies: pip install boto3 python-dotenv")
        return False
    
    print(f"✅ Configuration: {message}")
    print(f"   - Cloud sync enabled: {is_cloud_enabled()}")
    
    # 2. Test connection  
    print("\n2️⃣  Testing connection...")
    
    # Force connect first
    if cloud_storage.connect():
        print("✅ Connection successful!")
    else:
        print("❌ Connection failed!")
        return False
    
    # 3. Test file operations
    print("\n3️⃣  Testing file operations...")
    
    # Create test file
    test_file = project_root / "test_upload.txt"
    from datetime import datetime
    test_content = f"Test upload from {Path(__file__).name}\nTimestamp: {datetime.now().isoformat()}"
    
    try:
        test_file.write_text(test_content)
        print(f"📝 Created test file: {test_file}")
        
        # Test upload
        cloud_path = "test/test_upload.txt"
        if cloud_storage.upload_file(test_file, cloud_path):
            print(f"✅ Upload successful: {cloud_path}")
            
            # Test file exists
            if cloud_storage.file_exists(cloud_path):
                print("✅ File exists check successful")
            else:
                print("❌ File exists check failed")
                
            # Test download
            download_path = project_root / "test_download.txt"
            if cloud_storage.download_file(cloud_path, download_path):
                print(f"✅ Download successful: {download_path}")
                
                # Verify content
                downloaded_content = download_path.read_text()
                if downloaded_content == test_content:
                    print("✅ Content verification successful")
                else:
                    print("❌ Content verification failed")
                    print(f"   Expected: {test_content[:50]}...")
                    print(f"   Got: {downloaded_content[:50]}...")
                
                # Cleanup
                download_path.unlink()
                print("🧹 Cleaned up downloaded test file")
            else:
                print("❌ Download failed")
        else:
            print("❌ Upload failed")
            
        # Cleanup
        test_file.unlink()
        print("🧹 Cleaned up test file")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        # Cleanup on error
        if test_file.exists():
            test_file.unlink()
        return False
    
    # 4. Test list files
    print("\n4️⃣  Testing list files...")
    try:
        files = cloud_storage.list_files("test/", max_keys=10)
        print(f"✅ Found {len(files)} files in test/ folder")
        for file in files[:5]:  # Show first 5 files
            print(f"   📄 {file}")
        if len(files) > 5:
            print(f"   ... and {len(files) - 5} more files")
    except Exception as e:
        print(f"❌ List files failed: {e}")
    
    # 5. Test SPECT data sync (dry run)
    print("\n5️⃣  Testing SPECT data sync functions...")
    try:
        from core.config.cloud_storage import sync_spect_data
        from core.config.paths import SPECT_DATA_PATH
        
        print(f"📁 Local SPECT path: {SPECT_DATA_PATH}")
        
        if SPECT_DATA_PATH.exists():
            # Count local files
            local_files = list(SPECT_DATA_PATH.rglob("*"))
            local_file_count = len([f for f in local_files if f.is_file()])
            print(f"📊 Found {local_file_count} local files in SPECT data")
            
            if local_file_count > 0:
                print("💡 You can sync SPECT data using: sync_spect_data()")
            else:
                print("💡 No SPECT data to sync yet")
        else:
            print("📂 SPECT data folder doesn't exist yet")
            
    except Exception as e:
        print(f"⚠️  SPECT sync test failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 All tests completed successfully!")
    print("\n💡 Next steps:")
    print("   1. Your BackBlaze B2 connection is working!")
    print("   2. You can now integrate cloud sync into your application")
    print("   3. Use sync_spect_data() to sync patient data")
    print("   4. Test with real SPECT data when available")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)