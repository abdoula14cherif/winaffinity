from supabase import create_client, Client
from app.config import settings

# Client public (respecte les Row Level Security policies) — à utiliser pour tout ce qui vient d'un utilisateur
supabase_public: Client = create_client(settings.supabase_url, settings.supabase_anon_key)

# Client admin (contourne les RLS) — réservé aux opérations serveur strictement contrôlées,
# jamais exposé à une requête utilisateur non authentifiée
supabase_admin: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)
