"""Upload a batch of regenerated videos after 12:01 PM Pacific.

Waits for all runs to finish generating, then uploads each to its channel
with publish times staggered 1-3 hours after 12:01 PM Pacific.
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone, timedelta

# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

# Content bank IDs to upload (mapped from the original run IDs)
CB_IDS = [161, 157, 156, 159, 158, 149, 160, 154, 153, 150, 151, 148, 147]

PACIFIC_OFFSET = timedelta(hours=-7)  # PDT


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://orchestrator:orchestrator@localhost:5432/orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(db_url, pool_size=2, max_overflow=1)


async def wait_for_generation():
    """Wait until all content bank items are generated."""
    engine = _get_engine()
    while True:
        async with AsyncSession(engine) as s:
            id_list = ",".join(str(i) for i in CB_IDS)
            r = await s.execute(text(f"""
                SELECT cb.id, cb.status, cb.title, c.name
                FROM content_bank cb
                JOIN channels c ON c.id = cb.channel_id
                WHERE cb.id IN ({id_list})
            """))
            rows = r.fetchall()

        pending = []
        ready = []
        failed = []
        for cb_id, status, title, channel in rows:
            if status == "generated":
                ready.append((cb_id, title, channel))
            elif status in ("queued", "locked", "generating"):
                pending.append((cb_id, title, channel, status))
            elif status == "failed":
                failed.append((cb_id, title, channel))

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Ready: {len(ready)}, Pending: {len(pending)}, Failed: {len(failed)}")
        for cb_id, title, channel, status in pending:
            print(f"  {status:12} {channel}: {title[:60]}")

        if not pending:
            print(f"\nAll done! {len(ready)} ready, {len(failed)} failed")
            break

        await asyncio.sleep(30)
    await engine.dispose()
    return ready, failed


async def wait_for_publish_window():
    """Wait until 12:01 PM Pacific."""
    now_utc = datetime.now(timezone.utc)
    now_pacific = now_utc + PACIFIC_OFFSET

    # Target: 12:01 PM Pacific today (or tomorrow if already past)
    target_pacific = now_pacific.replace(hour=12, minute=1, second=0, microsecond=0)
    if now_pacific >= target_pacific:
        # Already past 12:01 PM Pacific today
        print("Already past 12:01 PM Pacific — uploading now")
        return

    target_utc = target_pacific - PACIFIC_OFFSET
    wait_seconds = (target_utc - now_utc).total_seconds()
    print(f"Waiting {wait_seconds/60:.0f} minutes until 12:01 PM Pacific...")
    await asyncio.sleep(wait_seconds)


async def upload_all(ready):
    """Upload all ready videos with staggered publish times."""
    from apps.publishing_service.uploader import upload_video

    engine = _get_engine()

    # Base publish time: 1-3 hours from now, rounded to nearest 5 minutes
    now_utc = datetime.now(timezone.utc)

    for i, (cb_id, title, channel) in enumerate(ready):
        async with AsyncSession(engine) as s:
            # Get run_id and video path
            r = await s.execute(text("""
                SELECT cb.run_id, c.id as channel_id
                FROM content_bank cb
                JOIN channels c ON c.id = cb.channel_id
                WHERE cb.id = :cbid
            """), {"cbid": cb_id})
            row = r.fetchone()
            if not row:
                print(f"  SKIP {title}: no run found")
                continue
            run_id, channel_id = row

            # Get video path
            r2 = await s.execute(text("""
                SELECT content FROM assets
                WHERE run_id = :rid AND (asset_type LIKE 'rendered%%')
                ORDER BY id DESC LIMIT 1
            """), {"rid": run_id})
            asset_row = r2.fetchone()
            if not asset_row:
                print(f"  SKIP {title}: no rendered asset")
                continue

            asset = json.loads(asset_row[0])
            video_path = asset.get("path")
            if not video_path or not os.path.exists(video_path):
                print(f"  SKIP {title}: video file not found at {video_path}")
                continue

            # Get metadata
            r3 = await s.execute(text("""
                SELECT content FROM assets
                WHERE run_id = :rid AND asset_type = 'publish_metadata'
                ORDER BY id DESC LIMIT 1
            """), {"rid": run_id})
            meta_row = r3.fetchone()
            meta = json.loads(meta_row[0]) if meta_row else {}

        # Derive token file
        token_name = channel.lower().replace(" ", "").replace("'", "").replace("\u2019", "")
        token_file = f"youtube_token_{token_name}.json"
        if not os.path.exists(token_file):
            print(f"  SKIP {title}: no token file {token_file}")
            continue

        # Schedule publish 1-3 hours from now, staggered
        publish_delay = random.randint(3600, 10800)
        publish_time = now_utc + timedelta(seconds=publish_delay + i * 300)  # 5 min stagger
        minute = (publish_time.minute // 5) * 5
        publish_time = publish_time.replace(minute=minute, second=0, microsecond=0)
        publish_at_iso = publish_time.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        description = meta.get("description", "")
        tags = meta.get("tags", [])

        print(f"  Uploading: {channel} — {title[:50]}... (publish at {publish_at_iso})")

        try:
            result = upload_video(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category="Entertainment",
                privacy_status="private",
                youtube_token_file=token_file,
                made_for_kids=False,
                publish_at=publish_at_iso,
            )

            if result.get("published"):
                print(f"    Uploaded! {result.get('url')} — publishes at {publish_at_iso}")
                # Update status
                async with AsyncSession(engine) as s:
                    await s.execute(text("UPDATE content_bank SET status = 'uploaded' WHERE id = :cbid"), {"cbid": cb_id})
                    await s.execute(text("UPDATE content_runs SET status = 'published' WHERE id = :rid"), {"rid": run_id})
                    await s.execute(text("""
                        INSERT INTO assets (run_id, channel_id, asset_type, content)
                        VALUES (:rid, :cid, 'publish_result', :content)
                    """), {"rid": run_id, "cid": channel_id,
                           "content": json.dumps({**result, "publish_at": publish_at_iso})})
                    await s.commit()
            else:
                print(f"    FAILED: {result}")
        except Exception as e:
            print(f"    ERROR: {e}")

    await engine.dispose()


async def main():
    print("=== Batch Upload Script ===")
    print(f"Waiting for {len(CB_IDS)} videos to finish generating...")

    ready, failed = await wait_for_generation()

    if failed:
        print(f"\n{len(failed)} videos failed generation:")
        for cb_id, title, channel in failed:
            print(f"  {channel}: {title}")

    if not ready:
        print("No videos ready to upload!")
        return

    await wait_for_publish_window()

    print(f"\nUploading {len(ready)} videos...")
    await upload_all(ready)
    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
