"""
Lightning Network Integration for Instant Payouts

Enables instant Bitcoin payments via Lightning Network for near-zero fees.
Integrates with LND (Lightning Network Daemon) or other Lightning implementations.

Usage:
    from lightning_payouts import LightningPayoutService
    
    service = LightningPayoutService()
    invoice = await service.create_invoice(amount_sats=10000, user_id="user_123")
    payment = await service.pay_invoice(invoice, amount_sats=10000)
"""

import os
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from decimal import Decimal
import structlog
import base64
import hashlib

logger = structlog.get_logger()

# Lightning Network configuration
LND_HOST = os.getenv('LND_HOST', 'localhost:10009')
LND_MACAROON_PATH = os.getenv('LND_MACAROON_PATH', '/root/.lnd/data/chain/bitcoin/mainnet/admin.macaroon')
LND_TLS_CERT_PATH = os.getenv('LND_TLS_CERT_PATH', '/root/.lnd/tls.cert')

# Conversion rates (updated by exchange rate service)
SATS_PER_EUR = 100000  # Example: 1 EUR = 100,000 sats (updated dynamically)

class LightningPayoutService:
    """
    Lightning Network payout service
    """
    
    def __init__(self):
        """Initialize Lightning service"""
        self.lnd_host = LND_HOST
        self.macaroon = self._load_macaroon()
        self.headers = {
            'Grpc-Metadata-macaroon': self.macaroon
        }
    
    def _load_macaroon(self) -> str:
        """Load LND macaroon for authentication"""
        try:
            with open(LND_MACAROON_PATH, 'rb') as f:
                macaroon_bytes = f.read()
                return base64.b64encode(macaroon_bytes).decode('ascii')
        except FileNotFoundError:
            logger.warning("LND macaroon not found, using mock mode")
            return "mock_macaroon"
    
    async def create_invoice(
        self,
        amount_sats: int,
        user_id: str,
        memo: str = "Remixa royalty payout"
    ) -> Dict[str, Any]:
        """
        Create Lightning invoice for receiving payment
        
        Args:
            amount_sats: Amount in satoshis
            user_id: User ID for tracking
            memo: Invoice memo/description
        
        Returns:
            Invoice details with payment request
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "value": str(amount_sats),
                    "memo": memo,
                    "expiry": "3600"  # 1 hour
                }
                
                async with session.post(
                    f"https://{self.lnd_host}/v1/invoices",
                    json=payload,
                    headers=self.headers,
                    ssl=False  # Use TLS cert in production
                ) as response:
                    result = await response.json()
                    
                    logger.info(
                        "lightning_invoice_created",
                        user_id=user_id,
                        amount_sats=amount_sats,
                        payment_request=result.get('payment_request', '')[:50]
                    )
                    
                    return {
                        "payment_request": result.get('payment_request'),
                        "payment_hash": result.get('r_hash'),
                        "amount_sats": amount_sats,
                        "expires_at": result.get('expiry')
                    }
                    
        except Exception as e:
            logger.error("lightning_invoice_error", error=str(e))
            raise
    
    async def pay_invoice(
        self,
        payment_request: str,
        amount_sats: Optional[int] = None,
        timeout_seconds: int = 60
    ) -> Dict[str, Any]:
        """
        Pay Lightning invoice
        
        Args:
            payment_request: BOLT11 payment request
            amount_sats: Amount in satoshis (for zero-amount invoices)
            timeout_seconds: Payment timeout
        
        Returns:
            Payment result with preimage
        """
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "payment_request": payment_request,
                    "timeout_seconds": timeout_seconds
                }
                
                if amount_sats:
                    payload["amt"] = str(amount_sats)
                
                async with session.post(
                    f"https://{self.lnd_host}/v1/channels/transactions",
                    json=payload,
                    headers=self.headers,
                    ssl=False
                ) as response:
                    result = await response.json()
                    
                    if result.get('payment_error'):
                        raise Exception(f"Payment failed: {result['payment_error']}")
                    
                    logger.info(
                        "lightning_payment_sent",
                        payment_hash=result.get('payment_hash'),
                        amount_sats=amount_sats
                    )
                    
                    return {
                        "payment_hash": result.get('payment_hash'),
                        "payment_preimage": result.get('payment_preimage'),
                        "payment_route": result.get('payment_route'),
                        "fee_sats": result.get('fee_sat', 0)
                    }
                    
        except Exception as e:
            logger.error("lightning_payment_error", error=str(e))
            raise
    
    async def check_invoice_status(self, payment_hash: str) -> Dict[str, Any]:
        """
        Check invoice payment status
        
        Args:
            payment_hash: Invoice payment hash
        
        Returns:
            Invoice status
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://{self.lnd_host}/v1/invoice/{payment_hash}",
                    headers=self.headers,
                    ssl=False
                ) as response:
                    result = await response.json()
                    
                    return {
                        "settled": result.get('settled', False),
                        "amount_paid_sats": int(result.get('amt_paid_sat', 0)),
                        "settle_date": result.get('settle_date'),
                        "payment_request": result.get('payment_request')
                    }
                    
        except Exception as e:
            logger.error("lightning_status_error", error=str(e))
            raise
    
    def convert_eur_to_sats(self, amount_eur: Decimal) -> int:
        """Convert EUR to satoshis"""
        return int(amount_eur * SATS_PER_EUR)
    
    def convert_sats_to_eur(self, amount_sats: int) -> Decimal:
        """Convert satoshis to EUR"""
        return Decimal(amount_sats) / Decimal(SATS_PER_EUR)

