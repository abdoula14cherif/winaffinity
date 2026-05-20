"""
Service emails automatiques via Resend
Emails envoyés :
  - Bienvenue après inscription
  - Confirmation après activation
  - Commission reçue
  - Demande de retrait
  - Retrait approuvé/rejeté
"""
import logging
import httpx
import os

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
FROM_NAME = "WIN AFFINITY"

async def send_email(to: str, subject: str, html: str) -> bool:
    """Envoie un email via Resend API."""
    if not RESEND_API_KEY:
        logger.warning("[EMAIL] RESEND_API_KEY manquant")
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"{FROM_NAME} <{FROM_EMAIL}>",
                    "to": [to],
                    "subject": subject,
                    "html": html,
                }
            )
            if res.status_code == 200:
                logger.info("[EMAIL] Envoyé à %s : %s", to, subject)
                return True
            logger.error("[EMAIL] Erreur %d : %s", res.status_code, res.text)
            return False
    except Exception as e:
        logger.error("[EMAIL] Exception : %s", e)
        return False

def _base_template(content: str) -> str:
    return f"""
    <div style="font-family:DM Sans,Arial,sans-serif;max-width:580px;margin:0 auto;background:#07101F;color:#F4EFE6;border-radius:16px;overflow:hidden;border:1px solid rgba(201,168,76,0.2)">
      <div style="background:linear-gradient(135deg,#0D1B2A,#07101F);padding:32px;text-align:center;border-bottom:1px solid rgba(201,168,76,0.2)">
        <div style="font-size:32px;margin-bottom:8px">◈</div>
        <div style="font-family:Georgia,serif;font-size:24px;font-weight:700;letter-spacing:0.1em;background:linear-gradient(135deg,#E8C96A,#C9A84C);-webkit-background-clip:text;-webkit-text-fill-color:transparent">WIN AFFINITY</div>
        <div style="font-size:12px;color:rgba(244,239,230,0.5);margin-top:4px">Plateforme d'affiliation premium</div>
      </div>
      <div style="padding:32px">
        {content}
      </div>
      <div style="padding:20px 32px;background:rgba(13,27,42,0.5);text-align:center;font-size:11px;color:rgba(244,239,230,0.3);border-top:1px solid rgba(201,168,76,0.1)">
        © 2026 WIN AFFINITY · <a href="https://winaffinity.vercel.app" style="color:#C9A84C;text-decoration:none">winaffinity.vercel.app</a>
      </div>
    </div>
    """

async def send_welcome(to: str, name: str, referral_code: str):
    """Email de bienvenue après inscription."""
    html = _base_template(f"""
        <h2 style="font-family:Georgia,serif;font-size:28px;color:#C9A84C;margin-bottom:8px">Bienvenue, {name} ! 🎉</h2>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Votre compte WIN AFFINITY a été créé avec succès.</p>
        <div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.2);border-radius:12px;padding:20px;margin-bottom:24px">
          <div style="font-size:12px;color:rgba(244,239,230,0.5);margin-bottom:4px">VOTRE CODE DE PARRAINAGE</div>
          <div style="font-size:28px;font-weight:700;color:#C9A84C;letter-spacing:0.1em">{referral_code}</div>
        </div>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:20px">Activez votre compte pour commencer à gagner des commissions.</p>
        <a href="https://winaffinity.vercel.app/payment" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#C9A84C,#A07020);color:#07101F;font-weight:700;text-decoration:none;border-radius:10px;font-size:15px">ACTIVER MON COMPTE →</a>
    """)
    await send_email(to, "🎉 Bienvenue sur WIN AFFINITY !", html)

async def send_activation_confirmed(to: str, name: str, referral_link: str):
    """Email après activation du compte."""
    html = _base_template(f"""
        <h2 style="font-family:Georgia,serif;font-size:28px;color:#4CAF7E;margin-bottom:8px">Compte activé ! ✅</h2>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Félicitations {name}, votre compte est maintenant actif !</p>
        <div style="display:grid;gap:12px;margin-bottom:24px">
          <div style="background:rgba(13,27,42,0.8);border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:rgba(244,239,230,0.6)">Filleul direct (N1)</span>
            <span style="color:#C9A84C;font-weight:600">1 250 FCFA</span>
          </div>
          <div style="background:rgba(13,27,42,0.8);border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:rgba(244,239,230,0.6)">Niveau 2</span>
            <span style="color:#4CAF7E;font-weight:600">600 FCFA</span>
          </div>
          <div style="background:rgba(13,27,42,0.8);border:1px solid rgba(201,168,76,0.15);border-radius:10px;padding:16px;display:flex;justify-content:space-between">
            <span style="color:rgba(244,239,230,0.6)">Niveau 3</span>
            <span style="color:#6495ED;font-weight:600">300 FCFA</span>
          </div>
        </div>
        <p style="font-size:13px;color:rgba(244,239,230,0.5);margin-bottom:16px">Votre lien de parrainage :</p>
        <div style="background:rgba(201,168,76,0.08);border:1px solid rgba(201,168,76,0.2);border-radius:10px;padding:14px;word-break:break-all;font-size:13px;color:#C9A84C;margin-bottom:24px">{referral_link}</div>
        <a href="https://winaffinity.vercel.app/dashboard" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#C9A84C,#A07020);color:#07101F;font-weight:700;text-decoration:none;border-radius:10px;font-size:15px">VOIR MON DASHBOARD →</a>
    """)
    await send_email(to, "✅ Compte activé - Commencez à gagner !", html)

