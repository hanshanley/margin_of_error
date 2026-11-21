import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
import { createHash } from "node:crypto";
import { gzipSync, gunzipSync } from "node:zlib";
import { administrativeRows, coverageCsvFile, coverageRows, historicalCountyDownload, historicalCountyRows,
  loadHistoricalCountyRows, indianaTurnoutDownload, stateCountyArchivesDownload, stateCountyArchiveFrames,
  northCarolinaAgeRows, washingtonAgeSeries, southeastHistoryRows, kansasStudyFrames, hawaiiHistoryFrames,
  alabamaBallotRows, alaskaBallotRows, alaskaMidtermMapQualified,
  connecticutTownRows, alabamaReconciledCountyFrame, alaskaAgeRows,
  publishedCpsStatus, cpsMapCells, cpsRowsForBasis,
  wyomingCurrentCountyFrame, wyomingCanvassCountyFrame, nebraskaCountyReportsFrame, coloradoPrecinctFrames }
  from "../public/scripts/participation-coverage.js";
import { countStates } from "../public/scripts/participation-counts.js";
import { bindHistoricalCountyMap, bindOfficialCountyArchive, countyMapFill }
  from "../public/scripts/participation-historical-county-map.js";
import { bindTetonPrecinctMap } from "../public/scripts/participation-teton-precinct-map.js";
import { bindDenverPrecinctMap } from "../public/scripts/participation-denver-precinct-map.js";
import { bindMarylandPrecinctLayer } from "../public/scripts/participation-maryland-precinct-map.js";
import { bindMinnesotaPrecinctLayer, minnesotaCountyHistory, minnesotaPrecinctFrames }
  from "../public/scripts/participation-minnesota-precinct-map.js";

test("Alaska digital age reports retain withheld statewide figures and explicitly unknown gender", () => {
  const csv = "state_code,election_date,age_group,reported_gender,registered_in_report,voter_history_credits,"
    + "history_per_registered,rate_hold_reason,source_status,source_reported_percent\n"
    + "AK,2022-11-08,TOTALS,all,602912,267964,,printed_percent_disagrees_with_counts,reported,40.10\n"
    + "AK,2022-11-08,TOTALS,unknown,699,119,0.17024320,,retained_after_failure,";
  const [total, unknown] = alaskaAgeRows(csv);
  assert.deepEqual([total.credited, total.rate, total.printed], [267964, null, "40.10"]);
  assert.deepEqual([unknown.gender, unknown.rate, unknown.status], ["unknown", 0.17024320, "retained_after_failure"]);
  assert.throws(() => alaskaAgeRows(csv.replace("0.17024320", "0.71024320")), /Invalid Alaska/);
});

test("Alaska keeps mixed central ballot modes out of the physical precinct scope", () => {
  const csv = "state_code,election_date,reporting_unit,unit_scope,source_status,reported_ballots,"
    + "election_day_ballots,absentee_ballots,early_ballots,question_ballots,remote_ballots\n"
    + "AK,2024-11-05,01-600 Ketchikan,precinct_election_day_only,reported,5,5,0,0,0,0\n"
    + "AK,2024-11-05,District 6 - Early Voting,central_unallocated_ballots,reported,4069,126,0,3943,0,0";
  assert.deepEqual(alaskaBallotRows(csv).map(row => [row.physical, row.count, row.modes[0]]),
    [[true, 5, 5], [false, 4069, 126]]);
  assert.throws(() => alaskaBallotRows(csv.replace("4069,126", "4068,126")), /Invalid Alaska/);
});

test("Alaska midterm mapping follows a verified geometry receipt, not a hardcoded edition", () => {
  const header = "state_code,election_date,reporting_unit,unit_scope,source_status,reported_ballots,"
    + "election_day_ballots,absentee_ballots,early_ballots,question_ballots,remote_ballots,"
    + "publication_status,official_control_edition_local,source_sha256";
  const row = "AK,2026-11-03,01-600 Ketchikan,precinct_election_day_only,reported,5,5,0,0,0,0,"
    + "OFFICIAL RESULTS,2026-12-01T10:00:00," + "a".repeat(64);
  const checks = ",display_geometry_status,display_geometry_sha256";
  const geometry = "1e9d6b95b88c4ebeea3a1ec5bcd3d0a6052d0436e82dfee0fb62fbc4c25381eb";
  const parsed = alaskaBallotRows(`${header}${checks}\n${row},verified_display_subset,${geometry}`, true);
  assert.ok(alaskaMidtermMapQualified(parsed));
  assert.equal(alaskaMidtermMapQualified(alaskaBallotRows(`${header}\n${row}`, true)), false);
  for (const [status, sha] of [["geometry_changed", "b".repeat(64)], ["source_stopped", ""]]) {
    const held = alaskaBallotRows(`${header}${checks}\n${row},${status},${sha}`, true);
    assert.equal(alaskaMidtermMapQualified(held), false);
    assert.equal(held[0].count, 5);
  }
});

test("Connecticut keeps split-town components and withholds inconsistent rates", () => {
  const csv = "state_code,election_date,geography_level,reporting_unit,source_unit_occurrence,active_checklist,"
    + "checked_as_voted,checked_as_voted_fraction,rate_hold_reason,source_status\n"
    + "CT,1998-11-03,town,Southbury,1,12130,,,malformed_count,reported\n"
    + "CT,2008-11-04,town_part,Durham,1,10,5,0.50000000,,reported\n"
    + "CT,2008-11-04,town_part,Durham,2,20,11,0.55000000,,reported";
  assert.deepEqual(connecticutTownRows(csv).map(row => [row.name, row.part, row.fraction]),
    [["Southbury", "1", ""], ["Durham", "1", "0.50000000"], ["Durham", "2", "0.55000000"]]);
  assert.throws(() => connecticutTownRows(csv.replace("Durham,2", "Durham,1")), /Invalid Connecticut/);
  assert.throws(() => connecticutTownRows(csv.replace("0.55000000", "0.50000000")), /Invalid Connecticut/);
});

test("Alabama reporting-unit controls retain conflicting totals and reject an inconsistent decision", () => {
  const prefix = "state_code,year,county,reconciliation,archive_status,control_status,";
  const controls = prefix + "county_archive_ballots,county_control_ballots,archive_minus_control\n"
    + "AL,2024,CLEBURNE,county_control_disagrees,reported,reported,7680,7860,-180\n"
    + "AL,2024,AUTAUGA,not_reconciled_without_both_sources,source_stopped,reported,,28388,";
  assert.equal(alabamaBallotRows(controls, false)[0].archive_minus_control, "-180");
  assert.equal(alabamaBallotRows(controls, false)[1].county_archive_ballots, "");
  assert.throws(() => alabamaBallotRows(controls.replace("-180", "180"), false), /Invalid Alabama county-control/);
  const units = prefix + "reporting_unit,unit_type,reported_ballots,source_unit_ordinal\n"
    + "AL,2024,CLEBURNE,county_control_disagrees,reported,reported,ABSENTEE,central_mode_or_provisional,12,17";
  assert.equal(alabamaBallotRows(units, true)[0].unit_type, "central_mode_or_provisional");
});

