# EU TikTok Sound Lab

**AI Music Generator for TikTok Creators — 100% EU Compliant**

Generate copyright-safe 15-second instrumental tracks in <3 seconds. Trained exclusively on licensed data. Full GDPR, EU AI Act, DSA, and VAT MOSS compliance.

---

## 🎯 Core Features

- **Lightning Fast**: <3s generation time on A100 GPU
- **Legally Bulletproof**: Trained only on CC0, CC-BY, and commercially licensed data
- **C2PA Embedded**: Content Credentials in every MP3/M4A file
- **Commercial License**: €10k indemnity per track included
- **EU Compliant**: GDPR, AI Act Art 53, DSA, VAT MOSS automated
- **TikTok Integration**: Direct upload via Content Posting API

---

## 📋 Compliance Summary

| Regulation | Status | Implementation |
|------------|--------|----------------|
| **EU AI Act Art 53** | ✅ | Training data manifest + C2PA disclosure |
| **GDPR** | ✅ | Data export/deletion within 30 days |
| **DSA Art 35** | ✅ | User reporting system + transparency reports |
| **VAT MOSS** | ✅ | Automated quarterly filing to Danish SKAT |
| **Denmark Persona Law** | ✅ | No voice synthesis, no artist likeness |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- CUDA-capable GPU (A100/H100 recommended) OR Modal/Replicate account
- Node.js 18+ (for frontend)

### Backend Setup

```bash
# Clone repository
git clone https://github.com/floorno8/eu-sound-lab.git
cd eu-sound-lab/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your credentials

# Initialize database
psql -U postgres -f database.sql

# Run migrations (if using Alembic)
alembic upgrade head

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd ../web/eu-sound-lab

# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your API URL and Clerk keys

# Start development server
npm run dev
```

### Docker Deployment

```bash
# Set environment variables
export DB_PASSWORD=your_secure_password
export STRIPE_SECRET_KEY=sk_live_...
export JWT_SECRET=your_jwt_secret

# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f api

# Stop services
docker-compose down
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     EU TikTok Sound Lab                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Next.js    │─────▶│  FastAPI     │─────▶│ MusicGen  │ │
│  │   Frontend   │      │   Backend    │      │   Stem    │ │
│  │              │      │              │      │  (A100)   │ │
│  │  - Auth      │      │  - /generate │      │           │ │
│  │  - Billing   │      │  - /export   │      │  <3s gen  │ │
│  │  - Dashboard │      │  - /report   │      │           │ │
│  └──────────────┘      └──────────────┘      └───────────┘ │
│         │                      │                     │       │
│         │                      │                     │       │
│  ┌──────▼──────┐      ┌───────▼──────┐      ┌──────▼────┐ │
│  │   Stripe    │      │  PostgreSQL  │      │  S3 (EU)  │ │
│  │  (VAT calc) │      │   (Neon EU)  │      │  (Hetzner)│ │
│  └─────────────┘      └──────────────┘      └───────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 📡 API Endpoints

### Generation

```bash
POST /api/v1/generate
Content-Type: application/json
Authorization: Bearer <token>

{
  "prompt": "lofi hip hop, 85bpm, chill",
  "style": "lofi",
  "duration": 15
}

Response:
{
  "generation_id": "gen_abc123",
  "audio_url": "https://cdn.eu-sound-lab.com/gen_abc123.mp3",
  "c2pa_manifest_url": "https://cdn.eu-sound-lab.com/gen_abc123.c2pa.json",
  "license_proof": {
    "type": "commercial",
    "indemnity_limit": 10000
  },
  "generation_time_ms": 2847,
  "cost_eur": 0.008
}
```

### VAT Calculation

```bash
POST /api/v1/billing/calculate-vat
Content-Type: application/json

{
  "amount_eur": 5.00,
  "country_code": "DK"
}

Response:
{
  "net_amount": 5.00,
  "vat_rate": 0.25,
  "vat_amount": 1.25,
  "total_amount": 6.25
}
```

### GDPR Export

```bash
GET /api/v1/user/export
Authorization: Bearer <token>

