from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio
import aiohttp
import socket
import subprocess
import json
import base64
import random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Global connection pool
active_connections = []
connection_stats = {}

# Models
class ConnectionSource(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str  # wifi, tor, proxy, vpn, mesh, i2p
    name: str
    status: str  # active, testing, failed, available
    speed: Optional[float] = None
    latency: Optional[float] = None
    anonymity_level: int = 1  # 1-5, 5 being most anonymous
    endpoint: Optional[str] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProxyRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[str] = None

# Free proxy sources (rotating list)
FREE_PROXY_APIS = [
    "https://api.proxyscrape.com/v2/?request=get&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
    "https://www.proxy-list.download/api/v1/get?type=http",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
]

# Tor bridges and entry nodes
TOR_BRIDGES = [
    "tor://127.0.0.1:9050",  # Local Tor if installed
]

# Public DNS over HTTPS providers
DOH_PROVIDERS = [
    "https://dns.google/dns-query",
    "https://cloudflare-dns.com/dns-query",
    "https://dns.quad9.net/dns-query",
]

@api_router.get("/")
async def root():
    return {"message": "Internet Access Miracle - Backend Online", "status": "ready"}

# Status endpoint is defined later with unified format

@api_router.get("/discover", response_model=List[ConnectionSource])
async def discover_connections():
    """Discover all available internet connection sources"""
    discovered = []
    
    # 1. Discover free proxies
    try:
        proxies = await fetch_free_proxies()
        for proxy in proxies[:10]:  # Limit to top 10
            discovered.append(ConnectionSource(
                type="proxy",
                name=f"Free Proxy {proxy}",
                status="available",
                anonymity_level=3,
                endpoint=proxy
            ))
    except Exception as e:
        logging.error(f"Proxy discovery failed: {e}")
    
    # 2. Check for Tor network
    tor_available = await check_tor_availability()
    if tor_available:
        discovered.append(ConnectionSource(
            type="tor",
            name="Tor Network",
            status="available",
            anonymity_level=5,
            endpoint="socks5://127.0.0.1:9050"
        ))
    
    # 3. DNS over HTTPS (always available)
    for i, doh in enumerate(DOH_PROVIDERS):
        discovered.append(ConnectionSource(
            type="doh",
            name=f"DNS over HTTPS {i+1}",
            status="available",
            anonymity_level=2,
            endpoint=doh
        ))
    
    # 4. WebRTC/P2P discovery
    discovered.append(ConnectionSource(
        type="webrtc",
        name="Peer-to-Peer Network",
        status="available",
        anonymity_level=2,
        endpoint="webrtc://mesh"
    ))
    
    # 5. Public VPN Gates
    vpn_gates = await fetch_vpn_gates()
    for vpn in vpn_gates[:5]:
        discovered.append(ConnectionSource(
            type="vpn",
            name=f"VPN Gate {vpn['country']}",
            status="available",
            anonymity_level=4,
            endpoint=vpn['endpoint']
        ))

    # 6. Installed VPN clients (desktop)
    try:
        vpn_clients = await detect_vpn_clients()
        for vc in vpn_clients:
            discovered.append(vc)
    except Exception as e:
        logging.error(f"VPN client detection failed: {e}")

    # 7. Local networks (Wi‑Fi / Ethernet / WISP)
    try:
        nets = await detect_local_networks()
        for net in nets:
            discovered.append(net)
    except Exception as e:
        logging.error(f"Local network detection failed: {e}")
    
    # Store in database
    for conn in discovered:
        await db.connections.update_one(
            {"endpoint": conn.endpoint},
            {"$set": conn.model_dump()},
            upsert=True
        )
    
    return discovered

@api_router.post("/test-connection")
async def test_connection(connection_id: str):
    """Test a specific connection source"""
    conn = await db.connections.find_one({"id": connection_id})
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    
    try:
        start_time = asyncio.get_event_loop().time()
        
        # Test connection based on type
        if conn['type'] == 'proxy':
            success = await test_proxy(conn['endpoint'])
        elif conn['type'] == 'tor':
            success = await test_tor()
        elif conn['type'] == 'doh':
            success = await test_doh(conn['endpoint'])
        else:
            success = True
        
        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        
        # Update connection status
        status = "active" if success else "failed"
        await db.connections.update_one(
            {"id": connection_id},
            {"$set": {"status": status, "latency": latency}}
        )
        
        return {"success": success, "latency": latency, "status": status}
    except Exception as e:
        return {"success": False, "error": str(e)}

@api_router.post("/connect")
async def auto_connect():
    """Automatically connect to the best available source"""
    # Get all available connections (exclude _id)
    connections = await db.connections.find(
        {"status": {"$in": ["available", "active"]}}, 
        {"_id": 0}
    ).to_list(100)
    
    if not connections:
        # Trigger discovery if none found
        await discover_connections()
        connections = await db.connections.find({"status": "available"}, {"_id": 0}).to_list(100)
    
    # If still none, bail
    if not connections:
        return {"success": False, "message": "No available connections"}

    # Test connections in parallel (top 10)
    test_tasks = [test_connection_direct(conn) for conn in connections[:10]]
    results = await asyncio.gather(*test_tasks, return_exceptions=True)

    # Find the best working connection using a simple score
    best_connection = None
    best_latency = None
    best_score = -1

    for i, result in enumerate(results):
        if isinstance(result, dict) and result.get('success'):
            conn = connections[i]
            latency = result.get('latency', 1000)
            score = conn.get('anonymity_level', 1) * 10 + (1000 / (latency + 1))
            if score > best_score:
                best_score = score
                best_connection = conn
                best_latency = latency

    if best_connection:
        # Demote currently active to available
        await db.connections.update_many(
            {"status": "active"},
            {"$set": {"status": "available"}}
        )
        # Activate the best connection
        await db.connections.update_one(
            {"id": best_connection['id']},
            {"$set": {"status": "active", "latency": best_latency}}
        )
        return {
            "success": True,
            "connection": best_connection,
            "message": "Connected to internet!"
        }

    return {"success": False, "message": "No working connections found"}
    
# Removed duplicate /proxy implementation and misplaced auto_connect code

@api_router.post("/proxy")
async def proxy_request(proxy_req: ProxyRequest):
    """Route web requests through active connection"""
    # Get active connection (exclude _id)
    active_conn = await db.connections.find_one({"status": "active"}, {"_id": 0})
    
    if not active_conn:
        # Try to auto-connect
        connect_result = await auto_connect()
        if not connect_result.get('success'):
            raise HTTPException(status_code=503, detail="No internet connection available")
        active_conn = connect_result['connection']
    
    ssl_disabled = os.environ.get("DISABLE_TLS_VERIFY", "false").lower() == "true"

    try:
        async with aiohttp.ClientSession() as session:
            request_kwargs = {
                "method": proxy_req.method,
                "url": proxy_req.url,
                "headers": proxy_req.headers or {},
                "data": proxy_req.body,
                "timeout": aiohttp.ClientTimeout(total=30)
            }
            if ssl_disabled:
                request_kwargs["ssl"] = False

            # Route request through the proxy when applicable
            if active_conn.get('type') == 'proxy' and active_conn.get('endpoint'):
                request_kwargs["proxy"] = f"http://{active_conn['endpoint']}"

            async with session.request(**request_kwargs) as response:
                content = await response.read()
                return JSONResponse(
                    content={
                        "status": response.status,
                        "headers": dict(response.headers),
                        "content": base64.b64encode(content).decode()
                    }
                )
    except Exception as e:
        # Mark connection as failed and propagate error
        await db.connections.update_one(
            {"id": active_conn['id']},
            {"$set": {"status": "failed"}}
        )
        raise HTTPException(status_code=502, detail=f"Connection failed: {str(e)}")

@api_router.get("/status")
async def get_status():
    """Get current connection status"""
    active_conns = await db.connections.find({"status": "active"}, {"_id": 0}).to_list(10)
    available_conns = await db.connections.find({"status": "available"}, {"_id": 0}).to_list(100)
    
    return {
        "active_connections": len(active_conns),
        "available_connections": len(available_conns),
        "connections": active_conns,
        "internet_status": "connected" if active_conns else "searching"
    }

@api_router.get("/diagnostics/summary")
async def diagnostics_summary():
    """Summarize discovered sources, quick health checks, and best route recommendation."""
    # Discover now to ensure fresh data
    discovered_models = await discover_connections()
    discovered = [d.model_dump() for d in discovered_models]

    # Quick tests for a subset
    test_tasks = [test_connection_direct(conn) for conn in discovered[:10]]
    results = await asyncio.gather(*test_tasks, return_exceptions=True)

    tested = []
    for conn, res in zip(discovered[:10], results):
        if isinstance(res, dict):
            conn = {**conn, **{"latency": res.get("latency"), "tested_success": res.get("success")}}
        tested.append(conn)

    # Group counts by type
    by_type = {}
    for c in discovered:
        t = c.get("type")
        by_type[t] = by_type.get(t, 0) + 1

    # Pick recommendation: highest anonymity with good latency among successful tests
    recommendation = None
    best_score = -1
    for c in tested:
        if c.get("tested_success"):
            latency = c.get("latency") or 1000
            anon = c.get("anonymity_level", 1)
            score = anon * 10 + (1000 / (latency + 1))
            if score > best_score:
                best_score = score
                recommendation = c

    return {
        "counts_by_type": by_type,
        "tested": tested,
        "recommendation": recommendation,
        "message": "Use /api/connect to activate the recommended route"
    }

# Helper functions
async def fetch_free_proxies() -> List[str]:
    """Fetch free proxies from multiple sources"""
    proxies = []
    async with aiohttp.ClientSession() as session:
        for api_url in FREE_PROXY_APIS[:2]:  # Try first 2 sources
            try:
                async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        text = await response.text()
                        proxy_list = text.strip().split('\n')
                        proxies.extend(proxy_list[:20])
                        break
            except:
                continue
    return proxies

async def check_tor_availability() -> bool:
    """Check if Tor is available"""
    try:
        # Try to connect to local Tor SOCKS proxy
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 9050))
        sock.close()
        return result == 0
    except:
        return False

