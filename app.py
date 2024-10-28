import os
import wave
import pyaudio
import speech_recognition as sr
from twilio.rest import Client
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from geocoder import ip
import joblib
import numpy as np
import librosa
from librosa.feature import spectral_contrast
import logging
import time
from flask import Flask, render_template, request, jsonify, redirect, url_for
import webbrowser
import threading
from threading import Event, Thread, Lock
from langchain_ollama import ChatOllama
import re
import pandas as pd
from math import radians, sin, cos, sqrt, atan2
from Main import upload_to_drive
import geocoder
import json
import os


# Initialize Flask app
app = Flask(__name__)

# Initialize the ChatOllama model
try:
    model_chat = ChatOllama(model="llama3.2:1b", base_url="http://localhost:11434/")
except Exception as e:
    print(f"Warning: Could not initialize ChatOllama model: {e}")
    model_chat = None

# Twilio account credentials
account_sid = "YOUR_TWILIO_SID"
auth_token = "YOUR_TWILIO_TOKEN"
client = Client(account_sid, auth_token)

# Load ML model for audio detection
model_audio = joblib.load('models/final_random_forest_model.pkl')

# Modified crime data loading function
def load_crime_data():
    try:
        df = pd.read_csv('datasets\local_crime_data_20241026_020944.csv')
        crime_data = []
        
        intensity_colors = {
            'High': 'red',
            'Medium': 'yellow',
            'Low': 'green'
        }
        
        for _, row in df.iterrows():
            crime_data.append({
                'lat': row['Latitude'],
                'lng': row['Longitude'],
                'type': row['Incident_Type'],
                'date': row['Date'],
                'time': row['Time'],
                'intensity': row['Intensity'],
                'color': intensity_colors[row['Intensity']]
            })
        return crime_data
    except Exception as e:
        print(f"Warning: Could not load crime data: {e}")
        return []

# Load initial crime data
crime_data = load_crime_data()
KEYWORD_FILE = 'keyword.json'
def load_keyword():
    try:
        if os.path.exists(KEYWORD_FILE):
            with open(KEYWORD_FILE, 'r') as f:
                data = json.load(f)
                return data.get('keyword', 'help')
        return 'help'
    except:
        return 'help'

def save_keyword(keyword):
    with open(KEYWORD_FILE, 'w') as f:
        json.dump({'keyword': keyword}, f)

@app.route('/update_keyword', methods=['POST'])
def update_keyword():
    try:
        data = request.get_json()
        keyword = data.get('keyword', 'help').lower()
        save_keyword(keyword)
        return jsonify({'success': True}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# PyAudio configuration
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 22050
CHUNK = RATE * 3
SILENCE_THRESHOLD = 0.1
FEATURES_LENGTH = 77

# Directory to save audio chunks
OUTPUT_DIR = 'audio_chunks1'
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Setup logging
logging.basicConfig(level=logging.INFO)

# Create events for alert handling
alert_cancelled = Event()
alert_active = False

# Helper Functions
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)*2 + cos(lat1) * cos(lat2) * sin(dlon/2)*2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def check_nearby_crimes(user_lat, user_lon, radius_km=2):
    """
    Check if there are any crimes within the specified radius
    Returns tuple (is_safe, nearby_crimes)
    """
    if crime_data.empty:
        return True, []
        
    nearby_crimes = []
    
    for _, crime in crime_data.iterrows():
        distance = calculate_distance(
            user_lat, user_lon,
            crime['Latitude'], crime['Longitude']
        )
        
        if distance <= radius_km:
            nearby_crimes.append({
                'type': crime['Incident_Type'],
                'distance': round(distance, 2),
                'intensity': crime['Intensity']
            })
    
    return len(nearby_crimes) == 0, nearby_crimes

