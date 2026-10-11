// Portable fallback for this workspace's bundled Node runtime, where npm is not on PATH.
import { existsSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { homedir } from 'node:os';
import { spawnSync } from 'node:child_process';
const candidates = [join(dirname(process.execPath), 'node_modules/npm/bin/npm-cli.js'), join(dirname(process.execPath), '../node_modules/npm/bin/npm-cli.js')];
const cached = join(homedir(), 'AppData/Local/pnpm/store/v11/links/@/npm');
if (existsSync(cached)) for (const version of readdirSync(cached)) for (const hash of readdirSync(join(cached, version))) candidates.push(join(cached, version, hash, 'node_modules/npm/bin/npm-cli.js'));
const cli = candidates.find(existsSync);
if (!cli) { console.error('npm was not found. Install Node.js 22.12+ with npm, then use npm install and npm run dev.'); process.exit(1); }
const result = spawnSync(process.execPath, [cli, ...process.argv.slice(2)], { stdio: 'inherit' });
if (result.error) console.error(result.error.message);
process.exit(result.status ?? 1);
