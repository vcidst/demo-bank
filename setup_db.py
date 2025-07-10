#!/usr/bin/env python3
"""
Database setup script for the banking demo app.
Run this to initialize the database and populate with demo users.
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

def get_db_connection():
    """Get database connection using same environment variables as Rasa"""
    return psycopg2.connect(
        host=os.getenv("DATABASE_URL", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        database=os.getenv("POSTGRES_DB", "rasa"),
        user=os.getenv("PGUSER", "rasa"),
        password=os.getenv("POSTGRES_PASSWORD", "rasa"),
        cursor_factory=RealDictCursor
    )

def init_db():
    """Initialize database tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("Creating users table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Creating chat_messages table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                message TEXT NOT NULL,
                response TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        print("✅ Database tables created successfully")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

def populate_users():
    """Populate users table with demo data"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if demo user exists
        cursor.execute("SELECT id FROM users WHERE username = %s", ("demo",))
        if cursor.fetchone():
            print("Demo users already exist")
            return
        
        print("Populating demo users...")
        demo_users = [
            ("demo", "demo123", "demo@bankoframa.com"),
            ("admin", "admin123", "admin@bankoframa.com"),
            ("user1", "password123", "user1@bankoframa.com"),
            ("alice", "alice123", "alice@bankoframa.com"),
            ("bob", "bob123", "bob@bankoframa.com"),
        ]
        
        for username, password, email in demo_users:
            cursor.execute(
                "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
                (username, password, email)
            )
            print(f"  Created user: {username}")
        
        conn.commit()
        print("✅ Demo users populated successfully")
        
    except Exception as e:
        print(f"❌ Error populating users: {e}")
        sys.exit(1)
    finally:
        if conn:
            conn.close()

def show_users():
    """Show all users in the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id, username, email, created_at FROM users ORDER BY created_at")
        users = cursor.fetchall()
        
        print("\n📋 Users in database:")
        print("-" * 60)
        for user in users:
            print(f"ID: {user['id']:<3} | Username: {user['username']:<10} | Email: {user['email']}")
        print("-" * 60)
        
    except Exception as e:
        print(f"❌ Error showing users: {e}")
    finally:
        if conn:
            conn.close()

def test_connection():
    """Test database connection"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"✅ Database connection successful")
        print(f"PostgreSQL version: {version['version']}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def main():
    print("Banking Demo - Database Setup")
    print("=" * 40)
    
    # Test connection first
    if not test_connection():
        print("\n💡 Make sure PostgreSQL is running and environment variables are set:")
        print("   - DATABASE_URL (host)")
        print("   - PGPORT (port)")
        print("   - POSTGRES_DB (database name)")
        print("   - PGUSER (username)")
        print("   - POSTGRES_PASSWORD (password)")
        sys.exit(1)
    
    # Initialize database
    init_db()
    
    # Populate with demo users
    populate_users()
    
    # Show users
    show_users()
    
    print("\n🚀 Database setup complete!")
    print("You can now run the app with: python main.py")
    print("Login credentials:")
    print("  - demo / demo123")
    print("  - admin / admin123")
    print("  - user1 / password123")

if __name__ == "__main__":
    main()
