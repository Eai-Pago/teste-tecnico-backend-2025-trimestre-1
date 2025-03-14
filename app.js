import express from 'express';
import createUploadRouter from './controllers/uploadController.js';
import createStreamRouter from './controllers/streamController.js';
import createCacheMiddleware from './middlewares/cacheMiddleware.js';
import { createClient } from 'redis';

const app = express();

(async () => {
  try {
    const redisClient = createClient({ url: `redis://${process.env.REDIS_HOST || 'localhost'}:6379` });
    redisClient.on('error', (err) => console.error('Redis Client Error:', err));
    await redisClient.connect();
    
    const uploadRouter = createUploadRouter(redisClient);
    const streamRouter = createStreamRouter(redisClient);
    const cacheMiddleware = createCacheMiddleware(redisClient);

    app.use('/upload', uploadRouter);
    app.use('/static', cacheMiddleware, streamRouter);
    
    console.log('🚀 Redis conectado e app configurado');
  } catch (error) {
    console.error('Erro ao conectar ao Redis:', error);
    process.exit(1);
  }
})();

export default app;
