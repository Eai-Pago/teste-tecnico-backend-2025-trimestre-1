import express from 'express';
import path from 'path';
import fs from 'fs';
import { cache } from '../services/cacheService.js';

const router = express.Router();

router.get('/video/:filename', async (req, res) => {
  const { filename } = req.params;
  const videoPath = path.join(process.env.VIDEO_STORAGE_PATH, filename);
  const cacheKey = `video:${filename}`; // Corrigido

  let videoBuffer = cache.get(cacheKey);

  if (!videoBuffer && !fs.existsSync(videoPath)) {
    return res.status(404).send('Arquivo não encontrado.');
  }

  if (!videoBuffer) {
    try {
      videoBuffer = await fs.promises.readFile(videoPath);
      cache.set(cacheKey, videoBuffer);
    } catch (err) {
      return res.status(500).send('Erro ao ler o vídeo.');
    }
  }

  const range = req.headers.range;
  const total = videoBuffer.length;

  if (range) {
    const match = range.match(/bytes=(\d+)-(\d*)/);
    if (!match) {
      return res.status(416).send('Range inválido');
    }

    const start = parseInt(match[1], 10);
    const end = match[2] ? parseInt(match[2], 10) : total - 1;

    if (start >= total || end >= total) {
      return res.status(416).send('Range fora do limite do vídeo.');
    }

    const chunk = videoBuffer.slice(start, end + 1);

    res.status(206).set({
      'Content-Range': `bytes ${start}-${end}/${total}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunk.length,
      'Content-Type': 'video/mp4',
    });

    return res.end(chunk);
  }

  res.status(200).set({
    'Content-Length': total,
    'Content-Type': 'video/mp4',
  });

  return res.end(videoBuffer);
});

export default router;
