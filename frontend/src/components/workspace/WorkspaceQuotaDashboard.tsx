import type { ReactNode } from "react";
import type { WorkspaceQuotaUsage, WorkspaceQuotaUsageModel } from "@/lib/api";

interface WorkspaceQuotaDashboardProps {
  usage: WorkspaceQuotaUsage;
}

function percent(used: number, limit: number): number {
  if (limit <= 0) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function ProgressBar({
  used,
  limit,
}: {
  used: number;
  limit: number;
}) {
  const pct = percent(used, limit);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs text-zinc-500">
        <span>
          {used.toLocaleString()} / {limit.toLocaleString()}
        </span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 rounded-full bg-zinc-200">
        <div
          className="h-2 rounded-full bg-blue-600 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function findPeakModel(
  models: WorkspaceQuotaUsageModel[],
  metric: "cell_count" | "dimension_count"
): WorkspaceQuotaUsageModel | null {
  if (models.length === 0) return null;
  return models.reduce((best, current) =>
    current[metric] > best[metric] ? current : best
  );
}

export default function WorkspaceQuotaDashboard({
  usage,
}: WorkspaceQuotaDashboardProps) {
  const peakCellsModel = findPeakModel(usage.models, "cell_count");
  const peakDimensionsModel = findPeakModel(usage.models, "dimension_count");

  const peakCells = peakCellsModel ? peakCellsModel.cell_count : 0;
  const peakDimensions = peakDimensionsModel
    ? peakDimensionsModel.dimension_count
    : 0;

  return (
    <section className="mb-8 rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-zinc-900">Workspace Quotas</h2>
          <p className="text-xs text-zinc-500">
            Live usage across models, dimensions, cells, and storage
          </p>
        </div>
        <div className="w-fit rounded-md bg-zinc-100 px-3 py-1.5 text-xs text-zinc-700">
          {usage.models.length} model{usage.models.length === 1 ? "" : "s"}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <QuotaCard title="Models">
          <ProgressBar used={usage.model_count} limit={usage.max_models} />
        </QuotaCard>

        <QuotaCard title="Storage">
          <ProgressBar
            used={Math.round(usage.storage_used_mb * 1000)}
            limit={usage.storage_limit_mb * 1000}
          />
          <p className="mt-1 text-xs text-zinc-500">
            {usage.storage_used_mb.toFixed(3)} MB used
          </p>
        </QuotaCard>

        <QuotaCard title="Max Cells / Model">
          <ProgressBar used={peakCells} limit={usage.max_cells_per_model} />
          {peakCellsModel && (
            <p className="mt-1 truncate text-xs text-zinc-500">
              Highest: {peakCellsModel.model_name}
            </p>
          )}
        </QuotaCard>

        <QuotaCard title="Max Dimensions / Model">
          <ProgressBar
            used={peakDimensions}
            limit={usage.max_dimensions_per_model}
          />
          {peakDimensionsModel && (
            <p className="mt-1 truncate text-xs text-zinc-500">
              Highest: {peakDimensionsModel.model_name}
            </p>
          )}
        </QuotaCard>
      </div>
    </section>
  );
}

function QuotaCard({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-zinc-200 bg-zinc-50 p-3">
      <h3 className="mb-2 text-sm font-medium text-zinc-700">{title}</h3>
      {children}
    </div>
  );
}