test("Alabama maps only checked county agreements in a whole dated frame", () => {
  const counties = ["TOTAL", "CLEBURNE", ...Array.from({ length: 66 }, (_, i) => `TEST${i}`)]
    .map(county => ({ year: "2024", county, county_control_ballots: "7860",
      reconciliation: county === "CLEBURNE" ? "county_control_disagrees" : "reconciled" }));
  const frame = alabamaReconciledCountyFrame(counties, "2024-11-05");
  assert.equal(frame.size, 68);
  assert.equal(frame.get("CLEBURNE").count, null);
  assert.equal(frame.get("TEST0").count, 7860);
  assert.equal(alabamaReconciledCountyFrame(counties.slice(1), "2024-11-05").size, 0);
  assert.equal(alabamaReconciledCountyFrame(counties, "2020-11-03").size, 0);
});

test("Southeast histories preserve missing ages and distinguish printed and calculated rates", () => {
  const al = "state_code,year,source_status,geography,geography_level,age_group,reported_ballots\n"
    + "AL,2018,reported,BARBOUR,county,100+,\nAL,2024,reported,BARBOUR,county,100+,0";
  assert.deepEqual(southeastHistoryRows(al, "AL").map(row => row.count), [null, 0]);
  const sc = "state_code,year,source_status,reported_participation,reported_registered,numerator_basis,"
    + "published_turnout_pct,published_rate_matches_counts,participation_per_reported_registration\n"
    + "SC,2018,reported,600,1000,ballots_cast,50.0%,False,0.6\n"
    + "SC,2006,retained_after_failure,500,1000,voter_history_credits,50.0%,True,0.5";
  const rows = southeastHistoryRows(sc, "SC");
  assert.equal(rows[0].matches, false);
  assert.equal(rows[0].fraction, 0.6);
  assert.equal(rows[1].basis, "voter_history_credits");
  assert.equal(rows[1].retained, true);
  assert.throws(() => southeastHistoryRows(sc.replace("False,0.6", "False,0.5"), "SC"), /Invalid South Carolina/);
});

test("Washington history distinguishes placeholders, held age labels, missing counts and real zeros", () => {
  const row = (year, election_type, observation_status, total_ballots) => ({
    geography: "Adams", age_group: "55-64", election_date: `${year}-11-04`,
    election_type, observation_status, total_ballots,
  });
  const rows = [
    row(2026, "midterm", "workbook_placeholder", ""),
    row(2024, "presidential", "reported_workbook_aggregate", "0"),
    row(2022, "midterm", "reported_workbook_aggregate", ""),
    row(2018, "midterm", "reported_workbook_aggregate", "30"),
    row(2014, "midterm", "held_ambiguous_age_label", "83"),
    row(2014, "midterm", "held_ambiguous_age_label", "92"),
  ];
  assert.deepEqual(washingtonAgeSeries(rows, "Adams", "55-64", "total", "ballots", "midterm")
    .map(p => p.value), [null, null, 30, null]);
  assert.equal(washingtonAgeSeries(rows, "Adams", "55-64", "total", "ballots", "presidential")[0].value, 0);
  assert.throws(() => washingtonAgeSeries([...rows, rows[1]], "Adams", "55-64", "total", "ballots", ""), /Duplicate/);
});

test("Minnesota county history keeps election type, reported zero, and retained counts distinct", () => {
  const code = "27001";
  const frame = (status, counts) => ({
    status, counties: new Map([[code, { rows: counts.map(count => ({ count })) }]]),
  });
  const frames = new Map([
    ["2024-11-05", frame("reported", [4, 17])],
    ["2022-11-08", frame("retained_after_failure", [7, 0])],
    ["2020-11-03", frame("reported", [0])],
  ]);
  assert.deepEqual(minnesotaCountyHistory(frames, code), [
    { year: 2020, type: "Presidential", status: "reported", count: 0 },
    { year: 2022, type: "Midterm", status: "retained_after_failure", count: 7 },
    { year: 2024, type: "Presidential", status: "reported", count: 21 },
  ]);
  assert.deepEqual(minnesotaCountyHistory(frames, "27003"), []);
});

test("Maryland maps bind only the matching edition and exclude unassigned activity", () => {
  const asset = new URL("../public/participation-archive-geometry/precinct-MD-2022.json.gz", import.meta.url);
  const layer = JSON.parse(gunzipSync(readFileSync(asset)));
  const frame = { date: "2022-11-08", county: "Howard", sha: layer.source_sha256, activity: 131738, unplaced: 21 };
  assert.equal(bindMarylandPrecinctLayer(layer, frame).length, 118);
  assert.throws(() => bindMarylandPrecinctLayer(layer, { ...frame, sha: "0".repeat(64) }), /scope/);
  assert.throws(() => bindMarylandPrecinctLayer(layer, { ...frame, activity: 131717 }), /reconcile/);
  assert.throws(() => bindMarylandPrecinctLayer(layer, { ...frame, county: "Somerset" }), /scope/);
});

test("full-size precinct descriptors allow verified bulk data without relaxing ordinary coverage limits", () => {
  const base_url = "https://example.test/verified";
  const descriptor = (path, bytes) => ({ path, bytes, url: `${base_url}/${path}`, media_type: "text/csv",
    compression: "gzip", sha256: "a".repeat(64) });
  const downloads = {};
  const sources = { base_url, supported_release: { downloads } };
  for (const [file, bytes] of [["participation-co-precinct-voting-statistics", 390202],
    ["participation-mn-historical-precinct-turnout", 759753]]) {
    const path = `release/${file}.csv.gz`;
    downloads[path] = descriptor(path, bytes);
    assert.equal(coverageCsvFile(sources, path), downloads[path]);
    downloads[path] = descriptor(path, 2000001);
    assert.throws(() => coverageCsvFile(sources, path), /not bound/);
  }
  const coverage = "release/participation-administrative-coverage.csv.gz";
  downloads[coverage] = descriptor(coverage, 65537);
  assert.throws(() => coverageCsvFile(sources, coverage), /not bound/);
});

test("Minnesota maps require equal participation counts and election-year precinct IDs", () => {
  const layer = {
    contract: "participation.mn_historical_precinct_display.v1", state_code: "MN",
    county_geoid: "27001", election_date: "2024-11-05", coordinate_system: "EPSG:4326",
    display_only: true, ballots_allocated_by_geometry: false,
    features: [{ properties: { precinct_id: "270010005", reported_total_voters: 0 },
      geometry: { type: "Polygon", coordinates: [] } }],
  };
  const rows = [{ id: "270010005", count: 0 }];
  assert.deepEqual(bindMinnesotaPrecinctLayer(layer, "2024-11-05", "27001", rows), rows);
  assert.throws(() => bindMinnesotaPrecinctLayer(layer, "2022-11-08", "27001", rows), /scope/);
  assert.throws(() => bindMinnesotaPrecinctLayer(layer, "2024-11-05", "27001", [{ ...rows[0], count: 1 }]), /differs/);
  const csv = "state_code,election_date,county_geoid,county,precinct_id,precinct_name,source_status,rate_hold_reason,reported_total_voters,registered_at_7am,same_day_registrations\n"
    + "MN,2024-11-05,27001,Aitkin,270010005,Aitkin,reported,pre_registration_excludes_same_day_registrants,0,10,0";
  assert.throws(() => minnesotaPrecinctFrames(csv, line => line.split(",")), /Incomplete/);
  assert.throws(() => minnesotaPrecinctFrames(csv.replace(",0,10,0", ",,10,0"), line => line.split(",")), /Invalid/);
});

