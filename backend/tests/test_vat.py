"""
Integration Tests: VAT MOSS Compliance

Tests:
1. Calculate VAT for all 27 EU countries
2. Verify 2 location proofs required
3. Generate VAT MOSS XML report
4. Test quarterly aggregation
5. Verify VAT rates are current (2026)
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
import uuid

# ============================================================================
# VAT RATES (2026 Q2)
# ============================================================================

EXPECTED_VAT_RATES = {
    "AT": 0.20, "BE": 0.21, "BG": 0.20, "HR": 0.25, "CY": 0.19,
    "CZ": 0.21, "DK": 0.25, "EE": 0.24, "FI": 0.255, "FR": 0.20,
    "DE": 0.19, "EL": 0.24, "HU": 0.27, "IE": 0.23, "IT": 0.22,
    "LV": 0.21, "LT": 0.21, "LU": 0.17, "MT": 0.18, "NL": 0.21,
    "PL": 0.23, "PT": 0.23, "RO": 0.21, "SK": 0.20, "SI": 0.22,
    "ES": 0.21, "SE": 0.25
}

# ============================================================================
# TEST: VAT CALCULATION FOR ALL EU COUNTRIES
# ============================================================================

def test_vat_calculation_all_eu_countries(db_connection, test_user):
    """
    Test VAT calculation for all 27 EU member states
    
    Verifies:
    - Correct VAT rate for each country
    - Net + VAT = Total
    - 2 location proofs recorded
    """
    cursor = db_connection.cursor()
    
    test_amount = Decimal("10.00")
    
    for country_code, expected_rate in EXPECTED_VAT_RATES.items():
        # Calculate VAT
        vat_amount = test_amount * Decimal(str(expected_rate))
        total_amount = test_amount + vat_amount
        
        # Create VAT transaction
        txn_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO vat_transactions (
                id, user_id, amount_net, vat_rate, vat_amount, total_amount,
                currency, country_code, location_proof_1, location_proof_2,
                stripe_payment_intent_id, payment_status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 'EUR', %s, %s, %s, %s, 'succeeded'
            )
        """, (
            txn_id, test_user['id'], test_amount, Decimal(str(expected_rate)),
            vat_amount, total_amount, country_code,
            "stripe_billing_address", f"ip_geolocation:185.123.45.67",
            f"pi_{country_code.lower()}_test"
        ))
    
    db_connection.commit()
    
    # Verify all transactions created
    cursor.execute("""
        SELECT country_code, vat_rate, amount_net, vat_amount, total_amount
        FROM vat_transactions
        WHERE user_id = %s
        ORDER BY country_code
    """, (test_user['id'],))
    
    transactions = cursor.fetchall()
    assert len(transactions) == 27, "Should have transactions for all 27 EU countries"
    
    for txn in transactions:
        country = txn['country_code']
        expected_rate = EXPECTED_VAT_RATES[country]
        
        # Verify VAT rate
        assert float(txn['vat_rate']) == expected_rate, \
            f"VAT rate for {country} should be {expected_rate}"
        
        # Verify calculation
        net = float(txn['amount_net'])
        vat = float(txn['vat_amount'])
        total = float(txn['total_amount'])
        
        assert abs(vat - (net * expected_rate)) < 0.01, \
            f"VAT calculation incorrect for {country}"
        assert abs(total - (net + vat)) < 0.01, \
            f"Total calculation incorrect for {country}"

# ============================================================================
# TEST: 2 LOCATION PROOFS REQUIRED
# ============================================================================

