/** Types du domaine, alignes sur le schema OpenAPI de l'API Django. */

export type Role = "ADMIN" | "ASSISTANT" | "TEACHER" | "STUDENT";

export type SemesterState = "DRAFT" | "OPEN" | "CLOSED" | "PUBLISHED";

/** Les deux sessions d'examen d'un فصل. */
export type ExamSession = "NORMAL" | "RESIT";

export type GradeStatus =
  | "ENTERED"
  | "ABSENT"
  | "EXCUSED"
  | "EXEMPT"
  | "MISSING";

export type OverallDecision = "PASSED" | "RESIT";

export type SubjectDecisionCode =
  | "SATISFIED"
  | "NOT_SATISFIED"
  | "NOT_APPLICABLE";

export interface CurrentUser {
  id: number;
  username: string;
  full_name_ar: string;
  role: Role;
  role_display: string;
  must_change_password: boolean;
  matricule: string | null;
  /** Capacites effectives : role + exceptions individuelles. */
  permissions: string[];
}

export interface PermissionEtat {
  code: string;
  libelle: string;
  par_le_role: boolean;
  /** `null` : aucune exception, la personne suit son role. */
  exception: boolean | null;
  raison: string;
  effective: boolean;
}

export interface MatriceDroits {
  roles: { code: Role; libelle: string; utilisateurs: number }[];
  categories: {
    titre: string;
    permissions: {
      code: string;
      libelle: string;
      roles: Record<string, { accordee: boolean; verrouillee: boolean }>;
    }[];
  }[];
}

export interface UtilisateurDroits {
  id: number;
  username: string;
  full_name_ar: string;
  role: Role;
  role_display: string;
  exceptions: { permission: string; granted: boolean }[];
}

export interface DetailDroitsUtilisateur {
  id: number;
  username: string;
  full_name_ar: string;
  role: Role;
  role_display: string;
  permissions: PermissionEtat[];
}

export interface Section {
  id: number;
  code: string;
  name_ar: string;
  display_order: number;
  is_active: boolean;
  student_count: number;
}