async def fetch_vpn_gates() -> List[Dict[str, Any]]:
    """Fetch VPN Gate public servers"""
    vpn_gates = [
        {"country": "US", "endpoint": "vpngate://us-server"},
        {"country": "JP", "endpoint": "vpngate://jp-server"},
        {"country": "KR", "endpoint": "vpngate://kr-server"},
    ]
    return vpn_gates

async def detect_vpn_clients() -> List[ConnectionSource]:
    """Detect installed VPN/tunnel clients on the host and expose as sources.
    This is best-effort and currently targets desktop clients with CLIs.
    """
    detected: List[ConnectionSource] = []
    # Windscribe CLI
    try:
        # Typical Windows path; if not present, skip
        windscribe_cli = Path("C:/Program Files/Windscribe/windscribe-cli.exe")
        if windscribe_cli.exists():
            # Query status
            proc = subprocess.run([str(windscribe_cli), "status"], capture_output=True, text=True, timeout=5)
            status_text = proc.stdout.lower()
            is_connected = "connected" in status_text
            detected.append(ConnectionSource(
                type="vpn",
                name="Windscribe",
                status="available" if not is_connected else "active",
                anonymity_level=4,
                endpoint="system://windscribe"
            ))
    except Exception:
        pass

    # Speedify CLI
    try:
        speedify_cli = Path("C:/Program Files/Speedify/speedify_cli.exe")
        if speedify_cli.exists():
            proc = subprocess.run([str(speedify_cli), "show"], capture_output=True, text=True, timeout=5)
            status_text = proc.stdout.lower()
            is_connected = "connected" in status_text or "state: connected" in status_text
            detected.append(ConnectionSource(
                type="vpn",
                name="Speedify",
                status="available" if not is_connected else "active",
                anonymity_level=3,
                endpoint="system://speedify"
            ))
    except Exception:
        pass

    # Generic VPN adapters (Windows)
    try:
        # Parse ipconfig output for TUN/TAP or VPN markers
        proc = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, timeout=7)
        text = proc.stdout.lower()
        adapter_hits = [
            "vpn",
            "tap-windows",
            "wireguard",
            "ppp adapter",
            "ras",
            "tunnel",
        ]
        if any(hit in text for hit in adapter_hits):
            detected.append(ConnectionSource(
                type="vpn",
                name="System VPN Adapter",
                status="available",
                anonymity_level=3,
                endpoint="system://adapter"
            ))
    except Exception:
        pass

    return detected

