import Link from "next/link";
import { ArrowRight, FileQuestion } from "lucide-react";

export const metadata = { title: "الصفحة غير موجودة — معهد الأصلين" };

/**
 * Page introuvable, a l'interieur de l'application.
 *
 * Elle sert surtout aux liens qui ont vieilli : une competition supprimee, un
 * onglet reste ouvert, un signet vers une fiche qui n'existe plus. Le message
 * dit que la chose a disparu, pas qu'une erreur s'est produite — et il propose
 * la seule suite utile, revenir a l'accueil.
 */
export default function Introuvable() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-4 text-center">
      <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-green-50 text-primary">
        <FileQuestion size={28} />
      </span>

      <div>
        <p className="chiffres text-3xl font-bold text-dark">404</p>
        <h1 className="mt-1 text-lg font-bold text-dark">الصفحة غير موجودة</h1>
      </div>

      <p className="max-w-sm text-sm leading-relaxed text-gris">
        الرابط الذي فتحته لم يعد يشير إلى شيء. قد يكون العنصر حُذف، أو أن العنوان
        غير صحيح.
      </p>

      <Link
        href="/"
        className="flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
        style={{ background: "linear-gradient(135deg,#006633,#008844)" }}
      >
        <ArrowRight size={15} />
        العودة إلى الرئيسية
      </Link>
    </div>
  );
}
