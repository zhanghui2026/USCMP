import { useEffect, useState } from 'react';
import { Card, Tag, Empty, Typography, Spin, Descriptions, Statistic, Row, Col, Alert } from 'antd';
import { getDataCoverage, getMemberHoldings } from '../api/client';
import type { HoldingsResponse, HoldingAssetRecord, DataSourceCoverage } from '../api/types';

const { Text } = Typography;

interface Props {
  memberId: string;
}

const ASSET_TYPE_COLORS: Record<string, string> = {
  stock: 'blue',
  bond: 'green',
  fund: 'purple',
  real_estate: 'orange',
  other: 'default',
};

const ASSET_TYPE_LABELS: Record<string, string> = {
  stock: '股票',
  bond: '债券',
  fund: '基金',
  real_estate: '房地产',
  other: '其他',
};

export default function HoldingsTab({ memberId }: Props) {
  const [data, setData] = useState<HoldingsResponse | null>(null);
  const [coverage, setCoverage] = useState<DataSourceCoverage | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHoldings();
  }, [memberId]);

  const loadHoldings = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await getMemberHoldings(memberId, { limit: 100 });
      setData(result);
      getDataCoverage().then((cov) => {
        setCoverage(cov.sources.find((s) => s.source_id === 'holdings') || null);
      }).catch(() => {});
    } catch (err) {
      setError('加载持股数据失败');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <Spin style={{ display: 'flex', justifyContent: 'center', padding: 40 }} />;
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#ef4444' }}>
        {error}
      </div>
    );
  }

  if (!data || data.holdings.length === 0) {
    return (
      <div>
        {coverage && <CoverageNotice coverage={coverage} />}
        <Empty description="暂无持股披露数据" image={Empty.PRESENTED_IMAGE_SIMPLE} />
        <div style={{ marginTop: 12, fontSize: 11, color: '#6b7280', textAlign: 'center' }}>
          持股披露数据需通过 Congressional Financial Disclosure 导入。
        </div>
      </div>
    );
  }

  const { holdings, summary, disclaimer } = data;

  return (
    <div>
      {coverage && <CoverageNotice coverage={coverage} />}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Statistic
            title="资产总数"
            value={summary.total_assets}
            valueStyle={{ color: '#e5e7eb', fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="资产类型"
            value={Object.keys(summary.by_asset_type).length}
            valueStyle={{ color: '#e5e7eb', fontSize: 20 }}
          />
        </Col>
        <Col span={8}>
          <Statistic
            title="披露年份"
            value={Object.keys(summary.by_year).length}
            valueStyle={{ color: '#e5e7eb', fontSize: 20 }}
          />
        </Col>
      </Row>

      {Object.keys(summary.by_asset_type).length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <Text style={{ color: '#9ca3af', fontSize: 11, marginBottom: 8, display: 'block' }}>
            资产类型分布:
          </Text>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {Object.entries(summary.by_asset_type).map(([type, count]) => (
              <Tag key={type} color={ASSET_TYPE_COLORS[type] || 'default'}>
                {ASSET_TYPE_LABELS[type] || type}: {count}
              </Tag>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 16 }}>
        <Text style={{ color: '#9ca3af', fontSize: 11, marginBottom: 8, display: 'block' }}>
          持股明细:
        </Text>
        {holdings.map((item: HoldingAssetRecord) => (
          <Card
            key={item.id}
            size="small"
            style={{ marginBottom: 8, background: '#1a1a2e' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
              <div style={{ flex: 1 }}>
                <Text strong style={{ color: '#d1d5db', fontSize: 13, display: 'block' }}>
                  {item.asset_name}
                </Text>
                {item.ticker && (
                  <Tag color="blue" style={{ fontSize: 10, marginTop: 4 }}>
                    {item.ticker}
                  </Tag>
                )}
              </div>
              <Tag color={ASSET_TYPE_COLORS[item.asset_type] || 'default'}>
                {ASSET_TYPE_LABELS[item.asset_type] || item.asset_type}
              </Tag>
            </div>

            <Descriptions size="small" column={2} style={{ marginTop: 8 }}>
              <Descriptions.Item label="金额区间">
                <Text style={{ color: '#fbbf24', fontSize: 12 }}>
                  {item.value_range_label || `$${(item.value_min || 0).toLocaleString()} - $${(item.value_max || 0).toLocaleString()}`}
                </Text>
              </Descriptions.Item>
              {item.filing_year && (
                <Descriptions.Item label="披露年份">
                  <Text style={{ color: '#d1d5db', fontSize: 12 }}>{item.filing_year}</Text>
                </Descriptions.Item>
              )}
              <Descriptions.Item label="来源">
                <Text style={{ color: '#9ca3af', fontSize: 11 }}>{item.source}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="可靠性">
                <Tag color={item.source_reliability === 'official' ? 'green' : 'orange'} style={{ fontSize: 10 }}>
                  {item.source_reliability}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        ))}
      </div>

      <div style={{ marginTop: 16, padding: '8px 12px', background: '#111827', borderRadius: 6 }}>
        <Text style={{ color: '#6b7280', fontSize: 11 }}>
          {disclaimer}
        </Text>
      </div>
    </div>
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