test("Denver map requires exact full 2022 precinct identities, not matching suffixes", () => {
  const asset = new URL("../public/participation-archive-geometry/precinct-CO-Denver-2022.json.gz", import.meta.url);
  const layer = JSON.parse(gunzipSync(readFileSync(asset)));
  const rows = layer.features.map(({ properties }) => ({ precinct: properties.precinct, count: 70, rate: 50 }));
  assert.equal(bindDenverPrecinctMap(layer, [...rows].reverse())[2], rows[2]);
  const wrong = [{ ...rows[0], precinct: `${rows[0].precinct[0] === "7" ? "6" : "7"}${rows[0].precinct.slice(1)}` },
    ...rows.slice(1)];
  assert.throws(() => bindDenverPrecinctMap(layer, wrong), /roster/);
  assert.throws(() => bindDenverPrecinctMap({ ...layer, election_date: "2024-11-05" }, rows), /scope/);
});

test("Colorado precinct statistics retain observed zero and reject missing or incompatible rate decisions", () => {
  const header = "state_code,election_date,county,precinct,registered,active,inactive,ballots_cast,"
    + "qualified_same_report_registration_fraction_pct,rate_hold_reason,source_status,source_url,source_sha256,"
    + "source_bytes,registration_basis";
  const rows = Array.from({ length: 64 }, (_, i) =>
    `CO,2024-11-05,County ${i},${String(i).padStart(10, "0")},10,9,1,`
    + (i ? "0,0," : "11,,ballots_exceed_registered")
    + `,reported,https://co.elstats3.civera.com/api/download_contest/26759_table.csv?split_party=false,${"a".repeat(64)},`
    + "100,Total registration (active plus inactive)");
  const csv = [header, ...rows].join("\n");
  const frame = coloradoPrecinctFrames(csv).get("2024-11-05");
  assert.equal(frame.counties.get("County 0")[0].rate, null);
  assert.equal(frame.counties.get("County 1")[0].rate, 0);
  assert.throws(() => coloradoPrecinctFrames(csv.replace("11,,ballots_exceed_registered", "11,110,")), /differ/);
  assert.throws(() => coloradoPrecinctFrames(csv + "\n" + rows[0]), /repeat/);
  assert.throws(() => coloradoPrecinctFrames([header, ...rows.slice(1)].join("\n")), /Incomplete/);
  const countOnly = [header, ...rows.map((_, i) =>
    `CO,2020-11-03,County ${i},${String(i).padStart(10, "0")},,,,1,,registration_column_party_labeled,`
    + `reported,https://co.elstats3.civera.com/api/download_contest/25358_table.csv?split_party=false,${"a".repeat(64)},100,`
  )].join("\n");
  assert.deepEqual(coloradoPrecinctFrames(countOnly).get("2020-11-03").counties.get("County 0")[0], {
    precinct: "0000000000", count: 1, registered: null, rate: null, hold: "registration_column_party_labeled",
  });
  assert.throws(() => coloradoPrecinctFrames(countOnly.replace(",,,,1,,", ",,,,1,50,")), /differ/);
  const shortfall = [header + ",county_ballot_shortfall", ...rows.map((row, i) => row
    .replace("2024-11-05", "2016-11-08").replace("26759_table", "25362_table")
    .replace("County 0,", "Larimer,").replace("11,,ballots_exceed_registered", "9,,county_ballot_control_disagrees")
    + (i ? "," : ",32"))].join("\n");
  assert.deepEqual(coloradoPrecinctFrames(shortfall).get("2016-11-08").counties.get("Larimer")[0], {
    precinct: "0000000000", count: 9, registered: 10, rate: null, hold: "county_ballot_control_disagrees", shortfall: 32,
  });
  assert.throws(() => coloradoPrecinctFrames(shortfall.replace("),32", "),31")), /differ/);
});

test("the partial Nebraska map preserves a reported zero and leaves unverified counties blank", () => {
  const asset = new URL("../public/participation-archive-geometry/county-NE-2026.geojson.gz", import.meta.url);
  const geometry = JSON.parse(gunzipSync(readFileSync(asset)));
  const header = "county,election_date,disposition,ballots,election_day,early,provisional,source_status,"
    + "report_status,report_clock,index_clock,source_url,source_sha256,source_bytes";
  const data = geometry.features.map(({ properties: { name } }, index) => {
    if (index === 0) return `${name},2026-11-03,reported,0,0,0,0,reported,official,11/11/2026 9:19 AM,`
      + `11/11/2026 10:00 AM,https://countyelectionresults.nebraska.gov/election_files/${encodeURIComponent(name)}`
      + `/2026_General_official_results.pdf,${"a".repeat(64)},100`;
    return `${name},2026-11-03,layout_unqualified,,,,,,,,,,,`;
  });
  const csv = [header, ...data].join("\n");
  const frame = nebraskaCountyReportsFrame(csv);
  assert.equal(frame.rows.has("state"), false);
  const bound = bindOfficialCountyArchive(geometry, frame);
  assert.equal(bound[0].value.count, 0);
  assert.equal(bound.slice(1).every(row => row.value === null), true);
  const fill = count => countyMapFill({ count, rate: null }, true);
  assert.notEqual(fill(0), countyMapFill(bound[1].value, true));
  assert.notEqual(fill(0), fill(1));
  assert.notEqual(fill(999), fill(1_000));
  assert.equal(fill(1_000), fill(4_999));
  assert.notEqual(fill(4_999), fill(5_000));
  assert.equal(countyMapFill({ count: 100, rate: 50 }, false), countyMapFill({ count: 200, rate: 50 }, false));
  assert.throws(() => nebraskaCountyReportsFrame(csv.replace("reported,0,0,0,0", "reported,7,0,0,0")), /provenance/);
  assert.throws(() => nebraskaCountyReportsFrame(csv.replace("layout_unqualified,,,,", "layout_unqualified,,3,,")), /provenance/);
  const replaced = structuredClone(geometry);
  replaced.features[1].properties.name = "Not A Nebraska County";
  assert.throws(() => bindOfficialCountyArchive(replaced, frame), /roster/);
});

