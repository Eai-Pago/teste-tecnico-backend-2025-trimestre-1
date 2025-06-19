import {
  Controller,
  Get,
  HttpStatus,
  Param,
  Post,
  Query,
  Res,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { VideoService } from './video.service';
import { FileInterceptor } from '@nestjs/platform-express';
import { Response } from 'express';
import { QueryParamsDTO } from './dto/queryParams.dto';

@Controller('/upload')
export class VideoController {
  constructor(private readonly videoService: VideoService) {}

  @UseInterceptors(FileInterceptor('file'))
  @Post('/video')
  async createVideo(
    @UploadedFile() file: Express.Multer.File,
    @Res() res: Response,
  ) {
    const data = await this.videoService.createVideo(file);

    res.status(HttpStatus.NO_CONTENT).json({ data });
  }

  @UseInterceptors(FileInterceptor('file'))
  @Get('/static/video/:filename')
  async findByKey(
    @Param('filename') filename: string,
    @Query() { page, limit }: QueryParamsDTO,
    @Res() res: Response,
  ) {
    const data = await this.videoService.findByKey(filename, limit, page);

    if (data && data['status'] === HttpStatus.OK) {
      res.status(HttpStatus.OK).json(data);
      return;
    }

    res.status(HttpStatus.PARTIAL_CONTENT).json(data);
  }
}
