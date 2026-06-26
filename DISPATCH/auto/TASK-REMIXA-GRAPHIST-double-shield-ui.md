# TASK: REMIXA-GRAPHIST-double-shield-ui

## Agent Role
* **Agent**: Graphist (Cursor / Codex / Frontend Engineer)
* **Status**: ASSIGNED
* **Dependencies**: React, Next.js, TailwindCSS (if configured), D3/SVG Lineage Graph

## Context & Objectives
Because TikTok and other social networks strip file metadata headers (including C2PA signatures), our public `/verify` portal must support a fallback verification mechanism. If standard metadata parsing fails, the portal must send the file for waveform verification.

Your task is to update the drag-and-drop verification route to handle this double-shield mechanism and enhance the lineage chain visualization.

## Files to Modify
1. [verify/page.tsx](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/frontend/app/verify/page.tsx)

## Execution Instructions

### Step 1: Support Dual Verification Endpoints
* In `verify/page.tsx`, handle files uploaded via the drag-and-drop zone.
* First, attempt to post the file to `/api/c2pa/validate` to read metadata headers.
* If the API returns a `404` or "no manifest found" (indicating the file header was stripped):
  * Trigger a request to the backend `/api/c2pa/verify-waveform` endpoint.
  * Show a loading spinner with text: "Checking waveform watermark..."

### Step 2: Render Strip Warning Badges
* If the verification is recovered via the waveform fallback, display a warning badge:
  `[⚠️ Waveform Verified - Metadata Stripped]`
  with a tooltip explaining that social media processing stripped the file's metadata, but our robust waveform watermark verified its authenticity.

### Step 3: Enhance D3/SVG Lineage Graph
* Ensure the lineage graph shows all nodes from the root track to all remixes.
* Format node bubbles with:
  * Username of the creator.
  * Prompt prefix.
  * Distributed royalty share percentage.

## Verification Checklist
* [ ] Test drag-and-drop with a metadata-clean track (should resolve instantly via C2PA endpoint).
* [ ] Test drag-and-drop with a metadata-stripped track (should fall back and resolve via waveform endpoint).
* [ ] Verify that UI elements adapt cleanly to mobile and desktop layouts.
