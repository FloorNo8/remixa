#!/usr/bin/env python3
"""
SDD Spec-Composition Pipeline (compose, not audit).
Simulates the additive co-authoring loop where each role profile (cpo, cmo, legal, royalty-steward)
contributes its respective specification domain to build a unified Remixa System Design Document.
"""

import os
import sys
from datetime import datetime

WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGENTS_DIR = os.path.join(WORKSPACE_DIR, ".agents", "skills")
OUTPUT_PATH = os.path.join(WORKSPACE_DIR, "docs", "remixa_system_design_document.md")

def load_role_jd(role_name: str) -> str:
    jd_path = os.path.join(AGENTS_DIR, role_name, "SKILL.md")
    if not os.path.exists(jd_path):
        print(f"Error: JD file for {role_name} not found at {jd_path}")
        sys.exit(1)
    with open(jd_path, "r", encoding="utf-8") as f:
        return f.read()

def run_composition_pipeline():
    print("🚀 Initiating SDD Spec-Composition Pipeline...")
    
    # Ensure docs directory exists
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    
    # Load all JDs for verification and loading
    cpo_jd = load_role_jd("role-cpo")
    cmo_jd = load_role_jd("role-cmo")
    legal_jd = load_role_jd("role-legal")
    steward_jd = load_role_jd("role-royalty-steward")
    
    print("✅ Successfully loaded all team role profiles (JDs).")
    print("🔄 Running additive co-authoring loop turns...")
    
    # Turn 1: role-cpo (Product & Telemetry Architecture)
    cpo_contribution = """
## 1. Product & Telemetry Specification (role-cpo)

We establish three primary subscription tiers alongside a dynamic developer API to balance compute cost profile against platform margins:

*   **Remixa Free (€0.00):** 5 generations/hour, 10 remixes/hour, standard watermarking (AudioSeal).
*   **Remixa Pro (€9.99/mo):** 20 generations/hour, 100 remixes/hour, C2PA signed metadata, unwatermarked high-fidelity exports, whitelisting protection (own tracks only).
*   **Remixa Business (€49.99/mo):** 100 generations/hour, 500 remixes/hour, whitelisting protection for any licensed track, batch whitelisting CSV uploads, programmatic developer API access keys.

### The "Reach Score" Logarithmic Index:
To encourage high-quality Sound Root Beat submissions, creators are provided with a visual metric dashboard showcasing their catalog's B2B reach:
$$\text{Reach Score} = \log_{10}(\text{Total Views}) + (\text{Active Branches} \times 1.5) + (\text{Brand Whitelists} \times 10)$$
This ensures that commercial placements verified through media agency licensing are heavily prioritized, representing true utility value.
"""

    # Turn 2: role-cmo (Positioning & Multi-Persona Copywriting)
    cmo_contribution = """
## 2. Positioning & Copywriting Framework (role-cmo)

We frame the platform's utility around five distinct adoption personas to build rapid catalog momentum:

### A. The Commercial Media Agency
*   *Positioning:* Risk-transference and absolute brand safety.
*   *Copy Hook:* *"Stop pitching audio you cannot clear. Remixa offers the first commercial generative music library with complete platform mute-protection and cryptographic C2PA provenance."*

### B. The Velocity Creator & MCN
*   *Positioning:* Consistent, unique sonic branding without demonetization risks.
*   *Copy Hook:* *"Create custom sonic signatures and mood variations for all channels under a single, unified Pro whitelisted seat."*

### C. The Tech & Indie Game Developer
*   *Positioning:* Dynamic, interactive stem soundtracks at a fraction of stock costs.
*   *Copy Hook:* *"Integrate our Developer Stems API to dynamically adjust score intensity, drum layers, and instrumentation based on real-time gameplay."*

### D. The Bedroom Vocalist & Social Artist
*   *Positioning:* Instant collaborative remixing and global distribution.
*   *Copy Hook:* *"Sing over trending beats, pay a flat €0.10, and publish cleared releases directly to Spotify and TikTok with automatic royalty splits."*
"""

    # Turn 3: role-legal (Compliance, GDPR & Risk Transference)
    legal_contribution = """
## 3. Compliance, GDPR & Risk Indemnification (role-legal)

Commercial B2B music distribution requires strict compliance guarantees to absorb agency liability:

1.  **Legal Risk Transference:** When agencies register campaign details (Agency, Client Brand, Campaign ID) to whitelist a URL, Remixa stands behind the track's originality as the sole rights-holder, protecting the agency and client from copyright claims.
2.  **C2PA Content Credentials:** Standardized metadata is embedded into the audio ID3 tags to verify the generation pedigree, meeting EU AI Act transparency rules.
3.  **GDPR-Safe Catalog Survival:** When a user requests profile erasure under GDPR Article 17, we hard-delete their PII (email, Stripe IDs, name) but preserve their generated audio files and parent-child splits intact if they are parents of active downstream remixes or whitelisted placements, avoiding database cascading failures and protecting downstream buyers.
"""

    # Turn 4: role-royalty-steward (Ledger & Split Architecture)
    steward_contribution = """
## 4. Ledger Architecture & Transaction splits (role-royalty-steward)

Every derivative co-creation transaction (remix, vocal layer, or sync placement) enforces a strict conservation constraint to prevent double-spending or deficit:

*   **Parent Creator Split:** 40% (or 30% parent / 10% grandparent if nested).
*   **Platform Fee:** 30% (retained as platform gross margin).
*   **Sound Producer Catalog Pool:** 30% (apportioned to training catalog contributors based on usage weights).

### The Invariant Constraint:
All backend code and database triggers must satisfy the following ledger balance:
$$\text{amount} = \text{platform\_fee} + \text{creator\_share} + \text{grandparent\_share} + \text{producer\_pool\_share}$$
"""

    # Assemble the final SDD
    sdd_header = f"""# System Design Document (SDD): Remixa Platform & Adoption Pipeline

**Version:** 1.0.0  
**Date:** {datetime.now().strftime('%Y-%m-%d')}  
**Status:** Composed  
**Authors:** Remixa Multi-Vendor Co-Authoring Loop (`role-cpo`, `role-cmo`, `role-legal`, `role-royalty-steward`)

---

## Executive Summary
This document outlines the system architecture, licensing models, compliance gates, and copy positioning frameworks required to transition Remixa from a simple consumer music generator into a B2B generative music library for agencies, content creators, developers, and social artists.

---
"""

    sdd_content = "\n".join([
        sdd_header,
        cpo_contribution,
        "---",
        cmo_contribution,
        "---",
        legal_contribution,
        "---",
        steward_contribution
    ])

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(sdd_content)
        
    print(f"🎉 Successfully composed Remixa SDD! Document written to: {OUTPUT_PATH}")

if __name__ == "__main__":
    run_composition_pipeline()
