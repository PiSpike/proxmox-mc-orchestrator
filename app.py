import spikeproxmox
import spikecloudflare
import spikevelocity
import spikemail
import datetime
import sqlite3
import re
import requests
import random
import os
import secrets
import threading
from flask import Flask, render_template, request, redirect, flash, url_for, session

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_KEY')
DB_FILE = "database.db"

# --- DATABASE LOGIC ---

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS requests 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             email TEXT, 
             servername TEXT, 
             seed TEXT,
             gamemode TEXT,
             difficulty TEXT,
             ip TEXT,
             whitelist_enabled INTEGER default 0,
             owner_name TEXT,
             uuid TEXT,
             status TEXT,
             created_at TIMESTAMP)''')
        # Ensure sequence starts high enough to avoid conflicts
        conn.execute("INSERT OR IGNORE INTO sqlite_sequence (name, seq) VALUES ('requests', 200)")
    print("Database initialized.")

def get_db_connection():
    """Helper to connect to the database and return rows as dictionaries."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # This lets us access columns by name
    return conn

# Initialize the DB when the script starts
init_db()

def print_sql_table_no_modules(db_file, table_name):
    conn = sqlite3.connect(db_file)
    c = conn.cursor()

    try:
        # Fetch data
        c.execute(f"SELECT * FROM {table_name}")
        records = c.fetchall()
        
        if not records:
            print(f"The table '{table_name}' is empty.")
            return

        # Get column names
        headers = [description[0] for description in c.description]
        
        # Combine headers and records for width calculation
        all_rows = [headers] + records

        # Calculate maximum column widths
        widths = []
        for i in range(len(headers)):
            max_width = max(len(str(row[i])) for row in all_rows)
            widths.append(max_width)

        # Create a format string for alignment
        format_string = "|".join([f" {{:<{w}}} " for w in widths])
        format_string = f"|{format_string}|"

        # Print the header row
        print("-" * len(format_string.replace('|', '+')))
        print(format_string.format(*headers))
        print("-" * len(format_string.replace('|', '+')))

        # Print the data rows
        for row in records:
            clean_row = [str(item) if item is not None else "NULL" for item in row]
            print(format_string.format(*clean_row))
        
        print("-" * len(format_string.replace('|', '+')))

    except sqlite3.Error as e:
        print(f"An SQL error occurred: {e}")
    finally:
        conn.close()

print_sql_table_no_modules(DB_FILE, 'requests')

def sanitize_name(name):
    # This removes anything that isn't a letter or a number
    return re.sub(r'[^a-zA-Z0-9]', '', name)

def get_actual_uuid(username):
    try:
        # Mojang API: converts name to UUID
        res = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{username}", timeout=5)
        if res.status_code == 200:
            return res.json()['id'] # Undashed UUID
    except Exception as e:
        print(f"UUID lookup failed: {e}")
    return "00000000000000000000000000000000" # Fallback


# --- ROUTES ---

@app.route('/')
def index():
    # Get messages from URL if they exist (for user feedback)
    error = request.args.get('error')
    msg = request.args.get('msg')
    
    # You can pass both to the template
    return render_template('index.html', error=error, msg=msg)


@app.route('/request-server', methods=['POST'])
def handle_request():
    # 1. Get and Sanitize input
    email = request.form.get('email', '').strip()
    raw_name = request.form.get('servername', '').strip()
    raw_seed = request.form.get('seed', '').strip()
    clean_seed = sanitize_name(raw_seed)
    clean_name = sanitize_name(raw_name)

    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    if not re.match(email_regex, email):
        print("Invalid email format")
        flash("Please enter a valid email address.", "danger")
        return redirect('/')

    if len(raw_name) > 20:
        print("Server name too long")
        flash("Server name must be 20 characters or less.", "danger")
        return redirect('/')

    if len(email) > 50:
        print("Email too long")
        flash("Email is too long.", "danger")
        return redirect('/')

    # 2. Check Database for uniqueness
    with get_db_connection() as conn:
        existing = conn.execute(
            'SELECT id FROM requests WHERE servername = ? COLLATE NOCASE', 
            (clean_name,)
        ).fetchone()

        if existing:
            flash(f"The name '{clean_name}' is already being used in another world!", "danger")
            return redirect('/')

        # 3. If unique, proceed to insert
        gamemode = request.form.get('gamemode')
        difficulty = request.form.get('difficulty')
        whitelist_active = 1 if request.form.get('whitelist_checkbox') == 'on' else 0
        mc_username = sanitize_name(request.form.get('mc_username', ''))
        
        new_request = f"New Request: {email}, {clean_name}, {gamemode}, {clean_seed}, {difficulty}\nhttps://spikenet.net/admin"
        print(new_request)
        spikemail.send_email(os.environ.get('EMAIL'), "New Minecraft Server Request", new_request)

        conn.execute('INSERT INTO requests (email, servername, gamemode, seed, difficulty, whitelist_enabled, owner_name, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                     (email, clean_name, gamemode, clean_seed, difficulty, whitelist_active, mc_username, 'PENDING', datetime.datetime.now()))
        conn.commit()
        
        flash(f"Request for '{clean_name}' sent to the Admin! Check your email soon.", "success")
        print_sql_table_no_modules(DB_FILE, 'requests')

    return redirect('/')


@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('login'))
    conn = get_db_connection()
    # Fetch all requests from the database file
    requests_from_db = conn.execute('SELECT * FROM requests').fetchall()
    conn.close()
    return render_template('admin.html', requests=requests_from_db)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if secrets.compare_digest(request.form['password'], os.environ.get('ADMIN_PASS')):
            session['is_admin'] = True
            return redirect(url_for('admin'))
    return '''
        <form method="post">
            Password: <input type="password" name="password">
            <input type="submit" value="Login">
        </form>
    '''

def approval_email(email, subject, body):
    spikemail.send_email(email, subject, body)
    print("Approval email sent")


@app.route('/approve/<int:req_id>', methods=['POST'])
def approve(req_id):



    # 1. Fetch the existing request data from the SQL file
    with get_db_connection() as conn:
        req = conn.execute('SELECT * FROM requests WHERE id = ?', (req_id,)).fetchone()
    
    if not req:
        return "Error: Request not found in database", 404

    # 2. Use the data from the database (falling back to defaults if empty)
    raw_seed = req['seed'] #if req['seed'] else ''
    raw_mode = req['gamemode'] if req['gamemode'] else 'survival'
    raw_diff = req['difficulty'] if req['difficulty'] else 'hard'

    # 3. Determine the next available VMID
    new_vmid = req_id
    last_octet = req_id - 200
    new_ip = f"10.0.10.{last_octet}"
    
    mc_name = f"mc-{req['servername']}"
    # All servers now use the standard port 25565
    standard_port = 25565
    
    # 4. Sanitize the data for the Proxmox Hostname
    clean_seed = re.sub(r'[^a-zA-Z0-9]', '', str(raw_seed))

    
    clean_mode = re.sub(r'[^a-z]', '', raw_mode.lower())
    clean_diff = re.sub(r'[^a-z]', '', raw_diff.lower())
    whitelist_enabled = req['whitelist_enabled']
    uuid = get_actual_uuid(req['owner_name'])
    # 5. Create the data dictionary for spikeproxmox.py
    server_data = {
        'seed': clean_seed,
        'mc_name': mc_name,
        'gamemode': clean_mode,
        'difficulty': clean_diff,
        'whitelist_enabled': whitelist_enabled,
        'owner_name': req['owner_name'],
        'uuid': uuid
    }

    # 6. Provision the Server & Update Database status
    template = 129

    thread = threading.Thread(target=spikeproxmox.provision_new_server, args=(new_vmid, template, server_data))
    thread.daemon = True  # Ensures thread dies if the main app stops
    thread.start()

    # Tell the user it's happening
    flash(f"Server creation for Request #{req_id} has started in the background.")


    spikecloudflare.create_subdomain(mc_name)
    spikevelocity.add_server_to_velocity(mc_name, new_ip)

    email = req['email']
    subject = "Your Minecraft Server Request has been Approved!"
    body = f"Your Minecraft server request has been approved and is now live! \nConnect using IP: {mc_name}.spikenet.net \nMinecraft version 1.21.11"

    
    my_timer = threading.Timer(90, approval_email, args=(email, subject, body))
    # Start the timer
    print(f"Sending email in 90 seconds")
    my_timer.start()

    with get_db_connection() as conn:
        # Update the port and status, and ensure the sanitized values are saved
        conn.execute('''
            UPDATE requests 
            SET ip = ?, 
                seed = ?, 
                gamemode = ?, 
                difficulty = ?,
                uuid = ? 
            WHERE id = ?
        ''', (new_ip, clean_seed, clean_mode, clean_diff, uuid, req_id))
        
        conn.commit()
        print_sql_table_no_modules(DB_FILE, 'requests')

    return redirect(url_for('admin'))


@app.route('/delete/<int:request_id>', methods=['POST'])
def delete_server(request_id):
    with get_db_connection() as conn:
        req = conn.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
        mc_name = f"mc-{req['servername']}"
        print(f"Deleting server with ID: {request_id}")

        # Call the script to destroy the container in Proxmox
        spikeproxmox.delete_mc_container(request_id)

        spikecloudflare.remove_subdomain(mc_name)
        spikevelocity.remove_server_from_velocity(mc_name)
        spikemail.send_email(req['email'], "Minecraft Server Deleted", f"Your Minecraft server '{mc_name}' has been deleted.")
        # Remove from database
        conn.execute('DELETE FROM requests WHERE id = ?', (request_id,))
        conn.commit()
        
        print_sql_table_no_modules(DB_FILE, 'requests')
    
    return redirect('/admin')


@app.route('/deny/<int:request_id>', methods=['POST'])
def deny_request(request_id):
    with get_db_connection() as conn:
        req = conn.execute('SELECT * FROM requests WHERE id = ?', (request_id,)).fetchone()
        print(f"Denying request with ID: {request_id}")
        spikemail.send_email(req['email'], "Minecraft Server Request Denied", "Your request for a Minecraft server has been denied.")
        # Remove from database
        conn.execute('DELETE FROM requests WHERE id = ?', (request_id,))
        conn.commit()
        
        print_sql_table_no_modules(DB_FILE, 'requests')
        
    return redirect('/admin')


if __name__ == '__main__':
    # Makes the server accessible on the local network
    app.run(host='0.0.0.0', port=5000, debug=True)
