from dotenv import load_dotenv
import os
import urllib.parse

load_dotenv()

# URL encode the password to handle special characters
password = urllib.parse.quote_plus(os.getenv('DB_PASSWORD', ''))

DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'think41_ecommerce'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': password,
    'port': os.getenv('DB_PORT', '5432')
}
