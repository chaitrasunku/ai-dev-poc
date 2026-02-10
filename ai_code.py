import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import redis.asyncio as redis
import sqlalchemy
from fastapi import Depends, FastAPI, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from sqlalchemy.exc import OperationalError, SQLAlchemyError

# --- 1. Configuration ---

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://petstore_user:petstore_password@localhost:5432/petstore_db"
    SECRET_KEY: str = "super-secret-key-CHANGE-ME-IN-PROD"  # Replace with a strong, random key in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    LOG_LEVEL: str = "INFO"

settings = Settings()

# --- 2. Logging Setup ---

logger = logging.getLogger("petstore_api")
logger.setLevel(settings.LOG_LEVEL)

if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)

console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# --- 3. Database Setup ---

MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 5

engine = None
SessionLocal = None
Base = declarative_base()

def initialize_database():
    """Initializes the database engine and session factory with retries."""
    global engine, SessionLocal
    if engine is not None and SessionLocal is not None:
        return

    for i in range(MAX_RETRIES):
        try:
            logger.info(f"Attempting to connect to database... (Attempt {i+1}/{MAX_RETRIES})")
            engine = create_engine(
                settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20
            )
            with engine.connect() as connection:
                connection.execute(sqlalchemy.text("SELECT 1")) # Test connection
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            logger.info("Database connection established successfully.")
            return
        except OperationalError as e:
            logger.warning(f"Database connection failed: {e}")
            if i < MAX_RETRIES - 1:
                logger.info(f"Retrying in {RETRY_DELAY_SECONDS} seconds...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.critical("Failed to connect to the database after multiple retries. Exiting.")
                raise
        except Exception as e:
            logger.critical(f"An unexpected error occurred during database connection: {e}")
            raise

def get_db():
    """Dependency to get a database session."""
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call initialize_database() first.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables(db_engine):
    """Creates database tables based on SQLAlchemy models."""
    logger.info("Creating database tables if they don't exist...")
    Base.metadata.create_all(bind=db_engine)
    logger.info("Database tables creation complete.")

# --- 4. Security ---

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="user/login")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

TOKEN_BLACKLIST = set()

def invalidate_token(token: str):
    TOKEN_BLACKLIST.add(token)

def is_token_blacklisted(token: str) -> bool:
    return token in TOKEN_BLACKLIST

# --- 5. SQLAlchemy Models ---

class PetStatus(str, Enum):
    available = "available"
    pending = "pending"
    sold = "sold"

class OrderStatus(str, Enum):
    placed = "placed"
    approved = "approved"
    delivered = "delivered"

class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    category = Column(String, index=True)
    photoUrls = Column(String)
    tags = Column(String)
    status = Column(Enum(PetStatus), default=PetStatus.available, nullable=False)

    orders = relationship("Order", back_populates="pet")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    firstName = Column(String)
    lastName = Column(String)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    phone = Column(String)
    userStatus = Column(Integer, default=0)

    orders = relationship("Order", back_populates="user")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    quantity = Column(Integer, nullable=False)
    shipDate = Column(DateTime)
    status = Column(Enum(OrderStatus), default=OrderStatus.placed, nullable=False)
    complete = Column(Boolean, default=False)

    pet = relationship("Pet", back_populates="orders")
    user = relationship("User", back_populates="orders")

# --- 6. Pydantic Schemas ---

class PetBase(BaseModel):
    name: str = Field(..., example="doggie")
    category: Optional[str] = Field(None, example="Dogs")
    photoUrls: List[str] = Field([], example=["http://example.com/photo1.jpg"])
    tags: List[str] = Field([], example=["cute", "friendly"])
    status: PetStatus = Field(PetStatus.available, example="available")

class PetCreate(PetBase):
    pass

class PetUpdate(PetBase):
    id: int = Field(..., example=1)

class PetResponse(PetBase):
    id: int

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj: Pet):
        # Handle string to list conversion for photoUrls and tags
        obj.photoUrls = obj.photoUrls.split(',') if obj.photoUrls else []
        obj.tags = obj.tags.split(',') if obj.tags else []
        return super().model_validate(obj)

class OrderBase(BaseModel):
    pet_id: int = Field(..., example=1)
    quantity: int = Field(..., gt=0, example=1)
    shipDate: Optional[datetime] = Field(None, example="2023-10-27T10:00:00Z")
    status: OrderStatus = Field(OrderStatus.placed, example="placed")
    complete: bool = Field(False, example=False)

class OrderCreate(OrderBase):
    pass

class OrderResponse(OrderBase):
    id: int
    user_id: Optional[int] = None

    model_config = {"from_attributes": True}

class InventoryResponse(BaseModel):
    available: int = Field(..., example=10)
    pending: int = Field(..., example=5)
    sold: int = Field(..., example=2)

