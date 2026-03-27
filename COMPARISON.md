# VoxKit Framework Comparison — Test Results

**Date:** _______________
**Tester:** _______________
**Phone used:** _______________
**Network:** WiFi / 4G / 5G

---

## Setup Complexity

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Number of config steps | | |
| External services in chain | Twilio → LiveKit Cloud | Twilio → Your Server → Daily |
| Number of API keys needed | 4 (LK, LK Secret, Soniox, OpenAI) | 5 (Daily, Twilio SID, Twilio Auth, Soniox, OpenAI) |
| Running processes needed | 1 (agent.py) | 1 (server.py) + auto-spawned bots |
| Setup time (minutes) | | |
| Worked on first try? | Yes / No | Yes / No |
| If no, what went wrong? | | |

---

## Performance — Call 1

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Pickup-to-greeting (seconds) | | |
| Response latency (seconds) | | |
| Audio quality (1-5) | | |
| STT accuracy — English (1-5) | | |
| STT accuracy — Urdu (1-5) | | |
| Any audio glitches? | | |
| Any dropped words? | | |

---

## Performance — Call 2

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Pickup-to-greeting (seconds) | | |
| Response latency (seconds) | | |
| Audio quality (1-5) | | |
| STT accuracy — English (1-5) | | |
| STT accuracy — Urdu (1-5) | | |
| Any audio glitches? | | |
| Any dropped words? | | |

---

## Performance — Call 3

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Pickup-to-greeting (seconds) | | |
| Response latency (seconds) | | |
| Audio quality (1-5) | | |
| STT accuracy — English (1-5) | | |
| STT accuracy — Urdu (1-5) | | |
| Any audio glitches? | | |
| Any dropped words? | | |

---

## Reliability

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Total test calls attempted | | |
| Successful connections | | |
| Failed connections | | |
| Calls dropped mid-conversation | | |
| Average call duration tested | | |

---

## Developer Experience

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Code complexity (1-5, 1=simple) | | |
| Documentation quality (1-5) | | |
| Error messages helpfulness (1-5) | | |
| Debugging ease (1-5) | | |
| Community/support (1-5) | | |

---

## Architecture Fit for VoxKit Production

| Consideration | LiveKit | Pipecat |
|---------------|---------|---------|
| Multi-tenant support | | |
| Concurrent call scaling | | |
| Agent dispatch flexibility | | |
| Hosting requirements | Cloud-managed (LK Cloud) | Self-hosted server + Daily |
| Vendor lock-in concern | LiveKit Cloud | Daily.co |
| Cost model clarity | | |
| SIP integration maturity | | |

---

## Averages (fill after all calls)

| Metric | LiveKit | Pipecat |
|--------|---------|---------|
| Avg pickup-to-greeting (s) | | |
| Avg response latency (s) | | |
| Avg audio quality | | |
| Avg STT accuracy (English) | | |
| Avg STT accuracy (Urdu) | | |

---

## Notes

### LiveKit Notes
```




```

### Pipecat Notes
```




```

---

## Final Decision

**Chosen framework:** _______________

**Primary reasons:**
1.
2.
3.

**Concerns to watch:**
1.
2.
