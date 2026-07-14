import { Controller, Get, Inject } from '@nestjs/common';
import { ForwardStateReadService } from './forward-state.service';

@Controller('forward-state')
export class ForwardStateController {
  constructor(@Inject(ForwardStateReadService) private readonly service: ForwardStateReadService) {}

  @Get()
  status() {
    return this.service.status();
  }
}
