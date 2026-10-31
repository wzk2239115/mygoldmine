import { COLUMNS } from './constants.js';

export const RAW_STAGE = {
  id: 'raw',
  code: 'RAW',
  label: '原矿',
  hint: '原始池；已归档只计入顶部统计，不在这里展开'
};

export function stageMeta(stage) {
  if (stage === 'raw') return RAW_STAGE;
  return COLUMNS.find((column) => column.id === stage) || RAW_STAGE;
}

export function stageCount(stats, stage) {
  if (stage === 'raw') return stats?.status?.inbox ?? 0;
  if (stage === 'review') return stats?.reviewReady ?? 0;
  return stats?.status?.[stage] ?? 0;
}

export function filterStageFindings(findings, stage) {
  return findings.filter((finding) => {
    if (stage === 'review') return Boolean(finding.reviewReady);
    if (finding.reviewReady) return false;
    if (stage === 'raw') return finding.status === 'inbox';
    return finding.status === stage;
  });
}
