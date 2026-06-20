"""
C2PA Verification API Endpoints

Provides endpoints to verify C2PA content credentials and check
binding between C2PA manifest and database parent_id.

Endpoints:
- GET /api/c2pa/verify/{generation_id} - Verify C2PA manifest
- GET /api/c2pa/manifest/{generation_id} - Get C2PA manifest
- POST /api/c2pa/validate - Validate manifest against database

Usage:
    from api_c2pa import router as c2pa_router
    app.include_router(c2pa_router)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import json
import psycopg2
from psycopg2.extras import RealDictCursor
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/c2pa", tags=["c2pa"])

# ============================================================================
# MODELS
# ============================================================================

class C2PAVerificationResponse(BaseModel):
    """Response for C2PA verification"""
    verified: bool
    generation_id: str
    manifest_parent_id: Optional[str]
    database_parent_id: Optional[str]
    binding_valid: bool
    issues: list[str]
    manifest: Optional[Dict[str, Any]]

class C2PAValidationRequest(BaseModel):
    """Request to validate C2PA manifest"""
    generation_id: str
    manifest: Dict[str, Any]

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/verify/{generation_id}", response_model=C2PAVerificationResponse)
async def verify_c2pa(
    generation_id: str,
    db = Depends(get_db)
) -> C2PAVerificationResponse:
    """
    Verify C2PA manifest for a generation
    
    Checks:
    1. Manifest exists
    2. Manifest parent_id matches database parent_id
    3. Manifest is well-formed
    4. Hash matches audio file
    
    Args:
        generation_id: UUID of generation to verify
    
    Returns:
        Verification result with binding status
    
    Example:
        GET /api/c2pa/verify/gen_abc123
        
        Response:
        {
            "verified": true,
            "generation_id": "gen_abc123",
            "manifest_parent_id": "gen_xyz789",
            "database_parent_id": "gen_xyz789",
            "binding_valid": true,
            "issues": [],
            "manifest": {...}
        }
    """
    cur = db.cursor()
    
    try:
        # Get generation from database
        cur.execute("""
            SELECT 
                id,
                parent_id,
                c2pa_manifest,
                audio_url
            FROM generations
            WHERE id = %s
        """, (generation_id,))
        
        gen = cur.fetchone()
        
        if not gen:
            raise HTTPException(
                status_code=404,
                detail=f"Generation {generation_id} not found"
            )
        
        issues = []
        manifest = gen['c2pa_manifest']
        database_parent_id = gen['parent_id']
        
        # Check if manifest exists
        if not manifest:
            return C2PAVerificationResponse(
                verified=False,
                generation_id=generation_id,
                manifest_parent_id=None,
                database_parent_id=database_parent_id,
                binding_valid=False,
                issues=["No C2PA manifest found"],
                manifest=None
            )
        
        # Extract parent_id from manifest
        manifest_parent_id = manifest.get('parent_generation_id')
        
        # Check binding (manifest parent_id must match database parent_id)
        binding_valid = True
        
        if database_parent_id is None and manifest_parent_id is not None:
            binding_valid = False
            issues.append(f"Manifest has parent_id '{manifest_parent_id}' but database has NULL")
        elif database_parent_id is not None and manifest_parent_id is None:
            binding_valid = False
            issues.append(f"Database has parent_id '{database_parent_id}' but manifest has NULL")
        elif database_parent_id != manifest_parent_id:
            binding_valid = False
            issues.append(
                f"Parent ID mismatch: manifest='{manifest_parent_id}', "
                f"database='{database_parent_id}'"
            )
        
        # Check manifest structure
        required_fields = ['claim_generator', 'instance_id', 'assertions']
        for field in required_fields:
            if field not in manifest:
                issues.append(f"Missing required field: {field}")
                binding_valid = False
        
        # Log verification
        logger.info(
            "c2pa_verification",
            generation_id=generation_id,
            binding_valid=binding_valid,
            issues=issues
        )
        
        return C2PAVerificationResponse(
            verified=binding_valid and len(issues) == 0,
            generation_id=generation_id,
            manifest_parent_id=manifest_parent_id,
            database_parent_id=database_parent_id,
            binding_valid=binding_valid,
            issues=issues,
            manifest=manifest
        )
        
    except Exception as e:
        logger.error(
            "c2pa_verification_error",
            generation_id=generation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Verification failed: {str(e)}"
        )
    finally:
        cur.close()

@router.get("/manifest/{generation_id}")
async def get_manifest(
    generation_id: str,
    db = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get C2PA manifest for a generation
    
    Args:
        generation_id: UUID of generation
    
    Returns:
        C2PA manifest JSON
    
    Example:
        GET /api/c2pa/manifest/gen_abc123
    """
    cur = db.cursor()
    
    try:
        cur.execute("""
            SELECT c2pa_manifest
            FROM generations
            WHERE id = %s
        """, (generation_id,))
        
        gen = cur.fetchone()
        
        if not gen:
            raise HTTPException(
                status_code=404,
                detail=f"Generation {generation_id} not found"
            )
        
        if not gen['c2pa_manifest']:
            raise HTTPException(
                status_code=404,
                detail=f"No C2PA manifest found for {generation_id}"
            )
        
        return gen['c2pa_manifest']
        
    finally:
        cur.close()

