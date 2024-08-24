from flask import Flask, render_template, request, redirect, url_for, flash
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE = 'checklist.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    return conn

# Create tables if they don't exist
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS fields (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        field_type TEXT NOT NULL,  -- e.g., text, checkbox, number
                        category TEXT NOT NULL    -- e.g., Personal Hygiene, Cleaning & Sanitization
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS checklist (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        time TEXT,
                        inspector_name TEXT
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS checklist_fields (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        checklist_id INTEGER,
                        field_id INTEGER,
                        value TEXT,
                        FOREIGN KEY (checklist_id) REFERENCES checklist(id),
                        FOREIGN KEY (field_id) REFERENCES fields(id)
                    )''')
    conn.commit()
    conn.close()

def get_record_by_id(record_id):
    conn = get_db()
    record = conn.execute('SELECT * FROM checklist WHERE id = ?', (record_id,)).fetchone()
    conn.close()
    return record

def get_fields():
    conn = get_db()
    fields = conn.execute('SELECT * FROM fields').fetchall()
    conn.close()
    return fields

def get_field_by_id(field_id):
    conn = get_db()
    field = conn.execute('SELECT * FROM fields WHERE id = ?', (field_id,)).fetchone()
    conn.close()
    return field


def update_record_in_db(record_id, form_data):
    conn = get_db()
    cursor = conn.cursor()

    # Update record details
    cursor.execute('UPDATE checklist SET date = ?, time = ?, inspector_name = ? WHERE id = ?',
                   (form_data['date'], form_data['time'], form_data['inspector_name'], record_id))

    # Update or insert field values
    for key, value in form_data.items():
        if key.endswith('_comment'):
            field_id = key.replace('_comment', '')
            cursor.execute('REPLACE INTO checklist_fields (checklist_id, field_id, value) VALUES (?, ?, ?)',
                           (record_id, field_id, value))
        elif key in form_data and key not in ['date', 'time', 'inspector_name']:
            cursor.execute('REPLACE INTO checklist_fields (checklist_id, field_id, value) VALUES (?, ?, ?)',
                           (record_id, key, 'on' if value else ''))
    
    conn.commit()
    conn.close()

def delete_record_from_db(record_id):
    conn = get_db()
    cursor = conn.cursor()

    # Delete from checklist_fields
    cursor.execute('DELETE FROM checklist_fields WHERE checklist_id = ?', (record_id,))

    # Delete from records
    cursor.execute('DELETE FROM checklist WHERE id = ?', (record_id,))

    conn.commit()
    conn.close()


@app.route('/', methods=['GET', 'POST'])
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, date, inspector_name FROM checklist ORDER BY date DESC LIMIT 10')
    records = cursor.fetchall()
    
    if request.method == 'POST':
        selected_date = request.form['date']
        name = request.form['name']
        return redirect(url_for('checklist', date=selected_date, name=name))
    
    return render_template('index.html', records=records)

@app.route('/checklist', methods=['GET', 'POST'])
def checklist():
    date = request.args.get('date', datetime.now().date())
    time = datetime.now().strftime('%H:%M')

    conn = get_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        inspector_name = request.form['inspector_name']
        cursor.execute('INSERT INTO checklist (date, time, inspector_name) VALUES (?, ?, ?)',
                       (date, time, inspector_name))
        checklist_id = cursor.lastrowid
        print(request.form)
        for field_name in request.form:
            print(field_name)
            if field_name not in ['date', 'time', 'inspector_name']:
                value = request.form[field_name]
                cursor.execute('INSERT INTO checklist_fields (checklist_id, field_id, value) VALUES (?, ?, ?)',
                               (checklist_id, field_name, value))

        conn.commit()
        flash('Checklist submitted successfully!', 'success')
        return redirect(url_for('records'))

    cursor.execute('SELECT * FROM fields')
    fields = cursor.fetchall()

    # Group fields by category
    categories = {}
    for field in fields:
        category = field[3]
        if category not in categories:
            categories[category] = []
        categories[category].append(field)

    return render_template('checklist.html', date=date, time=time, fields=fields, categories=categories)

@app.route('/records')
def records():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, date, inspector_name FROM checklist ORDER BY date DESC')
    records = cursor.fetchall()

    cursor.execute('SELECT * FROM fields')
    fields = cursor.fetchall()

    conn.close()
    return render_template('records.html', records=records, fields=fields)


@app.route('/manage_records', methods=['GET', 'POST'])
def manage_record():
    # Fetch the record and fields based on the record_id
    record_id = request.args.get('record_id')
    record = get_record_by_id(record_id)  # Implement this function
    fields = get_fields()  # Implement this function
    
    if request.method == 'POST':
        # Handle form submissions for editing or deleting the record
        if 'update' in request.form:
            update_record_in_db(record_id, request.form)  # Implement this function
            return redirect(url_for('manage_record', record_id=record_id))
        elif 'delete' in request.form:
            # validate the name provided inspector_name_confirm
            inspector_name = request.form['inspector_name_confirm']
            if inspector_name != record[3]:
                flash('The inspector name provided does not match the original inspector name.', 'error')
                return redirect(url_for('manage_record', record_id=record_id))
            delete_record_from_db(record_id)  # Implement this function
            return redirect(url_for('records'))  # Adjust as needed

    return render_template('manage_records.html', record=record, fields=fields)


@app.route('/add_fields', methods=['GET', 'POST'])
def add_fields():
    if request.method == 'POST':
        name = request.form['name']
        field_type = request.form['type']
        category = request.form['category']
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO fields (name, field_type, category) VALUES (?, ?, ?)', (name, field_type, category))
        conn.commit()
        conn.close()
        flash('Field added successfully!', 'success')
        return redirect(url_for('add_fields'))
    # get the existing fields
    fields = get_fields()
    return render_template('add_fields.html', fields=fields)


@app.route('/edit_field/<int:field_id>', methods=['GET', 'POST'])
def edit_field(field_id):
    field = get_field_by_id(field_id)
    if request.method == 'POST':
        name = request.form['name']
        field_type = request.form['type']
        category = request.form['category']

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE fields SET name = ?, field_type = ?, category = ? WHERE id = ?', (name, field_type, category, field_id))
        conn.commit()
        conn.close()
        flash('Field updated successfully!', 'success')
        return redirect(url_for('add_fields'))
    return render_template('edit_field.html', field=field)

@app.route('/delete_field/<int:field_id>', methods=['GET','POST'])
def delete_field(field_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM checklist_fields WHERE field_id = ?', (field_id,))
    cursor.execute('DELETE FROM fields WHERE id = ?', (field_id,))
    conn.commit()
    conn.close()
    flash('Field deleted successfully!', 'success')
    return redirect(url_for('add_fields'))


@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.template_global()
def get_field_value(checklist_id, field_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        checklist_id = str(checklist_id)  # Ensure checklist_id is a string
        field_id = str(field_id)  # Ensure field_id is a string
        cursor.execute('SELECT value FROM checklist_fields WHERE checklist_id = ? AND field_id = ?', (checklist_id, field_id))
        result = cursor.fetchone()
        if result:
            value = result[0]
            # Check if the field_id indicates it's a checkbox
            if field_id.endswith('_comment'):
                return value
            else:
                return 'Verified' if value == 'on' else 'Unverified'
        return None
    except Exception as e:
        print(f"Error retrieving field value: {e}")
        return None



if __name__ == '__main__':
    init_db()
    app.run(debug=True)
