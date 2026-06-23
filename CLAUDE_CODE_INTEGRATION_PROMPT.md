# Claude Code Prompt: Complete Remixa Integration (Pre-Alpha → Production)

**Date:** 2026-06-23  
**Context:** Remixa has solid infrastructure and extensive feature code, but critical integration gaps prevent production use  
**Repository:** https://github.com/FloorNo8/remixa  
**Current State:** Pre-alpha scaffold with ~21K LOC, deployed but unmounted routers

---

## Your Mission

Transform Remixa from a pre-alpha scaffold into a production-ready platform by completing 7 critical integration tasks in order. All feature code exists—your job is to wire it together correctly, fix the money bugs, and **implement ALL mocked features to production quality**.

**Success Criteria:** All 7 blockers resolved, tests passing, routers mounted, real auth working, money-correct by construction verified, **ALL mocked features fully implemented**.

---

## CRITICAL: Read These Files First

**Before starting, read these files to understand the codebase:**

1. **Architecture & Constraints:**
   - `AGENTS.md` - Canonical agent guidance, gotchas, security rules
   - `backend/ROYALTY_ARCHITECTURE.md` - Money-correctness design
   - `DISCOVER_REPORT/PRODUCTION_READINESS_AUDIT.md` - Detailed audit findings

2. **Current State:**
   - `backend/main.py` - Only admin_router mounted, see what's missing
   - `backend/api_v2.py` - Remix/payout router (unmounted)
   - `backend/api_advanced.py` - Advanced features router (unmounted)
   - `backend/api_c2pa.py` - C2PA router (unmounted)
   - `backend/migrations/004_royalty_hardening.sql` - Money-correctness constraints

3. **Tests:**
   - `backend/tests/test_royalty_hardening.py` - Money-correctness tests
   - `backend/pytest.ini` - 70% coverage gate (must pass)

---

## Task 1: Implement Real Clerk JWT Authentication

**Current State:** `backend/main.py:296` returns hardcoded mock user, no JWT verification

**What to Do:**

1. **Fix `backend/clerk_auth.py`:**
   - Implement real JWT verification using `python-jose` (already in requirements.txt)
   - Verify against Clerk JWKS URL: `https://clerk.{domain}/.well-known/jwks.json`
   - Extract `user_id`, `email`, `role` from JWT claims
   - Return proper User object (not dict)

2. **Update `backend/main.py`:**
   - Remove mock `get_current_user` at line 296
   - Import real `get_current_user` from `clerk_auth.py`
   - Add `Header` import for authorization header

3. **Fix RBAC bug in `backend/rbac.py:49`:**
   - Current: `hasattr(current_user, 'role')` fails on dict
   - Fix: Handle both dict and object (use `getattr` with fallback)

**Verification:**
```bash
# Should return 401 with proper error
curl -X GET https://eu-sound-lab.fly.dev/api/v1/rate-limit/info

# Should return 200 with valid Clerk token
curl -X GET https://eu-sound-lab.fly.dev/api/v1/rate-limit/info \
  -H "Authorization: Bearer <valid-clerk-jwt>"
```

**Files to Modify:**
- `backend/clerk_auth.py` (implement JWT verification)
- `backend/main.py` (remove mock, import real auth)
- `backend/rbac.py` (fix hasattr bug)

**Tests to Pass:**
- `backend/tests/test_clerk_auth.py` (all tests)
- `backend/tests/test_auth_integration.py` (all tests)

---

## Task 2: Mount All Routers in main.py

**Current State:** Only `admin_router` mounted, api_v2/api_advanced/api_c2pa defined but not wired

**What to Do:**

1. **In `backend/main.py`, add after line 142 (after admin_router):**
   ```python
   from api_v2 import router as api_v2_router
   from api_advanced import router as api_advanced_router
   from api_c2pa import router as api_c2pa_router
   
   app.include_router(api_v2_router, prefix="/api/v2", tags=["v2"])
   app.include_router(api_advanced_router, prefix="/api/advanced", tags=["advanced"])
   app.include_router(api_c2pa_router, prefix="/api/c2pa", tags=["c2pa"])
   ```

2. **Verify router definitions:**
   - `backend/api_v2.py` - Check `router = APIRouter()` exists
   - `backend/api_advanced.py` - Check `router = APIRouter()` exists
   - `backend/api_c2pa.py` - Check `router = APIRouter()` exists

