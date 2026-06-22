"""
Service email via Brevo (Sendinblue)
"""
import os
import logging
import httpx

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "abdoula12cherif@gmail.com")
SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "WIN AFFINITY")

async def send_email(to_email: str, to_name: str, subject: str, html_content: str) -> bool:
    if not BREVO_API_KEY:
        logger.warning("[EMAIL] Clé Brevo manquante")
        return False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "api-key": BREVO_API_KEY,
                    "Content-Type": "application/json"
                },
                json={
                    "sender": {"name": SENDER_NAME, "email": SENDER_EMAIL},
                    "to": [{"email": to_email, "name": to_name}],
                    "subject": subject,
                    "htmlContent": html_content
                },
                timeout=10
            )
            if r.status_code in (200, 201):
                logger.info("[EMAIL] Envoyé à %s", to_email)
                return True
            else:
                logger.error("[EMAIL] Erreur %s : %s", r.status_code, r.text)
                return False
    except Exception as e:
        logger.error("[EMAIL] Exception : %s", e)
        return False

async def send_welcome_email(to_email: str, to_name: str, referral_code: str) -> bool:
    subject = "🎉 Bienvenue sur WIN AFFINITY !"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#F0F4F8;padding:20px">
      <div style="background:#1A3A5C;border-radius:16px;padding:24px;text-align:center;margin-bottom:20px">
        <h1 style="color:#FF6B35;font-size:28px;margin:0">◈ WIN AFFINITY</h1>
      </div>
      <div style="background:#fff;border-radius:16px;padding:24px">
        <h2 style="color:#1A3A5C">Bonjour {to_name} ! 👋</h2>
        <p style="color:#6B7A8D;line-height:1.6">Bienvenue sur WIN AFFINITY ! Votre compte a été créé avec succès.</p>
        <div style="background:#F0F4F8;border-radius:12px;padding:16px;margin:16px 0">
          <p style="color:#6B7A8D;font-size:12px;margin:0 0 6px">VOTRE CODE DE PARRAINAGE</p>
          <p style="color:#FF6B35;font-size:24px;font-weight:800;margin:0">{referral_code}</p>
        </div>
        <p style="color:#6B7A8D">Activez votre compte pour commencer à gagner !</p>
        <a href="https://winaffinity.vercel.app/payment" style="display:inline-block;background:linear-gradient(135deg,#FF6B35,#FF8C5A);color:#fff;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;margin-top:10px">Activer mon compte</a>
      </div>
      <p style="text-align:center;color:#6B7A8D;font-size:12px;margin-top:16px">© 2026 WIN AFFINITY • winaffinitysupport@gmail.com</p>
    </div>"""
    return await send_email(to_email, to_name, subject, html)

async def send_activation_email(to_email: str, to_name: str, level: str, referral_code: str) -> bool:
    subject = "✅ Compte activé — WIN AFFINITY"
    levels = {"starter": "🥉 Starter", "standard": "🥈 Standard", "premium": "🥇 Premium"}
    level_txt = levels.get(level, "🥈 Standard")
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#F0F4F8;padding:20px">
      <div style="background:#1A3A5C;border-radius:16px;padding:24px;text-align:center;margin-bottom:20px">
        <h1 style="color:#FF6B35;font-size:28px;margin:0">◈ WIN AFFINITY</h1>
      </div>
      <div style="background:#fff;border-radius:16px;padding:24px">
        <h2 style="color:#1A3A5C">🎉 Félicitations {to_name} !</h2>
        <p style="color:#6B7A8D">Votre compte est maintenant <strong style="color:#00B894">ACTIF</strong> en niveau <strong style="color:#FF6B35">{level_txt}</strong></p>
        <div style="background:#F0F4F8;border-radius:12px;padding:16px;margin:16px 0">
          <p style="color:#6B7A8D;font-size:12px;margin:0 0 6px">VOTRE LIEN DE PARRAINAGE</p>
          <p style="color:#FF6B35;font-size:13px;margin:0">https://winaffinity.vercel.app/auth/register?ref={referral_code}</p>
        </div>
        <a href="https://winaffinity.vercel.app/dashboard" style="display:inline-block;background:linear-gradient(135deg,#FF6B35,#FF8C5A);color:#fff;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700">Accéder à mon dashboard</a>
      </div>
      <p style="text-align:center;color:#6B7A8D;font-size:12px;margin-top:16px">© 2026 WIN AFFINITY • winaffinitysupport@gmail.com</p>
    </div>"""
    return await send_email(to_email, to_name, subject, html)

async def send_reset_password_email(to_email: str, to_name: str, reset_url: str) -> bool:
    subject = "🔒 Réinitialisation mot de passe — WIN AFFINITY"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;background:#F0F4F8;padding:20px">
      <div style="background:#1A3A5C;border-radius:16px;padding:24px;text-align:center;margin-bottom:20px">
        <h1 style="color:#FF6B35;font-size:28px;margin:0">◈ WIN AFFINITY</h1>
      </div>
      <div style="background:#fff;border-radius:16px;padding:24px">
        <h2 style="color:#1A3A5C">🔒 Réinitialisation mot de passe</h2>
        <p style="color:#6B7A8D">Bonjour {to_name}, vous avez demandé à réinitialiser votre mot de passe.</p>
        <p style="color:#6B7A8D">Ce lien est valable <strong>1 heure</strong> :</p>
        <a href="{reset_url}" style="display:inline-block;background:linear-gradient(135deg,#FF6B35,#FF8C5A);color:#fff;padding:14px 28px;border-radius:10px;text-decoration:none;font-weight:700;margin:16px 0">Réinitialiser mon mot de passe</a>
        <p style="color:#6B7A8D;font-size:12px">Si vous n avez pas fait cette demande, ignorez cet email.</p>
      </div>
      <p style="text-align:center;color:#6B7A8D;font-size:12px;margin-top:16px">© 2026 WIN AFFINITY • winaffinitysupport@gmail.com</p>
    </div>"""
    return await send_email(to_email, to_name, subject, html)
