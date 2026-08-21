"""
Ajustement des attributions par defaut.

Deux changements decides par la direction :

1. Le tableau de bord devient une capacite comme les autres
   (`tableau.consulter`) : l'assistance n'a pas a le voir, son ecran est le
   poste de saisie.
2. L'assistance est ramenee a la seule saisie des notes.

Les attributions des autres roles ne sont pas touchees, et la migration est
reversible.
"""

from django.db import migrations

TABLEAU = "tableau.consulter"
NOTES_SAISIR = "notes.saisir"

#: Ce que l'assistance perd ici. Reaccordable a tout moment depuis la matrice.
RETIREES_ASSISTANT = [
    "notes.consulter",
    "etudiantes.gerer",
    "journal.consulter",
]


def appliquer(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")

    for role in ("ADMIN", "TEACHER"):
        RolePermission.objects.get_or_create(role=role, permission=TABLEAU)

    RolePermission.objects.filter(
        role="ASSISTANT", permission__in=RETIREES_ASSISTANT
    ).delete()
    RolePermission.objects.get_or_create(
        role="ASSISTANT", permission=NOTES_SAISIR
    )


def revenir(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")
    RolePermission.objects.filter(permission=TABLEAU).delete()
    for permission in RETIREES_ASSISTANT:
        RolePermission.objects.get_or_create(
            role="ASSISTANT", permission=permission
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0004_userpermission")]

    operations = [migrations.RunPython(appliquer, revenir)]
