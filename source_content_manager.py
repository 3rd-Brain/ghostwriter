import requests
from typing import Literal, Dict, Union, List
import os
from openai import OpenAI
import uuid

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def tweet_to_source_content(tweets: List[Dict]) -> List[Dict]:
    """
    Process tweets by extracting text and generating embeddings, then uploading to AstraDB

    Args:
        tweets: List of tweet dictionaries containing 'text' field

    Returns:
        List of dictionaries containing text, embeddings, and upload response
    """
    print("\n=== Debug Tweet Processing ===")
    print(f"Number of tweets to process: {len(tweets)}")
    print(f"Sample tweet structure: {tweets[0] if tweets else 'No tweets'}")
    print(f"OpenAI API Key configured: {'Yes' if OPENAI_API_KEY else 'No'}")
    print("=== End Debug Section ===\n")
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured in environment")

    processed_tweets = []

    for tweet in tweets:
        # Skip retweets
        if tweet.get('isRetweet', False):
            continue
            
        # Extract text from tweet
        text = tweet.get('text', '')
        if not text:
            continue

        try:
            # Generate embedding using OpenAI
            response = openai_client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )

            # Extract embedding from response
            embedding = response.data[0].embedding

            # Get the current user's ID from environment
            user_id = os.environ.get("CURRENT_USER_ID")
            if not user_id:
                raise Exception("User ID not found in environment")

            # Generate a unique content ID
            content_id = str(uuid.uuid4())

            # Extract metrics from tweet
            likes = tweet.get('likes', 0)
            shares = tweet.get('retweets', 0)
            quotes = tweet.get('quotes', 0)
            bookmarks = tweet.get('bookmarks', 0)
            replies = tweet.get('replies', 0)
            impressions = tweet.get('impressions', 0)
            followers = tweet.get('followers', 0)
            
            # Calculate weighted metrics according to formulas
            # Use 1 as follower count if it's 0 to avoid division by zero
            follower_count = max(followers, 1)
            impression_follower_ratio = impressions / follower_count
            
            weighted_impressions = (impression_follower_ratio) * 0.15
            weighted_replies = (replies / max(impression_follower_ratio, 0.001)) * 0.25
            weighted_bookmarks = (bookmarks / max(impression_follower_ratio, 0.001)) * 0.25
            weighted_shares = (shares / max(impression_follower_ratio, 0.001)) * 0.15
            weighted_likes = (likes / max(impression_follower_ratio, 0.001)) * 0.2
            
            # Calculate overall score
            score = weighted_impressions + weighted_replies + weighted_bookmarks + weighted_shares + weighted_likes
            
            # Prepare document for upload
            document = {
                "content_id": content_id,
                "user_id": user_id,
                "content": text,
                "source": "Twitter",
                "channel_source": "Twitter",
                "$vector": embedding,
                "context": "NA",
                "metadata": {
                    "likes": likes,
                    "shares": shares,
                    "quotes": quotes,
                    "bookmarks": bookmarks,
                    "replies": replies,
                    "impressions": impressions,
                    "followers": followers,
                    "weighted_likes": weighted_likes,
                    "weighted_shares": weighted_shares,
                    "weighted_bookmarks": weighted_bookmarks,
                    "weighted_replies": weighted_replies,
                    "weighted_impressions": weighted_impressions,
                    "score": score
                }
            }

            # Prepare upload payload
            payload = {
                "insertOne": {
                    "document": document
                }
            }

            # Get AstraDB credentials
            ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
            ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

            if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
                raise Exception("AstraDB credentials not configured")

            # Construct URL for user's source content collection
            url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_source_content"

            # Set headers
            headers = {
                "Token": ASTRA_DB_APPLICATION_TOKEN,
                "Content-Type": "application/json"
            }

            # Upload to AstraDB
            upload_response = requests.post(url, headers=headers, json=payload)
            upload_response.raise_for_status()

            processed_tweets.append({
                'text': text,
                'embedding': embedding,
                'upload_response': upload_response.json()
            })

        except Exception as e:
            print(f"Failed to process tweet: {str(e)}")
            continue

    return processed_tweets

def gather_user_tweets(
    max_items: int,
    sort: Literal["Latest", "Top"],
    user_url: str
) -> Dict:
    """
    Gather tweets from a user's X/Twitter profile using Apify

    Args:
        max_items: Maximum number of tweets to retrieve
        sort: Sort order - "Latest" or "Top"
        user_url: Full URL of user's X/Twitter profile

    Returns:
        Dict containing the Twitter data response
    """
    print("\n=== Debug Tweet Gathering ===")
    print(f"Max items: {max_items}")
    print(f"Sort order: {sort}")
    print(f"User URL: {user_url}")
    print(f"Apify token configured: {'Yes' if os.environ.get('APIFY_API_TOKEN') else 'No'}")
    print("=== End Debug Section ===\n")
    APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN")

    if not APIFY_API_TOKEN:
        raise Exception("APIFY_API_TOKEN not configured in environment")

    # Apify endpoint
    url = "https://api.apify.com/v2/actor-tasks/james-3rdbrain~twitter-x-com-scraper-unlimited-ghostwriter/run-sync-get-dataset-items"

    # Request headers
    headers = {
        "Content-Type": "application/json"
    }

    # Request parameters
    params = {
        "token": APIFY_API_TOKEN
    }

    # Request payload
    payload = {
        "maxItems": max_items,
        "sort": sort,
        "startUrls": [user_url]
    }

    try:
        response = requests.post(url, headers=headers, params=params, json=payload)
        response.raise_for_status()
        result = response.json()
        print("\n=== Debug Apify Response ===")
        print(f"Response status: {response.status_code}")
        print(f"Response data sample: {str(result)[:200]}...")
        print("=== End Debug Section ===\n")
        return result
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to gather tweets: {str(e)}")
def count_user_documents(user_id: str) -> int:
    """
    Count documents for a specific user in AstraDB
    Args:
        user_id: String containing the user ID to count documents for
    Returns:
        Integer count of documents
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return 0
        
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_source_content"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "countDocuments": {
            "filter": {"user_id": user_id}
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        return result.get("status", {}).get("count", 0)
    except:
        return 0
