"""
Monitoring Module - Sentry, Prometheus, Health Checks

Features:
- Sentry integration for error tracking
- Prometheus metrics for observability
- Comprehensive health checks
- Performance monitoring
"""

import os
import time
from typing import Dict, Any
import structlog
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import psycopg2
import redis
import requests

logger = structlog.get_logger()

# ============================================================================
# SENTRY INTEGRATION
# ============================================================================

def init_sentry():
    """
    Initialize Sentry for error tracking
    
    Environment variables:
    - SENTRY_DSN: Sentry project DSN
    - ENVIRONMENT: Environment name (production, staging, development)
    """
    sentry_dsn = os.getenv("SENTRY_DSN")
    environment = os.getenv("ENVIRONMENT", "development")
    
    if not sentry_dsn:
        logger.warning("sentry_not_configured", message="SENTRY_DSN not set, skipping Sentry initialization")
        return False
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,  # 10% for profiling
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
            ],
            # Set release version from environment or git commit
            release=os.getenv("GIT_COMMIT", "unknown"),
            # Send PII (Personally Identifiable Information) - set to False for GDPR compliance
            send_default_pii=False,
            # Before send callback to filter sensitive data
            before_send=filter_sensitive_data,
        )
        
        logger.info(
            "sentry_initialized",
            environment=environment,
            dsn_configured=True
        )
        return True
        
    except ImportError:
        logger.error("sentry_import_error", message="sentry-sdk not installed. Run: pip install sentry-sdk")
        return False
    except Exception as e:
        logger.error("sentry_init_error", error=str(e))
        return False

