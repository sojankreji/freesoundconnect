/**
 * OAuth app credentials. Sources, in priority order:
 *  1. FREESOUND_CLIENT_ID / FREESOUND_CLIENT_SECRET environment variables
 *  2. credentials.json next to the compiled main process (gitignored;
 *     written by CI from repo secrets, or copied from
 *     credentials.example.json for local development)
 */
import * as fs from "fs";
import * as path from "path";

export interface Credentials {
  clientId: string;
  clientSecret: string;
}

export function loadCredentials(): Credentials {
  const envId = process.env["FREESOUND_CLIENT_ID"];
  const envSecret = process.env["FREESOUND_CLIENT_SECRET"];
  if (envId && envSecret) return { clientId: envId, clientSecret: envSecret };

  try {
    const jsonPath = path.join(__dirname, "credentials.json");
    const data = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
    if (data.clientId && data.clientSecret) return data;
  } catch {
    /* not present */
  }

  return { clientId: "", clientSecret: "" };
}
