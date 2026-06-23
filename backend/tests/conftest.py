"""
Pytest Configuration and Fixtures
Shared test fixtures for all test modules
"""

import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
import os
from typing import Generator
import uuid
from datetime import datetime

# ============================================================================
# DATABASE FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def test_db_url():
    """Get test database URL from environment"""
    return os.getenv("TEST_DATABASE_URL", "postgresql://localhost/eu_sound_lab_test")


@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema(test_db_url):
    """
    Build the full schema (database.sql + migrations/*.sql, in order) in the test DB
    before any test runs. CI provides an empty Postgres, so without this every DB-backed
    test errored with 'relation does not exist' rather than actually running (FN8-696).
    Idempotent: resets the public schema so a re-run is deterministic.
    Verified end-to-end against postgres:14 (all files apply exit 0).
    """
    import glob

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sql_files = [os.path.join(backend_dir, "database.sql")]
    sql_files += sorted(glob.glob(os.path.join(backend_dir, "migrations", "*.sql")))

    conn = psycopg2.connect(test_db_url)
    conn.autocommit = True
    try:
        cur = conn.cursor()
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        for path in sql_files:
            with open(path, "r", encoding="utf-8") as fh:
                sql = fh.read()
            # psycopg2 runs a multi-statement string as ONE transaction, so strip
            # CONCURRENTLY (CREATE INDEX / REFRESH MATERIALIZED VIEW), which cannot run in
            # a transaction block. Harmless on a fresh test DB, and it lets the royalty
            # function refresh the matview inside a test transaction.
            cur.execute(sql.replace(" CONCURRENTLY", ""))
        cur.close()
    finally:
        conn.close()
    yield

@pytest.fixture(scope="function")
def db_connection(test_db_url):
    """
    Provide a clean database connection for each test
    Automatically rolls back after test
    """
    conn = psycopg2.connect(test_db_url, cursor_factory=RealDictCursor)
    conn.autocommit = False
    
    yield conn
    
    # Rollback any changes
    conn.rollback()
    conn.close()

@pytest.fixture(scope="function")
def db_cursor(db_connection):
    """Provide a database cursor"""
    cursor = db_connection.cursor()
    yield cursor
    cursor.close()

# ============================================================================
# REDIS FIXTURES
# ============================================================================

@pytest.fixture(scope="session")
def redis_url():
    """Get Redis URL from environment"""
    return os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")

@pytest.fixture(scope="function")
def redis_client(redis_url):
    """
    Provide a Redis client for testing
    Flushes test database after each test
    """
    client = redis.from_url(redis_url, decode_responses=True)
    
    yield client
    
    # Clean up
    client.flushdb()
    client.close()

# ============================================================================
# TEST DATA FIXTURES
# ============================================================================

@pytest.fixture
def test_user(db_connection):
    """Create a test user"""
    cursor = db_connection.cursor()
    
    user_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, stripe_customer_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id, email, subscription_tier
    """, (user_id, f"test_{user_id[:8]}@example.com", "pro", f"cus_{user_id[:12]}"))
    
    user = cursor.fetchone()
    db_connection.commit()
    
    return dict(user)

@pytest.fixture
def test_free_user(db_connection):
    """Create a test free tier user"""
    cursor = db_connection.cursor()
    
    user_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, stripe_customer_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id, email, subscription_tier
    """, (user_id, f"free_{user_id[:8]}@example.com", "free", f"cus_{user_id[:12]}"))
    
    user = cursor.fetchone()
    db_connection.commit()
    
    return dict(user)

