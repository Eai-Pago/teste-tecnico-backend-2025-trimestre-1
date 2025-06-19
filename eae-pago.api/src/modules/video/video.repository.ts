import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/sequelize';
import { Video } from './video.entity';

@Injectable()
export class VideoRepository {
  constructor(
    @InjectModel(Video)
    private readonly videoModel: typeof Video,
  ) {}

  async create(file: string): Promise<Video> {
    return await this.videoModel.create({
      file,
      createdAt: new Date(),
      updatedAt: new Date(),
    } as Video);
  }

  async findOne(videoId: number): Promise<Video | null> {
    return await this.videoModel.findOne({ where: { id: videoId } });
  }

  async findAll(offset: number, limit: number): Promise<Video[]> {
    return await this.videoModel.findAll({
      offset,
      limit,
      order: [['createdAt', 'DESC']],
    });
  }

  async delete(videoId: number): Promise<number> {
    return await this.videoModel.destroy({ where: { id: videoId } });
  }
}
