"""
EU TikTok Sound Lab v2 - Stripe Integration
Module 4: Balance top-ups, payouts, webhook handling
"""

import stripe
import os
from fastapi import HTTPException, Request, APIRouter, Depends
from typing import Dict
from clerk_auth import get_current_user
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ============================================================================
# BALANCE TOP-UP
# ============================================================================

async def create_topup_session(user_id: str, amount_eur: float = 10.0) -> Dict:
    """
    Create Stripe Checkout session for balance top-up
    
    Args:
        user_id: User UUID
        amount_eur: Amount to add (default €10)
    
    Returns:
        Checkout session URL
    """
    
    if amount_eur < 5 or amount_eur > 100:
        raise HTTPException(
            status_code=400,
            detail="Top-up amount must be between €5 and €100"
        )
    
    # Get user email for Stripe
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT email, stripe_customer_id FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create or retrieve Stripe customer
    if user['stripe_customer_id']:
        customer_id = user['stripe_customer_id']
    else:
        customer = stripe.Customer.create(
            email=user['email'],
            metadata={"user_id": user_id}
        )
        customer_id = customer.id
        
        # Update user record
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET stripe_customer_id = %s WHERE id = %s",
            (customer_id, user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    
    # Create Checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {
                    'name': f'Balance Top-up (€{amount_eur:.2f})',
                    'description': 'Add credits for remixing tracks'
                },
                'unit_amount': int(amount_eur * 100)  # Convert to cents
            },
            'quantity': 1
        }],
        mode='payment',
        success_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL')}/dashboard?topup=success",
        cancel_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL')}/dashboard?topup=cancelled",
        metadata={
            'user_id': user_id,
            'type': 'balance_topup',
            'amount_eur': str(amount_eur)
        }
    )
    
    return {
        'session_id': session.id,
        'url': session.url
    }

# ============================================================================
# STRIPE CONNECT (for payouts)
# ============================================================================

async def create_connect_account(user_id: str) -> Dict:
    """
    Create Stripe Connect account for receiving payouts
    
    Returns:
        Onboarding link
    """
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT email, stripe_connect_account_id FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create Connect account if doesn't exist
    if user['stripe_connect_account_id']:
        account_id = user['stripe_connect_account_id']
    else:
        account = stripe.Account.create(
            type='express',
            email=user['email'],
            capabilities={
                'transfers': {'requested': True}
            },
            metadata={'user_id': user_id}
        )
        account_id = account.id
        
        # Update user record
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET stripe_connect_account_id = %s WHERE id = %s",
            (account_id, user_id)
        )
        conn.commit()
        cur.close()
        conn.close()
    
    # Create account link for onboarding
    account_link = stripe.AccountLink.create(
        account=account_id,
        refresh_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL')}/earnings",
        return_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL')}/earnings?connected=true",
        type='account_onboarding'
    )
    
    return {
        'account_id': account_id,
        'onboarding_url': account_link.url
    }

