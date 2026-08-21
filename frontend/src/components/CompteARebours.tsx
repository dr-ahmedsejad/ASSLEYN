"use client";

import { useEffect, useState } from "react";
import { LockKeyhole } from "lucide-react";

/**
 * Minuteur de reouverture d'un compte bloque.
 *
 * Sans lui, l'ecran dit « reessayez plus tard » et l'etudiante reessaie
 * aussitot — puis appelle l'administration. Le decompte repond a la seule
 * question qu'elle se pose : combien de temps encore.
 *
 * Le compte a rebours part de la valeur donnee par le serveur. Il n'y a pas
 * d'horloge partagee : l'heure du telephone peut etre fausse, une duree ne
 * l'est jamais.
 *
 * L'appelant monte ce composant avec `key={secondes}` : une nouvelle reponse
 * du serveur le recree avec la duree fraiche, plutot qu'un effet qui
 * ecraserait le decompte en cours.
 */
export function CompteARebours({
  secondes,
  niveau,
  message,
  onFin,
}: {
  secondes: number;
  niveau?: number;
  message?: string;
  onFin?: () => void;
}) {
  const [restant, setRestant] = useState(secondes);

  useEffect(() => {
    if (restant <= 0) {
      onFin?.();
      return;
    }
    const minuterie = setTimeout(() => setRestant((s) => s - 1), 1000);
    return () => clearTimeout(minuterie);
  }, [restant, onFin]);

  const minutes = Math.floor(Math.max(restant, 0) / 60);
  const secondesRestantes = Math.max(restant, 0) % 60;
  const termine = restant <= 0;

  return (
    <div
      role="alert"
      className="rounded-xl border border-red-200 bg-red-50 px-3.5 py-3 text-sm text-red-700"
    >
      <p className="flex items-center gap-2 font-semibold">
        <LockKeyhole size={16} />
        {termine ? "يمكنك المحاولة الآن" : "تم إقفال الحساب مؤقتا"}
      </p>

      {termine ? (
        <p className="mt-1.5 leading-relaxed">
          انتهت مدة الإقفال. أعيدي إدخال كلمة السر.
        </p>
      ) : (
        <>
          <p
            className="chiffres mt-2 text-center text-3xl font-bold tabular-nums"
            aria-live="polite"
          >
            {minutes}:{String(secondesRestantes).padStart(2, "0")}
          </p>
          <p className="mt-1.5 text-center text-xs leading-relaxed">
            {message ?? "بعد عدة محاولات خاطئة."}
            {niveau && niveau > 1 ? (
              <>
                {" "}
                تطول المدة كلما تكررت المحاولات.
              </>
            ) : null}
          </p>
          <p className="mt-2 text-center text-xs">
            إن نسيت كلمة السر، راجعي مصلحة الامتحانات.
          </p>
        </>
      )}
    </div>
  );
}
