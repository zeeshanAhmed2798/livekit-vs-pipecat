# LiveKit Test Setup Guide

## Architecture

```
Your Phone → Twilio Number → Elastic SIP Trunk → LiveKit SIP Endpoint → LiveKit Agent
```

## Prerequisites

- Python 3.10+
- Twilio account with a phone number
- LiveKit Cloud account (https://cloud.livekit.io)
- Soniox API key (https://console.soniox.com)
- OpenAI API key (https://platform.openai.com)
- LiveKit CLI installed (`brew install livekit-cli` or see https://docs.livekit.io/home/cli/)

---

## Step 1: Install Dependencies

```bash
cd livekit-test
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
```

## Step 2: Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual keys
```

## Step 3: Create Twilio Elastic SIP Trunk

1. Go to **Twilio Console** → **Elastic SIP Trunking** → **Trunks**
2. Click **Create new SIP Trunk**
   - Name: `VoxKit-LiveKit-Test`
3. Under **Origination** tab:
   - Click **Add new Origination URI**
   - URI: `sip:your-project.livekit.cloud` (replace with your LiveKit SIP endpoint)
   - Priority: 10, Weight: 10
   - Click **Add**
4. Under **Termination** tab:
   - You can leave this empty for inbound-only testing.

> **Finding your LiveKit SIP endpoint:**
> Go to LiveKit Cloud Dashboard → your project → Telephony section.
> The SIP endpoint is typically: `sip:<your-project-id>.livekit.cloud`
> Or check via CLI: `lk sip info`

## Step 4: Associate Phone Number with Trunk

1. Go to **Twilio Console** → **Phone Numbers** → **Manage** → **Active Numbers**
2. Click on your phone number
3. Under **Voice Configuration**:
   - Configure with: **SIP Trunk**
   - SIP Trunk: Select `VoxKit-LiveKit-Test`
4. Click **Save configuration**

## Step 5: Create LiveKit Inbound SIP Trunk

### Option A: LiveKit Cloud Dashboard (Recommended)

1. Go to **LiveKit Cloud Dashboard** → **Telephony** → **SIP Trunks**
2. Click **Create new trunk**
3. Select **Inbound** direction
4. Switch to **JSON editor** tab
5. Paste the following JSON:

```json
{
  "trunk": {
    "name": "VoxKit-Twilio-Inbound",
    "numbers": ["+1XXXXXXXXXX"],
    "krisp_enabled": true
  }
}
```

Replace `+1XXXXXXXXXX` with your Twilio phone number in E.164 format.

6. Click **Create**

### Option B: Using LiveKit CLI

```bash
lk sip inbound create \
  --new-trunk-name "VoxKit-Twilio-Inbound" \
  --new-trunk-numbers "+1XXXXXXXXXX" \
  --new-trunk-krisp-enabled
```

## Step 6: Create SIP Dispatch Rule

The dispatch rule tells LiveKit which agent to assign to inbound calls.

### Option A: Dashboard

1. Go to **Telephony** → **SIP Dispatch Rules**
2. Click **Create dispatch rule**
3. Use JSON editor:

```json
{
  "name": "VoxKit Test Dispatch",
  "trunk_ids": [],
  "rule": {
    "dispatchRuleIndividual": {
      "roomPrefix": "voxkit-call-"
    }
  },
  "room_config": {
    "agents": [
      {
        "agent_name": "voxkit-test-agent"
      }
    ]
  }
}
```

4. Click **Create**

### Option B: Using CLI

```bash
lk sip dispatch create \
  --new-dispatch-name "VoxKit Test Dispatch" \
  --new-dispatch-rule-individual-room-prefix "voxkit-call-" \
  --new-dispatch-agent-name "voxkit-test-agent"
```

> **Important:** The `agent_name` here ("voxkit-test-agent") must match the
> `agent_name` in the `@server.rtc_session(agent_name="voxkit-test-agent")`
> decorator in `agent.py`.

## Step 7: Run the Agent

```bash
# Development mode (auto-reload on changes)
python agent.py dev

# Production mode
python agent.py start
```

You should see output like:
```
INFO - Worker registered with LiveKit Cloud
INFO - Waiting for job requests...
```

## Step 8: Test It

1. Call your Twilio phone number from your mobile
2. You should hear the agent greet you within a few seconds
3. Speak in Urdu or English — the agent will respond

## Troubleshooting

- **Agent not picking up:** Check that the dispatch rule's `agent_name` matches exactly.
- **No audio:** Verify Krisp is enabled on the inbound trunk. Check Twilio Elastic SIP Trunk origination URI.
- **Agent connects but no STT:** Verify `SONIOX_API_KEY` is correct in `.env`.
- **Twilio returning errors:** Check Twilio Console → Debugger for SIP error codes.
- **Check LiveKit logs:** Go to LiveKit Cloud Dashboard → Sessions for detailed call traces.

## Deployment on VPS (Hostinger)

```bash
# SSH into your VPS
ssh user@your-vps-ip

# Clone/upload the livekit-test directory
# Install Python 3.10+ if not available
sudo apt update && sudo apt install python3.10 python3.10-venv

# Setup
cd livekit-test
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your keys

# Run in background with nohup or use systemd/supervisor
nohup python agent.py start > agent.log 2>&1 &

# Or use screen/tmux for easier monitoring
screen -S voxkit-agent
python agent.py start
# Ctrl+A, D to detach
```

> **Note:** The LiveKit agent connects *outbound* to LiveKit Cloud via WebSocket.
> No inbound ports need to be open on your VPS. Only outbound HTTPS/WSS is required.
