import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import { comparePostsNewestFirst, getPostPath } from '../lib/posts';

export async function GET(context) {
	const posts = (await getCollection('posts', ({ data }) => !data.draft)).sort(comparePostsNewestFirst);

	return rss({
		title: 'The Margin of Error',
		description: 'Essays, evidence, and computational detours by Hans W. A. Hanley.',
		site: context.site,
		items: posts.map((post) => ({
			title: post.data.title,
			description: post.data.description,
			pubDate: post.data.publishedAt,
			link: getPostPath(post),
		})),
	});
}