test("the 2002 Nebraska map admits only a complementary dated geometry subset", () => {
  const asset = new URL("../public/participation-archive-geometry/county-NE-2002.geojson.gz", import.meta.url);
  const geometry = JSON.parse(gunzipSync(readFileSync(asset)));
  const rows = new Map([["state", { name: "Nebraska", count: 490914 }]]);
  for (const { properties: { name } } of geometry.features) rows.set(`county/${name}`, { name, count: 1 });
  for (const id of geometry.missing_counties) rows.set(`county/${id}`, { name: `Unmapped ${id}`, count: 1 });
  const frame = { code: "NE", date: "2002-11-05", rows };
  assert.throws(() => bindOfficialCountyArchive(geometry, frame), /complete/);
  assert.equal(bindOfficialCountyArchive(geometry, frame, true).length, 75);
  const overlap = structuredClone(geometry);
  overlap.missing_counties[0] = overlap.features[0].properties.key;
  assert.throws(() => bindOfficialCountyArchive(overlap, frame, true), /identity/);
  assert.throws(() => bindOfficialCountyArchive({ ...geometry, reference_date: "2006-01-01" }, frame, true), /complete/);
});

test("the Wyoming county map uses county controls and the freshness of the accepted precinct canvass", () => {
  const frame = wyomingCanvassCountyFrame({
    election_date: "2026-11-03", state_ballots_cast: 12, status: "retained_after_failure",
    source: { url: "https://example.test/official-canvass.pdf" },
    county_controls: [{ county: "Teton", ballots_cast: 12 }],
  });
  assert.equal(frame.status, "retained_after_failure");
  assert.match(frame.url, /official-canvass\.pdf$/);
  assert.equal(frame.rows.get("county/Teton").count, 12);
  assert.equal(frame.rows.get("county/Teton").rate, null);
});

test("the Teton display layer maps a revised count and rejects a replaced or missing precinct ID", () => {
  const layer = JSON.parse(gunzipSync(readFileSync(new URL(
    "../public/participation-archive-geometry/precinct-WY-Teton-2026.json.gz", import.meta.url))));
  const { election_date, state_code, county } = layer;
  const rows = layer.features.map(({ properties }) => ({
    precinct_key: properties.precinct_key, county, election_date, state_code, ballots_cast: 100,
  }));
  const canvass = { election_date, state_code, complete_native_query: rows };
  assert.equal(bindTetonPrecinctMap(layer, canvass).length, 17);
  rows[0].ballots_cast = 0;
  assert.equal(bindTetonPrecinctMap(layer, canvass)[0].ballots_cast, 0);
  rows[0].precinct_key = "99-1";
  assert.throws(() => bindTetonPrecinctMap(layer, canvass), /IDs or polygons/);
  rows.pop();
  assert.throws(() => bindTetonPrecinctMap(layer, canvass), /count inventory/);
});

const catalog = { datasets: {
  "participation-counts-2026": { status: "loaded" },
  "participation-native-bindings-2026": { status: "loaded" },
} };

test("Census release status distinguishes missing links, denied access, and retained tables", () => {
  assert.equal(publishedCpsStatus(undefined), "");
  assert.match(publishedCpsStatus({ status: "reported", rows: 884 }), /are included/);
  assert.match(publishedCpsStatus({ status: "report_not_linked", rows: 0 }), /did not find both/);
  assert.match(publishedCpsStatus({ status: "source_stopped", rows: 0 }), /denied/);
  assert.match(publishedCpsStatus({ status: "retained_after_failure", rows: 884 }), /last verified/);
});

test("Census group maps preserve a published zero but exclude suppressed points and the U.S. benchmark", () => {
  const cohort = { year: "2010", group: "25 to 44", cvap_voted_pct: "0", cvap_voted_moe_pp: "2" };
  const rows = [
    { ...cohort, state_code: "AL" },
    { ...cohort, state_code: "AK", cvap_voted_pct: "", cvap_voted_moe_pp: "" },
    { ...cohort, state_code: "US" },
    { ...cohort, state_code: "AZ", group: "25 to 34" },
  ];
  assert.deepEqual([...cpsMapCells(rows, "2010", "cvap", "25 to 44")], [["AL", { point: "0", moe: "2" }]]);
});

test("legacy statewide totals keep the selected denominator's actual source table", () => {
  const rows = [
    { year: "2004", group: "Total", source_table: "4a", vap_voted_pct: "58.3" },
    { year: "2004", group: "Total", source_table: "4c", cvap_voted_pct: "63.8" },
    { year: "2004", group: "18 to 24", source_table: "4b", vap_voted_pct: "41.9" },
    { year: "2006", group: "Total", source_table: "4b", cvap_voted_pct: "47.8" },
  ];
  assert.deepEqual(cpsRowsForBasis(rows, "vap"), [rows[0], rows[2], rows[3]]);
  assert.deepEqual(cpsRowsForBasis(rows, "cvap"), [rows[1], rows[2], rows[3]]);
});

test("Wyoming current county workbook is count-only and rejects unreconciled or duplicated rows", () => {
  const url = "https://sos.wyo.gov/Elections/Docs/2026/Results/General/2026_Wyoming_General_Results.zip";
  const sha256 = "a".repeat(64);
  const counties = Array.from({ length: 23 }, (_, i) => ({
    county: `County ${String.fromCharCode(65 + i)}`, ballots: i, physical_row: 5 + i,
  }));
  const row = {
    state_code: "WY", year: 2026, status: "reported", cast_ballot_count_qualified: true,
    participation_measure_literal: "Total Ballots Cast", denominator: null,
    source_url: url, source_sha256: sha256, ballots: 253,
    statewide_ballot_parent: {
      contract: "participation.reviewed_statewide_ballot_parent.v1",
      workbook: "2026 General Results Summaries - OFFICIAL.xlsx",
      sheet: "Statewide Total Ballots Cast", cell: "B28", source: { url, sha256 },
      ballots: 253, counties,
    },
  };
  const frame = wyomingCurrentCountyFrame([row]);
  assert.equal(frame.rows.size, 24);
  assert.equal(frame.rows.get("county/County A").count, 0);
  assert([...frame.rows.values()].every(value => value.rate === null && value.registered === null));
  assert.throws(() => wyomingCurrentCountyFrame([row, row]), /Unverified/);
  counties[1].ballots = 2;
  assert.throws(() => wyomingCurrentCountyFrame([row]), /statewide total/);
  counties[1].county = counties[0].county;
  assert.throws(() => wyomingCurrentCountyFrame([row]), /ambiguous/);
});

test("the archive reader does not treat West Virginia voter-history credits as physical ballots", () => {
  const header = "state_code,year,election_date,geography_level,geography,reported_ballots_cast,"
    + "reported_registered_voters,qualified_same_report_registration_fraction_pct,rate_hold_reason,source_status,"
    + "source_url,source_sha256,report_edition,participation_measure,reported_total_voters,registration_basis,"
    + "reported_voter_history_credits";
  const facts = `,100,50,,reported,https://sos.wv.gov/media/655/download?inline,${"a".repeat(64)},`
    + ",voter_history_credits,,Registered voters,50";
  const state = "WV,2008,2008-11-04,state,West Virginia," + facts;
  const county = "WV,2008,2008-11-04,county,Barbour," + facts;
  const [frame] = stateCountyArchiveFrames([header, state, county].join("\n"));
  assert.equal(frame.measure, "voter_history_credits");
  assert.equal(frame.rows.get("county/Barbour").count, 50);
  assert.throws(() => stateCountyArchiveFrames([header, state, county.replace("Barbour,,100", "Barbour,50,100")].join("\n")),
    /report identity differs/);
});

