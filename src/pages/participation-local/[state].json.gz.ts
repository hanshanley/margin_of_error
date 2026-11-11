import type { APIRoute } from 'astro';
import { loadCountPublication, legacyCountExport } from '../../../scripts/participation-count-publication.mjs';

export function getStaticPaths() {
	return loadCountPublication().metadata.additional_states.map((state: string) => ({
		params: { state },
		props: { state },
	}));
}

export const GET: APIRoute = ({ props }) => new Response(new Uint8Array(legacyCountExport(props.state)), {
	headers: { 'Content-Type': 'application/gzip' },
});