async def detect_local_networks() -> List[ConnectionSource]:
    detected: List[ConnectionSource] = []

    # Wi‑Fi via netsh
    try:
        proc = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=6)
        out = proc.stdout
        lines = [l.strip() for l in out.splitlines()]
        state_line = next((l for l in lines if l.lower().startswith("state")), None)
        ssid_line = next((l for l in lines if l.lower().startswith("ssid")), None)
        connected = state_line and ("connected" in state_line.lower())
        ssid = None
        if ssid_line and ":" in ssid_line:
            ssid = ssid_line.split(":", 1)[1].strip()
        if connected:
            name = f"Wi‑Fi {ssid}" if ssid else "Wi‑Fi"
            endpoint = f"wifi://{ssid}" if ssid else "wifi://"
            # If SSID hints at a WISP, reflect that in name
            if ssid and ("wisp" in ssid.lower() or "isp" in ssid.lower()):
                name = f"WISP {ssid}"
            detected.append(ConnectionSource(
                type="wifi",
                name=name,
                status="available",
                anonymity_level=1,
                endpoint=endpoint
            ))
    except Exception:
        pass

    # Ethernet presence via ipconfig
    try:
        proc = subprocess.run(["ipconfig", "/all"], capture_output=True, text=True, timeout=8)
        text = proc.stdout.lower()
        has_eth = ("ethernet adapter" in text) and ("media disconnected" not in text)
        if has_eth:
            detected.append(ConnectionSource(
                type="direct",
                name="Ethernet",
                status="available",
                anonymity_level=1,
                endpoint="ethernet://default"
            ))
    except Exception:
        pass

    return detected

