import { Bot, Boxes, Brain, Cpu, Database, Layers3, Server, Shield, Terminal } from 'lucide-react';

const ICONS = {
  bot: Bot,
  boxes: Boxes,
  brain: Brain,
  cpu: Cpu,
  database: Database,
  layers: Layers3,
  server: Server,
  shield: Shield,
  terminal: Terminal
};

export default function ProjectMark({ project }) {
  const Icon = ICONS[project?.icon] || Layers3;
  return (
    <span
      className={`project-mark tone-${project?.tone || 'ink'}`}
      title={`${project?.name || project?.id || ''}${project?.direction ? ` · ${project.direction}` : ''}`}
    >
      <Icon size={15} strokeWidth={2.1} aria-hidden="true" />
    </span>
  );
}
