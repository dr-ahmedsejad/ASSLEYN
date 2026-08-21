"""
Amorcage des attributions de permissions.

Les valeurs du catalogue sont ecrites en base pour que l'administration les
voie et puisse les modifier. La migration est reversible et ne touche pas aux
attributions deja presentes : la rejouer ne remet rien a plat.
"""

from django.db import migrations

from apps.accounts.rbac import DEFAUTS


def poser_defauts(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")
    for role, permissions in DEFAUTS.items():
        for permission in permissions:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def retirer_defauts(apps, schema_editor):
    RolePermission = apps.get_model("accounts", "RolePermission")
    RolePermission.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_alter_user_role_rolepermission")]

    operations = [migrations.RunPython(poser_defauts, retirer_defauts)]
