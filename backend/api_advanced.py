"""
Advanced Features API (Phase 7)

Endpoints for multi-currency, dynamic splits, royalty pools,
blockchain integration, and instant payouts.

Usage:
    from api_advanced import router as advanced_router
    app.include_router(advanced_router)
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
import structlog
import os

logger = structlog.get_logger()

router = APIRouter(prefix="/api/advanced", tags=["advanced"])

# ============================================================================
# MODELS
# ============================================================================

class CurrencyRate(BaseModel):
    """Currency exchange rate"""
    from_currency: str = Field(..., pattern="^[A-Z]{3}$")
    to_currency: str = Field(..., pattern="^[A-Z]{3}$")
    rate: Decimal = Field(..., gt=0)
    source: str = "ECB"

class CurrencyConversion(BaseModel):
    """Currency conversion request"""
    amount: Decimal
    from_currency: str = Field(..., pattern="^[A-Z]{3}$")
    to_currency: str = Field(..., pattern="^[A-Z]{3}$")

class RoyaltySplitConfig(BaseModel):
    """Custom royalty split configuration"""
    generation_id: str
    platform_percentage: Decimal = Field(..., ge=0, le=100)
    parent_percentage: Decimal = Field(..., ge=0, le=100)
    grandparent_percentage: Decimal = Field(..., ge=0, le=100)
    
    @validator('grandparent_percentage')
    def validate_sum(cls, v, values):
        total = values.get('platform_percentage', 0) + values.get('parent_percentage', 0) + v
        if abs(total - 100) > 0.01:
            raise ValueError(f'Percentages must sum to 100, got {total}')
        return v

class RoyaltyPool(BaseModel):
    """Royalty pool for collaborations"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class RoyaltyPoolMember(BaseModel):
    """Member of a royalty pool"""
    user_id: str
    share_percentage: Decimal = Field(..., gt=0, le=100)

class BlockchainTransaction(BaseModel):
    """Blockchain transaction record"""
    transaction_hash: str = Field(..., pattern="^0x[a-fA-F0-9]{64}$")
    blockchain: str = Field(..., pattern="^(ethereum|polygon|base|arbitrum)$")
    transaction_type: str
    from_address: Optional[str] = Field(None, pattern="^0x[a-fA-F0-9]{40}$")
    to_address: Optional[str] = Field(None, pattern="^0x[a-fA-F0-9]{40}$")
    amount_wei: Optional[int] = None

class InstantPayoutConfig(BaseModel):
    """Instant payout configuration"""
    enabled: bool = False
    min_threshold: Decimal = Field(default=10.00, ge=1.00)
    payout_method: str = Field(..., pattern="^(stripe|paypal|crypto|bank_transfer)$")
    payout_destination: str

# ============================================================================
# MULTI-CURRENCY ENDPOINTS
# ============================================================================

