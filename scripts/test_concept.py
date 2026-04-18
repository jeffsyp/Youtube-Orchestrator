"""Generate a fresh test concept for Crab Rave Shorts."""
import asyncio
import json
import re
import sys

sys.stdout.reconfigure(line_buffering=True)

from apps.worker.concept_generator import _get_engine
from packages.prompts.concept_drafts import build_concept_pitches_prompt, build_script_prompt
from packages.clients.claude import generate
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def main():
    engine = _get_engine()
    async with AsyncSession(engine) as s:
        row = await s.execute(text("""
            SELECT c.name, c.niche, COALESCE(cs.voice_id, 'fIGaHjfrR8KmMy0vGEVJ') as voice_id
            FROM channels c LEFT JOIN channel_schedules cs ON cs.channel_id = c.id WHERE c.id = 22
        """))
        ch = row.fetchone()
    await engine.dispose()

    channel_name, niche, voice_id = ch[0], ch[1], ch[2]

    # Phase 1: Pitch
    system, user = build_concept_pitches_prompt(
        channel_name=channel_name, niche=niche, past_titles=[], count=1,
    )
    resp = generate(prompt=user, system=system, model="claude-sonnet-4-6", max_tokens=4000)
    resp = resp.strip()
    if resp.startswith("```"):
        resp = re.sub(r"^```(?:json)?\s*", "", resp)
        resp = re.sub(r"\s*```$", "", resp)
    pitches = json.loads(resp)
    p = pitches[0]
    print(f"Pitch: {p['title']}")
    print(f"Brief: {p['brief']}")
    print()

    # Phase 2: Script
    sys2, usr2 = build_script_prompt(
        channel_name=channel_name, niche=niche, voice_id=voice_id, channel_id=22,
        title=p["title"], brief=p["brief"], structure=p["structure"],
        key_facts=p.get("key_facts", ""),
        format_strategy=p.get("format_strategy", "mini_story"),
    )
    resp2 = generate(prompt=usr2, system=sys2, model="claude-sonnet-4-6", max_tokens=4000)
    resp2 = resp2.strip()
    if resp2.startswith("```"):
        resp2 = re.sub(r"^```(?:json)?\s*", "", resp2)
        resp2 = re.sub(r"\s*```$", "", resp2)
    concept = json.loads(resp2)

    print(f"Title: {concept['title']}")
    print(f"Lines: {len(concept['narration'])}")
    total_words = 0
    for i, line in enumerate(concept["narration"]):
        wc = len(line.split())
        total_words += wc
        print(f"  {i}: ({wc}w) {line}")
    print(f"\nTotal words: {total_words} (~{total_words / 150 * 60:.0f}s at 150wpm)")

    with open("/tmp/test_concept.json", "w") as f:
        json.dump(concept, f, indent=2)
    print("\nSaved to /tmp/test_concept.json")


if __name__ == "__main__":
    asyncio.run(main())
