import os
import signal
import threading
import asyncio
import webbrowser
from typing import Optional, List
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat
from telethon.errors import SessionPasswordNeededError
import pystray
from PIL import Image, ImageDraw

from config import config
from api_client import forward_to_api
from database import SessionLocal, ForwardRule, SessionStore, engine, Base
from rich.console import Console

# --- Setup ---
import sys
console = Console()
app = FastAPI()

# Determine the correct path for templates
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
    # Fix for uvicorn/isatty crash in --noconsole mode
    if sys.stdout is None: sys.stdout = open(os.devnull, "w")
    if sys.stderr is None: sys.stderr = open(os.devnull, "w")
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

templates = Jinja2Templates(directory=os.path.join(base_path, "templates"))

# Global Telethon Client and Tray Icon
client: Optional[TelegramClient] = None
tray_icon: Optional[pystray.Icon] = None

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Telegram Logic ---

async def init_client():
    global client
    db = SessionLocal()
    stored_session = db.query(SessionStore).first()
    db.close()

    session_string = stored_session.session_string if stored_session else ""
    client = TelegramClient(StringSession(session_string), config.API_ID, config.API_HASH)
    
    # Start the client but don't force login yet (that happens via Web UI)
    await client.connect()

    if await client.is_user_authorized():
        console.log("[green]Telegram User Authorized.[/green]")
        setup_event_handlers()
    else:
        console.log("[yellow]Telegram User NOT Authorized. Please login via web UI.[/yellow]")

def setup_event_handlers():
    @client.on(events.NewMessage())
    async def handler(event):
        # Determine source peer ID
        peer_id = event.chat_id
        
        # Check database for active rules for this peer
        db = SessionLocal()
        rule = db.query(ForwardRule).filter(ForwardRule.source_peer_id == peer_id, ForwardRule.is_active == True).first()
        db.close()

        if not rule:
            return

        console.log(f"[blue]Forwarding message from {rule.source_peer_name} ({peer_id})...[/blue]")
        
        msg = event.message
        text = msg.message or msg.caption or "(No text)"
        
        # Media handling
        downloaded_files = []
        if msg.media:
            try:
                file_path = await msg.download_media(file="tmp/")
                if file_path:
                    downloaded_files.append(file_path)
            except Exception as e:
                console.log(f"[red]Media download failed:[/red] {e}")

        # Forward
        await forward_to_api(
            message=text,
            client_token=rule.nfip_client_token,
            topic_token=rule.nfip_topic_token,
            files=downloaded_files if downloaded_files else None
        )

        # Cleanup
        for f in downloaded_files:
            try: os.remove(f)
            except: pass

# --- Web Routes ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    # Auto-redirect to login if not authorized
    if not await client.is_user_authorized():
        return RedirectResponse(url="/login")
    
    rules = db.query(ForwardRule).all()
    return templates.TemplateResponse(
        request=request, name="index.html", context={"rules": rules}
    )

@app.get("/add", response_class=HTMLResponse)
async def add_rule_page(request: Request):
    if not await client.is_user_authorized():
        return RedirectResponse(url="/login")
    
    channels = []
    # Fetch channels/groups the user is in
    async for dialog in client.iter_dialogs():
        if dialog.is_channel or dialog.is_group:
            channels.append({"id": dialog.id, "title": dialog.name})
    
    return templates.TemplateResponse(
        request=request, name="add_rule.html", context={"channels": channels}
    )

@app.post("/add")
async def add_rule(
    peer_id_with_name: str = Form(...),
    nfip_client_token: str = Form(...),
    nfip_topic_token: str = Form(...),
    is_active: bool = Form(False),
    db: Session = Depends(get_db)
):
    peer_id_str, peer_name = peer_id_with_name.split("|", 1)
    peer_id = int(peer_id_str)
    
    # Check if exists
    existing = db.query(ForwardRule).filter(ForwardRule.source_peer_id == peer_id).first()
    if existing:
        existing.nfip_client_token = nfip_client_token
        existing.nfip_topic_token = nfip_topic_token
        existing.is_active = is_active
    else:
        new_rule = ForwardRule(
            source_peer_id=peer_id,
            source_peer_name=peer_name,
            nfip_client_token=nfip_client_token,
            nfip_topic_token=nfip_topic_token,
            is_active=is_active
        )
        db.add(new_rule)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/delete/{rule_id}")
