from google.oauth2 import service_account

SERVICE_ACCOUNT_FILE = 'google_api/client_secret.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
credentials = service_account.Credentials \
    .from_service_account_file(SERVICE_ACCOUNT_FILE, scopes = SCOPES) \
    .with_subject('movies@discord-bots-272616.iam.gserviceaccount.com')