class UserBase(BaseModel):
    username: str = Field(..., example="theuser")
    firstName: Optional[str] = Field(None, example="John")
    lastName: Optional[str] = Field(None, example="Doe")
    email: EmailStr = Field(..., example="john.doe@example.com")
    phone: Optional[str] = Field(None, example="123-456-7890")
    userStatus: Optional[int] = Field(0, example=0)

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, example="password123")

class UserLogin(BaseModel):
    username: str = Field(..., example="theuser")
    password: str = Field(..., example="password123")

class UserResponse(UserBase):
    id: int

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    username: Optional[str] = None

# --- 7. Services (CRUD Logic) ---

class PetService:
    def get_pet(self, db: Session, pet_id: int) -> Optional[Pet]:
        return db.query(Pet).filter(Pet.id == pet_id).first()

    def create_pet(self, db: Session, pet: PetCreate) -> Pet:
        db_pet = Pet(
            name=pet.name,
            category=pet.category,
            photoUrls=",".join(pet.photoUrls) if pet.photoUrls else None,
            tags=",".join(pet.tags) if pet.tags else None,
            status=pet.status,
        )
        db.add(db_pet)
        db.commit()
        db.refresh(db_pet)
        return db_pet

    def update_pet(self, db: Session, pet_id: int, pet: PetUpdate) -> Optional[Pet]:
        db_pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if db_pet:
            for field, value in pet.model_dump(exclude_unset=True).items():
                if field in ["photoUrls", "tags"]:
                    setattr(db_pet, field, ",".join(value) if value else None)
                else:
                    setattr(db_pet, field, value)
            db.commit()
            db.refresh(db_pet)
        return db_pet

    def delete_pet(self, db: Session, pet_id: int) -> bool:
        db_pet = db.query(Pet).filter(Pet.id == pet_id).first()
        if db_pet:
            db.delete(db_pet)
            db.commit()
            return True
        return False

class OrderService:
    def place_order(self, db: Session, order: OrderCreate, user_id: Optional[int] = None) -> Order:
        db_pet = db.query(Pet).filter(Pet.id == order.pet_id).first()
        if not db_pet:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
        
        if db_pet.status == PetStatus.available:
            db_pet.status = PetStatus.pending
            db.add(db_pet)

        db_order = Order(
            pet_id=order.pet_id,
            user_id=user_id,
            quantity=order.quantity,
            shipDate=order.shipDate if order.shipDate else datetime.utcnow(),
            status=order.status,
            complete=order.complete,
        )
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        return db_order

    def get_order(self, db: Session, order_id: int) -> Optional[Order]:
        return db.query(Order).filter(Order.id == order_id).first()

    def get_inventory(self, db: Session) -> InventoryResponse:
        available_count = db.query(Pet).filter(Pet.status == PetStatus.available).count()
        pending_count = db.query(Pet).filter(Pet.status == PetStatus.pending).count()
        sold_count = db.query(Pet).filter(Pet.status == PetStatus.sold).count()
        return InventoryResponse(available=available_count, pending=pending_count, sold=sold_count)

