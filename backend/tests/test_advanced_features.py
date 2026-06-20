"""
Advanced Features Test Suite (Phase 7)

Tests for multi-currency, dynamic splits, royalty pools,
blockchain integration, and instant payouts.

Usage:
    pytest backend/tests/test_advanced_features.py -v
"""

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
from decimal import Decimal
import uuid
import os

@pytest.fixture
def db():
    """Database connection fixture"""
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL", "postgresql://localhost/remixa_test"),
        cursor_factory=RealDictCursor
    )
    yield conn
    conn.close()

# ============================================================================
# MULTI-CURRENCY TESTS
# ============================================================================

class TestMultiCurrency:
    """Test multi-currency support"""
    
    def test_add_currency_rate(self, db):
        """Test adding exchange rate"""
        cur = db.cursor()
        
        rate_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO currency_rates (id, from_currency, to_currency, rate)
            VALUES (%s, 'USD', 'EUR', 0.92)
            RETURNING id, rate
        """, (rate_id,))
        
        result = cur.fetchone()
        assert result['rate'] == Decimal('0.92')
        
        db.commit()
        cur.close()
    
    def test_currency_conversion(self, db):
        """Test currency conversion function"""
        cur = db.cursor()
        
        # Add rate
        cur.execute("""
            INSERT INTO currency_rates (from_currency, to_currency, rate)
            VALUES ('USD', 'EUR', 0.92)
        """)
        db.commit()
        
        # Convert
        cur.execute("""
            SELECT convert_currency(100.00, 'USD', 'EUR') as converted
        """)
        
        result = cur.fetchone()
        assert result['converted'] == Decimal('92.00')
        
        cur.close()
    
    def test_same_currency_no_conversion(self, db):
        """Test that same currency returns original amount"""
        cur = db.cursor()
        
        cur.execute("""
            SELECT convert_currency(100.00, 'EUR', 'EUR') as converted
        """)
        
        result = cur.fetchone()
        assert result['converted'] == Decimal('100.00')
        
        cur.close()

# ============================================================================
# DYNAMIC ROYALTY SPLITS TESTS
# ============================================================================

class TestDynamicRoyaltySplits:
    """Test custom royalty split configurations"""
    
    def test_create_split_config(self, db):
        """Test creating custom split configuration"""
        cur = db.cursor()
        
        # Create user and generation
        user_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO users (id, username, email, password_hash)
            VALUES (%s, 'testuser', 'test@test.com', 'hash')
        """, (user_id,))
        
        cur.execute("""
            INSERT INTO generations (id, user_id, prompt, audio_url, status)
            VALUES (%s, %s, 'test', 'url', 'completed')
        """, (gen_id, user_id))
        
        # Create split config
        config_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO royalty_split_configs (
                id, generation_id, platform_percentage,
                parent_percentage, grandparent_percentage
            ) VALUES (%s, %s, 25.00, 55.00, 20.00)
            RETURNING id
        """, (config_id, gen_id))
        
        result = cur.fetchone()
        assert result['id'] == config_id
        
        db.commit()
        cur.close()
    
    def test_split_must_sum_to_100(self, db):
        """Test that splits must sum to 100%"""
        cur = db.cursor()
        
        user_id = str(uuid.uuid4())
        gen_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO users (id, username, email, password_hash)
            VALUES (%s, 'testuser2', 'test2@test.com', 'hash')
        """, (user_id,))
        
        cur.execute("""
            INSERT INTO generations (id, user_id, prompt, audio_url, status)
            VALUES (%s, %s, 'test', 'url', 'completed')
        """, (gen_id, user_id))
        
        # Try invalid split (sums to 110)
        with pytest.raises(psycopg2.IntegrityError):
            cur.execute("""
                INSERT INTO royalty_split_configs (
                    generation_id, platform_percentage,
                    parent_percentage, grandparent_percentage
                ) VALUES (%s, 40.00, 50.00, 20.00)
            """, (gen_id,))
            db.commit()
        
        db.rollback()
        cur.close()

# ============================================================================
# ROYALTY POOLS TESTS
# ============================================================================

