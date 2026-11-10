import type { APIRoute } from 'astro';
import { gzipSync } from 'node:zlib';
import { loadAdditionalParticipation } from '../../../scripts/additional-participation.mjs';

export function getStaticPaths() {
	const data = loadAdditionalParticipation({ nativeCountyParents: true });
	return [...new Set([...data.counties.map(row => row.state_code), ...Object.keys(data.county_frames || {})])].map(state => ({
		params: { state },
		props: {
			counties: data.counties.filter(row => row.state_code === state),
			precincts: data.precincts.filter(row => row.state_code === state),
			nongeographic: data.nongeographic.filter(row => row.state_code === state),
			county_frames: data.county_frames?.[state],
		},
	}));
}

export const GET: APIRoute = ({ props }) => new Response(new Uint8Array(gzipSync(JSON.stringify(props))), {
	headers: { 'Content-Type': 'application/gzip' },
});