def initialize_audio():
    """Initialize and verify audio setup"""
    try:
        # Test PyAudio initialization
        audio = pyaudio.PyAudio()
        
        # Check if there's at least one input device
        if audio.get_host_api_info_by_index(0).get('deviceCount') <= 0:
            logging.error("No audio input devices found")
            return False
            
        # Test microphone initialization
        with sr.Microphone() as source:
            recognizer = sr.Recognizer()
            recognizer.adjust_for_ambient_noise(source, duration=1)
            
        logging.info("Audio system initialized successfully")
        return True
        
    except Exception as e:
        logging.error(f"Failed to initialize audio system: {e}")
        return False

def record_audio(file_path="output.wav", record_seconds=8):
    audio = pyaudio.PyAudio()
    stream = audio.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print(f"Recording for {record_seconds} seconds...")
    frames = []
    for _ in range(0, int(RATE / CHUNK * record_seconds)):
        data = stream.read(CHUNK)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(audio.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))

    print("Recording finished.")
    return file_path

def extract_features(file_path):
    try:
        audio_np, _ = librosa.load(file_path, sr=RATE, mono=True)
        
        if np.max(np.abs(audio_np)) < SILENCE_THRESHOLD:
            logging.info("Silence detected, skipping feature extraction.")
            return None
        
        # Extract features
        rms = librosa.feature.rms(y=audio_np)
        mfccs = librosa.feature.mfcc(y=audio_np, sr=RATE, n_mfcc=13)
        spectral_centroid = librosa.feature.spectral_centroid(y=audio_np, sr=RATE)
        spectral_bandwidth = librosa.feature.spectral_bandwidth(y=audio_np, sr=RATE)
        spectral_flatness = librosa.feature.spectral_flatness(y=audio_np)
        zero_crossing_rate = librosa.feature.zero_crossing_rate(y=audio_np)
        chroma = librosa.feature.chroma_stft(y=audio_np, sr=RATE)
        spectral_contrasts = spectral_contrast(y=audio_np, sr=RATE)
        mel_spectrogram = librosa.feature.melspectrogram(y=audio_np, sr=RATE, n_mels=40)

        # Calculate averages
        features = np.concatenate((
            [np.mean(rms), np.mean(spectral_centroid), np.mean(spectral_bandwidth),
             np.mean(spectral_flatness), np.mean(zero_crossing_rate)],
            np.mean(mfccs, axis=1),
            np.mean(chroma, axis=1),
            np.mean(spectral_contrasts, axis=1),
            np.mean(mel_spectrogram, axis=1)
        ))

        if len(features) != FEATURES_LENGTH:
            logging.error(f"Feature length mismatch: Expected {FEATURES_LENGTH}, got {len(features)}")
            return None
        
        return features
    except Exception as e:
        logging.error(f"Error extracting features: {e}")
        return None



# Sleep mode variables and functions

sleep_timer = None
keyword = None
keyword_lock = Lock()
# Sleep mode variables and functions
sleep_until = 0
sleep_lock = Lock()


def announce_sleep_mode():
    wake_time = time.strftime('%H:%M:%S', time.localtime(sleep_until))
    announcement = f"""
    ============================
    SYSTEM ENTERING SLEEP MODE
    Time: {time.strftime('%H:%M:%S')}
    Will wake at: {wake_time}
    Duration: 30 minutes
    ============================
    """
    logging.info(announcement)
    return announcement

def is_system_sleeping():
    """Check if the system is currently in sleep mode."""
    global sleep_until
    with sleep_lock:
        return time.time() < sleep_until

def toggle_sleep_mode(is_sleeping):
    """Toggle sleep mode on/off with a 30-minute timer."""
    global sleep_until
    with sleep_lock:
        if is_sleeping:
            # Set sleep mode for 30 minutes
            sleep_duration = 30 * 60  # 30 minutes in seconds
            sleep_until = time.time() + sleep_duration
            logging.info("""
            ============================
            SLEEP MODE ACTIVATED
            System will resume in 30 minutes
            ============================
            """)
        else:
            # Deactivate sleep mode immediately
            sleep_until = 0
            logging.info("""
            ============================
            SLEEP MODE DEACTIVATED
            System resuming normal operation
            ============================
            """)