test("election-office archive frames preserve native measures, held rates and last-good metadata", () => {
  const header = "state_code,year,election_date,geography_level,geography,reported_ballots_cast,"
    + "reported_registered_voters,qualified_same_report_registration_fraction_pct,rate_hold_reason,source_status,"
    + "source_url,source_sha256,report_edition,participation_measure,reported_total_voters,registration_basis";
  const source = `retained_after_failure,https://example.test/report.pdf,${"a".repeat(64)},,total_voters,`;
  const statewide = `CA,2024,2024-11-05,state,California,,120,50,,${source}60,"15-day report, not election-day stock"`;
  const county = `CA,2024,2024-11-05,county,Alameda,,100,,printed_disagreement,${source}60,"15-day report, not election-day stock"`;
  const [frame] = stateCountyArchiveFrames([header, statewide, county].join("\n"));
  assert.equal(frame.measure, "total_voters");
  assert.equal(frame.status, "retained_after_failure");
  assert.equal(frame.basis, "15-day report, not election-day stock");
  assert.equal(frame.rows.get("state").count, 60);
  assert.equal(frame.rows.get("county/Alameda").rate, null);
  assert.throws(() => stateCountyArchiveFrames([header, statewide, county, county].join("\n")), /repeated/);
  assert.throws(() => stateCountyArchiveFrames([header, statewide.replace(",50,,", ",51,,"), county].join("\n")), /fraction/);
  assert.throws(() => stateCountyArchiveFrames([header, statewide, county.replace("Alameda,,100", "Alameda,60,100")].join("\n")), /count/);
  assert.throws(() => stateCountyArchiveFrames([header, county].join("\n")), /state or county total/);
  const current = [statewide, ...Array.from({ length: 58 }, (_, i) =>
    county.replace("Alameda", `County ${i + 1}`))].map(row => row.replace("CA,2024,2024-11-05", "CA,2026,2026-11-03"));
  const currentCsv = [header, ...current].join("\n");
  assert.throws(() => stateCountyArchiveFrames(currentCsv), /identity/);
  assert.equal(stateCountyArchiveFrames(currentCsv, { currentCalifornia: true })[0].rows.size, 59);
  assert.throws(() => stateCountyArchiveFrames(
    [header, ...current.slice(0, -1)].join("\n"), { currentCalifornia: true }), /Incomplete California/);
  assert.throws(() => stateCountyArchiveFrames(currentCsv.replaceAll("2026-11-03", "2026-11-04"),
    { currentCalifornia: true }), /identity/);
});

test("the 2026 Nebraska canvass needs its own slot and all 93 counties", () => {
  const layer = JSON.parse(gunzipSync(readFileSync(new URL(
    "../public/participation-archive-geometry/county-NE-2026.geojson.gz", import.meta.url))));
  const header = "state_code,year,election_date,geography_level,geography,reported_ballots_cast,"
    + "reported_registered_voters,qualified_same_report_registration_fraction_pct,rate_hold_reason,source_status,"
    + "source_url,source_sha256,report_edition,participation_measure,reported_total_voters,registration_basis";
  const row = (level, name, scale) => `NE,2026,2026-11-03,${level},${name},,${2 * scale},50,,reported,`
    + `https://example.test/fixture.pdf,${"a".repeat(64)},,total_voters,${scale},Registered voters in same book`;
  const records = [header, row("state", "Nebraska", 93),
    ...layer.features.map(({ properties }) => row("county", properties.name, 1))];
  const csv = records.join("\n");
  assert.throws(() => stateCountyArchiveFrames(csv), /identity/);
  assert.throws(() => stateCountyArchiveFrames(csv, { currentCalifornia: true }), /identity/);
  assert.throws(() => stateCountyArchiveFrames(records.slice(0, -1).join("\n"),
    { currentNebraska: true }), /Incomplete Nebraska/);
  const [frame] = stateCountyArchiveFrames(csv, { currentNebraska: true });
  assert.equal(bindOfficialCountyArchive(layer, frame).length, 93);
});

test("pre-2015 Shannon County uses the dated code without changing the source row", () => {
  const feature = { type: "Feature", properties: { key: "46113", name: "Shannon", state_code: "SD",
    boundary_year: 2014, level: "county" }, geometry: { type: "Polygon" } };
  const collection = { type: "FeatureCollection", features: [feature] };
  const row = { year: 2014, code: "SD", fips: "46102", name: "Oglala Lakota County",
    count: 2793, registered: 8457, rate: 33.03 };
  const reference = { year: 2014, state_code: "SD", geography: { key: "46113", level: "county" },
    jurisdiction_id: "4611300000", jurisdiction: "Shannon County", total_participation: 2793, registered: 8457 };
  const bind = (rows = [row], prior = [reference]) => bindHistoricalCountyMap(collection, prior, rows, "SD", 2014)[0];
  assert.equal(bind().value, row);
  assert.equal(bind().method, "sd_shannon_county_pre_2015_code");
  assert.equal(bind([row], [{ ...reference, registered: 8000 }]).value, null);
  assert.equal(bind([row], [{ ...reference, total_participation: 2794 }]).value, null);
  assert.throws(() => bind([row, { ...row, fips: "46113", name: "Shannon County" }]), /Ambiguous/);
});

test("Hawaii history retains a disputed statewide count without plotting a rate", () => {
  const header = "state_code,year,geography,reported_voter_turnout,reported_registered_voters,"
    + "qualified_turnout_percent,rate_hold_reason,source_status,source_url";
  const source = "https://elections.hawaii.gov/resources/registration-voter-turnout-statistics/";
  const areas = ["Statewide", "County of Hawaii", "County of Maui", "County of Kauai", "City & County of Honolulu"];
  const rows = Array.from({ length: 34 }, (_, i) => i ? 1958 + i * 2 : 1959)
    .flatMap(year => areas.map(area => `HI,${year},${area},` + (year === 2022 && area === "Statewide"
      ? "2002,4000,,county_totals_do_not_reconcile" : "500,1000,50.000000,") + `,reported,${source}`));
  const csv = [header, ...rows].join("\n");
  const frames = hawaiiHistoryFrames(csv);
  assert.equal(frames.length, 170);
  const held = frames.find(row => row.code === "Statewide" && row.date === "2022").rows.get("state");
  assert.equal(held.count, 2002);
  assert.equal(held.rate, null);
  assert.throws(() => hawaiiHistoryFrames(csv.replace("50.000000", "49.000000")), /Invalid Hawaii/);
});

test("Kansas study validates an entire statewide series and its registration fraction", () => {
  const header = "state_code,year,election_date,reported_general_election_turnout,reported_registration,"
    + "turnout_per_reported_registration,source_status,source_url";
  const source = "https://www.sos.ks.gov/elections/10elec/2010_Future_of_Kansas_Elections_report.pdf";
  const rows = Array.from({ length: 7 }, (_, index) => {
    const year = 2008 - 2 * index;
    return `KS,${year},${year}-11-04,750,1000,0.75000000,reported,${source}`;
  });
  const csv = [header, ...rows].join("\n");
  assert.equal(kansasStudyFrames(csv).at(-1).rows.get("state").rate, 75);
  assert.throws(() => kansasStudyFrames(csv.replace("0.75000000", "0.74000000")), /Invalid Kansas/);
  assert.throws(() => kansasStudyFrames([header, ...rows.slice(1)].join("\n")), /Incomplete/);
});

