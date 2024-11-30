from sqlalchemy import create_engine
from models import Base
import os

# Use localhost since the port is mapped from the container to your local machine
database_url = "postgresql://postgres:mysecretpassword@localhost:5432/moviedb"
engine = create_engine(database_url)

def create_tables():
    try:
        Base.metadata.create_all(engine)
        print("Tables created successfully!")
    except Exception as e:
        print(f"Error creating tables: {e}")

if __name__ == "__main__":
    create_tables()
