import {
  Controller,
  Get,
  HttpStatus,
  Param,
  Post,
  Query,
  Req,
  Res,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { VideoService } from './video.service';
import { FileInterceptor } from '@nestjs/platform-express';
import { Request, Response } from 'express';
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
    @Req() req: Request,
    @Param('filename') filename: string,
    @Query() { page, limit }: QueryParamsDTO,
    @Res() res: Response,
  ) {
    const data = await this.videoService.findByKey(
      filename,
      req.headers['range'] as string,
    );

    res.status(HttpStatus.PARTIAL_CONTENT).json(data);
  }
}
