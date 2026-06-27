"""
Unit Tests for Sentry Alert Configuration.
Covers monitoring/sentry_config.py functions.
"""

import pytest
from unittest.mock import MagicMock, patch
from monitoring.sentry_config import (
    configure_sentry_alerts,
    capture_royalty_error,
    capture_constraint_violation,
    capture_ledger_drift,
    capture_orphaned_snapshot,
    capture_negative_balance,
    capture_payout_failure,
    RoyaltyErrorType,
    AlertSeverity,
    _filter_sensitive_data,
    _filter_sensitive_breadcrumb,
    SENTRY_AVAILABLE
)

@patch("monitoring.sentry_config.sentry_sdk")
def test_configure_sentry_success(mock_sentry):
    """Test successful Sentry initialization."""
    with patch("monitoring.sentry_config.SENTRY_AVAILABLE", True):
        res = configure_sentry_alerts(
            dsn="https://public@sentry.example.com/1",
            environment="test",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.5
        )
        assert res is True
        mock_sentry.init.assert_called_once()
        mock_sentry.set_tag.assert_any_call("service", "remixa-royalty-engine")
        mock_sentry.set_tag.assert_any_call("money_correctness", "enabled")

def test_configure_sentry_missing_dsn():
    """Test skipped initialization when no DSN is provided."""
    with patch("monitoring.sentry_config.SENTRY_AVAILABLE", True), \
         patch("os.getenv", return_value=None):
        res = configure_sentry_alerts(dsn=None)
        assert res is False

@patch("monitoring.sentry_config.sentry_sdk")
def test_configure_sentry_failure(mock_sentry):
    """Test graceful handling of Sentry initialization errors."""
    mock_sentry.init.side_effect = Exception("Sentry crash")
    with patch("monitoring.sentry_config.SENTRY_AVAILABLE", True):
        res = configure_sentry_alerts(dsn="https://public@sentry.example.com/1")
        assert res is False

@patch("monitoring.sentry_config.sentry_sdk")
def test_capture_royalty_error_without_exception(mock_sentry):
    """Test capturing royalty error message without an exception object."""
    mock_scope = MagicMock()
    mock_sentry.push_scope.return_value.__enter__.return_value = mock_scope

    with patch("monitoring.sentry_config.SENTRY_AVAILABLE", True):
        capture_royalty_error(
            error_type=RoyaltyErrorType.CONSERVATION_VIOLATION,
            severity=AlertSeverity.CRITICAL,
            message="Sum mismatch",
            context={"user_id": "u1", "val": 100}
        )

        mock_sentry.push_scope.assert_called_once()
        mock_scope.set_tag.assert_any_call("error_type", "conservation_invariant_violated")
        mock_scope.set_tag.assert_any_call("money_correctness_violation", "true")
        assert mock_scope.level == "error"
        mock_scope.set_context.assert_any_call("user_id", {"value": "u1"})
        mock_scope.set_context.assert_any_call("val", {"value": "100"})
        mock_sentry.capture_message.assert_called_once_with("Sum mismatch", level="error")

@patch("monitoring.sentry_config.sentry_sdk")
def test_capture_royalty_error_with_exception(mock_sentry):
    """Test capturing royalty error with exception object."""
    mock_scope = MagicMock()
    mock_sentry.push_scope.return_value.__enter__.return_value = mock_scope
    ex = ValueError("drift")

    with patch("monitoring.sentry_config.SENTRY_AVAILABLE", True):
        capture_royalty_error(
            error_type=RoyaltyErrorType.LEDGER_DRIFT,
            severity=AlertSeverity.HIGH,
            message="Drift error",
            exception=ex
        )
        mock_sentry.capture_exception.assert_called_once_with(ex)