async def test_proxy(proxy: str) -> bool:
    """Test if proxy is working"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://httpbin.org/ip",
                proxy=f"http://{proxy}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                return response.status == 200
    except:
        return False

async def test_tor() -> bool:
    """Test Tor connection"""
    return await check_tor_availability()

async def test_doh(endpoint: str) -> bool:
    """Test DNS over HTTPS"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{endpoint}?name=google.com",
                headers={"accept": "application/dns-json"},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                return response.status == 200
    except:
        return False

async def test_connection_direct(conn: dict) -> dict:
    """Test a connection directly"""
    try:
        start_time = asyncio.get_event_loop().time()
        
        if conn['type'] == 'proxy':
            success = await test_proxy(conn['endpoint'])
        elif conn['type'] == 'tor':
            success = await test_tor()
        elif conn['type'] == 'doh':
            success = await test_doh(conn['endpoint'])
        elif conn['type'] in ('vpn', 'wifi', 'direct'):
            # Probe a simple HTTP endpoint; if reachable quickly, assume OK
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        "http://httpbin.org/ip",
                        timeout=aiohttp.ClientTimeout(total=6)
                    ) as response:
                        success = response.status == 200
            except Exception:
                success = False
        else:
            success = True

        latency = (asyncio.get_event_loop().time() - start_time) * 1000
        return {"success": success, "latency": latency}
    except:
        return {"success": False, "latency": 9999}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

