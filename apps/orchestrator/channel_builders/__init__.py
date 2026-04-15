"""Per-channel custom video builders.

Each channel can have its own build pipeline that handles
image generation, animation, music, subtitles, etc.
"""

from apps.orchestrator.channel_builders.skeletorinio import build_skeletorinio
from apps.orchestrator.channel_builders.nature_receipts import build_nature_receipts
from apps.orchestrator.channel_builders.hardcore_ranked import build_hardcore_ranked
from apps.orchestrator.channel_builders.deep_we_go import build_deep_we_go
from apps.orchestrator.channel_builders.nightnight import build_nightnight
from apps.orchestrator.channel_builders.munchlax_lore import build_munchlax_lore
from apps.orchestrator.channel_builders.spookland import build_spookland
from apps.orchestrator.channel_builders.one_on_ones import build_one_on_ones
from apps.orchestrator.channel_builders.deity_drama import build_deity_drama
from apps.orchestrator.channel_builders.historic_ls import build_historic_ls
from apps.orchestrator.channel_builders.schmoney_facts import build_schmoney_facts

# Map channel IDs to their custom builder functions
CHANNEL_BUILDERS = {
    13: build_munchlax_lore,  # Munchlax Lore — POV Pokemon IRL
    18: build_skeletorinio,  # Skeletorinio — skeleton "What If" videos
    19: build_spookland,  # SpookLand — POV horror scenarios
    21: build_one_on_ones,  # One on Ones For Fun — cross-franchise battles
    # 22: Deity Drama — uses default meme pipeline (crude cartoon, no narration)
    25: build_nature_receipts,  # Nature Receipts — "What if [animal]" scenarios
    26: build_hardcore_ranked,  # Hardcore Ranked — visual comparison/ranking
    27: build_deep_we_go,  # Deep We Go — "What happens to your body" glass person
    28: build_nightnight,  # NightNightShorts — anime crossover "what if"
    30: build_historic_ls,  # Historic Ls — history's biggest fails
    31: build_schmoney_facts,  # Schmoney Facts — "What if you had X money"
}


def get_channel_builder(channel_id: int):
    """Return the custom builder for a channel, or None for default pipeline."""
    return CHANNEL_BUILDERS.get(channel_id)
