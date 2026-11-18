import assert from "node:assert/strict";
import { createHash, webcrypto } from "node:crypto";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import test from "node:test";
import { bindDistrictResults, districtFill, districtValue, fetchDistrictGeometry,
  validateDistrictGeometry } from "../public/scripts/participation-house-districts.js";

globalThis.crypto ||= webcrypto;
const body = readFileSync(new URL("./fixtures/district-paths.json.gz", import.meta.url));
const decoded = gunzipSync(body);
const geometry = JSON.parse(decoded);
const original = JSON.parse(gunzipSync(readFileSync(new URL("./fixtures/district-congress.json.gz", import.meta.url))));
const splitOriginal = JSON.parse(gunzipSync(readFileSync(
  new URL("./fixtures/district-congress-split.json.gz", import.meta.url))));
const clone = value => structuredClone(value);
const sha = value => createHash("sha256").update(value).digest("hex");
const receipt = {
  contract:geometry.contract,
  url:`https://raw.githubusercontent.com/hanshanley/voter-participation/${"a".repeat(40)}/data/congressional-geometry/20261118-02/district-paths.json.gz`,
  bytes:body.length,sha256:sha(body),decoded_bytes:decoded.length,decoded_sha256:sha(decoded),
};

function revise(delta) {
  const raw = clone(original), race = raw.races.find(row => row.chamber === "house" && row.qualified_comparison);
  raw.candidates.find(row => row.id === race.id && row.party_group === "D").votes += delta;
  const change = row => {
    row.D += delta;
    row.D_minus_R_margin_pp = 100*(row.D-row.R)/(row.D+row.R);
    row.D_two_party_share_pct = 100*row.D/(row.D+row.R);
    row.R_two_party_share_pct = 100*row.R/(row.D+row.R);
    row.raw_recorded_margin_change_pp = row.D_minus_R_margin_pp-row.previous.D_minus_R_margin_pp;
    row.raw_recorded_D_share_change_pp = row.raw_recorded_margin_change_pp/2;
    row.qualified_margin_change_pp = row.qualified_comparison ? row.raw_recorded_margin_change_pp : null;
  };
  change(race);change(raw.reviewed_races.find(row=>row.id===race.id));
  const state = raw.house_states.find(row=>row.state_code===race.state_code);
  state.current.D += delta;
  state.current.D_minus_R_margin_pp = 100*(state.current.D-state.current.R)/(state.current.D+state.current.R);
  state.raw_recorded_margin_change_pp = state.current.D_minus_R_margin_pp-state.previous.D_minus_R_margin_pp;
  state.raw_recorded_D_share_change_pp = state.raw_recorded_margin_change_pp/2;
  state.qualified_margin_change_pp = state.qualified_comparison ? state.raw_recorded_margin_change_pp : null;
  return {raw,id:race.id};
}

test("all 435 native outlines join once; all exported qualifications and counts survive",()=>{
  const before = JSON.stringify(original), map = bindDistrictResults(geometry,original);
  assert.equal(map.length,435);
  assert.equal(map.filter(item=>item.row.qualified_comparison).length,259);
  assert.equal(new Set(map.map(item=>item.path.geoid)).size,435);
  assert.equal(map.filter(item=>item.path.district_code==="00").length,6);
  for (const {row,path} of map) {
    assert.equal(path.district,row.baseline.district);
    assert.equal(districtValue(row,"margin"),row.qualified_margin_change_pp);
    assert.equal(districtValue(row,"democratic_two_party_share"),
      row.qualified_comparison ? row.qualified_margin_change_pp/2 : null);
    const literal = original.races.find(item=>item.id===row.id);
    for (const party of ["D","R","O","U"]) assert.equal(row[party],literal[party]);
  }
  assert.equal(JSON.stringify(original),before);
});

test("reviewed exact split fragments admit both Colorado districts without dropping the other 433",()=>{
  const before = JSON.stringify(splitOriginal), map = bindDistrictResults(geometry,splitOriginal);
  assert.equal(map.length,435);
  assert.equal(map.filter(item=>item.row.qualified_comparison).length,261);
  assert.equal(map.filter(item=>!item.row.qualified_comparison).length,174);
  for (const district of ["CO-07","CO-08"]) {
    const {row} = map.find(item=>item.path.district===district);
    assert(row.qualified_comparison);
    assert.equal(districtValue(row,"margin"),row.raw_recorded_margin_change_pp);
    assert.equal(districtValue(row,"democratic_two_party_share"),row.raw_recorded_margin_change_pp/2);
  }
  for (const {row} of map) {
    const native = splitOriginal.races.find(item=>item.id===row.id);
    for (const party of ["D","R","O","U"]) assert.equal(row[party],native[party]);
  }
  assert.equal(JSON.stringify(splitOriginal),before);
});

