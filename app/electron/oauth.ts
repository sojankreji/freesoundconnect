/** OAuth2 "Log in with Freesound": browser flow, loopback server, tokens. */
import * as http from "http";

import { loadCredentials } from "./credentials";
import { API_BASE, FreesoundError, fetchProfile } from "./freesound-api";
import { AppConfig, OAuthData, logError, saveConfig } from "./store";

const AUTHORIZE_URL = `${API_BASE}/oauth2/authorize/`;
const TOKEN_URL = `${API_BASE}/oauth2/access_token/`;
export const REDIRECT_PORT = 8918;
const REDIRECT_URI = `http://127.0.0.1:${REDIRECT_PORT}/callback`;

export function hasCredentials(): boolean {
  const creds = loadCredentials();
  return Boolean(creds.clientId && creds.clientSecret);
}

export function buildAuthorizeUrl(): string {
  const { clientId } = loadCredentials();
  const qs = new URLSearchParams({
    client_id: clientId, response_type: "code",
  });
  return `${AUTHORIZE_URL}?${qs.toString()}`;
}

async function postForm(data: Record<string, string>): Promise<any> {
  let resp: Response;
  try {
    resp = await fetch(TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(data).toString(),
      signal: AbortSignal.timeout(30000),
    });
  } catch (err: any) {
    throw new FreesoundError(`Network error: ${err?.message ?? err}`);
  }
  if (!resp.ok) {
    const detail = (await resp.text()).slice(0, 200);
    throw new FreesoundError(
      `Freesound login error (HTTP ${resp.status}): ${detail}`);
  }
  return resp.json();
}

export function exchangeCodeForTokens(code: string): Promise<any> {
  const { clientId, clientSecret } = loadCredentials();
  return postForm({
    grant_type: "authorization_code",
    client_id: clientId,
    client_secret: clientSecret,
    code,
    redirect_uri: REDIRECT_URI,
  });
}

function refreshAccessToken(refreshToken: string): Promise<any> {
  const { clientId, clientSecret } = loadCredentials();
  return postForm({
    grant_type: "refresh_token",
    client_id: clientId,
    client_secret: clientSecret,
    refresh_token: refreshToken,
  });
}

/**
 * Local loopback server that waits for Freesound's browser redirect.
 * Resolves with the authorization code; `cancel()` aborts the wait (used
 * when the user pastes the code manually or dismisses the login).
 */
export function waitForOAuthCode(timeoutMs = 300000): {
  code: Promise<string>; cancel: () => void;
} {
  let cancelFn = () => {};
  const code = new Promise<string>((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url ?? "/", `http://127.0.0.1:${REDIRECT_PORT}`);
      const authCode = url.searchParams.get("code");
      const authError = url.searchParams.get("error");
      const message = authCode
        ? "You're logged in to Freesound Connect. You can close this tab."
        : "Login failed or was cancelled. You can close this tab.";
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end(`<html><body style="font-family:sans-serif;text-align:center;` +
              `padding:60px"><h2>${message}</h2></body></html>`);
      finish(() => {
        if (authCode) resolve(authCode);
        else reject(new FreesoundError(
          `Freesound login failed: ${authError ?? "no code returned"}`));
      });
    });

    const timer = setTimeout(() => finish(() => reject(new FreesoundError(
      "Login timed out waiting for the browser. Please try again."))),
      timeoutMs);

    let done = false;
    function finish(settle: () => void): void {
      if (done) return;
      done = true;
      clearTimeout(timer);
      server.close();
      settle();
    }
    cancelFn = () => finish(() => reject(new FreesoundError("cancelled")));

    server.on("error", (err) => finish(() => reject(new FreesoundError(
      `Could not start local login listener on port ${REDIRECT_PORT}: ` +
      `${err.message}`))));
    server.listen(REDIRECT_PORT, "127.0.0.1");
  });
  return { code, cancel: () => cancelFn() };
}

/** Extract the code from a pasted redirect URL, or pass raw codes through. */
export function extractCode(text: string): string {
  if (text.includes("code=")) {
    try {
      const code = new URL(text).searchParams.get("code");
      if (code) return code;
    } catch {
      /* not a URL — treat as a raw code */
    }
  }
  return text;
}

/** Holds tokens, persists them into the shared config, refreshes on demand. */
export class AuthManager {
  private refreshing: Promise<string> | null = null;

  constructor(private config: AppConfig) {}

  get oauth(): OAuthData {
    return this.config.oauth ?? {};
  }

  isLoggedIn(): boolean {
    return Boolean(this.oauth.refresh_token);
  }

  state(): { loggedIn: boolean; username: string | null; avatarUrl: string | null } {
    return {
      loggedIn: this.isLoggedIn(),
      username: this.oauth.username ?? null,
      avatarUrl: this.oauth.avatar_url ?? null,
    };
  }

  applyTokens(tokenData: any): void {
    this.config.oauth = {
      ...this.oauth,
      access_token: tokenData.access_token,
      refresh_token: tokenData.refresh_token ?? this.oauth.refresh_token,
      expires_at: Date.now() / 1000 + Number(tokenData.expires_in ?? 3600) - 60,
    };
    saveConfig(this.config);
  }

  applyProfile(profile: { username: string | null; avatar_url: string | null }): void {
    this.config.oauth = {
      ...this.oauth,
      username: profile.username ?? undefined,
      avatar_url: profile.avatar_url ?? undefined,
    };
    saveConfig(this.config);
  }

  async ensureValidToken(): Promise<string> {
    const { access_token, refresh_token, expires_at } = this.oauth;
    if (!refresh_token) throw new FreesoundError("Not logged in.");
    if (access_token && Date.now() / 1000 < (expires_at ?? 0)) {
      return access_token;
    }
    this.refreshing ??= refreshAccessToken(refresh_token)
      .then((tokenData) => {
        this.applyTokens(tokenData);
        return this.oauth.access_token!;
      })
      .finally(() => { this.refreshing = null; });
    return this.refreshing;
  }

  async completeLogin(code: string): Promise<void> {
    const tokenData = await exchangeCodeForTokens(code);
    if (!tokenData.access_token) {
      throw new FreesoundError(
        `Unexpected response from Freesound: ${JSON.stringify(tokenData)}`);
    }
    this.applyTokens(tokenData);
    try {
      this.applyProfile(await fetchProfile(tokenData.access_token));
    } catch (err) {
      logError("fetch_profile", err);
    }
  }

  logout(): void {
    delete this.config.oauth;
    saveConfig(this.config);
  }
}
