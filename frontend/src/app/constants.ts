export const PARTY_COLORS: Record<string, string> = {
  Democratic: '#1890ff',
  Democrat: '#1890ff',
  Republican: '#f5222d',
  Independent: '#8c8c8c',
};

export const DATA_MODE_COLORS: Record<string, string> = {
  mock: 'orange',
  mixed: 'blue',
  real: 'green',
  real_sandbox: 'cyan',
  unknown: 'default',
};

export const DATA_MODE_LABELS: Record<string, string> = {
  mock: 'Mock 数据',
  mixed: '混合数据',
  real: '真实数据',
  real_sandbox: 'Real+Sandbox',
  unknown: '未知',
};

export const DATA_MODE_TOOLTIPS: Record<string, string> = {
  mock: '当前展示数据均为 Mock 生成数据，仅供演示',
  mixed: '当前同时包含 Mock 演示数据与真实国会议员数据',
  real: '当前展示数据来源于真实数据源',
  real_sandbox: '当前展示真实数据及沙盒数据',
  unknown: '数据模式未知',
};

export function getPartyColor(party?: string): string {
  return PARTY_COLORS[party || ''] || '#8c8c8c';
}