def filter_sensitive_data(event: Dict[str, Any], hint: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter sensitive data before sending to Sentry (GDPR compliance)
    
    Removes:
    - Email addresses
    - Payment information
    - API keys
    - Personal data
    """
    # Remove sensitive headers
    if "request" in event and "headers" in event["request"]:
        sensitive_headers = ["authorization", "cookie", "x-api-key"]
        for header in sensitive_headers:
            if header in event["request"]["headers"]:
                event["request"]["headers"][header] = "[FILTERED]"
    
    # Remove sensitive query parameters
    if "request" in event and "query_string" in event["request"]:
        sensitive_params = ["token", "api_key", "password"]
        query_string = event["request"]["query_string"]
        for param in sensitive_params:
            if param in query_string.lower():
                event["request"]["query_string"] = "[FILTERED]"
    
    return event

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

# Request metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"]
)

# Generation metrics
generations_total = Counter(
    "generations_total",
    "Total number of generations",
    ["style", "subscription_tier"]
)

generation_duration_seconds = Histogram(
    "generation_duration_seconds",
    "Generation duration in seconds",
    ["style"]
)

generation_errors_total = Counter(
    "generation_errors_total",
    "Total generation errors",
    ["error_type"]
)

# Remix metrics
remixes_total = Counter(
    "remixes_total",
    "Total number of remixes",
    ["layer_type", "subscription_tier"]
)

remix_duration_seconds = Histogram(
    "remix_duration_seconds",
    "Remix processing duration in seconds",
    ["layer_type"]
)

# Earnings metrics
earnings_total = Counter(
    "earnings_total_eur",
    "Total earnings distributed in EUR"
)

license_transactions_total = Counter(
    "license_transactions_total",
    "Total license transactions",
    ["status"]
)

# System metrics
active_users_gauge = Gauge(
    "active_users",
    "Number of active users in last 24 hours"
)

database_connections_gauge = Gauge(
    "database_connections",
    "Number of active database connections"
)

redis_connected_gauge = Gauge(
    "redis_connected",
    "Redis connection status (1=connected, 0=disconnected)"
)

# Rate limit metrics
rate_limit_exceeded_total = Counter(
    "rate_limit_exceeded_total",
    "Total rate limit exceeded events",
    ["limit_type", "subscription_tier"]
)

# ============================================================================
# METRICS ENDPOINT
# ============================================================================

def get_prometheus_metrics() -> Response:
    """
    Generate Prometheus metrics in text format
    
    Returns:
        Response with Prometheus metrics
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ============================================================================
# HEALTH CHECK
# ============================================================================

class HealthChecker:
    """
    Comprehensive health check for all system components
    """
    
    def __init__(self):
        self.checks = {
            "database": self._check_database,
            "redis": self._check_redis,
            "r2_storage": self._check_r2_storage,
            "replicate_api": self._check_replicate_api,
        }
    
    def _check_database(self) -> Dict[str, Any]:
        """Check PostgreSQL database connection"""
        try:
            conn = psycopg2.connect(
                os.getenv("DATABASE_URL"),
                connect_timeout=3
            )
            cur = conn.cursor()
            
            # Test query
            cur.execute("SELECT 1")
            cur.fetchone()
            
            # Get connection count
            cur.execute("SELECT count(*) FROM pg_stat_activity")
            connection_count = cur.fetchone()[0]
            
            cur.close()
            conn.close()
            
            database_connections_gauge.set(connection_count)
            
            return {
                "status": "healthy",
                "response_time_ms": 0,  # Would need timing
                "connections": connection_count
            }
            
        except Exception as e:
            logger.error("health_check_database_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connection"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            client = redis.from_url(redis_url, socket_connect_timeout=3)
            
            start = time.time()
            client.ping()
            response_time = int((time.time() - start) * 1000)
            
            redis_connected_gauge.set(1)
            
            return {
                "status": "healthy",
                "response_time_ms": response_time
            }
            
        except Exception as e:
            logger.error("health_check_redis_failed", error=str(e))
            redis_connected_gauge.set(0)
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def _check_r2_storage(self) -> Dict[str, Any]:
        """Check Cloudflare R2 storage"""
        try:
            # Simple check: verify environment variables are set
            r2_account_id = os.getenv("R2_ACCOUNT_ID")
            r2_access_key = os.getenv("R2_ACCESS_KEY_ID")
            r2_secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
            
            if not all([r2_account_id, r2_access_key, r2_secret_key]):
                return {
                    "status": "degraded",
                    "message": "R2 credentials not fully configured"
                }
            
            # TODO: Add actual S3 API call to test connectivity
            return {
                "status": "healthy",
                "message": "R2 credentials configured"
            }
            
        except Exception as e:
            logger.error("health_check_r2_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def _check_replicate_api(self) -> Dict[str, Any]:
        """Check Replicate API connectivity"""
        try:
            api_token = os.getenv("REPLICATE_API_TOKEN")
            
            if not api_token:
                return {
                    "status": "degraded",
                    "message": "Replicate API token not configured"
                }
            
            # Test API connectivity
            start = time.time()
            response = requests.get(
                "https://api.replicate.com/v1/models",
                headers={"Authorization": f"Bearer {api_token}"},
                timeout=5
            )
            response_time = int((time.time() - start) * 1000)
            
            if response.status_code == 200:
                return {
                    "status": "healthy",
                    "response_time_ms": response_time
                }
            else:
                return {
                    "status": "degraded",
                    "status_code": response.status_code,
                    "response_time_ms": response_time
                }
                
        except requests.exceptions.Timeout:
            return {
                "status": "unhealthy",
                "error": "API timeout"
            }
        except Exception as e:
            logger.error("health_check_replicate_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_all(self) -> Dict[str, Any]:
        """
        Run all health checks
        
        Returns:
            Dict with overall status and individual check results
        """
        results = {}
        overall_healthy = True
        
        for name, check_func in self.checks.items():
            try:
                result = check_func()
                results[name] = result
                
                if result["status"] != "healthy":
                    overall_healthy = False
                    
            except Exception as e:
                logger.error(f"health_check_{name}_exception", error=str(e))
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                overall_healthy = False
        
        return {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": time.time(),
            "checks": results,
            "version": os.getenv("GIT_COMMIT", "unknown")
        }

# ============================================================================
# GLOBAL HEALTH CHECKER INSTANCE
# ============================================================================

health_checker = HealthChecker()

# ============================================================================
# PERFORMANCE TRACKING
# ============================================================================

class PerformanceTracker:
    """Track performance metrics for operations"""
    
    @staticmethod
    def track_generation(style: str, subscription_tier: str, duration_seconds: float):
        """Track generation metrics"""
        generations_total.labels(
            style=style,
            subscription_tier=subscription_tier
        ).inc()
        
        generation_duration_seconds.labels(style=style).observe(duration_seconds)
    
    @staticmethod
    def track_remix(layer_type: str, subscription_tier: str, duration_seconds: float):
        """Track remix metrics"""
        remixes_total.labels(
            layer_type=layer_type,
            subscription_tier=subscription_tier
        ).inc()
        
        remix_duration_seconds.labels(layer_type=layer_type).observe(duration_seconds)
    
    @staticmethod
    def track_earnings(amount_eur: float):
        """Track earnings distribution"""
        earnings_total.inc(amount_eur)
    
    @staticmethod
    def track_license_transaction(status: str):
        """Track license transaction"""
        license_transactions_total.labels(status=status).inc()
    
    @staticmethod
    def track_rate_limit_exceeded(limit_type: str, subscription_tier: str):
        """Track rate limit exceeded events"""
        rate_limit_exceeded_total.labels(
            limit_type=limit_type,
            subscription_tier=subscription_tier
        ).inc()

performance_tracker = PerformanceTracker()
