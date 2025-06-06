import express from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';

const router = express.Router();
const MAX_SIZE = 10 * 1024 * 1024;

const storage = multer.memoryStorage(); 
const upload = multer({
  storage,
  fileFilter: (_, file, cb) => {
    if (!file.mimetype.startsWith('video/')) {
      return cb(new Error('Invalid file type'), false);
    }
    cb(null, true);
  }
});

router.post('/video', upload.single('video'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).send('Arquivo inválido.');
    }

    if (req.file.size > MAX_SIZE) {
      return res.status(400).send('Arquivo excede o limite de 10MB.');
    }

    const filename = req.file.originalname;
    const filePath = path.join(process.env.VIDEO_STORAGE_PATH, filename);

    const { cache } = await import('../services/cacheService.js');
    cache.set(`/static/video/${filename}`, req.file.buffer);

    await fs.promises.writeFile(filePath, req.file.buffer);

    return res.sendStatus(204);
  } catch (err) {
    return res.status(400).send(err.message || 'Erro ao fazer upload');
  }
});

export default router;