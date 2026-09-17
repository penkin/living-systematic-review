export type SignalLevel = "HIGH" | "MODERATE" | "LOW";
export type PrimaryStatus = SignalLevel | "UNRESOLVED" | "NOT_RELEVANT" | "OUT_OF_SCOPE";
export type WorkflowLane = "review_now" | "watch" | "visible" | "unresolved" | "context" | "excluded";
export type ReviewDecision = "CONFIRM" | "OVERRIDE" | "REMAP" | "DEFER" | "EXCLUDE";

export const OUTCOMES = [
  { id: "O1", name: "All-cause mortality during heat events", studies: 14, certainty: "Moderate", uncertaintyPoints: 1 },
  { id: "O2", name: "Heat-related emergency-department attendance", studies: 9, certainty: "Moderate", uncertaintyPoints: 1 },
  { id: "O3", name: "Cardiovascular mortality", studies: 6, certainty: "Low", uncertaintyPoints: 2 },
  { id: "O4", name: "Occupational heat strain", studies: 5, certainty: "Low", uncertaintyPoints: 2 },
  { id: "O5", name: "Adverse birth outcomes", studies: 3, certainty: "Very low", uncertaintyPoints: 3 },
  { id: "O6", name: "Renal/kidney injury", studies: 2, certainty: "Very low", uncertaintyPoints: 3 },
  { id: "O7", name: "Cooling interventions", studies: 2, certainty: "Very low", uncertaintyPoints: 3 },
  { id: "O8", name: "Heat early-warning systems", studies: 1, certainty: "Very low", uncertaintyPoints: 3 },
  { id: "O9", name: "Mental-health service utilisation", studies: 1, certainty: "Very low", uncertaintyPoints: 3 },
] as const;

export type ScoreComponents = {
  relevance: number;
  lmic: number;
  equity: number;
  design: number;
  policy: number;
  novelty: number;
  uncertainty: number;
};

export type RecordSeed = {
  id: string;
  title: string;
  summary: string;
  year: number;
  language: string;
  country: string;
  region: string;
  setting: string;
  recordType: string;
  studyDesign: string;
  population: string;
  exposure: string;
  outcomeText: string;
  mappedOutcome?: string;
  possibleOutcomes?: string[];
  potentialNewOutcome?: string;
  relevanceLabel: "Direct" | "Mostly" | "Partial" | "Not relevant";
  scopeIssue?: string;
  scopeStatus: "signal" | "context" | "out_of_scope" | "scope_question";
  signalEligible: boolean;
  scores: ScoreComponents;
  certainty?: string;
  existingStudies?: number;
  harmReported?: boolean;
  newInterventionClass?: boolean;
  contextGap?: string;
  progressPlus?: string[];
  policyArea?: string;
  duplicateGroupId?: string;
  publicationStatus: "published" | "protocol" | "preprint_duplicate" | "commentary" | "conference_abstract" | "retracted" | "synthesis";
};

export type ComputedRecord = RecordSeed & {
  totalScore: number | null;
  rubricSignal: SignalLevel | null;
  baseSignal: SignalLevel | null;
  finalSignal: PrimaryStatus;
  lane: WorkflowLane;
  suggestedAction: string;
  overrideFlags: string[];
  fullReason: string;
  shortReason: string;
  aiConfidence: "High" | "Moderate" | "Low";
  reviewerDecision?: ReviewDecision;
  reviewerReason?: string;
  reviewerInitials?: string;
  reviewedAt?: string;
};

const unresolvedStatuses = new Set(["protocol", "preprint_duplicate", "commentary", "conference_abstract", "retracted"]);

function raiseSignal(level: SignalLevel): SignalLevel {
  if (level === "LOW") return "MODERATE";
  if (level === "MODERATE") return "HIGH";
  return "HIGH";
}

function scoreToSignal(score: number): SignalLevel {
  if (score >= 11) return "HIGH";
  if (score >= 6) return "MODERATE";
  return "LOW";
}

function certaintyToSignal(certainty?: string): SignalLevel | null {
  if (certainty === "Very low") return "HIGH";
  if (certainty === "Low") return "MODERATE";
  if (certainty === "Moderate") return "LOW";
  return null;
}

function outcomeLabel(seed: RecordSeed) {
  if (seed.mappedOutcome) {
    const outcome = OUTCOMES.find(item => item.id === seed.mappedOutcome);
    return `${seed.mappedOutcome} — ${outcome?.name ?? "Mapped H3 outcome"}`;
  }
  if (seed.possibleOutcomes?.length) return seed.possibleOutcomes.join(" / ");
  return seed.potentialNewOutcome ? `Potential new outcome — ${seed.potentialNewOutcome}` : "No mapped H3 outcome";
}

