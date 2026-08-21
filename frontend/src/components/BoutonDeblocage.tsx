"use client";

import { useActionState, useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { Unlock } from "lucide-react";

import { deverrouiller, type ResultatDeblocage } from "@/lib/securite-actions";

const ETAT_INITIAL: ResultatDeblocage = {};

function Bouton() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="flex items-center gap-1.5 rounded-xl px-3 py-2 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      style={{ background: "linear-gradient(135deg,#004d24,#006633)" }}
    >
      <Unlock size={14} />
      {pending ? "جارٍ الفتح…" : "فتح الحساب"}
    </button>
  );
}

/**
 * Deblocage d'un compte, avec le temps restant sous les yeux.
 *
 * Le decompte n'est pas decoratif : il dit a l'administration si le geste est
 * utile. Deux minutes restantes ne valent pas un appel a l'etablissement ;
 * vingt-cinq, si.
 */
export function BoutonDeblocage({
  verrou,
  secondes,
}: {
  verrou: number;
  secondes: number;
}) {
  const [etat, action] = useActionState(deverrouiller, ETAT_INITIAL);
  const [restant, setRestant] = useState(secondes);

  useEffect(() => {
    if (restant <= 0) return;
    const minuterie = setTimeout(() => setRestant((s) => s - 1), 1000);
    return () => clearTimeout(minuterie);
  }, [restant]);

  const minutes = Math.floor(Math.max(restant, 0) / 60);
  const reste = Math.max(restant, 0) % 60;

  return (
    <form action={action} className="flex items-center gap-3">
      <input type="hidden" name="verrou" value={verrou} />

      <span
        className="chiffres text-sm font-bold tabular-nums text-red-700"
        aria-label="الوقت المتبقي"
      >
        {minutes}:{String(reste).padStart(2, "0")}
      </span>

      {etat.erreur ? (
        <span role="alert" className="text-xs text-red-700">
          {etat.erreur}
        </span>
      ) : null}

      <Bouton />
    </form>
  );
}
