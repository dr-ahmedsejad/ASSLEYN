import CoquilleServeur from "@/components/layout/CoquilleServeur";

/**
 * Coquille des pages metier.
 *
 * Deux redirections defensives, posees par `CoquilleServeur` : pas de session
 * → page de connexion ; mot de passe provisoire → page de changement. Le
 * serveur decide, pas le navigateur.
 */
export default function LayoutApplication({
  children,
}: {
  children: React.ReactNode;
}) {
  return <CoquilleServeur>{children}</CoquilleServeur>;
}
