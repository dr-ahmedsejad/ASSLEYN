"use client";

import { useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";

/**
 * Champ de mot de passe avec bascule d'affichage.
 *
 * Sur un telephone, une saisie masquee se corrige a l'aveugle : l'oeil evite
 * de recommencer trois fois. Le bouton est place au bord de fin du champ —
 * `inset-inline-end`, donc a gauche en lecture arabe — et reste hors du flux
 * de saisie : `type="button"`, sinon la touche Entree le declencherait au lieu
 * d'envoyer le formulaire.
 *
 * La bascule est purement locale : rien n'est memorise, chaque champ repart
 * masque.
 */
export function ChampMotDePasse({
  nom,
  libelle,
  autoComplete,
  longueurMinimale,
  autoFocus,
}: {
  nom: string;
  libelle: string;
  autoComplete: string;
  longueurMinimale?: number;
  autoFocus?: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const identifiant = useId();

  return (
    <div>
      <label
        htmlFor={identifiant}
        className="mb-1.5 block text-sm font-medium text-dark-soft"
      >
        {libelle}
      </label>

      <div className="relative">
        <input
          id={identifiant}
          name={nom}
          type={visible ? "text" : "password"}
          required
          minLength={longueurMinimale}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          className="champ champ-mdp"
        />

        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-pressed={visible}
          aria-controls={identifiant}
          aria-label={visible ? "إخفاء كلمة السر" : "إظهار كلمة السر"}
          title={visible ? "إخفاء كلمة السر" : "إظهار كلمة السر"}
          className="absolute inset-inline-end-0 top-1/2 flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-lg text-gris transition-colors hover:bg-gray-50 hover:text-dark"
          style={{ insetInlineEnd: "0.35rem" }}
        >
          {visible ? <EyeOff size={17} /> : <Eye size={17} />}
        </button>
      </div>
    </div>
  );
}
