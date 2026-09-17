import { useMemo, useState } from "react";
import { trpc } from "@/lib/trpc";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  FileSearch,
  Filter,
  Layers3,
  Map,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Target,
  XCircle,
} from "lucide-react";

type View = "inbox" | "equity" | "configuration";
type FilterKey = "all" | "review_now" | "watch" | "visible" | "unresolved" | "context" | "excluded";

const laneLabels: Record<FilterKey, string> = {
  all: "All records",
  review_now: "Review now",
  watch: "Review this cycle",
  visible: "Visible / low",
  unresolved: "Unresolved",
  context: "Context & scope",
  excluded: "Excluded",
};

const statusStyles: Record<string, string> = {
  HIGH: "bg-[#fbe9e7] text-[#c43b2f] border-[#f5c6c1]",
  MODERATE: "bg-[#fff4dc] text-[#a36c05] border-[#f5dfac]",
  LOW: "bg-[#e6f3ef] text-[#217561] border-[#bfe3d7]",
  UNRESOLVED: "bg-[#f1edf7] text-[#735a9c] border-[#ded4ee]",
  NOT_RELEVANT: "bg-[#f2f4f7] text-[#687483] border-[#dde2e8]",
  OUT_OF_SCOPE: "bg-[#f6eee7] text-[#8e6038] border-[#ead5c3]",
};

function scoreBar(value: number, max: number) {
  return `${Math.min(100, Math.round((value / max) * 100))}%`;
}

function signalLabel(record: any) {
  if (record.finalSignal === "NOT_RELEVANT") return "Not relevant";
  if (record.finalSignal === "OUT_OF_SCOPE") return "Out of scope";
  return record.finalSignal;
}

function LaneIcon({ lane }: { lane: string }) {
  if (lane === "review_now") return <ShieldAlert className="h-4 w-4" />;
  if (lane === "unresolved") return <CircleAlert className="h-4 w-4" />;
  if (lane === "context") return <BookOpen className="h-4 w-4" />;
  if (lane === "excluded") return <XCircle className="h-4 w-4" />;
  return <Target className="h-4 w-4" />;
}