# ============================================================================
# LIGHTNING ADDRESS SUPPORT
# ============================================================================

class LightningAddressService:
    """
    Lightning Address (user@domain.com) support
    Implements LNURL-pay protocol
    """
    
    @staticmethod
    async def resolve_lightning_address(address: str) -> Dict[str, Any]:
        """
        Resolve Lightning Address to LNURL endpoint
        
        Args:
            address: Lightning address (e.g., user@remixa.com)
        
        Returns:
            LNURL metadata
        """
        try:
            username, domain = address.split('@')
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://{domain}/.well-known/lnurlp/{username}"
                ) as response:
                    result = await response.json()
                    
                    logger.info(
                        "lightning_address_resolved",
                        address=address,
                        callback=result.get('callback')
                    )
                    
                    return result
                    
        except Exception as e:
            logger.error("lightning_address_error", error=str(e))
            raise
    
    @staticmethod
    async def pay_lightning_address(
        address: str,
        amount_sats: int,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Pay to Lightning Address
        
        Args:
            address: Lightning address
            amount_sats: Amount in satoshis
            comment: Optional payment comment
        
        Returns:
            Payment invoice
        """
        try:
            # Resolve address
            metadata = await LightningAddressService.resolve_lightning_address(address)
            
            # Get invoice from callback
            callback_url = metadata['callback']
            params = {
                'amount': amount_sats * 1000  # Convert to millisats
            }
            
            if comment:
                params['comment'] = comment
            
            async with aiohttp.ClientSession() as session:
                async with session.get(callback_url, params=params) as response:
                    result = await response.json()
                    
                    return {
                        "payment_request": result.get('pr'),
                        "success_action": result.get('successAction')
                    }
                    
        except Exception as e:
            logger.error("lightning_address_payment_error", error=str(e))
            raise

# ============================================================================
# DATABASE INTEGRATION
# ============================================================================

async def process_lightning_payout(
    user_id: str,
    amount_eur: Decimal,
    lightning_address: str
) -> Dict[str, Any]:
    """
    Process payout via Lightning Network
    
    Args:
        user_id: User ID
        amount_eur: Amount in EUR
        lightning_address: User's Lightning address
    
    Returns:
        Payout result
    """
    service = LightningPayoutService()
    ln_address = LightningAddressService()
    
    try:
        # Convert EUR to sats
        amount_sats = service.convert_eur_to_sats(amount_eur)
        
        # Pay to Lightning address
        invoice_data = await ln_address.pay_lightning_address(
            address=lightning_address,
            amount_sats=amount_sats,
            comment=f"Remixa royalty payout for user {user_id}"
        )
        
        # Pay invoice
        payment_result = await service.pay_invoice(
            payment_request=invoice_data['payment_request'],
            amount_sats=amount_sats
        )
        
        logger.info(
            "lightning_payout_completed",
            user_id=user_id,
            amount_eur=float(amount_eur),
            amount_sats=amount_sats,
            fee_sats=payment_result['fee_sats']
        )
        
        return {
            "success": True,
            "amount_eur": float(amount_eur),
            "amount_sats": amount_sats,
            "fee_sats": payment_result['fee_sats'],
            "payment_hash": payment_result['payment_hash'],
            "payment_preimage": payment_result['payment_preimage']
        }
        
    except Exception as e:
        logger.error(
            "lightning_payout_failed",
            user_id=user_id,
            error=str(e)
        )
        return {
            "success": False,
            "error": str(e)
        }

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example_lightning_payout():
    """Example: Process Lightning payout"""
    
    result = await process_lightning_payout(
        user_id="user_123",
        amount_eur=Decimal("25.00"),
        lightning_address="artist@remixa.com"
    )
    
    if result['success']:
        print(f"✓ Paid {result['amount_sats']} sats (€{result['amount_eur']})")
        print(f"  Fee: {result['fee_sats']} sats")
        print(f"  Hash: {result['payment_hash']}")
    else:
        print(f"✗ Payment failed: {result['error']}")

if __name__ == "__main__":
    asyncio.run(example_lightning_payout())
