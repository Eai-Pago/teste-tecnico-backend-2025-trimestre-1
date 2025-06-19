import { Injectable, OnModuleInit } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createClient, RedisClientType } from 'redis';

@Injectable()
export class RedisService implements OnModuleInit {
  private redisClient: RedisClientType;

  constructor(private readonly configService: ConfigService) {}

  async onModuleInit() {
    this.redisClient = await this.connectToRedis();
  }

  private async connectToRedis(): Promise<RedisClientType> {
    return (await createClient({
      url: this.configService.get<string>('REDIS_URL'),
    }).connect()) as RedisClientType;
  }

  async get(key: string) {
    return await this.redisClient.get(key);
  }

  async getTtl(key: string) {
    return await this.redisClient.ttl(key);
  }

  async getAllKeys(key: string) {
    return await this.redisClient.keys(key);
  }

  async set(key: string, value: string, ttl: number) {
    return await this.redisClient.set(key, value, {
      EX: ttl,
    });
  }

  async del(key: string) {
    return await this.redisClient.del(key);
  }

  async sAdd(myset: string, value: string) {
    return await this.redisClient.sAdd(myset, value);
  }

  async sIsMember(myset: string, value: string) {
    return await this.redisClient.sIsMember(myset, value);
  }

  async sRem(myset: string, value: string) {
    return await this.redisClient.sRem(myset, value);
  }

  public async revokeToken(userId: number) {
    await this.redisClient.del(`auth-token-${userId}`);
  }
}