**Verification:**
```bash
# Should return OpenAPI spec with 40+ endpoints
curl https://eu-sound-lab.fly.dev/openapi.json | jq '.paths | length'

# Should list all mounted routers
curl https://eu-sound-lab.fly.dev/docs
```

**Files to Modify:**
- `backend/main.py` (add 3 include_router calls)

**Tests to Pass:**
- `backend/tests/test_remix_flow.py` (should now reach endpoints)

---

## Task 3: Fix Payout Column Mismatch

**Current State:** `distribute_remix_royalties_v2` writes to `user_ledger`, but `request_payout` reads `users.pending_payout` (never updated)

**What to Do:**

1. **Update `backend/migrations/004_royalty_hardening.sql:152-276`:**
   - After line 265 (ledger insert), add:
   ```sql
   -- Update pending_payout for withdrawal
   UPDATE users 
   SET pending_payout = pending_payout + v_parent_share
   WHERE id = v_parent_creator_id;
   
   IF v_grandparent_creator_id IS NOT NULL THEN
     UPDATE users 
     SET pending_payout = pending_payout + v_grandparent_share
     WHERE id = v_grandparent_creator_id;
   END IF;
   ```

2. **Create migration 011:**
   - File: `backend/migrations/011_sync_pending_payout.sql`
   - Backfill existing ledger balances to `users.pending_payout`:
   ```sql
   UPDATE users u
   SET pending_payout = COALESCE(
     (SELECT SUM(amount) FROM user_ledger WHERE user_id = u.id AND type = 'credit'),
     0
   );
   ```

3. **Update `backend/apply_migrations.py`:**
   - Add `011_sync_pending_payout.sql` to migration list

**Verification:**
```bash
# After remix, check both match
psql $DATABASE_URL -c "
  SELECT u.id, u.pending_payout, 
         COALESCE(SUM(ul.amount), 0) as ledger_balance
  FROM users u
  LEFT JOIN user_ledger ul ON ul.user_id = u.id AND ul.type = 'credit'
  GROUP BY u.id
  HAVING u.pending_payout != COALESCE(SUM(ul.amount), 0);
"
# Should return 0 rows
```

**Files to Modify:**
- `backend/migrations/004_royalty_hardening.sql` (add pending_payout updates)
- `backend/migrations/011_sync_pending_payout.sql` (new file)
- `backend/apply_migrations.py` (add 011 to list)

**Tests to Pass:**
- `backend/tests/test_royalty_hardening.py::test_payout_balance_consistency`

---

## Task 4: Fix Idempotency (Stable IDs)

**Current State:** Fresh `request_id` and `generation_id` per request defeat Stripe idempotency and DB uniqueness

**What to Do:**

1. **Update `backend/api_v2.py:492` (request_id):**
   - Current: `request_id = str(uuid.uuid4())`
   - Fix: Derive from user + parent + timestamp:
   ```python
   # Stable request_id for idempotency
   request_id = hashlib.sha256(
       f"{user_id}:{parent_id}:{prompt}:{style}".encode()
   ).hexdigest()[:32]
   ```

2. **Update `backend/api_v2.py:607` (generation_id):**
   - Current: `new_generation_id = str(uuid.uuid4())`
   - Fix: Use request_id as generation_id:
   ```python
   new_generation_id = f"gen_{request_id}"
   ```

3. **Update Stripe idempotency key at line 559:**
   - Current: `f"remix_{user_id}_{generation_id}_{request_id}"`
   - Fix: `f"remix_{request_id}"` (request_id is now stable)

4. **Verify ON CONFLICT works:**
   - Check `backend/migrations/004_royalty_hardening.sql:242`
   - Should have: `ON CONFLICT (remixer_id, generation_id) DO NOTHING`

**Verification:**
```bash
# Make same remix request twice
curl -X POST https://eu-sound-lab.fly.dev/api/v2/remix \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parent_id":"gen_abc","prompt":"add drums","style":"edm"}'

# Second request should return same generation_id, no double-charge
curl -X POST https://eu-sound-lab.fly.dev/api/v2/remix \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"parent_id":"gen_abc","prompt":"add drums","style":"edm"}'

# Check Stripe dashboard - should see only 1 charge
# Check user_ledger - should see only 1 credit per user
```

**Files to Modify:**
- `backend/api_v2.py` (stable request_id, generation_id, idempotency key)

