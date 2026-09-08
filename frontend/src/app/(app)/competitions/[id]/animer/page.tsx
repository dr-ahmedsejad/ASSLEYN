import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { ConsoleConcours } from "@/components/ConsoleConcours";
import { Refus } from "@/components/Refus";
import { Alerte, Carte } from "@/components/ui";
import { apiRequestOuIntrouvable } from "@/lib/api";
import { utilisateurAvec } from "@/lib/acces";
import { PERMISSIONS } from "@/lib/nav-config";
import type { DerouleConcours } from "@/lib/types";

export const metadata = { title: "إدارة المسابقة — معهد الأصلين" };

/**
 * Console du jury.
 *
 * Le deroule complet est charge ici, cote serveur, puis confie au composant
 * client : la suite se joue sans reseau. C'est aussi la raison pour laquelle
 * cette page ne doit pas etre rechargee pendant le concours — le rendu initial,
 * lui, a besoin du serveur.
 */
export default async function PageAnimer({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  if (!(await utilisateurAvec(PERMISSIONS.COMPETITION_ANIMER))) {
    return <Refus titre="إدارة المسابقة" />;
  }

  const { id } = await params;
  const deroule = await apiRequestOuIntrouvable<DerouleConcours>(
    `/competitions/${id}/deroule/`,
  );

  if (deroule.competition.state === "DRAFT") {
    redirect(`/competitions/${id}`);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-dark">
          {deroule.competition.name}
        </h1>
        <Link
          href="/competitions"
          className="flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
        >
          <ArrowRight size={15} />
          كل المسابقات
        </Link>
      </div>

      <Carte>
        <Alerte ton="info">
          لا تُحدِّث هذه الصفحة أثناء المسابقة. البرنامج كامل محفوظ في الجهاز،
          ويعمل دون شبكة — أما إعادة التحميل فتحتاج إلى الخادم.
        </Alerte>
      </Carte>

      {/* `key` sur l'etat : la console travaille sur une copie locale du
          deroule, qu'un simple rafraichissement ne remplace pas. Quand le jury
          termine la seance, il faut donc la remonter pour qu'elle reparte des
          donnees du serveur — sans quoi elle continuerait d'afficher un tour a
          lancer dans une session close. */}
      <ConsoleConcours
        key={deroule.competition.state}
        deroule={deroule}
      />
    </div>
  );
}
