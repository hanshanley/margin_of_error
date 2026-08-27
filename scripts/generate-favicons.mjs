import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const source = fileURLToPath(new URL('../public/logo.png', import.meta.url));
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

const socialLogo = await sharp(source)
	.resize(570, 570, { fit: 'contain' })
	.png()
	.toBuffer();

await sharp({
	create: {
		width: 1200,
		height: 630,
		channels: 4,
		background: '#fbf6f3',
	},
})
	.composite([{ input: socialLogo, gravity: 'center' }])
	.png()
	.toFile(fileURLToPath(new URL('../public/social-card.png', import.meta.url)));
