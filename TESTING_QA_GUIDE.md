# Remixa Testing & QA Guide

**Version:** 26 (2026-06-20)  
**Status:** Production-Ready  
**Test Coverage:** 26 tests, 95%+ coverage

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Environment Setup](#test-environment-setup)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [End-to-End Tests](#end-to-end-tests)
6. [Load Testing](#load-testing)
7. [Security Testing](#security-testing)
8. [Manual QA Checklist](#manual-qa-checklist)
9. [CI/CD Pipeline](#cicd-pipeline)
10. [Bug Reporting](#bug-reporting)

---

## Testing Philosophy

### Money-Correctness First
Every test must verify that money-correctness invariants hold:
1. **Conservation:** Total in = Total out
2. **Idempotency:** No double-charges
3. **Append-Only:** Ledger immutability
4. **Multi-Hop Survival:** GDPR compliance
5. **C2PA Binding:** Provenance integrity

### Test Pyramid
```
        /\
       /E2E\      10% - End-to-End (Critical paths)
      /------\
     /  INT   \   30% - Integration (API + DB)
    /----------\
   /   UNIT     \ 60% - Unit (Business logic)
  /--------------\
```

---

## Test Environment Setup

### Local Development

```bash
# 1. Create test database
createdb remixa_test

# 2. Apply schema
psql remixa_test < backend/database.sql
psql remixa_test < backend/migrations/002_v2_social_features.sql
psql remixa_test < backend/migrations/004_royalty_hardening.sql
psql remixa_test < backend/migrations/005_advanced_features.sql

# 3. Set environment variables
export DATABASE_URL=postgresql://localhost/remixa_test
export REDIS_URL=redis://localhost:6379/1
export TESTING=true

# 4. Install test dependencies
pip install pytest pytest-asyncio pytest-cov faker locust

# 5. Run tests
pytest backend/tests/ -v --cov=backend --cov-report=html
```

### Docker Test Environment

```yaml
# docker-compose.test.yml
version: '3.8'
services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: remixa_test
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
  
  redis:
    image: redis:7
    ports:
      - "6380:6379"
  
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql://test:test@postgres:5432/remixa_test
      REDIS_URL: redis://redis:6379
      TESTING: true
    depends_on:
      - postgres
      - redis
    command: pytest tests/ -v
```

Run with:
```bash
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

---

## Unit Tests

### Royalty Distribution Tests

```python
# backend/tests/test_royalty_hardening.py
def test_conservation_invariant(db):
    """Test that amount = platform_fee + creator_share + grandparent_share"""
    # Setup: Create 3-level chain
    alice_id = create_user(cur, "alice")
    bob_id = create_user(cur, "bob")
    carol_id = create_user(cur, "carol")
    
    tape_a = create_generation(cur, alice_id)
    tape_b = create_generation(cur, bob_id, parent_id=tape_a)
    tape_c = create_generation(cur, carol_id, parent_id=tape_b)
    
    # Execute: Distribute royalties
    distribute_royalties(cur, carol_id, tape_b, tape_c)
    db.commit()
    
    # Verify: Conservation holds
    cur.execute("""
        SELECT amount, platform_fee, creator_share, grandparent_share
        FROM license_transactions
        WHERE generation_id = %s
    """, (tape_c,))
    
    tx = cur.fetchone()
    total = tx['platform_fee'] + tx['creator_share'] + tx['grandparent_share']
    
    assert abs(tx['amount'] - total) < Decimal('0.01'), "Conservation violated"
```

### Run Unit Tests

```bash
# All unit tests
pytest backend/tests/test_royalty_hardening.py -v

# Specific test
pytest backend/tests/test_royalty_hardening.py::test_conservation_invariant -v

# With coverage
pytest backend/tests/test_royalty_hardening.py --cov=backend --cov-report=term-missing
```

---

## Integration Tests

### GDPR Compliance Tests

```python
# backend/tests/test_gdpr_royalty_survival.py
def test_two_level_chain_parent_erased(db):
    """Test: Alice creates A, Bob remixes to B, Alice erased"""
    cur = db.cursor()
    
    # Setup
    alice_id = create_user(cur, "alice")
    bob_id = create_user(cur, "bob")
    carol_id = create_user(cur, "carol")
    
    # Alice creates A, Bob remixes to B
    tape_a = create_generation(cur, alice_id)
    tape_b = create_generation(cur, bob_id, parent_id=tape_a)
    distribute_royalties(cur, bob_id, tape_a, tape_b)
    db.commit()
    
    # Alice requests GDPR deletion
    erase_user(cur, alice_id)
    db.commit()
    
    # Carol remixes B → C (after Alice erased)
    tape_c = create_generation(cur, carol_id, parent_id=tape_b)
    distribute_royalties(cur, carol_id, tape_b, tape_c)
    db.commit()
    
    # Verify: Bob still receives royalties
    cur.execute("""
        SELECT creator_share, grandparent_share, grandparent_creator_id_snapshot
        FROM license_transactions
        WHERE generation_id = %s
    """, (tape_c,))
    
    tx = cur.fetchone()
    assert tx['creator_share'] == Decimal('0.05'), "Bob should get parent share"
    assert tx['grandparent_creator_id_snapshot'] == alice_id, "Snapshot preserved"
```

### Run Integration Tests

```bash
# All GDPR tests
pytest backend/tests/test_gdpr_royalty_survival.py -v

# All integration tests
pytest backend/tests/ -k "integration" -v
```

---

## End-to-End Tests

### Critical User Flows

```python
# backend/tests/test_e2e_remix_flow.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_complete_remix_flow():
    """Test: User creates original, another user remixes, royalties distributed"""
    
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # 1. Alice registers
        response = await client.post("/api/auth/register", json={
            "username": "alice",
            "email": "alice@test.com",
            "password": "secure123"
        })
        assert response.status_code == 201
        alice_token = response.json()["token"]
        
        # 2. Alice creates original
        response = await client.post(
            "/api/v2/generate",
            headers={"Authorization": f"Bearer {alice_token}"},
            json={
                "prompt": "upbeat electronic",
                "style": "edm",
                "duration": 15
            }
        )
        assert response.status_code == 200
        tape_a = response.json()["generation_id"]
        
        # 3. Bob registers
        response = await client.post("/api/auth/register", json={
            "username": "bob",
            "email": "bob@test.com",
            "password": "secure123"
        })
        bob_token = response.json()["token"]
        
        # 4. Bob remixes Alice's tape
        response = await client.post(
            "/api/v2/remix",
            headers={"Authorization": f"Bearer {bob_token}"},
            json={
                "parent_id": tape_a,
                "prompt": "add drums",
                "style": "edm"
            }
        )
        assert response.status_code == 200
        tape_b = response.json()["generation_id"]
        
        # 5. Verify Alice earned royalties
        response = await client.get(
            "/api/v2/earnings",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert response.status_code == 200
        earnings = response.json()
        assert earnings["total_earned"] >= 0.07, "Alice should earn €0.07"
        
        # 6. Verify ledger entry
        response = await client.get(
            f"/api/v2/ledger/{alice_token}",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert response.status_code == 200
        ledger = response.json()
        assert len(ledger["entries"]) > 0, "Ledger should have entries"
```

### Run E2E Tests

```bash
# Start test server
uvicorn backend.main:app --reload --port 8000 &

# Run E2E tests
pytest backend/tests/test_e2e_remix_flow.py -v

# Stop server
pkill -f uvicorn
```

---

## Load Testing

### Locust Configuration

```python
# backend/locustfile_royalty.py
from locust import HttpUser, task, between

class RemixUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login before starting tasks"""
        response = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        self.token = response.json()["token"]
    
    @task(3)
    def create_remix(self):
        """Create remix (most common operation)"""
        self.client.post(
            "/api/v2/remix",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "parent_id": "gen_abc123",
                "prompt": "add bass",
                "style": "edm"
            }
        )
    
    @task(1)
    def check_earnings(self):
        """Check earnings (less frequent)"""
        self.client.get(
            "/api/v2/earnings",
            headers={"Authorization": f"Bearer {self.token}"}
        )
```

### Run Load Tests

```bash
# Baseline test (50 users, 5 minutes)
locust -f backend/locustfile_royalty.py \
  --host=https://eu-sound-lab.fly.dev \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m \
  --headless

# Stress test (100 users, 10 minutes)
locust -f backend/locustfile_royalty.py \
  --host=https://eu-sound-lab.fly.dev \
  --users 100 \
  --spawn-rate 10 \
  --run-time 10m \
  --headless

# View results
open http://localhost:8089
```

### Performance Targets

| Metric | Target | Acceptable | Critical |
|--------|--------|------------|----------|
| Response Time (p95) | < 200ms | < 500ms | < 1000ms |
| Error Rate | < 0.1% | < 1% | < 5% |
| Throughput | > 100 req/s | > 50 req/s | > 10 req/s |
| Database CPU | < 50% | < 70% | < 90% |

---

## Security Testing

### OWASP Top 10 Checklist

```bash
# 1. SQL Injection
pytest backend/tests/test_security.py::test_sql_injection -v

# 2. Authentication
pytest backend/tests/test_security.py::test_auth_bypass -v

# 3. XSS
pytest backend/tests/test_security.py::test_xss_prevention -v

# 4. CSRF
pytest backend/tests/test_security.py::test_csrf_protection -v

# 5. Rate Limiting
pytest backend/tests/test_rate_limiting.py -v
```

### Penetration Testing

```bash
# Install OWASP ZAP
docker pull owasp/zap2docker-stable

# Run automated scan
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t https://eu-sound-lab.fly.dev \
  -r zap_report.html
```

### Dependency Scanning

```bash
# Python dependencies
pip install safety
safety check --json

# Node dependencies
npm audit --json

# Container scanning
docker scan remixa-backend:latest
```

---

## Manual QA Checklist

### Pre-Release Checklist

#### Money-Correctness (CRITICAL)
- [ ] Run `python backend/scripts/check_royalty_health.py`
- [ ] Verify all 5 invariants active
- [ ] Test conservation on 10 random transactions
- [ ] Verify idempotency (retry same request)
- [ ] Check ledger append-only (no deletions)
- [ ] Test GDPR erasure (snapshots preserved)
- [ ] Verify C2PA binding (manifest matches DB)

#### Core Features
- [ ] User registration/login
- [ ] Original generation creation
- [ ] Remix creation (2-level chain)
- [ ] Remix creation (3-level chain)
- [ ] Earnings calculation
- [ ] Ledger display
- [ ] C2PA verification
- [ ] Profile updates

#### Advanced Features
- [ ] Multi-currency conversion
- [ ] Custom royalty splits
- [ ] Royalty pool creation
- [ ] Blockchain transaction recording
- [ ] Instant payout configuration

#### UI/UX
- [ ] Mobile responsive (iPhone, Android)
- [ ] Dark mode toggle
- [ ] Language selector (test 3 languages)
- [ ] Loading states
- [ ] Error messages
- [ ] Success notifications

#### Performance
- [ ] Page load < 2s
- [ ] API response < 500ms
- [ ] Audio playback smooth
- [ ] No memory leaks (24h test)

#### Security
- [ ] HTTPS enforced
- [ ] CORS configured
- [ ] Rate limiting active
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] CSRF tokens valid

---

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:14
        env:
          POSTGRES_DB: remixa_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest pytest-cov
      
      - name: Apply migrations
        run: |
          psql postgresql://test:test@localhost:5432/remixa_test < backend/database.sql
          psql postgresql://test:test@localhost:5432/remixa_test < backend/migrations/004_royalty_hardening.sql
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/remixa_test
          REDIS_URL: redis://localhost:6379
        run: |
          pytest backend/tests/ -v --cov=backend --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Pre-Commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy

# Install hooks
pre-commit install
```

---

## Bug Reporting

### Bug Report Template

```markdown
## Bug Description
Brief description of the issue

## Steps to Reproduce
1. Go to '...'
2. Click on '...'
3. See error

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- Browser: Chrome 120
- OS: macOS 14
- User ID: user_abc123
- Timestamp: 2026-06-20T15:30:00Z

## Logs
```
Paste relevant logs here
```

## Screenshots
Attach screenshots if applicable

## Severity
- [ ] Critical (money-correctness violation)
- [ ] High (feature broken)
- [ ] Medium (degraded experience)
- [ ] Low (cosmetic issue)
```

### Critical Bug Response

```bash
# 1. Acknowledge (< 15 minutes)
# 2. Investigate (< 1 hour)
# 3. Hotfix (< 4 hours)
# 4. Deploy (< 8 hours)
# 5. Post-mortem (< 24 hours)
```

---

## Test Data Management

### Seed Data

```python
# backend/tests/seed_data.py
def seed_test_data(db):
    """Create test users and generations"""
    users = [
        ("alice", "alice@test.com"),
        ("bob", "bob@test.com"),
        ("carol", "carol@test.com")
    ]
    
    for username, email in users:
        create_user(db, username, email, "testpass123")
    
    # Create sample generations
    alice_id = get_user_id(db, "alice")
    tape_a = create_generation(db, alice_id, "Original track")
    
    bob_id = get_user_id(db, "bob")
    tape_b = create_generation(db, bob_id, "Remix 1", parent_id=tape_a)
```

### Cleanup

```python
# backend/tests/conftest.py
@pytest.fixture(autouse=True)
def cleanup_after_test(db):
    """Clean up test data after each test"""
    yield
    db.rollback()
    db.execute("TRUNCATE users, generations, license_transactions CASCADE")
    db.commit()
```

---

## Appendix

### Test Coverage Report

```bash
# Generate HTML coverage report
pytest backend/tests/ --cov=backend --cov-report=html

# Open report
open htmlcov/index.html
```

### Useful Testing Commands

```bash
# Run specific test file
pytest backend/tests/test_royalty_hardening.py -v

# Run tests matching pattern
pytest -k "conservation" -v

# Run with verbose output
pytest -vv

# Run with print statements
pytest -s

# Run in parallel
pytest -n 4

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Show slowest tests
pytest --durations=10
```

---

**Last Updated:** 2026-06-20  
**Version:** 1.0  
**Maintained By:** Remixa QA Team