test("Virginia turnout keeps a county and independent city with the same name separate", () => {
  const header = "state_code,year,election_date,geography_level,geography,reported_ballots_cast,"
    + "reported_registered_voters,qualified_same_report_registration_fraction_pct,rate_hold_reason,source_status,"
    + "source_url,source_sha256,report_edition,participation_measure,reported_total_voters,registration_basis";
  const row = (level, name, count) => `VA,2022,2022-11-08,${level},${name},${count},,,registration_not_in_report,`
    + `reported,https://example.test/turnout.html,${"a".repeat(64)},2022-12-06T02:16:00,ballots_cast,,`;
  const records = [header, row("state", "Virginia", 134)];
  const features = [];
  for (const [level, suffix, size, offset] of [["county", "COUNTY", 95, 1], ["county_equivalent", "CITY", 38, 500]]) {
    for (let i = 0; i < size; i++) {
      const name = i === 0 ? "Fairfax" : `Area ${i}`;
      records.push(row(level, `${name.toUpperCase()} ${suffix}`, offset === 500 && i === 0 ? 2 : 1));
      features.push({ type: "Feature", properties: { key: `51${String(i + offset).padStart(3, "0")}`,
        name, boundary_year: 2022, state_code: "VA", level: "county" }, geometry: { type: "Polygon" } });
    }
  }
  const [frame] = stateCountyArchiveFrames(records.join("\n"));
  const joined = bindOfficialCountyArchive({ type: "FeatureCollection", features }, frame);
  assert.equal(joined.length, 133);
  assert.deepEqual(joined.filter(({ feature }) => feature.properties.name === "Fairfax")
    .map(({ value }) => [value.name, value.count, value.rate]), [["FAIRFAX COUNTY", 1, null], ["FAIRFAX CITY", 2, null]]);
  assert.throws(() => stateCountyArchiveFrames(records.slice(0, -1).join("\n")), /Incomplete/);
  const native = [header, ...records.slice(2).map(row => row.replace("VA,2022,2022-11-08", "VA,2024,2024-11-05")
    .replace("registration_not_in_report", "native_registration_frame_not_certified_turnout_denominator"))];
  const readNative = lines => stateCountyArchiveFrames(lines.join("\n"), { virginiaNative: true });
  const [localityFrame] = readNative(native);
  assert.equal(localityFrame.rows.has("state"), false);
  const nativeFeatures = features.map(feature => ({ ...feature,
    properties: { ...feature.properties, boundary_year: 2024 } }));
  assert.equal(bindOfficialCountyArchive({ type: "FeatureCollection", features: nativeFeatures }, localityFrame).length, 133);
  assert.throws(() => readNative(native.slice(0, -1)), /Incomplete/);
  assert.throws(() => stateCountyArchiveFrames(native.join("\n")), /identity/);
});

test("official county maps require a complete, unique roster on the exact dated layer", () => {
  const rows = new Map([["state", { name: "New Jersey" }]]);
  const features = Array.from({ length: 21 }, (_, i) => {
    const name = `Area ${i + 1}`;
    rows.set(`county/${name}`, { name, count: i, rate: i ? null : 0 });
    return { type: "Feature", properties: { key: `34${String(i * 2 + 1).padStart(3, "0")}`,
      name, boundary_year: 2024, state_code: "NJ", level: "county" }, geometry: { type: "Polygon" } };
  });
  const collection = { type: "FeatureCollection", features };
  const frame = { code: "NJ", date: "2024-11-05", rows };
  assert.deepEqual(bindOfficialCountyArchive(collection, frame).map(({ value }) => value.count),
    Array.from({ length: 21 }, (_, i) => i));
  assert.throws(() => bindOfficialCountyArchive(collection, { ...frame, date: "2022-11-08" }), /identity/);
  assert.throws(() => bindOfficialCountyArchive({ ...collection, features: features.slice(1) }, frame), /complete/);
  const wrong = { ...features[0], properties: { ...features[0].properties, name: "Unrelated county" } };
  assert.throws(() => bindOfficialCountyArchive({ ...collection, features: [wrong, ...features.slice(1)] }, frame), /roster/);
});
const counts = { states: { MN: { views: {
  available: { counties: 87, precincts: 4105, holds: 0,
    dispositions: { counties: { reported: 87, unknown: 0, withheld: 0, qualified_fractions: 73 } } },
} } } };

test("historical county downloads are bound to the exact runtime and separate from 2026", () => {
  const path = "participation/eac-county-year-decisions.csv.gz";
  const base_url = "https://example.org/runtime";
  const url = `${base_url}/${path}`;
  const series = { contract: "participation.eac_county_counted_ballot_reconciliation.v1",
    historical_not_2026: true, no_county_boundary_equivalence_inferred: true,
    direct_count_rows: 8, county_rows: 10, downloads: { [path]: { path, url, bytes: 42, sha256: "a".repeat(64) } } };
  const sources = { base_url, historical_eac_counties: series };
  assert.deepEqual(historicalCountyDownload(sources), { url, counts: 8, rows: 10 });
  assert.equal(historicalCountyDownload({ ...sources, base_url: "https://example.org/older" }), null);
  assert.equal(historicalCountyDownload({ ...sources,
    historical_eac_counties: { ...series, historical_not_2026: false } }), null);
});

const historicalCsv = [
  "state,year,county_fips,county_name,county_registered,county_turnout,county_highest_office_flag,direct_registered,direct_turnout,direct_highest_office_flag,decision,direct_reported_turnout,same_report_registration_fraction_pct",
  'AL,2024,01001,"COUNTY, ""A""",25,0,0,25,0,0,reconciled_direct_county_turnout,0,0.0',
  "AL,2022,01001,A COUNTY,25,17,0,26,17,0,reconciled_direct_county_turnout,17,",
  "AL,2022,01003,B COUNTY,25,17,1,25,17,1,highest_office_source_reported,,",
  "AK,2022,02000,ALASKA,25,17,0,25,17,0,not_a_county_scope,,",
].join("\n");
const historicalSeries = { county_rows: 4, direct_count_rows: 2, same_report_registration_fraction_rows: 1,
  election_years: [2022, 2024], decisions: {
    reconciled_direct_county_turnout: 2, highest_office_source_reported: 1, not_a_county_scope: 1,
  } };

test("historical county table preserves literal identities, true zeros, missing rates and held counts", () => {
  const rows = historicalCountyRows(historicalCsv, historicalSeries);
  assert.deepEqual(rows[0], { code: "AL", year: 2024, fips: "01001", name: 'COUNTY, "A"',
    registered: 25, count: 0, rate: 0, decision: "reconciled_direct_county_turnout" });
  assert.deepEqual(rows.slice(1).map(row => [row.count, row.registered, row.rate]),
    [[17, null, null], [null, null, null], [null, null, null]]);
  assert.throws(() => historicalCountyRows(historicalCsv.replace(",2024,", ",2026,"), historicalSeries), /identity/);
  assert.throws(() => historicalCountyRows(historicalCsv.replace("highest_office_source_reported,,",
    "highest_office_source_reported,17,"), historicalSeries), /decision/);
  assert.throws(() => historicalCountyRows(historicalCsv.replace(",0,0.0", ",0,0.1"), historicalSeries), /fraction/);
  assert.throws(() => historicalCountyRows(historicalCsv, { ...historicalSeries, direct_count_rows: 3 }), /summary/);
});