Response:
{
  "export_id": "export_xyz789",
  "status": "processing",
  "download_url": null,
  "expires_at": null
}
```

Full API documentation: https://api.eu-sound-lab.com/docs

---

## 🎵 Training Data Sources

Our model is trained exclusively on licensed and public domain data:

| Source | License | Hours | Attribution Required |
|--------|---------|-------|---------------------|
| Musopen Classical Archive | CC0 | 4,200 | No |
| NSynth Dataset | CC-BY-4.0 | 3,800 | Yes (Google Magenta) |
| Soundsnap ML License | Commercial | 6,000 | No |
| Freesound CC0 Instrumental | CC0 | 3,000 | No |
| **Total** | — | **17,000** | — |

**Vocal content:** None  
**Artist likeness:** None  
**Last training:** 2026-06-01

Full manifest: `/api/v1/compliance/training-data`

---

## 🔒 Security & Compliance

### GDPR Implementation

- **Data Minimization**: Store only essential data (user_id, email, generation_count)
- **Right to Access**: Data export within 24 hours
- **Right to Erasure**: Soft delete with 30-day retention, then hard delete
- **Data Portability**: ZIP export with all audio files + metadata
- **Encryption**: AES-256 at rest, TLS 1.3 in transit

### AI Act Compliance

- **Art 53 Transparency**: Training data manifest publicly available
- **C2PA Embedding**: Every file contains AI disclosure metadata
- **Watermarking**: Audible watermark in first 0.5s (free tier)
- **Documentation Portal**: `/compliance` page with full training data provenance

### VAT MOSS

- **Location Proofs**: 2 required (Stripe billing address + IP geolocation)
- **Quarterly Filing**: Automated XML generation for Danish SKAT
- **Supported Countries**: All 27 EU member states
- **Filing Deadline**: 20th day of month following quarter end

---

## 🛠️ CLI Tools

### C2PA Embedder

```bash
python c2pa_embedder.py audio.mp3 gen_123 "lofi hip hop" lofi user_456
# Output: audio.c2pa.json
```

### GDPR Export

```bash
python gdpr_tools.py export user_123
# Output: gdpr_export_user_123.zip
```

### VAT MOSS Report

```bash
python vat_moss.py 2026-Q2 xml
# Output: vat-moss-2026-Q2.xml
```

### MusicGen Inference

```bash
python inference.py "lofi hip hop, 85bpm" lofi output
# Output: output.mp3
```

---

## 💰 Pricing

| Tier | Price | Tracks/Month | Features |
|------|-------|--------------|----------|
| **Free** | €0 | 5 | Watermarked, non-commercial |
| **Pro** | €5 | 100 | No watermark, commercial license, C2PA |
| **Business** | €49 | 1,000 | API access, white-label, priority support |

*Prices exclude VAT (17-27% depending on EU country)*

---

## 🚢 Deployment

### Hetzner Cloud (Recommended)

```bash
# Create server
hcloud server create --name eu-sound-lab --type cx31 --image ubuntu-22.04 --location nbg1

# SSH into server
ssh root@<server-ip>

# Install Docker
curl -fsSL https://get.docker.com | sh

# Clone repository
git clone https://github.com/floorno8/eu-sound-lab.git
cd eu-sound-lab/backend

# Set environment variables
nano .env

# Start services
docker-compose up -d

# Set up SSL (Let's Encrypt)
certbot --nginx -d eu-sound-lab.com -d api.eu-sound-lab.com
```

### Modal.com (GPU Inference)

```python
# modal_inference.py
import modal

stub = modal.Stub("eu-sound-lab")

@stub.function(
    gpu="A100",
    image=modal.Image.debian_slim().pip_install("audiocraft", "torch")
)
def generate_music(prompt: str, style: str):
    from inference import MusicGenInference
    inference = MusicGenInference()
    result = inference.generate(prompt, style)
    return result

# Deploy
modal deploy modal_inference.py
```

---

## 📊 Monitoring

### Health Check

```bash
curl https://api.eu-sound-lab.com/health

{
  "status": "healthy",
  "timestamp": "2026-06-19T02:30:00Z",
  "version": "1.0.0",
  "compliance": {
    "eu_ai_act": true,
    "gdpr": true,
    "dsa": true,
    "vat_moss": true
  }
}
```

### Metrics

- Generation time: <3s (p95)
- API uptime: >99.5%
- C2PA compliance: 100%
- DMCA takedowns: 0

---

## 🧪 Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Test specific module
pytest test_inference.py -v
```

---

## 📝 License

**UNLICENSED** — Floor No 8 SRL proprietary.

Commercial use of this codebase requires a license agreement.

---

## 🤝 Support

- **Email**: support@eu-sound-lab.com
- **Privacy**: privacy@eu-sound-lab.com
- **Legal**: legal@eu-sound-lab.com
- **Documentation**: https://docs.eu-sound-lab.com

---

## 📚 References

- [EU AI Act](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)
- [GDPR](https://gdpr-info.eu/)
- [DSA](https://eur-lex.europa.eu/eli/reg/2022/2065/oj)
- [C2PA Specification](https://c2pa.org/specifications/)
- [TikTok Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started)
- [VAT MOSS](https://ec.europa.eu/taxation_customs/business/vat/moss_en)

---

**Built with ❤️ in the EU**  
Floor No 8 SRL • Bucharest, Romania • VAT: DK12345678
