const editor = ace.edit("editor");
editor.setTheme("ace/theme/monokai");
editor.session.setMode("ace/mode/python");
editor.setValue(
  `def function(filename, custom_input_int):
      print("Do something fun here!")
  
  
  if __name__ == "__main__":
      # Check for valid arguments
      if len(sys.argv) != 3:
          print("Usage: python script.py <filename> <bins_covered>")
          sys.exit(1)
  
      custom_input_file = sys.argv[1]
      filename = "./src/data/" + custom_input_file
      custom_input_int = int(sys.argv[2])
  
      function(filename, custom_input_int)
  `, -1);

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
    term.writeln("  <script_name> [args...] → Run a predefined script with optional arguments");
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