test("split qualification still requires its exact reviewed policy, district, block and memberships",()=>{
  for (const mutate of [
    b=>{b.split_geometry_review_version="unreviewed";},
    b=>{b.split_geometry_review_sha256="0".repeat(64);},
    b=>{b.affected_split_blocks=["080010096072001"];},
    b=>{b.previous_membership.sha256="0".repeat(64);},
    b=>{b.method="identical_split_blocks_by_number";},
    b=>{b.historical_votes_allocated=true;},
    b=>{b.legal_boundary_certification=true;},
  ]) {
    const raw=clone(splitOriginal);
    for (const rows of [raw.races,raw.reviewed_races]) {
      mutate(rows.find(row=>row.baseline?.district==="CO-07").baseline.boundary_eligibility);
    }
    assert.throws(()=>bindDistrictResults(geometry,raw),/boundary/);
  }
  const raw=clone(splitOriginal);
  const approved=raw.races.find(row=>row.baseline?.district==="CO-07").baseline.boundary_eligibility;
  for (const rows of [raw.races,raw.reviewed_races]) {
    const boundary=rows.find(row=>row.baseline?.district==="CO-06").baseline.boundary_eligibility;
    for (const field of ["method","split_geometry_review_version","split_geometry_review_sha256",
      "affected_split_blocks"]) boundary[field]=clone(approved[field]);
  }
  assert.throws(()=>bindDistrictResults(geometry,raw),/boundary/);
});

test("north-up SVG display places northern districts above southern districts",()=>{
  const paths = new Map(geometry.paths.map(row=>[row.district,row]));
  assert(paths.get("WA-04").point[1] < paths.get("FL-20").point[1]);
  assert(paths.get("CA-01").point[1] < paths.get("CA-52").point[1]);
});

test("upward and downward complete-vector corrections propagate without changing holds or other districts",()=>{
  const before = bindDistrictResults(geometry,original);
  for (const delta of [7,-13]) {
    const {raw,id} = revise(delta), after = bindDistrictResults(geometry,raw);
    assert.equal(after.filter(item=>item.row.qualified_comparison).length,259);
    const changes = after.filter((item,index)=>districtValue(item.row,"margin")!==districtValue(before[index].row,"margin"));
    assert.equal(changes.length,1);assert.equal(changes[0].row.id,id);
    assert.equal(changes[0].row.D,before.find(item=>item.row.id===id).row.D+delta);
    assert.equal(Math.sign(districtValue(changes[0].row,"margin")
      -districtValue(before.find(item=>item.row.id===id).row,"margin")),Math.sign(delta));
    for (let i=0;i<after.length;i++) if (after[i].row.id!==id) assert.deepEqual(after[i],before[i]);
  }
  assert.deepEqual(bindDistrictResults(geometry,original),before);
});

test("changed plans, unresolved split blocks and RCV holds never become a zero or colored swing",()=>{
  const map = bindDistrictResults(geometry,original);
  const held = map.filter(item=>!item.row.qualified_comparison);
  assert.equal(held.length,176);
  assert(held.some(item=>item.row.comparison_holds.some(reason=>reason.includes("split_block"))));
  assert(held.some(item=>item.path.state_code==="ME"));
  assert(held.some(item=>item.path.state_code==="AK"));
  for (const {row} of held) {
    assert.equal(districtValue(row,"margin"),null);
    assert.notEqual(districtFill(null,20),districtFill(0,20));
  }
  assert.notEqual(districtFill(10,20),districtFill(-10,20));
  assert.equal(districtFill(0,20),"#f3f1ea");
});

test("wrong current vintage, CRS, source pins, duplicate and unassigned-as-seat mutations refuse",()=>{
  const mutations = [
    value=>{value.congress=119;},value=>{value.native_crs="EPSG:4326";},
    value=>{value.display_method="nad83_albers_display_only_topology_preserving_0.25_viewbox_units";},
    value=>{value.sources.current.MO.file="tl_2025_29_cd119.zip";},
    value=>{value.sources.current.CA.sha256="missing";},
    value=>{value.paths[1]=clone(value.paths[0]);},
    value=>{value.paths.find(row=>row.unassigned_area).unassigned_area=false;},
    value=>{value.paths[0].d="M0,0<script>Z";},
    value=>{value.paths[0].geoid="1";},
    value=>{value.paths[0].bounds[0]=NaN;},
  ];
  for (const mutate of mutations) {
    const value=clone(geometry);mutate(value);assert.throws(()=>validateDistrictGeometry(value));
  }
});

test("candidate, boundary and seat mismatches refuse rather than silently dropping a district",()=>{
  for (const mutate of [
    raw=>{raw.candidates[0].votes+=1;},
    raw=>{raw.races[0].baseline.boundary_eligibility.state_fips="01";},
    raw=>{raw.races.splice(raw.races.findIndex(row=>row.chamber==="house"),1);},
  ]) {
    const raw=clone(original);mutate(raw);assert.throws(()=>bindDistrictResults(geometry,raw));
  }
});

test("geometry fetch verifies compressed and decoded bytes; actual corruption and stale receipts refuse",async()=>{
  const fetcher=async()=>new Response(body);
  assert.equal((await fetchDistrictGeometry(receipt,fetcher)).voting_districts,435);
  const corrupt=Buffer.from(body);corrupt[40]^=1;
  await assert.rejects(fetchDistrictGeometry(receipt,async()=>new Response(corrupt)),/checksum/);
  await assert.rejects(fetchDistrictGeometry({...receipt,decoded_sha256:"0".repeat(64)},fetcher),/checksum/);
  await assert.rejects(fetchDistrictGeometry({...receipt,url:receipt.url.replace("district-paths","old-paths")},fetcher),/receipt/);
  await assert.rejects(fetchDistrictGeometry(receipt,async()=>new Response("",{status:503})),/HTTP 503/);
});
