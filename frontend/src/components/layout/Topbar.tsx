"use client";

import { Suspense } from "react";
import { Menu } from "lucide-react";

import type { CurrentUser, Semester } from "@/lib/types";

import SelecteurFasl from "./SelecteurFasl";
import UserMenu from "./UserMenu";

interface Props {
  user: CurrentUser;
  fusul: Semester[];
  faslCourant: Semester | null;
  onOpenMobile: () => void;
  onToggleCollapsed: () => void;
}

/**
 * Premier mot du nom complet.
 *
 * Un salut se fait par le prenom : « مرحبا دعيه », pas « مرحبا دعيه أدو ».
 * Les noms d'ici comptent souvent trois ou quatre parties, et la barre du haut
 * doit rester lisible sur un telephone.
 */
function prenom(nomComplet: string): string {
  return nomComplet.trim().split(/\s+/)[0] || nomComplet;
}

/**
 * Barre du haut : ouverture mobile, repli desktop, contexte de travail, profil.
 *
 * Le selecteur de فصل est enveloppe dans un `Suspense` : il lit les parametres
 * d'URL, ce qui impose une frontiere de suspension au rendu statique.
 */
export default function Topbar({
  user,
  fusul,
  faslCourant,
  onOpenMobile,
  onToggleCollapsed,
}: Props) {
  return (
    <header className="sticky top-0 z-30 flex items-center gap-2 border-b border-gray-100 bg-white px-3 py-2.5 sm:gap-3 sm:py-3 lg:px-6">
      <button
        type="button"
        onClick={onOpenMobile}
        aria-label="فتح القائمة"
        className="rounded-xl p-2 text-gris transition-colors hover:bg-gray-50 hover:text-primary lg:hidden"
      >
        <Menu size={18} />
      </button>

      <button
        type="button"
        onClick={onToggleCollapsed}
        aria-label="طي القائمة"
        className="hidden rounded-xl p-2 text-gris transition-colors hover:bg-gray-50 hover:text-primary lg:block"
      >
        <Menu size={18} />
      </button>

      {/* Le nom de l'institut figure deja dans le bandeau lateral. Cette
          place revient a la personne connectee : sur un telephone, ou tout le
          reste est masque, c'est le seul repere qui dise « c'est bien ton
          compte ». Le prenom suffit, et tient dans la largeur. */}
      <p className="min-w-0 flex-1 truncate text-sm font-semibold text-dark">
        مرحبا <span className="text-primary">{prenom(user.full_name_ar)}</span>
      </p>

      <div className="flex flex-1 items-center justify-end gap-2 sm:flex-none sm:gap-3">
        {user.role === "STUDENT" ? null : (
          <Suspense fallback={null}>
            <SelecteurFasl fusul={fusul} courant={faslCourant} />
          </Suspense>
        )}
        <UserMenu user={user} />
      </div>
    </header>
  );
}
