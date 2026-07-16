"""Freesound OAuth2 app credentials.

Copy this file to oauth_credentials.py (which is gitignored) and fill in
the values from your registered Freesound app:

  1. Log in at https://freesound.org and go to
     https://freesound.org/apiv2/apps/
  2. Create a new API credential / app.
  3. Set its Redirect URI to exactly:
       http://127.0.0.1:8918/callback
     (this must match REDIRECT_URI in freesound_connect.py)
  4. Copy the Client ID and Client Secret it gives you below.

CLIENT_SECRET ends up embedded in any executable you build and
distribute — that's expected for a desktop OAuth2 client (Freesound's
own docs assume this for non-server apps). Just don't commit
oauth_credentials.py to a public repo; keep the real values in your CI
secrets instead (see .github/workflows/build.yml).
"""

CLIENT_ID = ""
CLIENT_SECRET = ""