test("same-year maps require reviewed native county identities and preserve eligible zero and count-only rows", () => {
  const feature = key => ({ type: "Feature", properties: { key, state_code: "AL",
    boundary_year: 2024, level: "county" }, geometry: { type: "Polygon" } });
  const features = ["01001", "01003", "01005", "01007", "01009"].map(feature);
  const collection = { type: "FeatureCollection", features };
  const row = (fips, name, count, rate) => ({ code: "AL", year: 2024, fips, name, count, rate });
  const rows = [row("01001", "A County", 0, 0), row("01003", "B", 15, null),
    row("01005", "C", 17, 50), row("01007", "D", 21, 60), row("01009", "E", 22, 65)];
  const prior = (key, jurisdiction, count, extra) => ({ year: 2024, state_code: "AL",
    geography: { key, level: "county" }, jurisdiction_id: `${key}00000`,
    total_participation: count, jurisdiction, ...extra });
  const references = [prior("01001", "A", 0), prior("01003", "B County", 15),
    prior("01005", "Wrong name", 17), prior("01007", "D", 20),
    prior("01009", "E", 22, { supplemental_unit: true })];
  assert.deepEqual(bindHistoricalCountyMap(collection, references, rows, "AL", 2024)
    .map(({ value }) => value), [rows[0], rows[1], null, null, null]);
  assert.equal(bindHistoricalCountyMap(collection, [{ ...references[0], year: 2022 }],
    rows, "AL", 2024)[0].value, null);
  assert.throws(() => bindHistoricalCountyMap(collection, [...references, references[0]], rows,
    "AL", 2024), /Ambiguous/);
  assert.throws(() => bindHistoricalCountyMap(collection, references, [...rows, rows[0]],
    "AL", 2024), /Ambiguous/);
  assert.throws(() => bindHistoricalCountyMap(collection, references, rows, "AL", 2022), /identity/);
});

test("2008 Ohio maps a five-digit county only with explicit matching ballot evidence", () => {
  const collection = { type: "FeatureCollection", features: [{
    type: "Feature", properties: { key: "39093", name: "Lorain", state_code: "OH",
      boundary_year: 2008, level: "county" }, geometry: { type: "Polygon" },
  }] };
  const row = { code: "OH", year: 2008, fips: "39093", name: "LORAIN COUNTY",
    count: 148218, registered: 204400, rate: 72.51 };
  const source = { year: 2008, state_code: "OH", jurisdiction_id: "39093", jurisdiction: "LORAIN",
    total_participation: 148218, registered: 204400,
    source_url: "https://www.eac.gov/sites/default/files/eac_assets/1/6/2008%20eavs%20xls%20august%2011%202010.zip",
    source_details: { f2: "Number of ballots counted at precincts and/or at a central location "
      + "(including UOCAVA and other absentee or early vote ballots)" } };
  const bind = (sources, value = row) => bindHistoricalCountyMap(collection, sources, [value], "OH", 2008)[0];
  assert.equal(bind([source]).value, row);
  assert.equal(bind([source]).method, "ohio_2008_native_counted_ballot_report");
  assert.equal(bind([{ ...source, source_details: { f2: "Number of voters generated after \"vote history\" has been added." } }]).value, null);
  assert.equal(bind([{ ...source, source_details: { ...source.source_details, f1_comments: "Includes rejected ballots." } }]).value, null);
  assert.equal(bind([{ ...source, source_details: { ...source.source_details, f2_comments: "Includes rejected ballots." } }]).value, null);
  assert.equal(bind([{ ...source, registered: 204399 }]).value, null);
  assert.equal(bind([{ ...source, total_participation: 148219 }]).value, null);
  assert.equal(bind([{ ...source, source_url: "https://example.test/unreviewed" }]).value, null);
  assert.throws(() => bind([source, source]), /Ambiguous/);
});

test("historical county reader verifies the complete gzip and rejects changed or unbound sources", async t => {
  const path = "participation/eac-county-year-decisions.csv.gz", base_url = "https://example.test/accepted";
  const url = `${base_url}/${path}`, original = gzipSync(historicalCsv);
  const series = { ...historicalSeries, contract: "participation.eac_county_counted_ballot_reconciliation.v1",
    historical_not_2026: true, no_county_boundary_equivalence_inferred: true, held_rows_are_not_zero: true,
    source_registered_voter_fraction_not_populational_turnout: true, downloads: { [path]: {
      path, url, bytes: original.length, sha256: createHash("sha256").update(original).digest("hex"),
    } } };
  const sources = { base_url, historical_eac_counties: series };
  const fetch = t.mock.method(globalThis, "fetch", async target => {
    assert.equal(target, url);
    return new Response(original);
  });
  assert.equal((await loadHistoricalCountyRows(sources)).length, 4);
  await assert.rejects(loadHistoricalCountyRows({ ...sources, base_url: "https://example.test/different" }), /qualified/);
  assert.equal(fetch.mock.callCount(), 1);
  const changed = Buffer.from(original);
  changed[10] ^= 1;
  fetch.mock.mockImplementation(async () => new Response(changed));
  await assert.rejects(loadHistoricalCountyRows(sources), /checksum/);
});

for (const [filename, download] of [
  ["participation-indiana-general-turnout-history", indianaTurnoutDownload],
  ["participation-state-county-turnout-archives", stateCountyArchivesDownload],
]) test(`${filename} is linked only to the accepted release`, () => {
  const path = `release/${filename}.csv.gz`;
  const base_url = "https://example.test/accepted";
  const file = { path, url: `${base_url}/${path}`, bytes: 5800, sha256: "a".repeat(64),
    compression: "gzip", media_type: "text/csv" };
  const sources = { base_url, supported_release: { downloads: { [path]: file } } };
  assert.equal(download(sources), file.url);
  assert.equal(download({ base_url }), null);
  assert.equal(download({ ...sources, base_url: "https://example.test/other" }), null);
  assert.equal(download({ ...sources, base_url: null }), null);
});

test("North Carolina keeps both archive editions and withholds an incompatible fraction", () => {
  const header = "state_code,election_date,geography_level,native_age_label,voters_with_history,"
    + "active_and_inactive_registered_voters,source_defined_rate_pct,history_edition,registration_edition,status";
  const ages = ["Age 18 - 25", "Age 26 - 40", "Age 41 - 65", "Age Over 66"];
  const lines = ages.map((age, i) => `NC,2026-11-03,state,${age},${i ? "40,100,40.0" : "101,100,"},`
    + "2026-12-01,2026-11-03,retained_after_failure");
  const parse = lines => northCarolinaAgeRows([header, ...lines].join("\n"));
  const rows = parse(lines);
  assert.deepEqual(rows[0], { age: ages[0], voted: 101, registered: 100, fraction: null,
    historyEdition: "2026-12-01", registrationEdition: "2026-11-03", status: "retained_after_failure" });
  assert.equal(rows[1].fraction, 40);
  assert.throws(() => parse([lines[0].replace(",101,100,,", ",101,100,100,"), ...lines.slice(1)]), /Invalid/);
  assert.throws(() => parse([lines[0].replace("2026-12-01", "2026-12-02"), ...lines.slice(1)]), /Mixed/);
  assert.throws(() => parse(lines.slice(0, -1)), /Incomplete/);
});

