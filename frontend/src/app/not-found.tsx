export const metadata = { title: "غير موجود — معهد الأصلين" };

/**
 * Page introuvable hors de l'application authentifiee.
 *
 * Elle couvre surtout l'ecran de la salle : un code de competition mal recopie
 * depuis une projection, ou une session supprimee. Cet ecran-la est projete
 * devant une assemblee — le fond sombre de la salle vaut mieux qu'une page
 * blanche, et le message doit se lire de loin.
 */
export default function Introuvable() {
  return (
    <div
      className="flex min-h-screen flex-col items-center justify-center gap-3 px-6 text-center"
      style={{
        background:
          "radial-gradient(1400px 700px at 50% -20%, rgba(0,102,51,.55), transparent 65%), #04160d",
      }}
    >
      <p className="text-xs font-semibold tracking-[0.22em] text-accent">
        معهد الأصلين
      </p>
      <p className="chiffres text-5xl font-bold text-white/80 sm:text-7xl">
        404
      </p>
      <h1 className="text-xl font-bold text-white sm:text-3xl">
        لا توجد مسابقة بهذا الرمز
      </h1>
      <p className="max-w-md text-sm leading-relaxed text-white/60 sm:text-base">
        تحقق من الرمز المعروض على الشاشة. قد تكون المسابقة حُذفت، أو أن الرمز
        نُسخ ناقصا.
      </p>
    </div>
  );
}
