#!/usr/bin/env python3
"""
CLI tool to verify AI disclosure credentials, C2PA manifests,
and AudioSeal watermark IDs in generated audio files.
"""
import os
import sys
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

# Add parent directory to path so we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from c2pa_embedder import C2PAEmbedder


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_track.py <audio_file_path_or_generation_id>")
        sys.exit(1)

    target = sys.argv[1]
    
    db_url = os.getenv("DATABASE_URL")
    conn = None
    generation_id = None
    audio_path = None
    
    # Check if target is a file or a UUID/generation ID
    if os.path.exists(target):
        audio_path = target
        print(f"[*] Analyzing local file: {audio_path}")
    else:
        # Assume it is a generation ID and try to resolve via DB/Download
        generation_id = target
        print(f"[*] Analyzing generation ID: {generation_id}")
        
        if not db_url:
            print("Error: DATABASE_URL env var required to resolve generation ID.")
            sys.exit(1)
            
        try:
            conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
            with conn.cursor() as cur:
                cur.execute("SELECT id, audio_url, watermark_id FROM generations WHERE id = %s", (generation_id,))
                row = cur.fetchone()
                if not row:
                    print(f"Error: Generation {generation_id} not found in database.")
                    sys.exit(1)
                
                audio_url = row["audio_url"]
                expected_watermark_id = row["watermark_id"]
                print(f"[+] Found generation in DB. Watermark ID: {expected_watermark_id}")
                
                # Check if file is available locally in the cache or temp dir
                cache_path = f"/tmp/remixa_cache/{generation_id}.mp3"
                if os.path.exists(cache_path):
                    audio_path = cache_path
                    print(f"[+] Found cached file: {audio_path}")
                else:
                    # Download file from audio_url
                    import requests
                    print(f"[*] Downloading track from {audio_url} ...")
                    temp_dir = "/tmp/remixa_verify"
                    os.makedirs(temp_dir, exist_ok=True)
                    audio_path = os.path.join(temp_dir, f"{generation_id}.mp3")
                    
                    resp = requests.get(audio_url)
                    resp.raise_for_status()
                    with open(audio_path, "wb") as f:
                        f.write(resp.content)
                    print(f"[+] Download complete: {audio_path}")
                    
        except Exception as e:
            print(f"Error connecting to database or downloading file: {e}")
            if conn:
                conn.close()
            sys.exit(1)

    # Instantiate embedder
    embedder = C2PAEmbedder()
    
    # 1. Verify C2PA manifest metadata
    manifest = None
    try:
        manifest = embedder.verify_c2pa(audio_path)
        print("\n=== C2PA Content Credentials ===")
        print(f"[PASSED] C2PA manifest found in audio metadata.")
        
        # Extract title and model version
        title = manifest.get("title", "Unknown")
        print(f" - Title: {title}")
        
        assertions = manifest.get("assertions", [])
        for assert_item in assertions:
            label = assert_item.get("label")
            data = assert_item.get("data", {})
            if label == "c2pa.ai_generative_training":
                print(f" - Model Version: {data.get('model', 'Unknown')}")
                print(f" - Training Hash: {data.get('training_data_hash', 'Unknown')}")
            elif label == "c2pa.actions":
                actions = data if isinstance(data, list) else [data]
                for act in actions:
                    print(f" - Action: {act.get('action')} by {act.get('softwareAgent')}")
                    params = act.get("parameters", {})
                    print(f"   Prompt: \"{params.get('prompt')}\"")
                    print(f"   Style: \"{params.get('style')}\"")
        
        # Try to extract generation ID from manifest
        instance_id = manifest.get("instance_id", "")
        if instance_id.startswith("xmp:iid:"):
            resolved_gen_id = instance_id.replace("xmp:iid:", "")
            if not generation_id:
                generation_id = resolved_gen_id
                print(f"[+] Extracted Generation ID from C2PA: {generation_id}")
                
    except Exception as e:
        print("\n=== C2PA Content Credentials ===")
        print(f"[FAILED] C2PA verification failed: {e}")

    # 2. Extract AudioSeal Watermark
    print("\n=== AudioSeal Waveform Watermark ===")
    print("[*] Decoding watermark message from waveform...")
    try:
        decoded_watermark_id = embedder.decode_waveform_watermark(audio_path)
        if decoded_watermark_id is not None:
            print(f"[PASSED] Decoded Watermark ID: {decoded_watermark_id}")
        else:
            print("[WARNING] No AudioSeal watermark detected in waveform (or low probability).")
            decoded_watermark_id = None
    except Exception as e:
        print(f"[FAILED] Watermark decoding failed: {e}")
        decoded_watermark_id = None

    # 3. Cross-reference with Database if connection is available
    if db_url and generation_id:
        print("\n=== Database Integrity Cross-Reference ===")
        try:
            if not conn:
                conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
            
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, watermark_id, style, is_public, parent_id
                    FROM generations
                    WHERE id = %s
                """, (generation_id,))
                db_record = cur.fetchone()
                
                if db_record:
                    print(f"[+] Found DB record for generation ID: {generation_id}")
                    print(f" - Expected Watermark ID: {db_record['watermark_id']}")
                    print(f" - Style: {db_record['style']}")
                    print(f" - Parent ID: {db_record['parent_id']}")
                    
                    if decoded_watermark_id is not None:
                        if int(db_record['watermark_id']) == int(decoded_watermark_id):
                            print("[VERIFIED] Waveform watermark ID matches database records exactly.")
                        else:
                            print("[ERROR] Watermark ID mismatch! DB has {}, but file contains {}.")
                    else:
                        print("[ERROR] File does not contain expected watermark ID.")
                else:
                    print(f"[WARNING] No DB record found for generation ID: {generation_id}")
        except Exception as e:
            print(f"[ERROR] Database cross-reference failed: {e}")
        finally:
            if conn:
                conn.close()

    print("\n[*] Analysis finished.")


if __name__ == "__main__":
    main()
