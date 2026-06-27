# System Design Document (SDD): Remixa Platform & Adoption Pipeline

**Version:** 1.0.0  
**Date:** 2026-06-27  
**Status:** Composed  
**Authors:** Remixa Multi-Vendor Co-Authoring Loop (`role-cpo`, `role-cmo`, `role-legal`, `role-royalty-steward`)

---

## Executive Summary
This document outlines the system architecture, licensing models, compliance gates, and copy positioning frameworks required to transition Remixa from a simple consumer music generator into a B2B generative music library for agencies, content creators, developers, and social artists.

---


## 1. Product & Telemetry Specification (role-cpo)

We establish three primary subscription tiers alongside a dynamic developer API to balance compute cost profile against platform margins:

*   **Remixa Free (€0.00):** 5 generations/hour, 10 remixes/hour, standard watermarking (AudioSeal).
*   **Remixa Pro (€9.99/mo):** 20 generations/hour, 100 remixes/hour, C2PA signed metadata, unwatermarked high-fidelity exports, whitelisting protection (own tracks only).
*   **Remixa Business (€49.99/mo):** 100 generations/hour, 500 remixes/hour, whitelisting protection for any licensed track, batch whitelisting CSV uploads, programmatic developer API access keys.

### The "Reach Score" Logarithmic Index:
To encourage high-quality Sound Root Beat submissions, creators are provided with a visual metric dashboard showcasing their catalog's B2B reach:
$$	ext{Reach Score} = \log_{10}(	ext{Total Views}) + (	ext{Active Branches} 	imes 1.5) + (	ext{Brand Whitelists} 	imes 10)$$
This ensures that commercial placements verified through media agency licensing are heavily prioritized, representing true utility value.

---

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

---

## 3. Compliance, GDPR & Risk Indemnification (role-legal)

Commercial B2B music distribution requires strict compliance guarantees to absorb agency liability:

1.  **Legal Risk Transference:** When agencies register campaign details (Agency, Client Brand, Campaign ID) to whitelist a URL, Remixa stands behind the track's originality as the sole rights-holder, protecting the agency and client from copyright claims.
2.  **C2PA Content Credentials:** Standardized metadata is embedded into the audio ID3 tags to verify the generation pedigree, meeting EU AI Act transparency rules.
3.  **GDPR-Safe Catalog Survival:** When a user requests profile erasure under GDPR Article 17, we hard-delete their PII (email, Stripe IDs, name) but preserve their generated audio files and parent-child splits intact if they are parents of active downstream remixes or whitelisted placements, avoiding database cascading failures and protecting downstream buyers.

---

## 4. Ledger Architecture & Transaction splits (role-royalty-steward)

Every derivative co-creation transaction (remix, vocal layer, or sync placement) enforces a strict conservation constraint to prevent double-spending or deficit:

*   **Parent Creator Split:** 40% (or 30% parent / 10% grandparent if nested).
*   **Platform Fee:** 30% (retained as platform gross margin).
*   **Sound Producer Catalog Pool:** 30% (apportioned to training catalog contributors based on usage weights).

### The Invariant Constraint:
All backend code and database triggers must satisfy the following ledger balance:
$$	ext{amount} = 	ext{platform\_fee} + 	ext{creator\_share} + 	ext{grandparent\_share} + 	ext{producer\_pool\_share}$$
