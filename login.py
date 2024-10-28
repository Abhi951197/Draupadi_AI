from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# MySQL configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'safety_app'

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        keyword = request.form['keyword']

        # Check if account already exists
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s', [email])
        account = cursor.fetchone()

        if account:
            flash('Account already exists with this email!', 'danger')
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address!', 'danger')
        elif not username or not password or not email or not keyword:
            flash('Please fill out the form completely!', 'danger')
        else:
            # Insert new user into database
            cursor.execute('INSERT INTO users (username, email, password, keyword) VALUES (%s, %s, %s, %s)', 
                           (username, email, password, keyword))
            mysql.connection.commit()
            flash('You have successfully registered! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['username'] = account['username']
            session['email'] = account['email']
            flash('You are logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Incorrect email or password!', 'danger')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'loggedin' in session:
        return render_template('index.html')
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('loggedin', None)
    session.pop('username', None)
    session.pop('email', None)
    flash('You have successfully logged out!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