**Tests to Pass:**
- `backend/tests/test_remix_flow.py::test_remix_idempotency_prevents_double_charge`

---

## Task 5: Wire Cron Scheduler

**Current State:** `fly.toml:21` references `scripts.cron_runner` which doesn't exist → cron crash-loops

**What to Do:**

1. **Create `backend/scripts/cron_runner.py`:**
   ```python
   #!/usr/bin/env python3
   """
   Cron entrypoint for Fly.io scheduled tasks.
   Usage: python -m scripts.cron_runner <job_name>
   """
   import sys
   import os
   from scripts.process_payouts import main as process_payouts
   from scripts.update_exchange_rates import main as update_rates
   from scripts.refresh_balances import main as refresh_balances
   
   JOBS = {
       'process_payouts': process_payouts,
       'update_exchange_rates': update_rates,
       'refresh_balances': refresh_balances,
   }
   
   if __name__ == '__main__':
       if len(sys.argv) < 2:
           print(f"Usage: {sys.argv[0]} <job_name>")
           print(f"Available jobs: {', '.join(JOBS.keys())}")
           sys.exit(1)
       
       job_name = sys.argv[1]
       if job_name not in JOBS:
           print(f"Unknown job: {job_name}")
           sys.exit(1)
       
       print(f"Running job: {job_name}")
       JOBS[job_name]()
   ```

2. **Update `backend/fly.toml:21-30`:**
   ```toml
   [[services.processes]]
   name = "cron"
   command = "python -m scripts.cron_runner process_payouts"
   schedule = "0 2 * * *"  # Daily at 2 AM UTC
   
   [[services.processes]]
   name = "exchange_rates"
   command = "python -m scripts.cron_runner update_exchange_rates"
   schedule = "0 */6 * * *"  # Every 6 hours
   ```

3. **Verify scripts have `main()` functions:**
   - `backend/scripts/process_payouts.py` - Add `def main()` wrapper
   - `backend/scripts/update_exchange_rates.py` - Add `def main()` wrapper
   - `backend/scripts/refresh_balances.py` - Add `def main()` wrapper

**Verification:**
```bash
# Test locally
python -m scripts.cron_runner process_payouts
python -m scripts.cron_runner update_exchange_rates

# Check Fly.io cron logs
flyctl logs -a eu-sound-lab --region ams | grep cron
```

**Files to Create:**
- `backend/scripts/cron_runner.py` (new file)

**Files to Modify:**
- `backend/fly.toml` (update cron commands)
- `backend/scripts/process_payouts.py` (add main() wrapper)
- `backend/scripts/update_exchange_rates.py` (add main() wrapper)
- `backend/scripts/refresh_balances.py` (add main() wrapper)

**Tests to Pass:**
- `backend/tests/test_cron_runner.py` (all tests)

---

## Task 6: Run Test Suite and Fix Failures

**Current State:** 65 tests exist but were never run, some contradict code

**What to Do:**

1. **Set up test database:**
   ```bash
   createdb remixa_test
   psql remixa_test < backend/database.sql
   psql remixa_test < backend/migrations/002_v2_social_features.sql
   psql remixa_test < backend/migrations/004_royalty_hardening.sql
   psql remixa_test < backend/migrations/011_sync_pending_payout.sql
   ```

2. **Run tests and fix failures:**
   ```bash
   cd backend
   export DATABASE_URL=postgresql://localhost/remixa_test
   export REDIS_URL=redis://localhost:6379/1
   export TESTING=true
   pytest -v --cov=backend --cov-report=term-missing
   ```

3. **Fix known issues:**
   - `test_royalty_hardening.py:520-559` - TypeError on erased grandparent
   - `test_royalty_hardening.py:189-192` - NULL snapshot instead of preserving
   - Any tests that assume different royalty splits than `004:152-276`

4. **Ensure 70% coverage gate passes:**
   - Check `pytest.ini` - `--cov-fail-under=70`
   - Add tests for uncovered code paths if needed

**Verification:**
```bash
# All tests should pass
pytest backend/tests/ -v

# Coverage should be ≥70%
pytest backend/tests/ --cov=backend --cov-report=term-missing

# No test should be skipped
pytest backend/tests/ -v | grep -i skip
```

**Files to Modify:**
- `backend/tests/test_royalty_hardening.py` (fix failing tests)
- `backend/migrations/004_royalty_hardening.sql` (fix NULL snapshot bug)
- Any other test files with failures