@router.post("/currency/rates")
async def add_currency_rate(
    rate: CurrencyRate,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    Add or update currency exchange rate
    
    Args:
        rate: Currency rate data
    
    Returns:
        Created rate with ID
    
    Example:
        POST /api/advanced/currency/rates
        {
            "from_currency": "USD",
            "to_currency": "EUR",
            "rate": 0.92,
            "source": "ECB"
        }
    """
    cur = db.cursor()
    
    try:
        rate_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO currency_rates (
                id, from_currency, to_currency, rate, source
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            rate_id,
            rate.from_currency,
            rate.to_currency,
            rate.rate,
            rate.source
        ))
        
        result = cur.fetchone()
        db.commit()
        
        logger.info(
            "currency_rate_added",
            rate_id=rate_id,
            from_currency=rate.from_currency,
            to_currency=rate.to_currency,
            rate=float(rate.rate)
        )
        
        return {
            "id": result['id'],
            "created_at": result['created_at'].isoformat(),
            **rate.dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error("currency_rate_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.post("/currency/convert")
async def convert_currency(
    conversion: CurrencyConversion,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    Convert amount between currencies
    
    Args:
        conversion: Conversion request
    
    Returns:
        Converted amount with rate used
    
    Example:
        POST /api/advanced/currency/convert
        {
            "amount": 100.00,
            "from_currency": "USD",
            "to_currency": "EUR"
        }
    """
    cur = db.cursor()
    
    try:
        cur.execute("""
            SELECT convert_currency(%s, %s, %s) as converted_amount
        """, (
            conversion.amount,
            conversion.from_currency,
            conversion.to_currency
        ))
        
        result = cur.fetchone()
        
        return {
            "original_amount": float(conversion.amount),
            "from_currency": conversion.from_currency,
            "converted_amount": float(result['converted_amount']),
            "to_currency": conversion.to_currency
        }
        
    except Exception as e:
        logger.error("currency_conversion_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.get("/currency/rates/{from_currency}/{to_currency}")
async def get_currency_rate(
    from_currency: str,
    to_currency: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Get latest exchange rate between two currencies"""
    cur = db.cursor()
    
    try:
        cur.execute("""
            SELECT rate, effective_date, source
            FROM currency_rates
            WHERE from_currency = %s AND to_currency = %s
            ORDER BY effective_date DESC
            LIMIT 1
        """, (from_currency.upper(), to_currency.upper()))
        
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"No rate found for {from_currency} to {to_currency}"
            )
        
        return {
            "from_currency": from_currency.upper(),
            "to_currency": to_currency.upper(),
            "rate": float(result['rate']),
            "effective_date": result['effective_date'].isoformat(),
            "source": result['source']
        }
        
    finally:
        cur.close()

# ============================================================================
# DYNAMIC ROYALTY SPLITS
# ============================================================================

@router.post("/royalty-splits")
async def create_royalty_split(
    config: RoyaltySplitConfig,
    user_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create custom royalty split configuration
    
    Args:
        config: Split configuration
        user_id: User creating the config (must own generation)
    
    Returns:
        Created configuration
    """
    cur = db.cursor()
    
    try:
        # Verify user owns the generation
        cur.execute("""
            SELECT user_id FROM generations WHERE id = %s
        """, (config.generation_id,))
        
        gen = cur.fetchone()
        if not gen:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        if gen['user_id'] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        # Create config
        config_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO royalty_split_configs (
                id, generation_id, platform_percentage,
                parent_percentage, grandparent_percentage, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            config_id,
            config.generation_id,
            config.platform_percentage,
            config.parent_percentage,
            config.grandparent_percentage,
            user_id
        ))
        
        result = cur.fetchone()
        db.commit()
        
        logger.info(
            "royalty_split_created",
            config_id=config_id,
            generation_id=config.generation_id,
            user_id=user_id
        )
        
        return {
            "id": result['id'],
            "created_at": result['created_at'].isoformat(),
            **config.dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error("royalty_split_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.get("/royalty-splits/{generation_id}")
async def get_royalty_split(
    generation_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Get royalty split configuration for a generation"""
    cur = db.cursor()
    
    try:
        cur.execute("""
            SELECT * FROM royalty_split_configs
            WHERE generation_id = %s
        """, (generation_id,))
        
        result = cur.fetchone()
        
        if not result:
            # Return default split
            return {
                "generation_id": generation_id,
                "platform_percentage": 30.00,
                "parent_percentage": 50.00,
                "grandparent_percentage": 20.00,
                "is_default": True
            }
        
        return dict(result)
        
    finally:
        cur.close()

# ============================================================================
# ROYALTY POOLS (COLLABORATIONS)
# ============================================================================

@router.post("/pools")
async def create_royalty_pool(
    pool: RoyaltyPool,
    user_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a royalty pool for collaborative remixes
    
    Args:
        pool: Pool data
        user_id: Creator user ID
    
    Returns:
        Created pool with ID
    """
    cur = db.cursor()
    
    try:
        pool_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO royalty_pools (id, name, description, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at
        """, (pool_id, pool.name, pool.description, user_id))
        
        result = cur.fetchone()
        db.commit()
        
        logger.info("royalty_pool_created", pool_id=pool_id, user_id=user_id)
        
        return {
            "id": result['id'],
            "created_at": result['created_at'].isoformat(),
            **pool.dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error("royalty_pool_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.post("/pools/{pool_id}/members")
async def add_pool_member(
    pool_id: str,
    member: RoyaltyPoolMember,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Add member to royalty pool"""
    cur = db.cursor()
    
    try:
        member_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO royalty_pool_members (id, pool_id, user_id, share_percentage)
            VALUES (%s, %s, %s, %s)
            RETURNING id, joined_at
        """, (member_id, pool_id, member.user_id, member.share_percentage))
        
        result = cur.fetchone()
        db.commit()
        
        return {
            "id": result['id'],
            "joined_at": result['joined_at'].isoformat(),
            **member.dict()
        }
        
    except psycopg2.IntegrityError as e:
        db.rollback()
        if "pool shares cannot exceed" in str(e).lower():
            raise HTTPException(status_code=400, detail="Pool shares would exceed 100%")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error("pool_member_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.get("/pools/{pool_id}")
async def get_pool(
    pool_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Get royalty pool with members"""
    cur = db.cursor()
    
    try:
        # Get pool
        cur.execute("SELECT * FROM royalty_pools WHERE id = %s", (pool_id,))
        pool = cur.fetchone()
        
        if not pool:
            raise HTTPException(status_code=404, detail="Pool not found")
        
        # Get members
        cur.execute("""
            SELECT rpm.*, u.username
            FROM royalty_pool_members rpm
            JOIN users u ON rpm.user_id = u.id
            WHERE rpm.pool_id = %s
        """, (pool_id,))
        
        members = cur.fetchall()
        
        return {
            **dict(pool),
            "members": [dict(m) for m in members]
        }
        
    finally:
        cur.close()

# ============================================================================
# BLOCKCHAIN INTEGRATION
# ============================================================================

@router.post("/blockchain/transactions")
async def record_blockchain_transaction(
    tx: BlockchainTransaction,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Record blockchain transaction"""
    cur = db.cursor()
    
    try:
        tx_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO blockchain_transactions (
                id, transaction_hash, blockchain, transaction_type,
                from_address, to_address, amount_wei
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (
            tx_id,
            tx.transaction_hash,
            tx.blockchain,
            tx.transaction_type,
            tx.from_address,
            tx.to_address,
            tx.amount_wei
        ))
        
        result = cur.fetchone()
        db.commit()
        
        logger.info(
            "blockchain_tx_recorded",
            tx_id=tx_id,
            tx_hash=tx.transaction_hash,
            blockchain=tx.blockchain
        )
        
        return {
            "id": result['id'],
            "created_at": result['created_at'].isoformat(),
            **tx.dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error("blockchain_tx_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.get("/blockchain/transactions/{tx_hash}")
async def get_blockchain_transaction(
    tx_hash: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Get blockchain transaction by hash"""
    cur = db.cursor()
    
    try:
        cur.execute("""
            SELECT * FROM blockchain_transactions
            WHERE transaction_hash = %s
        """, (tx_hash,))
        
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return dict(result)
        
    finally:
        cur.close()

# ============================================================================
# INSTANT PAYOUTS
# ============================================================================

@router.post("/instant-payouts/config")
async def configure_instant_payout(
    config: InstantPayoutConfig,
    user_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Configure instant payout settings"""
    cur = db.cursor()
    
    try:
        cur.execute("""
            INSERT INTO instant_payout_configs (
                user_id, enabled, min_threshold, payout_method, payout_destination
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                enabled = EXCLUDED.enabled,
                min_threshold = EXCLUDED.min_threshold,
                payout_method = EXCLUDED.payout_method,
                payout_destination = EXCLUDED.payout_destination,
                updated_at = NOW()
            RETURNING id, created_at, updated_at
        """, (
            user_id,
            config.enabled,
            config.min_threshold,
            config.payout_method,
            config.payout_destination
        ))
        
        result = cur.fetchone()
        db.commit()
        
        logger.info("instant_payout_configured", user_id=user_id, enabled=config.enabled)
        
        return {
            "id": result['id'],
            "created_at": result['created_at'].isoformat(),
            "updated_at": result['updated_at'].isoformat(),
            **config.dict()
        }
        
    except Exception as e:
        db.rollback()
        logger.error("instant_payout_config_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

@router.get("/instant-payouts/queue")
async def get_payout_queue(
    status: Optional[str] = None,
    db = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get instant payout queue"""
    cur = db.cursor()
    
    try:
        if status:
            cur.execute("""
                SELECT * FROM instant_payout_queue
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT 100
            """, (status,))
        else:
            cur.execute("""
                SELECT * FROM instant_payout_queue
                ORDER BY created_at DESC
                LIMIT 100
            """)
        
        results = cur.fetchall()
        return [dict(r) for r in results]
        
    finally:
        cur.close()

@router.post("/instant-payouts/process/{payout_id}")
async def process_instant_payout(
    payout_id: str,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """Process a pending instant payout"""
    cur = db.cursor()
    
    try:
        # Get payout
        cur.execute("""
            SELECT * FROM instant_payout_queue
            WHERE id = %s AND status = 'pending'
        """, (payout_id,))
        
        payout = cur.fetchone()
        
        if not payout:
            raise HTTPException(status_code=404, detail="Payout not found or already processed")
        
        # Update status to processing
        cur.execute("""
            UPDATE instant_payout_queue
            SET status = 'processing'
            WHERE id = %s
        """, (payout_id,))
        
        db.commit()
        
        # Add background task to process payout
        background_tasks.add_task(
            process_payout_async,
            payout_id,
            payout['user_id'],
            payout['amount'],
            payout['payout_method'],
            payout['payout_destination']
        )
        
        return {
            "payout_id": payout_id,
            "status": "processing",
            "message": "Payout is being processed"
        }
        
    except Exception as e:
        db.rollback()
        logger.error("instant_payout_process_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()

# ============================================================================
# ANALYTICS
# ============================================================================

@router.get("/analytics/royalties")
async def get_royalty_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    currency: str = "EUR",
    db = Depends(get_db)
) -> List[Dict[str, Any]]:
    """Get royalty analytics"""
    cur = db.cursor()
    
    try:
        # Refresh materialized view
        cur.execute("SELECT refresh_royalty_analytics()")
        
        # Query analytics
        query = """
            SELECT * FROM royalty_analytics
            WHERE currency = %s
        """
        params = [currency]
        
        if start_date:
            query += " AND date >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND date <= %s"
            params.append(end_date)
        
        query += " ORDER BY date DESC LIMIT 365"
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        return [dict(r) for r in results]
        
    finally:
        cur.close()

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def process_payout_async(
    payout_id: str,
    user_id: str,
    amount: Decimal,
    method: str,
    destination: str
):
    """Background task to process payout"""
    # TODO: Integrate with payment providers (Stripe, PayPal, etc.)
    logger.info(
        "processing_payout",
        payout_id=payout_id,
        user_id=user_id,
        amount=float(amount),
        method=method
    )
    
    # Simulate processing
    # In production, call actual payment provider APIs

def get_db():
    """Database connection dependency"""
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()
