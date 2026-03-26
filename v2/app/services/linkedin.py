import httpx
from fastapi import HTTPException

from app.config import settings


def _require_apify_token():
    if not settings.apify_api_token:
        raise HTTPException(
            status_code=503,
            detail="Scraping requires APIFY_API_TOKEN to be configured",
        )


async def fetch_linkedin_posts(profile_url: str, max_posts: int = 50) -> list[dict]:
    _require_apify_token()
    actor_id = settings.apify_linkedin_actor_id
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            f"https://api.apify.com/v2/acts/{actor_id}/run-sync-get-dataset-items",
            params={"token": settings.apify_api_token},
            json={
                "limit": max_posts,
                "username": profile_url,
            },
        )
        resp.raise_for_status()
        return resp.json()


def score_linkedin_post(post: dict) -> dict:
    likes = post.get("numLikes", 0) or 0
    comments = post.get("numComments", 0) or 0
    shares = post.get("numShares", 0) or 0
    impressions = post.get("numImpressions", 0) or 1

    return {
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "impressions": impressions,
        "engagement_rate": (likes + comments + shares) / max(impressions, 1),
    }
