export default function createCacheMiddleware(redisClient) {
  return async (req, res, next) => {
    try {
      const { filename } = req.params;
      if (!filename) {
        return next();
      }

      const cacheKey = `video:file:${filename}`;
      const cachedVideo = await redisClient.get(cacheKey);
      
      if (cachedVideo) {
        console.log('🚀 Servindo vídeo diretamente do cache (Redis)');
        const videoBuffer = Buffer.from(cachedVideo, 'base64');
        
        res.writeHead(200, {
          'Content-Length': Buffer.byteLength(videoBuffer),
          'Content-Type': 'video/mp4',
        });
        return res.end(videoBuffer);
      }

      next();
    } catch (error) {
      console.error('Erro no middleware de cache:', error);
      next();
    }
  };
}