async def process_payout(payout_request_id: str) -> Dict:
    """
    Process payout via Stripe Connect transfer
    Called by cron job or webhook
    """
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    # Get payout request
    cur.execute("""
        SELECT pr.id, pr.user_id, pr.amount, u.stripe_connect_account_id
        FROM payout_requests pr
        JOIN users u ON pr.user_id = u.id
        WHERE pr.id = %s AND pr.status = 'pending'
    """, (payout_request_id,))
    
    payout = cur.fetchone()
    
    if not payout:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Payout request not found or already processed")
    
    if not payout['stripe_connect_account_id']:
        # Update status to failed
        cur.execute("""
            UPDATE payout_requests 
            SET status = 'failed', error_message = 'No Stripe Connect account'
            WHERE id = %s
        """, (payout_request_id,))
        conn.commit()
        cur.close()
        conn.close()
        raise HTTPException(status_code=400, detail="User has no Stripe Connect account")
    
    try:
        # Create transfer
        transfer = stripe.Transfer.create(
            amount=int(payout['amount'] * 100),  # Convert to cents
            currency='eur',
            destination=payout['stripe_connect_account_id'],
            metadata={
                'payout_request_id': payout_request_id,
                'user_id': str(payout['user_id'])
            }
        )
        
        # Update payout request
        cur.execute("""
            UPDATE payout_requests 
            SET status = 'completed', 
                stripe_transfer_id = %s,
                completed_at = NOW()
            WHERE id = %s
        """, (transfer.id, payout_request_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        return {
            'status': 'completed',
            'transfer_id': transfer.id,
            'amount': payout['amount']
        }
        
    except stripe.error.StripeError as e:
        # Update status to failed
        cur.execute("""
            UPDATE payout_requests 
            SET status = 'failed', error_message = %s
            WHERE id = %s
        """, (str(e), payout_request_id))
        conn.commit()
        cur.close()
        conn.close()
        
        raise HTTPException(status_code=500, detail=f"Stripe error: {str(e)}")

# ============================================================================
# WEBHOOK HANDLER
# ============================================================================

async def handle_stripe_webhook(request: Request) -> Dict:
    """
    Handle Stripe webhooks
    
    Events:
    - checkout.session.completed: Add balance after top-up
    - payment_intent.succeeded: Confirm remix payment
    - transfer.created: Log payout
    """
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    # Handle event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        if session['metadata'].get('type') == 'balance_topup':
            user_id = session['metadata']['user_id']
            amount_eur = float(session['metadata']['amount_eur'])
            
            # Add to user balance
            cur.execute("""
                INSERT INTO user_balances (user_id, balance)
                VALUES (%s, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET balance = user_balances.balance + %s, updated_at = NOW()
            """, (user_id, amount_eur, amount_eur))
            
            conn.commit()
            print(f"[WEBHOOK] Added €{amount_eur} to user {user_id} balance")
    
    elif event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        
        # Log successful payment (if it's a remix payment)
        if payment_intent['metadata'].get('type') == 'remix':
            print(f"[WEBHOOK] Remix payment succeeded: {payment_intent['id']}")
    elif event['type'] == 'transfer.created':
        transfer = event['data']['object']
        
        # Log payout transfer
        print(f"[WEBHOOK] Payout transfer created: {transfer['id']}")
        
    elif event['type'] in ('payout.failed', 'payout.canceled', 'transfer.failed'):
        stripe_obj = event['data']['object']
        transaction_id = stripe_obj['id']
        error_msg = stripe_obj.get('failure_message') or "Stripe transfer/payout failed"
        
        # Find corresponding queue item
        cur.execute("""
            SELECT user_id, amount FROM instant_payout_queue
            WHERE transaction_id = %s AND status = 'processing'
        """, (transaction_id,))
        row = cur.fetchone()
        
        if row:
            user_id = row['user_id']
            amount = row['amount']
            
            # Update status in queue
            cur.execute("""
                UPDATE instant_payout_queue
                SET status = 'failed', error_message = %s, processed_at = NOW()
                WHERE transaction_id = %s
            """, (error_msg, transaction_id))
            
            # Insert reversal entry in user_ledger
            cur.execute("""
                INSERT INTO user_ledger (user_id, transaction_type, amount, description)
                VALUES (%s, 'payout_failed', %s, %s)
            """, (user_id, amount, f"Reversal of failed payout {transaction_id}: {error_msg}"))
            
            # Refresh materialized view
            try:
                cur.execute("SELECT refresh_user_balances()")
            except Exception as e:
                print(f"[WEBHOOK] Warning: Failed to refresh balances MV: {e}")
                
            conn.commit()
            print(f"[WEBHOOK] Reversed failed payout {transaction_id} for user {user_id}")
    
    cur.close()
    conn.close()
    
    return {'status': 'success'}

# ============================================================================
# VAT MOSS INTEGRATION (for license fees)
# ============================================================================

async def log_license_fee_to_vat_moss(
    transaction_id: str,
    remixer_id: str,
    amount_eur: float,
    country_code: str
):
    """
    Log license fee transaction to VAT MOSS system
    Digital service export (B2C)
    """
    
    conn = psycopg2.connect(os.getenv("DATABASE_URL"))
    cur = conn.cursor()
    
    # Get VAT rate for country
    vat_rates = {
        'DK': 0.25, 'DE': 0.19, 'FR': 0.20, 'RO': 0.19, 'PL': 0.23,
        'ES': 0.21, 'IT': 0.22, 'NL': 0.21, 'BE': 0.21, 'SE': 0.25
    }
    
    vat_rate = vat_rates.get(country_code, 0.20)  # Default 20%
    vat_amount = amount_eur * vat_rate
    total_amount = amount_eur + vat_amount
    
    # Insert VAT transaction
    cur.execute("""
        INSERT INTO vat_transactions (
            user_id, amount_net, vat_rate, vat_amount, total_amount,
            country_code, location_proof_1, location_proof_2,
            payment_status
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, 'succeeded'
        )
    """, (
        remixer_id,
        amount_eur,
        vat_rate,
        vat_amount,
        total_amount,
        country_code,
        'stripe_billing_address',
        f'license_transaction:{transaction_id}'
    ))
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"[VAT MOSS] Logged license fee: €{amount_eur} + €{vat_amount} VAT ({country_code})")


# ============================================================================
# API ROUTER & ENDPOINTS
# ============================================================================

router = APIRouter(prefix="/api/stripe", tags=["stripe"])

@router.post("/topup")
async def topup(amount_eur: float = 10.0, current_user: dict = Depends(get_current_user)):
    """Create a Stripe Checkout session for balance top-up"""
    return await create_topup_session(current_user["id"], amount_eur)

@router.post("/connect")
async def connect(current_user: dict = Depends(get_current_user)):
    """Create a Stripe Connect Express account for payouts"""
    return await create_connect_account(current_user["id"])

@router.post("/webhook")
async def webhook(request: Request):
    """Stripe webhook handler"""
    return await handle_stripe_webhook(request)
