import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, User, Product, Order, OrderItem, DistributionCenter
from config import DATABASE_CONFIG
import os

def create_database_connection():
    db_url = f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{DATABASE_CONFIG['database']}"
    engine = create_engine(db_url)
    
    # Drop all existing tables
    Base.metadata.drop_all(engine)
    
    # Create all tables
    Base.metadata.create_all(engine)
    return engine

def load_csv_data(filepath):
    return pd.read_csv(filepath)

def load_users(session, data_path):
    users_df = load_csv_data(os.path.join(data_path, 'users.csv'))
    for _, row in users_df.iterrows():
        user = User(
            id=row['id'],
            first_name=row['first_name'],
            last_name=row['last_name'],
            email=row['email'],
            age=row['age'],
            gender=row['gender'],
            state=row['state'],
            street_address=row['street_address'],
            postal_code=row['postal_code'],
            city=row['city'],
            country=row['country'],
            latitude=row['latitude'],
            longitude=row['longitude'],
            traffic_source=row['traffic_source'],
            created_at=pd.to_datetime(row['created_at'])
        )
        session.add(user)
    session.commit()

def load_distribution_centers(session, data_path):
    dc_df = load_csv_data(os.path.join(data_path, 'distribution_centers.csv'))
    for _, row in dc_df.iterrows():
        dc = DistributionCenter(
            id=row['id'],
            name=row['name'],
            latitude=row['latitude'],
            longitude=row['longitude']
        )
        session.add(dc)
    session.commit()

def load_products(session, data_path):
    products_df = load_csv_data(os.path.join(data_path, 'products.csv'))
    for _, row in products_df.iterrows():
        product = Product(
            id=row['id'],
            cost=row['cost'],
            category=row['category'],
            name=row['name'],
            brand=row['brand'],
            retail_price=row['retail_price'],
            department=row['department'],
            sku=row['sku'],
            distribution_center_id=row['distribution_center_id']
        )
        session.add(product)
    session.commit()

def load_orders(session, data_path):
    orders_df = load_csv_data(os.path.join(data_path, 'orders.csv'))
    for _, row in orders_df.iterrows():
        order = Order(
            order_id=row['order_id'],
            user_id=row['user_id'],
            status=row['status'],
            gender=row['gender'],
            created_at=pd.to_datetime(row['created_at']),
            returned_at=pd.to_datetime(row['returned_at']) if pd.notna(row['returned_at']) else None,
            shipped_at=pd.to_datetime(row['shipped_at']) if pd.notna(row['shipped_at']) else None,
            delivered_at=pd.to_datetime(row['delivered_at']) if pd.notna(row['delivered_at']) else None,
            num_of_item=row['num_of_item']
        )
        session.add(order)
    session.commit()

def load_order_items(session, data_path):
    try:
        order_items_df = load_csv_data(os.path.join(data_path, 'order_items.csv'))
        print("Columns in order_items.csv:", order_items_df.columns.tolist())
        for _, row in order_items_df.iterrows():
            order_item = OrderItem(
                order_id=row['order_id'],
                product_id=row['product_id'],
                # Assuming these columns exist, adjust based on actual CSV structure
                quantity=1,  # Default quantity if not in CSV
                sale_price=row.get('sale_price', 0.0)  # Default price if not in CSV
            )
            session.add(order_item)
        session.commit()
    except Exception as e:
        print(f"Error in load_order_items: {str(e)}")
        raise

def main():
    # Create database connection
    engine = create_database_connection()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Path to the CSV files
    data_path = '../ecommerce-dataset-main/ecommerce-dataset-main/archive/archive'
    
    try:
        # Load data in order of dependencies
        print("Loading distribution centers...")
        load_distribution_centers(session, data_path)
        
        print("Loading users...")
        load_users(session, data_path)
        
        print("Loading products...")
        load_products(session, data_path)
        
        print("Loading orders...")
        load_orders(session, data_path)
        
        print("Loading order items...")
        load_order_items(session, data_path)
        
        print("Data loading completed successfully!")
        
    except Exception as e:
        print(f"Error loading data: {str(e)}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    main()
