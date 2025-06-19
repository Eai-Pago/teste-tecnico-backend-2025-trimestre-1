import {  IsOptional, IsString } from 'class-validator';

export class QueryParamsDTO {
  @IsString()
  @IsOptional()
  public page?: number;

  @IsString()
  @IsOptional()
  public limit?: number;
}
