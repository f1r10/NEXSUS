"""Development-only initial schema bootstrap. Production requires versioned migrations."""
from app.db import Base, engine
from app import models  # noqa: F401

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("NEXUS schema initialized (development mode)")
