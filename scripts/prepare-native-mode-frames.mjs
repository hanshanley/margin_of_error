import assert from 'node:assert/strict';
import { existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { createHash } from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { nativeModeVersion, reviewNativeModeFrames, encodeNativeModeReview } from './native-mode-frames.mjs';

const target = join(nativeModeVersion, 'queries.json.gz');
assert.equal(existsSync(target), false, 'Never overwrite an existing prepared source-mode query');
const data = await reviewNativeModeFrames();
const raw = encodeNativeModeReview(data), body = gzipSync(raw, { mtime: 0 });
writeFileSync(target, body, { flag: 'wx' });
writeFileSync(join(nativeModeVersion, 'summary.json'), JSON.stringify(data.summary, null, 2) + '\n', { flag: 'wx' });
console.log(JSON.stringify({ status: 'PASS_prepared_complete204_source_mode_queries_NOT_live_fix',
  bytes: body.length, sha256: createHash('sha256').update(body).digest('hex'), summary: data.summary }));