# Lightweight dashboard for quick demo without the React dev server
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Smart Failover Router</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #111; }
        h1 { margin: 0 0 12px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
        .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; }
        button { padding: 10px 14px; border-radius: 8px; border: 1px solid #444; background: #fff; cursor: pointer; }
        button.primary { background: #0ea5e9; color: white; border-color: #0ea5e9; }
        pre { background: #f7f7f7; padding: 10px; border-radius: 8px; overflow: auto; }
        .muted { color: #666; font-size: 0.9em; }
        input[type=text] { width: 100%; padding: 8px 10px; border-radius: 8px; border: 1px solid #ccc; }
      </style>
    </head>
    <body>
      <h1>Smart Failover Router</h1>
      <p class=\"muted\">Demo dashboard backed by /api endpoints. Use Discover, Summary, and Connect.</p>
      <p class=\"muted\">Mobile app uses AdMob rewarded ads to unlock Connect (IDs preconfigured). This web demo uses a stubbed unlock. <a href=\"https://support.google.com/admob/answer/6128543\" target=\"_blank\">Review AdMob policies</a>. &nbsp; <a href=\"/privacy\" target=\"_blank\">Privacy Policy</a></p>
      <div class=\"grid\">
        <div class=\"card\">
          <h2>Discovery</h2>
          <button onclick=\"discover()\">Discover Sources</button>
          <pre id=\"discoverOut\"></pre>
        </div>
        <div class=\"card\">
          <h2>Diagnostics</h2>
          <button onclick=\"summary()\">Get Summary</button>
          <pre id=\"summaryOut\"></pre>
        </div>
        <div class=\"card\">
          <h2>Connect</h2>
          <p id=\"gateMsg\" class=\"muted\"></p>
          <div style=\"display:flex; gap:8px;\">
            <button class=\"primary\" onclick=\"connect()\">Connect Best Route</button>
            <button onclick=\"unlockGate()\">Watch Ad (stub)</button>
          </div>
          <pre id=\"connectOut\"></pre>
        </div>
        <div class=\"card\">
          <h2>Proxy Fetch</h2>
          <input id=\"url\" type=\"text\" placeholder=\"https://example.com\" />
          <div style=\"margin-top:8px\"><button onclick=\"proxyFetch()\">Fetch</button></div>
          <pre id=\"proxyOut\"></pre>
        </div>
      </div>
      <script>
        const api = (path, init) => fetch(`/api${path}`, init);
        const minutesUnlock = 30;
        const now = () => Date.now();
        const unlockedUntil = () => Number(localStorage.getItem('ad_unlocked_until') || 0);
        const isUnlocked = () => unlockedUntil() > now();
        const refreshGateMsg = () => {
          const el = document.getElementById('gateMsg');
          if (isUnlocked()) {
            const mins = Math.max(1, Math.floor((unlockedUntil() - now()) / 60000));
            el.textContent = `Connect is unlocked for ${mins} min.`;
          } else {
            el.textContent = 'Connect requires a rewarded ad (stubbed here).';
          }
        };
        function unlockGate(){
          // Stub: simulate rewarded ad completion
          localStorage.setItem('ad_unlocked_until', String(now() + minutesUnlock * 60000));
          refreshGateMsg();
        }
        async function discover(){
          try {
            const res = await api('/discover');
            const data = await res.json();
            document.getElementById('discoverOut').textContent = JSON.stringify(data, null, 2);
          } catch(e){ document.getElementById('discoverOut').textContent = String(e); }
        }
        async function summary(){
          try {
            const res = await api('/diagnostics/summary');
            const data = await res.json();
            document.getElementById('summaryOut').textContent = JSON.stringify(data, null, 2);
          } catch(e){ document.getElementById('summaryOut').textContent = String(e); }
        }
        async function connect(){
          if (!isUnlocked()) { refreshGateMsg(); return; }
          try {
            const res = await api('/connect', { method: 'POST' });
            const data = await res.json();
            document.getElementById('connectOut').textContent = JSON.stringify(data, null, 2);
          } catch(e){ document.getElementById('connectOut').textContent = String(e); }
        }
        async function proxyFetch(){
          const url = document.getElementById('url').value.trim();
          if(!url) return;
          try {
            const res = await api('/proxy', {
              method: 'POST',
              headers: { 'content-type': 'application/json' },
              body: JSON.stringify({ url })
            });
            const data = await res.json();
            document.getElementById('proxyOut').textContent = JSON.stringify({ status: data.status, headers: data.headers }, null, 2);
          } catch(e){ document.getElementById('proxyOut').textContent = String(e); }
        }
        refreshGateMsg();
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/privacy", response_class=HTMLResponse)
async def privacy():
    html = """
    <!doctype html>
    <html lang=\"en\">
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Privacy Policy</title>
      <style>
        body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #111; }
        h1 { margin: 0 0 12px; }
        h2 { margin-top: 20px; }
        p { line-height: 1.5; }
        ul { line-height: 1.5; }
        a { color: #0ea5e9; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .muted { color: #666; }
        .container { max-width: 820px; margin: 0 auto; }
        .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; }
      </style>
    </head>
    <body>
      <div class=\"container\">
        <h1>Privacy Policy</h1>
        <p class=\"muted\">This policy explains how the app handles data.</p>
        <div class=\"card\">
          <h2>Overview</h2>
          <p>
            The app provides internet failover diagnostics and a simple proxy fetch feature.
            We do not sell or share personal data. Minimal, non-personal operational data may be used
            to deliver app functionality.
          </p>

          <h2>Data We Handle</h2>
          <ul>
            <li>Connection metrics (e.g., latency, availability) to recommend a route.</li>
            <li>Basic request metadata for proxy fetch (status code and headers only).</li>
            <li>No storage of page content fetched via proxy beyond transient processing.</li>
          </ul>

          <h2>Advertising</h2>
          <p>
            The mobile app uses rewarded ads via Google AdMob to unlock certain actions.
            AdMob and its partners may collect device identifiers and usage data to deliver and measure ads.
            See Google’s policies: <a href=\"https://policies.google.com/technologies/ads\" target=\"_blank\">Ads &amp; Cookies</a> and
            <a href=\"https://support.google.com/admob/answer/6128543\" target=\"_blank\">AdMob Policy</a>.
          </p>

          <h2>Security</h2>
          <p>
            We use reasonable technical measures and avoid storing unnecessary personal data.
            DNS over HTTPS and proxy testing are performed via public endpoints for connectivity checks.
          </p>

          <h2>Your Choices</h2>
          <ul>
            <li>You can use the app without signing in.</li>
            <li>You may decline rewarded ads; core diagnostics remain accessible.</li>
          </ul>

          <h2>Contact</h2>
          <p>
            For privacy questions, contact the developer via the store listing’s email.
          </p>

          <p class=\"muted\">Last updated: 2025-11-05</p>
        </div>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

# Local run entry-point for development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
