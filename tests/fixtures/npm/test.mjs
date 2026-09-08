import assert from 'node:assert/strict';
import test from 'node:test';
import { answer } from './source.js';
test('consumer exports the expected value', () => assert.equal(answer, 42));
