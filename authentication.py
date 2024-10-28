from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def authenticate():
    # Load credentials from the 'credentials.json' file
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Save the credentials to 'token.json'
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    
    print("Authentication successful! 'token.json' has been created.")

if __name__ == '__main__':
    authenticate()
