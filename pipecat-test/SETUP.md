# Pipecat Test Setup Guide

## Architecture

```
Your Phone → Twilio Number → Webhook (server.py) → Daily Room (SIP) → Pipecat Bot (bot.py)
```

### Detailed Call Flow

1. You call your Twilio number
2. Twilio sends POST to your server's `/call` endpoint
3. Server creates a Daily room with SIP enabled
4. Server spawns `bot.py` as a subprocess with room details
5. Server returns TwiML with hold music (caller hears music)
6. Bot joins the Daily room and initializes pipeline
7. When Daily SIP is ready (`on_dialin_ready` event), bot tells Twilio to forward the call to Daily's SIP endpoint
8. Audio now flows: Phone ↔ Twilio ↔ Daily SIP ↔ Bot pipeline

## Prerequisites

- Python 3.10+
- Twilio account with a phone number
- Daily.co account (https://dashboard.daily.co)
- Soniox API key (https://console.soniox.com)
- OpenAI API key (https://platform.openai.com)
- ngrok (for local development) OR a VPS with public IP

---

## Step 1: Install Dependencies

```bash
cd pipecat-test
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

> **Note:** First run may take ~15 seconds as Pipecat downloads the Silero VAD model.

## Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual keys
```

## Step 3: Get Daily API Key

1. Go to **https://dashboard.daily.co**
2. Navigate to **Developers** → **API keys**
3. Copy your API key into `.env` as `DAILY_API_KEY`

## Step 4: Start the Server

### Option A: Local Development with ngrok

**Terminal 1 — Start the server:**
```bash
python server.py
```

You should see:
```
INFO - Starting VoxKit Pipecat server on port 8000
```

**Terminal 2 — Start ngrok:**
```bash
ngrok http 8000
```

Note the ngrok URL (e.g., `https://a1b2c3d4.ngrok-free.app`)

### Option B: VPS (Hostinger)

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Upload pipecat-test directory
# Install Python 3.10+ if needed
sudo apt update && sudo apt install python3.10 python3.10-venv

# Setup
cd pipecat-test
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys

# Run
python server.py
```

Your webhook URL will be: `http://your-vps-ip:8000/call`

> **Important:** For production, use HTTPS. You can put nginx with SSL in front
> of uvicorn, or use Caddy for automatic HTTPS.

## Step 5: Configure Twilio Webhook

1. Go to **Twilio Console** → **Phone Numbers** → **Manage** → **Active Numbers**
2. Click on your phone number
3. Under **Voice Configuration** → **A Call Comes In**:
   - Set to: **Webhook**
   - URL: `https://your-ngrok-url.ngrok-free.app/call` (or `https://your-vps:8000/call`)
   - HTTP Method: **POST**
4. Click **Save configuration**

## Step 6: Test It

1. Make sure the server is running (and ngrok if local)
2. Call your Twilio phone number from your mobile
3. You should hear hold music for 2-5 seconds
4. Then the bot connects and greets you
5. Speak in Urdu or English — the bot will respond

## Troubleshooting

- **Call goes to voicemail or error:**
  - Check Twilio Console → Debugger for webhook errors
  - Verify your webhook URL is accessible (try `curl https://your-url/health`)

- **Hold music plays forever:**
  - Bot may have failed to start. Check server terminal for errors.
  - Verify `DAILY_API_KEY` is correct.
  - Check that bot.py can be found (server spawns it from same directory).

- **Bot connects but no voice response:**
  - Check `OPENAI_API_KEY` and `SONIOX_API_KEY` in `.env`
  - Look at bot process output for errors

- **Call forwarding fails:**
  - Verify `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` are correct
  - Check bot logs for "Failed to forward call" error

- **ngrok URL changed:**
  - Free ngrok URLs change on restart — update Twilio webhook URL each time
  - Consider ngrok paid plan for stable URLs, or deploy to VPS

## Running Processes

This setup requires **two processes** running simultaneously:

| Process | Command | Purpose |
|---------|---------|---------|
| Server | `python server.py` | Handles Twilio webhooks, creates rooms |
| Bot(s) | (auto-spawned) | One per active call, auto-terminates |

The server spawns bot processes automatically. Each bot runs for the duration
of one phone call and then exits.

## VPS Deployment Tips

```bash
# Use screen or tmux for persistent sessions
screen -S voxkit-server
python server.py
# Ctrl+A, D to detach

# Or use systemd for auto-restart
sudo tee /etc/systemd/system/voxkit.service << 'EOF'
[Unit]
Description=VoxKit Pipecat Server
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/pipecat-test
Environment=PATH=/path/to/pipecat-test/venv/bin
ExecStart=/path/to/pipecat-test/venv/bin/python server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable voxkit
sudo systemctl start voxkit
sudo journalctl -u voxkit -f  # View logs
```
