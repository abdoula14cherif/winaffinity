"""
Routes portefeuille WIN AFFINITY
"""
import logging
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from app.database import get_supabase
from app.security import decode_access_token
from app.services.auth_service import get_user_by_id
from app.services.commission_service import get_wallet

router = APIRouter(prefix="/wallet", tags=["Wallet"])
templates = Jinja2Templates(directory="app/templates")
logger = logging.getLogger(__name__)

async def _get_user(request: Request):
    token = request.cookies.get("access_token")
    if not token: return None
    payload = decode_access_token(token)
    if not payload: return None
    return await get_user_by_id(get_supabase(), payload["sub"])

@router.get("", response_class=HTMLResponse)
async def get_wallet_page(request: Request):
    user = await _get_user(request)
    if not user: return RedirectResponse("/auth/login", status_code=302)
    if not user.get("is_active"): return RedirectResponse("/payment", status_code=302)
    db = get_supabase()
    wallet = await get_wallet(db, user["id"])

    # Transactions - commissions
    txs = []
    try:
        comms = db.table("commissions").select("*").eq("sponsor_id", user["id"]).order("created_at", desc=True).limit(20).execute().data or []
        for c in comms:
            txs.append({"type":"commission","label":"Commission parrainage N"+str(c.get("tier",1)),"amount":c.get("amount",0),"date":c.get("created_at","")})
    except: pass

    # Transferts reçus
    try:
        recv = db.table("transfers").select("*").eq("receiver_id", user["id"]).order("created_at", desc=True).limit(10).execute().data or []
        for r in recv:
            sender = db.table("users").select("full_name").eq("id", r["sender_id"]).execute().data
            name = sender[0]["full_name"] if sender else "Inconnu"
            txs.append({"type":"transfer_in","label":"Reçu de "+name,"amount":r.get("net_amount",0),"date":r.get("created_at","")})
    except: pass

    # Transferts envoyés
    try:
        sent = db.table("transfers").select("*").eq("sender_id", user["id"]).order("created_at", desc=True).limit(10).execute().data or []
        for s in sent:
            recv_user = db.table("users").select("full_name").eq("id", s["receiver_id"]).execute().data
            name = recv_user[0]["full_name"] if recv_user else "Inconnu"
            txs.append({"type":"transfer_out","label":"Envoyé à "+name,"amount":-s.get("amount",0),"date":s.get("created_at","")})
    except: pass

    # Retraits
    try:
        withdrawals = db.table("withdrawals").select("*").eq("user_id", user["id"]).order("created_at", desc=True).limit(5).execute().data or []
        for w in withdrawals:
            if w.get("status") == "approved":
                txs.append({"type":"withdrawal","label":"Retrait Mobile Money","amount":-w.get("amount",0),"date":w.get("created_at","")})
    except: pass

    # Trier par date
    txs.sort(key=lambda x: x.get("date",""), reverse=True)

    # Stats
    total_sent = sum(abs(t["amount"]) for t in txs if t["type"] == "transfer_out")
    total_received = sum(t["amount"] for t in txs if t["type"] == "transfer_in")

    return templates.TemplateResponse("wallet.html", {
        "request": request,
        "user": user,
        "wallet": wallet,
        "transactions": txs[:30],
        "total_sent": total_sent,
        "total_received": total_received,
    })

@router.get("/search")
async def search_user(request: Request, q: str = ""):
    user = await _get_user(request)
    if not user: return JSONResponse({"user": None})
    db = get_supabase()
    try:
        # Chercher par code parrainage
        res = db.table("users").select("id,full_name,referral_code").eq("referral_code", q.upper()).eq("is_active", True).execute().data
        if not res:
            # Chercher par email
            res = db.table("users").select("id,full_name,referral_code").eq("email", q.lower()).eq("is_active", True).execute().data
        if res and res[0]["id"] != user["id"]:
            return JSONResponse({"user": res[0]})
        return JSONResponse({"user": None})
    except Exception as e:
        return JSONResponse({"user": None})