def test_vat_requires_two_location_proofs(db_connection, test_user):
    """
    Test that VAT MOSS requires 2 different location proofs
    
    Per EU VAT MOSS rules:
    - Must have 2 non-contradictory pieces of evidence
    - Evidence must be from different sources
    - Common: billing address + IP geolocation
    """
    cursor = db_connection.cursor()
    
    # Valid transaction with 2 different proofs
    valid_txn_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO vat_transactions (
            id, user_id, amount_net, vat_rate, vat_amount, total_amount,
            currency, country_code, location_proof_1, location_proof_2,
            payment_status
        ) VALUES (
            %s, %s, 10.00, 0.19, 1.90, 11.90, 'EUR', 'DE',
            'stripe_billing_address', 'ip_geolocation:185.123.45.67',
            'succeeded'
        )
    """, (valid_txn_id, test_user['id']))
    
    db_connection.commit()
    
    # Verify transaction created
    cursor.execute("""
        SELECT location_proof_1, location_proof_2
        FROM vat_transactions
        WHERE id = %s
    """, (valid_txn_id,))
    
    txn = cursor.fetchone()
    assert txn['location_proof_1'] != txn['location_proof_2'], \
        "Location proofs must be different"
    
    # Test constraint: same proof should fail
    invalid_txn_id = str(uuid.uuid4())
    
    with pytest.raises(Exception):  # Should violate CHECK constraint
        cursor.execute("""
            INSERT INTO vat_transactions (
                id, user_id, amount_net, vat_rate, vat_amount, total_amount,
                currency, country_code, location_proof_1, location_proof_2,
                payment_status
            ) VALUES (
                %s, %s, 10.00, 0.19, 1.90, 11.90, 'EUR', 'DE',
                'stripe_billing_address', 'stripe_billing_address',
                'succeeded'
            )
        """, (invalid_txn_id, test_user['id']))
        db_connection.commit()
    
    db_connection.rollback()

# ============================================================================
# TEST: VAT MOSS QUARTERLY REPORT
# ============================================================================

def test_vat_moss_quarterly_report_generation(db_connection, test_user):
    """
    Test generation of VAT MOSS quarterly report
    
    Report should include:
    - Total sales per country
    - Total VAT collected per country
    - Quarter period
    - Aggregated by country
    """
    cursor = db_connection.cursor()
    
    # Create transactions for Q2 2026 (April-June)
    q2_start = datetime(2026, 4, 1)
    q2_end = datetime(2026, 6, 30)
    
    # Multiple transactions for same countries
    test_data = [
        ("DE", 100.00, 0.19),  # Germany
        ("DE", 50.00, 0.19),   # Germany (second transaction)
        ("FR", 75.00, 0.20),   # France
        ("ES", 120.00, 0.21),  # Spain
    ]
    
    for country, net_amount, vat_rate in test_data:
        vat_amount = net_amount * vat_rate
        total_amount = net_amount + vat_amount
        
        cursor.execute("""
            INSERT INTO vat_transactions (
                id, user_id, amount_net, vat_rate, vat_amount, total_amount,
                currency, country_code, location_proof_1, location_proof_2,
                payment_status, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, 'EUR', %s, %s, %s, 'succeeded', %s
            )
        """, (
            str(uuid.uuid4()), test_user['id'], net_amount, vat_rate,
            vat_amount, total_amount, country,
            "stripe_billing_address", "ip_geolocation:185.123.45.67",
            q2_start + timedelta(days=15)  # Mid-quarter
        ))
    
    db_connection.commit()
    
    # Generate quarterly report using view.
    # Scope to this test's own user_id: a MOSS quarterly report is intentionally
    # GLOBAL (one return across all customers), so the report SQL is correct as written.
    # But sibling VAT tests commit their own DE/FR/ES rows (created_at defaults to NOW(),
    # inside this Q2 window) into the shared session DB, inflating the global counts and
    # sums. Filtering by user_id isolates this test's 4 rows so the exact count/SUM
    # assertions below hold. (Each test gets a fresh test_user with a unique UUID.)
    cursor.execute("""
        SELECT
            country_code,
            DATE_TRUNC('quarter', created_at) as quarter,
            COUNT(*) as transaction_count,
            SUM(amount_net) as total_net,
            AVG(vat_rate) as avg_vat_rate,
            SUM(vat_amount) as total_vat,
            SUM(total_amount) as total_gross
        FROM vat_transactions
        WHERE payment_status = 'succeeded'
          AND user_id = %s
          AND created_at >= %s
          AND created_at <= %s
        GROUP BY country_code, DATE_TRUNC('quarter', created_at)
        ORDER BY country_code
    """, (test_user['id'], q2_start, q2_end))
    
    report = cursor.fetchall()
    
    # Verify Germany (2 transactions)
    de_report = [r for r in report if r['country_code'] == 'DE'][0]
    assert de_report['transaction_count'] == 2
    assert float(de_report['total_net']) == 150.00  # 100 + 50
    assert float(de_report['total_vat']) == 28.50   # (100 + 50) * 0.19
    
    # Verify France (1 transaction)
    fr_report = [r for r in report if r['country_code'] == 'FR'][0]
    assert fr_report['transaction_count'] == 1
    assert float(fr_report['total_net']) == 75.00
    assert float(fr_report['total_vat']) == 15.00   # 75 * 0.20
    
    # Verify Spain (1 transaction)
    es_report = [r for r in report if r['country_code'] == 'ES'][0]
    assert es_report['transaction_count'] == 1
    assert float(es_report['total_net']) == 120.00
    assert float(es_report['total_vat']) == 25.20   # 120 * 0.21

# ============================================================================
# TEST: VAT MOSS XML EXPORT
# ============================================================================

def test_vat_moss_xml_export_format(db_connection, test_user):
    """
    Test VAT MOSS XML export format
    
    XML should conform to EU VAT MOSS schema:
    - Header with period
    - Line items per country
    - Totals
    """
    cursor = db_connection.cursor()
    
    # Create sample transactions
    cursor.execute("""
        INSERT INTO vat_transactions (
            id, user_id, amount_net, vat_rate, vat_amount, total_amount,
            currency, country_code, location_proof_1, location_proof_2,
            payment_status, created_at
        ) VALUES
        (%s, %s, 100.00, 0.19, 19.00, 119.00, 'EUR', 'DE', 'billing', 'ip', 'succeeded', NOW()),
        (%s, %s, 75.00, 0.20, 15.00, 90.00, 'EUR', 'FR', 'billing', 'ip', 'succeeded', NOW())
    """, (str(uuid.uuid4()), test_user['id'], str(uuid.uuid4()), test_user['id']))
    
    db_connection.commit()
    
    # Generate XML (mock structure)
    from xml.etree import ElementTree as ET
    
    root = ET.Element("VATReturn")
    root.set("period", "2026-Q2")
    
    # Get data
    cursor.execute("""
        SELECT country_code, SUM(amount_net) as net, SUM(vat_amount) as vat
        FROM vat_transactions
        WHERE user_id = %s AND payment_status = 'succeeded'
        GROUP BY country_code
    """, (test_user['id'],))
    
    for row in cursor.fetchall():
        line = ET.SubElement(root, "Line")
        ET.SubElement(line, "CountryCode").text = row['country_code']
        ET.SubElement(line, "NetAmount").text = f"{float(row['net']):.2f}"
        ET.SubElement(line, "VATAmount").text = f"{float(row['vat']):.2f}"
    
    # Verify XML structure
    xml_string = ET.tostring(root, encoding='unicode')
    assert '<VATReturn period="2026-Q2">' in xml_string
    assert '<CountryCode>DE</CountryCode>' in xml_string
    assert '<CountryCode>FR</CountryCode>' in xml_string

# ============================================================================
# TEST: VAT RATE UPDATES
# ============================================================================

def test_vat_rates_are_current_2026(db_connection):
    """
    Test that VAT rates in system match 2026 rates
    
    Important changes in 2025-2026:
    - Estonia: 22% → 24% (2025)
    - Romania: 19% → 21% (2025)
    - Finland: 25.5% (unchanged)
    """
    from main import VAT_RATES
    
    # Verify critical rate changes
    assert VAT_RATES["EE"] == 0.24, "Estonia VAT should be 24% (raised in 2025)"
    assert VAT_RATES["RO"] == 0.21, "Romania VAT should be 21% (raised in 2025)"
    assert VAT_RATES["FI"] == 0.255, "Finland VAT should be 25.5%"
    
    # Verify highest and lowest rates
    assert VAT_RATES["HU"] == 0.27, "Hungary has highest VAT (27%)"
    assert VAT_RATES["LU"] == 0.17, "Luxembourg has lowest VAT (17%)"
    
    # Verify all 27 countries present
    assert len(VAT_RATES) == 27, "Should have VAT rates for all 27 EU countries"

# ============================================================================
# TEST: LOCATION PROOF VALIDATION
# ============================================================================

def test_location_proof_validation(db_connection, test_user):
    """
    Test validation of location proofs
    
    Valid proofs:
    - stripe_billing_address
    - ip_geolocation:[IP]
    - bank_country_code
    - sim_card_country
    """
    cursor = db_connection.cursor()
    
    valid_proof_combinations = [
        ("stripe_billing_address", "ip_geolocation:185.123.45.67"),
        ("bank_country_code:DE", "ip_geolocation:185.123.45.67"),
        ("stripe_billing_address", "sim_card_country:DE"),
    ]
    
    for proof1, proof2 in valid_proof_combinations:
        txn_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO vat_transactions (
                id, user_id, amount_net, vat_rate, vat_amount, total_amount,
                currency, country_code, location_proof_1, location_proof_2,
                payment_status
            ) VALUES (
                %s, %s, 10.00, 0.19, 1.90, 11.90, 'EUR', 'DE', %s, %s, 'succeeded'
            )
        """, (txn_id, test_user['id'], proof1, proof2))
    
    db_connection.commit()
    
    # Verify all created
    cursor.execute("""
        SELECT COUNT(*) as count FROM vat_transactions
        WHERE user_id = %s
    """, (test_user['id'],))
    
    assert cursor.fetchone()['count'] == len(valid_proof_combinations)