function buildReason(seed: RecordSeed, finalSignal: PrimaryStatus, overrideFlags: string[]) {
  if (finalSignal === "UNRESOLVED") {
    if (seed.publicationStatus === "retracted") return "Retracted article; dataset irregularities prevent a reliable signal decision.";
    if (seed.publicationStatus === "protocol") return "Protocol addresses the outcome but reports no empirical results for a signal decision.";
    if (seed.publicationStatus === "preprint_duplicate") return "Preprint duplicates an existing study and must not create a second independent signal.";
    if (seed.publicationStatus === "commentary") return "Commentary identifies a policy gap but provides no empirical primary-study signal.";
    if (seed.publicationStatus === "conference_abstract") return "Conference abstract lacks sufficient methods and effect estimates.";
    return "Human review is required before assigning a signal.";
  }
  if (finalSignal === "NOT_RELEVANT") {
    if (seed.scopeIssue) return seed.scopeIssue;
    return "The record does not report a mapped heat-related human health outcome.";
  }
  if (finalSignal === "OUT_OF_SCOPE") return seed.scopeIssue ?? "The record falls outside the current review population or geography scope.";
  if (overrideFlags.includes("Harm override")) return "Reports intervention harm, triggering the harm override.";
  if (overrideFlags.includes("New intervention class")) return "New intervention class addresses an evidence gap and triggers the High override.";
  if (seed.contextGap) return `${seed.contextGap}; context-gap modifier raises the review priority one level.`;
  if (seed.certainty === "Very low") return `${outcomeLabel(seed)} has very-low certainty with only ${seed.existingStudies ?? "limited"} existing studies.`;
  if (seed.certainty === "Low") return `${outcomeLabel(seed)} addresses an outcome with low existing certainty.`;
  if (seed.certainty === "Moderate") return `${outcomeLabel(seed)} is relevant, but existing evidence is already moderate certainty.`;
  return "Relevant evidence requires reviewer assessment for an update signal.";
}

function shortReason(seed: RecordSeed, finalSignal: PrimaryStatus, overrideFlags: string[]) {
  if (finalSignal === "UNRESOLVED") return buildReason(seed, finalSignal, overrideFlags);
  if (finalSignal === "NOT_RELEVANT") return seed.scopeIssue ?? "No mapped heat-related human health outcome is reported.";
  if (finalSignal === "OUT_OF_SCOPE") return seed.scopeIssue ?? "Outside the current review scope.";
  if (overrideFlags.includes("Harm override")) return "Intervention harm triggers immediate review regardless of score.";
  if (overrideFlags.includes("New intervention class")) return "New intervention class addresses an evidence gap and requires review.";
  if (seed.contextGap) return "Context gap raises priority for underrepresented evidence.";
  if (seed.certainty === "Very low") return `${outcomeLabel(seed)} has very-low certainty and limited existing evidence.`;
  if (seed.certainty === "Low") return `${outcomeLabel(seed)} addresses an outcome with low certainty.`;
  return `${outcomeLabel(seed)} is relevant, but existing certainty is moderate.`;
}

export function computeRecord(seed: RecordSeed): ComputedRecord {
  const overrideFlags: string[] = [];
  if (seed.harmReported) overrideFlags.push("Harm override");
  if (seed.newInterventionClass) overrideFlags.push("New intervention class");
  if (seed.contextGap) overrideFlags.push("Context gap modifier");
  if (seed.duplicateGroupId) overrideFlags.push("Study-family linked");

  let totalScore: number | null = null;
  let rubricSignal: SignalLevel | null = null;
  let baseSignal: SignalLevel | null = null;
  let finalSignal: PrimaryStatus;
  let lane: WorkflowLane;
  let suggestedAction: string;

  if (unresolvedStatuses.has(seed.publicationStatus) || seed.scopeStatus === "scope_question") {
    finalSignal = "UNRESOLVED";
    lane = "unresolved";
    suggestedAction = "No signal decision — human adjudication";
  } else if (seed.scopeStatus === "out_of_scope") {
    finalSignal = "OUT_OF_SCOPE";
    lane = "context";
    suggestedAction = "Retain as scope evidence";
  } else if (!seed.signalEligible || seed.scores.relevance === 0) {
    finalSignal = "NOT_RELEVANT";
    lane = seed.scopeStatus === "context" ? "context" : "excluded";
    suggestedAction = lane === "context" ? "Retain as context" : "Exclude from signal queue";
  } else {
    totalScore = Object.values(seed.scores).reduce((sum, value) => sum + value, 0);
    rubricSignal = scoreToSignal(totalScore);
    baseSignal = certaintyToSignal(seed.certainty);
    finalSignal = baseSignal ?? rubricSignal;
    if (seed.harmReported || seed.newInterventionClass) finalSignal = "HIGH";
    else if (seed.contextGap) finalSignal = raiseSignal(finalSignal);
    lane = finalSignal === "HIGH" ? "review_now" : finalSignal === "MODERATE" ? "watch" : "visible";
    suggestedAction = finalSignal === "HIGH" ? "Review now" : finalSignal === "MODERATE" ? "Review this cycle / watch" : "Visible but deprioritised";
  }

  const fullReason = buildReason(seed, finalSignal, overrideFlags);
  const short = shortReason(seed, finalSignal, overrideFlags);
  return {
    ...seed,
    totalScore,
    rubricSignal,
    baseSignal,
    finalSignal,
    lane,
    suggestedAction,
    overrideFlags,
    fullReason,
    shortReason: short.split(/\s+/).slice(0, 15).join(" "),
    aiConfidence: seed.possibleOutcomes?.length ? "Moderate" : "High",
  };
}

export const reviewConfiguration = {
  rubricVersion: "v0.2",
  summaryOfFindingsVersion: "H3-SoF-v1",
  decisionModel: "H3 certainty-first baseline with transparent A–G rubric diagnostics and explicit overrides",
  scope: "Empirical evidence concerning heat exposure, heat-related health or heat-response interventions, and African urban populations, with H3 outcomes defining the primary update-signal target.",
  thresholds: { high: "11–15 or override", moderate: "6–10", low: "0–5" },
  criteria: [
    { key: "A", label: "Relevance", max: 3 },
    { key: "B", label: "LMIC setting", max: 2 },
    { key: "C", label: "Equity relevance", max: 2 },
    { key: "D", label: "Study design", max: 2 },
    { key: "E", label: "Policy relevance", max: 2 },
    { key: "F", label: "Recency / novelty", max: 1 },
    { key: "G", label: "Review uncertainty", max: 3 },
  ],
};
