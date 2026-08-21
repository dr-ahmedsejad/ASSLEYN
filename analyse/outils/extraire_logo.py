"""
Extrait le logo de l'institut des listes PDF officielles.

Le logo figure en en-tete de chaque liste. Il y est stocke en deux flux : une
image JPEG pour les couleurs, et un flux gris (`SMask`) pour la transparence.
Ce script les recompose en PNG a fond transparent, recadre sur le contenu
reel, puis agrandit en Lanczos — l'original ne fait que 198x149.

    python analyse/outils/extraire_logo.py \
        "لائحة قسم الحافظات.pdf" frontend/public

Produit `logo-institut.png`, `logo-institut-carre.png` et `favicon.ico`.
Ne depend que de Pillow : `pip install Pillow`.

A relancer uniquement si l'institut change de logo.
"""

from __future__ import annotations

import io
import re
import sys
import zlib
from pathlib import Path

from PIL import Image

AGRANDISSEMENT = 5


def images_du_pdf(chemin: Path) -> list[dict]:
    """Retourne les objets image du PDF, decompresses si necessaire."""
    donnees = chemin.read_bytes()
    trouvees: list[dict] = []

    for objet in re.finditer(rb"(\d+)\s+\d+\s+obj(.*?)endobj", donnees, re.S):
        corps = objet.group(2)
        if b"/Image" not in corps:
            continue

        entete = corps.split(b"stream", 1)[0]
        largeur = re.search(rb"/Width\s+(\d+)", entete)
        hauteur = re.search(rb"/Height\s+(\d+)", entete)
        if not (largeur and hauteur):
            continue

        debut = corps.find(b"stream") + len(b"stream")
        while corps[debut : debut + 1] in (b"\r", b"\n"):
            debut += 1
        flux = corps[debut : corps.rfind(b"endstream")]

        if b"DCTDecode" in entete:
            filtre, contenu = "jpeg", flux
        elif b"FlateDecode" in entete:
            try:
                filtre, contenu = "brut", zlib.decompress(flux)
            except zlib.error:
                continue
        else:
            continue

        trouvees.append(
            {
                "numero": objet.group(1).decode(),
                "filtre": filtre,
                "taille": (int(largeur.group(1)), int(hauteur.group(1))),
                "gris": b"DeviceGray" in entete,
                "contenu": contenu,
            }
        )
    return trouvees


def composer(images: list[dict]) -> Image.Image:
    """Assemble l'image couleur et son masque de transparence."""
    couleurs = next(i for i in images if i["filtre"] == "jpeg")
    largeur, hauteur = couleurs["taille"]

    logo = Image.open(io.BytesIO(couleurs["contenu"])).convert("RGB")

    masque = next(
        (
            i
            for i in images
            if i["filtre"] == "brut"
            and i["gris"]
            and i["taille"] == (largeur, hauteur)
            and len(i["contenu"]) >= largeur * hauteur
        ),
        None,
    )
    if masque is None:
        raise SystemExit("Masque de transparence introuvable dans le PDF.")

    logo = logo.copy()
    logo.putalpha(
        Image.frombytes("L", (largeur, hauteur), masque["contenu"][: largeur * hauteur])
    )

    # Le PDF laisse des marges transparentes autour du logo.
    boite = logo.getbbox()
    if boite:
        logo = logo.crop(boite)
    return logo


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)

    source, destination = Path(sys.argv[1]), Path(sys.argv[2])
    destination.mkdir(parents=True, exist_ok=True)

    logo = composer(images_du_pdf(source))
    print(f"logo recadre : {logo.size}")

    grand = logo.resize(
        (logo.width * AGRANDISSEMENT, logo.height * AGRANDISSEMENT), Image.LANCZOS
    )
    grand.save(destination / "logo-institut.png", "PNG", optimize=True)
    print("logo-institut.png       :", grand.size)

    cote = max(grand.size)
    carre = Image.new("RGBA", (cote, cote), (0, 0, 0, 0))
    carre.paste(
        grand, ((cote - grand.width) // 2, (cote - grand.height) // 2), grand
    )

    carre.resize((512, 512), Image.LANCZOS).save(
        destination / "logo-institut-carre.png", "PNG", optimize=True
    )
    print("logo-institut-carre.png : 512x512")

    carre.resize((64, 64), Image.LANCZOS).save(
        destination / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)]
    )
    print("favicon.ico             : 16/32/48")


if __name__ == "__main__":
    main()
