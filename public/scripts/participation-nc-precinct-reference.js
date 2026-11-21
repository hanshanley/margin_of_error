import { checkedCountyBody } from "./participation-historical-county-map.js";

const root = new URL("../participation-archive-geometry/nc-precinct-reference/", import.meta.url);
const references = {
  "2012-11-06": [1477666, "abe8671893c2cda6a9bcdea76667bf823d679e07ea5e200c2bd5a893e98bb9d7",
    "c4230e764352a0da430268ea216657103ba5a7de323f5eb02d141f2f7075b485", 2048, 2798, 4532494, 3153860],
  "2014-11-04": [1767092, "85479a86552cbabc18c26fcf81cd95d6fd8e533242fafe3381424353806c8227",
    "01a85ac3f6a72ef4e15acf00a8a3f70c5278b9f241ee00883043a45ce49a9368", 2658, 2746, 2937828, 2835602],
  "2016-11-08": [1795341, "12f74a08331995950de4868bac63e21ec59665e6964205fd3f0e96d790900d18",
    "f3df01e36c89e58cb87fe95b58f243f8f0c216963a7168580fa7a990f8def2e8", 2698, 2704, 4768079, 4756227],
  "2018-11-06": [1794635, "4f285850778f29473e28ab0e674b6fdd84eff8394b34665111163d1e92ad052c",
    "f0877a95e84265a38cee25c5481ed5a3b989b91b276fbbe18273733a3f43731b", 2698, 2706, 3754102, 3733928],
  "2020-11-03": [1877797, "7a5dd2000aaab7af1f7651f0bd7d2e674f950ad13f91c7825d068f44cc3a06f4",
    "6012132cbec3d641003c6ef93b76eca98a4db540d7f46dc8ff2caaabe0ac8b40", 2645, 2662, 5544018, 5511349],
  "2022-11-08": [1774223, "203dff804ae805d34469ff2a3e7cd86e9dde1fb118089feffdc3a4f43ecafcb3",
    "a24f7be44301bd214a51a47868eb5925fbb331a061a9b3d05d5dd88ed8a5fd3e", 2412, 2675, 3786905, 3280936],
  "2024-11-05": [1659093, "740f22d93ca06f321fe76d9658694003b6c9df2d821b267b1ed4edf899b9d763",
    "56305c7b7c84a2a58702e87e4a5dcd176ce50281f62b894b24af0b162a008085", 2219, 2688, 5705861, 4447276],
};

export function northCarolinaPrecinctReference(frame) {
  if (frame?.code !== "NC" || !Object.hasOwn(references, frame.date)) return null;
  const [bytes, sha256, source, shown, records, credits, mapped] = references[frame.date];
  if (source !== frame.historySha || credits !== frame.rows.get("state")?.count) return null;
  return { bytes, sha256, shown, records, credits, mapped };
}

export function installNorthCarolinaPrecinctReference(host, election, getFrame) {
  const details = document.createElement("details"), summary = document.createElement("summary");
  const figure = document.createElement("figure"), caption = document.createElement("figcaption");
  const links = document.createElement("p"), download = document.createElement("a");
  summary.textContent = "Precinct reference map (counts only)";
  figure.style.marginInline = "0";
  caption.setAttribute("role", "status");
  figure.append(caption);
  download.href = "https://github.com/hanshanley/voter-participation/releases/download/"
    + "north-carolina-general-participation-2008-2024/north-carolina-precinct-reference-seven-editions.zip";
  download.textContent = "All reference maps, decision tables and reproduction (ZIP)";
  links.append(download);
  details.append(summary, figure, links);
  host.append(details);
  const number = new Intl.NumberFormat("en-US");
  let generation = 0, asset;
  const load = async () => {
    const token = ++generation;
    figure.querySelector("img")?.remove();
    if (asset) URL.revokeObjectURL(asset);
    asset = undefined;
    if (!details.open) return;
    const frame = getFrame(), reference = northCarolinaPrecinctReference(frame);
    if (!reference) {
      caption.textContent = "No reference map matches this source edition. Use the complete precinct download.";
      return;
    }
    caption.textContent = "Checking the precinct reference map…";
    try {
      const url = new URL(`${frame.date}-precinct-reference.svg.gz`, root);
      const bytes = await checkedCountyBody(url, reference);
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      const image = await new Response(stream, { headers: { "Content-Type": "image/svg+xml" } }).blob();
      if (token !== generation) return;
      asset = URL.createObjectURL(image);
      const img = document.createElement("img");
      img.src = asset;
      img.alt = `North Carolina voter-history credits in the ${frame.date} election, count-only precinct reference`;
      img.width = 960;
      img.height = 445;
      img.style.maxWidth = "100%";
      img.style.height = "auto";
      const covered = `${number.format(reference.shown)} of ${number.format(reference.records)} units shown`;
      caption.textContent = `${covered}; ${number.format(reference.mapped)} of ${number.format(reference.credits)} credits mapped. `
        + "Darker blue indicates more credits, not higher turnout. Gaps are not zero. These are dated reference boundaries."
        + (frame.status === "retained_after_failure" ? " The last verified source edition is retained." : "");
      figure.prepend(img);
    } catch {
      if (token === generation) caption.textContent = "The map could not be verified. The full data and maps remain downloadable.";
    }
  };
  details.addEventListener("toggle", load);
  election.addEventListener("change", load);
}
