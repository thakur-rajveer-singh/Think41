from sqlalchemy import create_engine
from chat_models import Base
from config import DATABASE_CONFIG

def init_chat_db():
    # Create database connection
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    
    # Create tables
    Base.metadata.create_all(engine)
    print("Chat database tables created successfully!")

if __name__ == "__main__":
    init_chat_db()
