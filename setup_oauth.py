"""
One-time script to generate a Google OAuth token for the bot.

Run locally:
    python setup_oauth.py

It will open a browser for consent, then print a JSON string.
Copy that string into the GOOGLE_TOKEN_JSON environment variable (Railway secret).
"""
import json
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def main():
    # Expects credentials.json downloaded from Google Cloud Console
    flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
    creds = flow.run_local_server(port=0)

    token_data = json.loads(creds.to_json())
    print("\n=== Copy the value below into GOOGLE_TOKEN_JSON ===\n")
    print(json.dumps(token_data))
    print("\n===================================================\n")


if __name__ == "__main__":
    main()
