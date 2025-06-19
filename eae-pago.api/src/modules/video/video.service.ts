import { Injectable, HttpStatus } from '@nestjs/common';
import { AppError } from 'src/common/AppError';
import { OperationErrors } from 'src/common/enums/OperationErrors.enum';
import { RedisService } from 'src/integrations/redis/redis.service';
import { VideoRepository } from './video.repository';

@Injectable()
export class VideoService {
  constructor(
    private readonly redisService: RedisService,
    private readonly videoRepository: VideoRepository,
  ) {}

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

    await this.videoRepository.create(
      file.buffer.toString('base64'),
    );

    return await this.redisService.set(
      `video-${file.originalname.replace(regexToRemoveExtension, '')}`,
      file.buffer.toString('base64'),
      60,
    );
  }

  public async findByKey(filename: string, limit?: number, page?: number) {
    if (limit && page) {
      const offset = limit * (page - 1);

      const video = await this.videoRepository.findAll(offset, limit);

      return {
        video,
        status: HttpStatus.PARTIAL_CONTENT,
      };
    }

    const existingVideo = await this.redisService.get(`video-${filename}`);

    if (!existingVideo)
      throw new AppError(
        OperationErrors.NOT_FOUND,
        HttpStatus.NOT_FOUND,
        'Vídeo não encontrado',
        false,
      );

    return {
      video: existingVideo,
      status: HttpStatus.OK,
    };
  }
}
