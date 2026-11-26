import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { issueLabel, positionReadout, caucusLabel } from '../src/lib/platform-display.mjs';

const parties = JSON.parse(readFileSync('public/party-platforms/analysis.json', 'utf8'));
const caucuses = JSON.parse(readFileSync('public/party-platforms/caucuses/analysis.json', 'utf8'));

test('every original national issue has a unique concise alias and three additive readouts', () => {
  const before = JSON.stringify(parties);
  const labels = parties.topics.map(topic => {
    const label = issueLabel(topic.topic_id);
    assert.ok(label.length < topic.title.length || label === topic.title);
    const position = parties.positions.find(row => row.topic_id === topic.topic_id);
    for (const group of ['democratic', 'republican', 'dsa']) {
      assert.ok(position.groups[group].summary.length > 0);
      assert.ok(positionReadout(topic.topic_id, group).length > 30);
    }
    return label;
  });
  assert.equal(new Set(labels).size, parties.topics.length);
  assert.equal(JSON.stringify(parties), before);
});

test('caucus themes have their own aliases even when national topic IDs overlap', () => {
  const labels = caucuses.topics.map(topic => caucusLabel(topic.id));
  assert.equal(new Set(labels).size, caucuses.topics.length);
  assert.notEqual(caucusLabel('topic-005'), issueLabel('topic-005'));
});

test('unknown subjects and organizations cannot silently borrow a display description', () => {
  assert.throws(() => issueLabel('topic-999'), /Missing issue/);
  assert.throws(() => caucusLabel('topic-999'), /Missing caucus/);
  assert.throws(() => positionReadout('topic-001', 'unknown'), /Missing position/);
});