class UserService:
    def get_user_by_username(self, db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    def create_user(self, db: Session, user: UserCreate) -> User:
        hashed_password = get_password_hash(user.password)
        db_user = User(
            username=user.username,
            firstName=user.firstName,
            lastName=user.lastName,
            email=user.email,
            password_hash=hashed_password,
            phone=user.phone,
            userStatus=user.userStatus,
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    def authenticate_user(self, db: Session, user_login: UserLogin) -> Optional[User]:
        user = self.get_user_by_username(db, user_login.username)
        if not user or not verify_password(user_login.password, user.password_hash):
            return None
        return user

pet_service = PetService()
order_service = OrderService()
user_service = UserService()

# --- 8. FastAPI Application ---

app = FastAPI(
    title="Petstore API",
    description="This is a sample Petstore server based on the OpenAPI 3.0 specification.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# --- 9. Dependencies for current user ---

async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been invalidated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token_data = TokenData(username=username)
    user = user_service.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    request.state.access_token = token 
    
    return user

# --- 10. Event Handlers ---

@app.on_startup
async def startup_event():
    logger.info("Application startup event.")
    try:
        initialize_database()
        create_db_and_tables(engine)

        redis_client = redis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            encoding="utf-8",
            decode_responses=True
        )
        await FastAPILimiter.init(redis_client)
        logger.info("FastAPILimiter initialized with Redis.")

    except Exception as e:
        logger.critical(f"Failed to initialize application: {e}")
        # In a production app, you might raise an exception here to prevent startup
        # if critical services like DB are unavailable.
        # For this exercise, we'll log and attempt to continue.

@app.on_shutdown
async def shutdown_event():
    logger.info("Application shutdown event.")
    if engine:
        engine.dispose()
        logger.info("Database engine disposed.")
    if FastAPILimiter.redis:
        await FastAPILimiter.redis.close()
        logger.info("FastAPILimiter Redis client closed.")


# --- 11. API Routers ---

@app.get("/health", status_code=status.HTTP_200_OK, tags=["System"])
async def health_check():
    """
    Performs a health check on the API and its dependencies.
    """
    try:
        db: Session = next(get_db())
        db.execute(sqlalchemy.text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed due to database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {e}",
        )

@app.post(
    "/pet",
    response_model=PetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Pet"],
    summary="Add a new pet to the store",
    dependencies=[Depends(RateLimiter(times=100, minutes=1)), Depends(get_current_user)]
)
async def add_pet(pet: PetCreate, db: Session = Depends(get_db)):
    """
    Add a new pet to the store. Requires authentication.
    """
    db_pet = pet_service.create_pet(db, pet)
    return PetResponse.from_orm(db_pet)

@app.get(
    "/pet/{pet_id}",
    response_model=PetResponse,
    tags=["Pet"],
    summary="Find pet by ID"
)
async def get_pet_by_id(pet_id: int, db: Session = Depends(get_db)):
    """
    Returns a single pet by its ID.
    """
    db_pet = pet_service.get_pet(db, pet_id)
    if db_pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    return PetResponse.from_orm(db_pet)

@app.put(
    "/pet",
    response_model=PetResponse,
    tags=["Pet"],
    summary="Update an existing pet",
    dependencies=[Depends(RateLimiter(times=100, minutes=1)), Depends(get_current_user)]
)
async def update_pet(pet: PetUpdate, db: Session = Depends(get_db)):
    """
    Update an existing pet in the store. Requires authentication.
    """
    db_pet = pet_service.update_pet(db, pet.id, pet)
    if db_pet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    return PetResponse.from_orm(db_pet)

@app.delete(
    "/pet/{pet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Pet"],
    summary="Delete a pet",
    dependencies=[Depends(RateLimiter(times=100, minutes=1)), Depends(get_current_user)]
)
async def delete_pet(pet_id: int, db: Session = Depends(get_db)):
    """
    Deletes a pet from the store. Requires authentication.
    """
    if not pet_service.delete_pet(db, pet_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    return None

@app.post(
    "/store/order",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Store"],
    summary="Place an order for a pet",
    dependencies=[Depends(RateLimiter(times=100, minutes=1))]
)
async def place_order(
    order: OrderCreate,
    current_user: Optional[User] = Depends(get_current_user), # Allow anonymous or authenticated orders
    db: Session = Depends(get_db)
):
    """
    Place an order for a pet in the store. Optionally accepts authentication.
    """
    try:
        user_id = current_user.id if current_user else None
        db_order = order_service.place_order(db, order, user_id)
        return OrderResponse.from_orm(db_order)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error placing order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not place order"
        )

@app.get(
    "/store/order/{order_id}",
    response_model=OrderResponse,
    tags=["Store"],
    summary="Find purchase order by ID",
    dependencies=[Depends(RateLimiter(times=100, minutes=1)), Depends(get_current_user)]
)
async def get_order_by_id(order_id: int, db: Session = Depends(get_db)):
    """
    Retrieve a purchase order by ID. Requires authentication.
    """
    db_order = order_service.get_order(db, order_id)
    if db_order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return OrderResponse.from_orm(db_order)

@app.get(
    "/store/inventory",
    response_model=InventoryResponse,
    tags=["Store"],
    summary="Returns pet inventories by status",
    dependencies=[Depends(RateLimiter(times=100, minutes=1)), Depends(get_current_user)]
)
async def get_pet_inventory(db: Session = Depends(get_db)):
    """
    Returns a map of status codes to quantities. Requires authentication.
    """
    return order_service.get_inventory(db)

@app.post(
    "/user",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["User"],
    summary="Create user"
)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Create a new user account.
    """
    if user_service.get_user_by_username(db, user.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    db_user = user_service.create_user(db, user)
    return UserResponse.from_orm(db_user)

@app.get(
    "/user/login",
    response_model=Token,
    tags=["User"],
    summary="Logs user into the system"
)
async def login_user(user_login: UserLogin, db: Session = Depends(get_db)):
    """
    Login user with username and password. Returns a JWT access token.
    """
    user = user_service.authenticate_user(db, user_login)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get(
    "/user/logout",
    status_code=status.HTTP_200_OK,
    tags=["User"],
    summary="Logs out current logged in user session",
    dependencies=[Depends(RateLimiter(times=100, minutes=1)), Depends(get_current_user)]
)
async def logout_user(request: Request):
    """
    Logs out the current user session by blacklisting their JWT. Requires authentication.
    """
    token = request.state.access_token 
    if token:
        invalidate_token(token)
        return {"message": "Successfully logged out"}
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No token found to invalidate")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Petstore API server on http://0.0.0.0:8000")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[-1]}")
    logger.info(f"Redis for rate limiting: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
    logger.info("Please ensure Redis and PostgreSQL services are running and accessible.")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=settings.LOG_LEVEL.lower())