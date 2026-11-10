export function rings(geometry) {
  return geometry.type === "MultiPolygon" ? geometry.coordinates.flat() : geometry.coordinates;
}

export function boundsFor(points) {
  return points.reduce(([x0, y0, x1, y1], [x, y]) =>
    [Math.min(x0, x), Math.min(y0, y), Math.max(x1, x), Math.max(y1, y)], [Infinity, Infinity, -Infinity, -Infinity]);
}

export function conicProjection(meridian, lower, upper) {
  const radians = Math.PI / 180;
  const n = (Math.sin(lower * radians) + Math.sin(upper * radians)) / 2;
  const c = Math.cos(lower * radians) ** 2 + 2 * n * Math.sin(lower * radians);
  return ([lon, lat]) => {
    const theta = n * (((lon - meridian + 540) % 360) - 180) * radians;
    const rho = Math.sqrt(c - 2 * n * Math.sin(lat * radians)) / n;
    return [rho * Math.sin(theta), rho * Math.cos(theta)];
  };
}

export function projectFeatures(features, project, [left, top, width, height]) {
  const projected = features.map(feature => ({ feature, rings: rings(feature.geometry).map(ring => ring.map(project)) }));
  const [x0, y0, x1, y1] = boundsFor(projected.flatMap(item => item.rings.flat()));
  const scale = Math.min(width / (x1 - x0), height / (y1 - y0));
  const ox = left + (width - (x1 - x0) * scale) / 2, oy = top + (height - (y1 - y0) * scale) / 2;
  return projected.map(item => {
    const transformed = item.rings.map(ring => ring.map(([x, y]) => [ox + (x - x0) * scale, oy + (y - y0) * scale]));
    const point = coordinate => {
      const [x, y] = project(coordinate);
      return [ox + (x - x0) * scale, oy + (y - y0) * scale];
    };
    return { feature: item.feature, point, bounds: boundsFor(transformed.flat()),
      d: transformed.map(ring => ring.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join("") + "Z").join("") };
  });
}

export function projectStateContext(features) {
  const items = [];
  for (const [codes, projection, region] of [
    [null, conicProjection(-96, 29.5, 45.5), [25, 20, 950, 500]],
    [["AK"], conicProjection(-154, 55, 65), [60, 465, 200, 125]],
    [["HI"], conicProjection(-157, 8, 18), [310, 525, 120, 65]],
  ]) {
    const selected = features.filter(feature => codes ? codes.includes(feature.properties.STUSAB)
      : !["AK", "HI", "PR", "GU", "VI", "MP", "AS"].includes(feature.properties.STUSAB));
    items.push(...projectFeatures(selected, projection, region));
  }
  return items;
}
