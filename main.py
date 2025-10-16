from typing import Union
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import Response
import requests
from json import loads
import logging
from fastapi.responses import StreamingResponse
import requests
import io
import time
from functools import wraps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = "https://raw.githubusercontent.com/ivan2282-i28/MoonLightRepo/refs/heads/main/"

app = FastAPI()

def get_mods():
    dat = requests.get(ROOT + "mods.json")
    data = loads(dat.text)
    return data

def get_news():
    dat = requests.get(ROOT + "news.json")
    data = loads(dat.text)
    return data

def get_new(id: int):
    dat1 = requests.get(ROOT + f"news/{id}/new.json")
    dat2 = requests.get(ROOT + f"news/{id}/new.md")
    data = loads(dat1.text)
    data["content"] = dat2.text
    return data

def get_mod(id: str):
    dat = requests.get(ROOT + f"mods/{id}/mod.json")
    data = loads(dat.text)
    return data

def get_mod_version(id: int, version: str):
    data = requests.get(ROOT + f"mods/{id}/version/{version}/mod.dll")
    return data.content

def retry_handler(max_retries=10):
    """Decorator to retry handler execution on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(f"Handler {func.__name__} failed with exception: {e}. Attempt {attempt + 1}/{max_retries}")
                    
                    # Exponential backoff
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # 1, 2, 4, 8... seconds
            
            # If we've exhausted all retries, raise the last exception
            logger.error(f"Handler {func.__name__} failed after {max_retries} attempts: {last_exception}")
            raise last_exception
        return wrapper
    return decorator

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/api/v2/mods")
def read_item(limit: int = 20, offset: int = 0):
    try:
        data = get_mods()
        all_mods = data.get("mods", [])
        
        if offset < 0 or limit < 0:
            raise HTTPException(status_code=400, detail="Offset and limit must be non-negative")
        
        paginated_mods = all_mods[offset:offset + limit]
        
        mods = []
        for mod_id in paginated_mods:
            mod_data = get_mod(mod_id)
            mod_info = {
                "self": f"/api/v1/mods/{mod_id}",
                "mod_id": mod_id,
                "mod_name": mod_data.get("title"),
                "author": mod_data.get("author"),
                "downloads": 10000000,
                "thumbnail": f"/api/v1/mods/{mod_id}/thumbnail",
                "created_at": mod_data.get("created")
            }
            mods.append(mod_info)
        
        return {
            "mods": mods,
            "pagination": {
                "offset": offset,
                "limit": limit,
                "total": len(all_mods)
            }
        }
    
    except Exception as e:
        logger.error(f"Error in /api/v2/mods: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v2/mods/trending")
def read_item():
    try:
        data = get_mods()
        trending_data = data["trending"]
        mods = []
        for i in trending_data:
            mod = get_mod(i)
            readmod = {
                "self": f"/api/v1/mods/{i}",
                "mod_id": i,
                "mod_name": mod["title"],
                "author": mod["author"],
                "downloads": 10000000,
                "thumbnail": f"/api/v1/mods/{i}/thumbnail",
                "created_at": mod["created"]
            }
            mods.append(readmod)
        return mods
    except Exception as e:
        logger.error(f"Error in /api/v2/mods/trending: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/trending")
def read_item():
    result = requests.request("GET","https://starlight.allofus.dev/api/v1/mods/trending")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods")
def read_item(limit: int = 20, offset: int = 0):
    result = requests.request("GET","https://starlight.allofus.dev/api/v1/mods/",params={"limit":limit,"offset":offset})
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/total")
def read_item():
    result = requests.request("GET","https://starlight.allofus.dev/api/v1/mods/total")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}")
def read_item(id: str):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/thumbnail")
def read_item(id: str):
    result = requests.get(f"https://starlight.allofus.dev/api/v1/mods/{id}/thumbnail", stream=True)
    
    # Get the actual content type from the response
    content_type = result.headers.get('content-type', 'image/png')
    
    # For thumbnails, use 'inline' instead of 'attachment' to display in browser
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=content_type,
        headers={
            'Content-Disposition': f'inline; filename="{id}_thumbnail"'
        }
    )

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/versions")
def read_item(id: str):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}/versions")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/versions/{id2}")
def read_item(id: str, id2 : str):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}/versions/{id2}")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/versions/{id2}/dependencies")
def read_item(id: str, id2 : str):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}/versions/{id2}/dependencies")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/versions/{id2}/file")
def read_item(id: str, id2: str):
    result = requests.get(f"https://starlight.allofus.dev/api/v1/mods/{id}/versions/{id2}/file", stream=True)
    
    # Return as streaming response
    return StreamingResponse(
        io.BytesIO(result.content),
        media_type=result.headers.get('content-type', 'application/octet-stream'),
        headers={
            'Content-Disposition': f'attachment; filename="{id}.dll"'
        }
    )

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/links")
def read_item(id: str):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}/links")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/links/{id2}")
def read_item(id: str, id2 : int):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}/links/{id2}")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/mods/{id}/tags")
def read_item(id: str):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/mods/{id}/tags")
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/news")
def read_item(limit: int = 20, offset: int = 0):
    result = requests.request("GET","https://starlight.allofus.dev/api/v1/news/",params={"limit":limit,"offset":offset})
    return result.json()

@retry_handler(max_retries=10)
@app.get("/api/v1/news/{id}")
def read_item(id:int):
    result = requests.request("GET",f"https://starlight.allofus.dev/api/v1/news/{id}")
    return result.json()