import type { CollectionEntry } from 'astro:content';

export function comparePostsNewestFirst(
	a: CollectionEntry<'posts'>,
	b: CollectionEntry<'posts'>,
) {
	const aDate = a.data.publishedAt?.valueOf();
	const bDate = b.data.publishedAt?.valueOf();

	if (aDate !== undefined && bDate !== undefined) return bDate - aDate;
	if (aDate !== undefined) return -1;
	if (bDate !== undefined) return 1;

	return (b.data.archiveOrder ?? 0) - (a.data.archiveOrder ?? 0);
}
