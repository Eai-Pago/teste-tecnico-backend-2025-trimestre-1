import express from 'express';
import fs from 'fs';
import path from 'path';

export default function createStreamRouter(redisClient) {
  const router = express.Router();

  router.get('/video/:filename', async (req, res) => {
    const { filename } = req.params;
    const sanitizedFilename = path.basename(filename);
    const cacheKey = `video:file:${sanitizedFilename}`;

    let cachedVideo = await redisClient.get(cacheKey);

    if (cachedVideo) {
      console.log('🚀 Servindo vídeo diretamente do cache (Redis)');
      const videoBuffer = Buffer.from(cachedVideo, 'base64');
      res.writeHead(200, {
        'Content-Length': Buffer.byteLength(videoBuffer),
        'Content-Type': 'video/mp4',
      });
      return res.end(videoBuffer);
    }

    // Caso não exista no cache, busca do disco
    const videoPath = path.resolve('uploads', sanitizedFilename);

    if (!fs.existsSync(videoPath)) {
      return res.sendStatus(404);
    }

    const stat = fs.statSync(videoPath);
    const fileSize = stat.size;
    const range = req.headers.range;

    if (range) {
      const parts = range.replace(/bytes=/, "").split("-");
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

      if (start >= fileSize || end >= fileSize) {
        return res.status(416).send('Requested range not satisfiable');
      }

      const chunkSize = (end - start) + 1;
      const file = fs.createReadStream(videoPath, { start, end });

      const headers = {
        'Content-Range': `bytes ${start}-${end}/${fileSize}`,
        'Accept-Ranges': 'bytes',
        'Content-Length': chunkSize,
        'Content-Type': 'video/mp4',
      };

      res.writeHead(206, headers);
      file.pipe(res);
    } else {
      const headers = {
        'Content-Length': fileSize,
        'Content-Type': 'video/mp4',
      };

      res.writeHead(200, headers);
      fs.createReadStream(videoPath).pipe(res);
    }
  });

  return router;
}
