import { Module } from '@nestjs/common';
import { VideoController } from './video.controller';
import { VideoService } from './video.service';
import { RedisService } from 'src/integrations/redis/redis.service';

@Module({
  imports: [],
  controllers: [VideoController],
  providers: [VideoService, RedisService],
})
export class VideoModule {}
