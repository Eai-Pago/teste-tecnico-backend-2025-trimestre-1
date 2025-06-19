import {
  AutoIncrement,
  Column,
  DataType,
  Model,
  PrimaryKey,
  Table,
} from 'sequelize-typescript';

@Table({ tableName: 'videos', timestamps: true })
export class Video extends Model<Video> {
  @PrimaryKey
  @AutoIncrement
  @Column(DataType.INTEGER)
  public declare id: number;

  @Column({
    type: DataType.TEXT,
    allowNull: false,
  })
  file: string;
}
