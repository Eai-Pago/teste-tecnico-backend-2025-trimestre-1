import { Module } from '@nestjs/common';
import { SequelizeModule } from '@nestjs/sequelize';
import { VideoController } from './video.controller';
import { VideoService } from './video.service';
import { Video } from './video.entity';
import { VideoRepository } from './video.repository';
import { RedisService } from 'src/integrations/redis/redis.service';

@Module({
  imports: [SequelizeModule.forFeature([Video])],
  controllers: [VideoController],
  providers: [VideoService, VideoRepository, RedisService],
})
export class VideoModule {}