**Tests to Pass:**
- ALL 65 tests in `backend/tests/`
- Coverage ≥70%

---

## Task 7: Implement ALL Mocked Features to Production Quality

**CRITICAL:** Do NOT remove any mocked features. Every mock MUST be implemented to production quality.

### 7.1: MusicGen Integration (REQUIRED)

**Current State:** `backend/main.py:405` returns fake CDN URL

**What to Implement:**

1. **Replace mock with real Replicate API:**
   ```python
   # backend/main.py:405
   import replicate
   
   @app.post("/api/v1/generate")
   async def generate_audio(request: GenerateRequest, current_user = Depends(get_current_user)):
       # Start Replicate prediction
       prediction = replicate.predictions.create(
           version="671ac645ce5e552cc63a54a2bbff63fcf798043055d2dac5fc9e36a837eedcfb",
           input={
               "prompt": request.prompt,
               "duration": request.duration,
               "model_version": "stereo-large"
           }
       )
       
       # Poll for completion
       while prediction.status not in ["succeeded", "failed"]:
           time.sleep(1)
           prediction = replicate.predictions.get(prediction.id)
       
       if prediction.status == "failed":
           raise HTTPException(status_code=500, detail="Generation failed")
       
       # Store in database
       audio_url = prediction.output
       cur.execute("""
           INSERT INTO generations (id, user_id, prompt, style, audio_url, status)
           VALUES (%s, %s, %s, %s, %s, 'completed')
       """, (generation_id, current_user.id, request.prompt, request.style, audio_url))
       
       return {"generation_id": generation_id, "audio_url": audio_url}
   ```

2. **Add Replicate to requirements.txt:**
   ```
   replicate==0.15.0
   ```

3. **Set environment variable:**
   ```bash
   flyctl secrets set REPLICATE_API_TOKEN=<your-token>
   ```

**Verification:**
```bash
# Test real generation
curl -X POST https://eu-sound-lab.fly.dev/api/v1/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"upbeat electronic","style":"edm","duration":15}'

# Should return real Replicate URL
# Download and verify audio file is playable
wget <audio_url> -O test.mp3
ffprobe test.mp3  # Should show valid audio metadata
```

**Files to Modify:**
- `backend/main.py` (implement real MusicGen)
- `requirements.txt` (add replicate)

---

### 7.2: C2PA Crypto Signatures (REQUIRED)

**Current State:** `backend/c2pa_embedder.py` uses fake hash, no crypto signature

**What to Implement:**

1. **Uncomment c2pa-python in requirements.txt:**
   ```
   c2pa-python==0.3.0
   ```

2. **Implement real C2PA signing:**
   ```python
   # backend/c2pa_embedder.py
   from c2pa import Builder, ManifestStore
   
   def embed_c2pa_manifest(audio_path: str, generation_id: str, parent_id: str = None):
       # Create manifest
       builder = Builder()
       builder.add_assertion("c2pa.actions", {
           "actions": [{
               "action": "c2pa.created",
               "when": datetime.utcnow().isoformat(),
               "softwareAgent": "Remixa/1.0"
           }]
       })
       
       if parent_id:
           builder.add_assertion("c2pa.ingredient", {
               "relationship": "parentOf",
               "c2pa_manifest": {
                   "uri": f"https://remixa.com/api/c2pa/manifest/{parent_id}"
               }
           })
       
       # Sign with private key
       manifest = builder.sign(
           audio_path,
           private_key_path="/app/secrets/c2pa_private_key.pem",
           cert_path="/app/secrets/c2pa_cert.pem"
       )
       
       return manifest
   ```

3. **Generate C2PA certificates:**
   ```bash
   # Generate private key
   openssl genrsa -out c2pa_private_key.pem 2048
   
   # Generate certificate
   openssl req -new -x509 -key c2pa_private_key.pem -out c2pa_cert.pem -days 365
   
   # Store in Fly.io secrets
   flyctl secrets set C2PA_PRIVATE_KEY="$(cat c2pa_private_key.pem)"
   flyctl secrets set C2PA_CERT="$(cat c2pa_cert.pem)"
   ```

