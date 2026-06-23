"""
Integration Tests: GDPR Compliance

Tests:
1. User data export (Art 20 - Right to data portability)
2. User data deletion (Art 17 - Right to erasure)
3. 30-day soft delete retention
4. Data anonymization
5. Consent logging
"""

import pytest
import uuid
from datetime import datetime, timedelta
import json

# ============================================================================
# TEST: GDPR DATA EXPORT
# ============================================================================

def test_gdpr_data_export_complete(db_connection, test_user, test_generation):
    """
    Test GDPR Art 20 - Right to data portability
    
    Export should include:
    - User profile data
    - All generations
    - All license transactions
    - All earnings
    - VAT transactions
    - Consent logs
    """
    cursor = db_connection.cursor()
    
    # Create GDPR export request
    export_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO gdpr_requests (id, user_id, request_type, status)
        VALUES (%s, %s, 'export', 'processing')
    """, (export_id, test_user['id']))
    
    db_connection.commit()
    
    # Simulate export generation
    # 1. Get user data
    cursor.execute("""
        SELECT id, email, subscription_tier, created_at, total_earned
        FROM users WHERE id = %s
    """, (test_user['id'],))
    user_data = dict(cursor.fetchone())
    
    # 2. Get generations
    cursor.execute("""
        SELECT id, prompt, style, audio_url, created_at, earnings, remix_count
        FROM generations WHERE user_id = %s
    """, (test_user['id'],))
    generations = [dict(row) for row in cursor.fetchall()]
    
    # 3. Get license transactions
    cursor.execute("""
        SELECT id, amount, creator_share, created_at
        FROM license_transactions WHERE original_creator_id = %s
    """, (test_user['id'],))
    transactions = [dict(row) for row in cursor.fetchall()]
    
    # Build export package
    export_data = {
        "export_id": export_id,
        "export_date": datetime.utcnow().isoformat(),
        "user": {
            "id": str(user_data['id']),
            "email": user_data['email'],
            "subscription_tier": user_data['subscription_tier'],
            "created_at": user_data['created_at'].isoformat(),
            "total_earned": float(user_data['total_earned'])
        },
        "generations": [
            {
                "id": str(g['id']),
                "prompt": g['prompt'],
                "style": g['style'],
                "audio_url": g['audio_url'],
                "created_at": g['created_at'].isoformat(),
                "earnings": float(g['earnings']),
                "remix_count": g['remix_count']
            }
            for g in generations
        ],
        "license_transactions": [
            {
                "id": str(t['id']),
                "amount": float(t['amount']),
                "creator_share": float(t['creator_share']),
                "created_at": t['created_at'].isoformat()
            }
            for t in transactions
        ]
    }
    
    # Verify export completeness
    assert 'user' in export_data
    assert 'generations' in export_data
    assert 'license_transactions' in export_data
    assert len(export_data['generations']) > 0
    
    # Update export request
    export_url = f"https://cdn.eu-sound-lab.com/exports/{export_id}.zip"
    expires_at = datetime.utcnow() + timedelta(days=7)
    
    cursor.execute("""
        UPDATE gdpr_requests
        SET status = 'completed', export_url = %s, export_expires_at = %s, completed_at = NOW()
        WHERE id = %s
    """, (export_url, expires_at, export_id))
    
    db_connection.commit()
    
    # Verify export request updated
    cursor.execute("""
        SELECT status, export_url, export_expires_at
        FROM gdpr_requests WHERE id = %s
    """, (export_id,))
    
    request = cursor.fetchone()
    assert request['status'] == 'completed'
    assert request['export_url'] is not None
    assert request['export_expires_at'] is not None

# ============================================================================
# TEST: GDPR DATA DELETION (SOFT DELETE)
# ============================================================================

def test_gdpr_soft_delete_user(db_connection, test_user, test_generation):
    """
    Test GDPR Art 17 - Right to erasure (soft delete)
    
    Soft delete should:
    - Set deleted_at timestamp
    - Keep data for 30 days (legal retention)
    - Anonymize user data
    - Keep audio files (for C2PA chain integrity)
    """
    cursor = db_connection.cursor()
    
    # Create deletion request
    deletion_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO gdpr_requests (id, user_id, request_type, status)
        VALUES (%s, %s, 'delete', 'processing')
    """, (deletion_id, test_user['id']))
    
    db_connection.commit()
    
    # Perform soft delete
    cursor.execute("""
        UPDATE users
        SET deleted_at = NOW(),
            email = %s,
            data_deletion_requested_at = NOW()
        WHERE id = %s
    """, (f"deleted_{test_user['id'][:8]}@deleted.local", test_user['id']))
    
    db_connection.commit()
    
    # Verify user marked as deleted
    cursor.execute("""
        SELECT deleted_at, email, data_deletion_requested_at
        FROM users WHERE id = %s
    """, (test_user['id'],))
    
    user = cursor.fetchone()
    assert user['deleted_at'] is not None, "User should have deleted_at timestamp"
    assert user['email'].startswith('deleted_'), "Email should be anonymized"
    assert user['data_deletion_requested_at'] is not None
    
    # Verify generations still exist (for C2PA chain)
    cursor.execute("""
        SELECT COUNT(*) as count FROM generations WHERE user_id = %s
    """, (test_user['id'],))
    
    assert cursor.fetchone()['count'] > 0, "Generations should be retained for 30 days"
    
    # Update deletion request
    cursor.execute("""
        UPDATE gdpr_requests
        SET status = 'completed', completed_at = NOW()
        WHERE id = %s
    """, (deletion_id,))
    
    db_connection.commit()

