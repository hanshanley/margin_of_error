import { readFileSync } from 'node:fs';

export interface PlatformFigure {
	view: string;
	name: string;
	path: string;
	display_path?: string;
	width: number;
	height: number;
}

interface Share {
	view: string;
	group: string;
	available: string;
	share: string;
	claims: string;
}

interface Claim {
	claim_id: string;
	group: string;
	claim_text: string;
	title: string;
	publication_date: string;
	source_url: string;
	locator: string;
	evidence: string;
}

interface Topic {
	topic_id: string;
	title: string;
	summary: string;
	caveat: string;
	label_origin: string;
	review_status: string;
	shares: Share[];
	representatives: Claim[];
}

interface PeriodFit {
	period: string;
	period_start: number;
	topics: number;
	claims: number;
	documents: number;
	groups_present: string[];
	fit: {
		selected_parameters: { method: string; coverage: number; cosine_silhouette: number };
	};
}

interface DensityRegion {
	view: string;
	pair: string;
	figure: string;
	marker: string;
	terms: string;
	passages: string;
	bundles: string;
	example_text: string;
	example_title: string;
	example_publication_date: string;
	example_log_density_ratio: string;
	source_url: string;
	locator: string;
}

interface Publication {
	preview_only?: boolean;
	source_revision: string;
	summary: {
		claims: number;
		claims_by_group: Record<string, number>;
		documents_by_group: Record<string, number>;
		bundles_by_group: Record<string, number>;
		corpus: { assistant_source_repaired_blocks: number };
		views: Record<string, { dimensions: number; group_passages: Record<string, number> }>;
	};
	topic_summary: { assistant_revised_labels: number };
	topics: Topic[];
	figures: PlatformFigure[];
	density_regions: DensityRegion[];
	downloads: { path: string; bytes: number }[];
	evolution: {
		summary: { topics: number; reviewed_labels: number };
		periods: PeriodFit[];
		topics: Topic[];
	} | null;
}

export const platforms: Publication = JSON.parse(
	readFileSync('public/party-platforms/analysis.json', 'utf8'),
);
export const platformRepository = `https://github.com/hanshanley/dsa/tree/${platforms.source_revision}`;
export const organizations = [
	{ id: 'democratic', name: 'Democratic Party' },
	{ id: 'republican', name: 'Republican Party' },
	{ id: 'dsa', name: 'Democratic Socialists of America' },
];
export const platformFigure = (view: string, name: string) => {
	const figure = platforms.figures.find((entry) => entry.view === view && entry.name === name);
	if (!figure) throw new Error(`Missing platform figure: ${view}/${name}`);
	return figure;
};
export const initialIssue = platforms.topics.find(topic => topic.title.includes('Labor Rights')) ??
	platforms.topics[0];
export const platformCover = {
	src: '/artifacts/party-platforms/three-platform-booklets-one-conversation.png',
	alt: 'Illustration of Democratic, Republican, and DSA platform booklets linked by strips of text.',
	width: 1672,
	height: 941,
};