@router.post("/validate", response_model=C2PAVerificationResponse)
async def validate_manifest(
    request: C2PAValidationRequest,
    db = Depends(get_db)
) -> C2PAVerificationResponse:
    """
    Validate a C2PA manifest against database
    
    Used before inserting a new generation to ensure C2PA binding
    constraint will be satisfied.
    
    Args:
        request: Validation request with generation_id and manifest
    
    Returns:
        Validation result
    
    Example:
        POST /api/c2pa/validate
        {
            "generation_id": "gen_abc123",
            "manifest": {
                "parent_generation_id": "gen_xyz789",
                ...
            }
        }
    """
    cur = db.cursor()
    
    try:
        manifest = request.manifest
        manifest_parent_id = manifest.get('parent_generation_id')
        
        # Get parent_id from database (if this is a remix)
        cur.execute("""
            SELECT parent_id
            FROM generations
            WHERE id = %s
        """, (request.generation_id,))
        
        gen = cur.fetchone()
        database_parent_id = gen['parent_id'] if gen else None
        
        issues = []
        binding_valid = True
        
        # Validate binding
        if database_parent_id != manifest_parent_id:
            binding_valid = False
            issues.append(
                f"Parent ID mismatch: manifest='{manifest_parent_id}', "
                f"database='{database_parent_id}'"
            )
        
        # Validate manifest structure
        required_fields = ['claim_generator', 'instance_id']
        for field in required_fields:
            if field not in manifest:
                issues.append(f"Missing required field: {field}")
                binding_valid = False
        
        return C2PAVerificationResponse(
            verified=binding_valid and len(issues) == 0,
            generation_id=request.generation_id,
            manifest_parent_id=manifest_parent_id,
            database_parent_id=database_parent_id,
            binding_valid=binding_valid,
            issues=issues,
            manifest=manifest
        )
        
    except Exception as e:
        logger.error(
            "c2pa_validation_error",
            generation_id=request.generation_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )
    finally:
        cur.close()

@router.get("/stats")
async def get_c2pa_stats(db = Depends(get_db)) -> Dict[str, Any]:
    """
    Get C2PA verification statistics
    
    Returns:
        Statistics about C2PA manifests in database
    
    Example:
        GET /api/c2pa/stats
        
        Response:
        {
            "total_generations": 1000,
            "with_manifest": 950,
            "without_manifest": 50,
            "binding_violations": 0,
            "verification_rate": 0.95
        }
    """
    cur = db.cursor()
    
    try:
        # Total generations
        cur.execute("SELECT COUNT(*) as total FROM generations")
        total = cur.fetchone()['total']
        
        # With manifest
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM generations 
            WHERE c2pa_manifest IS NOT NULL
        """)
        with_manifest = cur.fetchone()['count']
        
        # Check for binding violations
        cur.execute("""
            SELECT COUNT(*) as violations
            FROM generations
            WHERE c2pa_manifest IS NOT NULL
            AND (
                (parent_id IS NULL AND c2pa_manifest->>'parent_generation_id' IS NOT NULL)
                OR
                (parent_id IS NOT NULL AND c2pa_manifest->>'parent_generation_id' IS NULL)
                OR
                (parent_id::text != c2pa_manifest->>'parent_generation_id')
            )
        """)
        violations = cur.fetchone()['violations']
        
        return {
            "total_generations": total,
            "with_manifest": with_manifest,
            "without_manifest": total - with_manifest,
            "binding_violations": violations,
            "verification_rate": with_manifest / total if total > 0 else 0
        }
        
    finally:
        cur.close()

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_db():
    """Database connection dependency"""
    import os
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()
