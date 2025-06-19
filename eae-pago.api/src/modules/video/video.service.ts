import { Injectable, HttpStatus } from '@nestjs/common';
import { AppError } from 'src/common/AppError';
import { OperationErrors } from 'src/common/enums/OperationErrors.enum';
import { RedisService } from 'src/integrations/redis/redis.service';

@Injectable()
export class VideoService {
  constructor(private readonly redisService: RedisService) {}

  async createVideo(file: Express.Multer.File) {
    const maxSizeInBytes = 10 * 1024 * 1024;

    if (file.size > maxSizeInBytes)
      throw new AppError(
        OperationErrors.BAD_REQUEST,
        HttpStatus.BAD_REQUEST,
        'Arquivo deve ter no máximo 10MB',
        false,
      );

    const allowedMimeTypes = [
      'video/mp4',
      'video/mpeg',
      'video/ogg',
      'video/webm',
      'video/quicktime',
      'video/x-msvideo',
    ];

    if (!allowedMimeTypes.includes(file.mimetype))
      throw new AppError(
        OperationErrors.BAD_REQUEST,
        HttpStatus.BAD_REQUEST,
        'Arquivo deve ser um vídeo válido (mp4, mpeg, ogg, webm, mov, avi)',
        false,
      );

    const regexToRemoveExtension =
      /\.(mp4|mpeg|ogg|webm|quicktime|x-msvideo)/gi;

    return await this.redisService.set(
      `video-${file.originalname.replace(regexToRemoveExtension, '')}`,
      file.buffer.toString('base64'),
      60,
    );
  }

  public async findByKey(filename: string, range: string) {
    const existingVideo = await this.redisService.get(`video-${filename}`);

    if (!existingVideo)
      throw new AppError(
        OperationErrors.NOT_FOUND,
        HttpStatus.NOT_FOUND,
        'Vídeo não encontrado',
        false,
      );

    if (!range) {
      return existingVideo
    }

    const buffer = Buffer.from(existingVideo, 'base64');
    const fileSize = buffer.length;

    const parts = range.replace(/bytes=/, '').split('-');
    const start = parseInt(parts[0], 10);
    const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;

    if (start >= fileSize || end >= fileSize)
      throw new AppError(
        OperationErrors.INTERNAL_SERVER_ERROR,
        HttpStatus.INTERNAL_SERVER_ERROR,
        'Formato inválido',
        false,
      );

    const chunk = buffer.subarray(start, end + 1);

    return chunk;
  }
}
