"use client";

import { useEffect, useState } from "react";
import { Check, Copy, ExternalLink, Tv } from "lucide-react";

/**
 * Le lien de l'ecran de salle, pret a etre copie.
 *
 * L'adresse est construite depuis celle par laquelle on est arrive
 * (`window.location.origin`), et non depuis une valeur figee : le lien copie
 * depuis un telephone sur le reseau de l'institut porte l'adresse du reseau,
 * celui copie depuis le serveur porte la sienne. Coder l'origine en dur
 * donnerait un lien juste sur un poste et faux sur tous les autres.
 *
 * L'origine ne peut se lire que dans le navigateur : le premier rendu affiche
 * donc le chemin seul, remplace des l'hydratation.
 */
export function LienDirect({
  code,
  compact = false,
}: {
  code: string;
  /** Forme reduite, pour une liste. */
  compact?: boolean;
}) {
  const chemin = `/direct/${code}`;
  const [adresse, setAdresse] = useState(chemin);
  const [copie, setCopie] = useState(false);

  // Differe d'un tour : poser l'etat dans le corps de l'effet serait une mise
  // a jour synchrone, et le rendu enchainerait deux passes pour rien.
  useEffect(() => {
    const pose = setTimeout(
      () => setAdresse(`${window.location.origin}${chemin}`),
      0,
    );
    return () => clearTimeout(pose);
  }, [chemin]);

  useEffect(() => {
    if (!copie) return;
    const minuterie = setTimeout(() => setCopie(false), 2000);
    return () => clearTimeout(minuterie);
  }, [copie]);

  async function copier() {
    try {
      await navigator.clipboard.writeText(adresse);
      setCopie(true);
    } catch {
      // Presse-papiers refuse — page non securisee, permission absente.
      // On selectionne le texte : la copie manuelle reste possible.
      const champ = document.getElementById(`lien-${code}`) as
        | HTMLInputElement
        | null;
      champ?.select();
    }
  }

  if (compact) {
    return (
      <button
        type="button"
        onClick={copier}
        title="نسخ رابط شاشة القاعة"
        className="flex items-center gap-1.5 rounded-xl border border-gray-200 px-3.5 py-2 text-sm font-medium text-gris transition-colors hover:bg-gray-50"
      >
        {copie ? <Check size={14} className="text-primary" /> : <Copy size={14} />}
        <span className="chiffres">{code}</span>
      </button>
    );
  }

  return (
    <div className="rounded-2xl border border-gray-100 bg-gray-50 p-3.5">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-dark">
        <Tv size={15} className="text-gris" />
        رابط شاشة القاعة
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <input
          id={`lien-${code}`}
          type="text"
          readOnly
          dir="ltr"
          value={adresse}
          onFocus={(e) => e.currentTarget.select()}
          className="champ min-w-0 flex-1 bg-white text-xs"
        />

        <button
          type="button"
          onClick={copier}
          className="flex items-center gap-1.5 rounded-xl px-3.5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
          style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
        >
          {copie ? <Check size={15} /> : <Copy size={15} />}
          {copie ? "نُسخ" : "نسخ"}
        </button>

        <a
          href={chemin}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm font-medium text-gris transition-colors hover:bg-gray-100"
        >
          <ExternalLink size={15} />
          فتح
        </a>
      </div>

      <p className="mt-2 text-xs leading-relaxed text-gris">
        يُفتح دون تسجيل دخول. شاركه مع القاعة أو اعرضه على الشاشة.
      </p>
    </div>
  );
}
