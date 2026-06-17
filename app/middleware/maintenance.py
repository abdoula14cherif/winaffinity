"""
Middleware mode maintenance via Supabase
"""
from fastapi import Request
from fastapi.responses import HTMLResponse

async def maintenance_middleware(request: Request, call_next):
    exempt = ["/admin", "/auth/login", "/auth/logout", "/assets/", "/sw.js"]
    path = request.url.path
    if any(path.startswith(e) for e in exempt):
        return await call_next(request)
    try:
        from app.database import get_supabase
        db = get_supabase()
        res = db.table("settings").select("value").eq("key", "maintenance").execute()
        if res.data and res.data[0]["value"] == "true":
            msg_res = db.table("settings").select("value").eq("key", "maintenance_message").execute()
            msg = msg_res.data[0]["value"] if msg_res.data else "Site en maintenance. Revenez bientôt !"
            html = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>WIN AFFINITY — Maintenance</title>
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap" rel="stylesheet"/>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Poppins",sans-serif;background:linear-gradient(135deg,#1A3A5C,#2D5F8F);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#fff;text-align:center;padding:20px}
.box{max-width:480px}
.ico{font-size:70px;margin-bottom:20px}
h1{font-size:28px;font-weight:800;margin-bottom:10px}
p{font-size:14px;color:rgba(255,255,255,.7);line-height:1.6;margin-bottom:20px}
.badge{display:inline-flex;align-items:center;gap:8px;background:rgba(255,107,53,.2);border:1.5px solid rgba(255,107,53,.4);border-radius:20px;padding:8px 20px;font-size:13px;font-weight:600;color:#FF8C5A}
</style>
</head>
<body>
<div class="box">
  <div class="ico">🔧</div>
  <h1>Maintenance en cours</h1>
  <p>""" + msg + """</p>
  <div class="badge">⏰ Revenez bientôt</div>
</div>
</body></html>"""
            return HTMLResponse(content=html, status_code=503)
    except Exception:
        pass
    return await call_next(request)
