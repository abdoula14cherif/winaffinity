"""
Panel Admin WIN AFFINITY
Accès réservé aux comptes role='admin'
"""
import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Annotated
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id

router = APIRouter(prefix="/admin", tags=["Admin"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_admin(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    user = await get_user_by_id(get_supabase(), payload["sub"])
    if not user or user.get("role") != "admin": return None
    return user

@router.get("", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    admin = await _get_admin(request)
    if not admin: return RedirectResponse("/auth/login", status_code=302)
    db = get_supabase()
    try:
        users = db.table("users").select("*").order("created_at", desc=True).execute().data or []
        payments = db.table("payments").select("*").order("created_at", desc=True).limit(50).execute().data or []
        withdrawals = db.table("withdrawals").select("*").order("created_at", desc=True).limit(50).execute().data or []
        commissions = db.table("commissions").select("*").order("created_at", desc=True).limit(50).execute().data or []
        tasks = db.table("tasks").select("*").order("created_at", desc=True).execute().data or []
        formations = db.table("formations").select("*").order("created_at", desc=True).execute().data or []
        groups = db.table("groups").select("*").order("created_at", desc=True).execute().data or []
        total_balance = sum(w.get("balance",0) for w in (db.table("wallets").select("balance").execute().data or []))
        stats = {
            "total_users": len(users),
            "active_users": len([u for u in users if u.get("is_active")]),
            "pending_users": len([u for u in users if not u.get("is_active")]),
            "total_withdrawals": len(withdrawals),
            "pending_withdrawals": len([w for w in withdrawals if w.get("status")=="pending"]),
            "total_commissions": sum(com.get("amount",0) for com in commissions),
            "total_balance": total_balance,
            "total_payments": len([p for p in payments if p.get("status")=="completed"]),
        }
    except Exception as e:
        logger.error("[ADMIN] Erreur chargement : %s", e)
        users, payments, withdrawals, commissions, tasks, formations, groups = [], [], [], [], [], [], []
        stats = {}
    return templates.TemplateResponse("admin.html", {
        "request": request, "admin": admin,
        "users": users, "payments": payments,
        "withdrawals": withdrawals, "tasks": tasks, "formations": formations, "groups": groups,
        "stats": stats,
    })

@router.post("/user/toggle-active")
async def toggle_active(request: Request, user_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    user = db.table("users").select("is_active").eq("id", user_id).execute().data
    if not user: return JSONResponse({"error": "Utilisateur introuvable"}, status_code=404)
    new_status = not user[0]["is_active"]
    db.table("users").update({"is_active": new_status}).eq("id", user_id).execute()
    if new_status:
        wallet = db.table("wallets").select("id").eq("user_id", user_id).execute().data
        if not wallet:
            db.table("wallets").insert({"user_id": user_id, "balance": 0, "total_earned": 0}).execute()
        from app.services.commission_service import process_commissions
        await process_commissions(db, user_id)
    logger.info("[ADMIN] Compte %s → is_active=%s", user_id, new_status)
    return JSONResponse({"success": True, "is_active": new_status})

@router.post("/withdrawal/approve")
async def approve_withdrawal(request: Request, withdrawal_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    wd = db.table("withdrawals").select("*").eq("id", withdrawal_id).execute().data
    db.table("withdrawals").update({"status": "approved"}).eq("id", withdrawal_id).execute()
    logger.info("[ADMIN] Retrait approuvé : %s", withdrawal_id)
    if wd:
        try:
            w = wd[0]
            user = db.table("users").select("email,full_name").eq("id", w["user_id"]).execute().data
            if user:
                from app.services.email_service import send_withdrawal_approved
                await send_withdrawal_approved(user[0]["email"], user[0]["full_name"], w["net_amount"], w["operator"], w["phone"])
        except Exception as e:
            pass
    return JSONResponse({"success": True})

@router.post("/withdrawal/reject")
async def reject_withdrawal(request: Request, withdrawal_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    wd = db.table("withdrawals").select("*").eq("id", withdrawal_id).execute().data
    if wd:
        w = wd[0]
        if w["status"] == "pending":
            wallet = db.table("wallets").select("balance").eq("user_id", w["user_id"]).execute().data
            if wallet:
                db.table("wallets").update({"balance": wallet[0]["balance"] + w["amount"]}).eq("user_id", w["user_id"]).execute()
    db.table("withdrawals").update({"status": "rejected"}).eq("id", withdrawal_id).execute()
    if wd:
        try:
            w = wd[0]
            user = db.table("users").select("email,full_name").eq("id", w["user_id"]).execute().data
            if user:
                from app.services.email_service import send_withdrawal_rejected
                await send_withdrawal_rejected(user[0]["email"], user[0]["full_name"], w["amount"])
        except Exception as e:
            pass
    return JSONResponse({"success": True})

@router.post("/task/add")
async def add_task(request: Request, title: Annotated[str, Form()], description: Annotated[str, Form()], reward: Annotated[int, Form()], link: Annotated[str, Form()] = "", task_type: Annotated[str, Form()] = "link", video_url: Annotated[str, Form()] = ""):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("tasks").insert({"title": title, "description": description, "reward": reward, "link": link or None, "type": task_type, "video_url": video_url or None}).execute()
    return JSONResponse({"success": True})

@router.post("/wallet/update")
async def update_wallet(request: Request, user_id: Annotated[str, Form()], balance: Annotated[int, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        wallet = db.table("wallets").select("*").eq("user_id", user_id).execute().data
        if wallet:
            db.table("wallets").update({"balance": balance}).eq("user_id", user_id).execute()
        else:
            db.table("wallets").insert({"user_id": user_id, "balance": balance, "total_earned": balance}).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/task/toggle")
async def toggle_task(request: Request, task_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    task = db.table("tasks").select("is_active").eq("id", task_id).execute().data
    if task:
        db.table("tasks").update({"is_active": not task[0]["is_active"]}).eq("id", task_id).execute()
    return JSONResponse({"success": True})

@router.post("/user/update")
async def update_user(request: Request, user_id: Annotated[str, Form()], full_name: Annotated[str, Form()], email: Annotated[str, Form()], phone: Annotated[str, Form()], role: Annotated[str, Form()], is_active: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        db.table("users").update({
            "full_name": full_name,
            "email": email.lower(),
            "phone": phone,
            "role": role,
            "is_active": is_active == "true"
        }).eq("id", user_id).execute()
        logger.info("[ADMIN] User mis à jour : %s", user_id)
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[ADMIN] Erreur update user : %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/user/update")
async def update_user(request: Request, user_id: Annotated[str, Form()], full_name: Annotated[str, Form()], email: Annotated[str, Form()], phone: Annotated[str, Form()], role: Annotated[str, Form()], is_active: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        db.table("users").update({
            "full_name": full_name,
            "email": email.lower(),
            "phone": phone,
            "role": role,
            "is_active": is_active == "true"
        }).eq("id", user_id).execute()
        logger.info("[ADMIN] User mis à jour : %s", user_id)
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[ADMIN] Erreur update user : %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/task/delete")
@router.post("/notification/send")
async def send_notif_all(request: Request, title: Annotated[str, Form()], message: Annotated[str, Form()], type: Annotated[str, Form()], target: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    from app.services.notification_service import send_notification, send_to_all
    if target == "all":
        await send_to_all(db, title, message, type)
    else:
        users = db.table("users").select("id").eq("is_active", True).execute().data or []
        for u in users:
            await send_notification(db, u["id"], title, message, type)
    return JSONResponse({"success": True})

@router.post("/user/update")
async def update_user(request: Request, user_id: Annotated[str, Form()], full_name: Annotated[str, Form()], email: Annotated[str, Form()], phone: Annotated[str, Form()], role: Annotated[str, Form()], is_active: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        db.table("users").update({
            "full_name": full_name,
            "email": email.lower(),
            "phone": phone,
            "role": role,
            "is_active": is_active == "true"
        }).eq("id", user_id).execute()
        logger.info("[ADMIN] User mis à jour : %s", user_id)
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[ADMIN] Erreur update user : %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/user/update")
async def update_user(request: Request, user_id: Annotated[str, Form()], full_name: Annotated[str, Form()], email: Annotated[str, Form()], phone: Annotated[str, Form()], role: Annotated[str, Form()], is_active: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        db.table("users").update({
            "full_name": full_name,
            "email": email.lower(),
            "phone": phone,
            "role": role,
            "is_active": is_active == "true"
        }).eq("id", user_id).execute()
        logger.info("[ADMIN] User mis à jour : %s", user_id)
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[ADMIN] Erreur update user : %s", e)
        return JSONResponse({"error": str(e)}, status_code=500)

@router.post("/task/delete")
@router.post("/formation/add")
async def add_formation(request: Request, title: Annotated[str, Form()], description: Annotated[str, Form()], category: Annotated[str, Form()], link: Annotated[str, Form()] = ""):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("formations").insert({"title": title, "description": description, "category": category, "link": link or None}).execute()
    return JSONResponse({"success": True})

@router.post("/formation/toggle")
async def toggle_formation(request: Request, formation_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    f = db.table("formations").select("is_active").eq("id", formation_id).execute().data
    if f: db.table("formations").update({"is_active": not f[0]["is_active"]}).eq("id", formation_id).execute()
    return JSONResponse({"success": True})

@router.post("/formation/delete")
async def delete_formation(request: Request, formation_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("formations").delete().eq("id", formation_id).execute()
    return JSONResponse({"success": True})

@router.post("/group/add")
async def add_group(request: Request, name: Annotated[str, Form()], description: Annotated[str, Form()], category: Annotated[str, Form()], link: Annotated[str, Form()], members: Annotated[str, Form()] = "0"):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("groups").insert({"name": name, "description": description, "category": category, "link": link, "members": int(members or 0)}).execute()
    return JSONResponse({"success": True})

@router.post("/group/delete")
async def delete_group(request: Request, group_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("groups").delete().eq("id", group_id).execute()
    return JSONResponse({"success": True})

@router.post("/task/delete")
async def delete_task(request: Request, task_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("tasks").delete().eq("id", task_id).execute()
    return JSONResponse({"success": True})

@router.post("/announcement/add")
async def add_announcement(request: Request, message: Annotated[str, Form()], type: Annotated[str, Form()] = "info", link: Annotated[str, Form()] = ""):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("announcements").insert({"message": message, "type": type, "link": link or None}).execute()
    return JSONResponse({"success": True})

@router.post("/announcement/delete")
async def delete_announcement(request: Request, announcement_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("announcements").delete().eq("id", announcement_id).execute()
    return JSONResponse({"success": True})

@router.post("/announcement/toggle")
async def toggle_announcement(request: Request, announcement_id: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    a = db.table("announcements").select("is_active").eq("id", announcement_id).execute().data
    if a: db.table("announcements").update({"is_active": not a[0]["is_active"]}).eq("id", announcement_id).execute()
    return JSONResponse({"success": True})

@router.get("/support/conversations")
async def get_conversations(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    from app.services.support_service import get_all_conversations
    convs = await get_all_conversations(db)
    return JSONResponse({"conversations": convs})

@router.get("/support/messages/{user_id}")
async def get_user_messages(request: Request, user_id: str):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    from app.services.support_service import get_messages, mark_read
    messages = await get_messages(db, user_id)
    await mark_read(db, user_id, "user")
    return JSONResponse({"messages": messages})

@router.post("/support/reply")
async def admin_reply(request: Request, user_id: Annotated[str, Form()], message: Annotated[str, Form()]):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    from app.services.support_service import send_message
    from app.services.push_service import send_push_to_user
    ok = await send_message(db, user_id, "admin", message)
    try:
        await send_push_to_user(db, user_id, "💬 Nouveau message du support", message, "/support")
    except Exception:
        pass
    return JSONResponse({"success": ok})

@router.get("/suspicious")
async def get_suspicious(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        # Trouver les IPs avec plusieurs comptes
        users = db.table("users").select("id,full_name,email,registration_ip,is_active,created_at").execute().data or []
        ip_counts = {}
        for u in users:
            ip = u.get("registration_ip")
            if not ip:
                continue  # Ignorer les anciens comptes sans IP
            if ip not in ip_counts:
                ip_counts[ip] = []
            ip_counts[ip].append(u)
        suspicious = {ip: accs for ip, accs in ip_counts.items() if len(accs) > 1}
        return JSONResponse({"suspicious": suspicious})
    except Exception as e:
        return JSONResponse({"error": str(e)})

@router.post("/maintenance/on")
async def maintenance_on(request: Request, message: Annotated[str, Form()] = "Site en maintenance. Revenez bientôt !"):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("settings").upsert({"key": "maintenance", "value": "true"}).execute()
    db.table("settings").upsert({"key": "maintenance_message", "value": message}).execute()
    return JSONResponse({"success": True, "status": "on"})

@router.post("/maintenance/off")
async def maintenance_off(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("settings").upsert({"key": "maintenance", "value": "false"}).execute()
    return JSONResponse({"success": True, "status": "off"})

@router.get("/maintenance/status")
async def maintenance_status(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    res = db.table("settings").select("value").eq("key", "maintenance").execute()
    is_on = res.data and res.data[0]["value"] == "true"
    return JSONResponse({"maintenance": is_on})

@router.post("/popup/set")
async def set_popup(request: Request, message: Annotated[str, Form()], active: Annotated[str, Form()] = "true"):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("settings").upsert({"key": "popup_active", "value": active}).execute()
    db.table("settings").upsert({"key": "popup_message", "value": message}).execute()
    return JSONResponse({"success": True})

@router.post("/popup/off")
async def popup_off(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    db.table("settings").upsert({"key": "popup_active", "value": "false"}).execute()
    return JSONResponse({"success": True})

@router.get("/popup/status")
async def popup_status(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    active = db.table("settings").select("value").eq("key", "popup_active").execute().data
    msg = db.table("settings").select("value").eq("key", "popup_message").execute().data
    return JSONResponse({
        "active": active[0]["value"] == "true" if active else False,
        "message": msg[0]["value"] if msg else ""
    })

@router.get("/stats/advanced")
async def get_advanced_stats(request: Request):
    admin = await _get_admin(request)
    if not admin: return JSONResponse({"error": "Non autorisé"}, status_code=403)
    db = get_supabase()
    try:
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)

        # Inscriptions par jour (7 derniers jours)
        registrations = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            count = db.table("users").select("id").gte("created_at", day_str+"T00:00:00").lte("created_at", day_str+"T23:59:59").execute().data or []
            registrations.append({"date": day.strftime("%d/%m"), "count": len(count)})

        # Paiements par jour (7 derniers jours)
        payments = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            p = db.table("payments").select("amount").gte("created_at", day_str+"T00:00:00").lte("created_at", day_str+"T23:59:59").execute().data or []
            total = sum(x.get("amount", 0) for x in p)
            payments.append({"date": day.strftime("%d/%m"), "total": total})

        # Totaux globaux
        total_users = db.table("users").select("id", count="exact").execute().count or 0
        active_users = db.table("users").select("id", count="exact").eq("is_active", True).execute().count or 0
        total_payments = db.table("payments").select("amount").execute().data or []
        total_revenue = sum(x.get("amount", 0) for x in total_payments)
        pending_withdrawals = db.table("withdrawals").select("id", count="exact").eq("status", "pending").execute().count or 0

        return JSONResponse({
            "registrations": registrations,
            "payments": payments,
            "totals": {
                "total_users": total_users,
                "active_users": active_users,
                "total_revenue": total_revenue,
                "pending_withdrawals": pending_withdrawals,
            }
        })
    except Exception as e:
        return JSONResponse({"error": str(e)})