export interface AcademicYear {
  id: number;
  label: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface Semester {
  id: number;
  year: number;
  year_label: string;
  number: number;
  start_date: string;
  end_date: string;
  state: SemesterState;
  state_display: string;
  current_session: ExamSession;
  current_session_display: string;
  weight: string;
  published_at: string | null;
}

/** Barre de reussite effectivement appliquee a un قسم pour un فصل. */
export interface SeuilSection {
  section: number;
  section_name: string;
  pass_threshold: string;
  compensation_floor: string;
  version: number;
  propre_au_fasl: boolean;
  note: string;
}

export interface Subject {
  id: number;
  code: string;
  name_ar: string;
  display_order: number;
  is_active: boolean;
}

export interface Curriculum {
  id: number;
  section: number;
  section_name: string;
  semester: number;
  semester_number: number;
  subject: number;
  subject_code: string;
  subject_name: string;
  coefficient: string;
  display_order: number;
  is_active: boolean;
}

export interface GradeRow {
  enrollment: number;
  matricule: string;
  full_name_ar: string;
  /** Decimal : chaine cote API, mais on tolere un nombre par prudence. */
  value: string | number | null;
  /** Note de la session normale, rappelee pendant le rattrapage. */
  normal_value?: string | number | null;
  status: GradeStatus;
  updated_at: string | null;
}

export interface GradeSheet {
  curriculum: {
    id: number;
    section_name: string;
    subject_name: string;
    coefficient: string;
    semester_number: number;
    semester_state: SemesterState;
    editable: boolean;
  };
  session: ExamSession;
  session_display: string;
  current_session: ExamSession;
  max_grade: string;
  completion: { saisies: number; total: number };
  rows: GradeRow[];
}

export interface SubjectResult {
  subject_code: string;
  subject_name: string;
  coefficient: string;
  value: string | null;
  normal_value: string | null;
  resit_value: string | null;
  effective_value: string | null;
  decision: SubjectDecisionCode;
  decision_display: string;
}

export interface SemesterResult {
  id: number;
  matricule: string;
  full_name_ar: string;
  section_name: string;
  semester: number;
  semester_number: number;
  session: ExamSession;
  session_display: string;
  pass_threshold: string;
  average: string;
  average_display: string;
  total_coefficient: string;
  rank: number;
  cohort_size: number;
  decision_computed: OverallDecision;
  decision_final: OverallDecision;
  decision_display: string;
  is_overridden: boolean;
  override_reason: string;
  computed_at: string;
  subject_results: SubjectResult[];
}

export interface AnnualResult {
  id: number;
  matricule: string;
  full_name_ar: string;
  section_name: string;
  year: number;
  average: string;
  average_display: string;
  rank: number;
  cohort_size: number;
  semester_count: number;
  decision_computed: OverallDecision;
  decision_final: OverallDecision;
  decision_display: string;
  override_reason: string;
  computed_at: string;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Enrollment {
  id: number;
  student: number;
  matricule: string;
  full_name_ar: string;
  section: number;
  section_name: string;
  year: number;
  is_active: boolean;
}

export interface GradeHistoryEntry {
  id: number;
  grade: number;
  matricule: string;
  full_name_ar: string;
  subject_name: string;
  section_name: string;
  old_value: string | null;
  new_value: string | null;
  old_status: string;
  new_status: GradeStatus;
  reason: string;
  changed_by: number;
  changed_by_name: string;
  changed_at: string;
}


export type StatutSaisie =
  | "COMPLETE"
  | "PARTIELLE"
  | "NON_COMMENCEE"
  | "SANS_OBJET";

export interface MatiereAvancement {
  curriculum: number;
  subject_name: string;
  subject_code: string;
  coefficient: string;
  attendues: number;
  saisies: number;
  statut: StatutSaisie;
}

export interface SectionAvancement {
  id: number;
  name_ar: string;
  effectif: number;
  attendues: number;
  saisies: number;
  matieres: MatiereAvancement[];
}

/** Etat de la saisie d'un فصل, matiere par matiere. */
export interface AvancementSaisie {
  semester: {
    id: number;
    number: number;
    year_label: string;
    state: SemesterState;
    state_display: string;
    session: ExamSession;
    session_display: string;
    current_session: ExamSession;
    editable: boolean;
  };
  total: { attendues: number; saisies: number };
  sections: SectionAvancement[];
}

// --------------------------------------------------------------------------
// Surveillance des connexions
// --------------------------------------------------------------------------

export type IssueConnexion =
  | "SUCCESS"
  | "BAD_PASSWORD"
  | "UNKNOWN_USER"
  | "INACTIVE"
  | "LOCKED";

export interface TentativeConnexion {
  id: number;
  username: string;
  full_name_ar: string;
  role: Role | null;
  outcome: IssueConnexion;
  outcome_display: string;
  ip_address: string | null;
  user_agent: string;
  at: string;
}

export interface Verrou {
  id: number;
  username: string;
  full_name_ar: string;
  level: number;
  duree_minutes: number;
  started_at: string;
  until: string;
  ip_address: string | null;
  actif: boolean;
  secondes_restantes: number;
  released_at: string | null;
  released_by_name: string;
}

export interface VisiteuseAssidue {
  username: string;
  full_name_ar: string;
  visites: number;
  derniere: string;
}

export interface StatistiquesVisites {
  periode: string;
  visites: number;
  visiteurs: number;
  visites_aujourdhui: number;
  echecs: number;
  blocages: number;
  blocages_actifs: number;
  top_etudiantes: VisiteuseAssidue[];
  par_jour: { jour: string; visites: number }[];
}

/** Une ligne de la liste des comptes (`/rbac/comptes/`). */
export interface Compte {
  id: number;
  username: string;
  full_name_ar: string;
  role: Role;
  role_display: string;
  matricule: string | null;
  phone: string;
  is_active: boolean;
  must_change_password: boolean;
  last_login: string | null;
  date_joined: string;
  verrouille: boolean;
}

// --------------------------------------------------------------------------
// Concours
// --------------------------------------------------------------------------

export type EtatCompetition = "DRAFT" | "RUNNING" | "FINISHED";
export type IssueTour = "PENDING" | "CORRECT" | "NO_ANSWER";

export interface GroupeConcours {
  id: number;
  name: string;
  display_order: number;
  color: string;
  members: MembreGroupe[];
}

/**
 * Une participante d'un groupe : un nom, rien de plus.
 *
 * Ces listes disent qui compose une equipe le temps d'une seance. Les
 * participantes ne se connectent pas et rien ne leur est rattache.
 */
export interface MembreGroupe {
  id: number;
  name: string;
  display_order: number;
}

export interface QuestionConcours {
  id: number;
  text: string;
  /** Aide-memoire du jury. Ne sort jamais par l'ecran de la salle. */
  answer: string;
  display_order: number;
}

/** Les deux formes de session. Voir `CompetitionKind` cote serveur. */
export type TypeCompetition = "CULTURELLE" | "POETIQUE";

export interface Competition {
  id: number;
  name: string;
  kind: TypeCompetition;
  kind_display: string;
  /** Faux pour une ندوة شعرية : ni saisie ni projection d'enonces. */
  avec_questions: boolean;
  code: string;
  state: EtatCompetition;
  state_display: string;
  turn_seconds: number;
  /**
   * Enonces gardes hors du deroule, pour les departages.
   *
   * Une manche consomme un enonce par groupe encore a egalite : cinq groupes
   * et vingt reserves, ce sont quatre manches possibles.
   */
  questions_reservees: number;
  show_question: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  tours_prevus: number;
  nombre_groupes: number;
  nombre_questions: number;
  groups: GroupeConcours[];
  questions: QuestionConcours[];
}

export interface Tour {
  id: number;
  index: number;
  round_number: number;
  group: number;
  group_name: string;
  group_color: string;
  /** Zero pour un tour ordinaire, sinon le numero de la manche de departage. */
  tiebreak_round: number;
  question: number | null;
  question_text: string | null;
  /** Aide-memoire du jury. Absente de l'ecran de la salle. */
  question_answer: string | null;
  started_at: string | null;
  outcome: IssueTour;
  outcome_display: string;
  decided_at: string | null;
  awarded_late: boolean;
  note: string;
}

export interface LigneClassement {
  id: number;
  name: string;
  color: string;
  display_order: number;
  points: number;
  joues: number;
  restants: number;
  /** Resultat manche par manche des departages. Vide s'il n'y en a pas eu. */
  departage: number[];
  rank: number;
}

/** Tout ce dont la console du jury a besoin, livre en une fois. */
export interface DerouleConcours {
  competition: Competition;
  maintenant: string;
  tours: Tour[];
  classement: LigneClassement[];
  /** L'egalite qui reste a departager, et de quoi la departager. */
  departage: {
    groupes: string[];
    /** Faux : le jury posera sa question a voix haute. */
    avec_enonces: boolean;
  };
}

/** Ce que voit la salle. Rien de plus. */
export interface EcranDirect {
  name: string;
  kind: TypeCompetition;
  kind_display: string;
  state: EtatCompetition;
  state_display: string;
  turn_seconds: number;
  maintenant: string;
  /** `null` pour une ندوة شعرية : elle n'a pas de dernier tour ecrit d'avance. */
  tours_prevus: number | null;
  tours_joues: number;
  tour: {
    index: number;
    round_number: number;
    group_name: string;
    group_color: string;
    /** Les prenoms de la salle. Aucun matricule ne sort par cette route. */
    group_members: string[];
    tiebreak_round: number;
    question_text: string | null;
    started_at: string | null;
    secondes_restantes: number;
    en_marche: boolean;
  } | null;
  classement: LigneClassement[];
}