@router.post("/transfer")
async def do_transfer(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    body = await request.json()
    receiver_code = body.get("receiver_code", "")
    amount = int(body.get("amount", 0))
    note = body.get("note", "")
    if amount < 500:
        return JSONResponse({"error": "Minimum 500 FCFA"})
    db = get_supabase()
    try:
        # Vérifier destinataire
        recv = db.table("users").select("id,full_name").eq("referral_code", receiver_code).eq("is_active", True).execute().data
        if not recv:
            return JSONResponse({"error": "Destinataire introuvable"})
        recv = recv[0]
        if recv["id"] == user["id"]:
            return JSONResponse({"error": "Vous ne pouvez pas vous envoyer de l argent"})
        # Vérifier solde
        wallet = await get_wallet(db, user["id"])
        if wallet["balance"] < amount:
            return JSONResponse({"error": "Solde insuffisant"})
        # Calculer frais
        fee = round(amount * 0.02)
        net = amount - fee
        # Débiter expéditeur
        db.table("wallets").update({"balance": wallet["balance"] - amount}).eq("user_id", user["id"]).execute()
        # Créditer destinataire
        recv_wallet = await get_wallet(db, recv["id"])
        db.table("wallets").update({"balance": recv_wallet["balance"] + net, "total_earned": recv_wallet["total_earned"] + net}).eq("user_id", recv["id"]).execute()
        # Enregistrer transfert
        db.table("transfers").insert({"sender_id": user["id"], "receiver_id": recv["id"], "amount": amount, "fee": fee, "net_amount": net, "note": note}).execute()
        # Notifier destinataire
        try:
            from app.services.push_service import send_push_to_user
            await send_push_to_user(db, recv["id"], "💸 Transfert reçu !", user["full_name"]+" vous a envoyé "+str(net)+" FCFA", "/wallet")
        except: pass
        return JSONResponse({"success": True})
    except Exception as e:
        logger.error("[TRANSFER] Erreur : %s", e)
        return JSONResponse({"error": str(e)})

@router.post("/upgrade")
async def do_upgrade(request: Request):
    user = await _get_user(request)
    if not user: return JSONResponse({"error": "Non authentifié"}, status_code=401)
    if not user.get("is_active"): return JSONResponse({"error": "Compte non actif"})
    body = await request.json()
    level = body.get("level", "")
    amounts = {"starter": 1000, "standard": 2500, "premium": 5000}
    if level not in amounts:
        return JSONResponse({"error": "Niveau invalide"})
    price = amounts[level]
    # Vérifier que c'est bien un upgrade
    level_rank = {"starter": 1, "standard": 2, "premium": 3}
    current_rank = level_rank.get(user.get("level") or "standard", 2)
    new_rank = level_rank.get(level, 2)
    if new_rank <= current_rank:
        return JSONResponse({"error": "Vous êtes déjà à ce niveau ou supérieur"})
    db = get_supabase()
    try:
        wallet = await get_wallet(db, user["id"])
        if wallet["balance"] < price:
            return JSONResponse({"error": "Solde insuffisant. Il vous faut "+str(price)+" FCFA"})
        # Débiter le solde
        db.table("wallets").update({"balance": wallet["balance"] - price}).eq("user_id", user["id"]).execute()
        # Mettre à jour le niveau
        db.table("users").update({"level": level, "activation_amount": price}).eq("id", user["id"]).execute()
        # Enregistrer paiement
        db.table("payments").insert({"user_id": user["id"], "amount": price, "level": level, "status": "completed", "payment_method": "wallet_upgrade"}).execute()
        return JSONResponse({"success": True, "level": level})
    except Exception as e:
        logger.error("[UPGRADE] Erreur : %s", e)
        return JSONResponse({"error": str(e)})
