"""
Pagination de l'API.

DRF ignore `?page_size=` tant qu'on ne le lui autorise pas explicitement. Sans
cela, une page qui demande vingt-cinq lignes en recoit cinquante et calcule
son nombre de pages sur une taille qu'elle n'a jamais obtenue : les numeros de
page annonces ne correspondent alors a rien.

Le plafond n'est pas decoratif. `?page_size=100000` ferait charger les 98
dossiers, leurs notes et leurs resultats en une requete — un moyen simple de
mettre le serveur a genoux depuis un navigateur.
"""

from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class Pagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
