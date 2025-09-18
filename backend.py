#!/usr/bin/env python3
from flask import Flask, request, jsonify
from flask_cors import CORS
from twilio.rest import Client
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Environment variables
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM = os.environ["TWILIO_FROM"]
LOGIN_USERNAME = os.environ["LOGIN_USERNAME"]
LOGIN_PASSWORD = os.environ["LOGIN_PASSWORD"]

# Twilio setup
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.route('/api/login', methods=['POST'])
def login():
    """Handle user login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if username == LOGIN_USERNAME and password == LOGIN_PASSWORD:
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

@app.route('/api/messages', methods=['GET'])
def get_messages():
    """Fetch all messages from Twilio"""
    try:
        # Fetch a larger number of messages to ensure we get complete conversation history
        # This includes both messages sent by us and received by us
        all_messages = client.messages.list(limit=1000)  # Increased limit significantly
        
        # Group messages by phone number
        conversations = {}
        
        for msg in all_messages:
            # Determine the contact number (the other party in the conversation)
            if msg.from_ == TWILIO_FROM:
                # Message sent by us (outbound)
                contact = msg.to
                direction = "outbound"
            else:
                # Message received from someone else (inbound)
                contact = msg.from_
                direction = "inbound"
            
            # Skip if it's our own number (shouldn't happen but just in case)
            if contact == TWILIO_FROM:
                continue
            
            if contact not in conversations:
                conversations[contact] = []
            
            conversations[contact].append({
                "sid": msg.sid,
                "body": msg.body,
                "from": msg.from_,
                "to": msg.to,
                "direction": direction,  # Use our calculated direction
                "date_sent": msg.date_sent.isoformat() if msg.date_sent else None,
                "status": msg.status
            })
        
        # Sort messages in each conversation by date (oldest first)
        for contact in conversations:
            conversations[contact].sort(key=lambda x: x['date_sent'] or '1970-01-01')
        
        return jsonify({"success": True, "conversations": conversations})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """Send a message via Twilio"""
    try:
        data = request.get_json()
        to_number = data.get('to')
        message_body = data.get('body')
        
        if not to_number or not message_body:
            return jsonify({"success": False, "message": "Missing 'to' or 'body' parameter"}), 400
        
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_FROM,
            to=to_number
        )
        
        return jsonify({
            "success": True, 
            "message": "Message sent successfully",
            "sid": message.sid
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/conversation/<phone_number>', methods=['GET'])
def get_conversation(phone_number):
    """Get messages for a specific phone number"""
    try:
        # Get messages to and from this phone number
        messages_sent = client.messages.list(to=phone_number, limit=50)
        messages_received = client.messages.list(from_=phone_number, limit=50)
        
        # Combine and sort messages
        all_messages = []
        
        for msg in messages_sent:
            all_messages.append({
                "sid": msg.sid,
                "body": msg.body,
                "from": msg.from_,
                "to": msg.to,
                "direction": "outbound",
                "date_sent": msg.date_sent.isoformat() if msg.date_sent else None,
                "status": msg.status
            })
        
        for msg in messages_received:
            all_messages.append({
                "sid": msg.sid,
                "body": msg.body,
                "from": msg.from_,
                "to": msg.to,
                "direction": "inbound",
                "date_sent": msg.date_sent.isoformat() if msg.date_sent else None,
                "status": msg.status
            })
        
        # Sort by date
        all_messages.sort(key=lambda x: x['date_sent'] or '1970-01-01')
        
        return jsonify({"success": True, "messages": all_messages})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)