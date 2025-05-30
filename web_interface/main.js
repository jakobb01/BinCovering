// Default code for resetting the editor
const defaultEditorCode = `import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from generate import Generate  # Assuming you saved the class above in mymodule.py

class JakobB(Generate):
    def start(self):
        return "My custom start"

    def next(self):
        return 42

    def stop(self):
        return "Done"

gen = JakobB()
print(gen.start())  # Output: My custom start
print(gen.next())   # Output: 42
print(gen.stop())   # Output: Done
`;

const editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");
editor.session.setMode("ace/mode/python");
editor.setValue(defaultEditorCode, -1);

const term = new Terminal();
term.open(document.getElementById('terminal'));
term.writeln("Welcome to Python Runner!");

let currentLine = "";

term.onKey(e => {
  if (e.key === '\r') {
    const command = currentLine.trim();
    runCommand(command);
    currentLine = "";
  } else if (e.key === '\u007f') {
    currentLine = currentLine.slice(0, -1);
    term.write('\b \b');
  } else {
    currentLine += e.key;
    term.write(e.key);
  }
});

function runCommand(command) {
  if (command === "help") {
    term.writeln("");
    term.writeln("\nCommands:");
    term.writeln("  run             → Run the code in the editor");
    term.writeln("  <script_name> [args...] → Run a pre-saved script with optional arguments");
    term.writeln("  help            → Show this help message");

    fetch('/scripts')
      .then(res => res.json())
      .then(scripts => {
        term.writeln("\nAvailable scripts:");
        for (const section in scripts) {
          scripts[section].forEach(name => term.writeln(`  ${name} (${section})`));
        }
      });
  } else if (command === "run") {
    fetch('/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code: editor.getValue() })
    })
    .then(res => res.text())
    .then(output => term.writeln(`\n${output}`));
  } else {
    // Parse: <script_name> [args...]
    const parts = command.split(/\s+/);
    const script = parts[0];
    const args = parts.slice(1);

    // Find which section the script is in
    fetch('/scripts')
      .then(res => res.json())
      .then(scripts => {
        let foundSection = null;
        for (const section in scripts) {
          if (scripts[section].includes(script)) {
            foundSection = section;
            break;
          }
        }
        if (!foundSection) {
          term.writeln(`\n[Error] Script '${script}' not found.`);
          return;
        }
        fetch('/script', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ script, section: foundSection, args })
        })
        .then(res => res.text())
        .then(output => {
          term.writeln(`\n${output}`);
          loadSidebar(); // Refresh scripts and data section
        });
      });
  }
}

// --- Script List Sidebar Logic ---
function loadSidebar() {
  // Load scripts
  fetch('/scripts')
    .then(res => res.json())
    .then(data => {
      document.getElementById('script-list-generate-bins').innerHTML = '';
      document.getElementById('script-list-strategies').innerHTML = '';
      document.getElementById('script-list-custom-code').innerHTML = '';

      for (const section of ['generate_bins', 'strategies', 'custom_code']) {
        const ul = document.getElementById(`script-list-${section.replace('_', '-')}`);
        (data[section] || []).forEach(script => {
          const li = document.createElement('li');
          li.textContent = script;
          li.title = script; // Add tooltip for full name
          li.style.cursor = 'pointer';

          li.onclick = () => {
            fetch(`/src/${section}/${script}.py`)
              .then(res => res.text())
              .then(code => {
                editor.setValue(code, -1);
                editor.setReadOnly(false);
              });
            // Uncomment to run on click:
            /*
            term.writeln(`\n[Running script: ${script}]`);
            fetch('/script', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ script, section })
            })
            .then(res => res.text())
            .then(output => term.writeln(output));
            */
          };
          ul.appendChild(li);
        });
      }
    });

  // Load data files
  fetch('/data')
    .then(res => res.json())
    .then(files => {
      const ul = document.getElementById('data-list');
      ul.innerHTML = '';
      files.forEach(filename => {
        const li = document.createElement('li');
        li.textContent = filename;
        li.style.cursor = 'pointer';
        li.onclick = () => {
          fetch(`src/data/${filename}`)
            .then(res => res.text())
            .then(content => {
              editor.setValue(content, -1);
              editor.setReadOnly(true);
            });
        };
        ul.appendChild(li);
      });
    });
}

// Load scripts on page load
window.onload = function() {
  loadSidebar();
};

document.getElementById('save-script-btn').onclick = function() {
  const name = document.getElementById('save-script-name').value.trim();
  const code = editor.getValue();
  const section = document.getElementById('save-script-section').value;
  if (!name) {
    term.writeln('\n[Error] Please enter a script name.');
    return;
  }
  fetch('/save_script', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, code, section })
  })
  .then(res => res.text())
  .then(msg => {
    term.writeln('\n' + msg);
    loadSidebar();
  });
}

// Reset editor to default code when header is clicked
const header = document.getElementById('header');
header.style.cursor = 'pointer';
header.onclick = function() {
  editor.setValue(defaultEditorCode, -1);
  editor.setReadOnly(false);
};

// --- Theme toggle logic ---
const themeToggle = document.getElementById('theme-toggle');
let isLight = false;

function setTheme(light) {
  isLight = light;
  document.body.classList.toggle('light', isLight);
  // Ace editor theme
  editor.setTheme(isLight ? "ace/theme/github" : "ace/theme/monokai");
  // Terminal colors (xterm.js >=5.0.0)
  if (isLight) {
    term.options.theme = {
      background: '#f4f4f4',
      foreground: '#222'
    };
  } else {
    term.options.theme = {
      background: '#000',
      foreground: '#fff'
    };
  }
  // Button icon/text
  themeToggle.textContent = isLight ? "☀️ Light" : "🌙 Dark";
}

// Only one onload handler
window.onload = function() {
  loadSidebar();
  if (localStorage.getItem('theme') === 'light') setTheme(true);
};

// Only one onclick handler
themeToggle.onclick = function() {
  setTheme(!isLight);
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
};

