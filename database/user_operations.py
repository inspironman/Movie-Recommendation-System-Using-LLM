import os
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection():
    # Use environment variables for database connection details
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_name = os.environ.get('DB_NAME', 'moviedb')
    db_user = os.environ.get('DB_USER', 'user')
    db_password = os.environ.get('DB_PASSWORD', 'password')
    db_port = os.environ.get('DB_PORT', '5432')

    conn = psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password,
        port=db_port
    )
    return conn



def register_user(username, email, password):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Check if user already exists
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone() is not None:
            return "Username or email already exists"

        # Hash the password
        hashed_password = generate_password_hash(password)

        # Insert new user
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, hashed_password)
        )
        conn.commit()
        return "User registered successfully"
    except psycopg2.IntegrityError:
        conn.rollback()
        return "Username or email already exists"
    except Exception as e:
        conn.rollback()
        return f"An error occurred: {str(e)}"
    finally:
        cur.close()
        conn.close()


def authenticate_user(username, password):
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        
        if user and check_password_hash(user[3], password):  # Assuming password_hash is the 4th column
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2]
                # Add any other user details you want to return, but exclude sensitive information like the password hash
            }
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        cur.close()
        conn.close()