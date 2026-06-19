"""
Load Testing with Locust for EU TikTok Sound Lab

Target: 100 concurrent users, p95 response time <5s

Test scenarios:
1. Browse feed (GET /api/feed)
2. Create generation (POST /api/generate)
3. Create remix (POST /api/remix)
4. View generation (GET /api/generation/{id})
5. Upload to TikTok (POST /api/tiktok/upload)

Run: locust -f locustfile.py --host=https://api.eu-sound-lab.com
"""

from locust import HttpUser, task, between, events
import random
import json
import time
from datetime import datetime

# ============================================================================
# TEST DATA
# ============================================================================

SAMPLE_PROMPTS = [
    "lofi hip hop beat with rain sounds",
    "upbeat electronic dance music",
    "chill ambient soundscape",
    "energetic rock guitar riff",
    "smooth jazz piano melody",
    "epic orchestral cinematic music",
    "tropical house summer vibes",
    "dark techno industrial beat",
    "acoustic folk guitar",
    "synthwave retro 80s"
]

SAMPLE_STYLES = ["lofi", "edm", "ambient", "rock", "jazz", "orchestral", "house", "techno", "folk", "synthwave"]

SAMPLE_VOICES = ["male_deep", "female_soft", "child_playful", "robot_monotone"]

# Test user tokens (replace with actual test tokens)
TEST_TOKENS = [
    "test_token_1",
    "test_token_2",
    "test_token_3",
]

# ============================================================================
# CUSTOM METRICS
# ============================================================================

generation_times = []
remix_times = []
upload_times = []

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Print custom metrics at end of test"""
    if generation_times:
        avg_gen = sum(generation_times) / len(generation_times)
        p95_gen = sorted(generation_times)[int(len(generation_times) * 0.95)]
        print(f"\n📊 Generation Times: avg={avg_gen:.2f}s, p95={p95_gen:.2f}s")
    
    if remix_times:
        avg_remix = sum(remix_times) / len(remix_times)
        p95_remix = sorted(remix_times)[int(len(remix_times) * 0.95)]
        print(f"📊 Remix Times: avg={avg_remix:.2f}s, p95={p95_remix:.2f}s")
    
    if upload_times:
        avg_upload = sum(upload_times) / len(upload_times)
        p95_upload = sorted(upload_times)[int(len(upload_times) * 0.95)]
        print(f"📊 Upload Times: avg={avg_upload:.2f}s, p95={p95_upload:.2f}s")

# ============================================================================
# BASE USER CLASS
# ============================================================================

class EUSoundLabUser(HttpUser):
    """Base user class with common functionality"""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts"""
        self.token = random.choice(TEST_TOKENS)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        self.generation_ids = []
        self.public_generation_ids = []
    
    def get_random_generation_id(self):
        """Get a random generation ID from cache or fetch from feed"""
        if not self.public_generation_ids:
            # Fetch from feed
            response = self.client.get(
                "/api/feed",
                headers=self.headers,
                name="/api/feed (cache miss)"
            )
            if response.status_code == 200:
                data = response.json()
                self.public_generation_ids = [g['id'] for g in data.get('generations', [])]
        
        if self.public_generation_ids:
            return random.choice(self.public_generation_ids)
        return None

# ============================================================================
# BROWSING USER (60% of traffic)
# ============================================================================