async def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(ForwardRule).filter(ForwardRule.id == rule_id).first()
    if rule:
        db.delete(rule)
        db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    is_logged_in = await client.is_user_authorized() if client else False
    username = ""
    if is_logged_in:
        me = await client.get_me()
        username = me.username or me.first_name
    
    return templates.TemplateResponse(
        request=request, 
        name="login.html", 
        context={
            "is_logged_in": is_logged_in,
            "username": username,
            "step": "phone"
        }
    )

@app.post("/login/phone")
async def login_phone(phone: str = Form(...), request: Request = None):
    # Request code from Telegram
    sent_code = await client.send_code_request(phone)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "step": "code",
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash
        }
    )

@app.post("/login/code")
async def login_code(
    request: Request,
    phone: str = Form(...), 
    phone_code_hash: str = Form(...), 
    code: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        
        # Success - Save session
        session_str = client.session.save()
        db.query(SessionStore).delete()
        db.add(SessionStore(session_string=session_str))
        db.commit()
        
        setup_event_handlers()
        return RedirectResponse(url="/login", status_code=303)
    
    except SessionPasswordNeededError:
        # 2FA Triggered
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"step": "password"}
        )
    except Exception as e:
        console.log(f"[red]Login error:[/red] {e}")
        return HTMLResponse(content=f"Error: {e}. <a href='/login'>Try again</a>")

@app.post("/login/password")
async def login_password(
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        await client.sign_in(password=password)
        
        # Success - Save session
        session_str = client.session.save()
        db.query(SessionStore).delete()
        db.add(SessionStore(session_string=session_str))
        db.commit()
        
        setup_event_handlers()
        return RedirectResponse(url="/login", status_code=303)
    except Exception as e:
        console.log(f"[red]Password login error:[/red] {e}")
        return HTMLResponse(content=f"Error: {e}. <a href='/login'>Try again</a>")

@app.get("/logout")
async def logout(db: Session = Depends(get_db)):
    await client.log_out()
    db.query(SessionStore).delete()
    db.commit()
    return RedirectResponse(url="/login", status_code=303)

@app.on_event("startup")
async def startup_event():
    await init_client()
    
    if not await client.is_user_authorized():
        # Automatically open browser for login if not connected
        webbrowser.open("http://localhost:19999")
    else:
        # Connected! Just notify.
        console.log("[bold green]NFIP Telegram Forwarder is running.[/bold green]")
        # Give tray thread a second to initialize icon
        await asyncio.sleep(1.5)
        if tray_icon:
            tray_icon.notify("NFIP Telegram Forwarder is running", "NFIP Forwarder")

# --- System Tray Logic ---

def create_image():
    # Create a simple 64x64 blue icon with white "NF" text
    image = Image.new('RGB', (64, 64), color=(37, 99, 235))
    draw = ImageDraw.Draw(image)
    # Basic attempt to draw an N and F without a custom font file
    draw.text((16, 20), "NFIP", fill=(255, 255, 255))
    return image

def on_open_dashboard(icon, item):
    webbrowser.open("http://localhost:19999")

def on_quit(icon, item):
    icon.stop()
    # Send SIGINT to gracefully stop Uvicorn and Telethon
    os.kill(os.getpid(), signal.SIGINT)

def setup_tray():
    global tray_icon
    image = create_image()
    menu = pystray.Menu(
        pystray.MenuItem('Open Dashboard', on_open_dashboard, default=True),
        pystray.MenuItem('Quit', on_quit)
    )
    tray_icon = pystray.Icon("NFIP Forwarder", image, "NFIP Forwarder", menu)
    tray_icon.run()

if __name__ == "__main__":
    import uvicorn
    # Create tmp dir if not exists
    if not os.path.exists("tmp"):
        os.makedirs("tmp")
        
    # Start the system tray icon in a background thread
    tray_thread = threading.Thread(target=setup_tray, daemon=True)
    tray_thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=19999)
