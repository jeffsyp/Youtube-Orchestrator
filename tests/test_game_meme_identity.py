from packages.utils.game_meme_identity import normalize_game_meme_concept


def test_league_concepts_get_summoners_rift_identity_cues():
    concept = {
        "title": "THE LEAGUE JUNGLER WHO FINALLY SHOWED UP TO YOUR LANE",
        "brief": "Jungler ganks your lane for the first time all game and steals the kill",
        "art_style": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic.",
        "scenes": [
            {
                "image_prompt": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic. Close-up of a crude cartoon League of Legends mid laner with desperate wide eyes, a doodled health bar almost empty above their head, pointing urgently off-screen. One character only. NO text anywhere.",
                "video_prompt": "Mid laner frantically waves and screams JUNG COME JUNG COME HES LOW.",
            },
            {
                "image_prompt": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic. Close-up of a crude cartoon jungler character with a giant grin, holding a glowing doodled kill notification trophy, eyes sparkling. One character only. NO text anywhere.",
                "video_prompt": "Jungler pumps his fist and yells LETS GO nice gank bro, claiming the kill like he did all the work.",
            },
            {
                "image_prompt": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic. Close-up of the mid laner again, jaw on the floor, a doodled recall animation spinning above the jungler who is already leaving. One character only. NO text anywhere.",
                "video_prompt": "Mid laner whispers he took it and recalled.",
            },
        ],
    }

    normalized = normalize_game_meme_concept(concept, channel_id=16)
    scenes = normalized["scenes"]

    assert "summoner's rift" in scenes[0]["image_prompt"].lower()
    assert "minimap" in scenes[0]["image_prompt"].lower()
    assert "jungle" in scenes[1]["image_prompt"].lower()
    assert "kill-feed" in scenes[1]["image_prompt"].lower()
    assert "trophy" not in scenes[1]["image_prompt"].lower()
    assert "turret" in scenes[2]["image_prompt"].lower()
    assert "recall ring" in scenes[2]["image_prompt"].lower()
    assert "summoner's rift" in normalized["art_style"].lower()


def test_league_jungler_kill_steal_recall_gets_clear_story_beats():
    concept = {
        "title": "THE LEAGUE JUNGLER WHO FINALLY SHOWED UP TO YOUR LANE",
        "brief": "Jungler ganks your lane for the first time all game — steals the kill and immediately recalls",
        "art_style": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic.",
        "scenes": [
            {
                "image_prompt": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic. Close-up of a crude cartoon League of Legends mid laner with desperate wide eyes. One character only. NO text anywhere.",
                "video_prompt": "Mid laner frantically waves and screams JUNG COME JUNG COME HES LOW.",
            },
            {
                "image_prompt": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic. Close-up of a crude cartoon jungler character with a giant grin. One character only. NO text anywhere.",
                "video_prompt": "Jungler pumps his fist and yells LETS GO nice gank bro.",
            },
            {
                "image_prompt": "Simple crude cartoon with thick wobbly outlines and flat colors, like a funny doodle comic. Close-up of the mid laner again. One character only. NO text anywhere.",
                "video_prompt": "Mid laner whispers he took it and recalled.",
            },
        ],
    }

    normalized = normalize_game_meme_concept(concept, channel_id=16)
    scenes = normalized["scenes"]

    assert "jung, come mid, he's one, hurry" in scenes[0]["video_prompt"].lower()
    assert "river brush" in scenes[0]["image_prompt"].lower()
    assert "kill-feed" in scenes[1]["image_prompt"].lower()
    assert "last hit" in scenes[1]["video_prompt"].lower()
    assert "wait, you took it and recalled?" in scenes[2]["video_prompt"].lower()
    assert "background characters allowed as silent silhouettes" in scenes[2]["image_prompt"].lower()
