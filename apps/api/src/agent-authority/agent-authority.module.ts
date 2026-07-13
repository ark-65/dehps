import { Module } from '@nestjs/common';
import { AgentAuthorityController } from './agent-authority.controller';
import { PostgresAgentRequestReadRepository } from './agent-authority.repository';
import { AgentAuthorityReadService } from './agent-authority.service';

@Module({
  controllers: [AgentAuthorityController],
  providers: [
    AgentAuthorityReadService,
    {
      provide: 'AgentRequestReadRepository',
      useClass: PostgresAgentRequestReadRepository,
    },
  ],
})
export class AgentAuthorityModule {}
