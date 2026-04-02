import httpx
from config import config
from rich.console import Console
from typing import List, Optional
import os

console = Console()

async def forward_to_api(message: str, client_token: str, topic_token: str, files: Optional[List[str]] = None, format: str = "text"):
    """
    Forwards a message and optional files to the NFIP API.
    """
    data = {
        "auth_token": client_token,
        "topic_password": topic_token,
        "message": message,
        "format": format
    }
    
    files_to_send = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if files:
                for file_path in files:
                    # Open file in binary mode for multipart/form-data
                    f = open(file_path, "rb")
                    files_to_send.append(("files", (os.path.basename(file_path), f)))
                
                response = await client.post(
                    config.NFIP_API_URL,
                    data=data,
                    files=files_to_send
                )
            else:
                response = await client.post(
                    config.NFIP_API_URL,
                    data=data
                )
            
            if response.status_code == 200:
                console.log(f"[green]Successfully forwarded to API:[/green] {message[:50]}...")
            else:
                console.log(f"[red]Failed to forward to API (Status {response.status_code}):[/red] {response.text}")
                
    except Exception as e:
        console.log(f"[bold red]Exception occurred during API call:[/bold red] {e}")
    finally:
        # Close any open file handles
        for _, (_, f) in files_to_send:
            f.close()
