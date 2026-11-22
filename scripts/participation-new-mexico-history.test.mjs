import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import { loadNewMexicoHistory, newMexicoHistoryRows } from "../public/scripts/participation-new-mexico-history.js";

const header = "state_code,election_date,geography_level,county_id,county,unit,source_reported_count,"
  + "source_eligible_voters,source_eligible_rate_pct,rate_hold,source_status,source_clock,"
  + "native_numerator_label,native_denominator_label";
const row = (level, id, county, unit, count, eligible, hold = "") =>
  ["NM", "2022-11-08", level, id, county, unit, count, eligible, hold ? "" : 100 * count / eligible,
    hold, "reported", "11/29/2022 4:39 PM MT", "Ballots Cast", "Eligible Voters"].join(",");
const records = [row("state", "", "", "", 2162, 21617)];
for (let i = 1; i <= 33; i++) {
  const units = i === 1 ? 2131 : 1, total = i === 2 ? 0 : units, denominator = i === 2 ? -3 : units * 10;
  records.push(row("county", i, `County ${i}`, "", total, denominator,
    i === 2 ? "component_denominator_negative_or_below_count" : ""));
  for (let j = 1; j <= units; j++)
    records.push(row("reporting_unit", i, `County ${i}`, `PCT ${j}`, i === 2 ? 0 : 1, i === 2 ? -3 : 10,
      i === 2 ? "negative_source_denominator" : ""));
}
const csv = [header, ...records].join("\n");

test("New Mexico retains signed native cells and requires complete same-report rollups", () => {
  const rows = newMexicoHistoryRows(csv);
  assert.equal(rows.length, 34);
  assert.equal(rows.find(r => r.county === "County 2").rate, null);
  assert.throws(() => newMexicoHistoryRows(csv.replace(",2162,21617,", ",2163,21617,")), /New Mexico/);
  assert.throws(() => newMexicoHistoryRows(csv.replace(",0,-3,,negative_source_denominator,", ",0,-3,0,,")), /New Mexico/);
  assert.throws(() => newMexicoHistoryRows([csv, records.at(-1)].join("\n")), /New Mexico/);
  assert.throws(() => newMexicoHistoryRows(csv.replaceAll("County 3,", "County 2,")), /New Mexico/);
});

test("New Mexico reads only the checksum-bound runtime download", async () => {
  const path = "release/participation-nm-historical-native-turnout.csv.gz";
  const base_url = "https://example.test/accepted";
  const body = gzipSync(csv);
  const file = {path, url: `${base_url}/${path}`, media_type: "text/csv", compression: "gzip",
    bytes: body.byteLength, sha256: createHash("sha256").update(body).digest("hex")};
  const inputs = {base_url, supported_release: {downloads: {[path]: file}}};
  const data = await loadNewMexicoHistory(inputs, async url => {
    assert.equal(url, file.url);
    return new Response(body);
  });
  assert.equal(data.rows[0].count, 2162);
  assert.equal(await loadNewMexicoHistory({}), null);
  await assert.rejects(loadNewMexicoHistory(inputs, async () => new Response(Uint8Array.from(body, x => x ^ 1))), /checksum/);
  file.url = "https://example.test/other";
  await assert.rejects(loadNewMexicoHistory(inputs, () => assert.fail("Unbound URL requested")), /not bound/);
});