async def send_commission_received(to: str, name: str, amount: int, level: int, from_name: str):
    """Email quand une commission est reçue."""
    html = _base_template(f"""
        <h2 style="font-family:Georgia,serif;font-size:28px;color:#C9A84C;margin-bottom:8px">💰 Commission reçue !</h2>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Bonne nouvelle {name} !</p>
        <div style="background:rgba(201,168,76,0.08);border:2px solid rgba(201,168,76,0.3);border-radius:16px;padding:28px;text-align:center;margin-bottom:24px">
          <div style="font-size:14px;color:rgba(244,239,230,0.5);margin-bottom:8px">COMMISSION NIVEAU {level}</div>
          <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#C9A84C">+{amount} FCFA</div>
          <div style="font-size:13px;color:rgba(244,239,230,0.5);margin-top:8px">de {from_name}</div>
        </div>
        <a href="https://winaffinity.vercel.app/dashboard" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#C9A84C,#A07020);color:#07101F;font-weight:700;text-decoration:none;border-radius:10px;font-size:15px">VOIR MON SOLDE →</a>
    """)
    await send_email(to, f"💰 +{amount} FCFA de commission reçue !", html)

async def send_withdrawal_requested(to: str, name: str, amount: int, net: int, operator: str):
    """Email quand un retrait est demandé."""
    html = _base_template(f"""
        <h2 style="font-family:Georgia,serif;font-size:28px;color:#E09050;margin-bottom:8px">Demande de retrait reçue ⏳</h2>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Bonjour {name}, votre demande est en cours de traitement.</p>
        <div style="background:rgba(13,27,42,0.8);border:1px solid rgba(201,168,76,0.15);border-radius:12px;padding:20px;margin-bottom:24px">
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
            <span style="color:rgba(244,239,230,0.6)">Montant demandé</span>
            <span style="color:#F4EFE6;font-weight:600">{amount} FCFA</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
            <span style="color:rgba(244,239,230,0.6)">Frais (10%)</span>
            <span style="color:#E05A5A">-{amount-net} FCFA</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:10px 0">
            <span style="color:rgba(244,239,230,0.6)">Vous recevrez</span>
            <span style="color:#4CAF7E;font-weight:700;font-size:18px">{net} FCFA</span>
          </div>
        </div>
        <p style="font-size:13px;color:rgba(244,239,230,0.5)">Opérateur : <strong style="color:#C9A84C">{operator.replace('_',' ').title()}</strong></p>
    """)
    await send_email(to, "⏳ Demande de retrait en cours de traitement", html)

async def send_withdrawal_approved(to: str, name: str, net: int, operator: str, phone: str):
    """Email quand un retrait est approuvé."""
    html = _base_template(f"""
        <h2 style="font-family:Georgia,serif;font-size:28px;color:#4CAF7E;margin-bottom:8px">Retrait approuvé ! ✅</h2>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Bonne nouvelle {name} !</p>
        <div style="background:rgba(76,175,126,0.08);border:2px solid rgba(76,175,126,0.3);border-radius:16px;padding:28px;text-align:center;margin-bottom:24px">
          <div style="font-size:14px;color:rgba(244,239,230,0.5);margin-bottom:8px">MONTANT ENVOYÉ</div>
          <div style="font-family:Georgia,serif;font-size:48px;font-weight:700;color:#4CAF7E">{net} FCFA</div>
          <div style="font-size:13px;color:rgba(244,239,230,0.5);margin-top:8px">{operator.replace('_',' ').title()} · {phone}</div>
        </div>
        <a href="https://winaffinity.vercel.app/dashboard" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#C9A84C,#A07020);color:#07101F;font-weight:700;text-decoration:none;border-radius:10px;font-size:15px">VOIR MON DASHBOARD →</a>
    """)
    await send_email(to, "✅ Votre retrait a été approuvé !", html)

async def send_withdrawal_rejected(to: str, name: str, amount: int):
    """Email quand un retrait est rejeté."""
    html = _base_template(f"""
        <h2 style="font-family:Georgia,serif;font-size:28px;color:#E05A5A;margin-bottom:8px">Retrait annulé ❌</h2>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Bonjour {name}, votre demande de retrait de {amount} FCFA a été annulée.</p>
        <p style="color:rgba(244,239,230,0.7);margin-bottom:24px">Le montant a été recrédité sur votre solde. Contactez le support pour plus d'informations.</p>
        <a href="https://winaffinity.vercel.app/support" style="display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#C9A84C,#A07020);color:#07101F;font-weight:700;text-decoration:none;border-radius:10px;font-size:15px">CONTACTER LE SUPPORT →</a>
    """)
    await send_email(to, "❌ Votre demande de retrait a été annulée", html)
