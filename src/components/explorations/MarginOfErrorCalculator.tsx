import { useId, useMemo, useState } from 'react';

const confidenceLevels = [
	{ label: '90%', z: 1.645 },
	{ label: '95%', z: 1.96 },
	{ label: '99%', z: 2.576 },
];

export default function MarginOfErrorCalculator() {
	const sampleId = useId();
	const proportionId = useId();
	const confidenceId = useId();
	const [sampleSize, setSampleSize] = useState(1000);
	const [proportion, setProportion] = useState(50);
	const [confidenceIndex, setConfidenceIndex] = useState(1);

	const result = useMemo(() => {
		const boundedSample = Math.max(1, sampleSize);
		const p = Math.min(100, Math.max(0, proportion)) / 100;
		return confidenceLevels[confidenceIndex].z * Math.sqrt((p * (1 - p)) / boundedSample) * 100;
	}, [confidenceIndex, proportion, sampleSize]);

	return (
		<div className="calculator">
			<div className="calculator-inputs">
				<label htmlFor={sampleId}>
					<span>Sample size</span>
					<input
						id={sampleId}
						type="number"
						min="1"
						step="1"
						value={sampleSize}
						onChange={(event) => setSampleSize(Number(event.target.value))}
					/>
				</label>
				<label htmlFor={proportionId}>
					<span>Observed proportion</span>
					<span className="input-suffix">
						<input
							id={proportionId}
							type="number"
							min="0"
							max="100"
							step="1"
							value={proportion}
							onChange={(event) => setProportion(Number(event.target.value))}
						/>
						<i>%</i>
					</span>
				</label>
				<label htmlFor={confidenceId}>
					<span>Confidence level</span>
					<select
						id={confidenceId}
						value={confidenceIndex}
						onChange={(event) => setConfidenceIndex(Number(event.target.value))}
					>
						{confidenceLevels.map((level, index) => (
							<option value={index} key={level.label}>
								{level.label}
							</option>
						))}
					</select>
				</label>
			</div>
			<div className="calculator-result" aria-live="polite">
				<p>Approximate margin</p>
				<strong>±{result.toFixed(1)} points</strong>
				<div className="interval" aria-hidden="true">
					<span style={{ left: `${Math.max(0, proportion - result)}%` }} />
					<i style={{ left: `${proportion}%` }} />
					<span style={{ left: `${Math.min(100, proportion + result)}%` }} />
				</div>
				<small>
					Normal approximation; design effects, weighting, and nonresponse are not included.
				</small>
			</div>
		</div>
	);
}
