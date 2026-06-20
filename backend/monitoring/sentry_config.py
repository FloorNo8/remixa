"""
Sentry Configuration for Remixa Money-Correctness Monitoring

This module configures Sentry alerts and custom error tracking for:
1. Constraint violations (conservation, idempotency, C2PA)
2. Ledger drift detection
3. Orphaned snapshots
4. Negative balances
5. Payout failures

Setup:
1. Set SENTRY_DSN environment variable
2. Import and call configure_sentry_alerts() in main.py
3. Use capture_royalty_error() for money-correctness violations

Alert Routing:
- Critical: Constraint violations, negative balances
- High: Ledger drift, orphaned snapshots
- Warning: Payout delays, API errors
"""

import os
from typing import Optional, Dict, Any
from enum import Enum

try:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False
    print("⚠️  sentry-sdk not installed. Run: pip install sentry-sdk")

class AlertSeverity(Enum):
    """Alert severity levels"""
    CRITICAL = "error"      # Immediate action required
    HIGH = "warning"        # Action required within 1 hour
    WARNING = "info"        # Action required within 24 hours
    INFO = "debug"          # Informational only

class RoyaltyErrorType(Enum):
    """Types of royalty-related errors"""
    CONSERVATION_VIOLATION = "conservation_invariant_violated"
    IDEMPOTENCY_VIOLATION = "idempotency_constraint_violated"
    C2PA_BINDING_VIOLATION = "c2pa_binding_violated"
    LEDGER_DRIFT = "ledger_drift_detected"
    ORPHANED_SNAPSHOT = "orphaned_snapshot_detected"
    NEGATIVE_BALANCE = "negative_balance_detected"
    PAYOUT_FAILURE = "payout_processing_failed"
    CONSTRAINT_UNKNOWN = "unknown_constraint_violated"

def configure_sentry_alerts(
    dsn: Optional[str] = None,
    environment: str = "production",
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1
) -> bool:
    """
    Configure Sentry with custom error tracking for money-correctness
    
    Args:
        dsn: Sentry DSN (defaults to SENTRY_DSN env var)
        environment: Environment name (production, staging, development)
        traces_sample_rate: Percentage of transactions to trace (0.0-1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0-1.0)
    
    Returns:
        True if Sentry was configured successfully, False otherwise
    """
    if not SENTRY_AVAILABLE:
        return False
    
    dsn = dsn or os.getenv("SENTRY_DSN")
    if not dsn:
        print("⚠️  SENTRY_DSN not set, skipping Sentry configuration")
        return False
    
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                SqlalchemyIntegration(),
            ],
            before_send=_filter_sensitive_data,
            before_breadcrumb=_filter_sensitive_breadcrumb,
        )
        
        # Set custom tags for money-correctness monitoring
        sentry_sdk.set_tag("service", "remixa-royalty-engine")
        sentry_sdk.set_tag("money_correctness", "enabled")
        
        print(f"✅ Sentry configured for {environment}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to configure Sentry: {e}")
        return False

