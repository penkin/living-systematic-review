import { describe, expect, it } from "vitest";
import { computeRecord } from "./reviewEngine";
import { recordSeeds } from "./reviewData";

const record = (id: string) => {
  const seed = recordSeeds.find(item => item.id === id);
  if (!seed) throw new Error(`Missing seed ${id}`);
  return computeRecord(seed);
};

describe("review signal engine", () => {
  it("surfaces very-low-certainty renal evidence as High and preserves the rubric score", () => {
    const result = record("SYN-002");
    expect(result.finalSignal).toBe("HIGH");
    expect(result.lane).toBe("review_now");
    expect(result.baseSignal).toBe("HIGH");
    expect(result.rubricSignal).toBe("HIGH");
    expect(result.totalScore).toBe(14);
  });

  it("keeps a large study on a moderate-certainty outcome Low under the baseline rule", () => {
    const result = record("SYN-005");
    expect(result.finalSignal).toBe("LOW");
    expect(result.baseSignal).toBe("LOW");
    expect(result.rubricSignal).toBe("MODERATE");
    expect(result.lane).toBe("visible");
  });

  it("routes protocols, retractions, duplicates, commentaries, and abstracts to unresolved", () => {
    for (const id of ["SYN-012", "SYN-016", "SYN-019", "SYN-027", "SYN-031"]) {
      const result = record(id);
      expect(result.finalSignal, id).toBe("UNRESOLVED");
      expect(result.lane, id).toBe("unresolved");
      expect(result.totalScore, id).toBeNull();
    }
  });

  it("applies the harm override and links related study-family publications", () => {
    const harm = record("SYN-022");
    expect(harm.finalSignal).toBe("HIGH");
    expect(harm.overrideFlags).toContain("Harm override");

    const primary = record("SYN-014");
    const secondary = record("SYN-028");
    expect(primary.duplicateGroupId).toBe("CR-CPT-001");
    expect(secondary.duplicateGroupId).toBe("CR-CPT-001");
  });

  it("raises West African mortality evidence one level for a context gap", () => {
    const result = record("SYN-034");
    expect(result.baseSignal).toBe("LOW");
    expect(result.finalSignal).toBe("MODERATE");
    expect(result.overrideFlags).toContain("Context gap modifier");
  });

  it("does not silently map new outcomes or out-of-scope records into the signal queue", () => {
    expect(record("SYN-029").finalSignal).toBe("UNRESOLVED");
    expect(record("SYN-033").finalSignal).toBe("OUT_OF_SCOPE");
    expect(record("SYN-003").finalSignal).toBe("OUT_OF_SCOPE");
  });
});
