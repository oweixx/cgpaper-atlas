"""Cached public metadata requests. Authentication stays in request headers."""
import hashlib,json,time,threading
from datetime import datetime,timezone
import requests
from cg_config import CACHE
LOCK=threading.Lock()
NEXT=0

def fetch(url,headers=None,refresh=False):
    global NEXT
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding='utf-8'))
    CACHE.mkdir(parents=True,exist_ok=True)
    for attempt in range(6):
        with LOCK:
            time.sleep(max(0,NEXT-time.monotonic()))
            NEXT=time.monotonic()+.35
        try:
            response=requests.get(url,headers={'User-Agent':'CGPaperAtlas/1.0 (research metadata)',**(headers or {})},timeout=90)
            if response.status_code in [401,402,403,404]:
                raise RuntimeError(f'Metadata source HTTP {response.status_code}')
            if response.status_code==429 and any(t in response.text.lower() for t in ['daily','budget','credits']):
                raise RuntimeError('Daily API budget exhausted')
            if response.status_code in [429,500,502,503,504]:
                time.sleep(min(20,2**attempt));continue
            response.raise_for_status()
            result=response.json()
            path.write_text(json.dumps(result,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
            return result
        except (requests.RequestException,ValueError):
            if attempt==5: raise
            time.sleep(min(20,2**attempt))
    raise RuntimeError('Metadata source retries exhausted')

def retrieved(url):
    path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.json')
    return datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()

def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8',newline='\n')