4. **Update CHECK constraint to match new manifest structure:**
   ```sql
   -- backend/migrations/012_c2pa_manifest_structure.sql
   ALTER TABLE generations DROP CONSTRAINT IF EXISTS check_c2pa_parent_consistency;
   
   ALTER TABLE generations ADD CONSTRAINT check_c2pa_parent_consistency
   CHECK (
     parent_id IS NULL OR 
     c2pa_manifest->'assertions'->0->'data'->'c2pa_manifest'->>'uri' = 
       'https://remixa.com/api/c2pa/manifest/' || parent_id
   );
   ```

**Verification:**
```bash
# Generate audio with C2PA
curl -X POST https://eu-sound-lab.fly.dev/api/v2/remix \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"parent_id":"gen_abc","prompt":"add drums"}'

# Download audio
wget <audio_url> -O remix.mp3

# Verify C2PA signature
c2pa-tool verify remix.mp3
# Should show: ✓ Valid signature
# Should show parent relationship

# Verify manifest matches DB
curl https://eu-sound-lab.fly.dev/api/c2pa/manifest/<generation_id>
```

**Files to Modify:**
- `backend/c2pa_embedder.py` (implement real crypto)
- `requirements.txt` (uncomment c2pa-python)
- `backend/migrations/012_c2pa_manifest_structure.sql` (new file)

---

### 7.3: Blockchain Integration (REQUIRED)

**Current State:** `backend/nft_minter.py` has ImportError (no web3), missing Arbitrum, NotImplementedError for Arweave

**What to Implement:**

1. **Add web3 to requirements.txt:**
   ```
   web3==6.11.0
   py-arweave==1.0.0
   ```

2. **Implement Arbitrum support:**
   ```python
   # backend/nft_minter.py:47-66
   NETWORKS = {
       'ethereum': {
           'rpc_url': os.getenv('ETHEREUM_RPC_URL'),
           'chain_id': 1,
           'contract': '0x...'  # Your NFT contract
       },
       'polygon': {
           'rpc_url': os.getenv('POLYGON_RPC_URL'),
           'chain_id': 137,
           'contract': '0x...'
       },
       'base': {
           'rpc_url': os.getenv('BASE_RPC_URL'),
           'chain_id': 8453,
           'contract': '0x...'
       },
       'arbitrum': {  # ADD THIS
           'rpc_url': os.getenv('ARBITRUM_RPC_URL'),
           'chain_id': 42161,
           'contract': '0x...'
       }
   }
   ```

3. **Implement Arweave upload:**
   ```python
   # backend/nft_minter.py:326
   async def upload_to_arweave(self, metadata: dict, audio_url: str) -> str:
       from arweave import Wallet, Transaction
       
       # Load wallet
       wallet = Wallet(os.getenv('ARWEAVE_WALLET_KEY'))
       
       # Download audio
       audio_data = requests.get(audio_url).content
       
       # Create transaction
       tx = Transaction(wallet, data=audio_data)
       tx.add_tag('Content-Type', 'audio/mpeg')
       tx.add_tag('App-Name', 'Remixa')
       tx.add_tag('Generation-ID', metadata['generation_id'])
       
       # Sign and send
       tx.sign()
       tx.send()
       
       return f"https://arweave.net/{tx.id}"
   ```

4. **Deploy NFT contracts to all 4 chains:**
   ```bash
   # Use Hardhat or Foundry
   cd backend
   npx hardhat deploy --network ethereum
   npx hardhat deploy --network polygon
   npx hardhat deploy --network base
   npx hardhat deploy --network arbitrum
   ```

**Verification:**
```bash
# Test NFT minting on each chain
for chain in ethereum polygon base arbitrum; do
  curl -X POST https://eu-sound-lab.fly.dev/api/advanced/nft/mint \
    -H "Authorization: Bearer $TOKEN" \
    -d "{\"generation_id\":\"gen_test\",\"chain\":\"$chain\"}"
  
  # Should return transaction hash
  # Verify on block explorer
done

# Test Arweave upload
curl -X POST https://eu-sound-lab.fly.dev/api/advanced/nft/mint \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"generation_id":"gen_test","chain":"polygon","upload_to_arweave":true}'

# Should return Arweave URL
# Verify audio accessible at https://arweave.net/<tx_id>
```

**Files to Modify:**
- `backend/nft_minter.py` (add Arbitrum, implement Arweave)
- `requirements.txt` (add web3, py-arweave)
- `backend/smart_contract_royalties.sol` (deploy to all chains)

---

### 7.4: Lightning Network Integration (REQUIRED)

