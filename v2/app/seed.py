"""Seed system templates and workflows on first startup."""

import json
import logging
from pathlib import Path

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template, TemplateCategory
from app.models.workflow import Workflow
from app.services.embeddings import generate_embedding

logger = logging.getLogger("ghostwriter.seed")

SEED_TEMPLATES_FILE = Path(__file__).parent.parent / "scripts" / "seed_templates.json"
SEED_WORKFLOWS_FILE = Path(__file__).parent.parent / "scripts" / "seed_workflows.json"

CATEGORY_MAP = {
    "short_form": TemplateCategory.short_form,
    "atomic": TemplateCategory.atomic,
    "mid_form": TemplateCategory.mid_form,
}


async def seed_templates(db: AsyncSession) -> None:
    """Load seed templates if the templates table is empty."""
    count = (await db.execute(
        select(func.count()).select_from(Template).where(Template.account_id.is_(None))
    )).scalar()

    if count > 0:
        logger.info(f"Skipping seed — {count} system templates already exist")
        return

    if not SEED_TEMPLATES_FILE.exists():
        logger.warning(f"Seed file not found: {SEED_TEMPLATES_FILE}")
        return

    with open(SEED_TEMPLATES_FILE, "r", encoding="utf-8") as f:
        templates = json.load(f)

    logger.info(f"Seeding {len(templates)} system templates (this may take a few minutes on first run)...")

    for i, t in enumerate(templates, 1):
        category = CATEGORY_MAP.get(t["category"], TemplateCategory.short_form)
        content = t["content"]
        description = t.get("description", "")

        try:
            embed_text = f"{content}\n{description}" if description else content
            embedding = await generate_embedding(embed_text)
        except Exception as e:
            logger.warning(f"  [{i}/{len(templates)}] Embedding failed, skipping: {e}")
            continue

        template = Template(
            account_id=None,
            content=content,
            description=description,
            category=category,
            embedding=embedding,
        )
        db.add(template)

        if i % 25 == 0:
            await db.flush()
            logger.info(f"  [{i}/{len(templates)}] seeded...")

    await db.commit()
    logger.info(f"Seed complete — {len(templates)} system templates loaded")


async def seed_workflows(db: AsyncSession) -> None:
    """Load seed workflows if no system workflows exist."""
    count = (await db.execute(
        select(func.count()).select_from(Workflow).where(Workflow.account_id.is_(None))
    )).scalar()

    if count > 0:
        logger.info(f"Skipping seed — {count} system workflows already exist")
        return

    if not SEED_WORKFLOWS_FILE.exists():
        logger.warning(f"Seed file not found: {SEED_WORKFLOWS_FILE}")
        return

    with open(SEED_WORKFLOWS_FILE, "r", encoding="utf-8") as f:
        workflows = json.load(f)

    logger.info(f"Seeding {len(workflows)} system workflows...")

    for wf in workflows:
        workflow = Workflow(
            account_id=None,
            name=wf["name"],
            description=wf.get("description", ""),
            steps=wf["steps"],
        )
        db.add(workflow)

    await db.commit()
    logger.info(f"Seed complete — {len(workflows)} system workflows loaded")
