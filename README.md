# NFIP Telegram Forwarder

A Python-based Telegram forwarder that monitors specific groups or channels and sends messages/media to the NF's Informer Protocol (NFIP) API.

## Features
- **Monitors** multiple source peers (groups, channels, or users).
- **Supports** both text and media (photos, documents).
- **Asynchronous** implementation for high performance.
- **Temporary storage** with auto-cleanup for media.

## Setup Instructions

### 1. Prerequisites
- Python 3.10 or higher.
- A Telegram account and API credentials.

### 2. Get Telegram API Credentials
1. Visit [my.telegram.org](https://my.telegram.org) and log in.
2. Go to **API development tools**.
3. Create a new application (you can use any name/URL).
4. Note your `App api_id` and `App api_hash`.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment
1. Copy `.env.example` to `.env`.
2. Open `.env` and fill in your details:
   - `API_ID` & `API_HASH`: From step 2.
   - `NFIP_AUTH_TOKEN`: Your 7-character NFIP token.
   - `NFIP_TOPIC_PASSWORD`: Your destination's internal password.
   - `SOURCE_PEERS`: Comma-separated list of peer IDs or usernames.
     - Group IDs usually start with `-100`.
     - Usernames start with `@`.

### 5. Run the Forwarder
```bash
python main.py
```
- If running as a **User account** (default), you will be prompted to enter your phone number and the login code sent via Telegram.
- If using a **Bot account**, ensure `TELE_BOT_TOKEN` is set in your `.env` file.

## Troubleshooting
- **Media not downloading?** Ensure the `tmp/` folder exists and is writable.
- **API errors?** Check your `NFIP_AUTH_TOKEN` and `NFIP_TOPIC_PASSWORD` in the NFIP dashboard.
- **Peer not found?** Ensure the account/bot is a member of the source group/channel.
