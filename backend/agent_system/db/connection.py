from dotenv import load_dotenv
load_dotenv()
import os
import psycopg2

def connect_to_db():
    try:
        conn = psycopg2.connect(
            dbname = os.getenv("DB_NAME"),
            user = os.getenv("DB_USER"),
            password =  os.getenv("DB_PASSWORD"),
            host = os.getenv("DB_HOST"),
            port =  os.getenv("DB_PORT")   
        )
        
        with conn.cursor() as cur:
            cur.execute('SELECT version();')
            db_version = cur.fetchone()
            print(f"Connected to: {db_version}")
        return conn
        
    except Exception as error:
         print(f"Error connecting to database: {error}")
         

def create_vector_index(table_name:str,conn):
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE INDEX ON {table_name} USING hnsw (embedding vector_cosine_ops);")
        print(f"Cosine distance index created for {table_name}")
    except Exception as e:
        print(f"Error: {e}")
    conn.commit()
    


         



