from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.services.user_service import UserService

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id_str = payload.get("sub")
        print(f"Debug JWT: payload = {payload}")
        print(f"Debug JWT: user_id_str = {user_id_str}, type = {type(user_id_str)}")
        if user_id_str is None:
            raise credentials_exception
        user_id = int(user_id_str)
        print(f"Debug JWT: user_id = {user_id}, type = {type(user_id)}")
    except (JWTError, ValueError, TypeError) as e:
        print(f"Debug JWT: Error decoding token = {e}")
        raise credentials_exception
    
    user_service = UserService(db)
    user = user_service.get_by_id(user_id)
    if user is None:
        print(f"Debug JWT: User not found for user_id = {user_id}")
        raise credentials_exception
    
    print(f"Debug JWT: Found user = {user.id}, {user.email}")
    
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "created_at": user.created_at
    }