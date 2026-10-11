import { writeFileSync } from 'node:fs';
import { demoData } from '../src/data/demo.ts';
const value = (v: unknown) => typeof v === 'string' ? `'${v.replaceAll("'", "''")}'` : typeof v === 'boolean' ? String(v) : String(v);
const sql = Object.entries(demoData).map(([table, rows]) => {
  const name = table === 'usage' ? 'product_usage' : table;
  const keys = Object.keys(rows[0]);
  return `insert into public.${name} (${keys.join(', ')}) values\n${rows.map(row => `(${keys.map(k => value((row as unknown as Record<string, unknown>)[k])).join(', ')})`).join(',\n')}\non conflict (id) do update set ${keys.filter(k => k !== 'id').map(k => `${k} = excluded.${k}`).join(', ')};`;
});
// FK order must precede tasks/issues. Fixture order places projects before tasks.
writeFileSync('supabase/seed.sql', '-- Generated from src/data/demo.ts. Fictional snapshot anchored to 2026-10-10.\n-- Safe to rerun. Run the migration first.\nbegin;\n' + sql.join('\n\n') + '\ncommit;\n');
