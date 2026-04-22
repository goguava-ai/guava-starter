"""
Run this once to authorize your personal Google account and save a token.pkl.
After this, set AUTH_MODE=oauth when running the main example.

Usage:
    python examples/integrations/google_calendar/authorize.py
"""

import pickle

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]

flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
creds = flow.run_local_server(port=0)

with open("token.pkl", "wb") as f:
    pickle.dump(creds, f)

print("Done — token.pkl saved. You can now run with AUTH_MODE=oauth.")
