#!/usr/bin/env python3
"""
Hourly Payout Processor
Runs every hour to process pending payouts to Stripe Connect accounts.

Processes:
1. Find users with pending balance >= €20
2. Initiate Stripe transfer
3. Update payout status
4. Send confirmation email
"""

import psycopg2
import stripe
import os
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

stripe.api_key = STRIPE_SECRET_KEY

MIN_PAYOUT_AMOUNT = 20.00  # €20 minimum


def process_pending_payouts():
    """Process all eligible payouts."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Find users eligible for payout
        cursor.execute("""
            SELECT 
                u.id,
                u.email,
                u.username,
                u.stripe_account_id,
                COALESCE(SUM(t.amount), 0) as pending_balance
            FROM users u
            LEFT JOIN transactions t ON t.user_id = u.id AND t.status = 'completed' AND t.payout_id IS NULL
            WHERE u.stripe_account_id IS NOT NULL
            GROUP BY u.id, u.email, u.username, u.stripe_account_id
            HAVING COALESCE(SUM(t.amount), 0) >= %s
        """, (MIN_PAYOUT_AMOUNT,))
        
        eligible_users = cursor.fetchall()
        
        if not eligible_users:
            print("ℹ️  No users eligible for payout")
            return
        
        print(f"📤 Processing payouts for {len(eligible_users)} users...")
        
        for user_id, email, username, stripe_account_id, pending_balance in eligible_users:
            try:
                # Create Stripe transfer
                transfer = stripe.Transfer.create(
                    amount=int(pending_balance * 100),  # Convert to cents
                    currency="eur",
                    destination=stripe_account_id,
                    description=f"Payout to {username}",
                    metadata={
                        "user_id": user_id,
                        "username": username,
                    }
                )
                
                # Record payout in database
                cursor.execute("""
                    INSERT INTO payouts (user_id, amount, stripe_transfer_id, status)
                    VALUES (%s, %s, %s, 'processing')
                    RETURNING id
                """, (user_id, pending_balance, transfer.id))
                
                payout_id = cursor.fetchone()[0]
                
                # Link transactions to payout
                cursor.execute("""
                    UPDATE transactions
                    SET payout_id = %s
                    WHERE user_id = %s AND status = 'completed' AND payout_id IS NULL
                """, (payout_id, user_id))
                
                # Create withdrawal transaction
                cursor.execute("""
                    INSERT INTO transactions (user_id, type, amount, status, payout_id)
                    VALUES (%s, 'withdrawal', %s, 'completed', %s)
                """, (user_id, -pending_balance, payout_id))
                
                conn.commit()
                
                print(f"   ✅ {username}: €{pending_balance:.2f} → {stripe_account_id}")
                
                # TODO: Send confirmation email
                
            except stripe.error.StripeError as e:
                print(f"   ❌ {username}: Stripe error - {str(e)}")
                conn.rollback()
                
                # Record failed payout
                cursor.execute("""
                    INSERT INTO payouts (user_id, amount, status, error_message)
                    VALUES (%s, %s, 'failed', %s)
                """, (user_id, pending_balance, str(e)))
                conn.commit()
                
            except Exception as e:
                print(f"   ❌ {username}: Error - {str(e)}")
                conn.rollback()
        
        print(f"✅ Processed {len(eligible_users)} payouts")
        
    except Exception as e:
        print(f"❌ Error processing payouts: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_payout_statuses():
    """Update status of pending payouts by checking Stripe."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Get processing payouts
        cursor.execute("""
            SELECT id, stripe_transfer_id
            FROM payouts
            WHERE status = 'processing'
            AND created_at > NOW() - INTERVAL '7 days'
        """)
        
        processing_payouts = cursor.fetchall()
        
        if not processing_payouts:
            return
        
        print(f"🔄 Checking status of {len(processing_payouts)} pending payouts...")
        
        for payout_id, transfer_id in processing_payouts:
            try:
                # Check transfer status in Stripe
                transfer = stripe.Transfer.retrieve(transfer_id)
                
                if transfer.status == "paid":
                    cursor.execute("""
                        UPDATE payouts
                        SET status = 'completed', completed_at = NOW()
                        WHERE id = %s
                    """, (payout_id,))
                    print(f"   ✅ Payout {payout_id}: completed")
                    
                elif transfer.status == "failed":
                    cursor.execute("""
                        UPDATE payouts
                        SET status = 'failed', error_message = %s
                        WHERE id = %s
                    """, (transfer.failure_message, payout_id))
                    print(f"   ❌ Payout {payout_id}: failed")
                
            except stripe.error.StripeError as e:
                print(f"   ⚠️  Payout {payout_id}: Stripe error - {str(e)}")
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Error updating payout statuses: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def main():
    print("=" * 60)
    print(f"PAYOUT PROCESSOR - {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Process new payouts
    process_pending_payouts()
    
    # Update existing payout statuses
    update_payout_statuses()
    
    print("=" * 60)
    print("✅ Payout processor completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
