"use client";

import { useCallback, useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ProviderType = "saml" | "oidc";

interface SSOProvider {
  id: string;
  workspace_id: string;
  provider_type: ProviderType;
  display_name: string;
  issuer_url: string;
  client_id: string;
  metadata_url: string | null;
  certificate: string | null;
  auto_provision: boolean;
  default_role: string;
  domain_allowlist: string[] | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface SSOConfigPanelProps {
  workspaceId: string;
  token: string;
  apiBase?: string;
}

type FormState = {
  provider_type: ProviderType;
  display_name: string;
  issuer_url: string;
  client_id: string;
  client_secret: string;
  metadata_url: string;
  certificate: string;
  auto_provision: boolean;
  default_role: string;
  domain_allowlist: string; // comma-separated
};

const DEFAULT_FORM: FormState = {
  provider_type: "oidc",
  display_name: "",
  issuer_url: "",
  client_id: "",
  client_secret: "",
  metadata_url: "",
  certificate: "",
  auto_provision: true,
  default_role: "viewer",
  domain_allowlist: "",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function providerToForm(p: SSOProvider): FormState {
  return {
    provider_type: p.provider_type,
    display_name: p.display_name,
    issuer_url: p.issuer_url,
    client_id: p.client_id,
    client_secret: "",
    metadata_url: p.metadata_url ?? "",
    certificate: p.certificate ?? "",
    auto_provision: p.auto_provision,
    default_role: p.default_role,
    domain_allowlist: p.domain_allowlist ? p.domain_allowlist.join(", ") : "",
  };
}

function parseDomainAllowlist(raw: string): string[] | null {
  const parts = raw
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  return parts.length > 0 ? parts : null;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function SSOConfigPanel({
  workspaceId,
  token,
  apiBase = "http://localhost:8000",
}: SSOConfigPanelProps) {
  const [provider, setProvider] = useState<SSOProvider | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const fetchProvider = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${apiBase}/workspaces/${workspaceId}/sso`, {
        headers,
      });
      if (resp.status === 404) {
        setProvider(null);
        setForm(DEFAULT_FORM);
      } else if (!resp.ok) {
        throw new Error(`Failed to load SSO config: ${resp.statusText}`);
      } else {
        const data: SSOProvider = await resp.json();
        setProvider(data);
        setForm(providerToForm(data));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [workspaceId, token, apiBase]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchProvider();
  }, [fetchProvider]);

  function handleChange(
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >
  ) {
    const { name, value, type } = e.target;
    const checked =
      type === "checkbox" ? (e.target as HTMLInputElement).checked : undefined;
    setForm((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setSuccess(null);

    const payload = {
      workspace_id: workspaceId,
      provider_type: form.provider_type,
      display_name: form.display_name,
      issuer_url: form.issuer_url,
      client_id: form.client_id,
      ...(form.client_secret ? { client_secret: form.client_secret } : {}),
      ...(form.metadata_url ? { metadata_url: form.metadata_url } : {}),
      ...(form.certificate ? { certificate: form.certificate } : {}),
      auto_provision: form.auto_provision,
      default_role: form.default_role,
      domain_allowlist: parseDomainAllowlist(form.domain_allowlist),
    };

    try {
      let resp: Response;
      if (provider) {
        // Update existing
        resp = await fetch(`${apiBase}/workspaces/${workspaceId}/sso`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(payload),
        });
      } else {
        // Create new
        resp = await fetch(`${apiBase}/workspaces/${workspaceId}/sso`, {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        });
      }
      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail ?? `Save failed: ${resp.statusText}`);
      }
      const data: SSOProvider = await resp.json();
      setProvider(data);
      setForm(providerToForm(data));
      setSuccess(provider ? "SSO configuration updated." : "SSO provider created.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!provider) return;
    if (!confirm("Delete SSO provider? This will disable SSO login for this workspace.")) return;
    setDeleting(true);
    setError(null);
    setSuccess(null);
    try {
      const resp = await fetch(`${apiBase}/workspaces/${workspaceId}/sso`, {
        method: "DELETE",
        headers,
      });
      if (!resp.ok && resp.status !== 204) {
        throw new Error(`Delete failed: ${resp.statusText}`);
      }
      setProvider(null);
      setForm(DEFAULT_FORM);
      setSuccess("SSO provider deleted.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setDeleting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-zinc-400 text-sm">
        Loading SSO configuration...
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-zinc-900">SSO Configuration</h2>
          <p className="text-sm text-zinc-500 mt-0.5">
            {provider
              ? "Update your identity provider settings."
              : "Connect an identity provider to enable SSO login."}
          </p>
        </div>
        {provider && (
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              provider.is_active
                ? "bg-green-100 text-green-700"
                : "bg-zinc-100 text-zinc-500"
            }`}
          >
            {provider.is_active ? "Active" : "Inactive"}
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      {success && (
        <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {success}
        </div>
      )}

      <form onSubmit={handleSave} className="flex flex-col gap-5">
        {/* Provider Type */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">Provider Type</label>
          <select
            name="provider_type"
            value={form.provider_type}
            onChange={handleChange}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 focus:outline-none focus:ring-2 focus:ring-violet-400"
          >
            <option value="oidc">OIDC (OpenID Connect)</option>
            <option value="saml">SAML 2.0</option>
          </select>
        </div>

        {/* Display Name */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">Display Name</label>
          <input
            type="text"
            name="display_name"
            value={form.display_name}
            onChange={handleChange}
            placeholder="e.g. Okta, Azure AD"
            required
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>

        {/* Issuer URL */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">Issuer URL</label>
          <input
            type="url"
            name="issuer_url"
            value={form.issuer_url}
            onChange={handleChange}
            placeholder="https://your-idp.example.com"
            required
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>

        {/* Metadata URL */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">
            Metadata URL{" "}
            <span className="font-normal text-zinc-400">(optional)</span>
          </label>
          <input
            type="url"
            name="metadata_url"
            value={form.metadata_url}
            onChange={handleChange}
            placeholder="https://your-idp.example.com/.well-known/openid-configuration"
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>

        {/* Client ID */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">Client ID</label>
          <input
            type="text"
            name="client_id"
            value={form.client_id}
            onChange={handleChange}
            placeholder="your-client-id"
            required
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>

        {/* Client Secret */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">
            Client Secret{" "}
            <span className="font-normal text-zinc-400">
              {provider ? "(leave blank to keep existing)" : "(optional for SAML)"}
            </span>
          </label>
          <input
            type="password"
            name="client_secret"
            value={form.client_secret}
            onChange={handleChange}
            placeholder={provider ? "••••••••" : "your-client-secret"}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
        </div>

        {/* Certificate (SAML) */}
        {form.provider_type === "saml" && (
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-zinc-700">
              X.509 Certificate{" "}
              <span className="font-normal text-zinc-400">(optional)</span>
            </label>
            <textarea
              name="certificate"
              value={form.certificate}
              onChange={handleChange}
              rows={4}
              placeholder="-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----"
              className="rounded-md border border-zinc-300 px-3 py-2 text-xs font-mono text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
            />
          </div>
        )}

        {/* Auto-provision */}
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="auto_provision"
            name="auto_provision"
            checked={form.auto_provision}
            onChange={handleChange}
            className="h-4 w-4 rounded border-zinc-300 text-violet-600 focus:ring-violet-400"
          />
          <div>
            <label
              htmlFor="auto_provision"
              className="text-sm font-medium text-zinc-700 cursor-pointer"
            >
              Auto-provision users
            </label>
            <p className="text-xs text-zinc-500">
              Automatically create accounts for new SSO users on first login.
            </p>
          </div>
        </div>

        {/* Default Role */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">Default Role</label>
          <select
            name="default_role"
            value={form.default_role}
            onChange={handleChange}
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 focus:outline-none focus:ring-2 focus:ring-violet-400"
          >
            <option value="viewer">Viewer</option>
            <option value="modeler">Modeler</option>
            <option value="admin">Admin</option>
          </select>
          <p className="text-xs text-zinc-500">
            Role assigned to newly provisioned SSO users.
          </p>
        </div>

        {/* Domain Allowlist */}
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium text-zinc-700">
            Domain Allowlist{" "}
            <span className="font-normal text-zinc-400">(optional)</span>
          </label>
          <input
            type="text"
            name="domain_allowlist"
            value={form.domain_allowlist}
            onChange={handleChange}
            placeholder="example.com, corp.example.com"
            className="rounded-md border border-zinc-300 px-3 py-2 text-sm text-zinc-800 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-violet-400"
          />
          <p className="text-xs text-zinc-500">
            Comma-separated list of allowed email domains. Leave blank to allow all.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 pt-2">
          <button
            type="submit"
            disabled={saving}
            className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Saving..." : provider ? "Update Configuration" : "Save Configuration"}
          </button>

          {provider && (
            <button
              type="button"
              onClick={handleDelete}
              disabled={deleting}
              className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 transition-colors"
            >
              {deleting ? "Deleting..." : "Delete Provider"}
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
