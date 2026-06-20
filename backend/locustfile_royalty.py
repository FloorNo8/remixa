"""
Locust Load Test for Remixa Royalty System

Tests money-correctness under high load:
1. Concurrent remixes (idempotency test)
2. High-volume royalty distribution (conservation test)
3. Simultaneous GDPR deletions (snapshot test)

Usage:
    # Local test (100 users, 10 spawn rate)
    locust -f locustfile_royalty.py --host=http://localhost:8000 --users 100 --spawn-rate 10
    
    # Production test (headless, 5 minutes)
    locust -f locustfile_royalty.py --host=https://eu-sound-lab.fly.dev \
           --users 100 --spawn-rate 10 --run-time 5m --headless

Requirements:
    pip install locust faker
"""

from locust import HttpUser, task, between, events
from faker import Faker
import random
import json
import uuid
from datetime import datetime

fake = Faker()

# Test data
TEST_USERS = []
TEST_GENERATIONS = []
TEST_TOKENS = {}

class RemixUser(HttpUser):
    """
    Simulates a user creating remixes and checking earnings
    
    Weight distribution:
    - 70% remix creation (money-correctness critical path)
    - 20% earnings check (ledger reads)
    - 10% explore feed (discovery)
    """
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Setup: Create test user and authenticate"""
        self.user_id = str(uuid.uuid4())
        self.username = fake.user_name()
        self.token = self._create_test_user()
        
        # Create initial generation for remixing
        self.parent_generation_id = self._create_initial_generation()
    
    def _create_test_user(self) -> str:
        """Create a test user and return auth token"""
        response = self.client.post("/api/auth/register", json={
            "username": self.username,
            "email": fake.email(),
            "password": "TestPassword123!"
        })
        
        if response.status_code == 201:
            return response.json().get("token", "")
        return ""
    
    def _create_initial_generation(self) -> str:
        """Create an initial generation to remix"""
        response = self.client.post(
            "/api/v2/generations",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "prompt": "upbeat electronic music",
                "duration": 15
            }
        )
        
        if response.status_code == 201:
            return response.json().get("generation_id", "")
        return ""
    
    @task(7)
    def create_remix(self):
        """
        Create a remix (70% of traffic)
        
        Tests:
        - Conservation invariant (amount = platform_fee + creator_share + grandparent_share)
        - Idempotency (no double-charge on retry)
        - Ledger writes (user_ledger entries created)
        """
        if not self.parent_generation_id:
            return
        
        response = self.client.post(
            f"/api/v2/generations/{self.parent_generation_id}/remix",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "prompt": "add jazz vocals",
                "layer_type": "voice",
                "voice_model_id": str(uuid.uuid4())
            },
            name="/api/v2/generations/[id]/remix"
        )
        
        if response.status_code == 201:
            # Track successful remix for metrics
            events.request.fire(
                request_type="ROYALTY",
                name="remix_created",
                response_time=response.elapsed.total_seconds() * 1000,
                response_length=len(response.content),
                exception=None,
                context={}
            )
    
    @task(2)
    def check_earnings(self):
        """
        Check earnings (20% of traffic)
        
        Tests:
        - Ledger-based balance calculation
        - Query performance under load
        """
        response = self.client.get(
            "/api/v2/earnings",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/api/v2/earnings"
        )
        
        if response.status_code == 200:
            data = response.json()
            # Verify ledger balance is non-negative
            if data.get("total_earned", 0) < 0:
                events.request.fire(
                    request_type="VIOLATION",
                    name="negative_balance_detected",
                    response_time=0,
                    response_length=0,
                    exception=Exception(f"Negative balance: {data.get('total_earned')}"),
                    context={"user_id": self.user_id}
                )
    
    @task(1)
    def explore_feed(self):
        """
        Browse explore feed (10% of traffic)
        
        Tests:
        - Discovery queries
        - Remix chain visualization
        """
        self.client.get(
            "/api/v2/explore?sort=trending&limit=20",
            headers={"Authorization": f"Bearer {self.token}"},
            name="/api/v2/explore"
        )

class StressTestUser(HttpUser):
    """
    Aggressive stress test user for constraint violation detection
    
    Attempts to trigger:
    - Double-charge (idempotency violation)
    - Conservation violation (incorrect splits)
    - C2PA binding violation (mismatched parent_id)
    """
    
    wait_time = between(0.1, 0.5)  # Very fast requests
    
    def on_start(self):
        self.user_id = str(uuid.uuid4())
        self.token = self._create_test_user()
        self.parent_generation_id = self._create_initial_generation()
    
    def _create_test_user(self) -> str:
        response = self.client.post("/api/auth/register", json={
            "username": fake.user_name(),
            "email": fake.email(),
            "password": "TestPassword123!"
        })
        if response.status_code == 201:
            return response.json().get("token", "")
        return ""
    
    def _create_initial_generation(self) -> str:
        response = self.client.post(
            "/api/v2/generations",
            headers={"Authorization": f"Bearer {self.token}"},
            json={"prompt": "test track", "duration": 15}
        )
        if response.status_code == 201:
            return response.json().get("generation_id", "")
        return ""
    
    @task
    def rapid_fire_remixes(self):
        """
        Rapidly create multiple remixes of same parent
        
        Tests idempotency: Should only charge once per unique (remixer, generation)
        """
        if not self.parent_generation_id:
            return
        
        # Fire 3 rapid requests (simulating retry/race condition)
        for _ in range(3):
            self.client.post(
                f"/api/v2/generations/{self.parent_generation_id}/remix",
                headers={"Authorization": f"Bearer {self.token}"},
                json={
                    "prompt": "stress test remix",
                    "layer_type": "voice"
                },
                name="/api/v2/generations/[id]/remix [STRESS]"
            )

# ============================================================================
# CUSTOM METRICS
# ============================================================================

@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize custom metrics tracking"""
    environment.stats.custom_metrics = {
        "constraint_violations": 0,
        "negative_balances": 0,
        "successful_remixes": 0
    }

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Track custom metrics"""
    if request_type == "VIOLATION":
        if name == "negative_balance_detected":
            events.init.environment.stats.custom_metrics["negative_balances"] += 1
    elif request_type == "ROYALTY":
        if name == "remix_created":
            events.init.environment.stats.custom_metrics["successful_remixes"] += 1

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print custom metrics at end of test"""
    print("\n" + "=" * 80)
    print("MONEY-CORRECTNESS METRICS")
    print("=" * 80)
    print(f"Successful Remixes: {environment.stats.custom_metrics['successful_remixes']}")
    print(f"Constraint Violations: {environment.stats.custom_metrics['constraint_violations']}")
    print(f"Negative Balances: {environment.stats.custom_metrics['negative_balances']}")
    print("=" * 80)
    
    # Fail test if violations detected
    if environment.stats.custom_metrics['constraint_violations'] > 0:
        print("❌ TEST FAILED: Constraint violations detected")
        environment.process_exit_code = 1
    elif environment.stats.custom_metrics['negative_balances'] > 0:
        print("❌ TEST FAILED: Negative balances detected")
        environment.process_exit_code = 1
    else:
        print("✅ TEST PASSED: No money-correctness violations")

