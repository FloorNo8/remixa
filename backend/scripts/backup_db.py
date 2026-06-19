#!/usr/bin/env python3
"""Daily PostgreSQL backup to R2 with 30-day retention."""
import os
import subprocess
import sys
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError


def backup_postgres():
    """Create PostgreSQL backup and upload to R2."""
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    backup_file = f"/tmp/remixa-backup-{timestamp}.sql.gz"
    
    print(f"🔄 Starting backup at {timestamp}")
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)
    
    try:
        # Dump database (custom format, compressed)
        print("📦 Dumping database...")
        subprocess.run([
            "pg_dump",
            database_url,
            "-Fc",  # Custom format (compressed)
            "-f", backup_file
        ], check=True, capture_output=True, text=True)
        
        # Get file size
        file_size = os.path.getsize(backup_file)
        print(f"✅ Database dumped: {file_size / 1024 / 1024:.2f} MB")
        
        # Upload to R2
        print("☁️  Uploading to R2...")
        s3 = boto3.client('s3',
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("R2_SECRET_KEY")
        )
        
        bucket_name = os.getenv("R2_BACKUP_BUCKET", "remixa-backups")
        s3_key = f"db/{timestamp}.sql.gz"
        
        s3.upload_file(
            backup_file,
            bucket_name,
            s3_key,
            ExtraArgs={
                'Metadata': {
                    'backup-date': timestamp,
                    'size-bytes': str(file_size)
                }
            }
        )
        print(f"✅ Uploaded to s3://{bucket_name}/{s3_key}")
        
        # Delete local file
        os.remove(backup_file)
        print("🗑️  Local backup file deleted")
        
        # Clean up old backups (30-day retention)
        print("🧹 Cleaning up old backups...")
        cutoff = datetime.utcnow() - timedelta(days=30)
        
        try:
            response = s3.list_objects_v2(Bucket=bucket_name, Prefix="db/")
            deleted_count = 0
            
            for obj in response.get('Contents', []):
                key = obj['Key']
                # Extract timestamp from key (format: db/YYYYMMDD-HHMMSS.sql.gz)
                try:
                    backup_timestamp_str = key.split('/')[1][:15]  # YYYYMMDD-HHMMSS
                    backup_date = datetime.strptime(backup_timestamp_str, '%Y%m%d-%H%M%S')
                    
                    if backup_date < cutoff:
                        s3.delete_object(Bucket=bucket_name, Key=key)
                        deleted_count += 1
                        print(f"  🗑️  Deleted old backup: {key}")
                except (IndexError, ValueError) as e:
                    print(f"  ⚠️  Skipping invalid key: {key} ({e})")
                    continue
            
            if deleted_count > 0:
                print(f"✅ Deleted {deleted_count} old backup(s)")
            else:
                print("✅ No old backups to delete")
                
        except ClientError as e:
            print(f"⚠️  Failed to clean up old backups: {e}")
        
        print(f"✅ Backup complete: {timestamp}")
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Database dump failed: {e.stderr}")
        return 1
    except ClientError as e:
        print(f"❌ R2 upload failed: {e}")
        return 1
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(backup_postgres())
