import { useEffect, useState } from 'react';
import { Card, Tag, Spin, Empty, Statistic, Row, Col, Table, Typography, Alert } from 'antd';
import { getDataCoverage, getMemberContributions, getMemberFinanceSummary } from '../api/client';
import type {
  ContributionSummary, ContributionsResponse,
  DataSourceCoverage, MemberFinanceSummaryResponse,
} from '../api/types';

const { Text } = Typography;

interface Props {
  memberId: string;
}

function fmt(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(1)}K`;
  return `$${n.toFixed(0)}`;
}

export default function ContributionsTab({ memberId }: Props) {
  const [data, setData] = useState<ContributionsResponse | null>(null);
  const [summary, setSummary] = useState<MemberFinanceSummaryResponse | null>(null);
  const [coverage, setCoverage] = useState<DataSourceCoverage | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [sumRes, cov] = await Promise.all([
          getMemberFinanceSummary(memberId),
          getDataCoverage(),
        ]);
        setSummary(sumRes);
        setCoverage(cov.sources.find((s) => s.source_id === 'fec') || null);

        if (sumRes.total_count > 0) {
          const res = await getMemberContributions(memberId, { limit: 20 });
          setData(res);
        }
      } catch {
        setData(null);
        setSummary(null);
      } finally {
        setLoading(false);
      }
    })();
  }, [memberId]);

  const s = summary ?? data?.summary ?? null;
  const hasData = (s?.total_count ?? 0) > 0 || (summary?.total_count ?? 0) > 0;

  if (loading) return <Spin style={{ display: 'block', margin: '40px auto' }} />;
  if (!hasData) {
    return (
      <div>
        {coverage && <CoverageNotice coverage={coverage} />}
        <Empty description="暂无献金数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        <div style={{ marginTop: 12, fontSize: 11, color: '#6b7280', textAlign: 'center' }}>
          需通过 FEC bulk data 或 OpenSecrets API 导入后方可显示。
        </div>
      </div>
    );
  }

  if (summary && !data) {
    return (
      <div>
        {coverage && <CoverageNotice coverage={coverage} />}
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col span={8}>
            <Card size="small" style={{ background: '#1a1a2e' }}>
              <Statistic title="献金总额" value={summary.total_received} prefix="$" precision={0}
                valueStyle={{ color: '#52c41a', fontSize: 20 }} />
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small" style={{ background: '#1a1a2e' }}>
              <Statistic title="记录笔数" value={summary.total_count}
                valueStyle={{ color: '#1890ff', fontSize: 20 }} />
            </Card>
          </Col>
          <Col span={8}>
            <Card size="small" style={{ background: '#1a1a2e' }}>
              <Statistic title="捐赠方数" value={summary.top_donors.length}
                valueStyle={{ color: '#faad14', fontSize: 20 }} />
            </Card>
          </Col>
        </Row>
        <Alert type="info" showIcon message="已加载聚合汇总"
          description="明细数据仅在需要时按需加载。" style={{ marginBottom: 12, background: '#111827', borderColor: '#374151' }} />
        {s && renderDonorAndIndustry(s)}
        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 8, fontStyle: 'italic' }}>
          {summary.updated_at ? `汇总更新时间: ${summary.updated_at}` : ''}
        </div>
      </div>
    );
  }

  if (!s) {
    return (
      <div>
        {coverage && <CoverageNotice coverage={coverage} />}
        <Empty description="暂无献金数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <div>
      {coverage && <CoverageNotice coverage={coverage} />}
      <Row gutter={12} style={{ marginBottom: 12 }}>
        <Col span={8}>
          <Card size="small" style={{ background: '#1a1a2e' }}>
            <Statistic title="献金总额" value={s.total_received} prefix="$" precision={0}
              valueStyle={{ color: '#52c41a', fontSize: 20 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ background: '#1a1a2e' }}>
            <Statistic title="记录笔数" value={s.total_count}
              valueStyle={{ color: '#1890ff', fontSize: 20 }} />
          </Card>
        </Col>
        <Col span={8}>
          <Card size="small" style={{ background: '#1a1a2e' }}>
            <Statistic title="竞选委员会" value={data?.committees?.length ?? 0}
              valueStyle={{ color: '#faad14', fontSize: 20 }} />
          </Card>
        </Col>
      </Row>

      <Card size="small" title="竞选委员会" style={{ marginBottom: 8, background: '#1a1a2e' }}>
        {data?.committees?.map((cm) => (
          <div key={cm.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, fontSize: 11 }}>
            <span style={{ color: '#d1d5db', fontWeight: 600 }}>{cm.name}</span>
            <Tag style={{ fontSize: 10, margin: 0 }}>{cm.fec_committee_id}</Tag>
            {cm.party && <Tag color={cm.party === 'Republican' ? 'red' : cm.party === 'Democratic' ? 'blue' : 'default'} style={{ fontSize: 10, margin: 0 }}>{cm.party}</Tag>}
            <span style={{ color: '#6b7280' }}>{cm.state} | 第{cm.cycle}届</span>
          </div>
        ))}
      </Card>

      {Object.keys(s.by_cycle).length > 0 && (
        <Card size="small" title="按选举周期" style={{ marginBottom: 8, background: '#1a1a2e' }}>
          {Object.entries(s.by_cycle).map(([cycle, amount]) => (
            <div key={cycle} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11 }}>
              <span style={{ color: '#9ca3af' }}>{cycle} 届</span>
              <span style={{ color: '#d1d5db' }}>{fmt(amount)}</span>
            </div>
          ))}
        </Card>
      )}

      {Object.keys(s.by_type).length > 0 && (
        <Card size="small" title="按献金类型" style={{ marginBottom: 8, background: '#1a1a2e' }}>
          {Object.entries(s.by_type).map(([type, amount]) => (
            <div key={type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11 }}>
              <Tag style={{ fontSize: 10 }}>{type === 'individual' ? '个人' : type === 'pac' ? 'PAC' : type === 'party' ? '政党' : type}</Tag>
              <span style={{ color: '#d1d5db' }}>{fmt(amount)}</span>
            </div>
          ))}
        </Card>
      )}

      {renderDonorAndIndustry(s)}

      <div style={{ fontSize: 10, color: '#6b7280', marginTop: 8, fontStyle: 'italic' }}>
        {data?.disclaimer}
      </div>
    </div>
  );
}

function renderDonorAndIndustry(s: ContributionSummary | MemberFinanceSummaryResponse) {
  const donors = s.top_donors.map((d) => ({
    name: d.name ?? '未知',
    total: d.total ?? 0,
    count: d.count ?? 0,
    type: d.type ?? 'unknown',
  }));

  return (
    <>
      {donors.length > 0 && (
        <Card size="small" title="TOP 捐赠方" style={{ marginBottom: 8, background: '#1a1a2e' }}>
          <Table
            dataSource={donors}
            columns={[
              { title: '捐赠方', dataIndex: 'name', key: 'name', render: (v: string) => <Text style={{ color: '#d1d5db', fontSize: 12 }}>{v}</Text> },
              { title: '类型', dataIndex: 'type', key: 'type', render: (v: string) => <Tag style={{ fontSize: 10 }}>{v}</Tag> },
              { title: '总额', dataIndex: 'total', key: 'total', render: (v: number) => <span style={{ color: '#52c41a', fontSize: 12 }}>{fmt(v)}</span> },
              { title: '笔数', dataIndex: 'count', key: 'count', render: (v: number) => <span style={{ color: '#9ca3af', fontSize: 12 }}>{v}</span> },
            ]}
            rowKey="name"
            pagination={false}
            size="small"
            style={{ background: 'transparent' }}
          />
        </Card>
      )}

      {s.top_industries.length > 0 && (
        <Card size="small" title="TOP 行业来源" style={{ marginBottom: 8, background: '#1a1a2e' }}>
          {s.top_industries.map((ind) => (
            <div key={ind.industry} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 11 }}>
              <span style={{ color: '#9ca3af' }}>{ind.industry}</span>
              <span style={{ color: '#d1d5db' }}>{fmt(ind.total ?? 0)}（{ind.count}笔）</span>
            </div>
          ))}
        </Card>
      )}
    </>
  );
}

function CoverageNotice({ coverage }: { coverage: DataSourceCoverage }) {
  const statusLabel: Record<string, string> = {
    full: '全量',
    partial: '部分导入',
    sample: '样本数据',
    subset: '结构化子集',
  };
  return (
    <Alert
      type={coverage.status === 'full' ? 'success' : 'warning'}
      showIcon
      message={`数据覆盖: ${statusLabel[coverage.status] || coverage.status}`}
      description={coverage.note}
      style={{ marginBottom: 12, background: '#111827', borderColor: '#374151' }}
    />
  );
}
