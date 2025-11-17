from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.repositories import get_db
from src.configuration.config import settings
from src.modules.auth.entities.user_entity import UserEntity
from src.modules.auth.guards.jwt import get_current_user
from src.modules.conversations.dtos.conversation import (
    ChatMessage,
    ChatResponse,
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
)
from src.modules.conversations.services.conversations_service import ConversationsService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post(
    "/",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    description="Creates a new conversation. user_id is required and status defaults to 'active'.",
    responses={
        201: {
            "description": "Conversation created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "user_id": "user_123",
                        "started_at": "2024-01-15T10:30:00",
                        "ended_at": None,
                        "status": "active",
                        "created_at": "2024-01-15T10:30:00",
                        "updated_at": None,
                    }
                }
            },
        },
        401: {"description": "No autenticado"},
        422: {"description": "Data validation error"},
    },
)
def create_conversation(
    conversation: ConversationCreate,
    db: Session = Depends(get_db),
    _current_user: UserEntity = Depends(get_current_user),
):
    """
    Create a new conversation.

    - **user_id**: User ID (required, 1-255 characters)
    - **status**: Conversation status - 'active', 'completed' or 'abandoned' (optional, defaults to 'active')
    """
    service = ConversationsService(db)
    return service.create_conversation(conversation)


@router.get(
    "/",
    response_model=list[ConversationResponse],
    summary="Get all conversations",
    description="Gets a paginated list of all conversations. Uses 'skip' and 'limit' parameters for pagination.",
    responses={
        200: {
            "description": "List of conversations retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 1,
                            "user_id": "user_123",
                            "started_at": "2024-01-15T10:30:00",
                            "ended_at": None,
                            "status": "active",
                            "created_at": "2024-01-15T10:30:00",
                            "updated_at": None,
                        }
                    ]
                }
            },
        }
    },
)
def get_conversations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _current_user: UserEntity = Depends(get_current_user),
):
    """
    Get all conversations with pagination.

    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 100)
    """
    service = ConversationsService(db)
    return service.get_conversations(skip=skip, limit=limit)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get a conversation by ID",
    description="Gets the details of a specific conversation by its ID.",
    responses={
        200: {
            "description": "Conversation found",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "user_id": "user_123",
                        "started_at": "2024-01-15T10:30:00",
                        "ended_at": None,
                        "status": "active",
                        "created_at": "2024-01-15T10:30:00",
                        "updated_at": None,
                    }
                }
            },
        },
        401: {"description": "No autenticado"},
        404: {"description": "Conversation not found"},
    },
)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    _current_user: UserEntity = Depends(get_current_user),
):
    """
    Get a specific conversation by its ID.

    - **conversation_id**: Unique ID of the conversation to find
    """
    service = ConversationsService(db)
    conversation = service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found",
        )
    return conversation


@router.put(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Update a conversation",
    description="Updates an existing conversation. All fields are optional, only provided fields will be updated.",
    responses={
        200: {
            "description": "Conversation updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1,
                        "user_id": "user_123",
                        "started_at": "2024-01-15T10:30:00",
                        "ended_at": "2024-01-15T11:00:00",
                        "status": "completed",
                        "created_at": "2024-01-15T10:30:00",
                        "updated_at": "2024-01-15T11:00:00",
                    }
                }
            },
        },
        404: {"description": "Conversation not found"},
        422: {"description": "Data validation error"},
    },
)
def update_conversation(
    conversation_id: int,
    conversation: ConversationUpdate,
    db: Session = Depends(get_db),
    _current_user: UserEntity = Depends(get_current_user),
):
    """
    Update an existing conversation.

    - **conversation_id**: Unique ID of the conversation to update
    - **user_id**: New user ID (optional)
    - **started_at**: New start date (optional)
    - **ended_at**: New end date (optional)
    - **status**: New conversation status (optional)
    """
    service = ConversationsService(db)
    updated_conversation = service.update_conversation(conversation_id, conversation)
    if not updated_conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with ID {conversation_id} not found",
        )
    return updated_conversation


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Send a chat message",
    description="Sends a chat message. If conversation_id is not provided, a new conversation is created. If provided, the existing conversation is updated.",
    responses={
        200: {
            "description": "Message processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "conversation_id": 1,
                        "response": "I received your message: 'Hello'. I'm processing your request.",
                        "status": "active",
                    }
                }
            },
        },
        401: {"description": "No autenticado"},
        422: {"description": "Data validation error"},
    },
)
def chat(
    chat_message: ChatMessage,
    db: Session = Depends(get_db),
    current_user: UserEntity = Depends(get_current_user),
):
    """
    Send a chat message.

    - **message**: Chat message (required, 1-1000 characters)
    - **conversation_id**: Conversation ID (optional, a new one will be created if not provided)

    If conversation_id is not provided, a new conversation is created with status 'active'.
    If conversation_id is provided and the conversation exists, it is updated.
    If the conversation was completed or abandoned, it is reactivated.
    """
    service = ConversationsService(db, settings.OPENAI_API_KEY)
    user_id = str(current_user.id)
    return service.process_chat_message(chat_message, user_id)
