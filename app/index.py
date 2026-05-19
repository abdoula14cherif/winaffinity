"""
api/index.py
────────────
Point d'entrée Vercel (serverless).
Vercel cherche automatiquement ce fichier.
"""

import sys
import os

# Ajouter le dossier racine au path Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: E402
