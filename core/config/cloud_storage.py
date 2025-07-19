# core/config/cloud_storage.py
"""
Cloud Storage Manager untuk BackBlaze B2 - Updated untuk New Directory Structure
"""
import boto3
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from botocore.exceptions import ClientError, NoCredentialsError
from datetime import datetime

from .paths import (
    B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_ENDPOINT,
    is_cloud_enabled, get_cloud_path, get_local_path_from_cloud,
    PROJECT_ROOT, get_cloud_spect_path, get_cloud_pet_path,
    SPECT_DATA_PATH, PET_DATA_PATH
)

# Setup logging
logger = logging.getLogger(__name__)

class CloudStorageManager:
    """Manager untuk operasi cloud storage dengan BackBlaze B2"""
    
    def __init__(self):
        self.client = None
        self.bucket_name = B2_BUCKET_NAME
        self.is_connected = False
        
    def connect(self) -> bool:
        """Establish connection to BackBlaze B2"""
        try:
            if not is_cloud_enabled():
                logger.warning("Cloud storage is not enabled or configured")
                return False
                
            self.client = boto3.client(
                's3',
                endpoint_url=B2_ENDPOINT,
                aws_access_key_id=B2_KEY_ID,
                aws_secret_access_key=B2_APPLICATION_KEY
            )
            
            # Test connection
            if self.test_connection():
                self.is_connected = True
                logger.info("Successfully connected to BackBlaze B2")
                return True
            else:
                self.is_connected = False
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to BackBlaze B2: {e}")
            self.is_connected = False
            return False
    
    def test_connection(self) -> bool:
        """Test connection to BackBlaze B2"""
        try:
            if not self.client:
                return False
                
            # Try to list bucket contents (limit to 1 item)
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            
            logger.info("✅ Connection test successful")
            return True
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            logger.error(f"❌ Connection test failed: {error_code} - {e}")
            return False
        except NoCredentialsError:
            logger.error("❌ Invalid credentials")
            return False
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def upload_file(self, local_path: Path, cloud_path: str = None, 
                   preserve_original: bool = True) -> bool:
        """
        Upload file to cloud storage
        
        Args:
            local_path: Path to local file
            cloud_path: Optional cloud storage path (auto-generated if None)
            preserve_original: Keep original file after upload
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_connected:
                if not self.connect():
                    return False
            
            if not local_path.exists():
                logger.error(f"Local file does not exist: {local_path}")
                return False
            
            # Generate cloud path if not provided
            if cloud_path is None:
                cloud_path = get_cloud_path(local_path)
            
            # Upload file
            self.client.upload_file(
                str(local_path),
                self.bucket_name,
                cloud_path
            )
            
            logger.info(f"✅ Uploaded: {local_path} → {cloud_path}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ Upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            return False
    
    def download_file(self, cloud_path: str, local_path: Path = None,
                     create_dirs: bool = True) -> bool:
        """
        Download file from cloud storage
        
        Args:
            cloud_path: Path in cloud storage
            local_path: Local destination path (auto-generated if None)
            create_dirs: Create parent directories if they don't exist
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_connected:
                if not self.connect():
                    return False
            
            # Generate local path if not provided
            if local_path is None:
                local_path = get_local_path_from_cloud(cloud_path)
            
            # Create parent directories if needed
            if create_dirs:
                local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download file
            self.client.download_file(
                self.bucket_name,
                cloud_path,
                str(local_path)
            )
            
            logger.info(f"✅ Downloaded: {cloud_path} → {local_path}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ Download failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Download failed: {e}")
            return False
    
    def file_exists(self, cloud_path: str) -> bool:
        """Check if file exists in cloud storage"""
        try:
            if not self.is_connected:
                if not self.connect():
                    return False
            
            self.client.head_object(Bucket=self.bucket_name, Key=cloud_path)
            return True
            
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == '404':
                return False
            logger.error(f"Error checking file existence: {e}")
            return False
        except Exception as e:
            logger.error(f"Error checking file existence: {e}")
            return False
    
    def list_files(self, prefix: str = "", max_keys: int = 1000) -> List[str]:
        """List files in cloud storage with optional prefix"""
        try:
            if not self.is_connected:
                if not self.connect():
                    return []
            
            response = self.client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            if 'Contents' in response:
                files = [obj['Key'] for obj in response['Contents']]
            
            return files
            
        except ClientError as e:
            logger.error(f"Error listing files: {e}")
            return []
        except Exception as e:
            logger.error(f"Error listing files: {e}")
            return []
    
    def sync_folder(self, local_folder: Path, cloud_prefix: str = "",
                   upload_only: bool = False) -> Tuple[int, int]:
        """
        Sync folder with cloud storage
        
        Args:
            local_folder: Local folder to sync
            cloud_prefix: Prefix for cloud storage paths
            upload_only: Only upload, don't download
            
        Returns:
            Tuple of (uploaded_count, downloaded_count)
        """
        uploaded = 0
        downloaded = 0
        
        try:
            if not self.is_connected:
                if not self.connect():
                    return (0, 0)
            
            if not local_folder.exists():
                logger.error(f"Local folder does not exist: {local_folder}")
                return (0, 0)
            
            # Upload local files that are missing or newer in cloud
            for local_file in local_folder.rglob("*"):
                if local_file.is_file():
                    rel_path = local_file.relative_to(local_folder)
                    cloud_path = f"{cloud_prefix}/{rel_path}".replace("\\", "/")
                    
                    if not self.file_exists(cloud_path):
                        if self.upload_file(local_file, cloud_path):
                            uploaded += 1
            
            # Download cloud files that are missing locally (if not upload_only)
            if not upload_only:
                cloud_files = self.list_files(cloud_prefix)
                for cloud_file in cloud_files:
                    if cloud_file.startswith(cloud_prefix):
                        rel_path = cloud_file[len(cloud_prefix):].lstrip("/")
                        local_file = local_folder / rel_path
                        
                        if not local_file.exists():
                            if self.download_file(cloud_file, local_file):
                                downloaded += 1
            
            logger.info(f"Sync completed: {uploaded} uploaded, {downloaded} downloaded")
            return (uploaded, downloaded)
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return (uploaded, downloaded)
    
    def backup_with_timestamp(self, local_path: Path, backup_prefix: str = "backups") -> bool:
        """Create timestamped backup of file"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = local_path.name
            cloud_path = f"{backup_prefix}/{timestamp}_{filename}"
            
            return self.upload_file(local_path, cloud_path)
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return False

    # ===== NEW DIRECTORY STRUCTURE METHODS =====
    
    def sync_patient_data(self, session_code: str, patient_id: str = None, 
                         modality: str = "SPECT") -> Tuple[int, int]:
        """
        Sync specific patient data with new directory structure
        
        Args:
            session_code: Session/doctor code (NSY, ATL, NBL)
            patient_id: Patient ID (optional, sync all if None)
            modality: SPECT or PET
            
        Returns:
            Tuple of (uploaded_count, downloaded_count)
        """
        try:
            if modality.upper() == "SPECT":
                if patient_id:
                    from .paths import get_patient_spect_path
                    local_folder = get_patient_spect_path(patient_id, session_code)
                    cloud_prefix = get_cloud_spect_path(session_code, patient_id)
                else:
                    from .paths import get_session_spect_path
                    local_folder = get_session_spect_path(session_code)
                    cloud_prefix = get_cloud_spect_path(session_code)
            else:  # PET
                if patient_id:
                    from .paths import get_patient_pet_path
                    local_folder = get_patient_pet_path(patient_id, session_code)
                    cloud_prefix = get_cloud_pet_path(patient_id, session_code)
                else:
                    # For PET, session structure might be different
                    local_folder = PET_DATA_PATH / session_code
                    cloud_prefix = f"data/PET/{session_code}"
            
            if not local_folder.exists():
                logger.warning(f"Local folder doesn't exist: {local_folder}")
                return (0, 0)
            
            return self.sync_folder(local_folder, cloud_prefix)
            
        except Exception as e:
            logger.error(f"Failed to sync patient data: {e}")
            return (0, 0)
    
    def upload_patient_file(self, local_file: Path, session_code: str, 
                          patient_id: str, is_edited: bool = False) -> bool:
        """
        Upload patient file with proper cloud path structure
        
        Args:
            local_file: Local file path
            session_code: Session/doctor code
            patient_id: Patient ID
            is_edited: Whether this is an edited file
            
        Returns:
            True if successful
        """
        try:
            # Determine file type and create appropriate cloud path
            filename = local_file.name
            
            if is_edited and "_edited" not in filename:
                # Add _edited suffix before file extension
                name_parts = filename.rsplit(".", 1)
                if len(name_parts) == 2:
                    filename = f"{name_parts[0]}_edited.{name_parts[1]}"
                else:
                    filename = f"{filename}_edited"
            
            # Determine modality from local path
            if "SPECT" in str(local_file):
                cloud_path = f"data/SPECT/{session_code}/{patient_id}/{filename}"
            elif "PET" in str(local_file):
                cloud_path = f"data/PET/{session_code}/{patient_id}/{filename}"
            else:
                # Default to SPECT
                cloud_path = f"data/SPECT/{session_code}/{patient_id}/{filename}"
            
            return self.upload_file(local_file, cloud_path)
            
        except Exception as e:
            logger.error(f"Failed to upload patient file: {e}")
            return False

# Global instance
cloud_storage = CloudStorageManager()

# Convenience functions - Updated for new structure
def upload_file(local_path: Path, cloud_path: str = None) -> bool:
    """Upload file to cloud storage"""
    return cloud_storage.upload_file(local_path, cloud_path)

def download_file(cloud_path: str, local_path: Path = None) -> bool:
    """Download file from cloud storage"""
    return cloud_storage.download_file(cloud_path, local_path)

def sync_spect_data(session_code: str = None, patient_id: str = None) -> Tuple[int, int]:
    """
    Sync SPECT data folder with cloud - Updated for new structure
    
    Args:
        session_code: Sync specific session (NSY, ATL, NBL)
        patient_id: Sync specific patient within session
        
    Returns:
        Tuple of (uploaded_count, downloaded_count)
    """
    if session_code:
        return cloud_storage.sync_patient_data(session_code, patient_id, "SPECT")
    else:
        # Sync all SPECT data
        return cloud_storage.sync_folder(SPECT_DATA_PATH, "data/SPECT")

def sync_pet_data(session_code: str = None, patient_id: str = None) -> Tuple[int, int]:
    """
    Sync PET data folder with cloud - New function
    
    Args:
        session_code: Sync specific session
        patient_id: Sync specific patient within session
        
    Returns:
        Tuple of (uploaded_count, downloaded_count)
    """
    if session_code:
        return cloud_storage.sync_patient_data(session_code, patient_id, "PET")
    else:
        # Sync all PET data
        return cloud_storage.sync_folder(PET_DATA_PATH, "data/PET")

def upload_patient_file(local_file: Path, session_code: str, patient_id: str, 
                       is_edited: bool = False) -> bool:
    """Upload patient file with proper cloud path structure"""
    return cloud_storage.upload_patient_file(local_file, session_code, patient_id, is_edited)

def test_cloud_connection() -> bool:
    """Test cloud storage connection"""
    return cloud_storage.test_connection()