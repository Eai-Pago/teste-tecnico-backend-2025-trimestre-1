const REDIS_HOST = process.env.REDIS_HOST || 'localhost';
const redisClient = redis.createClient({ url: `redis://${REDIS_HOST}:6379` });
redisClient.on('error', err => console.error('Redis error:', err));

redisClient.connect();