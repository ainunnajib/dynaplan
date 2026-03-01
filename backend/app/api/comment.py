import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.comment import CommentTargetType
from app.models.user import User
from app.schemas.comment import (
    CommentCreate,
    CommentWithMentionsResponse,
)
from app.services.comment import (
    create_comment,
    delete_comment,
    get_comment_by_id,
    get_comment_thread,
    get_mentions_for_user,
    list_comments,
    resolve_comment,
    unresolve_comment,
    _comment_to_response_dict,
)

router = APIRouter(tags=["comments"])


def _build_response(comment) -> CommentWithMentionsResponse:
    """Convert a Comment ORM object to the response schema."""
    return CommentWithMentionsResponse(**_comment_to_response_dict(comment))


async def _get_comment_or_404(
    comment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> object:
    comment = await get_comment_by_id(db, comment_id)
    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    return comment


@router.post(
    "/models/{model_id}/comments",
    response_model=CommentWithMentionsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_comment_endpoint(
    model_id: uuid.UUID,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new comment on a model target (module, line_item, or cell)."""
    comment = await create_comment(
        db=db,
        model_id=model_id,
        target_type=data.target_type,
        target_id=data.target_id,
        content=data.content,
        author_id=current_user.id,
        parent_id=data.parent_id,
    )
    return _build_response(comment)


@router.get(
    "/models/{model_id}/comments",
    response_model=List[CommentWithMentionsResponse],
)
async def list_comments_endpoint(
    model_id: uuid.UUID,
    target_type: Optional[CommentTargetType] = Query(default=None),
    target_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List comments for a model, optionally filtered by target_type and target_id."""
    comments = await list_comments(
        db=db,
        model_id=model_id,
        target_type=target_type,
        target_id=target_id,
    )
    return [_build_response(c) for c in comments]


@router.get(
    "/comments/{comment_id}/thread",
    response_model=List[CommentWithMentionsResponse],
)
async def get_thread_endpoint(
    comment=Depends(_get_comment_or_404),
    db: AsyncSession = Depends(get_db),
):
    """Get all replies to a comment."""
    replies = await get_comment_thread(db=db, parent_id=comment.id)
    return [_build_response(r) for r in replies]


@router.post(
    "/comments/{comment_id}/resolve",
    response_model=CommentWithMentionsResponse,
)
async def resolve_comment_endpoint(
    comment=Depends(_get_comment_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a comment as resolved."""
    updated = await resolve_comment(db=db, comment_id=comment.id, user_id=current_user.id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    return _build_response(updated)


@router.post(
    "/comments/{comment_id}/unresolve",
    response_model=CommentWithMentionsResponse,
)
async def unresolve_comment_endpoint(
    comment=Depends(_get_comment_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Unmark a resolved comment."""
    updated = await unresolve_comment(db=db, comment_id=comment.id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found",
        )
    return _build_response(updated)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_comment_endpoint(
    comment=Depends(_get_comment_or_404),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a comment. Only the author may delete their own comment."""
    if comment.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the comment author can delete this comment",
        )
    await delete_comment(db=db, comment=comment)


@router.get(
    "/me/mentions",
    response_model=List[CommentWithMentionsResponse],
)
async def get_my_mentions_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all comments that mention the current user."""
    comments = await get_mentions_for_user(db=db, user_id=current_user.id)
    return [_build_response(c) for c in comments]