class BrowsingUser(EUSoundLabUser):
    """User who browses feed and views generations"""
    
    weight = 60
    
    @task(10)
    def browse_feed(self):
        """Browse the main feed"""
        self.client.get(
            "/api/feed",
            headers=self.headers,
            name="/api/feed"
        )
    
    @task(5)
    def view_generation(self):
        """View a specific generation"""
        gen_id = self.get_random_generation_id()
        if gen_id:
            self.client.get(
                f"/api/generation/{gen_id}",
                headers=self.headers,
                name="/api/generation/[id]"
            )
    
    @task(3)
    def view_profile(self):
        """View a user profile"""
        gen_id = self.get_random_generation_id()
        if gen_id:
            # Get generation to find user_id
            response = self.client.get(
                f"/api/generation/{gen_id}",
                headers=self.headers,
                name="/api/generation/[id] (for profile)"
            )
            if response.status_code == 200:
                user_id = response.json().get('user_id')
                if user_id:
                    self.client.get(
                        f"/api/profile/{user_id}",
                        headers=self.headers,
                        name="/api/profile/[id]"
                    )
    
    @task(2)
    def search_generations(self):
        """Search for generations"""
        query = random.choice(["lofi", "edm", "chill", "upbeat", "ambient"])
        self.client.get(
            f"/api/search?q={query}",
            headers=self.headers,
            name="/api/search"
        )

# ============================================================================
# CREATOR USER (30% of traffic)
# ============================================================================

class CreatorUser(EUSoundLabUser):
    """User who creates generations and remixes"""
    
    weight = 30
    
    @task(5)
    def create_generation(self):
        """Create a new generation"""
        start_time = time.time()
        
        payload = {
            "prompt": random.choice(SAMPLE_PROMPTS),
            "style": random.choice(SAMPLE_STYLES),
            "duration_seconds": random.choice([15, 30, 60]),
            "is_public": random.choice([True, False])
        }
        
        response = self.client.post(
            "/api/generate",
            headers=self.headers,
            json=payload,
            name="/api/generate"
        )
        
        if response.status_code == 200:
            gen_id = response.json().get('generation_id')
            if gen_id:
                self.generation_ids.append(gen_id)
                if payload['is_public']:
                    self.public_generation_ids.append(gen_id)
            
            # Track generation time
            elapsed = time.time() - start_time
            generation_times.append(elapsed)
    
    @task(3)
    def create_remix(self):
        """Create a remix of existing generation"""
        parent_id = self.get_random_generation_id()
        if not parent_id:
            return
        
        start_time = time.time()
        
        payload = {
            "parent_id": parent_id,
            "layer_type": random.choice(["voice", "lyrics", "effects"]),
            "prompt": random.choice(SAMPLE_PROMPTS),
            "voice_model_id": random.choice(SAMPLE_VOICES) if random.random() > 0.5 else None
        }
        
        response = self.client.post(
            "/api/remix",
            headers=self.headers,
            json=payload,
            name="/api/remix"
        )
        
        if response.status_code == 200:
            gen_id = response.json().get('generation_id')
            if gen_id:
                self.generation_ids.append(gen_id)
            
            # Track remix time
            elapsed = time.time() - start_time
            remix_times.append(elapsed)
    
    @task(2)
    def view_my_generations(self):
        """View own generations"""
        self.client.get(
            "/api/my-generations",
            headers=self.headers,
            name="/api/my-generations"
        )
    
    @task(1)
    def view_earnings(self):
        """View earnings dashboard"""
        self.client.get(
            "/api/earnings",
            headers=self.headers,
            name="/api/earnings"
        )

# ============================================================================
# POWER USER (10% of traffic)
# ============================================================================

class PowerUser(EUSoundLabUser):
    """User who uploads to TikTok and uses advanced features"""
    
    weight = 10
    
    @task(3)
    def upload_to_tiktok(self):
        """Upload generation to TikTok"""
        if not self.generation_ids:
            return
        
        start_time = time.time()
        
        gen_id = random.choice(self.generation_ids)
        payload = {
            "generation_id": gen_id,
            "caption": f"Check out this sound! #{random.choice(SAMPLE_STYLES)} #music",
            "privacy_level": "public_to_everyone"
        }
        
        response = self.client.post(
            "/api/tiktok/upload",
            headers=self.headers,
            json=payload,
            name="/api/tiktok/upload"
        )
        
        if response.status_code == 200:
            elapsed = time.time() - start_time
            upload_times.append(elapsed)
    
    @task(2)
    def verify_c2pa(self):
        """Verify C2PA manifest"""
        gen_id = self.get_random_generation_id()
        if gen_id:
            self.client.get(
                f"/api/c2pa/verify/{gen_id}",
                headers=self.headers,
                name="/api/c2pa/verify/[id]"
            )
    
    @task(2)
    def view_provenance(self):
        """View generation provenance chain"""
        gen_id = self.get_random_generation_id()
        if gen_id:
            self.client.get(
                f"/api/generation/{gen_id}/provenance",
                headers=self.headers,
                name="/api/generation/[id]/provenance"
            )
    
    @task(1)
    def check_rate_limits(self):
        """Check rate limit status"""
        self.client.get(
            "/api/v1/rate-limit/info",
            headers=self.headers,
            name="/api/v1/rate-limit/info"
        )
    
    @task(1)
    def view_leaderboard(self):
        """View leaderboard"""
        self.client.get(
            "/api/leaderboard",
            headers=self.headers,
            name="/api/leaderboard"
        )

