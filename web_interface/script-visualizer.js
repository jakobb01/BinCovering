// --- Script Visualizer ---
function renderScriptVisual(code, filename) {
    const visual = document.getElementById('script-visual');
    visual.innerHTML = ''; // Clear previous
  
    // Parse imports (from ... import ... or import ...)
    const fromImportRegex = /from\s+([.\w_]+)\s+import\s+([A-Za-z0-9_,\s*]+)/g;
    const importRegex = /import\s+([A-Za-z0-9_.,\s]+)/g;
    const methodRegex = /^\s*def\s+([A-Za-z0-9_]+)\s*\(/gm;
    const classRegex = /^\s*class\s+([A-Za-z0-9_]+)/gm;
  
    let imports = new Set();
    let methods = [];
    let classes = [];
  
    // Extract imports
    let match;
    while ((match = fromImportRegex.exec(code))) {
      const module = match[1];
      const items = match[2].split(',').map(item => item.trim());
      items.forEach(item => {
        if (item && !['os', 'sys', 'datetime', 'random', 'subprocess', 'flask', 'request', 'jsonify', 'send_from_directory'].includes(item)) {
          imports.add(`${item} (from ${module})`);
        }
      });
    }
  
    while ((match = importRegex.exec(code))) {
      const modules = match[1].split(',').map(mod => mod.trim());
      modules.forEach(mod => {
        if (mod && !['os', 'sys', 'datetime', 'random', 'subprocess', 'flask', 'request', 'jsonify', 'send_from_directory'].includes(mod)) {
          imports.add(mod);
        }
      });
    }
  
    // Extract methods
    while ((match = methodRegex.exec(code))) {
      methods.push(match[1]);
    }
  
    // Extract classes
    while ((match = classRegex.exec(code))) {
      classes.push(match[1]);
    }
  
    // Create SVG container with proper dimensions
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', '400');
    svg.setAttribute('viewBox', '0 0 800 400');
    svg.style.background = 'transparent';
    svg.style.borderRadius = '8px';
  
    const importArray = Array.from(imports);
    
    // Calculate dynamic spacing
    const mainX = 400;
    const mainY = 200;
    
    // Create main file node (center)
    const mainNode = createVisualNode(
      filename ? filename.replace(/^.*[\\/]/, '').replace('.py', '') : 'Script',
      mainX, mainY, 'main', svg
    );
  
    // Create import nodes (left side) with proper margin
    importArray.forEach((imp, index) => {
      const x = 120; // Add left margin
      const y = 80 + (index * 45); // Closer spacing
      createVisualNode(imp, x, y, 'import', svg);
      createConnection(svg, x + 60, y, mainX - 60, mainY); // Connect to main node
    });
  
    // Create method nodes (right side)
    methods.forEach((method, index) => {
      const x = 680; // Add right margin
      const y = 80 + (index * 40);
      createVisualNode(`${method}()`, x, y, 'method', svg);
      createConnection(svg, mainX + 60, mainY, x - 60, y); // Connect from main node
    });
  
    // Create class nodes (bottom) with better spacing
    classes.forEach((cls, index) => {
      const x = 300 + (index * 150); // Better horizontal spacing
      const y = 320;
      createVisualNode(cls, x, y, 'class', svg);
      createConnection(svg, mainX, mainY + 20, x, y - 20); // Connect from main node
    });
  
    visual.appendChild(svg);
  }
  
  function createVisualNode(text, x, y, type, svg) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    
    // Convert text to uppercase
    const displayText = text.toUpperCase();
    
    // Set max width and calculate wrapping
    const maxWidth = type === 'import' ? 120 : 140;
    const charWidth = 7;
    const lineHeight = 14;
    const padding = 20;
    
    // Split text into words and wrap
    const words = displayText.split(' ');
    const lines = [];
    let currentLine = '';
    
    for (const word of words) {
      const testLine = currentLine ? `${currentLine} ${word}` : word;
      if (testLine.length * charWidth <= maxWidth - padding) {
        currentLine = testLine;
      } else {
        if (currentLine) {
          lines.push(currentLine);
          currentLine = word;
        } else {
          // Word is too long, truncate it
          lines.push(word.substring(0, Math.floor((maxWidth - padding) / charWidth) - 3) + '...');
          currentLine = '';
        }
      }
    }
    if (currentLine) lines.push(currentLine);
    
    // Calculate box dimensions
    const textWidth = Math.min(maxWidth, Math.max(80, lines.reduce((max, line) => 
      Math.max(max, line.length * charWidth + padding), 0)));
    const textHeight = Math.max(28, lines.length * lineHeight + 14);
    
    // Node background
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', x - textWidth/2);
    rect.setAttribute('y', y - textHeight/2);
    rect.setAttribute('width', textWidth);
    rect.setAttribute('height', textHeight);
    rect.setAttribute('rx', 14);
    
    // Set colors based on node type
    switch(type) {
      case 'main':
        rect.setAttribute('fill', '#4a9eff');
        rect.setAttribute('stroke', '#2563eb');
        break;
      case 'import':
        rect.setAttribute('fill', '#10b981');
        rect.setAttribute('stroke', '#047857');
        break;
      case 'method':
        rect.setAttribute('fill', '#f59e0b');
        rect.setAttribute('stroke', '#d97706');
        break;
      case 'class':
        rect.setAttribute('fill', '#ef4444');
        rect.setAttribute('stroke', '#dc2626');
        break;
    }
    rect.setAttribute('stroke-width', '2');
    
    // Add rectangle to group FIRST
    g.appendChild(rect);
    
    // Add text lines AFTER rectangle
    lines.forEach((line, index) => {
      const textEl = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      textEl.setAttribute('x', x);
      textEl.setAttribute('y', y - (lines.length - 1) * lineHeight/2 + index * lineHeight + 4);
      textEl.setAttribute('text-anchor', 'middle');
      textEl.setAttribute('font-family', 'monospace');
      textEl.setAttribute('font-size', '11');
      textEl.setAttribute('fill', 'white');
      textEl.setAttribute('font-weight', 'bold');
      textEl.textContent = line;
      g.appendChild(textEl);
    });
    
    // Add tooltip for full text
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = text;
    g.appendChild(title);
    
    // Add group to SVG
    svg.appendChild(g);
    
    return g;
  }
  
  function createConnection(svg, x1, y1, x2, y2) {
    // Add defs once per SVG
    if (!svg.querySelector('defs')) {
      const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      const arrowMarker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      arrowMarker.setAttribute('id', 'arrowhead');
      arrowMarker.setAttribute('markerWidth', '10');
      arrowMarker.setAttribute('markerHeight', '7');
      arrowMarker.setAttribute('refX', '9');
      arrowMarker.setAttribute('refY', '3.5');
      arrowMarker.setAttribute('orient', 'auto');
      
      const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
      polygon.setAttribute('points', '0 0, 10 3.5, 0 7');
      polygon.setAttribute('fill', '#666');
      
      arrowMarker.appendChild(polygon);
      defs.appendChild(arrowMarker);
      svg.appendChild(defs);
    }
    
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    line.setAttribute('x1', x1);
    line.setAttribute('y1', y1);
    line.setAttribute('x2', x2);
    line.setAttribute('y2', y2);
    line.setAttribute('stroke', '#666');
    line.setAttribute('stroke-width', '2');
    line.setAttribute('stroke-dasharray', '5,5');
    line.setAttribute('opacity', '0.7');
    line.setAttribute('marker-end', 'url(#arrowhead)');
    svg.appendChild(line);
  }
  
  // --- Hook up to editor changes ---
  function updateScriptVisual() {
    const code = editor.getValue();
    // Try to get filename from sidebar selection or fallback
    let filename = document.querySelector('.sidebar-section li.selected')?.textContent || '';
    renderScriptVisual(code, filename);
  }
  
  // When loading a script from sidebar, mark as selected and update visual
  function markSidebarSelected(name) {
    document.querySelectorAll('.sidebar-section li').forEach(li => {
      li.classList.toggle('selected', li.textContent === name);
    });
  }
  
  // Patch existing sidebar click handlers to update visual and selection
  function patchSidebarClicks() {
    ['generate-bins', 'strategies', 'custom-code'].forEach(section => {
      const ul = document.getElementById(`script-list-${section}`);
      if (ul) {
        ul.addEventListener('click', e => {
          if (e.target.tagName === 'LI') {
            markSidebarSelected(e.target.textContent);
            setTimeout(updateScriptVisual, 100); // Wait for code to load
          }
        });
      }
    });
  }
  
  // Initialize visualization when this script loads
  function initializeScriptVisualizer() {
    // Update visual when editor changes (debounced)
    let visualUpdateTimeout;
    editor.session.on('change', () => {
      clearTimeout(visualUpdateTimeout);
      visualUpdateTimeout = setTimeout(updateScriptVisual, 500);
    });
  
    // Initial setup
    setTimeout(() => {
      updateScriptVisual();
      patchSidebarClicks();
    }, 500);
  }
  
  // Auto-initialize if editor is available, otherwise wait for it
  if (typeof editor !== 'undefined') {
    initializeScriptVisualizer();
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      // Wait a bit for editor to be initialized
      setTimeout(initializeScriptVisualizer, 1000);
    });
  }