import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const extensionRoot = path.resolve(__dirname, '..');
const distDir = path.resolve(extensionRoot, 'dist');
const srcDir = path.resolve(extensionRoot, 'src');

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// 1. Process and write manifest.json to dist/manifest.json
const rootManifestPath = path.resolve(extensionRoot, 'manifest.json');
const manifest = JSON.parse(fs.readFileSync(rootManifestPath, 'utf8'));

const distManifest = {
  ...manifest,
  background: {
    service_worker: "service-worker/index.js",
    type: "module"
  },
  content_scripts: (manifest.content_scripts || []).map(cs => ({
    ...cs,
    js: cs.js.map(p => p.replace(/^dist\//, ''))
  })),
  side_panel: {
    default_path: "sidepanel/index.html"
  },
  action: {
    ...manifest.action,
    default_title: manifest.action?.default_title || "Sahaay Browser Sidebar"
  },
  options_ui: {
    page: "options/index.html",
    open_in_tab: false
  }
};

fs.writeFileSync(
  path.resolve(distDir, 'manifest.json'),
  JSON.stringify(distManifest, null, 2),
  'utf8'
);

// 2. Package sidepanel
const distSidepanelDir = path.resolve(distDir, 'sidepanel');
fs.mkdirSync(distSidepanelDir, { recursive: true });

let sidepanelHtml = fs.readFileSync(path.resolve(srcDir, 'sidepanel/index.html'), 'utf8');
sidepanelHtml = sidepanelHtml.replace('../../dist/sidepanel/sidepanel.js', './sidepanel.js');
fs.writeFileSync(path.resolve(distSidepanelDir, 'index.html'), sidepanelHtml, 'utf8');

fs.copyFileSync(
  path.resolve(srcDir, 'sidepanel/sidepanel.css'),
  path.resolve(distSidepanelDir, 'sidepanel.css')
);

// 3. Package popup
const distPopupDir = path.resolve(distDir, 'popup');
fs.mkdirSync(distPopupDir, { recursive: true });

let popupHtml = fs.readFileSync(path.resolve(srcDir, 'popup/index.html'), 'utf8');
popupHtml = popupHtml.replace('../../dist/popup/popup.js', './popup.js');
fs.writeFileSync(path.resolve(distPopupDir, 'index.html'), popupHtml, 'utf8');

// 4. Package options
const distOptionsDir = path.resolve(distDir, 'options');
fs.mkdirSync(distOptionsDir, { recursive: true });
fs.copyFileSync(
  path.resolve(srcDir, 'options/index.html'),
  path.resolve(distOptionsDir, 'index.html')
);

// 5. Verification: Check that every file referenced in distManifest exists
const filesToCheck = [
  distManifest.background.service_worker,
  ...distManifest.content_scripts.flatMap(cs => cs.js),
  distManifest.side_panel.default_path,
  distManifest.options_ui.page,
];

let allValid = true;
for (const relPath of filesToCheck) {
  const fullPath = path.resolve(distDir, relPath);
  if (!fs.existsSync(fullPath)) {
    console.error(`[Package Error] Missing referenced asset: ${relPath} (expected at ${fullPath})`);
    allValid = false;
  }
}

if (!allValid) {
  console.error('[Package Error] Extension packaging failed validation!');
  process.exit(1);
}

console.log('[Package Success] Extension successfully packaged to canonical directory:');
console.log(`  ${distDir}`);
console.log('  Manifest and all referenced files verified.');

