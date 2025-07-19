# debug_cloud_connection.py
"""
Debug script untuk troubleshoot BackBlaze B2 connection
"""
import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def check_dependencies():
    """Check if required packages are installed"""
    print("📦 Checking dependencies...")
    
    try:
        import boto3
        print(f"✅ boto3 version: {boto3.__version__}")
    except ImportError:
        print("❌ boto3 not installed. Run: pip install boto3")
        return False
    
    try:
        import botocore
        print(f"✅ botocore version: {botocore.__version__}")
    except ImportError:
        print("❌ botocore not installed. Run: pip install botocore")
        return False
    
    try:
        import dotenv
        print(f"✅ python-dotenv installed")
    except ImportError:
        print("❌ python-dotenv not installed. Run: pip install python-dotenv")
        return False
    
    return True

def check_env_file():
    """Check .env file and load variables"""
    print("\n📄 Checking .env file...")
    
    env_path = project_root / ".env"
    if not env_path.exists():
        print(f"❌ .env file not found at: {env_path}")
        return False
    
    print(f"✅ .env file found: {env_path}")
    
    # Load .env file manually to debug
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        
        # Check each required variable
        required_vars = [
            "B2_KEY_ID",
            "B2_APPLICATION_KEY", 
            "B2_BUCKET_NAME",
            "B2_ENDPOINT"
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if value:
                if var == "B2_APPLICATION_KEY":
                    print(f"✅ {var}: {value[:10]}***")  # Hide sensitive data
                else:
                    print(f"✅ {var}: {value}")
            else:
                print(f"❌ {var}: Not set")
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Missing variables: {missing_vars}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading .env: {e}")
        return False

def test_basic_connection():
    """Test basic connection with detailed error info"""
    print("\n🔗 Testing basic connection...")
    
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError
        
        # Get credentials from environment
        key_id = os.getenv("B2_KEY_ID")
        app_key = os.getenv("B2_APPLICATION_KEY")
        bucket_name = os.getenv("B2_BUCKET_NAME")
        endpoint = os.getenv("B2_ENDPOINT")
        
        print(f"🔧 Creating S3 client...")
        print(f"   Endpoint: {endpoint}")
        print(f"   Bucket: {bucket_name}")
        print(f"   Key ID: {key_id}")
        
        client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=app_key
        )
        
        print("✅ S3 client created successfully")
        
        # Test with list_objects_v2
        print("🧪 Testing list_objects_v2...")
        response = client.list_objects_v2(
            Bucket=bucket_name,
            MaxKeys=1
        )
        
        print("✅ Connection successful!")
        print(f"📊 Response keys: {list(response.keys())}")
        
        if 'Contents' in response:
            print(f"📁 Found {len(response['Contents'])} objects")
        else:
            print("📁 Bucket is empty (which is fine)")
        
        return True
        
    except NoCredentialsError as e:
        print(f"❌ Credentials Error: {e}")
        print("💡 Check your B2_KEY_ID and B2_APPLICATION_KEY")
        return False
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"❌ ClientError: {error_code}")
        print(f"📝 Message: {error_message}")
        
        if error_code == 'InvalidAccessKeyId':
            print("💡 Your B2_KEY_ID might be incorrect")
        elif error_code == 'SignatureDoesNotMatch':
            print("💡 Your B2_APPLICATION_KEY might be incorrect")
        elif error_code == 'NoSuchBucket':
            print("💡 Bucket name might be incorrect or doesn't exist")
        elif 'BadDigest' in error_code:
            print("💡 Try different endpoint region")
        else:
            print("💡 Check your endpoint URL and bucket region")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print(f"🔍 Error type: {type(e).__name__}")
        return False

def suggest_fixes():
    """Suggest common fixes"""
    print("\n🔧 Common fixes:")
    print("1. Install dependencies:")
    print("   pip install boto3 botocore python-dotenv")
    
    print("\n2. Check endpoint regions:")
    print("   - us-west-004: https://s3.us-west-004.backblazeb2.com")
    print("   - eu-central-003: https://s3.eu-central-003.backblazeb2.com") 
    print("   - ap-southeast-002: https://s3.ap-southeast-002.backblazeb2.com")
    
    print("\n3. Verify credentials in BackBlaze console:")
    print("   - Go to BackBlaze B2 > Application Keys")
    print("   - Check if key is active and has correct permissions")
    print("   - Make sure bucket name matches exactly")
    
    print("\n4. Try different endpoint format:")
    print("   - Some regions use different URL patterns")
    print("   - Check bucket details in BackBlaze console for correct endpoint")

def main():
    """Main debug function"""
    print("🔍 BackBlaze B2 Connection Debug Tool")
    print("=" * 60)
    
    # Step 1: Check dependencies
    if not check_dependencies():
        print("\n❌ Please install missing dependencies first")
        return False
    
    # Step 2: Check .env file
    if not check_env_file():
        print("\n❌ Please fix .env file configuration")
        return False
    
    # Step 3: Test connection
    if not test_basic_connection():
        print("\n❌ Connection failed")
        suggest_fixes()
        return False
    
    print("\n🎉 All checks passed! Connection is working.")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)