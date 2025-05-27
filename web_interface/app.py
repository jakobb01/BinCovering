from flask import Flask, request, send_from_directory, jsonify
import subprocess
import os

app = Flask(__name__, static_url_path='', static_folder='.')

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/run', methods=['POST'])
def run_code():
    data = request.get_json()
    code = data['code']
    try:
        result = subprocess.run(['python3', '-c', code], capture_output=True, text=True, timeout=5)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)

@app.route('/script', methods=['POST'])
def run_script():
    data = request.get_json()
    script = data['script']
    section = data.get('section')
    args = data.get('args', [])
    base = 'src'
    sections = ['generate_bins', 'strategies', 'custom_code']

    # If section is not provided or script not found in section, search all sections
    script_path = None
    search_sections = [section] if section in sections else sections
    for sec in search_sections:
        candidate = os.path.join(base, sec, f'{script}.py')
        if os.path.exists(candidate):
            script_path = candidate
            section = sec
            break

    if not script_path:
        return f"No script named '{script}' found in any section."

    try:
        cmd = ['python3', script_path] + args
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout + result.stderr
    except Exception as e:
        return str(e)
    
@app.route('/scripts', methods=['GET'])
def list_scripts():
    base = 'src'
    sections = ['generate_bins', 'strategies', 'custom_code']
    result = {}
    try:
        for section in sections:
            section_dir = os.path.join(base, section)
            if not os.path.exists(section_dir):
                os.makedirs(section_dir)
            files = os.listdir(section_dir)
            result[section] = [f[:-3] for f in files if f.endswith('.py')]
        return jsonify(result)
    except Exception as e:
        return str(e), 500

@app.route('/save_script', methods=['POST'])
def save_script():
    data = request.get_json()
    name = data.get('name', '').strip()
    code = data.get('code', '')
    section = data.get('section', 'custom_code')
    if not name or not name.isidentifier():
        return "Invalid script name. Use only letters, numbers, and underscores.", 400
    section_dir = os.path.join('src', section)
    if not os.path.exists(section_dir):
        os.makedirs(section_dir)
    script_path = os.path.join(section_dir, f'{name}.py')
    try:
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(code)
        return f"Script '{name}' saved successfully in '{section}'."
    except Exception as e:
        return f"Error saving script: {e}", 500

@app.route('/scripts/<section>/<script_name>')
def get_script_code(section, script_name):
    script_path = os.path.join('src', section, script_name)
    if not os.path.exists(script_path):
        return "Script not found.", 404
    with open(script_path, 'r', encoding='utf-8') as f:
        return f.read()

# --- Data section endpoints ---

@app.route('/data', methods=['GET'])
def list_data_files():
    data_dir = 'src/data'
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
    return jsonify(files)

@app.route('/data/<filename>')
def get_data_file(filename):
    data_dir = 'data'
    file_path = os.path.join(data_dir, filename)
    if not os.path.exists(file_path):
        return "File not found.", 404
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

if __name__ == '__main__':
    app.run(debug=True)
