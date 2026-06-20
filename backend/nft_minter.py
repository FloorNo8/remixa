"""
NFT Minting for Generations

Mints ERC-721 NFTs for AI-generated music on Ethereum/Polygon.
Includes metadata with C2PA credentials and royalty information.

Usage:
    from nft_minter import NFTMinter
    
    minter = NFTMinter(network='polygon')
    tx_hash = await minter.mint_generation(generation_id, owner_address)
"""

import os
import json
from typing import Dict, Any, Optional
from decimal import Decimal
from web3 import Web3
from web3.middleware import geth_poa_middleware
import structlog

logger = structlog.get_logger()

# Contract ABIs (simplified)
ERC721_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
            {"name": "uri", "type": "string"}
        ],
        "name": "safeMint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "tokenURI",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Network configurations
NETWORKS = {
    'ethereum': {
        'rpc_url': os.getenv('ETHEREUM_RPC_URL', 'https://mainnet.infura.io/v3/YOUR_KEY'),
        'chain_id': 1,
        'contract_address': os.getenv('ETHEREUM_NFT_CONTRACT'),
        'explorer': 'https://etherscan.io'
    },
    'polygon': {
        'rpc_url': os.getenv('POLYGON_RPC_URL', 'https://polygon-rpc.com'),
        'chain_id': 137,
        'contract_address': os.getenv('POLYGON_NFT_CONTRACT'),
        'explorer': 'https://polygonscan.com'
    },
    'base': {
        'rpc_url': os.getenv('BASE_RPC_URL', 'https://mainnet.base.org'),
        'chain_id': 8453,
        'contract_address': os.getenv('BASE_NFT_CONTRACT'),
        'explorer': 'https://basescan.org'
    }
}