def _filter_sensitive_data(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter sensitive data before sending to Sentry (GDPR compliance)
    
    Removes:
    - User emails
    - Payment details
    - API keys
    - Personal information
    """
    # Remove sensitive request data
    if 'request' in event:
        if 'headers' in event['request']:
            # Remove authorization headers
            event['request']['headers'] = {
                k: v for k, v in event['request']['headers'].items()
                if k.lower() not in ['authorization', 'cookie', 'x-api-key']
            }
        
        if 'data' in event['request']:
            # Remove sensitive fields
            sensitive_fields = ['email', 'password', 'stripe_token', 'card_number']
            if isinstance(event['request']['data'], dict):
                event['request']['data'] = {
                    k: '***REDACTED***' if k in sensitive_fields else v
                    for k, v in event['request']['data'].items()
                }
    
    # Keep error context for debugging
    return event

def _filter_sensitive_breadcrumb(crumb: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Filter sensitive data from breadcrumbs"""
    if crumb.get('category') == 'query':
        # Redact SQL query parameters that might contain sensitive data
        if 'message' in crumb:
            crumb['message'] = crumb['message'].replace('email', '***')
    return crumb

def capture_royalty_error(
    error_type: RoyaltyErrorType,
    severity: AlertSeverity,
    message: str,
    context: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None
) -> None:
    """
    Capture a royalty-related error in Sentry with proper context
    
    Args:
        error_type: Type of royalty error
        severity: Alert severity level
        message: Human-readable error message
        context: Additional context (user_id, transaction_id, etc.)
        exception: Optional exception object
    
    Example:
        capture_royalty_error(
            error_type=RoyaltyErrorType.CONSERVATION_VIOLATION,
            severity=AlertSeverity.CRITICAL,
            message="Conservation invariant violated: 0.10 != 0.03 + 0.08",
            context={
                "remixer_id": "uuid",
                "generation_id": "uuid",
                "amount": 0.10,
                "platform_fee": 0.03,
                "creator_share": 0.08
            }
        )
    """
    if not SENTRY_AVAILABLE:
        return
    
    # Set custom tags
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("error_type", error_type.value)
        scope.set_tag("money_correctness_violation", "true")
        scope.level = severity.value
        
        # Add context
        if context:
            for key, value in context.items():
                scope.set_context(key, {"value": str(value)})
        
        # Capture error
        if exception:
            sentry_sdk.capture_exception(exception)
        else:
            sentry_sdk.capture_message(message, level=severity.value)

def capture_constraint_violation(
    constraint_name: str,
    error_message: str,
    context: Dict[str, Any]
) -> None:
    """
    Capture a database constraint violation
    
    Args:
        constraint_name: Name of violated constraint
        error_message: Error message from database
        context: Transaction context (IDs, amounts, etc.)
    """
    error_type_map = {
        "check_conservation_invariant": RoyaltyErrorType.CONSERVATION_VIOLATION,
        "unique_remix_payment": RoyaltyErrorType.IDEMPOTENCY_VIOLATION,
        "check_c2pa_parent_consistency": RoyaltyErrorType.C2PA_BINDING_VIOLATION,
    }
    
    error_type = error_type_map.get(
        constraint_name,
        RoyaltyErrorType.CONSTRAINT_UNKNOWN
    )
    
    capture_royalty_error(
        error_type=error_type,
        severity=AlertSeverity.CRITICAL,
        message=f"Constraint violation: {constraint_name}",
        context={
            "constraint_name": constraint_name,
            "error_message": error_message,
            **context
        }
    )

def capture_ledger_drift(
    user_id: str,
    username: str,
    total_earned: float,
    ledger_balance: float,
    drift: float
) -> None:
    """
    Capture ledger drift detection
    
    Args:
        user_id: User UUID
        username: Username for reference
        total_earned: Value from users.total_earned
        ledger_balance: Sum from user_ledger
        drift: Absolute difference
    """
    capture_royalty_error(
        error_type=RoyaltyErrorType.LEDGER_DRIFT,
        severity=AlertSeverity.HIGH,
        message=f"Ledger drift detected for user {username}: €{drift:.2f}",
        context={
            "user_id": user_id,
            "username": username,
            "total_earned": total_earned,
            "ledger_balance": ledger_balance,
            "drift": drift
        }
    )

def capture_orphaned_snapshot(
    transaction_id: str,
    generation_id: str,
    snapshot_type: str
) -> None:
    """
    Capture orphaned snapshot detection
    
    Args:
        transaction_id: License transaction UUID
        generation_id: Generation UUID
        snapshot_type: 'parent' or 'grandparent'
    """
    capture_royalty_error(
        error_type=RoyaltyErrorType.ORPHANED_SNAPSHOT,
        severity=AlertSeverity.HIGH,
        message=f"Orphaned {snapshot_type} snapshot detected",
        context={
            "transaction_id": transaction_id,
            "generation_id": generation_id,
            "snapshot_type": snapshot_type
        }
    )

def capture_negative_balance(
    user_id: str,
    username: str,
    balance: float
) -> None:
    """
    Capture negative balance detection
    
    Args:
        user_id: User UUID
        username: Username for reference
        balance: Negative balance amount
    """
    capture_royalty_error(
        error_type=RoyaltyErrorType.NEGATIVE_BALANCE,
        severity=AlertSeverity.CRITICAL,
        message=f"Negative balance detected for user {username}: €{balance:.2f}",
        context={
            "user_id": user_id,
            "username": username,
            "balance": balance
        }
    )

def capture_payout_failure(
    payout_id: str,
    user_id: str,
    amount: float,
    error_message: str
) -> None:
    """
    Capture payout processing failure
    
    Args:
        payout_id: Payout UUID
        user_id: User UUID
        amount: Payout amount
        error_message: Error from Stripe or internal system
    """
    capture_royalty_error(
        error_type=RoyaltyErrorType.PAYOUT_FAILURE,
        severity=AlertSeverity.HIGH,
        message=f"Payout failed: €{amount:.2f}",
        context={
            "payout_id": payout_id,
            "user_id": user_id,
            "amount": amount,
            "error_message": error_message
        }
    )

# ============================================================================
# ALERT RULES (Configure in Sentry UI)
# ============================================================================
"""
Recommended Sentry alert rules:

1. Conservation Invariant Violations
   - Condition: error_type = "conservation_invariant_violated"
   - Frequency: Immediately
   - Notification: Email + Slack
   - Severity: Critical

2. Idempotency Violations
   - Condition: error_type = "idempotency_constraint_violated"
   - Frequency: Immediately
   - Notification: Email + Slack
   - Severity: Critical

3. C2PA Binding Violations
   - Condition: error_type = "c2pa_binding_violated"
   - Frequency: Immediately
   - Notification: Email + Slack
   - Severity: Critical

4. Ledger Drift
   - Condition: error_type = "ledger_drift_detected"
   - Frequency: After 5 occurrences in 1 hour
   - Notification: Email
   - Severity: High

5. Orphaned Snapshots
   - Condition: error_type = "orphaned_snapshot_detected"
   - Frequency: After 10 occurrences in 1 hour
   - Notification: Email
   - Severity: High

6. Negative Balances
   - Condition: error_type = "negative_balance_detected"
   - Frequency: Immediately
   - Notification: Email + Slack
   - Severity: Critical

7. Payout Failures
   - Condition: error_type = "payout_processing_failed"
   - Frequency: After 3 occurrences in 1 hour
   - Notification: Email
   - Severity: High
"""
