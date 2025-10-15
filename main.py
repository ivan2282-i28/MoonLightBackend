from typing import Union
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
import httpx
from urllib.parse import urljoin
from starlette.routing import Match
import requests
from json import loads
import logging

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

async def is_route_handled(request: Request) -> bool:
    """
    Check if the current route and method are handled by our application
    """
    for route in app.routes:
        # Skip the catch-all route itself
        if hasattr(route, 'path') and route.path == '/{path:path}':
            continue
            
        if hasattr(route, 'methods') and request.method in route.methods:
            match, _ = route.matches(request.scope)
            if match == Match.FULL:
                return True
    return False

async def forward_to_example_com(request: Request) -> Response:
    """
    Forward the request to starlight.allofus.dev and return the response
    """
    target_url = urljoin("https://starlight.allofus.dev", str(request.url.path))
    
    if request.url.query:
        target_url += f"?{request.url.query}"
    
    logger.info(f"Forwarding request to: {target_url}")
    
    # Prepare headers (remove some that shouldn't be forwarded)
    headers = dict(request.headers)
    headers_to_remove = ['host', 'content-length', 'content-encoding']
    for header in headers_to_remove:
        headers.pop(header, None)
    
    # Add a user agent if not present
    if 'user-agent' not in headers:
        headers['user-agent'] = 'MoonLight-Proxy/1.0'
    
    try:
        async with httpx.AsyncClient() as client:
            # Forward the request with same method, headers, and body
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=await request.body() if request.method in ["POST", "PUT", "PATCH"] else None,
                timeout=30.0,
                follow_redirects=True
            )
            
            logger.info(f"Received response from {target_url}: {response.status_code}")
            
            # Filter out problematic headers that should not be forwarded
            response_headers = dict(response.headers)
            
            # Remove conflicting headers that cause the "Content-Length" and "Transfer-Encoding" issue
            headers_to_remove_from_response = [
                'transfer-encoding', 
                # 'content-encoding',
                'content-length'
            ]
            
            for header in headers_to_remove_from_response:
                response_headers.pop(header, None)
            
            # Return the response from starlight.allofus.dev
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=response_headers
            )
    except httpx.ConnectError as e:
        logger.error(f"Connection error forwarding to {target_url}: {e}")
        raise HTTPException(status_code=502, detail=f"Cannot connect to upstream server: {str(e)}")
    except httpx.TimeoutException as e:
        logger.error(f"Timeout forwarding to {target_url}: {e}")
        raise HTTPException(status_code=504, detail=f"Upstream server timeout: {str(e)}")
    except httpx.RequestError as e:
        logger.error(f"Request error forwarding to {target_url}: {e}")
        raise HTTPException(status_code=502, detail=f"Error forwarding request: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error forwarding to {target_url}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Catch-all route for unhandled paths and methods - MUST BE LAST
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def catch_all(request: Request, path: str):
    logger.info(f"Catch-all route called: {request.method} {request.url.path}")
    
    # Check if this specific route-method combination is handled by our app
    if await is_route_handled(request):
        logger.info(f"Route {request.url.path} is handled locally but not found")
        raise HTTPException(status_code=404, detail="Route not found")
    
    # Forward request to starlight.allofus.dev
    return await forward_to_example_com(request)

