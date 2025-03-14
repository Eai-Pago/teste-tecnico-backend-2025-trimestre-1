import express from 'express';
import { writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import multer, { memoryStorage } from 'multer';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const uploadDir = join(__dirname, '..', 'uploads');
if (!existsSync(uploadDir)) {
  mkdirSync(uploadDir);
}

const upload = multer({
  storage: memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    if (file.mimetype.startsWith('video/')) {
      cb(null, true);
    } else {
      cb(new Error('Arquivo não é um vídeo'), false);
    }
  },
});

export default function createUploadRouter(redisClient) {
  const router = express.Router();

  router.post('/video', upload.single('video'), async (req, res) => {
    try {
      if (!req.file) {
        return res.status(400).send('Arquivo inválido ou não enviado.');
      }

      const file = req.file;
      const fileName = file.originalname;

      await redisClient.set(`video:file:${fileName}`, file.buffer.toString('base64'), { EX: 3600 });

      const savePath = join(uploadDir, fileName);
      setImmediate(() => {
        writeFileSync(savePath, file.buffer);
        console.log(`Arquivo salvo em disco: ${savePath}`);
      });

      return res.sendStatus(204);
    } catch (err) {
      console.error('Erro no upload:', err);
      return res.status(500).send('Falha no upload: ' + err.message);
    }
  });

  return router;
}