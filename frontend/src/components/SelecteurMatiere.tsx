"use client";

import { useRouter } from "next/navigation";
import type { AvancementSaisie } from "@/lib/types";

/**
 * Choix de la classe puis de la matiere, en deux listes deroulantes liees.
 *
 * Avec 27 matieres reparties sur quatre اقسام, une liste unique obligeait a
 * chercher a l'oeil. La premiere liste reduit le champ, la seconde ne montre
 * que ce qui appartient a la classe choisie.
 *
 * Les libelles se limitent aux noms : le detail chiffre — effectif, ضارب,
 * avancement — figure deja en tete de la grille, l'empiler ici alourdissait la
 * lecture. Choisir une matiere ouvre sa grille ; il n'y a rien d'autre a
 * actionner.
 */
export function SelecteurMatiere({
  avancement,
  sectionChoisie,
  matiereChoisie,
}: {
  avancement: AvancementSaisie;
  sectionChoisie: number | null;
  matiereChoisie: number | null;
}) {
  const router = useRouter();
  const session = avancement.semester.session;

  const section =
    avancement.sections.find((s) => s.id === sectionChoisie) ??
    avancement.sections[0];

  const matieres = section?.matieres ?? [];

  function allerVers(sectionId: number, curriculum?: number) {
    const params = new URLSearchParams({
      section: String(sectionId),
      session,
    });
    if (curriculum) params.set("curriculum", String(curriculum));
    router.push(`/saisie-notes?${params.toString()}`);
  }

  if (avancement.sections.length === 0) return null;

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-gris">
          القسم
        </span>
        <select
          value={section?.id ?? ""}
          aria-label="القسم"
          // Changer de classe remet le choix de la matiere a zero : celle
          // d'avant n'appartient pas a la nouvelle classe.
          onChange={(event) => allerVers(Number(event.target.value))}
          className="champ"
        >
          {avancement.sections.map((bloc) => (
            <option key={bloc.id} value={bloc.id}>
              {bloc.name_ar}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="mb-1.5 block text-xs font-medium text-gris">
          المادة
        </span>
        <select
          value={matiereChoisie ?? ""}
          aria-label="المادة"
          disabled={matieres.length === 0}
          onChange={(event) =>
            allerVers(section.id, Number(event.target.value))
          }
          className="champ"
        >
          <option value="">— اختر المادة —</option>
          {matieres.map((matiere) => (
            <option key={matiere.curriculum} value={matiere.curriculum}>
              {matiere.subject_name}
            </option>
          ))}
        </select>
      </label>

    </div>
  );
}
