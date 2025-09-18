# Bidness Chat - Twilio Messaging Dashboard

A Next.js and Flask application for managing Twilio SMS conversations with an iMessage-style interface.

## Features

- **Message Management**: View all Twilio conversations in a clean interface
- **Real-time Messaging**: Send and receive SMS messages through Twilio
- **iMessage-style UI**: Modern, responsive chat interface built with Tailwind CSS

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- Twilio Account with SMS-enabled phone number

### Backend Setup
1. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables in `.env`:
   ```
   TWILIO_ACCOUNT_SID=your_account_sid
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_FROM=your_twilio_phone_number
   LOGIN_USERNAME=Monky
   LOGIN_PASSWORD=SonalGAP
   ```

3. Start the Flask backend:
   ```bash
   python backend.py
   ```
   The API will be available at `http://localhost:5000`

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd bidness_webpage
   ```

2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   The web app will be available at `http://localhost:3000`

## Usage

1. Open `http://localhost:3000` in your browser
3. View your conversations in the left sidebar
4. Click on any conversation to view messages
5. Type in the message box and press Enter or click Send to reply

## API Endpoints

- `POST /api/login` - Authenticate user
- `GET /api/messages` - Fetch all conversations
- `POST /api/send-message` - Send a new message
- `GET /api/conversation/<phone_number>` - Get specific conversation

## File Structure

```
Bidness/
├── backend.py              # Flask API server
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables
├── bidness_webpage/       # Next.js frontend
│   ├── src/app/
│   │   ├── page.tsx       # Login page
│   │   └── dashboard/
│   │       └── page.tsx   # Main chat dashboard
│   └── package.json       # Node.js dependencies
└── README.md              # This file
```

## Deployment

- Backend: Deploy Flask app to services like Heroku, Railway, or DigitalOcean
- Frontend: Deploy Next.js app to Vercel, Netlify, or similar platforms
- Update API URLs in frontend for production deployment