# ============================================================================
# HEALTH CHECK USER (runs continuously)
# ============================================================================

class HealthCheckUser(EUSoundLabUser):
    """User that continuously checks health endpoints"""
    
    weight = 1
    wait_time = between(5, 10)  # Check every 5-10 seconds
    
    @task
    def health_check(self):
        """Check API health"""
        self.client.get(
            "/health",
            name="/health"
        )
    
    @task
    def metrics_check(self):
        """Check Prometheus metrics"""
        self.client.get(
            "/metrics",
            name="/metrics"
        )

# ============================================================================
# STRESS TEST SCENARIOS
# ============================================================================

class StressTestUser(EUSoundLabUser):
    """User for stress testing specific endpoints"""
    
    weight = 0  # Disabled by default, enable for stress tests
    
    @task
    def rapid_fire_generations(self):
        """Create many generations rapidly"""
        for i in range(10):
            payload = {
                "prompt": f"stress test {i}",
                "style": "lofi",
                "duration_seconds": 15,
                "is_public": False
            }
            self.client.post(
                "/api/generate",
                headers=self.headers,
                json=payload,
                name="/api/generate (stress)"
            )
            time.sleep(0.1)  # Small delay to avoid rate limiting

# ============================================================================
# CUSTOM LOAD SHAPE (OPTIONAL)
# ============================================================================

from locust import LoadTestShape

class StepLoadShape(LoadTestShape):
    """
    Step load pattern:
    - Start with 10 users
    - Increase by 10 every 60 seconds
    - Max 100 users
    - Run for 10 minutes total
    """
    
    step_time = 60  # Seconds per step
    step_load = 10  # Users to add per step
    spawn_rate = 5  # Users to spawn per second
    time_limit = 600  # Total test duration (10 minutes)
    
    def tick(self):
        run_time = self.get_run_time()
        
        if run_time > self.time_limit:
            return None
        
        current_step = run_time // self.step_time
        user_count = min((current_step + 1) * self.step_load, 100)
        
        return (user_count, self.spawn_rate)

# ============================================================================
# USAGE INSTRUCTIONS
# ============================================================================

"""
Run load tests:

1. Basic test (100 users, 5 min):
   locust -f locustfile.py --host=https://api.eu-sound-lab.com --users 100 --spawn-rate 10 --run-time 5m

2. Step load test:
   locust -f locustfile.py --host=https://api.eu-sound-lab.com --headless

3. Web UI (recommended):
   locust -f locustfile.py --host=https://api.eu-sound-lab.com
   # Open http://localhost:8089

4. Distributed load test (multiple machines):
   # Master:
   locust -f locustfile.py --master --host=https://api.eu-sound-lab.com
   
   # Workers (on other machines):
   locust -f locustfile.py --worker --master-host=<master-ip>

5. Export results:
   locust -f locustfile.py --host=https://api.eu-sound-lab.com --headless --html=report.html --csv=results

Target metrics:
- p95 response time: <5s for all endpoints
- Error rate: <1%
- Throughput: >100 req/s
- Concurrent users: 100
"""
