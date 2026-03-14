from pydantic import BaseModel


class PackagingPlan(BaseModel):
    title: str
    description: str
    tags: list[str]
    category: str = "Education"
    thumbnail_text: str
    srt_content: str
    asset_manifest: list[str]
    status: str = "ready"
