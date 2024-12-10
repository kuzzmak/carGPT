import psycopg2
from psycopg2 import sql

# Connect to the default PostgreSQL database (e.g., 'postgres')
try:
    conn = psycopg2.connect(
        dbname="ads",  # Default database
        user="adsuser",
        password="pass",
        host="localhost",   # or your server IP
        port="5432"         # Default PostgreSQL port
    )
    conn.autocommit = True  # Allow database creation outside transactions
    cursor = conn.cursor()
    print("Connected to PostgreSQL!")
    
    # Database name
    new_db_name = "new_database_name"
    
    # Create the database
    cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(new_db_name)))
    print(f"Database '{new_db_name}' created successfully!")

except psycopg2.Error as e:
    print(f"Error creating database: {e}")
finally:
    if cursor:
        cursor.close()
    if conn:
        conn.close()
    print("Connection closed.")
