import httpx

from app.config import settings


async def fetch_tweets(profile_url: str, max_tweets: int = 50) -> list[dict]:
    handle = profile_url.rstrip("/").split("/")[-1].lstrip("@")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.apify.com/v2/acts/apidojo~tweet-scraper/runs",
            params={"token": settings.apify_api_token},
            json={
                "handles": [handle],
                "tweetsDesired": max_tweets,
                "proxyConfig": {"useApifyProxy": True},
            },
        )
        resp.raise_for_status()
        run_id = resp.json()["data"]["id"]

        resp = await client.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items",
            params={"token": settings.apify_api_token},
        )
        resp.raise_for_status()
        return resp.json()


def score_tweet(tweet: dict, follower_count: int) -> dict:
    likes = tweet.get("likeCount", 0)
    replies = tweet.get("replyCount", 0)
    retweets = tweet.get("retweetCount", 0)
    bookmarks = tweet.get("bookmarkCount", 0)
    impressions = tweet.get("viewCount", 0) or 1

    impression_ratio = impressions / max(follower_count, 1)

    return {
        "weighted_impressions": (impression_ratio) * 0.15,
        "weighted_replies": (replies / impression_ratio) * 0.25 if impression_ratio else 0,
        "weighted_bookmarks": (bookmarks / impression_ratio) * 0.25 if impression_ratio else 0,
        "weighted_retweets": (retweets / impression_ratio) * 0.15 if impression_ratio else 0,
        "weighted_likes": (likes / impression_ratio) * 0.20 if impression_ratio else 0,
        "likes": likes,
        "replies": replies,
        "retweets": retweets,
        "bookmarks": bookmarks,
        "impressions": impressions,
    }
