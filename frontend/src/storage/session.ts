const TOKEN_KEY = "documind.sessionToken";

export const AUTH_HEADER = "Authorization";

/** Synchronous read of the cached signed session token (may be null). */
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

let pending: Promise<string> | null = null;

/**
 * Ensure this browser has a signed session token, minting one from the backend
 * on first use. The token embeds an unguessable tenant id and is signed by the
 * server, so it both isolates and cannot be forged to impersonate another user.
 * Persisted in localStorage so a returning visitor keeps their own documents.
 */
export async function ensureSessionToken(apiBase: string): Promise<string> {
  const existing = getStoredToken();
  if (existing) return existing;

  if (!pending) {
    const base = apiBase.replace(/\/$/, "");
    pending = fetch(`${base}/session`, { method: "POST" })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Session init failed (${res.status})`);
        const data = (await res.json()) as { token: string };
        localStorage.setItem(TOKEN_KEY, data.token);
        return data.token;
      })
      .finally(() => {
        pending = null;
      });
  }
  return pending;
}

/** Build request headers carrying the session token, minting it if needed. */
export async function authHeaders(
  apiBase: string,
  extra?: HeadersInit,
): Promise<HeadersInit> {
  const token = await ensureSessionToken(apiBase);
  return { ...(extra ?? {}), [AUTH_HEADER]: `Bearer ${token}` };
}
