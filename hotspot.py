from flask import Flask, render_template, jsonify
import pandas as pd

app = Flask(__name__)

# Load and process the crime data
def load_crime_data():
    df = pd.read_csv("C:/Users/abhis/Downloads/SCREAM_DETECTION (2)/SCREAM_DETECTION/local_crime_data_20241026_020944.csv")
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

@app.route('/')
def hotspot():
    return render_template('hotspot.html')

@app.route('/get_crime_data')
def get_crime_data():
    crime_data = load_crime_data()
    return jsonify(crime_data)

if __name__ == '__main__':
    app.run(debug=True,port=5000)