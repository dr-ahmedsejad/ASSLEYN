"""
Sonde de sante, destinee a l'orchestrateur.

Docker n'a aucun moyen de savoir si le processus qui ecoute sur le port sert
reellement l'application : un Django qui a perdu sa base repond encore. La
sonde interroge donc la base, et ne se contente pas d'exister.

Elle est deliberement muette sur le contenu : ni version, ni nom de base, ni
trace d'exception. Une sonde est un point d'entree non authentifie ; elle ne
doit rien apprendre a qui la scrute.
"""

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


@never_cache
def healthz(request):
    """Repond 200 si la base repond, 503 sinon."""
    try:
        with connection.cursor() as curseur:
            curseur.execute("SELECT 1")
            curseur.fetchone()
    except Exception:  # noqa: BLE001 — toute panne de base vaut « indisponible »
        return JsonResponse({"status": "degraded"}, status=503)
    return JsonResponse({"status": "ok"})
