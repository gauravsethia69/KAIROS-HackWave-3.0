// KAIROS current-App safe decoration update. No App.tsx or backend edits.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const root = process.cwd();
const appPath = path.join(root, 'src', 'app', 'App.tsx');
const cssPath = path.join(root, 'src', 'styles', 'kairos-sakura-theme.css');
const sourceArt = path.join(__dirname, 'kairos-fuji-panel.png');
const targetArt = path.join(root, 'public', 'assets', 'kairos-fuji-panel.png');
const gitDir = path.join(root, '.git');
const begin = '/* KAIROS CURRENT HERO IMAGE — BEGIN */';
const end = '/* KAIROS CURRENT HERO IMAGE — END */';
const fail = (message) => { console.error('Stopped safely: ' + message); process.exit(1); };
const sha = (filename) => crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex');

if (!fs.existsSync(appPath) || !fs.existsSync(cssPath)) fail('Run from the KAIROS project root (src/app/App.tsx and src/styles/kairos-sakura-theme.css required).');
if (!fs.existsSync(sourceArt)) fail('Missing kairos-fuji-panel.png: extract the entire ZIP alongside this installer.');
const app = fs.readFileSync(appPath, 'utf8');
if (!/\<KairosHeroScene\s*\/\>/.test(app)) fail('Current App.tsx does not contain <KairosHeroScene/>. No files were modified.');
const original = fs.readFileSync(cssPath, 'utf8');
if (original.includes(begin)) {
  if (fs.existsSync(targetArt) && sha(sourceArt) === sha(targetArt)) {
    console.log('Already installed. No files changed.');
    process.exit(0);
  }
  fail('A different/current Fuji override already exists; no changes made.');
}
if (original.includes('KAIROS FUJI HERO OVERRIDE — BEGIN')) fail('Old CSS-only Fuji override detected. Remove/review it first to avoid duplicated backgrounds.');
if (fs.existsSync(targetArt) && sha(sourceArt) !== sha(targetArt)) fail('An existing image at the target path differs. No changes made.');
if (!fs.existsSync(gitDir) || !fs.statSync(gitDir).isDirectory()) fail('Expected a .git folder to store a local backup before changing CSS.');

const override = `\n\n${begin}
/* For App.tsx with <KairosHeroScene/>: hide only that decorative child.
   The live title, breadcrumb, command bar and all application handlers remain untouched. */
.app-shell.kairos-sakura-theme .page-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 18px;
  min-height: 280px;
}
.app-shell.kairos-sakura-theme .page-heading > div:first-child {
  position: relative;
  z-index: 1;
  min-width: 0;
  flex: 1 1 48%;
}
/* In the supplied App.tsx, the second (last) child is <KairosHeroScene/>. */
.app-shell.kairos-sakura-theme .page-heading > :last-child {
  display: none !important;
}
.app-shell.kairos-sakura-theme .page-heading::after {
  content: "";
  display: block;
  flex: 0 1 48%;
  width: 48%;
  min-width: 260px;
  height: clamp(220px, 25vw, 340px);
  align-self: center;
  background: url('/assets/kairos-fuji-panel.png') no-repeat center right / contain;
  pointer-events: none;
  user-select: none;
}
@media (max-width: 1100px) {
  .app-shell.kairos-sakura-theme .page-heading { min-height: 230px; }
  .app-shell.kairos-sakura-theme .page-heading::after {
    min-width: 200px;
    width: 42%;
    flex-basis: 42%;
    height: 245px;
  }
}
@media (max-width: 760px) {
  .app-shell.kairos-sakura-theme .page-heading { min-height: 0; }
  .app-shell.kairos-sakura-theme .page-heading::after { display: none !important; }
}
${end}\n`;

const backupDir = path.join(gitDir, 'kairos-hero-backups');
fs.mkdirSync(backupDir, { recursive: true });
const stamp = new Date().toISOString().replace(/[:.]/g, '-');
const backupFile = path.join(backupDir, `kairos-sakura-theme-before-fuji-${stamp}.css`);
fs.writeFileSync(backupFile, original, 'utf8');
fs.mkdirSync(path.dirname(targetArt), { recursive: true });
let artCreated = false;
try {
  if (!fs.existsSync(targetArt)) {
    fs.copyFileSync(sourceArt, targetArt);
    artCreated = true;
  }
  fs.writeFileSync(cssPath, original + override, 'utf8');
} catch (error) {
  fs.writeFileSync(cssPath, original, 'utf8');
  if (artCreated && fs.existsSync(targetArt)) fs.unlinkSync(targetArt);
  fail(error.message);
}
console.log('SUCCESS: Fuji image replaces the current workspace hero through scoped CSS.');
console.log('Modified: src/styles/kairos-sakura-theme.css');
console.log('Added: public/assets/kairos-fuji-panel.png');
console.log('Not edited: App.tsx, KairosHeroScene.tsx, backend, Supabase, AI, landing, gate.');
console.log('Backup: ' + path.relative(root, backupFile));
console.log('Next: npm.cmd run build; npm.cmd run dev');
