export type FeatureStatus =
  | "submitted"
  | "under_review"
  | "planned"
  | "in_progress"
  | "shipped"
  | "declined";

const KNOWN_STATUSES: readonly FeatureStatus[] = [
  "submitted",
  "under_review",
  "planned",
  "in_progress",
  "shipped",
  "declined",
];

const STATUS_LABEL: Record<FeatureStatus, string> = {
  submitted: "Submitted",
  under_review: "Under review",
  planned: "Planned",
  in_progress: "In progress",
  shipped: "Completed",
  declined: "Declined",
};

const STATUS_STYLE: Record<FeatureStatus, string> = {
  submitted: "bg-zinc-100 text-zinc-700",
  under_review: "bg-blue-50 text-blue-700",
  planned: "bg-amber-50 text-amber-700",
  in_progress: "bg-violet-50 text-violet-700",
  shipped: "bg-green-50 text-green-700",
  declined: "bg-zinc-100 text-zinc-500",
};

export function normalizeStatus(value: string): FeatureStatus {
  return (KNOWN_STATUSES as readonly string[]).includes(value) ? (value as FeatureStatus) : "submitted";
}

export function statusLabel(status: string): string {
  return STATUS_LABEL[normalizeStatus(status)];
}

export function StatusChip({ status, className = "" }: { status: string; className?: string }) {
  const safeStatus = normalizeStatus(status);
  return (
    <span
      className={`inline-flex h-7 shrink-0 items-center whitespace-nowrap rounded-[6px] px-2.5 text-[0.75rem] font-semibold ${STATUS_STYLE[safeStatus]} ${className}`}
    >
      {STATUS_LABEL[safeStatus]}
    </span>
  );
}

export { KNOWN_STATUSES };
