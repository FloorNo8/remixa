"""
GDPR Compliance Tools
Implements Art 15-22: Data export, erasure, portability
"""

import psycopg2
import json
import zipfile
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
import os
import structlog

logger = structlog.get_logger()

class GDPRTools:
    """
    GDPR compliance utilities for EU TikTok Sound Lab
    """
    
    def __init__(self, database_url: str, storage_url: str):
        """
        Initialize GDPR tools
        
        Args:
            database_url: PostgreSQL connection string
            storage_url: S3-compatible storage URL
        """
        self.database_url = database_url
        self.storage_url = storage_url
    
    def export_user_data(self, user_id: str) -> bytes:
        """
        GDPR Art 20 - Right to data portability
        
        Exports all user data as ZIP file containing:
        - user_data.json (profile, subscription)
        - generations.json (all generation metadata)
        - audio/ folder with all generated tracks
        - vat_transactions.json (billing history)
        
        Args:
            user_id: User UUID
            
        Returns:
            ZIP file as bytes
        """
        
        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()
        
        # Get user data
        cur.execute("""
            SELECT id, email, subscription_tier, created_at
            FROM users
            WHERE id = %s AND deleted_at IS NULL
        """, (user_id,))
        user = cur.fetchone()
        
        if not user:
            raise ValueError(f"User {user_id} not found or already deleted")
        
        # Get generations
        cur.execute("""
            SELECT id, prompt, style, duration_seconds, audio_url, 
                   c2pa_manifest_url, generation_time_ms, cost_eur, created_at
            FROM generations
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        generations = cur.fetchall()
        
        # Get VAT transactions
        cur.execute("""
            SELECT amount_net, vat_rate, vat_amount, total_amount, 
                   country_code, created_at
            FROM vat_transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        transactions = cur.fetchall()
        
        # Get TikTok uploads
        cur.execute("""
            SELECT generation_id, tiktok_video_id, status, created_at
            FROM tiktok_uploads
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (user_id,))
        uploads = cur.fetchall()
        
        cur.close()
        conn.close()
        
        # Create ZIP file
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # Add user data
            user_data = {
                "user_id": str(user[0]),
                "email": user[1],
                "subscription_tier": user[2],
                "created_at": user[3].isoformat(),
                "export_date": datetime.utcnow().isoformat(),
                "data_controller": "Floor No 8 SRL",
                "legal_basis": "GDPR Art 6.1.b (Contract performance)"
            }
            zip_file.writestr('user_data.json', json.dumps(user_data, indent=2))
            
            # Add generations metadata
            generations_data = []
            for gen in generations:
                generations_data.append({
                    "generation_id": str(gen[0]),
                    "prompt": gen[1],
                    "style": gen[2],
                    "duration_seconds": gen[3],
                    "audio_url": gen[4],
                    "c2pa_manifest_url": gen[5],
                    "generation_time_ms": gen[6],
                    "cost_eur": float(gen[7]),
                    "created_at": gen[8].isoformat()
                })
            zip_file.writestr('generations.json', json.dumps(generations_data, indent=2))
            
            # Add VAT transactions
            transactions_data = []
            for tx in transactions:
                transactions_data.append({
                    "amount_net": float(tx[0]),
                    "vat_rate": float(tx[1]),
                    "vat_amount": float(tx[2]),
                    "total_amount": float(tx[3]),
                    "country_code": tx[4],
                    "created_at": tx[5].isoformat()
                })
            zip_file.writestr('vat_transactions.json', json.dumps(transactions_data, indent=2))
            
            # Add TikTok uploads
            uploads_data = []
            for upload in uploads:
                uploads_data.append({
                    "generation_id": str(upload[0]),
                    "tiktok_video_id": upload[1],
                    "status": upload[2],
                    "created_at": upload[3].isoformat()
                })
            zip_file.writestr('tiktok_uploads.json', json.dumps(uploads_data, indent=2))
            
            # Download and add audio files
            for i, gen in enumerate(generations):
                audio_url = gen[4]
                try:
                    response = requests.get(audio_url, timeout=30)
                    if response.status_code == 200:
                        filename = f"audio/{i+1:03d}_{gen[0]}.mp3"
                        zip_file.writestr(filename, response.content)
                except Exception as e:
                    print(f"Warning: Failed to download {audio_url}: {e}")
            
            # Add README
            readme = """# EU TikTok Sound Lab - GDPR Data Export

This archive contains all your personal data stored by EU TikTok Sound Lab.

## Contents

- user_data.json: Your profile and subscription information
- generations.json: Metadata for all tracks you've generated
- vat_transactions.json: Your billing history
- tiktok_uploads.json: TikTok uploads linked to your account
- audio/: All generated audio files

## Your Rights

Under GDPR, you have the right to:
- Access your data (Art 15) - You're exercising this right now
- Rectify inaccurate data (Art 16) - Contact support@eu-sound-lab.com
- Erase your data (Art 17) - Use the "Delete Account" button in settings
- Restrict processing (Art 18) - Contact support@eu-sound-lab.com
- Data portability (Art 20) - This export fulfills this right
- Object to processing (Art 21) - Contact support@eu-sound-lab.com

## Data Controller

Floor No 8 SRL
Bucharest, Romania
Email: privacy@eu-sound-lab.com

## Questions?

If you have questions about this export or your data rights, contact:
privacy@eu-sound-lab.com

Export generated: """ + datetime.utcnow().isoformat() + """
"""
            zip_file.writestr('README.txt', readme)
        
        return zip_buffer.getvalue()
    
    def delete_user_data(self, user_id: str, immediate: bool = False) -> Dict:
        """
        GDPR Art 17 - Right to erasure
        
        Soft delete by default (30-day retention for legal compliance)
        Hard delete if immediate=True (only after 30 days)
        
        Args:
            user_id: User UUID
            immediate: If True, hard delete immediately (use with caution)
            
        Returns:
            Dict with deletion status
        """
        
        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()
        
        if immediate:
            # Catalog Survival: check if we should anonymize or hard-delete
            self._erase_or_delete_user(cur, user_id)
            conn.commit()
            
            cur.close()
            conn.close()
            
            return {
                "status": "erased_or_deleted",
                "user_id": user_id,
                "deletion_type": "immediate",
                "deleted_at": datetime.utcnow().isoformat()
            }
        else:
            # Soft delete (set deleted_at timestamp)
            cur.execute("""
                UPDATE users
                SET deleted_at = NOW()
                WHERE id = %s AND deleted_at IS NULL
            """, (user_id,))
            
            if cur.rowcount == 0:
                cur.close()
                conn.close()
                raise ValueError(f"User {user_id} not found or already deleted")
            
            conn.commit()
            cur.close()
            conn.close()
            
            return {
                "status": "scheduled_for_deletion",
                "user_id": user_id,
                "deletion_type": "soft",
                "deleted_at": datetime.utcnow().isoformat(),
                "permanent_deletion_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "message": "Your data will be permanently deleted in 30 days. Contact support to cancel."
            }
    
    def anonymize_user_data(self, user_id: str) -> Dict:
        """
        Alternative to deletion: Anonymize user data
        Keeps aggregated statistics while removing PII
        
        Args:
            user_id: User UUID
            
        Returns:
            Dict with anonymization status
        """
        
        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()
        
        # Anonymize email
        cur.execute("""
            UPDATE users
            SET email = 'anonymized_' || id || '@deleted.local',
                stripe_customer_id = NULL
            WHERE id = %s
        """, (user_id,))
        
        # Remove prompts from generations (keep style/duration for analytics)
        cur.execute("""
            UPDATE generations
            SET prompt = NULL
            WHERE user_id = %s
        """, (user_id,))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "anonymized",
            "user_id": user_id,
            "anonymized_at": datetime.utcnow().isoformat(),
            "retained_data": ["generation_count", "subscription_tier", "usage_statistics"]
        }

    def _erase_or_delete_user(self, cur, user_id: str):
        """
        Implements Catalog Survival/Immunity.
        If the user has generations that are parents of other generations (remixes)
        or are referenced in whitelisted brand videos (licensed_videos), we anonymize
        the user (PII erasure) rather than hard-deleting the database row, preserving
        downstream rights and metadata.
        """
        # 1. Check if user has remixed generations
        cur.execute("""
            SELECT COUNT(*) 
            FROM generations 
            WHERE parent_id IN (SELECT id FROM generations WHERE user_id = %s)
        """, (user_id,))
        remix_count = cur.fetchone()[0]
        
        # 2. Check if user has whitelisted/licensed videos
        cur.execute("""
            SELECT COUNT(*) 
            FROM licensed_videos 
            WHERE generation_id IN (SELECT id FROM generations WHERE user_id = %s)
        """, (user_id,))
        license_count = cur.fetchone()[0]
        
        if remix_count > 0 or license_count > 0:
            # Anonymize (PII Erasure / Catalog Survival)
            cur.execute("""
                UPDATE users
                SET email = 'erased_' || id || '@deleted.local',
                    username = 'Deleted Creator',
                    stripe_customer_id = NULL,
                    stripe_account_id = NULL,
                    is_erased = TRUE,
                    deleted_at = NOW()
                WHERE id = %s
            """, (user_id,))
            
            # Anonymize prompts in their generations (GDPR requirement)
            cur.execute("""
                UPDATE generations
                SET prompt = NULL
                WHERE user_id = %s
            """, (user_id,))
            
            logger.info("user_anonymized_for_catalog_survival", user_id=user_id, remixes=remix_count, licenses=license_count)
        else:
            # Safe to hard delete
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            logger.info("user_hard_deleted", user_id=user_id)
    
    def cleanup_expired_deletions(self) -> Dict:
        """
        Cron job: Hard delete users marked for deletion >30 days ago
        Run daily via cron
        
        Returns:
            Dict with cleanup statistics
        """
        
        conn = psycopg2.connect(self.database_url)
        cur = conn.cursor()
        
        # Find users deleted >30 days ago
        cur.execute("""
            SELECT id, email, deleted_at
            FROM users
            WHERE deleted_at IS NOT NULL
              AND deleted_at < NOW() - INTERVAL '30 days'
        """)
        expired_users = cur.fetchall()
        
        # Hard delete them
        deleted_count = 0
        for user in expired_users:
            self._erase_or_delete_user(cur, user[0])
            deleted_count += 1
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            "status": "cleanup_complete",
            "deleted_users": deleted_count,
            "cleanup_date": datetime.utcnow().isoformat()
        }
    
    def get_user_consent_log(self, user_id: str) -> List[Dict]:
        """
        GDPR Art 7 - Conditions for consent
        Returns log of all consent actions
        
        Args:
            user_id: User UUID
            
        Returns:
            List of consent events
        """
        
        # TODO: Implement consent logging table
        # For now, return mock data
        return [
            {
                "consent_type": "terms_of_service",
                "granted": True,
                "timestamp": "2026-06-01T10:00:00Z",
                "ip_address": "redacted",
                "user_agent": "redacted"
            },
            {
                "consent_type": "privacy_policy",
                "granted": True,
                "timestamp": "2026-06-01T10:00:00Z",
                "ip_address": "redacted",
                "user_agent": "redacted"
            },
            {
                "consent_type": "marketing_emails",
                "granted": False,
                "timestamp": "2026-06-01T10:00:00Z",
                "ip_address": "redacted",
                "user_agent": "redacted"
            }
        ]


# ============================================================================
# CLI TOOL
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python gdpr_tools.py <command> <user_id>")
        print("Commands: export, delete, anonymize, cleanup")
        sys.exit(1)
    
    command = sys.argv[1]
    user_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Mock database URL (replace with actual)
    database_url = os.getenv("DATABASE_URL", "postgresql://localhost/eu_sound_lab")
    storage_url = os.getenv("STORAGE_URL", "https://storage.eu-sound-lab.com")
    
    tools = GDPRTools(database_url, storage_url)
    
    if command == "export":
        print(f"Exporting data for user {user_id}...")
        zip_data = tools.export_user_data(user_id)
        
        output_file = f"gdpr_export_{user_id}.zip"
        with open(output_file, 'wb') as f:
            f.write(zip_data)
        
        print(f"✅ Export saved: {output_file} ({len(zip_data)} bytes)")
    
    elif command == "delete":
        print(f"Deleting user {user_id}...")
        result = tools.delete_user_data(user_id, immediate=False)
        print(f"✅ {result['status']}")
        print(f"   Permanent deletion: {result.get('permanent_deletion_date', 'N/A')}")
    
    elif command == "anonymize":
        print(f"Anonymizing user {user_id}...")
        result = tools.anonymize_user_data(user_id)
        print(f"✅ {result['status']}")
        print(f"   Retained data: {', '.join(result['retained_data'])}")
    
    elif command == "cleanup":
        print("Running cleanup of expired deletions...")
        result = tools.cleanup_expired_deletions()
        print(f"✅ Deleted {result['deleted_users']} expired users")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
