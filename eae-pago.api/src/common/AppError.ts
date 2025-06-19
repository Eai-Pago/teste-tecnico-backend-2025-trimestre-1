import { HttpException, HttpStatus } from '@nestjs/common';
import { OperationErrors } from './enums/OperationErrors.enum';

export class AppError extends Error {
  public readonly name: OperationErrors;
  public readonly httpCode: HttpStatus;
  public readonly isOperational: boolean;
  public readonly description: string;

  constructor(
    name: OperationErrors,
    httpCode: HttpStatus,
    description: string,
    isOperational: boolean,
  ) {
    super(description);
    Object.setPrototypeOf(this, new.target.prototype);

    this.name = name;
    this.httpCode = httpCode;
    this.description = description;
    this.isOperational = isOperational;

    Error.captureStackTrace(this);

    throw new HttpException(
      {
        message: this.description,
      },
      this.httpCode,
      {},
    );
  }
}
