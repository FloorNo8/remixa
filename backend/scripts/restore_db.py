#!/usr/bin/env python3
"""Restore PostgreSQL from R2 backup."""
import os
import sys
import subprocess
from datetime import datetime
import boto3
from botocore.exceptions import ClientError


def list_backups():
    """List available backups from R2."""
    try:
        s3 = boto3.client('s3',
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY")
        )
        
        bucket_name = os.getenv("R2_BACKUP_BUCKET", "remixa-backups")
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix="db/")
        
        backups = []
        for obj in response.get('Contents', []):
            key = obj['Key']
            size = obj['Size']
            modified = obj['LastModified']
            backups.append({
                'key': key,
                'size': size,
                'modified': modified
            })
        
        # Sort by modified date (newest first)
        backups.sort(key=lambda x: x['modified'], reverse=True)
        
        print("\n📦 Available backups:")
        print("-" * 80)
        for i, backup in enumerate(backups, 1):
            size_mb = backup['size'] / 1024 / 1024
            print(f"{i}. {backup['key']}")
            print(f"   Size: {size_mb:.2f} MB | Modified: {backup['modified']}")
        print("-" * 80)
        
        return backups
        
    except ClientError as e:
        print(f"❌ Failed to list backups: {e}")
        return []


def restore_postgres(backup_key):
    """Restore PostgreSQL from R2 backup."""
    print(f"🔄 Starting restore from {backup_key}")
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)
    
    # Confirm restore
    print("\n⚠️  WARNING: This will DROP all existing data and restore from backup!")
    print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")
    print(f"Backup: {backup_key}")
    
    confirm = input("\nType 'yes' to continue: ")
    if confirm.lower() != 'yes':
        print("❌ Restore cancelled")
        return 1
    
    restore_file = "/tmp/restore.sql.gz"
    
    try:
        # Download from R2
        print("\n☁️  Downloading backup from R2...")
        s3 = boto3.client('s3',
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY")
        )
        
        bucket_name = os.getenv("R2_BACKUP_BUCKET", "remixa-backups")
        s3.download_file(bucket_name, backup_key, restore_file)
        
        file_size = os.path.getsize(restore_file)
        print(f"✅ Downloaded: {file_size / 1024 / 1024:.2f} MB")
        
        # Restore database
        print("\n🔄 Restoring database...")
        print("   This may take several minutes...")
        
        subprocess.run([
            "pg_restore",
            "-d", database_url,
            "--clean",  # Drop existing objects
            "--if-exists",  # Don't error if objects don't exist
            "--no-owner",  # Don't restore ownership
            "--no-acl",  # Don't restore access privileges
            "-v",  # Verbose
            restore_file
        ], check=True, capture_output=True, text=True)
        
        print("✅ Database restored successfully")
        
        # Delete local file
        os.remove(restore_file)
        print("🗑️  Local restore file deleted")
        
        print(f"\n✅ Restore complete from {backup_key}")
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Database restore failed: {e.stderr}")
        return 1
    except ClientError as e:
        print(f"❌ R2 download failed: {e}")
        return 1
    except Exception as e:
        print(f"❌ Restore failed: {e}")
        return 1
    finally:
        # Clean up local file if it exists
        if os.path.exists(restore_file):
            os.remove(restore_file)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  List backups:    python restore_db.py list")
        print("  Restore backup:  python restore_db.py <backup_key>")
        print("\nExample:")
        print("  python restore_db.py db/20260619-020000.sql.gz")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "list":
        backups = list_backups()
        if backups:
            print("\nTo restore a backup, run:")
            print(f"  python restore_db.py {backups[0]['key']}")
    else:
        # Assume it's a backup key
        backup_key = command
        sys.exit(restore_postgres(backup_key))


if __name__ == "__main__":
    main()
