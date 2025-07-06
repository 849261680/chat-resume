from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.auth import UserCreate
from app.core.security import get_password_hash, verify_password

class UserService:
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_id(self, user_id: int) -> User:
        return self.db.query(User).filter(User.id == user_id).first()
    
    def get_by_email(self, email: str) -> User:
        return self.db.query(User).filter(User.email == email).first()
    
    def create(self, user_create: UserCreate) -> User:
        hashed_password = get_password_hash(user_create.password)
        user = User(
            email=user_create.email,
            hashed_password=hashed_password,
            full_name=user_create.full_name
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def authenticate(self, email: str, password: str) -> User:
        user = self.get_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user