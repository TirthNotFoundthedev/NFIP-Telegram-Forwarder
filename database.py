from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

DATABASE_URL = "sqlite:///./nfip_forwarder.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ForwardRule(Base):
    __tablename__ = "forward_rules"
    id = Column(Integer, primary_key=True, index=True)
    source_peer_id = Column(Integer, unique=True, index=True) # Telegram Channel/Group ID
    source_peer_name = Column(String) # Friendly name (e.g., "Daily News")
    nfip_client_token = Column(String)
    nfip_topic_token = Column(String)
    is_active = Column(Boolean, default=True)

class SessionStore(Base):
    __tablename__ = "session_store"
    id = Column(Integer, primary_key=True, index=True)
    session_string = Column(String) # For Telethon's StringSession (to keep logged in)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
