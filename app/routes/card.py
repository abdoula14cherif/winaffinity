"""
Routes Carte Virtuelle WIN AFFINITY
"""
import logging
import random
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.commission_service import get_wallet

router = APIRouter(prefix="/card", tags=["Card"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

def generate_card_number():
    groups = [str(random.randint(1000,9999)) for _ in range(4)]
    groups[0] = "4242"
    return " ".join(groups)

@router.get("", response_class=HTMLResponse)
async def get_card(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    card = db.table("virtual_cards").select("*").eq("user_id", user["id"]).execute().data
    card = card[0] if card else None
    transactions = []
    if card:
        txs = db.table("card_transactions").select("*").eq("card_id", card["id"]).order("created_at", desc=True).limit(20).execute().data or []
        for tx in txs:
            if tx["type"] in ("transfer_out", "withdrawal", "recharge_out"):
                tx["amount"] = -abs(tx["amount"])
            else:
                tx["amount"] = abs(tx["amount"])
        transactions = txs
    return templates.TemplateResponse("card.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "card": card,
        "transactions": transactions,
    })

@router.post("/create")
async def create_card(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    db = get_supabase()
    existing = db.table("virtual_cards").select("id").eq("user_id", user["id"]).execute().data
    if existing: return JSONResponse({"error": "Vous avez déjà une carte"})
    card_number = generate_card_number()
    db.table("virtual_cards").insert({
        "user_id": user["id"],
        "card_number": card_number,
        "card_holder": user["full_name"].upper(),
        "balance": 0,
        "status": "active"
    }).execute()
    return JSONResponse({"success": True})

@router.post("/recharge")
async def recharge_card(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    body = await request.json()
    amount = int(body.get("amount", 0))
    if amount < 500: return JSONResponse({"error": "Minimum 500 FCFA"})
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])
    if wallet["balance"] < amount: return JSONResponse({"error": "Solde WIN AFFINITY insuffisant"})
    card = db.table("virtual_cards").select("*").eq("user_id", user["id"]).execute().data
    if not card: return JSONResponse({"error": "Carte introuvable"})
    card = card[0]
    fee = round(amount * 0.01)
    net = amount - fee
    try:
        db.table("wallets").update({"balance": wallet["balance"] - amount}).eq("user_id", user["id"]).execute()
        db.table("virtual_cards").update({"balance": card["balance"] + net}).eq("id", card["id"]).execute()
        db.table("card_transactions").insert({"card_id": card["id"], "user_id": user["id"], "type": "recharge", "amount": net, "description": f"Recharge depuis solde WIN AFFINITY (-{fee}F frais)"}).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)})

@router.post("/send")
async def send_card(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    body = await request.json()
    receiver_code = body.get("receiver_code", "")
    amount = int(body.get("amount", 0))
    note = body.get("note", "")
    if amount < 100: return JSONResponse({"error": "Minimum 100 FCFA"})
    db = get_supabase()
    card = db.table("virtual_cards").select("*").eq("user_id", user["id"]).execute().data
    if not card: return JSONResponse({"error": "Carte introuvable"})
    card = card[0]
    if card["balance"] < amount: return JSONResponse({"error": "Solde carte insuffisant"})
    recv = db.table("users").select("id,full_name").eq("referral_code", receiver_code).eq("is_active", True).execute().data
    if not recv: return JSONResponse({"error": "Destinataire introuvable"})
    recv = recv[0]
    if recv["id"] == user["id"]: return JSONResponse({"error": "Vous ne pouvez pas vous envoyer de l argent"})
    recv_card = db.table("virtual_cards").select("*").eq("user_id", recv["id"]).execute().data
    try:
        db.table("virtual_cards").update({"balance": card["balance"] - amount}).eq("id", card["id"]).execute()
        db.table("card_transactions").insert({"card_id": card["id"], "user_id": user["id"], "type": "transfer_out", "amount": amount, "description": f"Envoi à {recv['full_name']}" + (f" - {note}" if note else ""), "receiver_id": recv["id"]}).execute()
        if recv_card:
            recv_card = recv_card[0]
            db.table("virtual_cards").update({"balance": recv_card["balance"] + amount}).eq("id", recv_card["id"]).execute()
            db.table("card_transactions").insert({"card_id": recv_card["id"], "user_id": recv["id"], "type": "transfer_in", "amount": amount, "description": f"Reçu de {user['full_name']}" + (f" - {note}" if note else "")}).execute()
        else:
            recv_wallet = await get_wallet(db, recv["id"])
            db.table("wallets").update({"balance": recv_wallet["balance"] + amount, "total_earned": recv_wallet["total_earned"] + amount}).eq("user_id", recv["id"]).execute()
        try:
            from app.services.push_service import send_push_to_user
            await send_push_to_user(db, recv["id"], "💳 Transfert carte reçu !", f"{user['full_name']} vous a envoyé {amount} FCFA sur votre carte", "/card")
        except: pass
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)})

@router.post("/withdraw")
async def withdraw_card(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    body = await request.json()
    amount = int(body.get("amount", 0))
    if amount < 500: return JSONResponse({"error": "Minimum 500 FCFA"})
    db = get_supabase()
    card = db.table("virtual_cards").select("*").eq("user_id", user["id"]).execute().data
    if not card: return JSONResponse({"error": "Carte introuvable"})
    card = card[0]
    if card["balance"] < amount: return JSONResponse({"error": "Solde carte insuffisant"})
    fee = round(amount * 0.02)
    net = amount - fee
    try:
        db.table("virtual_cards").update({"balance": card["balance"] - amount}).eq("id", card["id"]).execute()
        db.table("card_transactions").insert({"card_id": card["id"], "user_id": user["id"], "type": "withdrawal", "amount": amount, "description": f"Retrait vers solde WIN AFFINITY (-{fee}F frais)"}).execute()
        wallet = await get_wallet(db, user["id"])
        db.table("wallets").update({"balance": wallet["balance"] + net, "total_earned": wallet["total_earned"] + net}).eq("user_id", user["id"]).execute()
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"error": str(e)})
