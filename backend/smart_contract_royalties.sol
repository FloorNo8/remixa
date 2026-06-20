// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/interfaces/IERC2981.sol";

/**
 * @title RemixaNFT
 * @dev ERC-721 NFT with EIP-2981 royalty enforcement for AI-generated music
 * 
 * Features:
 * - Automatic royalty splits (platform, parent, grandparent)
 * - On-chain provenance tracking
 * - C2PA metadata binding
 * - Multi-hop royalty distribution
 */
contract RemixaNFT is ERC721, ERC721URIStorage, Ownable, IERC2981 {
    
    // ========================================================================
    // STATE VARIABLES
    // ========================================================================
    
    uint256 private _nextTokenId;
    
    // Royalty configuration (basis points, 1/100th of a percent)
    uint96 public constant PLATFORM_ROYALTY = 300;      // 3%
    uint96 public constant PARENT_ROYALTY = 500;        // 5%
    uint96 public constant GRANDPARENT_ROYALTY = 200;   // 2%
    uint96 public constant TOTAL_ROYALTY = 1000;        // 10% total
    
    address public platformAddress;
    
    // Token metadata
    struct TokenMetadata {
        string generationId;
        address creator;
        uint256 parentTokenId;
        uint256 grandparentTokenId;
        bool isRemix;
        string c2paManifest;
    }
    
    mapping(uint256 => TokenMetadata) public tokenMetadata;
    mapping(string => uint256) public generationIdToTokenId;
    
    // Royalty tracking
    struct RoyaltyInfo {
        address platformReceiver;
        address parentReceiver;
        address grandparentReceiver;
        uint96 platformAmount;
        uint96 parentAmount;
        uint96 grandparentAmount;
    }
    
    mapping(uint256 => RoyaltyInfo) public royaltyInfo;
    
    // Events
    event GenerationMinted(
        uint256 indexed tokenId,
        string generationId,
        address indexed creator,
        bool isRemix
    );
    
    event RoyaltyPaid(
        uint256 indexed tokenId,
        address indexed receiver,
        uint256 amount,
        string royaltyType
    );
    
    // ========================================================================
    // CONSTRUCTOR
    // ========================================================================
    
    constructor(address _platformAddress) 
        ERC721("Remixa Music NFT", "REMIXA") 
        Ownable(msg.sender)
    {
        platformAddress = _platformAddress;
    }
    
    // ========================================================================
    // MINTING
    // ========================================================================
    
    /**
     * @dev Mint original generation (no parent)
     */
    function mintOriginal(
        address to,
        string memory generationId,
        string memory uri,
        string memory c2paManifest
    ) public onlyOwner returns (uint256) {
        uint256 tokenId = _nextTokenId++;
        
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, uri);
        
        tokenMetadata[tokenId] = TokenMetadata({
            generationId: generationId,
            creator: to,
            parentTokenId: 0,
            grandparentTokenId: 0,
            isRemix: false,
            c2paManifest: c2paManifest
        });
        
        generationIdToTokenId[generationId] = tokenId;
        
        // Set royalty info (only platform for originals)
        royaltyInfo[tokenId] = RoyaltyInfo({
            platformReceiver: platformAddress,
            parentReceiver: address(0),
            grandparentReceiver: address(0),
            platformAmount: TOTAL_ROYALTY,
            parentAmount: 0,
            grandparentAmount: 0
        });
        
        emit GenerationMinted(tokenId, generationId, to, false);
        
        return tokenId;
    }
    
    /**
     * @dev Mint remix (with parent)
     */
    function mintRemix(
        address to,
        string memory generationId,
        string memory uri,
        string memory c2paManifest,
        uint256 parentTokenId
    ) public onlyOwner returns (uint256) {
        require(_ownerOf(parentTokenId) != address(0), "Parent token does not exist");
        
        uint256 tokenId = _nextTokenId++;
        
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, uri);
        
        // Get parent metadata
        TokenMetadata memory parentMeta = tokenMetadata[parentTokenId];
        
        // Determine grandparent
        uint256 grandparentTokenId = parentMeta.isRemix ? parentMeta.parentTokenId : 0;
        
        tokenMetadata[tokenId] = TokenMetadata({
            generationId: generationId,
            creator: to,
            parentTokenId: parentTokenId,
            grandparentTokenId: grandparentTokenId,
            isRemix: true,
            c2paManifest: c2paManifest
        });
        
        generationIdToTokenId[generationId] = tokenId;
        
        // Set royalty info with splits
        address parentCreator = tokenMetadata[parentTokenId].creator;
        address grandparentCreator = grandparentTokenId > 0 
            ? tokenMetadata[grandparentTokenId].creator 
            : address(0);
        
        royaltyInfo[tokenId] = RoyaltyInfo({
            platformReceiver: platformAddress,
            parentReceiver: parentCreator,
            grandparentReceiver: grandparentCreator,
            platformAmount: PLATFORM_ROYALTY,
            parentAmount: PARENT_ROYALTY,
            grandparentAmount: grandparentCreator != address(0) ? GRANDPARENT_ROYALTY : 0
        });
        
        emit GenerationMinted(tokenId, generationId, to, true);
        
        return tokenId;
    }
    
    // ========================================================================
    // EIP-2981 ROYALTY STANDARD
    // ========================================================================
    
    /**
     * @dev Returns royalty info for a token sale
     * Note: This returns the total royalty. Actual distribution happens off-chain
     * or through a separate royalty splitter contract.
     */
    function royaltyInfo(uint256 tokenId, uint256 salePrice)
        external
        view
        override
        returns (address receiver, uint256 royaltyAmount)
    {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        
        RoyaltyInfo memory info = royaltyInfo[tokenId];
        
        // Return platform as primary receiver
        // Actual split happens in distributeRoyalties()
        receiver = info.platformReceiver;
        royaltyAmount = (salePrice * TOTAL_ROYALTY) / 10000;
    }
    
    /**
     * @dev Distribute royalties to all parties
     * Called by marketplace or royalty splitter contract
     */
    function distributeRoyalties(uint256 tokenId) external payable {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        require(msg.value > 0, "No payment sent");
        
        RoyaltyInfo memory info = royaltyInfo[tokenId];
        
        // Calculate amounts
        uint256 platformAmount = (msg.value * info.platformAmount) / 10000;
        uint256 parentAmount = (msg.value * info.parentAmount) / 10000;
        uint256 grandparentAmount = (msg.value * info.grandparentAmount) / 10000;
        
        // Distribute
        if (platformAmount > 0) {
            payable(info.platformReceiver).transfer(platformAmount);
            emit RoyaltyPaid(tokenId, info.platformReceiver, platformAmount, "platform");
        }
        
        if (parentAmount > 0 && info.parentReceiver != address(0)) {
            payable(info.parentReceiver).transfer(parentAmount);
            emit RoyaltyPaid(tokenId, info.parentReceiver, parentAmount, "parent");
        }
        
        if (grandparentAmount > 0 && info.grandparentReceiver != address(0)) {
            payable(info.grandparentReceiver).transfer(grandparentAmount);
            emit RoyaltyPaid(tokenId, info.grandparentReceiver, grandparentAmount, "grandparent");
        }
    }
    
    // ========================================================================
    // VIEWS
    // ========================================================================
    
    function getTokenMetadata(uint256 tokenId) 
        external 
        view 
        returns (TokenMetadata memory) 
    {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        return tokenMetadata[tokenId];
    }
    
    function getRoyaltyInfo(uint256 tokenId) 
        external 
        view 
        returns (RoyaltyInfo memory) 
    {
        require(_ownerOf(tokenId) != address(0), "Token does not exist");
        return royaltyInfo[tokenId];
    }
    
    function getTokenByGenerationId(string memory generationId) 
        external 
        view 
        returns (uint256) 
    {
        return generationIdToTokenId[generationId];
    }
    
    // ========================================================================
    // ADMIN
    // ========================================================================
    
    function setPlatformAddress(address _platformAddress) external onlyOwner {
        platformAddress = _platformAddress;
    }
    
    // ========================================================================
    // OVERRIDES
    // ========================================================================
    
    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }
    
    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721URIStorage, IERC165)
        returns (bool)
    {
        return interfaceId == type(IERC2981).interfaceId || super.supportsInterface(interfaceId);
    }
}
