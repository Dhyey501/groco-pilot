import asyncio
import base64
import json
import subprocess
import time
import urllib.request
import websockets

async def snap_dashboard():
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    cmd = [
        edge_path,
        "--headless=new",
        "--remote-debugging-port=9223",
        "--disable-gpu",
        "--window-size=1280,1080",
        "http://localhost:8501/?page=Dashboard",
    ]
    proc = subprocess.Popen(cmd)
    try:
        ws_url = None
        for _ in range(25):
            time.sleep(0.5)
            try:
                resp = urllib.request.urlopen("http://127.0.0.1:9223/json")
                pages = json.loads(resp.read().decode())
                for p in pages:
                    if "localhost:8501" in p.get("url", ""):
                        ws_url = p.get("webSocketDebuggerUrl")
                        break
                if ws_url:
                    break
            except Exception:
                pass

        if not ws_url:
            print("Failed to get websocket debugger url")
            return

        async with websockets.connect(ws_url) as ws:
            # Emulate light mode
            await ws.send(json.dumps({
                "id": 100,
                "method": "Emulation.setEmulatedMedia",
                "params": {"media": "screen", "features": [{"name": "prefers-color-scheme", "value": "light"}]}
            }))
            await ws.recv()

            # Wait 5 seconds for complete render
            await asyncio.sleep(5)

            # Dismiss rerun/error banners
            await ws.send(json.dumps({
                "id": 101,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": """
                    document.querySelectorAll('[role="dialog"]').forEach(el => {
                        if (el.textContent.includes('Connection error')) {
                            (el.closest('[data-testid="stModal"]') || el).remove();
                        }
                    });
                    const closeBtn = document.querySelector('button[aria-label="Close"]');
                    if (closeBtn) closeBtn.click();
                    """
                }
            }))
            await ws.recv()
            await asyncio.sleep(1)

            msg = {"id": 102, "method": "Page.captureScreenshot", "params": {"format": "png"}}
            await ws.send(json.dumps(msg))
            resp = await ws.recv()
            data = json.loads(resp)
            with open("dashboard_preview.png", "wb") as f:
                f.write(base64.b64decode(data["result"]["data"]))
            print("Successfully captured clean dashboard_preview.png")
    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(snap_dashboard())
