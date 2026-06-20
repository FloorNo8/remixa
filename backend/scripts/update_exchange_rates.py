#!/usr/bin/env python3
"""
Automatic Exchange Rate Updates

Fetches latest exchange rates from European Central Bank (ECB)
and updates the database. Run as a cron job (hourly/daily).

Usage:
    python backend/scripts/update_exchange_rates.py
    
Cron example (daily at 9 AM):
    0 9 * * * cd /app && python backend/scripts/update_exchange_rates.py
"""

import os
import sys
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from decimal import Decimal
import structlog
import xml.etree.ElementTree as ET

logger = structlog.get_logger()

# Supported currencies
SUPPORTED_CURRENCIES = ['USD', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD', 'SEK', 'NOK', 'DKK']
BASE_CURRENCY = 'EUR'

# ECB API endpoint
ECB_API_URL = 'https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml'

def fetch_ecb_rates():
    """
    Fetch latest exchange rates from ECB
    
    Returns:
        dict: Currency rates with EUR as base
    """
    try:
        response = requests.get(ECB_API_URL, timeout=10)
        response.raise_for_status()
        
        # Parse XML
        root = ET.fromstring(response.content)
        
        # ECB XML namespace
        ns = {'gesmes': 'http://www.gesmes.org/xml/2002-08-01',
              'ecb': 'http://www.ecb.int/vocabulary/2002-08-01/eurofxref'}
        
        # Find the Cube with time attribute (latest rates)
        cube_time = root.find('.//ecb:Cube[@time]', ns)
        
        if cube_time is None:
            raise ValueError("Could not find rates in ECB XML")
        
        rates = {}
        effective_date = cube_time.get('time')
        
        # Extract rates
        for cube in cube_time.findall('ecb:Cube', ns):
            currency = cube.get('currency')
            rate = cube.get('rate')
            
            if currency in SUPPORTED_CURRENCIES:
                rates[currency] = Decimal(rate)
        
        logger.info(
            "ecb_rates_fetched",
            effective_date=effective_date,
            currencies=list(rates.keys())
        )
        
        return rates, effective_date
        
    except Exception as e:
        logger.error("ecb_fetch_error", error=str(e))
        raise

def update_database_rates(rates, effective_date):
    """
    Update database with new exchange rates
    
    Args:
        rates: Dict of currency rates
        effective_date: Date string (YYYY-MM-DD)
    """
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    
    cur = conn.cursor()
    
    try:
        updated_count = 0
        
        # EUR to other currencies
        for currency, rate in rates.items():
            cur.execute("""
                INSERT INTO currency_rates (
                    from_currency, to_currency, rate, effective_date, source
                ) VALUES (%s, %s, %s, %s, 'ECB')
                ON CONFLICT (from_currency, to_currency, effective_date) 
                DO UPDATE SET rate = EXCLUDED.rate
            """, (BASE_CURRENCY, currency, rate, effective_date))
            updated_count += 1
            
            # Inverse rate (other currencies to EUR)
            inverse_rate = Decimal('1') / rate
            cur.execute("""
                INSERT INTO currency_rates (
                    from_currency, to_currency, rate, effective_date, source
                ) VALUES (%s, %s, %s, %s, 'ECB')
                ON CONFLICT (from_currency, to_currency, effective_date) 
                DO UPDATE SET rate = EXCLUDED.rate
            """, (currency, BASE_CURRENCY, inverse_rate, effective_date))
            updated_count += 1
        
        # Cross rates (USD to GBP, etc.)
        currencies = list(rates.keys())
        for i, from_curr in enumerate(currencies):
            for to_curr in currencies[i+1:]:
                # Calculate cross rate via EUR
                cross_rate = rates[to_curr] / rates[from_curr]
                
                cur.execute("""
                    INSERT INTO currency_rates (
                        from_currency, to_currency, rate, effective_date, source
                    ) VALUES (%s, %s, %s, %s, 'ECB_CROSS')
                    ON CONFLICT (from_currency, to_currency, effective_date) 
                    DO UPDATE SET rate = EXCLUDED.rate
                """, (from_curr, to_curr, cross_rate, effective_date))
                updated_count += 1
                
                # Inverse cross rate
                inverse_cross = Decimal('1') / cross_rate
                cur.execute("""
                    INSERT INTO currency_rates (
                        from_currency, to_currency, rate, effective_date, source
                    ) VALUES (%s, %s, %s, %s, 'ECB_CROSS')
                    ON CONFLICT (from_currency, to_currency, effective_date) 
                    DO UPDATE SET rate = EXCLUDED.rate
                """, (to_curr, from_curr, inverse_cross, effective_date))
                updated_count += 1
        
        conn.commit()
        
        logger.info(
            "rates_updated",
            count=updated_count,
            effective_date=effective_date
        )
        
        return updated_count
        
    except Exception as e:
        conn.rollback()
        logger.error("database_update_error", error=str(e))
        raise
    finally:
        cur.close()
        conn.close()

def main():
    """Main execution"""
    try:
        logger.info("exchange_rate_update_started")
        
        # Fetch rates from ECB
        rates, effective_date = fetch_ecb_rates()
        
        # Update database
        count = update_database_rates(rates, effective_date)
        
        logger.info(
            "exchange_rate_update_completed",
            rates_updated=count,
            effective_date=effective_date
        )
        
        print(f"✓ Updated {count} exchange rates for {effective_date}")
        return 0
        
    except Exception as e:
        logger.error("exchange_rate_update_failed", error=str(e))
        print(f"✗ Failed to update exchange rates: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