@app.route('/sleep_status', methods=['GET'])
def get_sleep_status():
    with sleep_lock:
        is_sleeping = time.time() < sleep_until
        remaining_time = max(0, sleep_until - time.time()) if is_sleeping else 0
        
        status_info = {
            "sleeping": is_sleeping,
            "remaining_minutes": round(remaining_time / 60, 1),
            "wake_time": time.strftime('%H:%M:%S', time.localtime(sleep_until)) if is_sleeping else None,
            "status_message": "System is in sleep mode" if is_sleeping else "System is active"
        }
        
        return jsonify(status_info)

@app.route('/toggle_sleep', methods=['POST'])
def toggle_sleep():
    try:
        data = request.json
        is_sleeping = data.get('sleeping', False)
        toggle_sleep_mode(is_sleeping) 
        return jsonify({
            "success": True, 
            "sleeping": is_system_sleeping(),
            "message": "Sleep mode toggled successfully"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



# @app.route('/toggle_sleep', methods=['POST'])
# def toggle_sleep():
#     """Toggle sleep mode on/off with a 30-minute default timer"""
#     global sleep_until
#     data = request.json
#     is_sleeping = data.get('sleeping', False)
    
#     with sleep_lock:
#         if is_sleeping:
#             # Set sleep mode for 30 minutes
#             sleep_until = time.time() + 30 * 60
#             logging.info("Sleep mode activated for 30 minutes")
#         else:
#             # Deactivate sleep mode immediately
#             sleep_until = 0
#             logging.info("Sleep mode deactivated")
    
#     return jsonify({"success": True, "sleeping": is_sleeping})

def verify_keyword(text):
    current_keyword = load_keyword().lower()
    return current_keyword in text.lower()

def two_stage_verification(recognizer, source):
    if is_system_sleeping():
        logging.info("System is in sleep mode, skipping verification")
        return False
        
    trigger_detected = False
    
    try:
        logging.info("Stage 1: Listening for initial trigger...")
        audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
        text = recognizer.recognize_google(audio)
        logging.info(f"Stage 1: Recognized text: {text}")

        # Check for trigger word with more detailed logging
        current_keyword = load_keyword()
        trigger_word_detected = current_keyword in text.lower()
        keyword_verified = verify_keyword(text)
        
        logging.info(f"Keyword detected: {trigger_word_detected}")
        logging.info(f"Keyword verified: {keyword_verified}")
        
        # Record audio for scream detection
        audio_file_path = record_audio(record_seconds=6)  # Reduced from 8 to 3 seconds
        scream_detected = predict_audio(audio_file_path)
        logging.info(f"Scream detected: {scream_detected}")

        trigger_detected = (trigger_word_detected and keyword_verified) or scream_detected
        logging.info(f"Stage 1 trigger_detected: {trigger_detected}")
        
    except sr.WaitTimeoutError:
        logging.info("Stage 1: No speech detected within timeout")
    except sr.UnknownValueError:
        logging.info("Stage 1: Speech was unintelligible")
        audio_file_path = record_audio(record_seconds=6)
        predict_audio(audio_file_path)
        if(scream_detected):
            pass
            
    except sr.RequestError as e:
        logging.error(f"Stage 1: Could not request results from speech recognition service: {e}")
    except Exception as e:
        logging.error(f"Stage 1 error: {e}")

    if trigger_detected:
        logging.info("Stage 1 trigger detected, proceeding to Stage 2...")
        end_time = time.time() + 30  # Reduced from 60 to 30 seconds

        while time.time() < end_time:
            try:
                logging.info("Stage 2: Listening for confirmation...")
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=3)
                text = recognizer.recognize_google(audio)
                logging.info(f"Stage 2: Recognized text: {text}")

                current_keyword = load_keyword()
                trigger_word_detected = current_keyword in text.lower()
                keyword_verified = verify_keyword(text)
                
                logging.info(f"Stage 2 - Keyword detected: {trigger_word_detected}")
                logging.info(f"Stage 2 - Keyword verified: {keyword_verified}")
                
                audio_file_path = record_audio(record_seconds=3)
                scream_detected = predict_audio(audio_file_path)
                logging.info(f"Stage 2 - Scream detected: {scream_detected}")

                if (trigger_word_detected and keyword_verified) or scream_detected:
                    logging.info("Stage 2 verification successful!")
                    return True
                    
            except sr.WaitTimeoutError:
                logging.info("Stage 2: No speech detected within timeout")
            except sr.UnknownValueError:
                logging.info("Stage 2: Speech was unintelligible")
                audio_file_path = record_audio(record_seconds=6)
                predict_audio(audio_file_path)
                if(scream_detected):
                 pass
            
            except sr.RequestError as e:
                logging.error(f"Stage 2: Could not request results from speech recognition service: {e}")
            except Exception as e:
                logging.error(f"Stage 2 error: {e}")

    return False

def predict_audio(file_path):
    try:
        features = extract_features(file_path)
        if features is None:
            logging.info("No features extracted from audio - likely silence")
            return False
            
        prediction = model_audio.predict([features])
        logging.info(f"Audio prediction result: {prediction[0]}")
        
        # Add threshold for prediction confidence if using predict_proba
        # proba = model_audio.predict_proba([features])
        # logging.info(f"Prediction probability: {proba}")
        
        return prediction[0] == 1
    except Exception as e:
        logging.error(f"Error in predict_audio: {e}")
        return False
    
    
@app.route('/cancel', methods=['POST'])
def cancel_alert():
    global alert_active
    alert_active = False
    alert_cancelled.set()
    return jsonify({"redirect": url_for('home')})

@app.route("/confirm_alert", methods=["POST"])
def confirm_alert():
    try:
        # Get device location
        g = geocoder.ip('me')
        location = f"{g.latlng[0]},{g.latlng[1]}"
        print(f"Alert confirmed! Device location: {location}")

        # Create a Google Maps link
        map_link = f"https://www.google.com/maps/place/{location}"

        # Send SMS with location
        message = client.messages.create(
            body=f"EMERGENCY ALERT: User in danger! Location: {location}. Map: {map_link}",
            from_="+12097530237",
            to="+919511972070"
        )
        print("Emergency SMS sent!")

        return jsonify({
            "message": "Alert confirmed and sent to emergency services.",
            "location": location,
            "redirect": url_for('home')
        })
        
    except Exception as e:
        print(f"Error in confirm_alert: {str(e)}")
        return jsonify({
            "message": "Error processing alert. Emergency services have been notified.",
            "error": str(e),
            "redirect": url_for('home')
        }), 500

def handle_alert_process(client, location, map_link, shareable_link):
    global alert_active
    
    alert_cancelled.clear()
    webbrowser.open('http://127.0.0.1:5000/alert')
    
    cancelled = alert_cancelled.wait(timeout=10)
    
    if cancelled:
        logging.info("Alert was cancelled by user")
        alert_active = False
        webbrowser.open('http://127.0.0.1:5000/')
        return False
    else:
        if alert_active:
            logging.info("No cancellation received, sending alert")
            success = send_alert(location, map_link, shareable_link, client)
            webbrowser.open('http://127.0.0.1:5000/')
            return success
        return False
    
    
def send_alert(location, map_link, shareable_link, client):
    try:
        message = client.messages.create(
            body=f"EMERGENCY ALERT: User in danger! Location: {location}. Map: {map_link}. Audio: {shareable_link}",
            from_="YOUR_TWILIO_NUMBER",
            to="AUTHORITY_NUMBER"
        )
        logging.info("SMS alert sent successfully")
        return True
    except Exception as e:
        logging.error(f"Failed to send SMS: {e}")
        return False

# def handle_alert_process(client, location, map_link, shareable_link):
#     global alert_active
    
#     alert_cancelled.clear()
#     webbrowser.open('http://127.0.0.1:5000/alert')
    
#     cancelled = alert_cancelled.wait(timeout=10)
    
#     if cancelled:
#         logging.info("Alert was cancelled by user")
#         alert_active = False
#         return False
#     else:
#         if alert_active:
#             logging.info("No cancellation received, sending alert")
#             return send_alert(location, map_link, shareable_link, client)
        return False

# Flask Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/map')
def map_view():
    return render_template('map.html')

@app.route('/get_crime_data')
def get_crime_data():
    return jsonify(crime_data)

@app.route('/next_page')
def next_page_route():
    return render_template('chatbot.html')

@app.route('/emergency')
def emergency():
    return render_template('emergency.html')

@app.route('/news')
def news():
    return render_template('news.html')

@app.route('/chatbot')
def chatbot():
    return render_template('chatbot.html')

@app.route('/alert')
def alert():
    global alert_active
    alert_active = True
    return render_template('alert.html')

# @app.route('/cancel', methods=['POST'])
# def cancel_alert():
#     global alert_active
#     alert_active = False
#     alert_cancelled.set()
#     return '', 204

@app.route('/set_keyword', methods=['POST'])
def set_keyword():
    global keyword
    data = request.json
    with keyword_lock:
        keyword = data.get('keyword')
    return jsonify({"success": True, "message": "Keyword set successfully"})



@app.route("/generate_response", methods=["POST"])
def generate_response():
    input_text = request.json.get("input_text")
    
    # List of emergency trigger phrases
    emergency_phrases = [
        "i am in danger",
        "help me",
        "emergency",
        "save me",
        "sos",
        "urgent help",
        "being followed",
        "someone is following",
        "need police",
        "call police",
        "need help urgently",
        "stalker"
    ]
    
    # Check for exact emergency phrases
    if any(phrase in input_text.lower().strip() for phrase in emergency_phrases):
        try:
            # Get user's location immediately
            g = geocoder.ip('me')
            if g.latlng:
                location = f"{g.latlng[0]},{g.latlng[1]}"
                print(f"Emergency detected! User location: {location}")
            
            crisis_response = (
                "EMERGENCY ALERT ACTIVATED. Stay calm. "
                "Your location has been tracked and help is being dispatched. "
                "Please stay on this chat. Redirecting to emergency interface..."
            )
            
            return jsonify({
                "response": crisis_response,
                "redirect_url": url_for("alert")
            })
            
        except Exception as e:
            print(f"Error processing emergency: {str(e)}")
            return jsonify({
                "response": "Emergency services are being notified. Please stay safe.",
                "redirect_url": url_for("alert")
            })
    
    # Handle safety check command
    if input_text.lower().strip() == "safe":
      if input_text.lower().strip() == "safe":
        try:
            # Get user's location
            g = geocoder.ip('me')
            if not g.latlng:
                return jsonify({"response": "Unable to get your location. Please ensure location services are enabled."})
            
            user_lat, user_lon = g.latlng
            is_safe, nearby_crimes = check_nearby_crimes(user_lat, user_lon)
            
            if is_safe:
                response = "Your current location appears to be safe. No reported incidents within 2km radius."
            else:
                response = f"⚠ CAUTION: There are {len(nearby_crimes)} reported incidents within 2km of your location./n/n"
                # response += "Nearby incidents:/n"
                # for crime in nearby_crimes:
                #     response += f"- {crime['type']} ({crime['distance']}km away, {crime['intensity']} intensity)/n"
                response += "/nPlease stay vigilant and avoid walking alone."
            
            return jsonify({"response": response})
            
        except Exception as e:
            return jsonify({"response": f"Error checking location safety: {str(e)}"})
    
    # Crisis keywords check
    crisis_keywords = r"/b(danger|help|emergency|urgent|followed|suspicious|assist|need help)/b"
    if re.search(crisis_keywords, input_text, re.IGNORECASE):
        crisis_response = (
            "It sounds like you may be in a crisis or emergency situation. "
            "Please stay calm. We are sending an alert to the authorities to assist you."
        )
        return jsonify({"response": crisis_response, "redirect_url": url_for("alert")})
    
    # Regular chatbot response for non-emergency queries
    detailed_prompt = (
        "You are a highly intelligent and helpful assistant designed to provide support and information to users. "
        "If you detect any mention of danger, emergency, or need for assistance, respond empathetically and clearly, "
        "informing the user that an alert will be sent. For regular questions, respond as usual./n"
        f"User Question: {input_text}"
    )
    
    response = model_chat.invoke(detailed_prompt)
    return jsonify({"response": response.content})

def main_audio_monitoring():
    global alert_active
    
    if not initialize_audio():
        logging.error("Audio monitoring could not start due to initialization failure")
        return
        
    recognizer = sr.Recognizer()
    
    while True:
        try:
            with sr.Microphone() as source:
                # Add a small delay to prevent CPU overuse
                time.sleep(0.1)
                
                recognizer.adjust_for_ambient_noise(source)
                
                alert_active = False
                alert_cancelled.clear()

                verified = two_stage_verification(recognizer, source)

                if verified:
                    logging.info("Verification passed. Starting alert process...")
                    audio_file_path = record_audio(record_seconds=8)
                    
                    try:
                        shareable_link = upload_to_drive(audio_file_path)
                    except Exception as e:
                        logging.error(f"Failed to upload audio: {e}")
                        shareable_link = "Audio upload failed"

                    try:
                        g = ip('me')
                        location = f"{g.latlng[0]},{g.latlng[1]}"
                        map_link = f"https://www.google.com/maps/place/{location}"
                    except Exception as e:
                        logging.error(f"Failed to get location: {e}")
                        location = "Location unavailable"
                        map_link = "Map link unavailable"

                    alert_sent = handle_alert_process(client, location, map_link, shareable_link)
                    
                    if alert_sent:
                        logging.info("Alert sent successfully")
                    else:
                        logging.info("Alert process completed, no SMS sent")
                    
                    time.sleep(2)

        except sr.RequestError as e:
            logging.error(f"Could not request results from Speech Recognition service: {e}")
        except sr.UnknownValueError:
            continue  # Just continue if speech wasn't understood
        except Exception as e:
            logging.error(f"Error in main audio loop: {e}")
            time.sleep(1)

            
# @app.route("/confirm_alert", methods=["POST"])
# def confirm_alert():
#     try:
#         # Get device location
#         g = geocoder.ip('me')
#         location = f"{g.latlng[0]},{g.latlng[1]}"
#         print(f"Alert confirmed! Device location: {location}")

#         # Create a Google Maps link
#         map_link = f"https://www.google.com/maps/place/{location}"

#         # Send SMS with location
#         message = client.messages.create(
#             body=f"EMERGENCY ALERT: User in danger! Location: {location}. Map: {map_link}",
#             from_="+12097530237",
#             to="+919511972070"
#         )
#         print("Emergency SMS sent!")

#         return jsonify({
#             "message": "Alert confirmed and sent to emergency services.",
#             "location": location
#         })
        
#     except Exception as e:
#         print(f"Error in confirm_alert: {str(e)}")
#         return jsonify({
#             "message": "Error processing alert. Emergency services have been notified.",
#             "error": str(e)
#         }), 500
        

if __name__ == '__main__':
    # Initialize logging with more detailed format
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Verify all required dependencies are available
    required_modules = ['pyaudio', 'speech_recognition', 'wave']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        logging.error(f"Missing required modules: {', '.join(missing_modules)}")
        exit(1)
    
    try:
        audio_thread = Thread(target=main_audio_monitoring)
        audio_thread.daemon = True
        audio_thread.start()
        logging.info("Audio monitoring thread started")
        
        app.run(debug=True, use_reloader=False, threaded=True,port=5000)
    except Exception as e:
        logging.error(f"Failed to start application: {e}")