**Current State:** `backend/lightning_payouts.py` has mock macaroon, wrong SATS_PER_EUR rate, no LND dependency

**What to Implement:**

1. **Fix SATS_PER_EUR rate:**
   ```python
   # backend/lightning_payouts.py:32
   # Current: SATS_PER_EUR = 100000 (off by 60×)
   # Fix: Fetch real-time rate
   def get_sats_per_eur() -> int:
       response = requests.get('https://blockchain.info/ticker')
       btc_per_eur = response.json()['EUR']['last']
       sats_per_btc = 100_000_000
       return int(sats_per_btc / btc_per_eur)
   
   SATS_PER_EUR = get_sats_per_eur()  # ~6,000,000 sats/EUR
   ```

2. **Add LND gRPC client:**
   ```python
   # requirements.txt
   lnd-grpc-client==0.4.0
   
   # backend/lightning_payouts.py:53-55
   import lnd_grpc
   
   # Load real macaroon from environment
   macaroon = os.getenv('LND_MACAROON')
   tls_cert = os.getenv('LND_TLS_CERT')
   
   lnd = lnd_grpc.Client(
       macaroon=macaroon,
       tls_cert=tls_cert,
       host=os.getenv('LND_HOST', 'localhost:10009')
   )
   ```

3. **Implement real Lightning payout:**
   ```python
   async def process_lightning_payout(user_id: str, amount_eur: Decimal, lightning_address: str):
       # Convert EUR to sats
       amount_sats = int(amount_eur * get_sats_per_eur())
       
       # Decode Lightning address to invoice
       invoice = await decode_lightning_address(lightning_address)
       
       # Send payment via LND
       payment = lnd.send_payment(
           payment_request=invoice,
           amt=amount_sats,
           timeout_seconds=60
       )
       
       if payment.status != 'SUCCEEDED':
           raise Exception(f"Payment failed: {payment.failure_reason}")
       
       # Record in database
       cur.execute("""
           INSERT INTO payouts (user_id, amount, method, status, tx_hash)
           VALUES (%s, %s, 'lightning', 'completed', %s)
       """, (user_id, amount_eur, payment.payment_hash))
       
       return payment.payment_hash
   ```

4. **Set up LND node or use hosted service:**
   ```bash
   # Option A: Self-hosted LND
   # Install LND, sync blockchain, generate macaroon
   
   # Option B: Use Voltage or Lightning Labs hosted node
   # Get macaroon and TLS cert from dashboard
   
   # Store in Fly.io secrets
   flyctl secrets set LND_MACAROON=<base64-macaroon>
   flyctl secrets set LND_TLS_CERT=<base64-cert>
   flyctl secrets set LND_HOST=<host:port>
   ```

**Verification:**
```bash
# Test Lightning payout
curl -X POST https://eu-sound-lab.fly.dev/api/advanced/payout/lightning \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"amount":0.10,"lightning_address":"user@getalby.com"}'

# Should return payment hash
# Verify payment received in Lightning wallet
# Check on mempool.space or 1ml.com

# Test rate conversion
curl https://eu-sound-lab.fly.dev/api/advanced/lightning/rate
# Should return current sats/EUR rate (~6M)
```

**Files to Modify:**
- `backend/lightning_payouts.py` (fix rate, add LND client, implement payouts)
- `requirements.txt` (add lnd-grpc-client)
- `backend/api_advanced.py:726-744` (remove TODO, wire to lightning_payouts)

---

### 7.5: Multi-Language Support (REQUIRED)

**Current State:** `frontend/app/components/MultiLanguageSupport.tsx` has 13 languages defined but only 5 have translations

**What to Implement:**

1. **Complete translations for all 13 languages:**
   ```typescript
   // frontend/app/components/MultiLanguageSupport.tsx
   const translations = {
     en: { /* existing */ },
     es: { /* existing */ },
     fr: { /* existing */ },
     de: { /* existing */ },
     it: { /* existing */ },
     
     // ADD COMPLETE TRANSLATIONS FOR:
     pt: {
       common: {
         welcome: "Bem-vindo ao Remixa",
         generate: "Gerar",
         remix: "Remix",
         // ... all keys
       },
       dashboard: { /* ... */ },
       earnings: { /* ... */ }
     },
     nl: { /* Dutch */ },
     pl: { /* Polish */ },
     ro: { /* Romanian */ },
     ar: { /* Arabic - RTL */ },
     he: { /* Hebrew - RTL */ },
     ja: { /* Japanese */ },
     zh: { /* Chinese */ }
   };
   ```