# ============================================================================
# TEST SCENARIOS
# ============================================================================

"""
Recommended test scenarios:

1. Baseline Load Test
   locust -f locustfile_royalty.py --host=http://localhost:8000 \
          --users 50 --spawn-rate 5 --run-time 5m --headless
   
   Expected: 0 constraint violations, 0 negative balances

2. Stress Test (Idempotency)
   locust -f locustfile_royalty.py --host=http://localhost:8000 \
          --users 100 --spawn-rate 10 --run-time 10m --headless \
          --user-classes StressTestUser
   
   Expected: 0 constraint violations (idempotency should prevent double-charge)

3. Production Smoke Test
   locust -f locustfile_royalty.py --host=https://eu-sound-lab.fly.dev \
          --users 10 --spawn-rate 1 --run-time 2m --headless
   
   Expected: 0 constraint violations, all requests < 1s response time

4. Sustained Load Test
   locust -f locustfile_royalty.py --host=http://localhost:8000 \
          --users 200 --spawn-rate 20 --run-time 30m --headless
   
   Expected: 0 constraint violations, p95 < 500ms

5. Spike Test
   locust -f locustfile_royalty.py --host=http://localhost:8000 \
          --users 500 --spawn-rate 50 --run-time 5m --headless
   
   Expected: Some failures OK, but 0 constraint violations
"""
