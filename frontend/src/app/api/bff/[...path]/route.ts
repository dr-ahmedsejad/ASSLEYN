/**
 * Relais BFF vers l'API Django.
 *
 * Les composants client ne connaissent que ce chemin. Le serveur Next y
 * rattache le cookie de session et le jeton CSRF, puis transmet a Django.
 * Aucun secret ne transite par le navigateur.
 *
 * Le relais est volontairement restreint : seuls les prefixes listes dans
 * `CHEMINS_AUTORISES` passent. Une route ajoutee cote Django n'est pas
 * exposee tant qu'elle n'a pas ete declaree ici.
 */

import { NextRequest, NextResponse } from "next/server";

import { authHeaders } from "@/lib/api";
import { API_BASE_URL, API_PREFIX } from "@/lib/config";

const CHEMINS_AUTORISES = [
  "grading/avancement",
  "grading/sheet",
  "grading/sheet/bulk",
  "semester-results",
  "annual-results",
  "curricula",
  "subjects",
  "sections",
  "semesters",
  "enrollments",
  "years",
  "rbac/matrice",
  "rbac/utilisateurs",
  "results/recompute",
  "grade-history",
  // Concours : la console du jury travaille depuis le navigateur, parce
  // qu'elle doit pouvoir differer ses gestes quand le reseau manque.
  "competitions",
  "tours",
];

function estAutorise(chemin: string): boolean {
  return CHEMINS_AUTORISES.some(
    (prefixe) => chemin === prefixe || chemin.startsWith(`${prefixe}/`),
  );
}

async function relayer(
  requete: NextRequest,
  contexte: { params: Promise<{ path: string[] }> },
): Promise<NextResponse> {
  const { path } = await contexte.params;
  // Neutralise toute tentative de remontee de chemin.
  const chemin = path
    .filter((segment) => segment !== "." && segment !== "..")
    .join("/");

  if (!estAutorise(chemin)) {
    return NextResponse.json(
      { detail: "المسار غير متاح." },
      { status: 404 },
    );
  }

  const entetes = await authHeaders(requete.method);
  entetes.set("Accept", "application/json");

  let corps: string | undefined;
  if (requete.method !== "GET" && requete.method !== "DELETE") {
    corps = await requete.text();
    entetes.set("Content-Type", "application/json");
  }

  const url = new URL(`${API_BASE_URL}${API_PREFIX}/${chemin}/`);
  requete.nextUrl.searchParams.forEach((valeur, cle) => {
    url.searchParams.set(cle, valeur);
  });

  const reponse = await fetch(url, {
    method: requete.method,
    headers: entetes,
    body: corps,
    cache: "no-store",
  });

  const texte = await reponse.text();
  return new NextResponse(texte || null, {
    status: reponse.status,
    headers: {
      "Content-Type":
        reponse.headers.get("Content-Type") ?? "application/json",
    },
  });
}

export const GET = relayer;
export const POST = relayer;
export const PATCH = relayer;
export const PUT = relayer;
export const DELETE = relayer;

export const dynamic = "force-dynamic";
