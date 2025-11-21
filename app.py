from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import sqlite3
import datetime
import uuid
import os
from user_agents import parse

app = Flask(__name__)

# --- CORS CONFIGURATION ---
CORS(app,
     supports_credentials=True,
     resources={r"/*": {"origins": [
         "https://sarvesh-dabke-portfolio.vercel.app",
         "https://sarvesh-dabke-portfolio.vercel.app/"
     ]}}
)

# --- DATABASE CONFIG ---
DB_NAME = os.environ.get("DB_NAME", "portfolio_tracker.db")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_id TEXT,
            ip_address TEXT,
            page_url TEXT,
            browser TEXT,
            os TEXT,
            device_type TEXT,
            timestamp DATETIME,
            is_repeat INTEGER,
            custom_log TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- TRACKING ENDPOINT ---
@app.route('/track_visit', methods=['POST'])
def track_visit():
    try:
        data = request.get_json() or {}
        page_url = data.get('page', 'Unknown Page')
        custom_log = data.get('log', '')

        user_agent_string = request.headers.get('User-Agent', '')
        user_agent = parse(user_agent_string)
        
        browser = f"{user_agent.browser.family} {user_agent.browser.version_string}"
        os_info = f"{user_agent.os.family} {user_agent.os.version_string}"

        if user_agent.is_mobile:
            device_type = "Mobile"
        elif user_agent.is_tablet:
            device_type = "Tablet"
        else:
            device_type = "Desktop"

        ip_address = request.remote_addr
        visitor_id = request.cookies.get('visitor_id')
        is_repeat = 1 if visitor_id else 0
        
        if not visitor_id:
            visitor_id = str(uuid.uuid4())

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO visits (visitor_id, ip_address, page_url, browser, os, device_type, timestamp, is_repeat, custom_log)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            visitor_id, ip_address, page_url, browser, os_info,
            device_type, datetime.datetime.now(), is_repeat, custom_log
        ))
        conn.commit()
        conn.close()

        resp = make_response(jsonify({"status": "tracked", "visitor": visitor_id}))
        resp.set_cookie('visitor_id', visitor_id, max_age=60*60*24*365, samesite='None', secure=True)
        return resp

    except Exception as e:
        print(f"Tracking Error: {e}")
        return jsonify({"error": str(e)}), 500

# --- VIEW LOGS ---
@app.route('/view_logs', methods=['GET'])
def view_logs():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM visits ORDER BY id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    
    logs = [dict(row) for row in rows]
    return jsonify(logs)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
