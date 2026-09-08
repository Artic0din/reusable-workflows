import { copyFileSync } from 'node:fs';
copyFileSync(new URL('source.js', import.meta.url), new URL('dist/main.js', import.meta.url));
