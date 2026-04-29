from packages.utils.hardcore_ranked_language import hardcore_ranked_pitch_rejection_reason


def test_rejects_precision_dependent_ballistic_liquid_pitch():
    pitch = {
        "title": "EVERY LIQUID RANKED BY HOW LONG IT TAKES TO STOP A BULLET",
        "brief": "Same bullet, same tank, same gun, but which liquid stops it fastest?",
        "structure": "Use the same rig every time and compare how many inches it takes before the bullet stops.",
        "key_facts": "Water takes three feet, concrete slurry takes eight inches, and mercury takes six inches.",
    }

    reason = hardcore_ranked_pitch_rejection_reason(pitch, channel_id=26)

    assert reason is not None
    assert "precision" in reason or "tiny" in reason


def test_allows_big_legible_hardcore_ranked_survival_pitch():
    pitch = {
        "title": "EVERY MACHINE RANKED BY HOW FAR IT GETS TO THE CENTER OF THE EARTH",
        "brief": "You try bigger and bigger machines to see which one reaches the deepest before melting or breaking apart.",
        "structure": "Shovel fails instantly, a drill gets deeper, a mega-bore reaches magma, and the final rig actually survives long enough to matter.",
        "key_facts": "Each upgrade earns a visibly deeper checkpoint before heat destroys it.",
    }

    reason = hardcore_ranked_pitch_rejection_reason(pitch, channel_id=26)

    assert reason is None