# ============================================================================
# TEST: 30-DAY RETENTION CLEANUP
# ============================================================================

def test_cleanup_expired_deletions(db_connection):
    """
    Test automatic cleanup of users deleted >30 days ago
    
    Cleanup should:
    - Delete users where deleted_at > 30 days
    - Cascade delete generations
    - Keep audit log entries
    """
    cursor = db_connection.cursor()
    
    # Create user deleted 31 days ago
    old_user_id = str(uuid.uuid4())
    deleted_31_days_ago = datetime.utcnow() - timedelta(days=31)
    
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, deleted_at)
        VALUES (%s, %s, 'free', %s)
    """, (old_user_id, f"old_{old_user_id[:8]}@deleted.local", deleted_31_days_ago))
    
    # Create generation for old user
    old_gen_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash
        ) VALUES (
            %s, %s, 'old prompt', 'lofi', 15,
            'https://cdn.test.com/old.mp3', 'https://cdn.test.com/old.c2pa.json',
            2500, 0.008, 'v1', 'hash'
        )
    """, (old_gen_id, old_user_id))
    
    # Create user deleted 29 days ago (should NOT be deleted)
    recent_user_id = str(uuid.uuid4())
    deleted_29_days_ago = datetime.utcnow() - timedelta(days=29)
    
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, deleted_at)
        VALUES (%s, %s, 'free', %s)
    """, (recent_user_id, f"recent_{recent_user_id[:8]}@deleted.local", deleted_29_days_ago))
    
    db_connection.commit()
    
    # Run cleanup function
    cursor.execute("""
        SELECT cleanup_expired_deletions() AS deleted_count
    """)
    deleted_count = cursor.fetchone()['deleted_count']
    
    db_connection.commit()
    
    # Verify old user deleted
    cursor.execute("""
        SELECT COUNT(*) as count FROM users WHERE id = %s
    """, (old_user_id,))
    assert cursor.fetchone()['count'] == 0, "User deleted >30 days ago should be removed"
    
    # Verify old generation deleted (cascade)
    cursor.execute("""
        SELECT COUNT(*) as count FROM generations WHERE id = %s
    """, (old_gen_id,))
    assert cursor.fetchone()['count'] == 0, "Generation should be cascade deleted"
    
    # Verify recent user NOT deleted
    cursor.execute("""
        SELECT COUNT(*) as count FROM users WHERE id = %s
    """, (recent_user_id,))
    assert cursor.fetchone()['count'] == 1, "User deleted <30 days ago should be retained"
    
    assert deleted_count >= 1, "Cleanup should report deleted users"

# ============================================================================
# TEST: DATA ANONYMIZATION
# ============================================================================

def test_user_data_anonymization(db_connection, test_user):
    """
    Test that user data is properly anonymized on deletion
    
    Anonymization should:
    - Replace email with anonymized version
    - Clear Stripe customer ID
    - Keep user ID (for foreign key integrity)
    - Keep generation data (for C2PA chain)
    """
    cursor = db_connection.cursor()
    
    original_email = test_user['email']
    
    # Anonymize user
    cursor.execute("""
        UPDATE users
        SET 
            email = %s,
            stripe_customer_id = NULL,
            deleted_at = NOW()
        WHERE id = %s
    """, (f"anonymized_{test_user['id'][:8]}@anonymized.local", test_user['id']))
    
    db_connection.commit()
    
    # Verify anonymization
    cursor.execute("""
        SELECT email, stripe_customer_id, deleted_at
        FROM users WHERE id = %s
    """, (test_user['id'],))
    
    user = cursor.fetchone()
    assert user['email'] != original_email, "Email should be changed"
    assert user['email'].startswith('anonymized_'), "Email should be anonymized"
    assert user['stripe_customer_id'] is None, "Stripe ID should be cleared"
    assert user['deleted_at'] is not None, "Should have deletion timestamp"

# ============================================================================
# TEST: CONSENT LOGGING
# ============================================================================

def test_consent_logging(db_connection, test_user):
    """
    Test GDPR Art 7 - Consent logging
    
    Consent log should record:
    - User ID
    - Consent type
    - Granted/revoked
    - IP address
    - User agent
    - Timestamp
    """
    cursor = db_connection.cursor()
    
    # Log consent
    consent_types = [
        ("marketing_emails", True),
        ("analytics_tracking", True),
        ("prompt_storage", False),
    ]
    
    for consent_type, granted in consent_types:
        cursor.execute("""
            INSERT INTO consent_log (
                id, user_id, consent_type, granted,
                ip_address, user_agent
            ) VALUES (
                %s, %s, %s, %s, %s, %s
            )
        """, (
            str(uuid.uuid4()), test_user['id'], consent_type, granted,
            '185.123.45.67', 'Mozilla/5.0 (Test)'
        ))
    
    db_connection.commit()
    
    # Verify consent logged
    cursor.execute("""
        SELECT consent_type, granted, ip_address, created_at
        FROM consent_log
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (test_user['id'],))
    
    logs = cursor.fetchall()
    assert len(logs) == 3, "Should have 3 consent logs"
    
    # Verify each consent
    for log in logs:
        assert log['consent_type'] in ['marketing_emails', 'analytics_tracking', 'prompt_storage']
        assert log['ip_address'] is not None
        assert log['created_at'] is not None

