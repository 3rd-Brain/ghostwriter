import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth import get_current_account
from app.models.account import Account
from app.models.source_content import SourceContent
from app.schemas.source_content import (
    SourceContentCreate, SourceContentResponse,
    SourceContentBatchRequest,
    SourceContentSearchRequest, SourceContentSearchResponse,
    TwitterImportRequest, TwitterImportResponse,
)
from app.services.embeddings import generate_embedding
from app.services.documents import extract_text, chunk_text
from app.services.twitter import fetch_tweets, score_tweet

router = APIRouter(prefix="/source-content", tags=["source-content"])


@router.post("", response_model=SourceContentResponse, status_code=201)
async def create_source_content(
    body: SourceContentCreate,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    embedding = await generate_embedding(body.content)
    sc = SourceContent(
        account_id=account.id,
        content=body.content,
        source=body.source,
        channel_source=body.channel_source,
        embedding=embedding,
        metadata_=body.metadata,
    )
    db.add(sc)
    await db.commit()
    await db.refresh(sc)
    return sc


@router.post("/batch", response_model=list[SourceContentResponse], status_code=201)
async def batch_import(
    body: SourceContentBatchRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for item in body.items:
        embedding = await generate_embedding(item.content)
        sc = SourceContent(
            account_id=account.id,
            content=item.content,
            source=item.source,
            channel_source=item.channel_source,
            embedding=embedding,
            metadata_=item.metadata,
        )
        db.add(sc)
        results.append(sc)
    await db.commit()
    for sc in results:
        await db.refresh(sc)
    return results


@router.post("/upload", response_model=list[SourceContentResponse], status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    text = extract_text(file_bytes, file.filename)
    chunks = chunk_text(text)

    results = []
    for chunk in chunks:
        embedding = await generate_embedding(chunk)
        sc = SourceContent(
            account_id=account.id,
            content=chunk,
            source=file.filename,
            channel_source=file.filename.rsplit(".", 1)[-1].upper(),
            embedding=embedding,
        )
        db.add(sc)
        results.append(sc)
    await db.commit()
    for sc in results:
        await db.refresh(sc)
    return results


@router.post("/import-twitter", response_model=TwitterImportResponse, status_code=201)
async def import_twitter(
    body: TwitterImportRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    tweets = await fetch_tweets(body.profile_url, body.max_tweets)
    follower_count = tweets[0].get("author", {}).get("followers", 1) if tweets else 1

    results = []
    for tweet in tweets:
        if tweet.get("isRetweet"):
            continue
        text = tweet.get("fullText") or tweet.get("text", "")
        if not text:
            continue

        metrics = score_tweet(tweet, follower_count)
        metrics["total_weight_metric"] = sum(
            v for k, v in metrics.items() if k.startswith("weighted_")
        )

        embedding = await generate_embedding(text)
        sc = SourceContent(
            account_id=account.id,
            content=text,
            source="Twitter",
            channel_source="Twitter",
            embedding=embedding,
            metadata_=metrics,
        )
        db.add(sc)
        results.append(sc)

    await db.commit()
    for sc in results:
        await db.refresh(sc)
    return TwitterImportResponse(imported_count=len(results), items=results)


@router.get("", response_model=list[SourceContentResponse])
async def list_source_content(
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SourceContent).where(SourceContent.account_id == account.id)
    )
    return result.scalars().all()


@router.post("/search", response_model=SourceContentSearchResponse)
async def search_source_content(
    body: SourceContentSearchRequest,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    query_embedding = await generate_embedding(body.query)
    stmt = (
        select(SourceContent)
        .where(SourceContent.account_id == account.id)
        .order_by(SourceContent.embedding.cosine_distance(query_embedding))
        .limit(body.limit)
    )
    result = await db.execute(stmt)
    return SourceContentSearchResponse(results=list(result.scalars().all()))


@router.delete("/{content_id}", status_code=204)
async def delete_source_content(
    content_id: uuid.UUID,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    sc = await db.get(SourceContent, content_id)
    if not sc or sc.account_id != account.id:
        raise HTTPException(status_code=404, detail="Source content not found")
    await db.delete(sc)
    await db.commit()
