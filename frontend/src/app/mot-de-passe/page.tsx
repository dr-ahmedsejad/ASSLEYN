import { redirect } from "next/navigation";

import { Alerte, Carte } from "@/components/ui";
import { getCurrentUser } from "@/lib/api";
import { FormulaireMotDePasse } from "./FormulaireMotDePasse";

export const metadata = { title: "تغيير كلمة السر — معهد الأصلين" };

export default async function PageMotDePasse() {
  const utilisateur = await getCurrentUser();
  if (!utilisateur) redirect("/connexion");

  const premiereConnexion = utilisateur.must_change_password;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold text-dark">تغيير كلمة السر</h1>

      <div className="max-w-sm">
        {premiereConnexion ? (
          <div className="mb-4">
            <Alerte ton="warning">
              كلمة السر الحالية مؤقتة. يجب تغييرها قبل متابعة الاستخدام.
            </Alerte>
          </div>
        ) : null}

        <Carte>
          <FormulaireMotDePasse />
        </Carte>
      </div>
    </div>
  );
}
