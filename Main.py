import os
import wave
import pyaudio
import speech_recognition as sr
from twilio.rest import Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from geocoder import IP


# Twilio account credentials
account_sid = "AC2b4a1447d8478eb8a489b6f0a3274fa9"
auth_token = "bdd89ab70ac88734217bc6318903b53f"
client = Client(account_sid, auth_token)

# Authenticate Google Drive API
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def authenticate():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        raise Exception("Authentication required! Run the auth script first.")
    return build('drive', 'v3', credentials=creds)

# Record audio from microphone
def record_audio(file_path="output.wav", record_seconds=10):
    format = pyaudio.paInt16
    channels = 1
    rate = 44100
    chunk = 1024

    audio = pyaudio.PyAudio()

    stream = audio.open(format=format,
                        channels=channels,
                        rate=rate,
                        input=True,
                        frames_per_buffer=chunk)

    print("Recording started...")

    frames = []
    for _ in range(0, int(rate / chunk * record_seconds)):
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(audio.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

    print("Recording finished.")

    return file_path

# Upload file to Google Drive and return the shareable link
def upload_to_drive(file_path):
    service = authenticate()
    
    file_metadata = {'name': os.path.basename(file_path)}
    media = MediaFileUpload(file_path, mimetype='audio/wav')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    
    # Set file permissions to allow anyone to access
    permission = {
        'type': 'anyone',
        'role': 'reader',
    }
    service.permissions().create(fileId=file.get('id'), body=permission).execute()

    # Generate shareable link
    shareable_link = f"https://drive.google.com/uc?export=download&id={file.get('id')}"
    return shareable_link

# Main function to integrate recording, uploading, and sending SMS
def main():
    # Initialize the recognizer
    recognizer = sr.Recognizer()

    # Use the default microphone as the audio source
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

        try:
            text = recognizer.recognize_google(audio)
            print("You said: " + text)

            if "help" in text.lower():
                print("Trigger word 'help' detected!")

                # Record the audio
                audio_file_path = record_audio()

                # Upload the audio file to Google Drive
                shareable_link = upload_to_drive(audio_file_path)
                print(f"File uploaded to Google Drive. Shareable link: {shareable_link}")

                # Get device location using IP geolocation
                g = ip('me')
                location = f"{g.latlng[0]},{g.latlng[1]}"
                print(f"Device location: {location}")

                # Create a Google Maps link to the coordinates
                map_link = f"https://www.google.com/maps/place/{location}"

                # Send an SMS message using Twilio
                message = client.messages.create(
                    body=f"This number is in danger. Location: {location}. View on map: {map_link}. Listen to the audio: {shareable_link}",
                    from_="+12565968186",  # Your Twilio phone number
                    to="+919594940316"  # The phone number you want to send the message to
                )
                print("SMS sent!")
        except sr.UnknownValueError:
            print("Sorry, could not understand the audio.")
        except sr.RequestError as e:
            print(f"Sorry, there was an error with the request: {e}")

if __name__ == "__main__":
    main()
