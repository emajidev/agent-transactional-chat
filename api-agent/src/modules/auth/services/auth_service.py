from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.configuration.config import settings
from src.modules.auth.dtos.auth import UserLogin, UserRegister
from src.modules.auth.entities.user_entity import UserEntity

# Configuración de JWT
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 días


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Genera el hash de la contraseña."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
    else:
        return payload


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def register_user(self, user_data: UserRegister) -> UserEntity:
        """Registra un nuevo usuario."""
        # Verificar si el usuario ya existe
        existing_user = (
            self.db.query(UserEntity)
            .filter(
                or_(UserEntity.username == user_data.username, UserEntity.email == user_data.email)
            )
            .first()
        )

        if existing_user:
            if existing_user.username == user_data.username:
                raise ValueError("El nombre de usuario ya está en uso")
            if existing_user.email == user_data.email:
                raise ValueError("El correo electrónico ya está en uso")

        # Crear nuevo usuario
        hashed_password = get_password_hash(user_data.password)
        new_user = UserEntity(
            username=user_data.username, email=user_data.email, hashed_password=hashed_password
        )

        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)

        return new_user

    def authenticate_user(self, login_data: UserLogin) -> UserEntity | None:
        """Autentica un usuario con username/email y contraseña."""
        # Buscar usuario por username o email
        user = (
            self.db.query(UserEntity)
            .filter(
                or_(
                    UserEntity.username == login_data.username,
                    UserEntity.email == login_data.username,
                )
            )
            .first()
        )

        if not user:
            return None

        if not verify_password(login_data.password, user.hashed_password):
            return None

        return user

    def get_user_by_id(self, user_id: int) -> UserEntity | None:
        """Obtiene un usuario por su ID."""
        return self.db.query(UserEntity).filter(UserEntity.id == user_id).first()
