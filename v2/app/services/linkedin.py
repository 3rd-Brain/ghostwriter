import httpx

from app.config import settings


async def fetch_linkedin_posts(profile_url: str, max_posts: int = 50) -> list[dict]:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            "https://api.apify.com/v2/actor-tasks/james-3rdbrain~ghostwriter-linkedin-posts-scraper/run-sync-get-dataset-items",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {settings.apify_api_token}",
            },
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