@pytest.fixture
def test_generation(db_connection, test_user):
    """Create a test generation"""
    cursor = db_connection.cursor()
    
    gen_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id, user_id, audio_url, is_public, parent_id, remix_chain
    """, (
        gen_id, test_user['id'], "test prompt", "lofi", 15,
        f"https://cdn.test.com/{gen_id}.mp3",
        f"https://cdn.test.com/{gen_id}.c2pa.json",
        2500, 0.008, "eu-sound-lab-v1", "test_hash",
        "base", True, 0.10
    ))
    
    generation = cursor.fetchone()
    db_connection.commit()
    
    return dict(generation)

@pytest.fixture
def test_remix_chain(db_connection, test_user):
    """
    Create a 3-level remix chain for testing royalty distribution
    Returns: (root_gen, child_gen, grandchild_gen)
    """
    cursor = db_connection.cursor()
    
    # Root generation
    root_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, remix_chain
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[]
        )
        RETURNING id, user_id, audio_url, parent_id, remix_chain
    """, (
        root_id, test_user['id'], "root prompt", "lofi", 15,
        f"https://cdn.test.com/{root_id}.mp3",
        f"https://cdn.test.com/{root_id}.c2pa.json",
        2500, 0.008, "eu-sound-lab-v1", "test_hash",
        "base", True, 0.10, []
    ))
    root = dict(cursor.fetchone())
    
    # Child generation (remix of root)
    child_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[]
        )
        RETURNING id, user_id, audio_url, parent_id, remix_chain
    """, (
        child_id, test_user['id'], "child prompt", "lofi", 15,
        f"https://cdn.test.com/{child_id}.mp3",
        f"https://cdn.test.com/{child_id}.c2pa.json",
        2500, 0.008, "eu-sound-lab-v1", "test_hash",
        "voice", True, 0.10, root_id, [root_id]
    ))
    child = dict(cursor.fetchone())
    
    # Grandchild generation (remix of child)
    grandchild_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[]
        )
        RETURNING id, user_id, audio_url, parent_id, remix_chain
    """, (
        grandchild_id, test_user['id'], "grandchild prompt", "lofi", 15,
        f"https://cdn.test.com/{grandchild_id}.mp3",
        f"https://cdn.test.com/{grandchild_id}.c2pa.json",
        2500, 0.008, "eu-sound-lab-v1", "test_hash",
        "lyrics", True, 0.10, child_id, [root_id, child_id]
    ))
    grandchild = dict(cursor.fetchone())
    
    db_connection.commit()
    
    return (root, child, grandchild)

@pytest.fixture
def mock_stripe_payment_intent():
    """Mock Stripe PaymentIntent for testing"""
    return {
        "id": "pi_test_123456",
        "status": "succeeded",
        "amount": 10,
        "currency": "eur",
        "customer": "cus_test123"
    }

# ============================================================================
# API CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def api_client():
    """
    Provide a test client for API testing
    TODO: Implement when FastAPI TestClient is needed
    """
    from fastapi.testclient import TestClient
    from main import app
    
    return TestClient(app)

# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data():
    """Clean up test data after all tests"""
    yield
    
    # Cleanup code runs after all tests
    print("\n🧹 Cleaning up test data...")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_test_user(db_connection, email: str = None, tier: str = "free") -> dict:
    """Helper to create a test user"""
    cursor = db_connection.cursor()
    
    user_id = str(uuid.uuid4())
    email = email or f"test_{user_id[:8]}@example.com"
    
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, stripe_customer_id)
        VALUES (%s, %s, %s, %s)
        RETURNING id, email, subscription_tier
    """, (user_id, email, tier, f"cus_{user_id[:12]}"))
    
    user = cursor.fetchone()
    db_connection.commit()
    
    return dict(user)

def create_test_generation(
    db_connection,
    user_id: str,
    parent_id: str = None,
    is_public: bool = True
) -> dict:
    """Helper to create a test generation"""
    cursor = db_connection.cursor()
    
    gen_id = str(uuid.uuid4())
    remix_chain = [parent_id] if parent_id else []
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, parent_id, remix_chain
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid[]
        )
        RETURNING id, user_id, audio_url, is_public, parent_id, remix_chain
    """, (
        gen_id, user_id, "test prompt", "lofi", 15,
        f"https://cdn.test.com/{gen_id}.mp3",
        f"https://cdn.test.com/{gen_id}.c2pa.json",
        2500, 0.008, "eu-sound-lab-v1", "test_hash",
        "base", is_public, 0.10, parent_id, remix_chain
    ))
    
    generation = cursor.fetchone()
    db_connection.commit()
    
    return dict(generation)
