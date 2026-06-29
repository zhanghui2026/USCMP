import { useState } from 'react';
import { Select, Card, Button, Spin, Empty, message, Row, Col, Tag } from 'antd';
import { getMembers, compareMembers } from '../api/client';
import type { MemberSummary, CompareResponse, RadarMetric } from '../api/types';
import { useEffect } from 'react';

export default function ComparePage() {
  const [allMembers, setAllMembers] = useState<MemberSummary[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [result, setResult] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getMembers({ limit: 200 }).then((r) => setAllMembers(r.members));
  }, []);

  const doCompare = async () => {
    if (selectedIds.length < 2) {
      message.warning('请至少选择 2 名议员');
      return;
    }
    setLoading(true);
    try {
      const r = await compareMembers({ member_ids: selectedIds });
      setResult(r);
    } catch (e) {
      message.error('对比失败');
    } finally {
      setLoading(false);
    }
  };

  const getMetricsForMember = (memberId: string): RadarMetric[] => {
    if (!result) return [];
    return result.radar_metrics.filter((m) => m.member_id === memberId);
  };

  const getMetricColor = (name: string) => {
    const colors: Record<string, string> = {
      party_alignment: '#1890ff',
      china_hawkishness: '#f5222d',
      donor_exposure: '#52c41a',
      conflict_risk: '#faad14',
      committee_relevance: '#722ed1',
    };
    return colors[name] || '#8c8c8c';
  };

  const getMetricLabel = (name: string) => {
    const labels: Record<string, string> = {
      party_alignment: '党派一致性',
      china_hawkishness: '涉华立场指数',
      donor_exposure: '金主暴露度',
      conflict_risk: '利益冲突风险',
      committee_relevance: '委员会相关度',
    };
    return labels[name] || name;
  };

  return (
    <div style={{ padding: 24, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 24, marginBottom: 16 }}>多人对比</h1>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={12} align="middle">
          <Col flex="auto">
            <Select
              mode="multiple"
              placeholder="选择议员（至少 2 名）"
              style={{ width: '100%' }}
              value={selectedIds}
              onChange={setSelectedIds}
              maxTagCount={5}
              options={allMembers.map((m) => ({
                value: m.id,
                label: `${m.display_name} (${m.party} - ${m.state})`,
              }))}
            />
          </Col>
          <Col>
            <Button type="primary" onClick={doCompare} loading={loading}>开始对比</Button>
          </Col>
        </Row>
      </Card>

      <Spin spinning={loading}>
        {result && (
          <>
            <Card title="雷达图指标" size="small" style={{ marginBottom: 16 }}>
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #1f2937' }}>
                      <th style={{ padding: 8, textAlign: 'left', color: '#9ca3af' }}>指标</th>
                      {result.members.map((m) => (
                        <th key={m.id} style={{ padding: 8, textAlign: 'center' }}>
                          <div style={{ fontWeight: 600 }}>{m.canonical_name}</div>
                          <div style={{ fontSize: 11, color: '#6b7280' }}>
                            <Tag color={m.party === 'Democratic' ? 'blue' : 'red'}>{m.party}</Tag>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {['party_alignment', 'china_hawkishness', 'donor_exposure', 'conflict_risk', 'committee_relevance'].map((metricName) => (
                      <tr key={metricName} style={{ borderBottom: '1px solid #111827' }}>
                        <td style={{ padding: 8, color: getMetricColor(metricName) }}>
                          {getMetricLabel(metricName)}
                        </td>
                        {result.members.map((m) => {
                          const metric = getMetricsForMember(m.id).find((x) => x.metric_name === metricName);
                          return (
                            <td key={m.id} style={{ padding: 8, textAlign: 'center' }}>
                              <div style={{
                                width: '100%', height: 8, background: '#1f2937', borderRadius: 4, overflow: 'hidden',
                              }}>
                                <div style={{
                                  width: `${metric?.value || 0}%`, height: '100%',
                                  background: getMetricColor(metricName), borderRadius: 4,
                                  transition: 'width 0.3s',
                                }} />
                              </div>
                              <span style={{ fontSize: 11, color: '#9ca3af' }}>{metric?.value?.toFixed(0) || 0}</span>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {result.common_committees.length > 0 && (
              <Card title="共同委员会" size="small" style={{ marginBottom: 16 }}>
                {result.common_committees.map((cc: Record<string, unknown>, i: number) => (
                  <Tag key={i} color="purple" style={{ marginBottom: 4 }}>
                    {cc.committee as string} ({cc.member_count as number}人)
                  </Tag>
                ))}
              </Card>
            )}

            <Card size="small" style={{ background: '#1a1a2e', border: '1px solid #faad14' }}>
              <div style={{ fontSize: 12, color: '#faad14' }}>
                {result.disclaimer}
              </div>
            </Card>
          </>
        )}
      </Spin>
    </div>
  );
}
