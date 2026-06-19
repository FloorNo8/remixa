#!/usr/bin/env python3
"""
Seed Tape Generator for EU Sound Lab
Generates 100 diverse base tapes + remixes to populate the platform at launch.

Usage:
    python scripts/generate_seed_tapes.py --count 100
    python scripts/generate_seed_tapes.py --count 100 --with-remixes
"""

import requests
import time
import random
import argparse
from typing import List, Dict

# API Configuration
API_BASE_URL = "http://localhost:8000"
SEED_USER_TOKEN = "YOUR_SEED_USER_TOKEN_HERE"  # Replace with actual token

# 100 diverse prompts across genres
SEED_PROMPTS = [
    # Lofi Hip Hop (10)
    "lofi hip hop 85bpm chill study vibes with vinyl crackle",
    "lofi beats 90bpm rainy day coffee shop atmosphere",
    "lofi jazz 80bpm late night study session",
    "lofi piano 75bpm peaceful morning meditation",
    "lofi guitar 88bpm sunset beach relaxation",
    "lofi ambient 70bpm deep focus concentration",
    "lofi boom bap 92bpm nostalgic 90s vibes",
    "lofi rhodes 82bpm cozy bedroom producer",
    "lofi strings 78bpm melancholic autumn evening",
    "lofi synth 86bpm cyberpunk city night",
    
    # Phonk (10)
    "phonk drift 140bpm dark aggressive memphis",
    "phonk trap 145bpm cowbell heavy bass",
    "phonk house 138bpm brazilian funk influence",
    "phonk drill 142bpm uk grime energy",
    "phonk wave 135bpm vaporwave aesthetic",
    "phonk rage 150bpm distorted 808s",
    "phonk ambient 130bpm ethereal dark",
    "phonk jersey 148bpm club bounce",
    "phonk experimental 125bpm glitch hop",
    "phonk classic 140bpm three 6 mafia style",
    
    # House (10)
    "house 128bpm summer beach party vibes",
    "deep house 122bpm soulful vocals atmospheric",
    "tech house 126bpm minimal groovy bassline",
    "progressive house 130bpm euphoric festival anthem",
    "tropical house 120bpm island paradise sunset",
    "future house 128bpm bouncy synth leads",
    "bass house 125bpm heavy drops wobble",
    "melodic house 124bpm emotional piano chords",
    "afro house 123bpm tribal percussion rhythms",
    "electro house 128bpm big room energy",
    
    # Trap (10)
    "trap 150bpm hard 808s aggressive hi hats",
    "melodic trap 140bpm emotional guitar sample",
    "drill trap 145bpm uk dark menacing",
    "latin trap 138bpm reggaeton influence",
    "cloud trap 135bpm dreamy ambient pads",
    "rage trap 155bpm distorted synths chaotic",
    "trap soul 142bpm rnb vocals smooth",
    "experimental trap 148bpm glitch electronic",
    "trap metal 160bpm heavy guitar riffs",
    "trap jazz 130bpm saxophone improvisation",
    
    # Ambient (10)
    "ambient 60bpm ethereal peaceful meditation",
    "dark ambient 55bpm cinematic horror atmosphere",
    "space ambient 65bpm cosmic journey exploration",
    "nature ambient 58bpm forest birds water",
    "drone ambient 50bpm minimalist sustained tones",
    "ambient techno 120bpm hypnotic repetitive",
    "ambient dub 70bpm echoing reverb delay",
    "ambient jazz 62bpm smooth saxophone chords",
    "ambient classical 68bpm orchestral strings",
    "ambient electronic 75bpm modular synth textures",
    
    # Drum & Bass (10)
    "drum and bass 174bpm liquid smooth vocals",
    "neurofunk 172bpm dark technical bassline",
    "jungle 168bpm breakbeat amen break",
    "jump up 175bpm energetic party anthem",
    "minimal dnb 170bpm stripped back groovy",
    "atmospheric dnb 174bpm ethereal pads",
    "halftime dnb 85bpm heavy trap influence",
    "techstep 172bpm industrial dark mechanical",
    "sambass 176bpm brazilian percussion",
    "intelligent dnb 168bpm jazz fusion complex",
    
    # Techno (10)
    "techno 130bpm industrial dark warehouse",
    "minimal techno 125bpm hypnotic repetitive",
    "acid techno 135bpm 303 bassline squelch",
    "hard techno 140bpm aggressive kick drums",
    "melodic techno 128bpm emotional synth leads",
    "dub techno 122bpm echoing delay reverb",
    "detroit techno 132bpm classic 909 drums",
    "peak time techno 138bpm festival main stage",
    "ambient techno 120bpm atmospheric pads",
    "experimental techno 145bpm glitch modular",
    
    # Dubstep (10)
    "dubstep 140bpm heavy wobble bass drops",
    "melodic dubstep 150bpm emotional vocals",
    "riddim 140bpm repetitive headbang rhythm",
    "brostep 145bpm aggressive metallic synths",
    "chillstep 70bpm ambient atmospheric",
    "deathstep 150bpm brutal distorted bass",
    "future bass 150bpm colorful synth chords",
    "tearout 140bpm chaotic sound design",
    "deep dubstep 140bpm sub bass minimal",
    "hybrid trap dubstep 150bpm festival energy",
    
    # Trance (10)
    "trance 138bpm uplifting euphoric anthem",
    "progressive trance 132bpm melodic journey",
    "psytrance 145bpm psychedelic trippy",
    "tech trance 140bpm driving bassline",
    "vocal trance 136bpm emotional female vocals",
    "goa trance 148bpm indian influences",
    "hard trance 142bpm aggressive energetic",
    "balearic trance 128bpm sunset beach vibes",
    "uplifting trance 138bpm emotional breakdown",
    "dark trance 140bpm industrial atmosphere",
    
    # Experimental (10)
    "glitch hop 110bpm stuttering synths",
    "vaporwave 80bpm nostalgic 80s aesthetic",
    "breakcore 200bpm chaotic amen breaks",
    "idm 120bpm complex rhythms aphex twin",
    "witch house 140bpm dark occult atmosphere",
    "footwork 160bpm juke chicago dance",
    "hyperpop 170bpm distorted vocals chaotic",
    "synthwave 120bpm retro 80s neon",
    "chiptune 140bpm 8bit gameboy sounds",
    "noise 100bpm harsh industrial experimental",
]


