from sqlalchemy import create_engine
from models import Base

# Update this URL to point to your local PostgreSQL instance
DATABASE_URL = "postgresql://user:password@localhost:5432/moviedb"
engine = create_engine(DATABASE_URL)

def create_tables():
    Base.metadata.create_all(engine)

if __name__ == "__main__":
    create_tables()
    print("Database tables created successfully.")