@patch("monitoring.sentry_config.capture_royalty_error")
def test_helpers(mock_capture):
    """Test convenience wrapper methods call correct capture parameters."""
    # test capture_constraint_violation
    capture_constraint_violation(
        constraint_name="check_conservation_invariant",
        error_message="Check constraint failed",
        context={"some_id": "abc"}
    )
    mock_capture.assert_called_with(
        error_type=RoyaltyErrorType.CONSERVATION_VIOLATION,
        severity=AlertSeverity.CRITICAL,
        message="Constraint violation: check_conservation_invariant",
        context={
            "constraint_name": "check_conservation_invariant",
            "error_message": "Check constraint failed",
            "some_id": "abc"
        }
    )

    # test capture_ledger_drift
    capture_ledger_drift(
        user_id="u1", username="bob", total_earned=10.0, ledger_balance=8.5, drift=1.5
    )
    mock_capture.assert_any_call(
        error_type=RoyaltyErrorType.LEDGER_DRIFT,
        severity=AlertSeverity.HIGH,
        message="Ledger drift detected for user bob: €1.50",
        context={
            "user_id": "u1",
            "username": "bob",
            "total_earned": 10.0,
            "ledger_balance": 8.5,
            "drift": 1.5
        }
    )

    # test capture_orphaned_snapshot
    capture_orphaned_snapshot(transaction_id="t1", generation_id="g1", snapshot_type="parent")
    mock_capture.assert_any_call(
        error_type=RoyaltyErrorType.ORPHANED_SNAPSHOT,
        severity=AlertSeverity.HIGH,
        message="Orphaned parent snapshot detected",
        context={
            "transaction_id": "t1",
            "generation_id": "g1",
            "snapshot_type": "parent"
        }
    )

    # test capture_negative_balance
    capture_negative_balance(user_id="u2", username="alice", balance=-50.0)
    mock_capture.assert_any_call(
        error_type=RoyaltyErrorType.NEGATIVE_BALANCE,
        severity=AlertSeverity.CRITICAL,
        message="Negative balance detected for user alice: €-50.00",
        context={
            "user_id": "u2",
            "username": "alice",
            "balance": -50.0
        }
    )

    # test capture_payout_failure
    capture_payout_failure(payout_id="p1", user_id="u3", amount=250.0, error_message="Stripe decl")
    mock_capture.assert_any_call(
        error_type=RoyaltyErrorType.PAYOUT_FAILURE,
        severity=AlertSeverity.HIGH,
        message="Payout failed: €250.00",
        context={
            "payout_id": "p1",
            "user_id": "u3",
            "amount": 250.0,
            "error_message": "Stripe decl"
        }
    )

def test_sentry_not_available_noop():
    """Verify functions exit early as no-ops if sentry is not available."""
    with patch("monitoring.sentry_config.SENTRY_AVAILABLE", False):
        res = configure_sentry_alerts(dsn="https://public@sentry.example.com/1")
        assert res is False
        # capture_royalty_error should return None early
        assert capture_royalty_error(RoyaltyErrorType.NEGATIVE_BALANCE, AlertSeverity.INFO, "msg") is None

def test_data_filter_gdpr():
    """Verify GDPR data filters mask sensitive fields."""
    event = {
        "request": {
            "headers": {
                "Authorization": "Bearer 123",
                "Cookie": "session=xyz",
                "Accept": "application/json"
            },
            "data": {
                "email": "test@test.com",
                "password": "my_password",
                "stripe_token": "tok_123",
                "card_number": "4111...",
                "prompt": "happy vibes"
            }
        }
    }
    filtered = _filter_sensitive_data(event, {})
    headers = filtered["request"]["headers"]
    assert "Authorization" not in headers
    assert "Cookie" not in headers
    assert headers["Accept"] == "application/json"

    data = filtered["request"]["data"]
    assert data["email"] == "***REDACTED***"
    assert data["password"] == "***REDACTED***"
    assert data["stripe_token"] == "***REDACTED***"
    assert data["card_number"] == "***REDACTED***"
    assert data["prompt"] == "happy vibes"

def test_breadcrumb_filter():
    """Verify query breadcrumbs mask emails."""
    crumb = {"category": "query", "message": "SELECT * FROM users WHERE email = 'bob@bob.com'"}
    filtered = _filter_sensitive_breadcrumb(crumb, {})
    assert filtered["message"] == "SELECT * FROM users WHERE *** = 'bob@bob.com'"
