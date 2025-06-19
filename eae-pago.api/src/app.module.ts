import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { VideoModule } from './modules/video/video.module';

@Module({
  imports: [ConfigModule.forRoot({ isGlobal: true }), VideoModule],
  controllers: [],
  providers: [],
})
export class AppModule {}