class TestRoyaltyPools:
    """Test collaborative royalty pools"""
    
    def test_create_pool(self, db):
        """Test creating royalty pool"""
        cur = db.cursor()
        
        user_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO users (id, username, email, password_hash)
            VALUES (%s, 'poolcreator', 'pool@test.com', 'hash')
        """, (user_id,))
        
        pool_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO royalty_pools (id, name, created_by)
            VALUES (%s, 'Test Pool', %s)
            RETURNING id, name
        """, (pool_id, user_id))
        
        result = cur.fetchone()
        assert result['name'] == 'Test Pool'
        
        db.commit()
        cur.close()
    
    def test_add_pool_members(self, db):
        """Test adding members to pool"""
        cur = db.cursor()
        
        # Create users
        creator_id = str(uuid.uuid4())
        member1_id = str(uuid.uuid4())
        member2_id = str(uuid.uuid4())
        
        for uid, username in [
            (creator_id, 'creator'),
            (member1_id, 'member1'),
            (member2_id, 'member2')
        ]:
            cur.execute("""
                INSERT INTO users (id, username, email, password_hash)
                VALUES (%s, %s, %s, 'hash')
            """, (uid, username, f"{username}@test.com"))
        
        # Create pool
        pool_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO royalty_pools (id, name, created_by)
            VALUES (%s, 'Collab Pool', %s)
        """, (pool_id, creator_id))
        
        # Add members
        cur.execute("""
            INSERT INTO royalty_pool_members (pool_id, user_id, share_percentage)
            VALUES (%s, %s, 50.00), (%s, %s, 50.00)
        """, (pool_id, member1_id, pool_id, member2_id))
        
        db.commit()
        
        # Verify members
        cur.execute("""
            SELECT COUNT(*) as count FROM royalty_pool_members
            WHERE pool_id = %s
        """, (pool_id,))
        
        result = cur.fetchone()
        assert result['count'] == 2
        
        cur.close()
    
    def test_pool_shares_cannot_exceed_100(self, db):
        """Test that pool shares cannot exceed 100%"""
        cur = db.cursor()
        
        creator_id = str(uuid.uuid4())
        member1_id = str(uuid.uuid4())
        member2_id = str(uuid.uuid4())
        
        for uid, username in [
            (creator_id, 'creator2'),
            (member1_id, 'member3'),
            (member2_id, 'member4')
        ]:
            cur.execute("""
                INSERT INTO users (id, username, email, password_hash)
                VALUES (%s, %s, %s, 'hash')
            """, (uid, username, f"{username}@test.com"))
        
        pool_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO royalty_pools (id, name, created_by)
            VALUES (%s, 'Over Pool', %s)
        """, (pool_id, creator_id))
        
        # Add first member (60%)
        cur.execute("""
            INSERT INTO royalty_pool_members (pool_id, user_id, share_percentage)
            VALUES (%s, %s, 60.00)
        """, (pool_id, member1_id))
        db.commit()
        
        # Try to add second member (50%) - should fail
        with pytest.raises(psycopg2.IntegrityError):
            cur.execute("""
                INSERT INTO royalty_pool_members (pool_id, user_id, share_percentage)
                VALUES (%s, %s, 50.00)
            """, (pool_id, member2_id))
            db.commit()
        
        db.rollback()
        cur.close()

# ============================================================================
# BLOCKCHAIN INTEGRATION TESTS
# ============================================================================

class TestBlockchainIntegration:
    """Test blockchain transaction recording"""
    
    def test_record_blockchain_transaction(self, db):
        """Test recording blockchain transaction"""
        cur = db.cursor()
        
        tx_id = str(uuid.uuid4())
        tx_hash = "0x" + "a" * 64
        
        cur.execute("""
            INSERT INTO blockchain_transactions (
                id, transaction_hash, blockchain, transaction_type,
                from_address, to_address
            ) VALUES (%s, %s, 'ethereum', 'royalty_payment', %s, %s)
            RETURNING id, transaction_hash
        """, (
            tx_id,
            tx_hash,
            "0x" + "1" * 40,
            "0x" + "2" * 40
        ))
        
        result = cur.fetchone()
        assert result['transaction_hash'] == tx_hash
        
        db.commit()
        cur.close()
    
    def test_unique_transaction_hash(self, db):
        """Test that transaction hash must be unique"""
        cur = db.cursor()
        
        tx_hash = "0x" + "b" * 64
        
        cur.execute("""
            INSERT INTO blockchain_transactions (
                transaction_hash, blockchain, transaction_type
            ) VALUES (%s, 'ethereum', 'content_registration')
        """, (tx_hash,))
        db.commit()
        
        # Try to insert duplicate
        with pytest.raises(psycopg2.IntegrityError):
            cur.execute("""
                INSERT INTO blockchain_transactions (
                    transaction_hash, blockchain, transaction_type
                ) VALUES (%s, 'polygon', 'ownership_transfer')
            """, (tx_hash,))
            db.commit()
        
        db.rollback()
        cur.close()

# ============================================================================
# INSTANT PAYOUTS TESTS
# ============================================================================

class TestInstantPayouts:
    """Test instant payout functionality"""
    
    def test_configure_instant_payout(self, db):
        """Test configuring instant payout"""
        cur = db.cursor()
        
        user_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO users (id, username, email, password_hash)
            VALUES (%s, 'payoutuser', 'payout@test.com', 'hash')
        """, (user_id,))
        
        cur.execute("""
            INSERT INTO instant_payout_configs (
                user_id, enabled, min_threshold, payout_method, payout_destination
            ) VALUES (%s, TRUE, 25.00, 'stripe', 'acct_123')
            RETURNING id, enabled
        """, (user_id,))
        
        result = cur.fetchone()
        assert result['enabled'] is True
        
        db.commit()
        cur.close()
    
    def test_payout_queue(self, db):
        """Test instant payout queue"""
        cur = db.cursor()
        
        user_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO users (id, username, email, password_hash)
            VALUES (%s, 'queueuser', 'queue@test.com', 'hash')
        """, (user_id,))
        
        payout_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO instant_payout_queue (
                id, user_id, amount, payout_method, payout_destination
            ) VALUES (%s, %s, 50.00, 'paypal', 'user@paypal.com')
            RETURNING id, status
        """, (payout_id, user_id))
        
        result = cur.fetchone()
        assert result['status'] == 'pending'
        
        db.commit()
        cur.close()

# ============================================================================
# ANALYTICS TESTS
# ============================================================================

class TestAnalytics:
    """Test royalty analytics"""
    
    def test_refresh_analytics(self, db):
        """Test refreshing analytics materialized view"""
        cur = db.cursor()
        
        cur.execute("SELECT refresh_royalty_analytics()")
        
        # Query analytics
        cur.execute("""
            SELECT COUNT(*) as count FROM royalty_analytics
        """)
        
        result = cur.fetchone()
        assert result['count'] >= 0  # Should not error
        
        cur.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
