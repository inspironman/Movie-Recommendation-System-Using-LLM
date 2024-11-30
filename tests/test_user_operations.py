import pytest
import psycopg2
from werkzeug.security import check_password_hash, generate_password_hash
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database.user_operations import *

@pytest.fixture(scope='module')
def db_connection():
    conn = psycopg2.connect("postgresql://postgres:mysecretpassword@localhost:5432/moviedb")
    yield conn
    conn.close()

@pytest.fixture(scope='module')
def setup_users(db_connection):
    cursor = db_connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS testusers;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS testusers (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );
    """)
    db_connection.commit()
    yield db_connection
    # Cleanup
    cursor.execute("DROP TABLE IF EXISTS testusers;")
    db_connection.commit()
    cursor.close()

def test_register_user_success(setup_users):
    username = "testuser1"
    email = "testuser1@example.com"
    password = "password123"

    try:
        conn = setup_users
        cursor = conn.cursor()
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        conn.commit()

        cursor.execute("SELECT * FROM testusers WHERE username = %s;", (username,))
        user = cursor.fetchone()
        
        assert user is not None, "User was not found in the database"
        assert user[1] == username, "Username doesn't match"
        assert user[2] == email, "Email doesn't match"
        assert check_password_hash(user[3], password), "Password hash doesn't match"
        
        cursor.close()
    except Exception as e:
        print(f"Test failed with error: {e}")
        if conn:
            conn.rollback()
        raise e

def test_register_duplicate_username(setup_users):
    # First user
    username = "duplicate_user"
    email1 = "user1@example.com"
    password = "password123"

    try:
        conn = setup_users
        cursor = conn.cursor()
        
        # Register first user
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email1, password_hash)
        )
        conn.commit()

        email2 = "user2@example.com"
        with pytest.raises(psycopg2.IntegrityError):
            cursor.execute(
                "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email2, password_hash)
            )
            conn.commit()

    except Exception as e:
        if not isinstance(e, psycopg2.IntegrityError):
            print(f"Test failed with unexpected error: {e}")
        conn.rollback()
        raise e
    finally:
        cursor.close()

def test_login_success(setup_users):
    username = "loginuser"
    password = "password123"
    email = "loginuser@example.com"

    conn = setup_users
    cursor = None
    try:
        conn.rollback()  

        cursor = conn.cursor()
        cursor.execute("DELETE FROM testusers WHERE username = %s", (username,))
        conn.commit()
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        conn.commit()
        cursor.execute("SELECT * FROM testusers WHERE username = %s", (username,))
        user = cursor.fetchone()

        assert user is not None, "User not found"
        assert check_password_hash(user[3], password), "Password verification failed"

    except Exception as e:
        conn.rollback()  
        print(f"Test failed with error: {e}")
        raise e

    finally:
        if cursor:
            cursor.close()



def test_login_wrong_password(setup_users):
    username = "wrongpassuser"
    password = "correctpass"
    wrong_password = "wrongpass"
    email = "wrongpassuser@example.com"

    try:
        conn = setup_users
        cursor = conn.cursor()
        
        # Register user
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        conn.commit()

        # Test login with wrong password
        cursor.execute("SELECT * FROM testusers WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        assert user is not None, "User not found"
        assert not check_password_hash(user[3], wrong_password), "Wrong password should not verify"
        
        cursor.close()
    except Exception as e:
        print(f"Test failed with error: {e}")
        conn.rollback()
        raise e

def test_user_exists(setup_users):
    username = "existinguser"
    email = "existinguser@example.com"
    password = "password123"

    try:
        conn = setup_users
        cursor = conn.cursor()
        
        # Create user
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        conn.commit()

        # Check if user exists
        cursor.execute("SELECT EXISTS(SELECT 1 FROM testusers WHERE username = %s)", (username,))
        exists = cursor.fetchone()[0]
        
        assert exists is True, "User should exist"
        
        # Check non-existent user
        cursor.execute("SELECT EXISTS(SELECT 1 FROM testusers WHERE username = %s)", ("nonexistentuser",))
        exists = cursor.fetchone()[0]
        
        assert exists is False, "Non-existent user should not exist"
        
        cursor.close()
    except Exception as e:
        print(f"Test failed with error: {e}")
        conn.rollback()
        raise e

def test_get_user_by_id(setup_users):
    username = "iduser"
    email = "iduser@example.com"
    password = "password123"

    try:
        conn = setup_users
        cursor = conn.cursor()
        
        # Create user
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO testusers (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
            (username, email, password_hash)
        )
        user_id = cursor.fetchone()[0]
        conn.commit()

        # Get user by ID
        cursor.execute("SELECT * FROM testusers WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        assert user is not None, "User not found"
        assert user[1] == username, "Username doesn't match"
        assert user[2] == email, "Email doesn't match"
        
        cursor.close()
    except Exception as e:
        print(f"Test failed with error: {e}")
        conn.rollback()
        raise e
