# ◈ WIN AFFINITY — Documentation

## Structure du projet

```
win_affinity/
│
├── app/
│   ├── main.py                  ← Point d'entrée FastAPI
│   ├── config.py                ← Configuration centralisée (.env)
│   ├── security.py              ← BCrypt, JWT, CSRF, validation
│   ├── database.py              ← Client Supabase singleton
│   │
│   ├── models/
│   │   ├── user.py              ← Schémas Pydantic (Register/Login)
│   │   └── payment.py           ← (Phase 2)
│   │
│   ├── routes/
│   │   ├── auth.py              ← GET/POST /auth/register & /auth/login
│   │   ├── payment.py           ← (Phase 2)
│   │   └── dashboard.py         ← (Phase 3)
│   │
│   ├── services/
│   │   ├── auth_service.py      ← Logique inscription / connexion
│   │   └── payment_service.py   ← (Phase 2)
│   │
│   └── templates/
│       ├── register.html        ✅ FAIT
│       ├── login.html           ✅ FAIT
│       ├── payment.html         ← (Phase 2)
│       └── dashboard.html       ← (Phase 3)
│
├── static/                      ← CSS / JS / images
├── supabase_schema.sql          ✅ FAIT — À exécuter dans Supabase
├── requirements.txt             ✅ FAIT
├── .env.example                 ✅ FAIT
└── README.md
```

## Démarrage rapide

```bash
# 1. Cloner et installer
cd win_affinity
pip install -r requirements.txt

# 2. Configurer l'environnement
cp .env.example .env
# Éditez .env avec vos vraies clés

# 3. Créer la base de données
# → Ouvrez Supabase → SQL Editor → collez supabase_schema.sql → Run

# 4. Lancer le serveur
uvicorn app.main:app --reload --port 8000

# 5. Accès
# Inscription : http://localhost:8000/auth/register?ref=CODE
# Connexion   : http://localhost:8000/auth/login
```

## Flux utilisateur

```
/auth/register?ref=CODE_PARRAINAGE
         ↓ (inscription réussie)
/auth/login
         ↓ (connexion réussie)
/payment          ← activation du compte
         ↓ (paiement confirmé)
/dashboard
```

## Sécurité implémentée

| Mesure               | Détail |
|----------------------|--------|
| BCrypt + Pepper      | Rounds=12, pepper côté app |
| JWT HTTP-only        | Access (1h) + Refresh (7j), cookies sécurisés |
| CSRF                 | Token signé itsdangerous sur chaque formulaire |
| Rate Limiting        | 5 tentatives/min login, 3/min inscription |
| Timing Attack        | Hash dummy si utilisateur inexistant |
| Input Sanitization   | Nettoyage + truncate sur toutes les entrées |
| Validation Pydantic  | Côté serveur obligatoire (ne pas faire confiance au client) |
| Mot de passe         | Min 8 car., majuscule, chiffre, spécial requis |
| RLS Supabase         | Row Level Security activé sur toutes les tables |

## Variables d'environnement requises

```
SECRET_KEY          → clé longue aléatoire (cookies)
JWT_SECRET_KEY      → clé longue aléatoire (JWT)
SUPABASE_URL        → https://ccbduullrdvudxdrnwbo.supabase.co
SUPABASE_ANON_KEY   → votre clé anon Supabase
LEEKPAY_PUBLIC_KEY  → pk_live_h0RQu365IhnhdXkW2YeWZiDmKQGo7Pn1
LEEKPAY_SECRET_KEY  → sk_live_... (depuis votre dashboard LeekPay)
```

## Phases de développement

- ✅ **Phase 1** — Inscription / Connexion (ce livrable)
- 🔜 **Phase 2** — Page de paiement LeekPay (activation compte)
- 🔜 **Phase 3** — Dashboard utilisateur complet
- 🔜 **Phase 4** — Admin panel + gestion des parrainages