def generate_tape(prompt: str, layer_type: str = "base", parent_id: str = None) -> Dict:
    """Generate a single tape via API."""
    payload = {
        "prompt": prompt,
        "layer_type": layer_type,
    }
    
    if parent_id:
        payload["parent_id"] = parent_id
    
    response = requests.post(
        f"{API_BASE_URL}/api/generate",
        json=payload,
        headers={"Authorization": f"Bearer {SEED_USER_TOKEN}"},
        timeout=30,
    )
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Failed to generate: {prompt}")
        print(f"   Status: {response.status_code}, Error: {response.text}")
        return None


def generate_base_tapes(count: int) -> List[Dict]:
    """Generate base layer tapes."""
    print(f"\n🎵 Generating {count} base tapes...")
    
    base_tapes = []
    prompts = SEED_PROMPTS[:count]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{count}] Generating: {prompt[:50]}...")
        
        tape = generate_tape(prompt, layer_type="base")
        if tape:
            base_tapes.append(tape)
            print(f"   ✅ Created: {tape['id']}")
        
        # Rate limiting: wait 1 second between requests
        time.sleep(1)
    
    print(f"\n✅ Generated {len(base_tapes)} base tapes")
    return base_tapes


def generate_remixes(base_tapes: List[Dict], remix_percentage: float = 0.3) -> List[Dict]:
    """Generate remix layers on top of base tapes."""
    print(f"\n🎨 Generating remixes ({int(remix_percentage * 100)}% of bases)...")
    
    # Select random base tapes to remix
    remix_count = int(len(base_tapes) * remix_percentage)
    bases_to_remix = random.sample(base_tapes, remix_count)
    
    remixes = []
    
    for i, base_tape in enumerate(bases_to_remix, 1):
        # Generate lyrics layer
        lyrics_prompt = f"{base_tape['prompt']} with melodic vocals"
        print(f"[{i}/{remix_count}] Adding lyrics to: {base_tape['id'][:8]}...")
        
        lyrics_tape = generate_tape(
            lyrics_prompt,
            layer_type="lyrics",
            parent_id=base_tape["id"]
        )
        
        if lyrics_tape:
            remixes.append(lyrics_tape)
            print(f"   ✅ Created lyrics layer: {lyrics_tape['id']}")
            
            # 10% chance to add voice layer on top
            if random.random() < 0.1:
                voice_prompt = f"{lyrics_prompt} with professional voice"
                print(f"   🎤 Adding voice layer...")
                
                voice_tape = generate_tape(
                    voice_prompt,
                    layer_type="voice",
                    parent_id=lyrics_tape["id"]
                )
                
                if voice_tape:
                    remixes.append(voice_tape)
                    print(f"   ✅ Created voice layer: {voice_tape['id']}")
        
        time.sleep(1)
    
    print(f"\n✅ Generated {len(remixes)} remix layers")
    return remixes


def main():
    parser = argparse.ArgumentParser(description="Generate seed tapes for EU Sound Lab")
    parser.add_argument("--count", type=int, default=100, help="Number of base tapes to generate")
    parser.add_argument("--with-remixes", action="store_true", help="Also generate remix layers")
    parser.add_argument("--api-url", type=str, default=API_BASE_URL, help="API base URL")
    parser.add_argument("--token", type=str, help="Seed user auth token")
    
    args = parser.parse_args()
    
    # Update globals
    global API_BASE_URL, SEED_USER_TOKEN
    API_BASE_URL = args.api_url
    if args.token:
        SEED_USER_TOKEN = args.token
    
    # Validate token
    if SEED_USER_TOKEN == "YOUR_SEED_USER_TOKEN_HERE":
        print("❌ Error: Please set SEED_USER_TOKEN or use --token flag")
        return
    
    print("=" * 60)
    print("EU SOUND LAB - SEED TAPE GENERATOR")
    print("=" * 60)
    print(f"API URL: {API_BASE_URL}")
    print(f"Base tapes: {args.count}")
    print(f"With remixes: {args.with_remixes}")
    print("=" * 60)
    
    # Generate base tapes
    base_tapes = generate_base_tapes(args.count)
    
    # Generate remixes if requested
    if args.with_remixes and base_tapes:
        remixes = generate_remixes(base_tapes)
        total = len(base_tapes) + len(remixes)
        print(f"\n🎉 Total tapes generated: {total}")
    else:
        print(f"\n🎉 Total base tapes generated: {len(base_tapes)}")
    
    print("\n✅ Seed generation complete!")


if __name__ == "__main__":
    main()
