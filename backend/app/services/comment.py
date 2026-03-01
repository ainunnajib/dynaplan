import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comment import Comment, CommentMention, CommentTargetType
from app.models.user import User


def extract_mentions(content: str) -> List[str]:
    """Parse @email patterns from text content. Returns list of email strings."""
    # Match @word@domain.tld style email mentions
    pattern = r"@([\w.+-]+@[\w.-]+\.[a-zA-Z]{2,})"
    return re.findall(pattern, content)


async def _get_users_by_emails(db: AsyncSession, emails: List[str]) -> List[User]:
    """Fetch users matching the given email list."""
    if not emails:
        return []
    result = await db.execute(
        select(User).where(User.email.in_(emails))
    )
    return list(result.scalars().all())


def _comment_to_response_dict(comment: Comment) -> dict:
    """Build a dict with flattened author info for schema construction."""
    return {
        "id": comment.id,
        "model_id": comment.model_id,
        "target_type": comment.target_type,
        "target_id": comment.target_id,
        "content": comment.content,
        "author_id": comment.author_id,
        "author_email": comment.author.email if comment.author else None,
        "author_name": comment.author.full_name if comment.author else None,
        "parent_id": comment.parent_id,
        "is_resolved": comment.is_resolved,
        "resolved_by": comment.resolved_by,
        "resolved_at": comment.resolved_at,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
        "mention_user_ids": [m.mentioned_user_id for m in (comment.mentions or [])],
    }


async def create_comment(
    db: AsyncSession,
    model_id: uuid.UUID,
    target_type: CommentTargetType,
    target_id: str,
    content: str,
    author_id: uuid.UUID,
    parent_id: Optional[uuid.UUID] = None,
) -> Comment:
    """Create a comment and persist any @mention records."""
    comment = Comment(
        model_id=model_id,
        target_type=target_type,
        target_id=target_id,
        content=content,
        author_id=author_id,
        parent_id=parent_id,
    )
    db.add(comment)
    await db.flush()  # get comment.id before creating mentions

    # Extract and persist @mentions
    mentioned_emails = extract_mentions(content)
    if mentioned_emails:
        mentioned_users = await _get_users_by_emails(db, mentioned_emails)
        for user in mentioned_users:
            mention = CommentMention(
                comment_id=comment.id,
                mentioned_user_id=user.id,
            )
            db.add(mention)

    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comment_by_id(
    db: AsyncSession, comment_id: uuid.UUID
) -> Optional[Comment]:
    """Fetch a single comment by its ID."""
    result = await db.execute(
        select(Comment).where(Comment.id == comment_id)
    )
    return result.scalar_one_or_none()


async def list_comments(
    db: AsyncSession,
    model_id: uuid.UUID,
    target_type: Optional[CommentTargetType] = None,
    target_id: Optional[str] = None,
) -> List[Comment]:
    """List comments for a model, optionally filtered by target_type and target_id."""
    query = select(Comment).where(Comment.model_id == model_id)
    if target_type is not None:
        query = query.where(Comment.target_type == target_type)
    if target_id is not None:
        query = query.where(Comment.target_id == target_id)
    query = query.order_by(Comment.created_at)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_comment_thread(
    db: AsyncSession, parent_id: uuid.UUID
) -> List[Comment]:
    """Get all direct replies to a comment, ordered by creation time."""
    result = await db.execute(
        select(Comment)
        .where(Comment.parent_id == parent_id)
        .order_by(Comment.created_at)
    )
    return list(result.scalars().all())


async def resolve_comment(
    db: AsyncSession, comment_id: uuid.UUID, user_id: uuid.UUID
) -> Optional[Comment]:
    """Mark a comment as resolved."""
    comment = await get_comment_by_id(db, comment_id)
    if comment is None:
        return None
    comment.is_resolved = True
    comment.resolved_by = user_id
    comment.resolved_at = datetime.now(tz=timezone.utc)
    await db.commit()
    await db.refresh(comment)
    return comment


async def unresolve_comment(
    db: AsyncSession, comment_id: uuid.UUID
) -> Optional[Comment]:
    """Unmark a resolved comment."""
    comment = await get_comment_by_id(db, comment_id)
    if comment is None:
        return None
    comment.is_resolved = False
    comment.resolved_by = None
    comment.resolved_at = None
    await db.commit()
    await db.refresh(comment)
    return comment


async def delete_comment(db: AsyncSession, comment: Comment) -> None:
    """Hard-delete a comment (cascades mentions)."""
    await db.delete(comment)
    await db.commit()


async def get_mentions_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> List[Comment]:
    """Get all comments that mention the given user."""
    result = await db.execute(
        select(Comment)
        .join(CommentMention, CommentMention.comment_id == Comment.id)
        .where(CommentMention.mentioned_user_id == user_id)
        .order_by(Comment.created_at)
    )
    return list(result.scalars().all())