test("administrative audit preserves zero records and rejects incomplete or inconsistent coverage", () => {
  const fields = ["state_code", "year", ...["statewide", "county_or_equivalent", "precinct"]
    .flatMap(scope => ["count", "rate"].map(kind => `${scope}_election_participation_${kind}_records`))];
  const rows = countStates.map(code => `${code},2026,1,0,2,1,0,0`);
  const parse = lines => administrativeRows([fields.join(","), ...lines].join("\n"));
  assert.deepEqual(parse(rows)[0], { code: countStates[0], counts: [1, 0, 2, 1, null, null, null, null, 0, 0] });
  assert.throws(() => parse(rows.slice(1)), /Incomplete administrative coverage/);
  assert.throws(() => parse([rows[1], ...rows.slice(1)]), /Invalid jurisdiction/);
  assert.throws(() => parse([rows[0].replace(",2,1,", ",0,1,"), ...rows.slice(1)]), /rates exceed/);
});

test("administrative audit separates municipal and reporting-unit metrics from strict precincts", () => {
  const fields = ["state_code", "year", ...["statewide", "county_or_equivalent", "precinct", "reporting_unit", "municipality"]
    .flatMap(scope => ["count", "rate"].map(kind => `${scope}_election_participation_${kind}_records`))];
  const rows = countStates.map(code => `${code},2026,1,0,2,1,0,0,37,0,7,0`);
  assert.deepEqual(administrativeRows([fields.join(","), ...rows].join("\n"))[0],
    { code: countStates[0], counts: [1, 0, 2, 1, 7, 0, 37, 0, 0, 0] });
  assert.throws(() => administrativeRows([fields.slice(0, -1).join(","),
    ...rows.map(row => row.slice(0, -2))].join("\n")), /Missing or repeated/);
  assert.throws(() => administrativeRows([fields.join(","),
    ...rows.map(row => row.replace(",37,0,", ",0,1,"))].join("\n")), /rates exceed/);
});
test("coverage uses the actual selected frame, not an old audit badge or source-row sum", () => {
  const rows = coverageRows(catalog, counts, {}, { year: 2026, mode: "available", level: "county" });
  assert.equal(rows.length, 51);
  const mn = rows.find(row => row.code === "MN");
  assert.equal(mn.source_rows, 87); assert.equal(mn.reported, 87); assert.equal(mn.fractions, 73);
  assert.equal(rows.find(row => row.code === "AK").status, "Missing for this scope");
  const early = coverageRows(catalog, counts, {}, { year: 2026, mode: "mail_returned", level: "precinct" });
  assert.equal(early.find(row => row.code === "MN").status, "Missing for this scope");
});
test("awaiting and rejected datasets are not disguised as ordinary geographic missingness", () => {
  const scope = { year: 2026, mode: "available", level: "county" };
  assert.equal(coverageRows({ datasets: {} }, null, null, scope)[0].status, "Awaiting publication");
  assert.equal(coverageRows({ datasets: {} }, null, null, scope)[0].reported, null);
  assert.equal(coverageRows(catalog, counts, {}, scope,
    { "participation-counts-2026": "checksum differs" })[0].status, "Rejected by reader");
  assert.deepEqual(coverageRows(catalog, counts, {}, { ...scope, year: 2024 }), []);
});
test("table-only reporting units are loaded without inventing geographic references or rates", () => {
  const native = { reporting_tables: { AZ: { rows: 1763, eligible_modes: ["official"],
    coverage: { source_rows: 1763, reported: 1762, unknown: 1, withheld: 0, fractions: 0 } } } };
  const row = coverageRows(catalog, {}, native, { year: 2026, mode: "official", level: "precinct" })
    .find(row => row.code === "AZ");
  assert.equal(row.status, "Loaded (table only)");
  assert.equal(row.source_rows, 1763);
  assert.equal(row.reference_units, 0);
  assert.equal(row.unknown, 1);
  assert.equal(row.fractions, 0);
});

test("coverage links the validated scope package and clears rejected, historical or unsafe links", async () => {
  const source = readFileSync(new URL("../public/scripts/participation-coverage.js", import.meta.url), "utf8");
  const start = source.indexOf("export function installCoverage(");
  assert(start >= 0);
  const element = tag => ({
    tag, children: [], dataset: {},
    set textContent(value) { this.text = value; this.children = []; },
    get textContent() { return this.text; },
    append(...children) { this.children.push(...children); },
    replaceChildren(...children) { this.children = children; },
  });
  const caption = element("p"), body = element("tbody");
  const host = { dataset: {}, querySelector: selector =>
    selector === "tbody" ? body : caption };
  const pointers = {
    counts: { version: "counts-version", complete_download: { url: "https://example.org/complete-counts.zip" } },
    native: { version: "native-version", complete_download: { url: "https://example.org/complete-native.zip" } },
  };
  const rejected = new Set();
  const install = runInNewContext(`(${source.slice(start + "export ".length)})`, {
    document: { createElement: element }, coverageRows,
    installAdministrativeCoverage: () => () => {},
    loadDatasetCatalog: async () => catalog,
    loadCountIndex: async () => {
      if (rejected.has("counts")) throw new Error("counts checksum differs");
      return { index: counts, entry: pointers.counts };
    },
    loadNativeIndex: async () => {
      if (rejected.has("native")) throw new Error("native checksum differs");
      return { index: {}, entry: pointers.native };
    },
  });
  const coverage = install(host);
  const scope = { year: 2026, mode: "available", level: "county" };
  const links = () => caption.children.filter(node => node?.tag === "a");
  await coverage.setScope(scope);
  assert.equal(links().length, 1);
  assert.equal(links()[0].href, pointers.counts.complete_download.url);
  assert.equal(links()[0].textContent, "Complete numerical inputs, queries and results");
  await coverage.setScope({ ...scope, level: "precinct" });
  assert.equal(links()[0].href, pointers.native.complete_download.url);
  for (const [level, dataset] of [["county", "counts"], ["precinct", "native"]]) {
    rejected.add(dataset);
    await coverage.setScope({ ...scope, level });
    assert.equal(links().length, 0);
    rejected.clear();
  }
  await coverage.setScope(scope);
  await coverage.setScope({ ...scope, year: 2024 });
  assert.equal(links().length, 0);
  for (const url of [null, undefined, "javascript:alert(1)", "http://example.org/complete.zip"]) {
    pointers.counts.complete_download.url = url;
    await coverage.setScope(scope);
    assert.equal(links().length, 0);
  }
});