export default function Home() {
  const [view, setView] = useState<View>("inbox");
  const [lane, setLane] = useState<FilterKey>("all");
  const [selectedId, setSelectedId] = useState("SYN-002");
  const [query, setQuery] = useState("");
  const [reviewDecision, setReviewDecision] = useState("CONFIRM");
  const [reviewReason, setReviewReason] = useState("");
  const [reviewerInitials, setReviewerInitials] = useState("");

  const recordsQuery = trpc.review.list.useQuery();
  const configQuery = trpc.review.config.useQuery();
  const utils = trpc.useUtils();
  const decisionMutation = trpc.review.updateDecision.useMutation({
    onSuccess: () => {
      void utils.review.list.invalidate();
      setReviewReason("");
    },
  });

  const records = recordsQuery.data ?? [];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return records.filter((record: any) => {
      const inLane = lane === "all" || record.lane === lane;
      const searchable = `${record.id} ${record.title} ${record.country} ${record.mappedOutcome ?? ""} ${record.outcomeText}`.toLowerCase();
      return inLane && (!needle || searchable.includes(needle));
    });
  }, [records, lane, query]);

  const selected = records.find((record: any) => record.id === selectedId) ?? records[0];
  const counts = useMemo(() => ({
    total: records.length,
    high: records.filter((r: any) => r.finalSignal === "HIGH").length,
    moderate: records.filter((r: any) => r.finalSignal === "MODERATE").length,
    low: records.filter((r: any) => r.finalSignal === "LOW").length,
    unresolved: records.filter((r: any) => r.lane === "unresolved").length,
    context: records.filter((r: any) => r.lane === "context").length,
    excluded: records.filter((r: any) => r.lane === "excluded").length,
    reviewed: records.filter((r: any) => r.reviewerDecision).length,
  }), [records]);

  const equityRecords = records.filter((record: any) => record.progressPlus?.length || record.contextGap);
  const subregions = Array.from(new Set(records.map((r: any) => r.region))).map(region => {
    const regionRecords = records.filter((r: any) => r.region === region);
    return { region, total: regionRecords.length, high: regionRecords.filter((r: any) => r.finalSignal === "HIGH").length, unresolved: regionRecords.filter((r: any) => r.lane === "unresolved").length };
  });

  const submitDecision = () => {
    if (!selected || !reviewReason.trim() || !reviewerInitials.trim()) return;
    decisionMutation.mutate({
      id: selected.id,
      decision: reviewDecision as "CONFIRM" | "OVERRIDE" | "REMAP" | "DEFER" | "EXCLUDE",
      reason: reviewReason.trim(),
      initials: reviewerInitials.trim(),
    });
  };

  return (
    <div className="min-h-screen bg-[#f6f8f9] text-[#17252b]">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-[246px] flex-col border-r border-[#dfe7e8] bg-[#10272c] text-[#d5e6e4] lg:flex">
        <div className="flex items-center gap-3 border-b border-white/10 px-6 py-6">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#dcf27d] text-[#1b3438]"><Activity className="h-5 w-5" /></div>
          <div><div className="text-sm font-bold tracking-tight text-white">Evidence Signal</div><div className="text-[10px] uppercase tracking-[0.2em] text-[#8eb2ad]">H3 review cockpit</div></div>
        </div>
        <div className="px-4 py-6">
          <div className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-[#739892]">Workspace</div>
          <nav className="space-y-1">
            <button onClick={() => setView("inbox")} className={`nav-item ${view === "inbox" ? "nav-item-active" : ""}`}><Layers3 className="h-4 w-4" />Review inbox <span className="nav-count">{counts.total}</span></button>
            <button onClick={() => setView("equity")} className={`nav-item ${view === "equity" ? "nav-item-active" : ""}`}><Map className="h-4 w-4" />Equity audit <span className="nav-count">{equityRecords.length}</span></button>
            <button onClick={() => setView("configuration")} className={`nav-item ${view === "configuration" ? "nav-item-active" : ""}`}><SlidersIcon />Rubric & rules</button>
          </nav>
        </div>
        <div className="mt-auto border-t border-white/10 p-5">
          <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-[#739892]">Review status</div>
          <div className="flex items-end justify-between"><span className="text-2xl font-semibold text-white">{counts.reviewed}</span><span className="text-xs text-[#8eb2ad]">of {counts.total} reviewed</span></div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10"><div className="h-full rounded-full bg-[#dcf27d]" style={{ width: `${counts.total ? (counts.reviewed / counts.total) * 100 : 0}%` }} /></div>
        </div>
      </aside>

      <main className="min-h-screen lg:pl-[246px]">
        <header className="sticky top-0 z-10 border-b border-[#dfe7e8] bg-[#f6f8f9]/95 px-5 py-4 backdrop-blur md:px-8">
          <div className="mx-auto flex max-w-[1500px] items-center justify-between gap-4">
            <div><div className="mb-1 text-[10px] font-bold uppercase tracking-[0.2em] text-[#6d8988]">Living evidence update signal</div><h1 className="text-xl font-semibold tracking-tight text-[#173239] md:text-2xl">Heat exposure & African urban health</h1></div>
            <div className="flex items-center gap-2"><span className="hidden rounded-full border border-[#c9ded6] bg-[#e9f5ef] px-3 py-1.5 text-xs font-medium text-[#28755e] sm:inline-flex"><span className="mr-2 mt-0.5 h-1.5 w-1.5 rounded-full bg-[#3f9c73]" />Demo dataset loaded</span><button className="icon-button" onClick={() => void recordsQuery.refetch()} title="Refresh"><RefreshCw className={`h-4 w-4 ${recordsQuery.isFetching ? "animate-spin" : ""}`} /></button></div>
          </div>
          <div className="mx-auto mt-4 flex max-w-[1500px] gap-2 overflow-x-auto lg:hidden"><button onClick={() => setView("inbox")} className={`mobile-tab ${view === "inbox" ? "mobile-tab-active" : ""}`}>Inbox</button><button onClick={() => setView("equity")} className={`mobile-tab ${view === "equity" ? "mobile-tab-active" : ""}`}>Equity audit</button><button onClick={() => setView("configuration")} className={`mobile-tab ${view === "configuration" ? "mobile-tab-active" : ""}`}>Rubric</button></div>
        </header>

        {view === "inbox" && <section className="mx-auto max-w-[1500px] px-5 py-6 md:px-8">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
            <StatCard label="Incoming records" value={counts.total} tone="neutral" />
            <StatCard label="Review now" value={counts.high} tone="high" />
            <StatCard label="This cycle" value={counts.moderate} tone="moderate" />
            <StatCard label="Visible / low" value={counts.low} tone="low" />
            <StatCard label="Unresolved" value={counts.unresolved} tone="unresolved" />
            <StatCard label="Context & scope" value={counts.context} tone="context" />
            <StatCard label="Excluded" value={counts.excluded} tone="neutral" />
          </div>

          <div className="mt-6 grid gap-5 xl:grid-cols-[minmax(360px,0.92fr)_minmax(560px,1.5fr)]">
            <section className="panel min-h-[680px] overflow-hidden">
              <div className="border-b border-[#e4eaeb] p-5"><div className="flex items-center justify-between gap-3"><div><h2 className="text-base font-semibold text-[#173239]">Priority queue</h2><p className="mt-1 text-xs text-[#718286]">Select a card to inspect the reasoning trail.</p></div><span className="rounded-full bg-[#edf3f2] px-2.5 py-1 text-xs font-semibold text-[#51716e]">{filtered.length} shown</span></div>
                <div className="mt-4 flex gap-2"><div className="relative flex-1"><Search className="absolute left-3 top-2.5 h-4 w-4 text-[#90a2a4]" /><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search records, outcomes, countries…" className="field pl-9" /></div><button className="icon-button border" title="Filters"><Filter className="h-4 w-4" /></button></div>
              </div>
              <div className="flex gap-1 overflow-x-auto border-b border-[#e4eaeb] px-5 py-2">{(Object.keys(laneLabels) as FilterKey[]).map(key => <button key={key} onClick={() => setLane(key)} className={`queue-tab ${lane === key ? "queue-tab-active" : ""}`}>{laneLabels[key]}</button>)}</div>
              <div className="max-h-[535px] overflow-y-auto p-3">{recordsQuery.isLoading ? <LoadingList /> : filtered.map((record: any) => <RecordListItem key={record.id} record={record} selected={selected?.id === record.id} onClick={() => setSelectedId(record.id)} />)}{!recordsQuery.isLoading && !filtered.length && <div className="p-10 text-center text-sm text-[#718286]">No records match this filter.</div>}</div>
            </section>

            <section className="space-y-5">
              {selected ? <RecordDetail record={selected} reviewDecision={reviewDecision} setReviewDecision={setReviewDecision} reviewReason={reviewReason} setReviewReason={setReviewReason} reviewerInitials={reviewerInitials} setReviewerInitials={setReviewerInitials} submitDecision={submitDecision} isSaving={decisionMutation.isPending} /> : <div className="panel p-10 text-center">Loading review cards…</div>}
            </section>
          </div>
        </section>}

        {view === "equity" && <EquityView records={records} subregions={subregions} />}
        {view === "configuration" && <ConfigurationView config={configQuery.data} />}
      </main>
    </div>
  );
}

function SlidersIcon() { return <BarChart3 className="h-4 w-4" />; }

function StatCard({ label, value, tone }: { label: string; value: number; tone: string }) {
  const toneMap: Record<string, string> = { high: "text-[#c43b2f]", moderate: "text-[#a36c05]", low: "text-[#217561]", unresolved: "text-[#735a9c]", context: "text-[#8e6038]", neutral: "text-[#173239]" };
  return <div className="panel p-4"><div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[#819295]">{label}</div><div className={`mt-2 text-2xl font-semibold ${toneMap[tone]}`}>{value}</div></div>;
}

function RecordListItem({ record, selected, onClick }: { record: any; selected: boolean; onClick: () => void }) {
  return <button onClick={onClick} className={`record-item ${selected ? "record-item-active" : ""}`}><div className="flex items-start gap-3"><div className={`mt-0.5 rounded-lg p-2 ${statusStyles[record.finalSignal] ?? statusStyles.NOT_RELEVANT}`}><LaneIcon lane={record.lane} /></div><div className="min-w-0 flex-1 text-left"><div className="flex items-center justify-between gap-2"><span className="text-[11px] font-bold tracking-wider text-[#6d8988]">{record.id}</span><span className={`rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${statusStyles[record.finalSignal] ?? statusStyles.NOT_RELEVANT}`}>{signalLabel(record)}</span></div><div className="mt-1 line-clamp-2 text-sm font-semibold leading-5 text-[#203c43]">{record.title}</div><div className="mt-2 flex items-center gap-2 text-[11px] text-[#7a8b8e]"><span>{record.country}</span><span>·</span><span>{record.recordType}</span></div></div><ChevronRight className="mt-3 h-4 w-4 shrink-0 text-[#a3b2b4]" /></div></button>;
}

function RecordDetail({ record, reviewDecision, setReviewDecision, reviewReason, setReviewReason, reviewerInitials, setReviewerInitials, submitDecision, isSaving }: any) {
  const components = [{ key: "A", label: "Relevance", value: record.scores.relevance, max: 3 }, { key: "B", label: "LMIC setting", value: record.scores.lmic, max: 2 }, { key: "C", label: "Equity", value: record.scores.equity, max: 2 }, { key: "D", label: "Study design", value: record.scores.design, max: 2 }, { key: "E", label: "Policy", value: record.scores.policy, max: 2 }, { key: "F", label: "Novelty", value: record.scores.novelty, max: 1 }, { key: "G", label: "Uncertainty", value: record.scores.uncertainty, max: 3 }];
  return (
    <div className="panel overflow-hidden">
      <div className="border-b border-[#e4eaeb] bg-[#fbfcfc] p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2"><span className="eyebrow">Evidence card</span><span className="rounded-full bg-[#edf3f2] px-2 py-1 text-[10px] font-bold text-[#567571]">{record.recordType}</span></div>
            <h2 className="mt-3 max-w-3xl text-xl font-semibold leading-7 tracking-tight text-[#173239]">{record.title}</h2>
            <p className="mt-2 text-sm text-[#718286]">{record.country} · {record.region} · {record.setting} · {record.year}</p>
          </div>
          <div className={`signal-pill ${statusStyles[record.finalSignal] ?? statusStyles.NOT_RELEVANT}`}><div className="text-[10px] uppercase tracking-[0.2em]">Priority signal</div><div className="mt-1 text-xl font-bold">{signalLabel(record)}</div>{record.totalScore !== null && <div className="mt-1 text-[11px] opacity-80">{record.totalScore}/15 rubric score</div>}</div>
        </div>
      </div>
      <div className="grid gap-6 p-6 md:grid-cols-[1.1fr_0.9fr]">
        <div><div className="eyebrow">Source summary</div><p className="mt-2 text-sm leading-6 text-[#42585d]">{record.summary}</p><div className="mt-5 grid gap-3 sm:grid-cols-2"><Info label="Exposure" value={record.exposure} /><Info label="Outcome in source" value={record.outcomeText} /><Info label="Study design" value={record.studyDesign} /><Info label="Population" value={record.population} /></div></div>
        <div className="rounded-2xl bg-[#f5f8f7] p-5"><div className="flex items-center justify-between"><div className="eyebrow">Decision trail</div><Sparkles className="h-4 w-4 text-[#759a8f]" /></div><div className="mt-4 space-y-4"><div><div className="text-[11px] font-semibold uppercase tracking-wider text-[#829396]">Relevance</div><div className="mt-1 text-sm font-semibold text-[#24454b]">{record.relevanceLabel} · {record.scores.relevance}/3</div></div><div><div className="text-[11px] font-semibold uppercase tracking-wider text-[#829396]">H3 mapping</div><div className="mt-1 text-sm font-semibold text-[#24454b]">{record.mappedOutcome ? `${record.mappedOutcome} · ${record.certainty} certainty` : record.possibleOutcomes?.join(" / ") ?? record.potentialNewOutcome ?? "No mapped outcome"}</div>{record.existingStudies && <div className="mt-1 text-xs text-[#718286]">{record.existingStudies} studies in current review</div>}</div><div><div className="text-[11px] font-semibold uppercase tracking-wider text-[#829396]">Equity</div><div className="mt-1 text-sm font-semibold text-[#24454b]">{record.progressPlus?.length ? record.progressPlus.join(" · ") : "No specific factor captured"}</div></div></div></div>
      </div>
      <div className="grid gap-6 border-t border-[#e4eaeb] p-6 pt-6 md:grid-cols-[1.1fr_0.9fr]">
        <div><div className="eyebrow">Why this result?</div><div className="mt-3 rounded-xl border border-[#e0e9e8] bg-white p-4"><div className="text-sm font-semibold leading-6 text-[#26464b]">{record.shortReason}</div><div className="mt-3 border-t border-[#edf1f1] pt-3 text-sm leading-6 text-[#64787b]">{record.fullReason}</div></div>{record.overrideFlags.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{record.overrideFlags.map((flag: string) => <span key={flag} className="inline-flex items-center gap-1 rounded-full bg-[#fff3d9] px-2.5 py-1 text-[11px] font-semibold text-[#9a6809]"><ShieldAlert className="h-3 w-3" />{flag}</span>)}</div>}</div>
        <div><div className="eyebrow">Rubric breakdown</div><div className="mt-3 space-y-2.5">{components.map(item => <div key={item.key} className="flex items-center gap-3"><span className="w-4 text-[10px] font-bold text-[#789093]">{item.key}</span><span className="w-24 text-xs text-[#607477]">{item.label}</span><div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#e6eeee]"><div className="h-full rounded-full bg-[#5f8d83]" style={{ width: scoreBar(item.value, item.max) }} /></div><span className="w-8 text-right text-xs font-semibold text-[#35565c]">{item.value}/{item.max}</span></div>)}</div></div>
      </div>
      <div className="border-t border-[#e4eaeb] bg-[#fbfcfc] p-6"><div className="flex items-center justify-between gap-3"><div><div className="eyebrow">Human review</div><div className="mt-1 text-sm text-[#64787b]">AI tags are suggestions. Confirm or record a reasoned override.</div></div>{record.reviewerDecision && <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e7f3eb] px-3 py-1.5 text-xs font-semibold text-[#2f7b59]"><CheckCircle2 className="h-3.5 w-3.5" />{record.reviewerDecision} by {record.reviewerInitials}</span>}</div><div className="mt-4 grid gap-3 md:grid-cols-[150px_1fr_100px_auto]"><select value={reviewDecision} onChange={e => setReviewDecision(e.target.value)} className="field"><option value="CONFIRM">Confirm</option><option value="OVERRIDE">Override</option><option value="REMAP">Remap</option><option value="DEFER">Defer</option><option value="EXCLUDE">Exclude</option></select><input value={reviewReason} onChange={e => setReviewReason(e.target.value)} placeholder="Reviewer reason (required)" className="field" /><input value={reviewerInitials} onChange={e => setReviewerInitials(e.target.value)} placeholder="Initials" className="field" /><button onClick={submitDecision} disabled={isSaving || !reviewReason.trim() || !reviewerInitials.trim()} className="primary-button">{isSaving ? "Saving…" : "Save decision"}</button></div></div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) { return <div className="rounded-xl border border-[#e6eded] bg-white p-3"><div className="text-[10px] font-bold uppercase tracking-wider text-[#849497]">{label}</div><div className="mt-1 text-xs font-medium leading-5 text-[#36545a]">{value}</div></div>; }
function LoadingList() { return <div className="space-y-3 p-2">{[1, 2, 3, 4, 5].map(i => <div key={i} className="h-24 animate-pulse rounded-xl bg-[#eef3f2]" />)}</div>; }

function EquityView({ records, subregions }: { records: any[]; subregions: any[] }) {
  const contextGaps = records.filter(record => record.contextGap);
  const factors = Array.from(new Set(records.flatMap(record => record.progressPlus ?? []))).map(factor => ({ factor, count: records.filter(record => record.progressPlus?.includes(factor)).length }));
  return <section className="mx-auto max-w-[1500px] px-5 py-6 md:px-8"><div className="mb-6 flex items-end justify-between"><div><div className="eyebrow">Equity audit</div><h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#173239]">Is African evidence being buried?</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-[#718286]">The audit surfaces where geography, language, occupation, settlement type, age, and uncertainty influence triage outcomes.</p></div><div className="hidden rounded-2xl bg-[#dcf27d] px-5 py-4 text-right md:block"><div className="text-2xl font-semibold text-[#203e40]">{contextGaps.length}</div><div className="text-[10px] font-bold uppercase tracking-widest text-[#55705f]">context gaps</div></div></div><div className="grid gap-5 lg:grid-cols-3"><div className="panel p-5 lg:col-span-2"><div className="flex items-center justify-between"><h3 className="font-semibold text-[#23434a]">Signal distribution by subregion</h3><BarChart3 className="h-4 w-4 text-[#7a9792]" /></div><div className="mt-5 space-y-4">{subregions.map(item => <div key={item.region}><div className="mb-2 flex justify-between text-xs"><span className="font-semibold text-[#416167]">{item.region}</span><span className="text-[#819295]">{item.total} records · {item.high} high · {item.unresolved} unresolved</span></div><div className="flex h-2 overflow-hidden rounded-full bg-[#e9eeee]"><div className="bg-[#c43b2f]" style={{ width: `${item.total ? (item.high / item.total) * 100 : 0}%` }} /><div className="bg-[#d5a438]" style={{ width: `${item.total ? ((item.total - item.high - item.unresolved) / item.total) * 100 : 0}%` }} /><div className="bg-[#a99ac8]" style={{ width: `${item.total ? (item.unresolved / item.total) * 100 : 0}%` }} /></div></div>)}</div></div><div className="panel p-5"><h3 className="font-semibold text-[#23434a]">PROGRESS-Plus factors</h3><div className="mt-5 space-y-3">{factors.map(item => <div key={item.factor} className="flex items-center justify-between border-b border-[#edf1f1] pb-3"><span className="text-sm text-[#557074]">{item.factor}</span><span className="rounded-full bg-[#eef5f3] px-2 py-1 text-xs font-semibold text-[#4f7e76]">{item.count}</span></div>)}</div></div></div><div className="mt-5 grid gap-5 lg:grid-cols-2"><div className="panel p-5"><div className="eyebrow">Context gaps surfaced</div><div className="mt-4 space-y-3">{contextGaps.map(record => <div key={record.id} className="flex items-center justify-between rounded-xl bg-[#f7faf9] p-3"><div><div className="text-xs font-bold text-[#5a7b76]">{record.id} · {record.mappedOutcome}</div><div className="mt-1 text-sm font-medium text-[#35565c]">{record.contextGap}</div></div><span className="rounded-full bg-[#fff1cf] px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[#9a6809]">+1 level</span></div>)}</div></div><div className="panel p-5"><div className="eyebrow">Equity flags to discuss</div><div className="mt-4 space-y-3 text-sm leading-6 text-[#617679]"><p><strong className="text-[#284c52]">Language:</strong> SYN-023 is French-language West African evidence and should be checked for extraction or indexing bias.</p><p><strong className="text-[#284c52]">Informal work:</strong> SYN-002, SYN-009, and SYN-024 capture occupational groups frequently missing from formal datasets.</p><p><strong className="text-[#284c52]">Setting:</strong> SYN-001 and the Cape Town trial foreground informal settlements; SYN-033 tests the urban-only boundary.</p></div></div></div></section>;
}

function ConfigurationView({ config }: { config: any }) {
  return <section className="mx-auto max-w-[1200px] px-5 py-6 md:px-8"><div className="eyebrow">Rubric & rules</div><h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#173239]">A transparent scoring engine</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-[#718286]">The uncertainty score comes from the versioned Summary of Findings. It is looked up, not inferred by AI.</p><div className="mt-6 grid gap-5 md:grid-cols-2"><div className="panel p-6"><div className="flex items-center gap-2"><FileSearch className="h-4 w-4 text-[#6e958a]" /><h3 className="font-semibold text-[#23434a]">A–G scoring rubric</h3></div><div className="mt-5 space-y-3">{config?.criteria?.map((criterion: any) => <div key={criterion.key} className="flex items-center justify-between border-b border-[#edf1f1] pb-3"><div><span className="mr-2 rounded bg-[#eaf3f1] px-1.5 py-1 text-[10px] font-bold text-[#527b73]">{criterion.key}</span><span className="text-sm text-[#4d676c]">{criterion.label}</span></div><span className="text-xs font-semibold text-[#829396]">max {criterion.max}</span></div>)}</div><div className="mt-5 rounded-xl bg-[#10272c] p-4 text-sm leading-6 text-[#d5e6e4]">Total score = A + B + C + D + E + F + G = <strong className="text-[#dcf27d]">15 points</strong>.</div></div><div className="panel p-6"><div className="flex items-center gap-2"><ShieldAlert className="h-4 w-4 text-[#b57816]" /><h3 className="font-semibold text-[#23434a]">Overrides & routing</h3></div><div className="mt-5 space-y-4 text-sm leading-6 text-[#617679]"><Rule title="Harm reported" text="High regardless of total score." /><Rule title="New intervention class" text="High regardless of total score." /><Rule title="Absent context" text="Raise one level, capped at High." /><Rule title="Protocol / retraction / duplicate / commentary / abstract" text="Unresolved lane; no standard signal." /><Rule title="Low records" text="Remain visible and are never hidden." /></div></div></div><div className="panel mt-5 p-6"><div className="eyebrow">Versioned configuration</div><div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><Info label="Rubric version" value={config?.rubricVersion ?? "v0.2"} /><Info label="SoF version" value={config?.summaryOfFindingsVersion ?? "H3-SoF-v1"} /><Info label="Decision model" value={config?.decisionModel ?? "H3 certainty-first baseline"} /><Info label="Rubric thresholds" value="High 11–15 · Moderate 6–10 · Low 0–5" /></div><div className="mt-5 rounded-xl border border-[#e7eded] bg-[#fbfcfc] p-4 text-sm leading-6 text-[#617679]"><strong className="text-[#294a50]">Scope:</strong> {config?.scope}</div></div></section>;
}
function Rule({ title, text }: { title: string; text: string }) { return <div className="flex gap-3"><Check className="mt-1 h-4 w-4 shrink-0 text-[#5e9583]" /><div><div className="font-semibold text-[#38575d]">{title}</div><div className="text-[#718286]">{text}</div></div></div>; }