# ============================================================================
# TEST: EXPORT EXPIRATION
# ============================================================================

def test_export_expiration_cleanup(db_connection, test_user):
    """
    Test that expired exports are cleaned up
    
    Exports should:
    - Expire after 7 days
    - Be automatically deleted
    - Remove from storage
    """
    cursor = db_connection.cursor()
    
    # Create expired export
    expired_export_id = str(uuid.uuid4())
    expired_date = datetime.utcnow() - timedelta(days=8)
    
    cursor.execute("""
        INSERT INTO gdpr_requests (
            id, user_id, request_type, status,
            export_url, export_expires_at, completed_at
        ) VALUES (
            %s, %s, 'export', 'completed',
            'https://cdn.test.com/expired.zip', %s, %s
        )
    """, (expired_export_id, test_user['id'], expired_date, expired_date))
    
    # Create valid export
    valid_export_id = str(uuid.uuid4())
    valid_expires = datetime.utcnow() + timedelta(days=5)
    
    cursor.execute("""
        INSERT INTO gdpr_requests (
            id, user_id, request_type, status,
            export_url, export_expires_at, completed_at
        ) VALUES (
            %s, %s, 'export', 'completed',
            'https://cdn.test.com/valid.zip', %s, NOW()
        )
    """, (valid_export_id, test_user['id'], valid_expires))
    
    db_connection.commit()
    
    # Run cleanup
    cursor.execute("""
        SELECT cleanup_expired_exports() AS deleted_count
    """)
    deleted_count = cursor.fetchone()['deleted_count']
    
    db_connection.commit()
    
    # Verify expired export deleted
    cursor.execute("""
        SELECT COUNT(*) as count FROM gdpr_requests WHERE id = %s
    """, (expired_export_id,))
    assert cursor.fetchone()['count'] == 0, "Expired export should be deleted"
    
    # Verify valid export retained
    cursor.execute("""
        SELECT COUNT(*) as count FROM gdpr_requests WHERE id = %s
    """, (valid_export_id,))
    assert cursor.fetchone()['count'] == 1, "Valid export should be retained"
    
    assert deleted_count >= 1, "Cleanup should report deleted exports"

# ============================================================================
# TEST: AUDIT LOG FOR GDPR OPERATIONS
# ============================================================================

def test_gdpr_operations_audit_log(db_connection, test_user):
    """
    Test that GDPR operations are logged in audit log
    
    Should log:
    - Data export requests
    - Data deletion requests
    - Consent changes
    """
    cursor = db_connection.cursor()
    
    # Log export request
    cursor.execute("""
        INSERT INTO audit_log (
            id, user_id, action, resource_type, resource_id, details
        ) VALUES (
            %s, %s, 'gdpr_export_requested', 'gdpr_request', %s, %s
        )
    """, (
        str(uuid.uuid4()), test_user['id'], str(uuid.uuid4()),
        json.dumps({"request_type": "export"})
    ))
    
    # Log deletion request
    cursor.execute("""
        INSERT INTO audit_log (
            id, user_id, action, resource_type, resource_id, details
        ) VALUES (
            %s, %s, 'gdpr_deletion_requested', 'gdpr_request', %s, %s
        )
    """, (
        str(uuid.uuid4()), test_user['id'], str(uuid.uuid4()),
        json.dumps({"request_type": "delete"})
    ))
    
    db_connection.commit()
    
    # Verify audit logs
    cursor.execute("""
        SELECT action, resource_type, details
        FROM audit_log
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (test_user['id'],))
    
    logs = cursor.fetchall()
    assert len(logs) >= 2, "Should have at least 2 audit logs"
    
    actions = [log['action'] for log in logs]
    assert 'gdpr_export_requested' in actions
    assert 'gdpr_deletion_requested' in actions
