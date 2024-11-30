import os
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection():
    db_host = os.environ.get('POSTGRES_HOST', 'localhost')
    db_name = os.environ.get('POSTGRES_DB', 'moviedb')
    db_user = os.environ.get('POSTGRES_USER', 'postgres')
    db_password = os.environ.get('POSTGRES_PASSWORD', 'mysecretpassword')
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
        cur.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
        if cur.fetchone() is not None:
            return "Username or email already exists"
        hashed_password = generate_password_hash(password)
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
        
        if user and check_password_hash(user[3], password):   
            return {
                'id': user[0],
                'username': user[1],
                'email': user[2]
            }
        else:
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        cur.close()
        conn.close()