import os
from typing import List, Union
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = os.getenv("API_ID")
    API_HASH = os.getenv("API_HASH")
    SESSION_NAME = os.getenv("SESSION_NAME", "nfip_forwarder")
    TELE_BOT_TOKEN = os.getenv("TELE_BOT_TOKEN")
    
    NFIP_CLIENT_TOKEN = os.getenv("NFIP_CLIENT_TOKEN")
    NFIP_TOPIC_TOKEN = os.getenv("NFIP_TOPIC_TOKEN")
    NFIP_API_URL = "https://nfip-api.vercel.app/notify"
    
    _SOURCE_PEERS_STR = os.getenv("SOURCE_PEERS", "")

    @classmethod
    def get_source_peers(cls) -> List[Union[int, str]]:
        if not cls._SOURCE_PEERS_STR:
            return []
        
        peers = []
        for p in cls._SOURCE_PEERS_STR.split(","):
            p = p.strip()
            if not p:
                continue
            
            # Try to convert to int (for IDs like -100xxx)
            try:
                if p.startswith("-"):
                     peers.append(int(p))
                elif p.isdigit():
                     peers.append(int(p))
                else:
                    peers.append(p)
            except ValueError:
                peers.append(p)
        return peers

    @classmethod
    def validate(cls):
        missing = []
        if not cls.API_ID: missing.append("API_ID")
        if not cls.API_HASH: missing.append("API_HASH")
        # Optional: check NFIP tokens if you want them required at startup
        # if not cls.NFIP_CLIENT_TOKEN: missing.append("NFIP_CLIENT_TOKEN")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        try:
            cls.API_ID = int(cls.API_ID)
        except ValueError:
            raise ValueError("API_ID must be an integer.")

config = Config()
