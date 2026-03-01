"use client";

interface ColumnMapperProps {
  /** Column names from the uploaded file */
  columnNames: string[];
  /** Mapping from column name to target field name (or null if unmapped) */
  mapping: Record<string, string | null>;
  /** Available target fields to map to */
  targetFields: string[];
  /** Label shown above the target fields select (e.g. "Line Item" or "Dimension Field") */
  targetLabel?: string;
  /** Called whenever the user changes any mapping */
  onChange: (mapping: Record<string, string | null>) => void;
}

/**
 * ColumnMapper — lets the user map each CSV/Excel column to a target field.
 *
 * Renders a table row per column. The user can pick a target from a <select>
 * or leave it as "(skip)" to ignore that column.
 */
export default function ColumnMapper({
  columnNames,
  mapping,
  targetFields,
  targetLabel = "Target field",
  onChange,
}: ColumnMapperProps) {
  function handleChange(col: string, value: string) {
    onChange({
      ...mapping,
      [col]: value === "" ? null : value,
    });
  }

  if (columnNames.length === 0) {
    return (
      <p className="text-sm text-zinc-500 italic">No columns to map.</p>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-zinc-200">
      <table className="w-full text-sm">
        <thead className="bg-zinc-50 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="px-4 py-2 w-1/2">File column</th>
            <th className="px-4 py-2 w-1/2">{targetLabel}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100">
          {columnNames.map((col) => (
            <tr key={col} className="bg-white hover:bg-zinc-50 transition-colors">
              <td className="px-4 py-2 font-mono text-zinc-800">{col}</td>
              <td className="px-4 py-2">
                <select
                  value={mapping[col] ?? ""}
                  onChange={(e) => handleChange(col, e.target.value)}
                  className="block w-full rounded-md border border-zinc-300 bg-white px-2 py-1.5 text-sm text-zinc-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                >
                  <option value="">(skip)</option>
                  {targetFields.map((field) => (
                    <option key={field} value={field}>
                      {field}
                    </option>
                  ))}
                </select>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
