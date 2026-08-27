import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const source = fileURLToPath(new URL('../public/favicon.svg', import.meta.url));
const outputs = [
	{ size: 32, path: '../public/favicon-32.png' },
	{ size: 180, path: '../public/apple-touch-icon.png' },
];

await Promise.all(
	outputs.map(({ size, path }) =>
		sharp(source)
			.resize(size, size)
			.png()
			.toFile(fileURLToPath(new URL(path, import.meta.url))),
	),
);
