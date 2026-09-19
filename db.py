import os
import psycopg2


def get_conn():
    """Connect to Neon using the DATABASE_URL environment variable."""
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url, connect_timeout=30)
