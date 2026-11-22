import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { gunzipSync } from "node:zlib";
import { bindDistrictResults, districtFill, districtValue } from "../public/scripts/participation-house-districts.js";

const [input, output] = process.argv.slice(2);
if (!input || !output || process.argv.length !== 4)
  throw new Error("Usage: node scripts/build-offline-house-district-map.mjs inputs reproduced");

const pin = body => ({ bytes: body.length, sha256: createHash("sha256").update(body).digest("hex") });
const receipt = JSON.parse(readFileSync(join(input, "receipt.json")));
const manifest = JSON.parse(readFileSync(join(input, "source.json")));
function checked(name, expected) {
  const body = readFileSync(join(input, name));
  const got = pin(body);
  if (got.bytes !== expected.bytes || got.sha256 !== expected.sha256)
    throw new Error(`Pinned input changed: ${name}`);
  const decoded = gunzipSync(body);
  const result = pin(decoded);
  if (result.bytes !== expected.decoded_bytes || result.sha256 !== expected.decoded_sha256)
    throw new Error(`Pinned decoded input changed: ${name}`);
  return JSON.parse(decoded);
}
const geometry = checked("district-paths.json.gz", receipt);
const congress = checked("results.json.gz", manifest.results);
const districts = bindDistrictResults(geometry, congress);
const qualified = districts.filter(({row}) => row.qualified_comparison).length;
const held = districts.length - qualified;
const bound = Math.max(5, Math.ceil(Math.max(...districts.map(({row}) => Math.abs(districtValue(row, "margin") ?? 0))) / 5) * 5);
const escape = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pp = value => value === null ? "Held" : `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
const display = count => count == null ? "Not supplied" : count.toLocaleString("en-US");
const rows = districts.map(({path, row}) => ({
  district: path.district, race_id: row.id, qualified: row.qualified_comparison,
  previous_D: row.previous?.D, previous_R: row.previous?.R, previous_O: row.previous?.O,
  current_D: row.D, current_R: row.R, current_O: row.O, current_U: row.U,
  D_minus_R_margin_change_pp: districtValue(row, "margin"),
  holds: row.comparison_holds.join("; "), source_updated_at: row.source_updated_at,
}));
const title = "House district swings, 2024 to 2026";
const description = `${qualified} qualified comparisons; ${held} held. D-minus-R margin change in percentage points.`;
const shapes = districts.map(({path}, i) => {
  const row = rows[i], value = row.D_minus_R_margin_change_pp;
  const label = value === null ? `${row.district}: held. ${row.holds}`
    : `${row.district}: ${pp(value)} percentage points.`;
  return `<path data-district="${row.district}" fill="${value === null ? "url(#held)" : districtFill(value, bound)}" d="${path.d}"><title>${escape(label)}</title></path>`;
}).join("");
function figure(paper) {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 800" role="img" aria-labelledby="title description">
<title id="title">${title}</title><desc id="description">${description} Gray hatching marks a hold, not zero change.</desc>
<defs><pattern id="held" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#dadbd6"/><path d="M-1 1L1-1M0 6L6 0M5 7L7 5" stroke="#68716d" stroke-width=".6"/></pattern></defs>
<rect width="1000" height="800" fill="${paper}"/>
<g fill="#1a1a1a"><text x="34" y="46" font-family="Georgia,serif" font-size="31">${title}</text><text x="34" y="75" font-family="system-ui,sans-serif" font-size="17">${description}</text></g>
<g transform="translate(0 78)" fill-rule="evenodd" stroke="#8c8f88" stroke-width=".45">${shapes}</g>
<g font-family="system-ui,sans-serif" fill="#454545" font-size="15">
<text x="58" y="700">Alaska</text><text x="310" y="700">Hawaii · insets not to scale</text>
<text x="34" y="745">Toward R</text><text x="344" y="745">toward D</text>
${[-1,-.5,0,.5,1].map((x,i) => `<rect x="${111+i*45}" y="730" width="44" height="18" fill="${districtFill(x*bound,bound)}"/>`).join("")}
<text x="111" y="771">−${bound}</text><text x="215" y="771">0</text><text x="305" y="771">+${bound}</text>
<rect x="443" y="730" width="26" height="18" fill="url(#held)"/><text x="479" y="745">Held, not zero</text>
<text x="650" y="745">Source check: ${escape(manifest.checked_at.slice(0, 10))} UTC</text>
<text x="650" y="771">Reviewed snapshot · not voter turnout</text></g></svg>\n`;
}
const chart = figure("#F2EFE7");
const csv = value => value == null ? "" : `"${String(value).replaceAll('"','""')}"`;
const fields = Object.keys(rows[0]);
const table = rows.map(r => `<tr><th scope="row">${r.district}</th>${[
  display(r.previous_D), display(r.previous_R), display(r.current_D), display(r.current_R),
  pp(r.D_minus_R_margin_change_pp), r.holds || "Qualified recorded comparison",
].map(cell => `<td>${escape(cell)}</td>`).join("")}</tr>`).join("\n");
const html = `<!DOCTYPE html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${title}</title><style>
body{background:#f2efe7;color:#1a1a1a;font:1rem/1.5 system-ui,sans-serif;max-width:65rem;margin:auto;padding:1rem}
h1,h2{font-family:Georgia,serif;font-weight:normal}h1{font-size:clamp(1.6rem,4vw,2.4rem)}
svg{display:block;width:100%;height:auto}.table{overflow:auto}table{border-collapse:collapse;min-width:40rem}
th,td{text-align:left;vertical-align:top;padding:.45rem;border-bottom:1px solid #d6d3cc}
td:nth-child(n+2):nth-child(-n+6){text-align:right;font-variant-numeric:tabular-nums}a{color:#254d69}
</style><main><h1>${title}</h1>
<p>${description} This is a fixed candidate checked ${escape(manifest.checked_at)}, not the live explorer. The map uses the 2026 Census district outlines.</p>
<p><a href="#district-table">Skip to the 435-district table</a> · <a href="district-map-values.csv">Download the exact plotted data</a></p>
${chart}
<p>Blue shows movement toward Democrats; red toward Republicans. Gray hatching marks an unavailable comparison, not zero change. These are candidate votes, not participation or observed voter switching.</p>
<h2 id="district-table">District counts and comparison decisions</h2>
<div class="table" role="region" aria-labelledby="district-table" tabindex="0"><table>
<thead><tr>${["District","2024 D","2024 R","2026 D","2026 R","Margin change (pp)","Decision"].map(label => `<th scope="col">${label}</th>`).join("")}</tr></thead><tbody>${table}</tbody></table></div>
</main></html>\n`;
mkdirSync(output);
writeFileSync(join(output, "house-district-map.html"), html);
writeFileSync(join(output, "house-district-map.svg"), chart);
writeFileSync(join(output, "house-district-map-substack.svg"), figure("#F7F5F0"));
writeFileSync(join(output, "district-map-values.csv"), [fields.join(","), ...rows.map(r => fields.map(f => csv(r[f])).join(","))].join("\n") + "\n");
