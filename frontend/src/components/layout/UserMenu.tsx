"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ChevronDown, KeyRound, LogOut } from "lucide-react";

import { deconnexion } from "@/lib/auth";
import type { CurrentUser } from "@/lib/types";

/**
 * Menu de profil : salut, role, changement de mot de passe, deconnexion.
 *
 * Le salut est ici, et non dans le titre de la barre : c'est le bloc qui
 * designe deja la personne connectee — son role, ses initiales, ses actions.
 * Le nom de l'institut, lui, reprend sa place au centre.
 */
export default function UserMenu({ user }: { user: CurrentUser }) {
  const [open, setOpen] = useState(false);
  const conteneur = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function surClicExterieur(event: MouseEvent) {
      if (
        conteneur.current &&
        !conteneur.current.contains(event.target as Node)
      ) {
        setOpen(false);
      }
    }
    function surEchap(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", surClicExterieur);
    document.addEventListener("keydown", surEchap);
    return () => {
      document.removeEventListener("mousedown", surClicExterieur);
      document.removeEventListener("keydown", surEchap);
    };
  }, []);

  const initiales = user.full_name_ar
    .split(" ")
    .map((partie) => partie[0])
    .join("")
    .slice(0, 2);

  return (
    <div ref={conteneur} className="relative border-s border-gray-100 ps-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition-colors hover:bg-gray-50"
      >
        {/* Colonne centree : le role se lit sous le nom, aligne sur son
            milieu — deux lignes qui designent la meme personne. */}
        <div className="flex min-w-0 flex-col items-center">
          {/* Le nom entier, pas seulement le prenom. La largeur est bornee et
              le nom tronque plutot que de pousser la barre : les noms d'ici
              comptent souvent trois ou quatre parties. */}
          <p
            className="max-w-40 truncate text-xs font-semibold leading-tight text-dark sm:max-w-64"
            title={user.full_name_ar}
          >
            مرحبا <span className="text-primary">{user.full_name_ar}</span>
          </p>
          <span
            className="mt-0.5 inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold"
            style={{ background: "rgba(0,102,51,0.08)", color: "#006633" }}
          >
            {user.role_display}
          </span>
        </div>

        <div
          className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 text-xs font-bold text-white"
          style={{
            background: "linear-gradient(135deg, #004d24, #006633)",
            borderColor: "#E5C018",
          }}
        >
          {initiales}
        </div>

        <ChevronDown
          size={13}
          className={`text-gris transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute end-0 top-full z-50 mt-2 w-60 overflow-hidden rounded-2xl border border-gray-100 bg-white shadow-card-lg"
        >
          <div
            className="border-b border-gray-100 px-4 py-3"
            style={{ background: "linear-gradient(135deg, #004d24, #006633)" }}
          >
            <div className="flex items-center gap-2.5">
              <div
                className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 text-sm font-bold text-white"
                style={{
                  background: "rgba(255,255,255,0.2)",
                  borderColor: "#E5C018",
                }}
              >
                {initiales}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-white">
                  {user.full_name_ar}
                </p>
                <p className="chiffres truncate text-xs text-white/70">
                  {user.matricule ?? user.username}
                </p>
              </div>
            </div>
          </div>

          <div className="py-1">
            <Link
              href="/mot-de-passe"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-dark-soft transition-colors hover:bg-gray-50 hover:text-primary"
            >
              <KeyRound size={14} className="text-gris" />
              تغيير كلمة السر
            </Link>
          </div>

          <div className="border-t border-gray-100 py-1">
            <form action={deconnexion}>
              <button
                type="submit"
                className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-gris transition-colors hover:bg-red-50 hover:text-secondary"
              >
                <LogOut size={14} style={{ color: "#C82020" }} />
                تسجيل الخروج
              </button>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
