import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import httpx

# Database connection using same environment variables as Rasa
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5432"),
        database=os.getenv("POSTGRES_DB", "rasa"),
        user=os.getenv("PGUSER", "rasa"),
        password=os.getenv("POSTGRES_PASSWORD", "rasa"),
        cursor_factory=RealDictCursor
    )

# Initialize database tables
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create chat_messages table
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
        print("Database tables initialized successfully")
        
    except Exception as e:
        print(f"Database initialization error: {e}")
    finally:
        if conn:
            conn.close()

# Populate users table with demo data
def populate_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if demo user exists
        cursor.execute("SELECT id FROM users WHERE username = %s", ("demo",))
        if cursor.fetchone():
            print("Demo user already exists")
            return
        
        # Insert demo users
        demo_users = [
            ("demo", "demo123", "demo@bankoframa.com"),
            ("admin", "admin123", "admin@bankoframa.com"),
            ("user1", "password123", "user1@bankoframa.com"),
        ]
        
        for username, password, email in demo_users:
            cursor.execute(
                "INSERT INTO users (username, password, email) VALUES (%s, %s, %s)",
                (username, password, email)
            )
        
        conn.commit()
        print("Demo users populated successfully")
        
    except Exception as e:
        print(f"Error populating users: {e}")
    finally:
        if conn:
            conn.close()

# Authentication helper
def authenticate_user(username: str, password: str) -> dict:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, email FROM users WHERE username = %s AND password = %s",
            (username, password)
        )
        user = cursor.fetchone()
        return dict(user) if user else None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None
    finally:
        if conn:
            conn.close()

# Save chat message
def save_chat_message(user_id: int, message: str, response: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_messages (user_id, message, response) VALUES (%s, %s, %s)",
            (user_id, message, response)
        )
        conn.commit()
    except Exception as e:
        print(f"Error saving chat message: {e}")
    finally:
        if conn:
            conn.close()

app = FastAPI(title="Banking Demo", description="Simple demo app for Rasa chat")
templates = Jinja2Templates(directory="templates")

RASA_SERVER_URL = os.getenv("RASA_SERVER_URL", "http://localhost:5005")

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    populate_users()

@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    user = authenticate_user(username, password)
    if user:
        response = RedirectResponse(url="/chat", status_code=302)
        response.set_cookie(key="user_id", value=str(user["id"]), httponly=True)
        response.set_cookie(key="username", value=user["username"], httponly=True)
        return response
    else:
        raise HTTPException(status_code=400, detail="Invalid credentials")

@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    user_id = request.cookies.get("user_id")
    username = request.cookies.get("username")
    if not user_id or not username:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("chat.html", {"request": request, "username": username})

@app.post("/api/chat")
async def chat_with_rasa(request: Request):
    user_id = request.cookies.get("user_id")
    username = request.cookies.get("username")
    if not user_id or not username:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    data = await request.json()
    message = data.get("message", "")
    
    try:
        # Send message to Rasa
        async with httpx.AsyncClient() as client:
            payload = {"sender": user_id, "message": message}
            response = await client.post(f"{RASA_SERVER_URL}/webhooks/rest/webhook", json=payload, timeout=10.0)
            response.raise_for_status()
            rasa_response = response.json()
        
        # Extract bot response
        bot_response = "I'm sorry, I didn't understand that."
        if rasa_response and len(rasa_response) > 0:
            bot_response = rasa_response[0].get("text", bot_response)
        
        # Save chat message to database
        save_chat_message(int(user_id), message, bot_response)
        
        return {"response": bot_response}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="user_id")
    response.delete_cookie(key="username")
    return response

# Database management endpoints
@app.get("/api/users")
async def get_users():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email, created_at FROM users ORDER BY created_at DESC")
        users = cursor.fetchall()
        return [dict(user) for user in users]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/api/chat-history/{user_id}")
async def get_chat_history(user_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT message, response, created_at FROM chat_messages WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (user_id,)
        )
        messages = cursor.fetchall()
        return [dict(msg) for msg in messages]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/api/tracker/{conversation_id}")
async def get_tracker(conversation_id: str, include_events: str = "ALL"):
    """Get Rasa tracker for a conversation"""
    try:
        params = {"include_events": include_events} if include_events else {}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{RASA_SERVER_URL}/conversations/{conversation_id}/tracker", 
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            tracker_data = response.json()
            
            # Extract conversation history
            conversation_history = []
            slots = tracker_data.get("slots", {})
            
            for event in tracker_data.get("events", []):
                if event.get("event") == "user":
                    conversation_history.append({
                        "type": "user",
                        "text": event.get("text", ""),
                        "timestamp": event.get("timestamp", 0)
                    })
                elif event.get("event") == "bot":
                    conversation_history.append({
                        "type": "bot", 
                        "text": event.get("text", ""),
                        "timestamp": event.get("timestamp", 0)
                    })
                else:
                    conversation_history.append({
                        "type": "event",
                        "text": event.get("event", "unknown_event"),
                        "timestamp": event.get("timestamp", 0)
                    })
            
            # Filter out null/empty slots for display
            filtered_slots = {k: v for k, v in slots.items() if v is not None and v != "" and k != "flow_hashes"}
            
            return {
                "conversation_id": conversation_id,
                "conversation_history": conversation_history,
                "slots": filtered_slots,
                "raw_tracker": tracker_data
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching tracker: {str(e)}")
