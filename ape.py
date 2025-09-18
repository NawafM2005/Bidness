#!/usr/bin/env python3
import os
from twilio.rest import Client
from dotenv import load_dotenv
load_dotenv()

# ENV
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM = os.environ["TWILIO_FROM"]

# Twilio setup
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

print(f"[START] Fetching inbound messages to {TWILIO_FROM}")

messages = client.messages.list(to=TWILIO_FROM, limit=50)

for msg in messages:
    if msg.direction == "inbound":
        print("------")
        print(f"From: {msg.from_}")
        print(f"Body: {msg.body}")
        print(f"Date: {msg.date_sent}")
        print(f"SID:  {msg.sid}")

print("[DONE]")
