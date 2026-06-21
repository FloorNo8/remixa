#!/usr/bin/env python3
"""
Payout Processor (FN8-692 batch path)

Run by scripts.cron_runner. Processes PENDING `payout_requests` (created by
api_v2.request_payout, which already debited the append-only `user_ledger` with a
`payout_requested` entry at request time). For each pending request that has a Stripe
Connect account, sends a Stripe Transfer and advances the request status. On failure it
RESTORES the creator's balance with a `payout_failed` ledger credit (append-only).

This replaces the previous version, which queried tables that do not exist in the schema
(`transactions`, `payouts`, `users.stripe_account_id`) and gated on the stale
`users.pending_payout` column — so it could never have run.
"""
import os
from datetime import datetime

import psycopg2

DATABASE_URL = os.getenv("DATABASE_URL")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")


def _stripe():
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def process_pending_payouts():
    """Send Stripe transfers for pending payout_requests (balance already debited at request)."""
    stripe = _stripe()
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT pr.id, pr.user_id, pr.amount, u.stripe_connect_account_id, u.email
            FROM payout_requests pr
            JOIN users u ON u.id = pr.user_id
            WHERE pr.status = 'pending'
              AND u.stripe_connect_account_id IS NOT NULL
            ORDER BY pr.created_at ASC
        """)
        pending = cur.fetchall()
        if not pending:
            print("ℹ️  No pending payouts")
            return

        print(f"📤 Processing {len(pending)} pending payout(s)...")
        for req_id, user_id, amount, connect_acct, email in pending:
            try:
                transfer = stripe.Transfer.create(
                    amount=int(round(float(amount) * 100)),  # euros → cents
                    currency="eur",
                    destination=connect_acct,
                    description=f"Remixa creator payout {req_id}",
                    metadata={"payout_request_id": str(req_id), "user_id": str(user_id)},
                    idempotency_key=f"payout_{req_id}",  # stable per request → no double transfer
                )
                cur.execute(
                    "UPDATE payout_requests SET status = 'processing', stripe_transfer_id = %s WHERE id = %s",
                    (transfer.id, req_id),
                )
                conn.commit()
                print(f"   ✅ {email or user_id}: €{float(amount):.2f} → {connect_acct} ({transfer.id})")
            except stripe.error.StripeError as e:
                conn.rollback()
                # Mark failed AND restore the balance via an append-only credit-back.
                cur.execute(
                    "UPDATE payout_requests SET status = 'failed', error_message = %s WHERE id = %s",
                    (str(e), req_id),
                )
                cur.execute("""
                    INSERT INTO user_ledger (user_id, transaction_type, amount, payout_request_id, description)
                    VALUES (%s, 'payout_failed', %s, %s, 'Payout failed — balance restored')
                """, (user_id, float(amount), req_id))
                conn.commit()
                print(f"   ❌ {email or user_id}: Stripe error — restored €{float(amount):.2f} ({e})")
    except Exception as e:
        conn.rollback()
        print(f"❌ process_pending_payouts error: {e}")
    finally:
        cur.close()
        conn.close()


def update_payout_statuses():
    """Reconcile 'processing' payout_requests against Stripe; credit back on reversal."""
    stripe = _stripe()
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, user_id, amount, stripe_transfer_id
            FROM payout_requests
            WHERE status = 'processing'
              AND stripe_transfer_id IS NOT NULL
              AND created_at > NOW() - INTERVAL '7 days'
        """)
        rows = cur.fetchall()
        if not rows:
            return

        print(f"🔄 Reconciling {len(rows)} processing payout(s)...")
        for req_id, user_id, amount, transfer_id in rows:
            try:
                tr = stripe.Transfer.retrieve(transfer_id)
                reversed_cents = getattr(tr, "amount_reversed", 0) or 0
                if reversed_cents >= int(round(float(amount) * 100)):
                    cur.execute(
                        "UPDATE payout_requests SET status = 'failed', error_message = 'reversed' WHERE id = %s",
                        (req_id,),
                    )
                    cur.execute("""
                        INSERT INTO user_ledger (user_id, transaction_type, amount, payout_request_id, description)
                        VALUES (%s, 'payout_reversed', %s, %s, 'Payout reversed — balance restored')
                    """, (user_id, float(amount), req_id))
                    print(f"   ↩️  Payout {req_id}: reversed → balance restored")
                else:
                    cur.execute(
                        "UPDATE payout_requests SET status = 'completed', completed_at = NOW() WHERE id = %s",
                        (req_id,),
                    )
                    print(f"   ✅ Payout {req_id}: completed")
            except stripe.error.StripeError as e:
                print(f"   ⚠️  Payout {req_id}: Stripe error — {e}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ update_payout_statuses error: {e}")
    finally:
        cur.close()
        conn.close()


def main():
    print("=" * 60)
    print(f"PAYOUT PROCESSOR — {datetime.utcnow().isoformat()}")
    print("=" * 60)
    process_pending_payouts()
    update_payout_statuses()
    print("✅ Payout processor completed")


if __name__ == "__main__":
    main()
