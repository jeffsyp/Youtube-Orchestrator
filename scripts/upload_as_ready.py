"""Watch for generated videos and upload each immediately.

Polls every 30s. Uploads to the correct channel with publish time
staggered 1-3 hours from upload, all after 12:01 PM Pacific.
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(line_buffering=True)

CB_IDS = [161, 157, 156, 159, 158, 149, 160, 154, 153, 150, 151, 148, 147]
PACIFIC_OFFSET = timedelta(hours=-7)  # PDT
uploaded = set()


def _get_engine():
    db_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/youtube_orchestrator")
    if "asyncpg" not in db_url:
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    return create_async_engine(db_url, pool_size=2, max_overflow=1)


def _publish_time():
    """Random publish time 1-3 hours from now, rounded to nearest 5 min."""
    now = datetime.now(timezone.utc)
    delay = random.randint(3600, 10800)
    t = now + timedelta(seconds=delay)
    t = t.replace(minute=(t.minute // 5) * 5, second=0, microsecond=0)
    return t.strftime("%Y-%m-%dT%H:%M:%S.000Z")


async def upload_one(cb_id, engine):
    """Upload a single generated video."""
    from apps.publishing_service.uploader import upload_video

    async with AsyncSession(engine) as s:
        r = await s.execute(text("""
            SELECT cb.run_id, cb.title, c.name, c.id as channel_id, cb.concept_json
            FROM content_bank cb
            JOIN channels c ON c.id = cb.channel_id
            WHERE cb.id = :cbid AND cb.status = 'generated'
        """), {"cbid": cb_id})
        row = r.fetchone()
        if not row:
            return False
        run_id, title, channel, channel_id, concept_json = row

        # Get video path
        r2 = await s.execute(text("""
            SELECT content FROM assets
            WHERE run_id = :rid AND (asset_type LIKE 'rendered%%')
            ORDER BY id DESC LIMIT 1
        """), {"rid": run_id})
        asset_row = r2.fetchone()

    if not asset_row:
        print(f"  SKIP {title[:50]}: no rendered asset")
        return False

    asset = json.loads(asset_row[0])
    video_path = asset.get("path")
    if not video_path or not os.path.exists(video_path):
        print(f"  SKIP {title[:50]}: file missing at {video_path}")
        return False

    # Get metadata
    async with AsyncSession(engine) as s:
        r3 = await s.execute(text("""
            SELECT content FROM assets WHERE run_id = :rid AND asset_type = 'publish_metadata'
            ORDER BY id DESC LIMIT 1
        """), {"rid": run_id})
        meta_row = r3.fetchone()
    meta = json.loads(meta_row[0]) if meta_row else {}

    # Token file
    token_name = channel.lower().replace(" ", "").replace("'", "").replace("\u2019", "")
    token_file = f"youtube_token_{token_name}.json"
    if not os.path.exists(token_file):
        print(f"  SKIP {title[:50]}: no token {token_file}")
        return False

    publish_at = _publish_time()
    description = meta.get("description", "")
    tags = meta.get("tags", [])
    thumbnail_path = meta.get("thumbnail_path")

    print(f"  Uploading: {channel} — {title[:50]}... (publish {publish_at})")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: upload_video(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category="Entertainment",
            privacy_status="private",
            youtube_token_file=token_file,
            made_for_kids=False,
            publish_at=publish_at,
            thumbnail_path=thumbnail_path,
        ))

        if result.get("published"):
            print(f"    OK! {result.get('url')} — publishes at {publish_at}")
            async with AsyncSession(engine) as s:
                await s.execute(text("UPDATE content_bank SET status = 'uploaded' WHERE id = :cbid"), {"cbid": cb_id})
                await s.execute(text("UPDATE content_runs SET status = 'published' WHERE id = :rid"), {"rid": run_id})
                await s.execute(text("""
                    INSERT INTO assets (run_id, channel_id, asset_type, content)
                    VALUES (:rid, :cid, 'publish_result', :content)
                """), {"rid": run_id, "cid": channel_id,
                       "content": json.dumps({**result, "publish_at": publish_at})})
                await s.commit()
            return True
        else:
            print(f"    FAILED: {result}")
            return False
    except Exception as e:
        print(f"    ERROR: {e}")
        return False


async def main():
    print("=== Upload As Ready ===")
    print(f"Watching {len(CB_IDS)} content bank items...")

    engine = _get_engine()

    while len(uploaded) < len(CB_IDS):
        async with AsyncSession(engine) as s:
            id_list = ",".join(str(i) for i in CB_IDS)
            r = await s.execute(text(f"""
                SELECT id, status, title FROM content_bank WHERE id IN ({id_list})
            """))
            rows = r.fetchall()

        generated = []
        pending = 0
        failed = 0
        for cb_id, status, title in rows:
            if cb_id in uploaded:
                continue
            if status == "generated":
                generated.append(cb_id)
            elif status in ("queued", "locked", "generating"):
                pending += 1
            elif status == "failed":
                failed += 1
                uploaded.add(cb_id)  # don't retry

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Uploaded: {len(uploaded)}, Ready: {len(generated)}, Pending: {pending}, Failed: {failed}")

        for cb_id in generated:
            ok = await upload_one(cb_id, engine)
            if ok:
                uploaded.add(cb_id)
            else:
                uploaded.add(cb_id)  # skip on error too

        if pending == 0 and not generated:
            break

        await asyncio.sleep(30)

    await engine.dispose()
    print(f"\nDone! Uploaded {len([x for x in uploaded])} videos.")


if __name__ == "__main__":
    asyncio.run(main())
