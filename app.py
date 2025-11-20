from flask import Flask, request, jsonify, make_response, send_file
from flask_cors import CORS
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import sqlite3
import datetime
import uuid
from user_agents import parse  # Library to parse device/browser info

app = Flask(__name__)
CORS(app, supports_credentials=True)

# --- CONFIGURATION ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
MY_EMAIL = os.environ.get("MY_EMAIL")
MY_APP_PASSWORD = os.environ.get("MY_APP_PASSWORD")
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

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email)

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
        os = f"{user_agent.os.family} {user_agent.os.version_string}"

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
            visitor_id, ip_address, page_url, browser, os,
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

# --- EMAIL CONTACT FORM ---
@app.route('/contact', methods=['POST'])
def contact():
    try:
        data = request.get_json()
        name = data.get('name')
        visitor_email = data.get('email')
        subject = data.get('subject')
        message_content = data.get('message')

        if not all([name, visitor_email, subject, message_content]):
            return jsonify({"error": "All fields are required."}), 400
        
        if not is_valid_email(visitor_email):
            return jsonify({"error": "Please enter a valid email address."}), 400

        msg = MIMEMultipart()
        msg['From'] = MY_EMAIL
        msg['To'] = MY_EMAIL
        msg['Reply-To'] = visitor_email
        msg['Subject'] = f"Portfolio Contact: {subject}"

        body = f"""
        New Message from Portfolio
        ---------------------------
        Name: {name}
        Email: {visitor_email}
        Subject: {subject}
        Message: {message_content}
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(MY_EMAIL, MY_APP_PASSWORD)
        server.send_message(msg)
        server.quit()

        return jsonify({"success": "Message sent successfully!"}), 200

    except Exception as e:
        print(f"Email Error: {e}")
        return jsonify({"error": "Failed to send message."}), 500

# --- DOWNLOAD DATABASE FILE ---
@app.route('/download_db', methods=['GET'])
def download_db():
    try:
        return send_file(
            DB_NAME,
            mimetype="application/octet-stream",
            as_attachment=True,
            download_name="portfolio_tracker.db"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- MAIN ---
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
