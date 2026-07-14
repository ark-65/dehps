import { Inject, Injectable } from '@nestjs/common';
import { ForwardStateReadRepository } from './forward-state.types';

@Injectable()
export class ForwardStateReadService {
  constructor(
    @Inject('ForwardStateReadRepository')
    private readonly repository: ForwardStateReadRepository,
  ) {}

  async status() {
    return {
      entity: 'forward_state',
      ...(await this.repository.status()),
      writeRoutesEnabled: false,
      productionAccess: false,
    };
  }
}
