import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.common.repositories import get_db
from src.configuration.config import settings
from src.modules.auth.dtos.auth import TokenResponse, UserLogin, UserRegister, UserResponse
from src.modules.auth.entities.user_entity import UserEntity
from src.modules.auth.guards.jwt import get_current_user
from src.modules.auth.services.auth_service import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    AuthService,
    create_access_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nuevo usuario",
    description="Crea una nueva cuenta de usuario con username, email y contraseña.",
    responses={
        201: {
            "description": "Usuario registrado exitosamente",
        },
        400: {"description": "El usuario o email ya existe"},
        422: {"description": "Error de validación de datos"},
    },
)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Registra un nuevo usuario.

    - **username**: Nombre de usuario (3-255 caracteres)
    - **email**: Correo electrónico válido
    - **password**: Contraseña (mínimo 6 caracteres)
    """
    auth_service = AuthService(db)
    try:
        new_user = auth_service.register_user(user_data)
        return UserResponse(id=new_user.id, username=new_user.username, email=new_user.email)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Iniciar sesión",
    description="Autentica un usuario y devuelve un token JWT.",
    responses={
        200: {
            "description": "Login exitoso",
        },
        401: {"description": "Credenciales inválidas"},
        422: {"description": "Error de validación de datos"},
    },
)
async def login(request: Request, db: Session = Depends(get_db)):
    """
    Inicia sesión con username/email y contraseña.

    - **username**: Nombre de usuario o email
    - **password**: Contraseña

    Devuelve un token JWT que debe usarse en el header Authorization: Bearer <token>
    """
    import logging
    logger = logging.getLogger("uvicorn.error")
    
    try:
        # Intentar obtener el body parseado por FastAPI primero
        try:
            parsed_data = await request.json()
        except Exception:
            # Si FastAPI no pudo parsearlo, leer el body manualmente
            body = await request.body()
            if not body:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Body vacío"
                )
            
            body_str = body.decode("utf-8")
            cleaned = body_str.strip()
            
            # Si el body es un string JSON (viene como string literal con comillas), parsearlo
            if cleaned.startswith('"') and cleaned.endswith('"'):
                # Es un string JSON, parsearlo dos veces
                try:
                    unquoted = json.loads(cleaned)  # Primera pasada: quita las comillas externas
                    if isinstance(unquoted, str):
                        # Si sigue siendo string, parsearlo de nuevo
                        parsed_data = json.loads(unquoted)
                    else:
                        parsed_data = unquoted
                except (json.JSONDecodeError, ValueError):
                    # Si falla, intentar limpiar y parsear
                    try:
                        # Remover comillas y escapar caracteres
                        unquoted_str = cleaned[1:-1].replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r').replace('\\t', '\t')
                        parsed_data = json.loads(unquoted_str)
                    except (json.JSONDecodeError, ValueError):
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="El body no es un JSON válido"
                        )
            else:
                # Intentar parsear directamente como JSON
                try:
                    parsed_data = json.loads(cleaned)
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="El body no es un JSON válido"
                    )
        
        # Validar y crear el objeto UserLogin
        if not parsed_data or not isinstance(parsed_data, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El body debe ser un objeto JSON válido"
            )
        
        login_data = UserLogin(**parsed_data)
        logger.info(f"Intento de login para usuario: {login_data.username}")
        
        auth_service = AuthService(db)
        user = auth_service.authenticate_user(login_data)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales inválidas",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Crear token JWT
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id, "username": user.username}, expires_delta=access_token_expires
        )

        return TokenResponse(
            access_token=access_token, token_type="bearer", user_id=user.id, username=user.username
        )
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Error al parsear el JSON: {str(e)}"
        ) from e
    except Exception as e:
        import traceback
        logger.error(f"Error en login: {str(e)}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        # En modo debug, mostrar más detalles del error
        error_detail = str(e) if settings.DEBUG else "Error interno del servidor"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        ) from e


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener usuario actual",
    description="Obtiene la información del usuario autenticado.",
    responses={
        200: {
            "description": "Información del usuario",
        },
        401: {"description": "No autenticado"},
    },
)
def get_current_user_info(current_user: UserEntity = Depends(get_current_user)):
    """
    Obtiene la información del usuario autenticado.
    """
    return UserResponse(
        id=current_user.id, username=current_user.username, email=current_user.email
    )