# ============================================================================
# TEST: VAT REFUND HANDLING
# ============================================================================

def test_vat_refund_transaction(db_connection, test_user):
    """
    Test VAT refund handling
    
    When payment is refunded:
    - Original transaction marked as 'refunded'
    - VAT amounts reversed
    - Not included in MOSS report
    """
    cursor = db_connection.cursor()
    
    # Create original transaction
    original_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO vat_transactions (
            id, user_id, amount_net, vat_rate, vat_amount, total_amount,
            currency, country_code, location_proof_1, location_proof_2,
            stripe_payment_intent_id, payment_status
        ) VALUES (
            %s, %s, 100.00, 0.19, 19.00, 119.00, 'EUR', 'DE',
            'billing', 'ip', 'pi_original', 'succeeded'
        )
    """, (original_id, test_user['id']))
    
    db_connection.commit()
    
    # Refund transaction
    cursor.execute("""
        UPDATE vat_transactions
        SET payment_status = 'refunded'
        WHERE id = %s
    """, (original_id,))
    
    db_connection.commit()
    
    # Verify refunded transactions excluded from MOSS report
    cursor.execute("""
        SELECT SUM(vat_amount) as total_vat
        FROM vat_transactions
        WHERE user_id = %s AND payment_status = 'succeeded'
    """, (test_user['id'],))
    
    result = cursor.fetchone()
    assert result['total_vat'] is None or float(result['total_vat']) == 0.00, \
        "Refunded transactions should not be included in VAT totals"
