import request from 'supertest';
import app from './app.js';

describe('GET /healthz', () => {
  it('responds with 200 and ok', async () => {
    const res = await request(app).get('/healthz');
    expect(res.status).toBe(200);
    expect(res.text).toBe('ok');
  });
});