class NFTMinter:
    """
    NFT minting service for AI-generated music
    """
    
    def __init__(self, network: str = 'polygon'):
        """
        Initialize NFT minter
        
        Args:
            network: Blockchain network ('ethereum', 'polygon', 'base')
        """
        if network not in NETWORKS:
            raise ValueError(f"Unsupported network: {network}")
        
        self.network = network
        self.config = NETWORKS[network]
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.config['rpc_url']))
        
        # Add PoA middleware for Polygon
        if network == 'polygon':
            self.w3.middleware_onion.inject(geth_poa_middleware, layer=0)
        
        # Load contract
        if self.config['contract_address']:
            self.contract = self.w3.eth.contract(
                address=self.config['contract_address'],
                abi=ERC721_ABI
            )
        else:
            self.contract = None
            logger.warning(f"No contract address configured for {network}")
        
        # Load wallet
        self.private_key = os.getenv('MINTER_PRIVATE_KEY')
        if self.private_key:
            self.account = self.w3.eth.account.from_key(self.private_key)
        else:
            self.account = None
            logger.warning("No minter private key configured")
    
    def create_metadata(
        self,
        generation_id: str,
        title: str,
        description: str,
        audio_url: str,
        image_url: str,
        creator_address: str,
        parent_id: Optional[str] = None,
        c2pa_manifest: Optional[Dict] = None,
        royalty_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Create ERC-721 metadata JSON
        
        Args:
            generation_id: Generation UUID
            title: Track title
            description: Track description
            audio_url: Audio file URL
            image_url: Cover image URL
            creator_address: Creator's wallet address
            parent_id: Parent generation ID (for remixes)
            c2pa_manifest: C2PA content credentials
            royalty_info: Royalty split information
        
        Returns:
            ERC-721 compliant metadata dict
        """
        metadata = {
            "name": title,
            "description": description,
            "image": image_url,
            "animation_url": audio_url,
            "external_url": f"https://remixa.com/tape/{generation_id}",
            "attributes": [
                {
                    "trait_type": "Generation ID",
                    "value": generation_id
                },
                {
                    "trait_type": "Creator",
                    "value": creator_address
                },
                {
                    "trait_type": "AI Generated",
                    "value": "Yes"
                }
            ]
        }
        
        # Add parent info for remixes
        if parent_id:
            metadata["attributes"].append({
                "trait_type": "Parent Generation",
                "value": parent_id
            })
            metadata["attributes"].append({
                "trait_type": "Type",
                "value": "Remix"
            })
        else:
            metadata["attributes"].append({
                "trait_type": "Type",
                "value": "Original"
            })
        
        # Add C2PA credentials
        if c2pa_manifest:
            metadata["c2pa"] = {
                "manifest": c2pa_manifest,
                "verified": True
            }
        
        # Add royalty information
        if royalty_info:
            metadata["royalties"] = royalty_info
        
        return metadata
    
    async def mint_generation(
        self,
        generation_id: str,
        owner_address: str,
        metadata: Dict[str, Any],
        metadata_uri: str
    ) -> str:
        """
        Mint NFT for a generation
        
        Args:
            generation_id: Generation UUID
            owner_address: NFT owner address
            metadata: NFT metadata dict
            metadata_uri: IPFS/Arweave URI for metadata
        
        Returns:
            Transaction hash
        """
        if not self.contract or not self.account:
            raise ValueError("NFT minting not configured")
        
        try:
            # Convert generation_id to token ID (uint256)
            token_id = int(generation_id.replace('-', ''), 16) % (2**256)
            
            # Build transaction
            tx = self.contract.functions.safeMint(
                owner_address,
                token_id,
                metadata_uri
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 200000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(
                "nft_minted",
                generation_id=generation_id,
                token_id=token_id,
                owner=owner_address,
                tx_hash=tx_hash.hex(),
                network=self.network
            )
            
            return tx_hash.hex()
            
        except Exception as e:
            logger.error(
                "nft_mint_error",
                generation_id=generation_id,
                error=str(e)
            )
            raise
    
    def get_token_uri(self, token_id: int) -> str:
        """Get token URI for a minted NFT"""
        if not self.contract:
            raise ValueError("Contract not configured")
        
        return self.contract.functions.tokenURI(token_id).call()
    
    def get_explorer_url(self, tx_hash: str) -> str:
        """Get block explorer URL for transaction"""
        return f"{self.config['explorer']}/tx/{tx_hash}"

# ============================================================================
# IPFS/ARWEAVE UPLOAD
# ============================================================================

class MetadataUploader:
    """
    Upload NFT metadata to IPFS or Arweave
    """
    
    def __init__(self, storage: str = 'ipfs'):
        """
        Initialize uploader
        
        Args:
            storage: Storage provider ('ipfs' or 'arweave')
        """
        self.storage = storage
        
        if storage == 'ipfs':
            self.ipfs_api = os.getenv('IPFS_API_URL', 'https://ipfs.infura.io:5001')
            self.ipfs_gateway = os.getenv('IPFS_GATEWAY', 'https://ipfs.io/ipfs/')
        elif storage == 'arweave':
            self.arweave_api = os.getenv('ARWEAVE_API_URL', 'https://arweave.net')
    
    async def upload_metadata(self, metadata: Dict[str, Any]) -> str:
        """
        Upload metadata to decentralized storage
        
        Args:
            metadata: NFT metadata dict
        
        Returns:
            URI (ipfs:// or ar://)
        """
        if self.storage == 'ipfs':
            return await self._upload_to_ipfs(metadata)
        elif self.storage == 'arweave':
            return await self._upload_to_arweave(metadata)
        else:
            raise ValueError(f"Unsupported storage: {self.storage}")
    
    async def _upload_to_ipfs(self, metadata: Dict[str, Any]) -> str:
        """Upload to IPFS"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.ipfs_api}/api/v0/add",
                data={'file': json.dumps(metadata)}
            ) as response:
                result = await response.json()
                cid = result['Hash']
                
                logger.info("metadata_uploaded_ipfs", cid=cid)
                return f"ipfs://{cid}"
    
    async def _upload_to_arweave(self, metadata: Dict[str, Any]) -> str:
        """Upload to Arweave"""
        import aiohttp
        
        # TODO: Implement Arweave upload with wallet
        raise NotImplementedError("Arweave upload not yet implemented")

# ============================================================================
# ROYALTY ENFORCEMENT (EIP-2981)
# ============================================================================

class RoyaltyEnforcer:
    """
    Enforce on-chain royalties using EIP-2981
    """
    
    @staticmethod
    def encode_royalty_info(
        receiver: str,
        percentage: Decimal
    ) -> Dict[str, Any]:
        """
        Encode royalty info for EIP-2981
        
        Args:
            receiver: Royalty receiver address
            percentage: Royalty percentage (e.g., 10.00 for 10%)
        
        Returns:
            Royalty info dict
        """
        # EIP-2981 uses basis points (1/100th of a percent)
        basis_points = int(percentage * 100)
        
        return {
            "receiver": receiver,
            "royaltyAmount": basis_points
        }
    
    @staticmethod
    def calculate_royalty(
        sale_price: Decimal,
        percentage: Decimal
    ) -> Decimal:
        """Calculate royalty amount from sale price"""
        return (sale_price * percentage) / Decimal('100')

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def example_mint():
    """Example: Mint NFT for a generation"""
    
    # Initialize minter
    minter = NFTMinter(network='polygon')
    uploader = MetadataUploader(storage='ipfs')
    
    # Create metadata
    metadata = minter.create_metadata(
        generation_id="gen_abc123",
        title="Summer Vibes Remix",
        description="AI-generated remix with guaranteed royalties",
        audio_url="https://cdn.remixa.com/gen_abc123.mp3",
        image_url="https://cdn.remixa.com/gen_abc123.jpg",
        creator_address="0x123...abc",
        parent_id="gen_xyz789",
        c2pa_manifest={"verified": True},
        royalty_info={
            "platform": "30%",
            "parent": "50%",
            "grandparent": "20%"
        }
    )
    
    # Upload metadata to IPFS
    metadata_uri = await uploader.upload_metadata(metadata)
    
    # Mint NFT
    tx_hash = await minter.mint_generation(
        generation_id="gen_abc123",
        owner_address="0x123...abc",
        metadata=metadata,
        metadata_uri=metadata_uri
    )
    
    print(f"NFT minted! Transaction: {minter.get_explorer_url(tx_hash)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(example_mint())
