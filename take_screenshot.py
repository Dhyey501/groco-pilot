import asyncio
import base64
import json
import subprocess
import time
import urllib.request
import websockets

async def capture_all_screens():
    edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    cmd = [
        edge_path,
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "--window-size=1280,1080",
        "http://localhost:8501",
    ]
    proc = subprocess.Popen(cmd)
    try:
        ws_url = None
        for _ in range(20):
            time.sleep(0.5)
            try:
                resp = urllib.request.urlopen("http://127.0.0.1:9222/json")
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

            # Helper to navigate and capture
            async def navigate_and_capture(url, filename):
                await ws.send(json.dumps({"id": 200, "method": "Page.navigate", "params": {"url": url}}))
                await ws.recv()

                # Poll until skeletons disappear and main text appears (up to 15 seconds)
                for _ in range(30):
                    await asyncio.sleep(0.5)
                    await ws.send(json.dumps({
                        "id": 201,
                        "method": "Runtime.evaluate",
                        "params": {
                            "expression": """
                            (function() {
                                const skeletons = document.querySelectorAll('[data-testid="stSkeleton"]');
                                const text = document.body.innerText || '';
                                return skeletons.length === 0 && (text.includes('Urgent Attention') || text.includes('Total In Kitchen') || text.includes('GrocoPilot') || text.includes('Add Groceries'));
                            })()
                            """,
                            "returnByValue": True
                        }
                    }))
                    check_resp = json.loads(await ws.recv())
                    if check_resp.get("result", {}).get("result", {}).get("value") is True:
                        break

                await asyncio.sleep(1.5)

                msg = {"id": 202, "method": "Page.captureScreenshot", "params": {"format": "png"}}
                await ws.send(json.dumps(msg))
                resp = await ws.recv()
                data = json.loads(resp)
                with open(filename, "wb") as f:
                    f.write(base64.b64decode(data["result"]["data"]))
                print(f"Saved {filename}")

            # 1. Capture Dashboard
            await navigate_and_capture("http://localhost:8501/?page=Dashboard", "dashboard_preview.png")

            # 2. Capture Add Items
            await navigate_and_capture("http://localhost:8501/?page=Add", "add_items_preview.png")

            # 3. Capture Recipes
            await navigate_and_capture("http://localhost:8501/?page=Recipes", "recipes_preview.png")

            # 4. Capture Waste & Savings
            await navigate_and_capture("http://localhost:8501/?page=Waste", "waste_preview.png")




    finally:
        proc.terminate()
        proc.wait()

if __name__ == "__main__":
    asyncio.run(capture_all_screens())