2. **Use professional translation service:**
   - Export English strings to JSON
   - Use DeepL API or professional translator
   - Import translations back
   - Verify with native speakers

3. **Test RTL languages:**
   ```typescript
   // Ensure RTL layout works
   const rtlLanguages = ['ar', 'he'];
   
   useEffect(() => {
     if (rtlLanguages.includes(currentLanguage)) {
       document.dir = 'rtl';
     } else {
       document.dir = 'ltr';
     }
   }, [currentLanguage]);
   ```

**Verification:**
```bash
# Test each language
for lang in en es fr de it pt nl pl ro ar he ja zh; do
  # Change language in UI
  # Verify all strings translated
  # Verify no "undefined" or missing keys
  # For ar/he: verify RTL layout correct
done

# Automated test
npm run test:i18n
# Should verify all keys present in all languages
```

**Files to Modify:**
- `frontend/app/components/MultiLanguageSupport.tsx` (complete all translations)
- `frontend/app/layout.tsx` (add RTL support)

---

## Final Verification: ALL Features Production-Ready

After completing all 7 tasks, verify EVERY feature works in production:

### Core Features
- [ ] Real Clerk JWT authentication working
- [ ] All routers mounted (admin, v2, advanced, c2pa)
- [ ] Money-correctness verified (no double-charges)
- [ ] Payout balances match ledger
- [ ] Cron jobs running without crashes

### Implemented Features (NOT Mocked)
- [ ] **MusicGen:** Real audio generation via Replicate
  - Test: Generate 10 tracks, all should be unique real audio
  - Verify: Download and play each file
  
- [ ] **C2PA:** Real crypto signatures
  - Test: Generate remix chain (A→B→C)
  - Verify: `c2pa-tool verify` shows valid signatures
  - Verify: Parent relationships correct in manifest
  
- [ ] **Blockchain:** NFT minting on all 4 chains
  - Test: Mint NFT on Ethereum, Polygon, Base, Arbitrum
  - Verify: Transaction hash on each block explorer
  - Verify: NFT visible in wallet (MetaMask)
  
- [ ] **Arweave:** Permanent audio storage
  - Test: Upload audio to Arweave
  - Verify: Audio accessible at arweave.net URL
  - Verify: Metadata correct
  
- [ ] **Lightning:** Instant Bitcoin payouts
  - Test: Request payout to Lightning address
  - Verify: Payment received in <1 second
  - Verify: Correct amount (check sats/EUR rate)
  
- [ ] **Multi-Language:** All 13 languages complete
  - Test: Switch to each language
  - Verify: No missing translations
  - Verify: RTL layout correct for Arabic/Hebrew

### Tests
- [ ] All 65 tests passing
- [ ] Coverage ≥70%
- [ ] No skipped tests
- [ ] CI pipeline green

### Production Health
- [ ] `/health` returns 200
- [ ] Database has real data
- [ ] No errors in Sentry for 24 hours
- [ ] All features accessible via API

---

## Success Criteria (FINAL)

**You are DONE when:**

✅ All 7 critical blockers resolved  
✅ All 65 tests passing with ≥70% coverage  
✅ All routers mounted and accessible  
✅ Real authentication working  
✅ Money-correctness verified  
✅ Cron jobs running  
✅ **MusicGen generating real audio**  
✅ **C2PA signatures cryptographically valid**  
✅ **NFTs minting on all 4 blockchains**  
✅ **Arweave uploads working**  
✅ **Lightning payouts instant (<1s)**  
✅ **All 13 languages fully translated**  
✅ Production deployment successful  
✅ No errors in Sentry for 24 hours  

**Then update:**
- `README.md` - Change status to "Production-Ready"
- Document all implemented features
- Create PR with all changes

---

## Important Notes

1. **NO SHORTCUTS:** Every mocked feature MUST be fully implemented
2. **TEST EVERYTHING:** Each feature must have working verification
3. **PRODUCTION QUALITY:** No TODOs, no NotImplementedError, no fake data
4. **FOLLOW AGENTS.md:** Never lower coverage gate, always test before deploying
5. **MONEY-CORRECTNESS:** All 5 invariants must hold with real money flows

---

**START HERE:** Task 1 - Implement Real Clerk JWT Authentication