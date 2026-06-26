# TASK: REMIXA-LEGIST-audioseal-waveform

## Agent Role
* **Agent**: Legist (Frontier LLM / Python DSP Engineer)
* **Status**: ASSIGNED
* **Dependencies**: Meta's `audioseal` and `torchaudio` libraries

## Context & Objectives
To conform with the EU AI Act Article 50 transparency requirements, Remixa must ensure all synthetic audio tracks generated on the platform are identifiable even after undergoing lossy compression or transcoding (e.g. when uploaded to TikTok).

Your task is to implement wave-level audio watermarking using Meta's `audioseal` library to embed the database `generation_id` directly in the audio waveform.

## Files to Modify
1. [requirements.txt](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/backend/requirements.txt)
2. [inference.py](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/backend/inference.py)
3. [api_c2pa.py](file:///Users/stefantalos/My%20Space/Fn8%20-%20Projects/remixa/backend/api_c2pa.py)

## Execution Instructions

### Step 1: Install Dependencies
* Add `audioseal==0.1.2` and `torchaudio` to `requirements.txt`.
* Run `pip install -r backend/requirements.txt`.

### Step 2: Implement Waveform Injection
* In `backend/inference.py`, load the generated audio track using `torchaudio`.
* Instantiate the AudioSeal watermark generator:
  ```python
  from audioseal import AudioSeal
  detector = AudioSeal.load_detector("audioseal_detector_16bits")
  generator = AudioSeal.load_generator("audioseal_wm_16bits")
  ```
* Convert the track's `generation_id` (UUID) into a 16-bit binary payload (or a unique numeric tag mapped to the database).
* Embed the watermark using the generator and save the watermarked audio to Cloudflare R2 storage.

### Step 3: Implement Extraction Endpoint
* In `backend/api_c2pa.py`, expose a new endpoint:
  ```python
  @router.post("/verify-waveform")
  async def verify_waveform(file: UploadFile = File(...), db = Depends(get_db)):
      ...
  ```
* Read the uploaded audio file into `torchaudio`, pass it through the AudioSeal `detector`, decode the 16-bit payload, and retrieve the corresponding track metadata and lineage chain from PostgreSQL database.

## Verification Checklist
* [ ] Verify that watermarking is fast enough to run within normal generation time (< 2 seconds overhead).
* [ ] Test that the watermark survives transcoding to 128 kbps mono MP3 format.
* [ ] Verify that `/api/c2pa/verify-waveform` successfully decodes the `generation_id` from a compressed file.
